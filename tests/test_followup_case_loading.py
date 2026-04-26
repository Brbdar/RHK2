import datetime as dt
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import rhk_reports as reports
from rhk_followup import (
    build_followup_baseline_payload,
    derive_followup_case_filename,
    prepare_followup_ui,
    promote_docx_imports_for_followup,
)
from rhk_import_docx import DOCX_CURRENT_WIPE_DEFAULTS, DOCX_PREV_WIPE_DEFAULTS, map_payload_to_ui
from rhk_import_merge import apply_import_updates


def test_prepare_followup_ui_promotes_current_rhk_to_prev_and_clears_current():
    ui = {
        "rhk_date": "12/25",
        "spap_rest": 62,
        "dpap_rest": 24,
        "mpap_rest": 38,
        "pawp_rest": 11,
        "rap_rest": 7,
        "co_rest": 4.2,
        "ci_rest": 2.3,
        "pvr_rest": 6.4,
        "exercise_done": True,
        "spap_peak": 92,
        "modules": ["P01", "P03"],
        "modules_lvl1": ["P01"],
        "ph_reason_rhk": "keine Angabe",
    }
    out = prepare_followup_ui(ui)

    assert out["prev_rhk_date"] == "12/25"
    assert out["prev_mpap"] == 38
    assert out["prev_pawp"] == 11
    assert out["prev_ci"] == 2.3
    assert out["prev_pvr"] == 6.4
    assert out["rhk_date"] == ""
    assert out["mpap_rest"] is None
    assert out["pawp_rest"] is None
    assert out["exercise_done"] is False
    assert out["spap_peak"] is None
    assert out["modules"] == []
    assert out["modules_lvl1"] == []
    assert out["prev_is_initial"] is False
    assert out["ph_reason_rhk"] == "Verlaufskontrolle"


def test_prepare_followup_ui_coerces_non_scalar_date_fields():
    ui = {
        "rhk_date": ["03/2025"],
        "prev_label": {"text": "  "},
        "ph_reason_rhk": {"value": "keine Angabe"},
    }
    out = prepare_followup_ui(ui)

    assert out["prev_rhk_date"] == "03/2025"
    assert out["prev_label"] == "Aus Vorbefund (03/2025) übernommen."
    assert out["ph_reason_rhk"] == "Verlaufskontrolle"


def test_promote_docx_imports_moves_current_into_previous_slot():
    imports = {
        "docx_current": {
            "source": "cur",
            "_ui_applied_keys_current": ["rhk_date", "mpap_rest", "age"],
            "_ui_applied_values_current": {"rhk_date": "05.03.2026", "mpap_rest": 38, "age": 52},
        },
        "docx_prev": {"source": "prev_old"},
    }
    new_cur, new_prev = promote_docx_imports_for_followup(imports)
    assert new_cur is None
    assert new_prev["source"] == "cur"
    assert new_prev["_ui_applied_keys_prev"] == ["prev_mpap", "prev_rhk_date"]
    assert new_prev["_ui_applied_values_prev"] == {"prev_rhk_date": "05.03.2026", "prev_mpap": 38}
    assert "_ui_applied_keys_current" not in new_prev
    assert "_ui_applied_values_current" not in new_prev


def test_docx_wipe_defaults_cover_imported_ui_keys_and_skip_dead_prev_method():
    payload = {
        "patient": {
            "age_years": 42,
            "sex": "weiblich",
            "height_cm": 168,
            "weight_kg": 61,
            "exam_date": "05.03.2026",
        },
        "canonical": {"rest": {"mpap": 35, "co_td": 5.1, "ci_td": 2.8, "pvr_wu": 4.4}},
        "timeseries": {
            "vitals": [{"bp_sys": 110, "bp_dia": 70, "bp_mean": 84, "hr": 72, "spo2": 97}],
            "bloodgas": [{"site": "ART", "time": "08:00", "hb_g_dl": 13.4}],
        },
        "phases": {},
        "quality": {"status": "green", "reasons": []},
    }

    updates_cur = map_payload_to_ui(payload, target="current")
    cur_ui_keys = {k for k in updates_cur if not k.startswith("docx_import_")}
    assert cur_ui_keys <= set(DOCX_CURRENT_WIPE_DEFAULTS)

    updates_prev = map_payload_to_ui(payload, target="prev")
    prev_ui_keys = {k for k in updates_prev if not k.startswith("docx_import_")}
    assert prev_ui_keys <= set(DOCX_PREV_WIPE_DEFAULTS)
    assert "prev_co_method" not in updates_prev


