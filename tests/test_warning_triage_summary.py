#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import collect_plausibility_warnings
from rhk_ui_render_summary import (
    _build_sticky_summary_html_cached,
    build_compare_overview_html,
    build_sticky_summary_html,
)


def _find_code(items, code):
    for it in items:
        if isinstance(it, dict) and str(it.get("code") or "") == code:
            return it
    return None


def test_collect_plausibility_warnings_adds_triage_and_quality_checks():
    ui = {
        "spap_rest": 20,
        "dpap_rest": 30,
        "mpap_rest": 25,
        "pawp_rest": 10,
        "rap_rest": 5,
        "co_rest": 5,
        "ci_rest": 2.2,
        "height_cm": 170,
        "weight_kg": 70,
        "sat_svc": 60,
        "sat_ra": 62,
        "sat_rv": 90,  # implausibly large jump
        "sat_pa": 64,
        "sat_ao": 97,
    }
    derived = {
        "mpap_calc": 27,
        "mpap_rest": 25,
        "co_rest": 5,
        "ci_rest": 2.2,
        "pvr_rest": 3.0,
        "bsa_m2": 1.82,
        "step_up_present": False,
    }

    warnings = collect_plausibility_warnings(ui, derived)

    order_warn = _find_code(warnings, "hemo_spap_dpap_order")
    assert order_warn is not None
    assert order_warn.get("triage") == "critical"
    assert order_warn.get("category") == "measurement_quality"
    assert "suggestion" in order_warn and str(order_warn.get("suggestion") or "").strip()

    sat_warn = _find_code(warnings, "sat_extreme_jump_sat_ra_sat_rv")
    assert sat_warn is not None
    assert sat_warn.get("category") == "measurement_quality"


def test_collect_plausibility_warnings_adds_interaction_safety_net():
    ui = {
        "on_nitrates": True,
        "ph_current_meds": ["PDE-5-Hemmer"],
        "pde5_hardship": True,
        "pde5_hardship_desc": "",
    }
    derived = {
        "ph_current_meds": ["PDE-5-Hemmer"],
        "ph_new_meds": [],
        "ph_tx_episodes": [{"drug": "Sildenafil", "status": "aktuell"}],
    }

    warnings = collect_plausibility_warnings(ui, derived)

    interaction = _find_code(warnings, "safety_nitrate_interaction")
    assert interaction is not None
    assert interaction.get("triage") == "critical"
    assert interaction.get("category") == "safety_interaction"

    hardship = _find_code(warnings, "safety_hardship_missing_reason")
    assert hardship is not None
    assert hardship.get("triage") == "important"


def test_collect_plausibility_warnings_flags_venous_sat_above_arterial():
    ui = {
        "sat_svc": 98,
        "sat_ra": 72,
        "sat_rv": 70,
        "sat_pa": 68,
        "sat_ao": 93,
    }
    derived = {}

    warnings = collect_plausibility_warnings(ui, derived)

    venous_warn = _find_code(warnings, "sat_venous_gt_ao_sat_svc")
    assert venous_warn is not None
    assert venous_warn.get("triage") == "important"
    assert venous_warn.get("category") == "measurement_quality"
    assert "sat_svc" in (venous_warn.get("fields") or [])
    assert "sat_ao" in (venous_warn.get("fields") or [])


def test_sticky_summary_renders_todo_panel_and_marker_payload():
    case = {
        "ui": {
            "on_nitrates": True,
            "ph_current_meds": ["PDE-5-Hemmer"],
            "pde5_hardship": True,
            "pde5_hardship_desc": "",
        },
        "derived": {
            "hemo_category": "precap",
            "rap_rest": 6,
            "mpap_rest": 38,
            "pawp_rest": 11,
            "pvr_rest": 5.4,
            "ci_rest": 2.1,
        },
        "scores": {"esc_ers_4s": "intermediate-high"},
        "warnings": [
            {
                "code": "hemo_spap_dpap_order",
                "severity": "error",
                "triage": "critical",
                "category": "measurement_quality",
                "message": "sPAP ist kleiner als dPAP.",
                "suggestion": "dPAP prüfen",
                "fields": ["spap_rest", "dpap_rest"],
            },
            {
                "code": "safety_hardship_missing_reason",
                "severity": "warn",
                "triage": "important",
                "category": "safety_interaction",
                "message": "Härtefall aktiviert, aber Begründung fehlt.",
                "fields": ["pde5_hardship_desc"],
            },
        ],
    }

    html = build_sticky_summary_html(case, flags={"dirty": True})

    assert "Klinische Sicherheit / To-Do" in html
    assert "Messqualität / Konsistenz" in html
    assert "Interaktions-Checkliste" in html
    assert "rhk-field-marker-payload" in html
    assert "spap_rest" in html
    assert "Kritisch" in html
    assert "Wichtig" in html


