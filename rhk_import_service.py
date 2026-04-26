"""DOCX import services kept separate from the Gradio UI layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from rhk_import_docx import map_payload_to_ui, parse_maclab_docx
from rhk_import_merge import apply_import_updates
from rhk_logging import log_exception
from rhk_ui_utils import build_docx_status_html

FILL_FROM_PREV_IF_MISSING = ("age", "sex", "height_cm", "weight_kg", "hb_g_dl")


@dataclass
class DocxImportBundle:
    ui_dict: Dict[str, Any]
    payload: Dict[str, Any]
    status_html: str


def _payload_or_empty(payload: Any) -> Dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _is_effectively_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return abs(float(value)) < 1e-12
        except (TypeError, ValueError):
            return False
    return False


def import_current_docx(
    file_path: str,
    *,
    ui_dict: Dict[str, Any],
    prev_payload: Any,
    prev_docx_payload: Any,
    wipe_defaults: Dict[str, Any],
) -> DocxImportBundle:
    prev_payload_dict = _payload_or_empty(prev_payload)
    prev_keys = prev_payload_dict.get("_ui_applied_keys_current") or []
    prev_vals = prev_payload_dict.get("_ui_applied_values_current") or {}
    prev_docx_payload_dict = _payload_or_empty(prev_docx_payload)

    payload = parse_maclab_docx(file_path)
    updates = map_payload_to_ui(payload, target="current")
    ui_out, applied_vals = apply_import_updates(
        ui=dict(ui_dict or {}),
        updates=updates,
        prev_applied_keys=prev_keys,
        prev_applied_values=prev_vals,
        wipe_defaults=wipe_defaults,
    )

    try:
        payload["_ui_applied_keys_current"] = sorted(list(applied_vals.keys()))
        payload["_ui_applied_values_current"] = applied_vals
    except Exception as exc:
        log_exception("RHK_IMPORT_CURRENT_PROVENANCE", "Persisting current DOCX import provenance failed.", exc)

    try:
        status_html = build_docx_status_html(payload, prev_docx_payload_dict)
    except Exception as exc:
        log_exception("RHK_IMPORT_CURRENT_STATUS", "Current DOCX status HTML rendering failed.", exc)
        status_html = ""

    return DocxImportBundle(ui_dict=ui_out, payload=payload, status_html=status_html)


def import_previous_docx(
    file_path: str,
    *,
    ui_dict: Dict[str, Any],
    prev_payload: Any,
    current_docx_payload: Any,
    wipe_defaults: Dict[str, Any],
    fill_from_prev_if_missing: Iterable[str] = FILL_FROM_PREV_IF_MISSING,
) -> DocxImportBundle:
    current_docx_payload_dict = _payload_or_empty(current_docx_payload)
    prev_payload_dict = _payload_or_empty(prev_payload)
    prev_keys = prev_payload_dict.get("_ui_applied_keys_prev") or []
    prev_vals = prev_payload_dict.get("_ui_applied_values_prev") or {}

    payload = parse_maclab_docx(file_path)
    updates_prev = map_payload_to_ui(payload, target="prev")
    ui_out, applied_vals_prev = apply_import_updates(
        ui=dict(ui_dict or {}),
        updates=updates_prev,
        prev_applied_keys=prev_keys,
        prev_applied_values=prev_vals,
        wipe_defaults=wipe_defaults,
    )

    updates_cur = map_payload_to_ui(payload, target="current")
    for key in fill_from_prev_if_missing:
        if _is_effectively_empty(ui_out.get(key)) and (updates_cur.get(key) is not None):
            ui_out[key] = updates_cur.get(key)

    try:
        payload["_ui_applied_keys_prev"] = sorted(list(applied_vals_prev.keys()))
        payload["_ui_applied_values_prev"] = applied_vals_prev
    except Exception as exc:
        log_exception("RHK_IMPORT_PREV_PROVENANCE", "Persisting previous DOCX import provenance failed.", exc)

    try:
        status_html = build_docx_status_html(current_docx_payload_dict, payload)
    except Exception as exc:
        log_exception("RHK_IMPORT_PREV_STATUS", "Previous DOCX status HTML rendering failed.", exc)
        status_html = ""

    return DocxImportBundle(ui_dict=ui_out, payload=payload, status_html=status_html)
