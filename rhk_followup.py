#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.49: rhk_followup.py - Verlaufsladen: alter Fall als neuer Katheter-Fall (Vor-RHK-Übernahme + Current-Reset)
"""Helpers for loading an old JSON case as a new follow-up catheter case.

Goal:
- Keep relevant baseline context from a prior case.
- Promote prior *current* RHK values into Vor-RHK comparison fields.
- Clear current-catheter fields so the user can document a new catheter.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, Mapping, Optional, Tuple

from rhk_validation import parse_floatish

# Old "current RHK" -> new "previous RHK" mapping.
_CUR_TO_PREV_NUMERIC_MAP: Dict[str, str] = {
    "spap_rest": "prev_spap",
    "dpap_rest": "prev_dpap",
    "mpap_rest": "prev_mpap",
    "pawp_rest": "prev_pawp",
    "rap_rest": "prev_rap",
    "co_rest": "prev_co",
    "ci_rest": "prev_ci",
    "pvr_rest": "prev_pvr",
}
_FOLLOWUP_DOCX_PROVENANCE_MAP: Dict[str, str] = {
    "rhk_date": "prev_rhk_date",
    **_CUR_TO_PREV_NUMERIC_MAP,
}


# Fields that represent the *current* catheter and should be blank for follow-up mode.
_FOLLOWUP_CLEAR_CURRENT: Dict[str, Any] = {
    # Current catheter date/measurements
    "rhk_date": "",
    "spap_rest": None,
    "dpap_rest": None,
    "mpap_rest": None,
    "pawp_rest": None,
    "rap_rest": None,
    "co_rest": None,
    "ci_rest": None,
    "pvr_rest": None,
    "co_method": "keine Angabe",
    # Exercise
    "exercise_done": False,
    "exercise_protocol": "",
    "exercise_peak_watts": None,
    "spap_peak": None,
    "dpap_peak": None,
    "mpap_peak": None,
    "pawp_peak": None,
    "co_peak": None,
    "ci_peak": None,
    # Volume challenge
    "volume_challenge_done": False,
    "pawp_pre": None,
    "pawp_post": None,
    "mpap_pre": None,
    "mpap_post": None,
    # Vasoreactivity
    "vaso_test_done": False,
    "vaso_agent": "",
    "vaso_response_desc": "",
    "vaso_mpap_pre": None,
    "vaso_co_pre": None,
    "vaso_mpap_post": None,
    "vaso_co_post": None,
    # Oximetry + hemo-related vitals
    "sat_svc": None,
    "sat_ivc": None,
    "sat_ra": None,
    "sat_rv": None,
    "sat_pa": None,
    "sat_ao": None,
    "bp_sys": None,
    "bp_dia": None,
    "bp_mean": None,
    "hr": None,
    "spo2": None,
    # Curve flags
    "wedge_v_wave": False,
    "wedge_a_wave": False,
    "rap_a_wave": False,
    "rap_v_wave": False,
    "rv_pseudo_dip": False,
    "rv_dip_plateau": False,
    # Pre-cath checklist values (for a fresh current procedure)
    "consent_done": False,
    "access_route": "",
    "inr": None,
    "ptt_s": None,
    "platelets_g_l": None,
    "anticoag_paused": False,
    "crp_mg_l": None,
    "lsb_present": False,
    "lsb_reason": "",
    # Modules/procedure text should be re-derived for the new case.
    "modules": [],
    "modules_lvl1": [],
    "modules_lvl2": [],
    "modules_lvl3": [],
    "procedere_free": "",
}


_FOLLOWUP_DROP_BASELINE_KEYS = {
    # Computed / stale outputs from old case
    "derived",
    "scores",
    "decision",
    "env",
    "hfpef",
    "warnings",
    "debug",
    "summary",
}


def _coerce_scalar_text(v: Any) -> str:
    """Best-effort coercion for text-like scalar fields from legacy/dirty payloads."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (list, tuple, set)):
        for item in v:
            s = _coerce_scalar_text(item)
            if s:
                return s
        return ""
    if isinstance(v, dict):
        for k in ("value", "label", "name", "text", "date"):
            if k in v:
                s = _coerce_scalar_text(v.get(k))
                if s:
                    return s
        return ""
    try:
        return str(v).strip()
    except Exception:
        return ""


def derive_followup_case_filename(loaded_name: str, *, today: Optional[_dt.date] = None) -> str:
    """Build a safe follow-up filename from a loaded case filename."""
    name = os.path.basename(_coerce_scalar_text(loaded_name)) or "rhk_case.json"
    stem, ext = os.path.splitext(name)
    if ext.lower() != ".json":
        ext = ".json"
    day = (today or _dt.date.today()).strftime("%Y%m%d")
    if stem.lower().endswith("_followup"):
        stem = f"{stem}_{day}"
    else:
        stem = f"{stem}_followup_{day}"
    return f"{stem}{ext}"