def test_current_docx_undo_clears_imported_rhk_date_and_context_fields():
    payload = {
        "patient": {
            "age_years": 42,
            "sex": "weiblich",
            "height_cm": 168,
            "weight_kg": 61,
            "exam_date": "05.03.2026",
        },
        "canonical": {"rest": {"mpap": 35}},
        "timeseries": {"bloodgas": [{"site": "ART", "time": "08:00", "hb_g_dl": 13.4}]},
        "phases": {},
        "quality": {"status": "green", "reasons": []},
    }

    updates = map_payload_to_ui(payload, target="current")
    merged_ui, applied = apply_import_updates(
        ui={"sex": "keine Angabe", "rhk_date": "", "age": None, "hb_g_dl": None},
        updates=updates,
        prev_applied_keys=[],
        prev_applied_values={},
        wipe_defaults=DOCX_CURRENT_WIPE_DEFAULTS,
    )

    for key, value in applied.items():
        if key in DOCX_CURRENT_WIPE_DEFAULTS and merged_ui.get(key) == value:
            merged_ui[key] = DOCX_CURRENT_WIPE_DEFAULTS[key]

    assert merged_ui["rhk_date"] == ""
    assert merged_ui["age"] is None
    assert merged_ui["sex"] == "keine Angabe"
    assert merged_ui["hb_g_dl"] is None


def test_followup_baseline_payload_marks_mode_and_drops_stale_sections():
    old_data = {
        "ui": {"age": 45},
        "derived": {"mpap": 40},
        "decision": {"bundle": "K01"},
        "summary": {"dummy": True},
        "site": "DZL",
        "meta": {"foo": "bar"},
    }
    now = dt.datetime(2026, 2, 9, 10, 30, 0)
    payload = build_followup_baseline_payload(
        old_data,
        {"age": 46, "rhk_date": ""},
        imports={"docx_prev": {"x": 1}},
        source_name="old_case.json",
        now=now,
    )
    assert payload.get("derived") is None
    assert payload.get("decision") is None
    assert payload.get("summary") is None
    assert payload["ui"]["age"] == 46
    assert payload["site"] == "DZL"
    assert payload["meta"]["foo"] == "bar"
    assert payload["meta"]["load_mode"] == "followup"
    assert payload["meta"]["followup_source_file"] == "old_case.json"
    assert payload["meta"]["followup_prepared_at"] == "2026-02-09T10:30:00"


def test_followup_filename_and_report_fingerprint_optimizations():
    fn = derive_followup_case_filename("my_case.json", today=dt.date(2026, 2, 9))
    assert fn == "my_case_followup_20260209.json"
    fn_list = derive_followup_case_filename(["legacy_case.json"], today=dt.date(2026, 2, 9))
    assert fn_list == "legacy_case_followup_20260209.json"

    old_max = reports.REPORT_CACHE_MAXSIZE
    try:
        reports.REPORT_CACHE_MAXSIZE = 0
        assert reports._case_fingerprint({"ui": {"a": 1}, "imports": {"big": object()}}) == ""

        reports.REPORT_CACHE_MAXSIZE = 8
        case_a = {"ui": {"a": 1}, "derived": {"x": 2}, "imports": {"big": 1}}
        case_b = {"ui": {"a": 1}, "derived": {"x": 2}, "imports": {"big": 999}}
        case_c = {"ui": {"a": 2}, "derived": {"x": 2}, "imports": {"big": 1}}
        assert reports._case_fingerprint(case_a) == reports._case_fingerprint(case_b)
        assert reports._case_fingerprint(case_a) != reports._case_fingerprint(case_c)
    finally:
        reports.REPORT_CACHE_MAXSIZE = old_max
