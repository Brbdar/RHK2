#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_bindings_imaging.py - Bildgebung-Tab: Visibility-Bindings ausgelagert
"""Bindings for the 'Bildgebung & Echo/CMR' tab (visibility only)."""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

from rhk_base import gr


def _log_debug(msg: str) -> None:
    if str(os.getenv("RHK_DEBUG_UI_ERRORS", "")).strip() in {"1", "2", "true", "yes", "on"}:
        print(f"[RHK_UI] {msg}", file=sys.stderr)


def bind_imaging_bindings(
    *,
    field_components: Dict[str, Any],
    imaging_ui: Dict[str, Any],
    bind_change: Callable[..., Any],
) -> None:
    """Attach imaging-tab specific bindings."""

    # CT description column only when CT done
    try:
        bind_change(
            field_components["ct_done"],
            lambda v: gr.update(visible=bool(v)),
            inputs=[field_components["ct_done"]],
            outputs=[imaging_ui["ct_desc_col"]],
        )
    except Exception as e:
        _log_debug(f"bind ct_done failed: {e.__class__.__name__}")

    # ILD details only when CT-ILD checked
    try:
        bind_change(
            field_components["ct_ild"],
            lambda v: (
                gr.update(visible=bool(v)),
                gr.update(visible=bool(v)),
                gr.update(visible=bool(v)),
            ),
            inputs=[field_components["ct_ild"]],
            outputs=[imaging_ui["acc_ild"], field_components["ild_extent"], imaging_ui["ild_tx_details"]],
        )
    except Exception as e:
        _log_debug(f"bind ct_ild failed: {e.__class__.__name__}")

    # V/Q accordion only when V/Q done
    try:
        bind_change(
            field_components["vq_done"],
            lambda v: gr.update(visible=bool(v)),
            inputs=[field_components["vq_done"]],
            outputs=[imaging_ui["acc_vq"]],
        )
    except Exception as e:
        _log_debug(f"bind vq_done failed: {e.__class__.__name__}")

    # CTEPD no PH criteria: only if V/Q defect checked
    try:
        bind_change(
            field_components["vq_defect"],
            lambda v: gr.update(visible=bool(v)),
            inputs=[field_components["vq_defect"]],
            outputs=[imaging_ui["ctepd_no_ph_col"]],
        )
    except Exception as e:
        _log_debug(f"bind vq_defect failed: {e.__class__.__name__}")

    # ILD antifibrotics detail fields only when status == "ja"
    def _toggle_antifib(status: Any):
        on = str(status or "").strip().lower() == "ja"
        return (
            gr.update(visible=on),
            gr.update(visible=on),
            gr.update(visible=on),
        )

    try:
        bind_change(
            field_components["antifibrotic_status"],
            _toggle_antifib,
            inputs=[field_components["antifibrotic_status"]],
            outputs=[imaging_ui["antifib_drug"], imaging_ui["antifib_since"], imaging_ui["antifib_note"]],
        )
    except Exception as e:
        _log_debug(f"bind antifibrotic_status failed: {e.__class__.__name__}")
