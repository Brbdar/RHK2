#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_bindings_clinic.py - Klinik-Tab: Visibility/Interaktions-Bindings ausgelagert, weniger Re-Renders
"""Bindings for the 'Klinik & Labor' tab.

Scope:
- Pure UI behavior (visibility toggles, dependent fields)
- PH therapy episode editor (add/delete/legacy import)

Non-goals:
- No medical rule logic, no case building, no imports into patient data model.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict

from rhk_base import gr
from rhk_ph_tx import (
    episodes_to_ph_tx_table_rows,
    episodes_to_ph_tx_text,
    legacy_lists_to_episodes,
    parse_ph_tx_table_rows,
)


def _log_debug(msg: str) -> None:
    if str(os.getenv("RHK_DEBUG_UI_ERRORS", "")).strip() in {"1", "2", "true", "yes", "on"}:
        print(f"[RHK_UI] {msg}", file=sys.stderr)


def bind_clinic_bindings(
    *,
    field_components: Dict[str, Any],
    clinic_ui: Dict[str, Any],
    bind_change: Callable[..., Any],
) -> None:
    """Attach clinic-tab specific bindings.

    Args:
        field_components: registry of named input components.
        clinic_ui: handle dict returned by ``build_clinic_tab``.
        bind_change: helper to register Gradio `.change` callbacks (best-effort across versions).
    """

    # -------------------------
    # Simple visibility toggles
    # -------------------------
    try:
        bind_change(
            field_components["allergies_present"],
            lambda present: gr.update(visible=bool(present)),
            inputs=[field_components["allergies_present"]],
            outputs=[clinic_ui["allergies_details"]],
        )
    except Exception as e:
        _log_debug(f"bind allergies_present failed: {e.__class__.__name__}")

    def _toggle_allergies_other(sel: Any):
        if not isinstance(sel, list):
            sel = [] if sel in (None, "") else [str(sel)]
        show_other = any(str(x).strip().lower() == "sonstiges" for x in sel)
        return gr.update(visible=bool(show_other))

    try:
        bind_change(
            field_components["allergies_list"],
            _toggle_allergies_other,
            inputs=[field_components["allergies_list"]],
            outputs=[field_components["allergies_other_text"]],
        )
    except Exception as e:
        _log_debug(f"bind allergies_list failed: {e.__class__.__name__}")

    try:
        bind_change(
            field_components["ekg_present"],
            lambda v: gr.update(visible=bool(v)),
            inputs=[field_components["ekg_present"]],
            outputs=[clinic_ui["ekg_details"]],
        )
    except Exception as e:
        _log_debug(f"bind ekg_present failed: {e.__class__.__name__}")

    def _toggle_ekg_other(ekg_signs: Any):
        if not isinstance(ekg_signs, list):
            ekg_signs = [] if ekg_signs in (None, "") else [str(ekg_signs)]
        show = any(str(x).strip().lower().startswith("sonst") for x in ekg_signs)
        return gr.update(visible=bool(show))

    try:
        bind_change(
            field_components["ekg_rhs_signs"],
            _toggle_ekg_other,
            inputs=[field_components["ekg_rhs_signs"]],
            outputs=[field_components["ekg_other_text"]],
        )
    except Exception as e:
        _log_debug(f"bind ekg_rhs_signs failed: {e.__class__.__name__}")

    try:
        bind_change(
            field_components["lsb_present"],
            lambda flag: gr.update(visible=bool(flag)),
            inputs=[field_components["lsb_present"]],
            outputs=[field_components["lsb_reason"]],
        )
    except Exception as e:
        _log_debug(f"bind lsb_present failed: {e.__class__.__name__}")

    # CHD: Details only if flagged (fix: return handle from tab module)
    try:
        if "chd_details" in clinic_ui:
            bind_change(
                field_components["chd_pos"],
                lambda flag: gr.update(visible=bool(flag)),
                inputs=[field_components["chd_pos"]],
                outputs=[clinic_ui["chd_details"]],
            )
    except Exception as e:
        _log_debug(f"bind chd_pos failed: {e.__class__.__name__}")

    # PDE-5 hardship: show justification only if checkbox active
    try:
        bind_change(
            field_components["pde5_hardship"],
            lambda flag: gr.update(visible=bool(flag)),
            inputs=[field_components["pde5_hardship"]],
            outputs=[field_components["pde5_hardship_desc"]],
        )
    except Exception as e:
        _log_debug(f"bind pde5_hardship failed: {e.__class__.__name__}")

    # -------------------------
    # Known PH vs suspected PH
    # -------------------------
    def _ph_known_changed(known: bool):
        k = bool(known)
        # Details visible only if "known" is checked.
        # If known: suspected auto-off (safety: avoids contradictory state).
        return (
            gr.update(visible=k),
            False if k else gr.update(),
        )

    def _ph_suspected_changed(suspected: bool):
        s = bool(suspected)
        # If suspected: known auto-off and hide details.
        if s:
            return (
                False,
                gr.update(visible=False),
            )
        return (
            gr.update(),
            gr.update(),
        )

    try:
        bind_change(
            field_components["ph_known"],
            _ph_known_changed,
            inputs=[field_components["ph_known"]],
            outputs=[clinic_ui["ph_known_details"], field_components["ph_suspected"]],
        )
        bind_change(
            field_components["ph_suspected"],
            _ph_suspected_changed,
            inputs=[field_components["ph_suspected"]],
            outputs=[field_components["ph_known"], clinic_ui["ph_known_details"]],
        )
    except Exception as e:
        _log_debug(f"bind ph_known/ph_suspected failed: {e.__class__.__name__}")

    # -------------------------
    # Anticoagulation UX
    # -------------------------
    # 1) Pause checkbox: smart control (avoid contradictory states)
    def _toggle_anticoag_paused(status: Any, current_val: Any):
        s = str(status or "").strip().lower()
        if s == "ja":
            # show checkbox and keep current value (do not reset on load)
            return gr.update(visible=True, value=bool(current_val))
        if "paus" in s:
            # status already implies pause -> hide checkbox, set True
            return gr.update(visible=False, value=True)
        # no/unknown -> hide, reset
        return gr.update(visible=False, value=False)

    try:
        bind_change(
            field_components["anticoag_status"],
            _toggle_anticoag_paused,
            inputs=[field_components["anticoag_status"], clinic_ui["anticoag_paused"]],
            outputs=[clinic_ui["anticoag_paused"]],
        )
    except Exception as e:
        _log_debug(f"bind anticoag_paused failed: {e.__class__.__name__}")

    # 2) Detail fields: show only when status == "ja"
    def _toggle_anticoag_details(status: Any):
        on = str(status or "").strip().lower() == "ja"
        return (
            gr.update(visible=on),
            gr.update(visible=on),
            gr.update(visible=on),
            gr.update(visible=on),
        )

    try:
        bind_change(
            field_components["anticoag_status"],
            _toggle_anticoag_details,
            inputs=[field_components["anticoag_status"]],
            outputs=[clinic_ui["anticoag_substance"], clinic_ui["anticoag_indication"], clinic_ui["anticoag_since"], clinic_ui["anticoag_note"]],
        )
    except Exception as e:
        _log_debug(f"bind anticoag_details failed: {e.__class__.__name__}")

    # -------------------------
    # PH therapy episode editor
    # -------------------------
    try:
        ph_tx_use_df = bool(clinic_ui.get("ph_tx_use_df"))

        ph_tx_add_btn = clinic_ui.get("ph_tx_add_btn")
        ph_tx_del_btn = clinic_ui.get("ph_tx_del_btn")
        ph_tx_from_legacy_btn = clinic_ui.get("ph_tx_from_legacy_btn")

        ph_tx_add_drug = clinic_ui.get("ph_tx_add_drug")
        ph_tx_add_status = clinic_ui.get("ph_tx_add_status")
        ph_tx_add_since = clinic_ui.get("ph_tx_add_since")
        ph_tx_add_until = clinic_ui.get("ph_tx_add_until")
        ph_tx_add_reason = clinic_ui.get("ph_tx_add_reason")
        ph_tx_add_note = clinic_ui.get("ph_tx_add_note")
        ph_tx_table = clinic_ui.get("ph_tx_table")
        ph_tx_del_idx = clinic_ui.get("ph_tx_del_idx")

        if not (ph_tx_add_btn and ph_tx_del_btn and ph_tx_from_legacy_btn and ph_tx_table):
            raise RuntimeError("missing PH tx components")

        def _as_rows(v: Any):
            if isinstance(v, list):
                return v
            eps = parse_ph_tx_table_rows(v)
            return episodes_to_ph_tx_table_rows(eps)

        def _as_text(v: Any):
            if isinstance(v, str):
                return v
            eps = parse_ph_tx_table_rows(v)
            return episodes_to_ph_tx_text(eps)

        def _ph_tx_add_episode(drug, status, since, until, reason, note, table_value):
            """Add one episode to the PH therapy editor.

            Supports:
            - Dataframe (list[list]) when pandas is available
            - Textbox (tab-delimited lines) when pandas is NOT available (default)
            """
            d = str(drug or "").strip()
            s = str(status or "").strip().lower()
            if not d or not s:
                # no change
                if ph_tx_use_df:
                    rows = _as_rows(table_value)
                    return (rows, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())
                txt = _as_text(table_value)
                return (txt, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update())

            rr = "" if str(reason or "").strip() in ("", "keine Angabe") else str(reason).strip()
            nn = "" if str(note or "").strip() in ("", "keine Angabe") else str(note).strip()

            new_row = [d, s, str(since or "").strip(), str(until or "").strip(), rr, nn]

            if ph_tx_use_df:
                rows = _as_rows(table_value)
                rows = list(rows) + [new_row]
                return (
                    rows,
                    gr.update(value=None),
                    gr.update(value="aktuell"),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(value="keine Angabe"),
                    gr.update(value=""),
                )

            # Textbox fallback (tab-delimited)
            txt = _as_text(table_value).rstrip("\n")
            line = "\t".join([str(x or "").strip() for x in (new_row + ["", ""])][:6])
            out = (txt + "\n" if txt.strip() else "") + line
            return (
                out,
                gr.update(value=None),
                gr.update(value="aktuell"),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value="keine Angabe"),
                gr.update(value=""),
            )

        def _ph_tx_delete_episode(idx, table_value):
            try:
                i = int(idx)
            except (TypeError, ValueError):
                return _as_rows(table_value) if ph_tx_use_df else _as_text(table_value)
            if i <= 0:
                return _as_rows(table_value) if ph_tx_use_df else _as_text(table_value)

            if ph_tx_use_df:
                rows = _as_rows(table_value)
                j = i - 1
                if j < 0 or j >= len(rows):
                    return rows
                return rows[:j] + rows[j + 1 :]

            # Textbox fallback
            txt = _as_text(table_value)
            lines = [ln for ln in (txt or "").splitlines() if ln.strip()]
            j = i - 1
            if j < 0 or j >= len(lines):
                return "\n".join(lines)
            lines = lines[:j] + lines[j + 1 :]
            return "\n".join(lines)

        def _ph_tx_from_legacy(cur, prev, new_meds, stopped, stop_reason, stop_reason_text):
            ui_tmp = {
                "ph_current_meds": cur,
                "ph_prev_meds": prev,
                "ph_new_meds": new_meds,
                "ph_stopped_meds": stopped,
                "ph_stop_reason": stop_reason,
                "ph_stop_reason_text": stop_reason_text,
            }
            eps = legacy_lists_to_episodes(ui_tmp)
            return episodes_to_ph_tx_table_rows(eps) if ph_tx_use_df else episodes_to_ph_tx_text(eps)

        # Bind buttons
        ph_tx_add_btn.click(
            _ph_tx_add_episode,
            inputs=[ph_tx_add_drug, ph_tx_add_status, ph_tx_add_since, ph_tx_add_until, ph_tx_add_reason, ph_tx_add_note, ph_tx_table],
            outputs=[ph_tx_table, ph_tx_add_drug, ph_tx_add_status, ph_tx_add_since, ph_tx_add_until, ph_tx_add_reason, ph_tx_add_note],
        )
        ph_tx_del_btn.click(
            _ph_tx_delete_episode,
            inputs=[ph_tx_del_idx, ph_tx_table],
            outputs=[ph_tx_table],
        )
        ph_tx_from_legacy_btn.click(
            _ph_tx_from_legacy,
            inputs=[
                field_components["ph_current_meds"],
                field_components["ph_prev_meds"],
                field_components["ph_new_meds"],
                field_components["ph_stopped_meds"],
                field_components["ph_stop_reason"],
                field_components["ph_stop_reason_text"],
            ],
            outputs=[ph_tx_table],
        )
    except Exception as e:
        _log_debug(f"bind PH tx editor failed: {e.__class__.__name__}")
