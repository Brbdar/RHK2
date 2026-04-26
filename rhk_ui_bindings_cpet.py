#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_bindings_cpet.py - CPET-Tab: Visibility-Bindings ausgelagert
"""Bindings for the CPET tab (visibility only)."""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

from rhk_base import gr


def _log_debug(msg: str) -> None:
    if str(os.getenv("RHK_DEBUG_UI_ERRORS", "")).strip() in {"1", "2", "true", "yes", "on"}:
        print(f"[RHK_UI] {msg}", file=sys.stderr)


def bind_cpet_bindings(
    *,
    field_components: Dict[str, Any],
    cpet_ui: Dict[str, Any],
    bind_change: Callable[..., Any],
) -> None:
    """Attach CPET-tab bindings."""

    try:
        bind_change(
            field_components["cpet_9panel_available"],
            lambda flag: gr.update(visible=bool(flag)),
            inputs=[field_components["cpet_9panel_available"]],
            outputs=[cpet_ui["cpet_9panel_details"]],
        )
    except Exception as e:
        _log_debug(f"bind cpet_9panel_available failed: {e.__class__.__name__}")
