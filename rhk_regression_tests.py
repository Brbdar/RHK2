#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.30: rhk_regression_tests.py - Import-Merge Placeholder-Strings als "leer" getestet (keine Angabe, -)
# Refactor v1.29: rhk_regression_tests.py - Echo-Import Sanitization Regression ergänzt (OCR/PDF -> unphys/0 wird verworfen)
# Refactor v1.24: rhk_regression_tests.py - Added sanitization regressions (0 != missing, unphys -> None)
"""Regression Test Suite (Rulebook)

Dependency light assertions for core RHK rule logic.

Run:
    python rhk_regression_tests.py
"""

from __future__ import annotations

from typing import Any, Dict, List

from rhk_base import DEFAULT_RULEBOOK_PATH, apply_rule_engine_trace, load_rulebook
from rhk_case import build_case
from rhk_echo_pdf_import import extract_echo_from_text
from rhk_import_docx import map_payload_to_ui
from rhk_import_merge import apply_import_updates
from rhk_validation import sanitize_ui_numbers


def _mk_env(**kw: Any) -> Dict[str, Any]:
    """Create a minimal env for the rule engine.

    Important:
    - Explicitly set booleans used in comparisons (e.g. `step_up_present != True`) to avoid
      unintended matches due to missing keys.
    """
    env: Dict[str, Any] = {
        "mpap": None,
        "pawp_rest": None,
        "pvr": None,
        "step_up_present": False,
        "liver_hint": False,
        "poph_candidate": False,
        "high_flow": False,
        # sometimes used elsewhere
        "vq_defect": False,
        "ct_embolie": False,
        "ct_mosaic": False,
        "ct_ild": False,
        "ct_emphysema": False,
        "lufu_restrictive": False,
        "lufu_obstructive": False,
        "lufu_diffusion": False,
        "leading_group": None,
        "risk_category": None,
    }
    env.update(kw)
    return env


def _run_case(
    case_id: str,
    env: Dict[str, Any],
    expect_dx_contains: str,
    expect_tags: List[str],
    expect_modules: List[str],
) -> None:
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    d, trace = apply_rule_engine_trace(env, rules)

    if expect_dx_contains.lower() not in (d.primary_dx or '').lower():
        raise AssertionError(
            f"{case_id}: primary_dx mismatch. Got='{d.primary_dx}' Expected contains='{expect_dx_contains}'. "
            f"Fired={[x.get('id') for x in trace.fired]}"
        )

    for t in expect_tags:
        if t not in (d.tags or []):
            raise AssertionError(f"{case_id}: missing tag '{t}'. Got tags={d.tags}")

    for m in expect_modules:
        if m not in (d.modules or []):
            raise AssertionError(f"{case_id}: missing module '{m}'. Got modules={d.modules}")



def test_numeric_sanitization() -> None:
    # 0 must never be treated as a real measurement for hemodynamics.
    ui0 = {
        "mpap_rest": 0,
        "pawp_rest": "0",
        "co_rest": 0,
        "age": 0,
        "height_cm": 0,
        "weight_kg": 0,
    }
    s0 = sanitize_ui_numbers(ui0)
    assert s0.get("mpap_rest") is None
    assert s0.get("pawp_rest") is None
    assert s0.get("co_rest") is None
    assert s0.get("height_cm") is None
    assert s0.get("weight_kg") is None

    # Out-of-range (unphysiological) should become None.
    su = sanitize_ui_numbers({"pawp_rest": 200})
    assert su.get("pawp_rest") is None


def test_build_case_applies_sanitization() -> None:
    case = build_case({"modules": ["core"], "mpap_rest": 0, "pawp_rest": 200}, rules=[])
    assert case["ui"].get("mpap_rest") is None
    assert case["ui"].get("pawp_rest") is None


def test_echo_import_sanitization() -> None:
    """Echo importer must treat 0/unphys as missing and keep unit conversions stable.

    This test uses the text-only path (browser OCR compatible) to stay dependency-light.
    """
    sample = """
    Größe: 180 cm
    Gewicht: 0 kg
    KOF: 1,99 m2
    TAPSE: 0 mm
    sPAP: 2500 mmHg
    TR Vmax: 340 cm/s
    RV GLS: 25 %
    RA ESA: 90 cm2
    VCI expir.: 0 mm
    """

    ui, meta = extract_echo_from_text(sample, source="test")

    # plausibles should survive
    assert ui.get("height_cm") == 180.0
    trv_ms = ui.get("trv_ms")
    assert isinstance(trv_ms, (int, float))
    assert abs(float(trv_ms) - 3.4) < 0.05  # cm/s -> m/s

    # strain: minus sign must be restored if dropped
    assert ui.get("rv_gls_pct") == -25.0

    # extreme but plausible value must NOT be auto-scaled away
    assert ui.get("ra_esa_cm2") == 90.0

    # unphys/0 must be treated as missing (not present)
    assert ui.get("weight_kg") is None
    assert ui.get("tapse_mm") is None
    assert ui.get("pasp_echo") is None
    assert ui.get("ivc_exp_mm") is None

    # meta should mention sanitization
    sk = meta.get("sanitized_keys") or []
    assert "tapse_mm" in sk
    assert "pasp_echo" in sk