def prepare_followup_ui(ui: Mapping[str, Any]) -> Dict[str, Any]:
    """Transform loaded UI dict into a fresh follow-up case input."""
    src = dict(ui or {})
    out = dict(src)

    cur_date = _coerce_scalar_text(src.get("rhk_date"))
    if cur_date:
        out["prev_rhk_date"] = cur_date

    # Promote current resting hemodynamics into previous comparison fields.
    for cur_key, prev_key in _CUR_TO_PREV_NUMERIC_MAP.items():
        v = parse_floatish(src.get(cur_key), treat_zero_as_missing=True)
        if v is not None:
            out[prev_key] = v

    # Mark context as follow-up and clear previous transition fields.
    if cur_date:
        out["prev_label"] = f"Aus Vorbefund ({cur_date}) übernommen."
    elif not _coerce_scalar_text(out.get("prev_label")):
        out["prev_label"] = "Aus geladenem Vorbefund übernommen."
    out["prev_is_initial"] = False
    out["prev_tx_added"] = []
    out["prev_tx_free"] = ""

    # If not explicitly set, make indication explicit for the new cycle.
    if _coerce_scalar_text(out.get("ph_reason_rhk")) in ("", "keine Angabe"):
        out["ph_reason_rhk"] = "Verlaufskontrolle"

    # New case cycle: current catheter block starts empty.
    out.update(_FOLLOWUP_CLEAR_CURRENT)
    return out


def promote_docx_imports_for_followup(imports: Mapping[str, Any]) -> Tuple[Any, Any]:
    """Move current DOCX payload to previous slot for follow-up comparison."""
    imp = dict(imports or {})
    docx_cur = imp.get("docx_current")
    docx_prev = imp.get("docx_prev")
    if isinstance(docx_cur, dict) and docx_cur:
        docx_prev = dict(docx_cur)
        cur_keys = docx_prev.pop("_ui_applied_keys_current", None)
        cur_vals = docx_prev.pop("_ui_applied_values_current", None)
        prev_keys = docx_prev.get("_ui_applied_keys_prev")
        prev_vals = docx_prev.get("_ui_applied_values_prev")

        remapped_keys = []
        if isinstance(cur_keys, (list, tuple, set)):
            for key in cur_keys:
                mapped = _FOLLOWUP_DOCX_PROVENANCE_MAP.get(str(key or "").strip())
                if mapped:
                    remapped_keys.append(mapped)

        remapped_vals: Dict[str, Any] = {}
        if isinstance(cur_vals, Mapping):
            for key, value in cur_vals.items():
                mapped = _FOLLOWUP_DOCX_PROVENANCE_MAP.get(str(key or "").strip())
                if mapped:
                    remapped_vals[mapped] = value

        merged_keys: list[str] = []
        if isinstance(prev_keys, (list, tuple, set)):
            merged_keys.extend(str(x).strip() for x in prev_keys if str(x).strip())
        merged_keys.extend(remapped_keys)
        merged_vals = dict(prev_vals) if isinstance(prev_vals, Mapping) else {}
        merged_vals.update(remapped_vals)

        if merged_keys:
            docx_prev["_ui_applied_keys_prev"] = sorted(set(merged_keys))
        elif "_ui_applied_keys_prev" in docx_prev:
            docx_prev.pop("_ui_applied_keys_prev", None)

        if merged_vals:
            docx_prev["_ui_applied_values_prev"] = merged_vals
        elif "_ui_applied_values_prev" in docx_prev:
            docx_prev.pop("_ui_applied_values_prev", None)
    return None, (docx_prev if isinstance(docx_prev, dict) and docx_prev else None)


def build_followup_baseline_payload(
    data: Mapping[str, Any],
    ui: Mapping[str, Any],
    *,
    imports: Optional[Mapping[str, Any]] = None,
    source_name: str = "",
    now: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """Create a new baseline payload for a follow-up case.

    Keeps unknown top-level metadata from the loaded payload, but removes stale
    computed/report keys so the case is treated as a fresh cycle.
    """
    out = dict(data or {}) if isinstance(data, Mapping) else {}
    out["ui"] = dict(ui or {})
    for k in _FOLLOWUP_DROP_BASELINE_KEYS:
        out.pop(k, None)

    if isinstance(imports, Mapping) and imports:
        out["imports"] = dict(imports)
    else:
        out.pop("imports", None)

    meta = out.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    meta["load_mode"] = "followup"
    if source_name:
        meta["followup_source_file"] = source_name
    ts = (now or _dt.datetime.now()).isoformat(timespec="seconds")
    meta["followup_prepared_at"] = ts
    out["meta"] = meta
    return out
