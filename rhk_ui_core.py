#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_core.py - UI-Core (DataProbe, HTML-Escape, Safe Render), keine Side-Effect-Imports, Debug-Logging ohne PHI
"""UI Core Utilities (RHK Befundassistent).

Clinical safety goals:
- UI rendering must never crash the app (fail-safe HTML generation).
- No PHI in logs by default (only function name + exception type).
- Deterministic formatting helpers (missing data stays missing; no implicit 0).
"""

from __future__ import annotations

import builtins
import functools
import html as _html
import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Union

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


_PathKey = Union[str, int]


def _debug_ui_errors_level() -> int:
    """Return debug level for UI errors.

    0 = silent (default)
    1 = log function + exception type
    2 = also print traceback (developer mode)
    """
    raw = str(os.getenv("RHK_DEBUG_UI_ERRORS", "")).strip().lower()
    if raw in {"2", "trace", "traceback", "full"}:
        return 2
    if raw in {"1", "true", "yes", "y", "on"}:
        return 1
    return 0


def ui_safe_render(fallback: str = "") -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Decorator for HTML builder functions.

    Rationale (clinical UX):
    - Rendering must be resilient: a single bad/missing sub-field must not break the entire app.
    - In production we suppress stack traces to avoid leaking sensitive context.

    Debugging:
    - Set env ``RHK_DEBUG_UI_ERRORS=1`` to log minimal error info.
    - Set env ``RHK_DEBUG_UI_ERRORS=2`` to also print a traceback (developer-only).
    """

    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover (UI safety net)
                lvl = _debug_ui_errors_level()
                if lvl >= 1:
                    # DO NOT include exception message (could contain user content).
                    print(
                        f"[RHK_UI] render error in {func.__name__}: {exc.__class__.__name__}",
                        file=sys.stderr,
                    )
                if lvl >= 2:
                    import traceback

                    traceback.print_exc()
                return fallback

        return wrapper

    return decorator


class DataProbe:
    """Robust accessor for nested clinical data structures.

    Guarantees:
    - Never raises on missing keys / None chains.
    - Normalizes numeric strings (comma as decimal separator).
    - Returns ``None`` for NaN/Inf (never propagates invalid floats).

    Important: DataProbe performs *no* medical validation (plausibility gates live elsewhere).
    It is strictly an access/format convenience for UI rendering.
    """

    def __init__(self, data: Optional[Dict[str, Any]]):
        self._data: Dict[str, Any] = data or {}

    def get(self, *path: _PathKey, default: Any = None) -> Any:
        """Deep safe get for dict/list structures."""
        curr: Any = self._data
        for key in path:
            if isinstance(curr, dict):
                curr = curr.get(key)
            elif isinstance(curr, list) and isinstance(key, int):
                try:
                    curr = curr[key]
                except Exception:
                    return default
            else:
                return default
        return curr if curr is not None else default

    def float(self, *path: _PathKey) -> Optional[float]:
        """Return float or None. Never raises."""
        val = self.get(*path)
        if val is None or val == "":
            return None
        try:
            if isinstance(val, str):
                val = val.replace(",", ".")
            f = float(val)
            return f if math.isfinite(f) else None
        except (TypeError, ValueError):
            return None

    def str(self, *path: _PathKey) -> str:
        """Return stripped string or empty string."""
        val = self.get(*path)
        return str(val).strip() if val is not None else ""

    def fmt(self, *path: _PathKey, nd: int = 0, dash: builtins.str = "–") -> builtins.str:
        """Format float with decimals; None -> dash."""
        val = self.float(*path)
        if val is None:
            return dash
        return f"{val:.{nd}f}"


def html_escape(s: Any) -> str:
    """Robust HTML escape."""
    if s is None:
        return ""
    try:
        return _html.escape(str(s), quote=True)
    except Exception:
        return ""


def _chip(text: str, tone: str = "", title: str = "") -> str:
    """Render a semantic chip.

    If ``title`` is provided, a CSS-only tooltip is embedded (no JS).
    """
    c = f"rhk-schip {tone}".strip()
    if title:
        safe_title = html_escape(title)
        tip_html = safe_title.replace("\n", "<br>")
        tattr = f" title='{safe_title}'"
        return (
            f"<span class='{c} rhk-has-tip'{tattr}>"
            f"{html_escape(text)}"
            f"<span class='rhk-tip'>{tip_html}</span>"
            f"</span>"
        )
    return f"<span class='{c}'>{html_escape(text)}</span>"


# --- Legacy helpers (kept for backward compatibility) ---

def _fmt_or_dash(v: Any, nd: int = 0) -> str:
    """Legacy helper required by older UI code."""
    try:
        if v is None or v == "":
            return "–"
        if isinstance(v, str):
            v = v.replace(",", ".")
        fv = float(v)
        if not math.isfinite(fv):
            return "–"
        return f"{fv:.{nd}f}"
    except Exception:
        return "–"


def _normalize_module_ids(ids: List[str]) -> List[str]:
    """Normalize a list of module IDs (stable order preserved)."""
    if not ids:
        return []
    out: List[str] = []
    for x in ids:
        if not x:
            continue
        s = str(x).strip()
        if s:
            out.append(s)
    return out


def _gradio_major_version() -> int:
    """Return gradio major version if importable, else 0."""
    try:
        import gradio as gr

        v = getattr(gr, "__version__", "0")
        return int(str(v).split(".")[0])
    except Exception:
        return 0


@functools.lru_cache(maxsize=16)
def load_rulebook_meta(path: str) -> Dict[str, Any]:
    """Read cached rulebook meta block from YAML (if available)."""
    if not path or not os.path.exists(path) or yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        return doc.get("meta", {}) if isinstance(doc, dict) else {}
    except Exception:
        return {}
