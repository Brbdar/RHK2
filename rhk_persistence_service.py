"""Persistence services for save/load/export edges.

The UI should orchestrate widgets, not schema migration or payload shaping.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rhk_case_migrations import migrate_case_payload, stamp_case_payload
from rhk_followup import (
    build_followup_baseline_payload,
    derive_followup_case_filename,
    prepare_followup_ui,
    promote_docx_imports_for_followup,
)
from rhk_reports import build_summary_dict, export_json, export_summary_json
from rhk_runtime_policy import get_runtime_case_dir

_EMPTY_ECHO_IMPORT = {"parsed": {}, "meta": {}, "has_file": False}

_ECHO_IMPORT_KEYS = [
    "echo_done",
    "lvef",
    "ee_ratio",
    "la_enlarged",
    "la_vmax_ml",
    "la_esa_cm2",
    "lavi_ml_m2",
    "afib",
    "pasp_echo",
    "trv_ms",
    "tapse_mm",
    "tapse_spap_ratio",
    "s_prime_cm_s",
    "ra_esa_cm2",
    "rv_edd_mm",
    "septal_flattening",
    "ivc_diam_mm",
    "ivc_collapse",
    "pericardial_effusion",
    "rvot_notch",
    "ivc_respiratory",
    "ra_eda_cm2",
    "rv_esd_mm",
    "rv_eda_cm2",
    "rv_esa_cm2",
    "rv_wall_thickness_mm",
    "rvfac_pct",
    "rv_gls_pct",
    "rv_fwls_pct",
    "rv_3d_edv_ml",
    "rv_3d_esv_ml",
    "rv_3d_sv_ml",
    "rv_3d_ef_pct",
    "rv_3d_edvi_ml_m2",
    "rv_3d_esvi_ml_m2",
    "paat_ms",
    "rvet_ms",
    "paat_rvet_ratio",
    "ivc_exp_mm",
    "ivc_insp_mm",
    "ivc_collapse_index_pct",
]

_ECHO_RADIO_KEYS = {"ivc_collapse", "pericardial_effusion", "rvot_notch", "ivc_respiratory"}


@dataclass
class SaveCaseBundle:
    case_path: str
    summary_path: str
    summary_dict: Dict[str, Any]
    saved_case: Dict[str, Any]
    updated_flags: Dict[str, Any]


@dataclass
class LoadedCaseBundle:
    ui_dict: Dict[str, Any]
    pending_modules: Dict[str, List[Any]]
    docx_cur: Any
    docx_prev: Any
    echo_cur: Dict[str, Any]
    echo_prev: Dict[str, Any]
    loaded_name: str
    baseline_payload: Dict[str, Any]
    migrated_payload: Dict[str, Any]


def _normalize_case_filename(name: Any) -> Optional[str]:
    text = str(name or "").strip()
    if not text:
        return None
    if not text.lower().endswith(".json"):
        text = text + ".json"
    return text


def _resolve_target_dir(target_dir: Optional[str] = None) -> str:
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
        return target_dir
    resolved = str(get_runtime_case_dir())
    os.makedirs(resolved, exist_ok=True)
    return resolved


def _safe_echo_import(payload: Any) -> Dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) and payload else dict(_EMPTY_ECHO_IMPORT)


def _echo_value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip().lower()
        return (not text) or (text in {"keine angabe", "n/a", "na", "-"})
    if isinstance(value, (int, float)):
        try:
            num = float(value)
        except (TypeError, ValueError):
            return False
        if num != num:
            return True
        return num == 0.0
    if isinstance(value, bool):
        return value is False
    return False


def _normalize_echo_radio(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"", "-", "keine angabe", "n/a", "na"}:
        return "keine Angabe"
    if text in {"ja", "yes", "y", "true", "1"}:
        return "ja"
    if text in {"nein", "no", "n", "false", "0"}:
        return "nein"
    return value


def _backfill_echo_imports(ui_dict: Dict[str, Any], echo_cur: Dict[str, Any], echo_prev: Dict[str, Any]) -> Dict[str, Any]:
    ui_out = dict(ui_dict or {})
    parsed_cur = (echo_cur or {}).get("parsed") or {}
    parsed_prev = (echo_prev or {}).get("parsed") or {}
    parsed = parsed_cur if parsed_cur else parsed_prev
    if not isinstance(parsed, dict) or not parsed:
        return ui_out

    for key in _ECHO_IMPORT_KEYS:
        if key not in parsed:
            continue
        current = ui_out.get(key)
        new_value = parsed.get(key)
        if key in _ECHO_RADIO_KEYS:
            new_value = _normalize_echo_radio(new_value)
        if isinstance(current, bool):
            if (current is False) and (new_value is True):
                ui_out[key] = True
            continue
        if _echo_value_is_empty(current) and (new_value is not None):
            ui_out[key] = new_value

    if (ui_out.get("echo_done") in (None, False)) and any(
        value for key, value in parsed.items() if key not in {"height_cm", "weight_kg", "bsa_m2"}
    ):
        ui_out["echo_done"] = True
    return ui_out


def save_case_bundle(
    case_state: Any,
    flags_state: Any,
    case_filename: Any,
    docx_cur_state: Any,
    docx_prev_state: Any,
    echo_cur_state: Any,
    echo_prev_state: Any,
    *,
    rulebook_meta: Optional[Dict[str, Any]] = None,
    target_dir: Optional[str] = None,
) -> SaveCaseBundle:
    if not isinstance(case_state, dict):
        raise ValueError("case_state must be a dict")

    remembered_name = _normalize_case_filename(case_filename)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    resolved_dir = _resolve_target_dir(target_dir)

    case_path = os.path.join(resolved_dir, remembered_name or f"rhk_case_{ts}.json")
    summary_path = os.path.join(
        resolved_dir,
        (os.path.splitext(remembered_name)[0] + "_summary.json") if remembered_name else f"rhk_summary_{ts}.json",
    )

    summary_dict = case_state.get("summary")
    if not isinstance(summary_dict, dict) or not summary_dict:
        summary_dict = build_summary_dict(case_state, rulebook_meta)

    export_case = dict(case_state)
    imports: Dict[str, Any] = {}
    if isinstance(docx_cur_state, dict) and docx_cur_state:
        imports["docx_current"] = docx_cur_state
    if isinstance(docx_prev_state, dict) and docx_prev_state:
        imports["docx_prev"] = docx_prev_state
    if isinstance(echo_cur_state, dict) and echo_cur_state:
        imports["echo_cur"] = echo_cur_state
    if isinstance(echo_prev_state, dict) and echo_prev_state:
        imports["echo_prev"] = echo_prev_state
    if imports:
        export_case["imports"] = imports

    export_case["summary"] = summary_dict
    saved_case = stamp_case_payload(export_case)
    export_json(saved_case, case_path)
    export_summary_json(summary_dict, summary_path)

    updated_flags = dict(flags_state or {})
    updated_flags["dirty"] = False
    updated_flags["saved_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    updated_flags["warnings"] = case_state.get("warnings") or []

    return SaveCaseBundle(
        case_path=case_path,
        summary_path=summary_path,
        summary_dict=summary_dict,
        saved_case=saved_case,
        updated_flags=updated_flags,
    )


def load_case_bundle(file_path: str, *, as_followup: bool = False) -> LoadedCaseBundle:
    with open(file_path, "r", encoding="utf-8") as handle:
        loaded_raw = json.load(handle)

    data = migrate_case_payload(loaded_raw)
    ui_dict = data.get("ui") if isinstance(data, dict) and "ui" in data else data
    if not isinstance(ui_dict, dict):
        ui_dict = {}
    ui_dict = dict(ui_dict)

    if as_followup:
        ui_dict = prepare_followup_ui(ui_dict)

    pending_modules = {
        "lvl1": ui_dict.get("modules_lvl1") or [],
        "lvl2": ui_dict.get("modules_lvl2") or [],
        "lvl3": ui_dict.get("modules_lvl3") or (ui_dict.get("modules") or []),
    }

    ui_dict["modules_lvl1"] = []
    ui_dict["modules_lvl2"] = []
    ui_dict["modules_lvl3"] = []

    imports = data.get("imports") if isinstance(data, dict) else {}
    if not isinstance(imports, dict):
        imports = {}

    if as_followup:
        docx_cur, docx_prev = promote_docx_imports_for_followup(imports)
    else:
        docx_cur = imports.get("docx_current")
        docx_prev = imports.get("docx_prev")

    echo_cur = _safe_echo_import(imports.get("echo_cur"))
    echo_prev = _safe_echo_import(imports.get("echo_prev"))
    ui_dict = _backfill_echo_imports(ui_dict, echo_cur, echo_prev)

    source_loaded_name = os.path.basename(file_path)
    loaded_name = derive_followup_case_filename(source_loaded_name) if as_followup else source_loaded_name

    if as_followup:
        imports_followup = dict(imports)
        if isinstance(docx_prev, dict) and docx_prev:
            imports_followup["docx_prev"] = docx_prev
        else:
            imports_followup.pop("docx_prev", None)
        imports_followup.pop("docx_current", None)
        baseline_payload = build_followup_baseline_payload(
            data if isinstance(data, dict) else {},
            ui_dict,
            imports=imports_followup,
            source_name=source_loaded_name,
        )
    else:
        if isinstance(data, dict) and ("ui" in data or "derived" in data or "decision" in data or "scores" in data):
            baseline_payload = data
            if "ui" not in baseline_payload:
                baseline_payload = {"ui": ui_dict, **data}
        else:
            baseline_payload = {"ui": ui_dict}

    return LoadedCaseBundle(
        ui_dict=ui_dict,
        pending_modules=pending_modules,
        docx_cur=docx_cur,
        docx_prev=docx_prev,
        echo_cur=echo_cur,
        echo_prev=echo_prev,
        loaded_name=loaded_name,
        baseline_payload=baseline_payload,
        migrated_payload=data,
    )
