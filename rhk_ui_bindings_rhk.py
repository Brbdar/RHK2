#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_bindings_rhk.py - RHK-Tab: DZL Visibility/State Bindings ausgelagert
"""Bindings for the RHK tab (currently: DZL controls)."""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

from rhk_base import gr


def _log_debug(msg: str) -> None:
    if str(os.getenv("RHK_DEBUG_UI_ERRORS", "")).strip() in {"1", "2", "true", "yes", "on"}:
        print(f"[RHK_UI] {msg}", file=sys.stderr)


def bind_rhk_bindings(
    *,
    field_components: Dict[str, Any],
    bind_change: Callable[..., Any],
) -> None:
    """Attach RHK-tab bindings."""

    # DZL: show decision dropdown + Ersttestung only if checkbox is set (and clear on uncheck)
    # IMPORTANT: When enabling, keep current values (never overwrite manual inputs).
    def _toggle_dzl(flag_val: Any, cur_decision: Any, cur_initial: Any):
        if bool(flag_val):
            return (
                gr.update(visible=True, value=(cur_decision if str(cur_decision or "").strip() else "Noch nicht gefragt")),
                gr.update(visible=True, value=bool(cur_initial)),
            )
        return (
            gr.update(visible=False, value=""),
            gr.update(visible=False, value=False),
        )

    try:
        bind_change(
            field_components["dzl_flag"],
            _toggle_dzl,
            inputs=[field_components["dzl_flag"], field_components["dzl_decision"], field_components["dzl_initial_test"],
            ],
            outputs=[field_components["dzl_decision"], field_components["dzl_initial_test"],
            ],
        )
    except Exception as e:
        _log_debug(f"bind DZL failed: {e.__class__.__name__}")
