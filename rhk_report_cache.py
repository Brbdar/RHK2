"""LRU cache used by report builders, extracted from ``rhk_reports``.

Why this lives in its own module
--------------------------------
- Disabled by default (``RHK_REPORT_CACHE_MAXSIZE`` env), so extracting it
  has zero behavioural risk in normal deployments.
- Caching rendered reports stores patient data in process memory; keeping
  the policy in a single small module makes the privacy implications easier
  to audit.

Public surface
--------------
- ``REPORT_CACHE_MAXSIZE``: integer pulled from the env at import time.
- ``_case_fingerprint(case)``: stable hash for cache keying.
- ``_cache_get(kind, fp)`` / ``_cache_set(kind, fp, value)``: LRU primitives.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional  # noqa: F401

from rhk_case_schema import CaseLike
from rhk_logging import log_exception

__all__ = [
    "REPORT_CACHE_MAXSIZE",
    "_case_fingerprint",
    "_cache_get",
    "_cache_set",
]

# Section keys mirrored from rhk_reports — kept inline (rather than imported
# from rhk_reports) to avoid a circular import. Single source of truth lives
# in rhk_reports; if a key is renamed there, update it here as well.
_K_UI = "ui"
_K_DERIVED = "derived"
_K_SCORES = "scores"
_K_DECISION = "decision"
_K_ENV = "env"
_K_WARNINGS = "warnings"
_K_HFPEF = "hfpef"
_K_DEBUG = "debug"

# WARNING (Datenschutz): Caching rendered reports stores patient data in
# process memory. This is undesirable in multi-user / online deployments.
# Therefore caching is DISABLED by default. Set RHK_REPORT_CACHE_MAXSIZE to
# a positive integer to enable an LRU cache of the given size.
REPORT_CACHE_MAXSIZE: int = int(os.getenv("RHK_REPORT_CACHE_MAXSIZE", "0"))

_report_cache_lock = threading.RLock()
_report_cache: "OrderedDict[tuple, object]" = OrderedDict()


def _case_fingerprint(case: CaseLike) -> str:
    """Stable fingerprint for a case dict.

    Cases are JSON-serializable by design (ui/derived/scores/decision/env/
    warnings/debug). We hash the sorted JSON to keep keys compact and to
    avoid memory blowups.
    """
    if REPORT_CACHE_MAXSIZE <= 0:
        return ""

    if isinstance(case, dict):
        case_for_fp: Dict[str, Any] = {
            "ui": case.get(_K_UI),
            "derived": case.get(_K_DERIVED),
            "scores": case.get(_K_SCORES),
            "decision": case.get(_K_DECISION),
            "env": case.get(_K_ENV),
            "hfpef": case.get(_K_HFPEF),
            "warnings": case.get(_K_WARNINGS),
            "debug": case.get(_K_DEBUG),
        }
    else:
        case_for_fp = case

    try:
        js = json.dumps(case_for_fp, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        log_exception(
            "RHK_REP_FP_SERIALIZE",
            "Case fingerprint fallback serialization used.",
            exc,
        )
        js = str(case_for_fp)
    return hashlib.blake2b(js.encode("utf-8", errors="ignore"), digest_size=16).hexdigest()


def _cache_get(kind: str, fp: str) -> Any:
    """Return the cached value (any shape) or ``None`` if absent.

    Typed as ``Any`` so callers can use the value directly as the string,
    dict, or list they stored. Callers know the shape per ``kind``.
    """
    if REPORT_CACHE_MAXSIZE <= 0:
        return None
    key = (kind, fp)
    with _report_cache_lock:
        if key in _report_cache:
            _report_cache.move_to_end(key)
            return _report_cache[key]
    return None


def _cache_set(kind: str, fp: str, value: Any) -> None:
    if REPORT_CACHE_MAXSIZE <= 0:
        return
    key = (kind, fp)
    with _report_cache_lock:
        _report_cache[key] = value
        _report_cache.move_to_end(key)
        while len(_report_cache) > REPORT_CACHE_MAXSIZE:
            _report_cache.popitem(last=False)
