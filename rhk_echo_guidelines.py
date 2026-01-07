#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central guideline rule library for Echo cutoffs and trend logic.

Used by
- rhk_ui_echo.py: Ampel (green, yellow, red) in preview and compare tables
- rhk_reports.py: Patient and doctor narratives with meaningful trend statements

Thresholds are stored in `echo_guidelines.yaml` to keep them transparent and
versionable.

Ampel meaning
- g: within reference range
- y: borderline or mildly/moderately abnormal
- r: clearly abnormal or high risk marker

This is an orientation aid. Final interpretation depends on clinical context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml


_YAML_PATH = Path(__file__).with_name("echo_guidelines.yaml")
_CACHE: Dict[str, Any] | None = None


@dataclass(frozen=True)
class TrendResult:
    key: str
    prev: Any
    cur: Any
    delta: Optional[float]
    direction: str  # higher | lower | more_negative | binary
    improved: Optional[bool]
    meaningful: bool
    reason: str


def _load_yaml() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data: Dict[str, Any] = {}
    if _YAML_PATH.exists():
        with _YAML_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    _CACHE = data
    return data


def guidelines_meta() -> Dict[str, Any]:
    return (_load_yaml().get("meta") or {})


def guidelines_sources() -> list[str]:
    meta = guidelines_meta()
    src = meta.get("sources") or []
    return [str(s) for s in src if str(s).strip()]


def rules() -> Dict[str, Any]:
    return (_load_yaml().get("rules") or {})


def rule_for(key: str) -> Dict[str, Any]:
    return rules().get(key) or {}


def label_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("label") or key)


def unit_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("unit") or "")


def note_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("note") or "")


def direction_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("direction") or "")


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            x = float(v)
            if x != x:
                return None
            return x
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip().lower()
        if not s or s in ("—", "-", "keine angabe", "n/a"):
            return None
        if s in ("ja", "nein"):
            return None
        s = s.replace(",", ".")
        try:
            x = float(s)
            if x != x:
                return None
            return x
        except Exception:
            return None
    return None


