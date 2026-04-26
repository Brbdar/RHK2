"""Case-oriented runtime helpers used by UI/export services."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from rhk_base import _normalize_module_ids
from rhk_case_schema import CaseLike
from rhk_logging import log_exception
from rhk_ui_helpers import _coerce_modules_list
from rhk_ui_utils import compute_egfr


def prepare_case_runtime_input(
    *,
    raw_ui: Dict[str, Any],
    case_state_in: Any,
    pmods_state: Any,
    flags: Dict[str, Any],
) -> Tuple[Dict[str, Any], CaseLike]:
    """Merge live UI data with existing case state and normalize runtime-only fields."""
    base_case: CaseLike = dict(case_state_in) if isinstance(case_state_in, dict) else {}
    base_ui = base_case.get("ui") if isinstance(base_case.get("ui"), dict) else (base_case if isinstance(base_case, dict) else {})

    if isinstance(base_ui, dict):
        raw = dict(base_ui)
        raw.update(raw_ui)
    else:
        raw = dict(raw_ui)

    try:
        egfr_val, _egfr_stage = compute_egfr(raw.get("creatinine_mg_dl"), raw.get("age"), raw.get("sex"))
    except Exception as exc:
        log_exception("RHK_UI_GENERATE_EGFR", "Generate-path eGFR computation failed.", exc)
        egfr_val = None
    if egfr_val is not None:
        egfr_store: int | float
        try:
            egfr_store = int(round(float(egfr_val)))
        except (TypeError, ValueError) as exc:
            log_exception("RHK_UI_GENERATE_EGFR_ROUND", "Generate-path eGFR rounding failed; storing raw value.", exc)
            egfr_store = egfr_val
        raw["egfr_ml_min_1_73"] = egfr_store
        raw["egfr"] = egfr_store
    elif raw.get("egfr") in (None, "") and raw.get("egfr_ml_min_1_73") not in (None, ""):
        raw["egfr"] = raw.get("egfr_ml_min_1_73")

    ui_mods = _normalize_module_ids(
        _coerce_modules_list(raw.get("modules_lvl1"))
        + _coerce_modules_list(raw.get("modules_lvl2"))
        + _coerce_modules_list(raw.get("modules_lvl3"))
        + _coerce_modules_list(raw.get("modules"))
    )
    seed_mods = _normalize_module_ids(
        ((pmods_state or {}).get("lvl1") or [])
        + ((pmods_state or {}).get("lvl2") or [])
        + ((pmods_state or {}).get("lvl3") or [])
    )
    if (not ui_mods) and seed_mods and (not flags.get("dirty")) and (not flags.get("has_report")):
        raw["modules"] = seed_mods
    else:
        raw["modules"] = ui_mods

    return raw, base_case