def test_sticky_summary_shows_missing_esc_ers_inputs():
    case = {
        "ui": {},
        "derived": {},
        "scores": {"esc_ers_4s": None, "esc_ers_4s_missing": ["WHO-FC", "6MWD"]},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "ESC/ERS unvollständig" in html
    assert "Fehlt: WHO-FC, 6MWD" in html
    assert "ESC/ERS unvollständig: WHO-FC, 6MWD" in html
    assert "who_fc" in html
    assert "six_mwd_m" in html


def test_sticky_summary_highlights_missing_hemo_core_fields():
    case = {
        "ui": {},
        "derived": {"hemo_category": "unknown"},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Hämo unvollständig" in html
    assert "Fehlt: mPAP, PAWP, PVR" in html
    assert "Hämodynamik unvollständig: mPAP, PAWP, PVR" in html
    assert "mpap_rest" in html
    assert "pawp_rest" in html
    assert "pvr_rest" in html


def test_sticky_summary_flags_missing_rhk_dates_when_data_present():
    case = {
        "ui": {"prev_mpap": 26},
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
        },
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "RHK-Datum fehlt" in html
    assert "Vorwerte ohne Datum" in html
    assert "RHK-Datum fehlt: aktuelles Untersuchungsdatum" in html
    assert "Vorwerte ohne Datum: Voruntersuchung" in html
    assert "rhk_date" in html
    assert "prev_rhk_date" in html


def test_sticky_summary_ignores_blank_prev_values_for_missing_date_warning():
    case = {
        "ui": {
            "prev_rap": "",
            "prev_mpap": "  ",
            "prev_pawp": None,
            "prev_ci": "",
            "prev_pvr": "",
        },
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
        },
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Vorwerte ohne Datum" not in html


def test_compare_overview_ignores_blank_prev_values():
    case = {
        "ui": {
            "prev_rap": "",
            "prev_mpap": " ",
            "prev_pawp": "",
            "prev_ci": "",
            "prev_pvr": "",
        },
        "derived": {
            "hemo_category": "precap",
            "rap_rest": 8,
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
            "ci_rest": 2.1,
        },
        "scores": {},
        "warnings": [],
    }

    html = build_compare_overview_html(case)

    assert html == ""


def test_sticky_summary_cache_picks_up_flag_warning_changes():
    case = {
        "ui": {},
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
        },
        "scores": {},
    }

    html_a = build_sticky_summary_html(
        case,
        flags={
            "warnings": [{"message": "Warnung A", "triage": "important", "category": "data_completeness"}],
        },
    )
    html_b = build_sticky_summary_html(
        case,
        flags={
            "warnings": [{"message": "Warnung B", "triage": "important", "category": "data_completeness"}],
        },
    )

    assert "Warnung A" in html_a
    assert "Warnung B" in html_b


def test_sticky_summary_cache_ignores_unrelated_ui_fields():
    _build_sticky_summary_html_cached.cache_clear()
    case = {
        "ui": {"story": "Alpha"},
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
        },
        "scores": {},
        "warnings": [],
    }
    html_a = build_sticky_summary_html(case)
    info_after_a = _build_sticky_summary_html_cached.cache_info()

    case["ui"]["story"] = "Beta"
    html_b = build_sticky_summary_html(case)
    info_after_b = _build_sticky_summary_html_cached.cache_info()

    assert html_a == html_b
    assert info_after_b.hits == info_after_a.hits + 1