def _as_yesno(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return "ja" if v else "nein"
    if isinstance(v, (int, float)):
        return "ja" if float(v) >= 0.5 else "nein"
    s = str(v).strip().lower()
    if s in ("ja", "nein"):
        return s
    if s in ("true", "yes", "y", "wahr"):
        return "ja"
    if s in ("false", "no", "n", "falsch"):
        return "nein"
    return None


def severity(key: str, value: Any) -> str:
    """Return g/y/r or empty if unknown.

    Binary markers:
    - pericardial_effusion: ja -> r, nein -> g
    - rvot_notch: ja -> r, nein -> g
    - ivc_collapse: ja -> g, nein -> r
    """
    if value is None:
        return ""

    d = direction_for(key)
    if d == "binary" or key in ("pericardial_effusion", "rvot_notch", "ivc_collapse"):
        yn = _as_yesno(value)
        if yn is None:
            return ""
        if key == "ivc_collapse":
            return "g" if yn == "ja" else "r"
        return "r" if yn == "ja" else "g"

    x = _as_float(value)
    if x is None:
        return ""

    r = rule_for(key)
    sev = r.get("severity") or {}

    # g/y/r checks (order matters, g then y then r)
    # Some rules use min_abs/max_abs (e.g. strain expressed as negative values). In those cases we compare |x|.
    xabs = abs(x)
    for code in ("g", "y", "r"):
        band = sev.get(code) or {}
        mn = band.get("min")
        mx = band.get("max")
        mn_abs = band.get("min_abs")
        mx_abs = band.get("max_abs")
        ok = True
        if mn is not None:
            try:
                ok = ok and x >= float(mn)
            except Exception:
                ok = False
        if mx is not None:
            try:
                ok = ok and x <= float(mx)
            except Exception:
                ok = False
        if mn_abs is not None:
            try:
                ok = ok and xabs >= float(mn_abs)
            except Exception:
                ok = False
        if mx_abs is not None:
            try:
                ok = ok and xabs <= float(mx_abs)
            except Exception:
                ok = False
        if ok and band:
            return code

    return ""


def meaningful_delta(key: str) -> Optional[float]:
    r = rule_for(key)
    md = r.get("meaningful_delta")
    try:
        return float(md) if md is not None else None
    except Exception:
        return None


def trend(key: str, prev: Any, cur: Any) -> TrendResult:
    """Evaluate a parameter trend.

    Meaningful change is detected if:
    - severity category changes (g/y/r) OR
    - absolute delta exceeds meaningful_delta threshold.

    Direction defines what is considered improvement.
    """
    d = direction_for(key)

    if d == "binary" or key in ("pericardial_effusion", "rvot_notch", "ivc_collapse"):
        p = _as_yesno(prev)
        c = _as_yesno(cur)
        improved: Optional[bool] = None
        meaningful = False
        reason = ""

        if p is None or c is None:
            return TrendResult(key, prev, cur, None, "binary", None, False, "insufficient")

        if key == "ivc_collapse":
            # ja is physiologic collapse, so appearance is improvement
            if p != c:
                meaningful = True
                improved = (c == "ja")
                reason = "state_change"
        else:
            if p != c:
                meaningful = True
                improved = (c == "nein")  # disappearance improves
                reason = "state_change"

        return TrendResult(key, p, c, None, "binary", improved, meaningful, reason)

    p = _as_float(prev)
    c = _as_float(cur)
    if p is None or c is None:
        return TrendResult(key, prev, cur, None, d or "", None, False, "insufficient")

    delta = c - p

    sev_prev = severity(key, p)
    sev_cur = severity(key, c)

    improved: Optional[bool] = None
    if d == "lower":
        improved = delta < 0
    elif d == "more_negative":
        improved = c < p
    else:  # higher
        improved = delta > 0

    meaningful = False
    reason = ""

    if sev_prev and sev_cur and sev_prev != sev_cur:
        meaningful = True
        reason = "severity_change"
    else:
        md = meaningful_delta(key)
        if md is not None and abs(delta) >= md:
            meaningful = True
            reason = "delta_threshold"

    return TrendResult(key, p, c, delta, d or "", improved, meaningful, reason)


def fmt_delta(delta: Optional[float], digits: int = 0) -> str:
    if delta is None:
        return "—"
    if digits <= 0:
        return str(int(round(delta)))
    return f"{delta:.{digits}f}".replace(".", ",")


def fmt_value(v: Any, digits: int = 0) -> str:
    x = _as_float(v)
    if x is None:
        yn = _as_yesno(v)
        return yn if yn is not None else "—"
    if digits <= 0:
        return str(int(round(x)))
    return f"{x:.{digits}f}".replace(".", ",")


def overall_trend(prev_map: Dict[str, Any], cur_map: Dict[str, Any], keys: list[str]) -> Tuple[str, Dict[str, TrendResult]]:
    """Summarize overall trend across a list of keys.

    Returns (summary_label, per_key_results).
    summary_label is one of: verbessert, stabil, verschlechtert, nicht beurteilbar
    """
    results: Dict[str, TrendResult] = {}
    meaningful = []
    for k in keys:
        if k in prev_map and k in cur_map:
            tr = trend(k, prev_map.get(k), cur_map.get(k))
            results[k] = tr
            if tr.meaningful and tr.improved is not None:
                meaningful.append(tr.improved)

    if not meaningful:
        return "nicht beurteilbar", results

    # Majority vote
    improve_count = sum(1 for x in meaningful if x)
    worsen_count = sum(1 for x in meaningful if not x)

    if improve_count > worsen_count:
        return "verbessert", results
    if worsen_count > improve_count:
        return "verschlechtert", results
    return "stabil", results