def test_import_merge_placeholder_string_empty() -> None:
    """Importer merge must treat common placeholder tokens as empty.

    Many Radio components default to 'keine Angabe'. Auto-fill should be allowed to
    replace that placeholder with imported values.
    """
    ui = {"pericardial_effusion": "keine Angabe"}
    updates = {"pericardial_effusion": "ja"}

    ui_new, applied = apply_import_updates(
        ui=ui,
        updates=updates,
        prev_applied_keys=None,
        prev_applied_values=None,
        wipe_defaults={"pericardial_effusion": "keine Angabe"},
    )
    assert ui_new.get("pericardial_effusion") == "ja"
    assert applied.get("pericardial_effusion") == "ja"

    ui2 = {"x": "-"}
    ui2_new, applied2 = apply_import_updates(
        ui=ui2,
        updates={"x": "foo"},
        prev_applied_keys=None,
        prev_applied_values=None,
        wipe_defaults={"x": "-"},
    )
    assert ui2_new.get("x") == "foo"
    assert applied2.get("x") == "foo"


def main() -> None:
    test_numeric_sanitization()
    test_build_case_applies_sanitization()
    test_echo_import_sanitization()
    test_import_merge_placeholder_string_empty()

    # 01 Unclassified High Flow (Safety Net)
    _run_case(
        "01",
        _mk_env(mpap=25, pawp_rest=10, pvr=1.5, step_up_present=False, liver_hint=False),
        expect_dx_contains="Unclassified PH (Flussdominante Druckerhöhung)",
        expect_tags=["PVR ≤ 2 WU", "High Output State"],
        expect_modules=["P32"],
    )

    # 02 Liver Profil A
    _run_case(
        "02",
        _mk_env(mpap=25, pawp_rest=10, pvr=1.5, step_up_present=False, liver_hint=True),
        expect_dx_contains="Unclassified PH (Flussdominante Druckerhöhung)",
        expect_tags=["Leber Profil A (Hyperdynam)", "PVR ≤ 2 WU"],
        expect_modules=["P32"],
    )

    # 03 Liver Profil B (postcap should remain, plus tag + P32)
    _run_case(
        "03",
        _mk_env(mpap=35, pawp_rest=20, pvr=1.5, step_up_present=False, liver_hint=True),
        expect_dx_contains="Postkapilläre PH",
        expect_tags=["Leber Profil B (Volumenbelastung)"],
        expect_modules=["P32"],
    )

    # 04 PoPH Candidate (manifest)
    _run_case(
        "04",
        _mk_env(mpap=35, pawp_rest=12, pvr=4.5, step_up_present=False, liver_hint=True, poph_candidate=True),
        expect_dx_contains="PoPH DD",
        expect_tags=["PoPH DD"],
        expect_modules=["P19", "P32"],
    )

    # 05 PoPH Borderline Risk
    _run_case(
        "05",
        _mk_env(mpap=25, pawp_rest=12, pvr=2.5, step_up_present=False, liver_hint=True, poph_candidate=True),
        expect_dx_contains="PoPH DD",
        expect_tags=["PoPH Risiko PVR 2-3"],
        expect_modules=["P19", "P32"],
    )

    # 06 Shunt Pure (primary dx must stay shunt; no forced P32)
    _run_case(
        "06",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=False, high_flow=False),
        expect_dx_contains="Shunt",
        expect_tags=["Shuntverdacht"],
        expect_modules=[],
    )

    # 07 Shunt + Liver Hint (enrichment + profile tag)
    _run_case(
        "07",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=True, high_flow=False),
        expect_dx_contains="Shunt",
        expect_tags=["Leber Profil A (Hyperdynam)"],
        expect_modules=["P32"],
    )

    # 08 Shunt + High Flow (enrichment)
    _run_case(
        "08",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=False, high_flow=True),
        expect_dx_contains="Shunt",
        expect_tags=["Shuntverdacht"],
        expect_modules=["P32"],
    )

    # 09 Precap PH (standard, no liver, no P32)
    _run_case(
        "09",
        _mk_env(mpap=35, pawp_rest=10, pvr=4.0, step_up_present=False, liver_hint=False),
        expect_dx_contains="Präkapilläre PH",
        expect_tags=["präkapillär"],
        expect_modules=[],
    )

    # 10 CpcPH (standard)
    _run_case(
        "10",
        _mk_env(mpap=45, pawp_rest=22, pvr=4.0, step_up_present=False, liver_hint=False),
        expect_dx_contains="CpcPH",
        expect_tags=["CpcPH"],
        expect_modules=[],
    )


    # --- Import policy regressions (v1.28) ---

    # A) map_payload_to_ui must not propagate 0 as a valid measurement (fehlend≠0)
    dummy_payload = {
        "patient": {"age_years": 0, "sex": "männlich", "height_cm": 180, "weight_kg": 0, "exam_date": "01.01.2025"},
        "timeseries": {"vitals": [{"time": "08:00", "bp_sys": 0, "bp_dia": 80, "bp_mean": 0, "hr": 0, "spo2": 0}], "bloodgas": [], "pressures": []},
        "canonical": {"rest": {"mpap": 0, "pawp": 12, "rap": 0, "spap": 60, "dpap": 20, "co_td": 0, "ci_td": None, "co_fick": 4.2, "ci_fick": 2.2, "pvr_wu": 0}},
        "quality": {"status": "green", "reasons": [], "warnings": []},
        "phases": {},
    }
    ui_map = map_payload_to_ui(dummy_payload, target="current")
    if ui_map.get("age") is not None:
        raise AssertionError("DOCX ui_map: age=0 must be treated as missing (None).")
    if ui_map.get("weight_kg") is not None:
        raise AssertionError("DOCX ui_map: weight_kg=0 must be treated as missing (None).")
    if ui_map.get("mpap_rest") is not None:
        raise AssertionError("DOCX ui_map: mpap_rest=0 must be treated as missing (None).")
    if ui_map.get("pvr_rest") is not None:
        raise AssertionError("DOCX ui_map: pvr_rest=0 must be treated as missing (None).")
    if ui_map.get("hr") is not None:
        raise AssertionError("DOCX ui_map: hr=0 must be treated as missing (None).")
    if ui_map.get("bp_sys") is not None:
        raise AssertionError("DOCX ui_map: bp_sys=0 must be treated as missing (None).")
    if ui_map.get("bp_mean") is not None:
        raise AssertionError("DOCX ui_map: bp_mean=0 must be treated as missing (None).")
    if ui_map.get("spo2") is not None:
        raise AssertionError("DOCX ui_map: spo2=0 must be treated as missing (None).")

    # B) apply_import_updates must allow first-time checkbox auto-fill, but preserve later manual corrections.
    ui0 = {"exercise_done": False}
    ui1, applied1 = apply_import_updates(
        ui=ui0,
        updates={"exercise_done": True},
        prev_applied_keys=[],
        prev_applied_values={},
        wipe_defaults={},
    )
    if ui1.get("exercise_done") is not True:
        raise AssertionError("Import merge: first-time bool autofill failed.")
    if "exercise_done" not in applied1:
        raise AssertionError("Import merge: applied-values missing for bool autofill.")

    # Manual correction after previous import must be preserved
    ui2, applied2 = apply_import_updates(
        ui={"exercise_done": False},
        updates={"exercise_done": True},
        prev_applied_keys=["exercise_done"],
        prev_applied_values={"exercise_done": True},
        wipe_defaults={},
    )
    if ui2.get("exercise_done") is not False:
        raise AssertionError("Import merge: manual bool correction was overwritten.")
    if "exercise_done" in applied2:
        raise AssertionError("Import merge: bool should not be re-applied after manual correction.")

    # C) Numeric 0 (Gradio empty) must be treated as empty for autofill
    ui3, applied3 = apply_import_updates(
        ui={"mpap_rest": 0},
        updates={"mpap_rest": 35.0},
        prev_applied_keys=[],
        prev_applied_values={},
        wipe_defaults={},
    )
    if ui3.get("mpap_rest") != 35.0:
        raise AssertionError("Import merge: numeric 0 was not treated as empty for autofill.")
    if "mpap_rest" not in applied3:
        raise AssertionError("Import merge: applied-values missing for numeric autofill.")

    # D) Stale wipe: clear previously imported values only if unchanged
    ui4, applied4 = apply_import_updates(
        ui={"mpap_rest": 35.0},
        updates={},
        prev_applied_keys=["mpap_rest"],
        prev_applied_values={"mpap_rest": 35.0},
        wipe_defaults={"mpap_rest": None},
    )
    if ui4.get("mpap_rest") is not None:
        raise AssertionError("Import merge: stale wipe did not clear unchanged imported value.")
    if applied4:
        raise AssertionError("Import merge: no updates expected in stale wipe scenario.")

    ui5, _applied5 = apply_import_updates(
        ui={"mpap_rest": 40.0},  # manual edit
        updates={},
        prev_applied_keys=["mpap_rest"],
        prev_applied_values={"mpap_rest": 35.0},
        wipe_defaults={"mpap_rest": None},
    )
    if ui5.get("mpap_rest") != 40.0:
        raise AssertionError("Import merge: manual numeric edit was incorrectly wiped.")

    print("OK: Regression suite passed (10 cases + import policy tests + echo import sanitization).")


if __name__ == "__main__":
    main()
