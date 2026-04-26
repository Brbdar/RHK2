#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.27: rhk_ui_progress.py - Section-Progress Engine ausgelagert, 0/NaN/Inf als "nicht ausgefüllt", Cross-Version Binding
"""UI-only section progress helpers.

This module provides the *section header progress* ("Ausfüllgrad") used in the UI.

Clinical/UX principles
----------------------
- **UI-only**: This MUST NOT influence any medical calculations, derived values,
  risk strata or recommendations.
- **Conservative counting**: avoid false positives ("looks complete"), therefore
  treat ambiguous values (e.g. numeric zero, NaN/Inf) as *not filled*.
- **Performance-first**: binding progress to many fields can cause server roundtrips
  on every keystroke. Therefore this feature is **OFF by default** and can be
  enabled explicitly with ``RHK_ENABLE_SECTION_PROGRESS=1``.

Implementation notes
--------------------
- The binding helpers tolerate different Gradio versions and component APIs.
- We intentionally avoid any caching that could store patient data.
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable, Optional, Sequence, Tuple

__all__ = [
    "is_filled",
    "render_section_header",
    "bind_section_progress",
]


_EMPTY_SENTINELS = {
    "keine angabe",
    "unklar",
    "—",
    "-",
    "nan",
    "inf",
    "+inf",
    "-inf",
}


def is_filled(v: Any) -> bool:
    """Return True if a UI value is *meaningfully* filled.

    This is a heuristic for UI progress indicators.

    Safety stance:
    - Missing values ≠ 0 → numeric ``0`` is treated as *not filled*.
    - ``NaN``/``Inf`` are treated as *not filled*.
    - Booleans count only when ``True`` (checked).
    """
    if v is None:
        return False

    # Booleans: only count when explicitly checked.
    if isinstance(v, bool):
        return bool(v)

    # Numbers
    if isinstance(v, (int, float)):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(fv):
            return False
        # Conservative: avoid counting empty Number inputs that come back as 0.
        if fv == 0.0:
            return False
        return True

    # Multi-select
    if isinstance(v, (list, tuple, set)):
        try:
            return any(str(x).strip() for x in v)
        except (TypeError, AttributeError):
            return False

    s = str(v).strip()
    if not s:
        return False

    sl = s.lower()
    if sl in _EMPTY_SENTINELS:
        return False

    # Conservative: text "0" often comes from "empty but serialized".
    if sl in {"0", "0.0", "0,0"}:
        return False

    return True


def render_section_header(title: str, filled: Any, total: Any) -> str:
    """Render section header HTML (title + progress bar)."""
    try:
        total_f = float(total) if total not in (None, "") else 0.0
    except (TypeError, ValueError):
        total_f = 0.0
    try:
        filled_f = float(filled) if filled not in (None, "") else 0.0
    except (TypeError, ValueError):
        filled_f = 0.0

    if total_f <= 0:
        pct = 0
        cls = "rhk-sec-progress is-optional"
        count_txt = "optional"
    else:
        pct = max(0, min(100, int(round(100.0 * filled_f / max(1e-6, total_f)))))
        cls = "rhk-sec-progress"
        count_txt = f"{filled_f:.1f}/{total_f:.1f}".replace(".", ",")

    safe_title = str(title or "")
    safe_count = str(count_txt)

    return (
        "<div class='rhk-sec-head'>"
        f"<div class='rhk-sec-title'>{safe_title}</div>"
        f"<div class='{cls}' title='Ausfüllgrad (Schätzwert)'>"
        f"<span class='rhk-sec-count'>{safe_count}</span>"
        f"<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt {safe_title}' aria-valuenow='{pct}' aria-valuemin='0' aria-valuemax='100'><div style='width:{pct}%'></div></div>"
        "</div></div>"
    )


def _default_bind_change(comp: Any, fn: Callable[..., Any], *, inputs: Any, outputs: Any) -> None:
    """Best-effort `.change` binding across Gradio versions."""
    try:
        comp.change(
            fn,
            inputs=inputs,
            outputs=outputs,
            queue=False,
            show_progress="hidden",
            scroll_to_output=False,
            trigger_mode="always_last",
        )
        return
    except TypeError:
        pass
    except Exception:
        # Some older components may raise generic exceptions for unsupported kwargs.
        pass

    try:
        comp.change(fn, inputs=inputs, outputs=outputs, trigger_mode="always_last", queue=False)
        return
    except TypeError:
        pass
    except Exception:
        pass

    try:
        comp.change(fn, inputs=inputs, outputs=outputs, queue=False)
        return
    except TypeError:
        pass
    except Exception:
        pass

    # Last resort
    try:
        comp.change(fn, inputs=inputs, outputs=outputs)
    except Exception:
        return


def _default_bind_blur(comp: Any, fn: Callable[..., Any], *, inputs: Any, outputs: Any) -> None:
    """Best-effort `.blur` binding (fallback to `.change`)."""
    if hasattr(comp, "blur"):
        try:
            comp.blur(
                fn,
                inputs=inputs,
                outputs=outputs,
                queue=False,
                show_progress="hidden",
                scroll_to_output=False,
            )
            return
        except Exception:
            # Fall back to change binding.
            pass

    _default_bind_change(comp, fn, inputs=inputs, outputs=outputs)


def bind_section_progress(
    header_comp: Any,
    title: str,
    comps: Sequence[Any],
    calc_fn: Callable[..., Tuple[Any, Any]],
    *,
    bind_change: Optional[Callable[..., Any]] = None,
    bind_blur: Optional[Callable[..., Any]] = None,
    env_flag: str = "RHK_ENABLE_SECTION_PROGRESS",
) -> None:
    """Bind progress refresh callbacks to all components of a section.

    Args:
        header_comp: Gradio HTML component receiving the rendered header HTML.
        title: Human readable section title.
        comps: List/sequence of input components belonging to the section.
        calc_fn: Function mapping current component values -> (filled, total).
        bind_change: Optional external binder (preferred) with signature compatible
            to ``comp.change`` wrapper used in `rhk_ui.py`.
        bind_blur: Optional external binder (preferred) for blur events.
        env_flag: Environment variable name that enables the feature.

    Note:
        This feature is OFF by default for performance. Enable explicitly with
        ``RHK_ENABLE_SECTION_PROGRESS=1``.
    """
    if str(os.getenv(env_flag, "0")).strip() != "1":
        return

    if not comps:
        return

    _bind_change = bind_change or (lambda c, f, inputs=None, outputs=None: _default_bind_change(c, f, inputs=inputs, outputs=outputs))
    _bind_blur = bind_blur or (lambda c, f, inputs=None, outputs=None: _default_bind_blur(c, f, inputs=inputs, outputs=outputs))

    def _cb(*vals: Any) -> str:
        filled, total = calc_fn(*vals)
        return render_section_header(title, filled, total)

    # Bind to each component. Use blur for high-frequency inputs where possible.
    for c in comps:
        try:
            cname = (getattr(c, "__class__", type("x", (), {})).__name__ or "").lower()
            if cname in {"textbox", "number"} and hasattr(c, "blur"):
                _bind_blur(c, _cb, inputs=comps, outputs=[header_comp])
            else:
                _bind_change(c, _cb, inputs=comps, outputs=[header_comp])
        except Exception:
            continue