def test_sticky_summary_cache_ignores_irrelevant_warning_keys():
    _build_sticky_summary_html_cached.cache_clear()
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "warn_x",
                "severity": "warn",
                "category": "measurement_quality",
                "message": "Achtung",
                "fields": ["mpap_rest"],
                "values": {"before": 1, "after": 2},
            }
        ],
    }

    html_a = build_sticky_summary_html(case)
    info_after_a = _build_sticky_summary_html_cached.cache_info()

    case["warnings"][0]["values"] = {"before": 10, "after": 20}
    html_b = build_sticky_summary_html(case)
    info_after_b = _build_sticky_summary_html_cached.cache_info()

    assert html_a == html_b
    assert info_after_b.hits == info_after_a.hits + 1


def test_sticky_summary_cache_tracks_flag_warnings_when_case_warnings_exist():
    _build_sticky_summary_html_cached.cache_clear()
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "case_warn",
                "severity": "warn",
                "category": "measurement_quality",
                "message": "Case Warnung",
                "fields": ["mpap_rest"],
            }
        ],
    }
    flags_a = {"warnings": [{"message": "Flag A", "triage": "hint", "category": "data_completeness"}]}
    flags_b = {"warnings": [{"message": "Flag B", "triage": "critical", "category": "data_completeness"}]}

    html_a = build_sticky_summary_html(case, flags=flags_a)
    info_after_a = _build_sticky_summary_html_cached.cache_info()
    html_b = build_sticky_summary_html(case, flags=flags_b)
    info_after_b = _build_sticky_summary_html_cached.cache_info()

    assert "Case Warnung" in html_a
    assert "Case Warnung" in html_b
    assert "Flag A" in html_a
    assert "Flag B" in html_b
    assert info_after_b.misses == info_after_a.misses + 1


def test_sticky_summary_dedupes_same_warning_from_case_and_flags():
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "same_warn",
                "severity": "warn",
                "triage": "important",
                "category": "measurement_quality",
                "message": "Doppelte Warnung",
                "fields": ["mpap_rest"],
            }
        ],
    }
    flags = {
        "warnings": [
            {
                "code": "same_warn",
                "severity": "error",
                "triage": "critical",
                "category": "measurement_quality",
                "message": "Doppelte Warnung",
                "fields": ["pawp_rest"],
            }
        ]
    }

    html = build_sticky_summary_html(case, flags=flags)

    assert html.count("<div class='rhk-todo-item-title'>Doppelte Warnung</div>") == 1
    assert "mpap_rest" in html
    assert "pawp_rest" in html


def test_sticky_summary_measurement_quality_not_duplicated_in_todo_columns():
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "hemo_spap_dpap_order",
                "severity": "error",
                "triage": "critical",
                "category": "measurement_quality",
                "message": "sPAP ist kleiner als dPAP.",
                "fields": ["spap_rest", "dpap_rest"],
            }
        ],
    }

    html = build_sticky_summary_html(case)

    assert html.count("<div class='rhk-todo-item-title'>sPAP ist kleiner als dPAP.</div>") == 1


def test_sticky_summary_prioritizes_relevant_measurement_quality_warnings():
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "hemo_spap_dpap_order",
                "severity": "error",
                "triage": "critical",
                "category": "measurement_quality",
                "message": "sPAP ist kleiner als dPAP.",
                "fields": ["spap_rest", "dpap_rest"],
            },
            {
                "code": "vol_challenge_incomplete",
                "severity": "info",
                "triage": "hint",
                "category": "measurement_quality",
                "message": "Volumenchallenge unvollständig dokumentiert.",
                "fields": ["pawp_pre", "pawp_post"],
            },
        ],
    }

    html = build_sticky_summary_html(case)

    assert "🔴 Kritisch (1)" in html
    assert "🔵 Hinweis (0)" in html
    assert "Messqualität / Konsistenz (zusätzliche Hinweise)" in html
    assert "Volumenchallenge unvollständig dokumentiert." in html


def test_sticky_summary_dedupes_duplicate_warnings_and_merges_fields():
    case = {
        "ui": {},
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 11, "pvr_rest": 4.2},
        "scores": {},
        "warnings": [
            {
                "code": "echo_dup",
                "severity": "warn",
                "triage": "important",
                "category": "measurement_quality",
                "message": "Dopplungstest",
                "fields": ["spap_rest"],
            },
            {
                "code": "echo_dup",
                "severity": "error",
                "triage": "critical",
                "category": "measurement_quality",
                "message": "Dopplungstest",
                "fields": ["dpap_rest"],
            },
        ],
    }

    html = build_sticky_summary_html(case)

    assert html.count("<div class='rhk-todo-item-title'>Dopplungstest</div>") == 1
    assert "spap_rest" in html
    assert "dpap_rest" in html


def test_sticky_summary_adds_renal_safety_todo_for_low_egfr():
    case = {
        "ui": {
            "creatinine_mg_dl": 2.1,
            "age": 74,
            "sex": "m",
        },
        "derived": {"hemo_category": "precap", "mpap_rest": 34, "pawp_rest": 12, "pvr_rest": 4.8},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "eGFR" in html
    assert "Nierenfunktion eingeschränkt" in html
    assert "Kontrastmittel-/Therapieplanung prüfen" in html
    assert "egfr_ml_min_1_73" in html
    assert "creatinine_mg_dl" in html


def test_sticky_summary_flags_egfr_missing_context_when_creatinine_exists():
    case = {
        "ui": {
            "creatinine_mg_dl": 1.6,
            "age": 68,
            "sex": "",
        },
        "derived": {"hemo_category": "precap", "mpap_rest": 28, "pawp_rest": 10, "pvr_rest": 3.1},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "eGFR nicht berechenbar" in html
    assert "Alter/Geschlecht fehlen" in html
    assert "age" in html
    assert "sex" in html


def test_sticky_summary_uses_flag_warnings_when_case_warnings_empty():
    case = {
        "ui": {},
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 30,
            "pawp_rest": 10,
            "pvr_rest": 3.8,
        },
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(
        case,
        flags={
            "warnings": [
                {
                    "code": "runtime_warn",
                    "message": "Laufzeitwarnung",
                    "triage": "important",
                    "category": "data_completeness",
                }
            ]
        },
    )

    assert "Laufzeitwarnung" in html
    assert "🟡 Wichtig 1" in html


def test_sticky_summary_interaction_checklist_treats_nein_as_false():
    case = {
        "ui": {
            "on_nitrates": "Nein",
            "ph_current_meds": ["Sildenafil"],
            "pde5_hardship": "Nein",
            "pde5_hardship_desc": "",
        },
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 10, "pvr_rest": 3.8},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Kontraindikation: Medikation sofort prüfen." not in html
    assert "Keine harte Kontraindikation erkannt." in html
    assert "Härtefall aktiv, Begründung fehlt." not in html
    assert "Nicht aktiviert." in html


def test_sticky_summary_interaction_checklist_treats_ja_as_true():
    case = {
        "ui": {
            "on_nitrates": "Ja",
            "rhk_date": "2026-03-20",
            "ph_current_meds": ["Sildenafil"],
            "pde5_hardship": "Ja",
            "pde5_hardship_desc": "",
        },
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 10, "pvr_rest": 3.8},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Kontraindikation: Medikation sofort prüfen." in html
    assert "Härtefall aktiv, Begründung fehlt." in html


def test_sticky_summary_adds_prioritized_open_todo_chip():
    case = {
        "ui": {
            "on_nitrates": "Ja",
            "rhk_date": "2026-03-20",
            "ph_current_meds": ["Sildenafil"],
            "pde5_hardship": "Ja",
            "pde5_hardship_desc": "",
        },
        "derived": {"hemo_category": "precap", "mpap_rest": 30, "pawp_rest": 10, "pvr_rest": 3.8},
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Offen: 2 priorisiert" in html
    assert "Kritisch: 1, Wichtig: 1" in html


def test_sticky_summary_adds_hemo_trend_chip_for_worsening_course():
    case = {
        "ui": {
            "prev_mpap": 24,
            "prev_pvr": 2.8,
            "prev_ci": 2.4,
        },
        "derived": {
            "hemo_category": "precap",
            "mpap_rest": 32,
            "pawp_rest": 11,
            "pvr_rest": 4.1,
            "ci_rest": 1.9,
        },
        "scores": {},
        "warnings": [],
    }

    html = build_sticky_summary_html(case)

    assert "Verlauf: schlechter" in html
    assert "schlechter: mPAP, PVR, CI" in html
