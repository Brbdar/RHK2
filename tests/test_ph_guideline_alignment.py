#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case
from rhk_echo_guidelines import compute_echo_ph_probability
from rhk_echo_report_doctor import build_echo_doctor_report
from rhk_interpretation import build_intelligent_interpretation

RULES = load_rulebook(DEFAULT_RULEBOOK_PATH)


def _recommendations(case) -> str:
    decision = case.get("decision") or {}
    if isinstance(decision, dict):
        return " ".join(decision.get("recommendations") or [])
    return " ".join(getattr(decision, "recommendations", []) or [])


def test_echo_probability_requires_two_sign_categories_for_high_probability():
    res = compute_echo_ph_probability({
        "trv_ms": 3.0,
        "rv_lv_ratio": 1.2,  # only category A
    })
    assert res.probability == "intermediär"
    assert res.category_count == 1


def test_echo_report_does_not_classify_pasp_only_as_probability():
    report = build_echo_doctor_report({
        "ui": {
            "echo_done": True,
            "pasp_echo": 55,
        }
    })
    assert "PH Echo-Screening eingeschränkt beurteilbar" in report
    assert "PASP allein ersetzt die ESC/ERS-Wahrscheinlichkeitsklassifikation nicht." in report


def test_interpretation_recognizes_vascular_exercise_pattern_key():
    txt = build_intelligent_interpretation({}, {
        "mpap_rest": 18,
        "pawp_rest": 10,
        "pvr_rest": 1.5,
        "exercise_done": True,
        "exercise_qc_hard_stop": False,
        "exercise_interpretability": "ok",
        "exercise_pattern": "exercise_2pt_pv_dominant",
        "dco": 3.0,
        "mpap_co_slope": 4.0,
        "pawp_co_slope": 1.0,
        "tpg_co_slope": 3.0,
        "step_up_present": False,
        "wedge_v_wave": False,
        "atrial_fib": False,
        "rap_v_wave_flag": False,
        "rv_dip_plateau_flag": False,
    })
    assert "pulmonalvaskulär dominanter Komponente" in txt


def test_interpretation_respects_exercise_hard_stop_alias():
    txt = build_intelligent_interpretation({}, {
        "mpap_rest": 18,
        "pawp_rest": 10,
        "pvr_rest": 1.5,
        "exercise_done": True,
        "exercise_qc_hard_stop": True,
        "exercise_interpretability": "hard_stop",
        "exercise_pattern": "exercise_2pt_pv_dominant",
    })
    assert "Belastungsauswertung nicht verwertbar" in txt
    assert "pulmonalvaskulär dominanter Komponente" not in txt


def test_high_risk_esc4_prioritizes_advanced_modules():
    case = build_case({
        "mpap_rest": 45,
        "pawp_rest": 10,
        "co_rest": 4.0,
        "who_fc": "IV",
        "six_mwd_m": 120,
        "bnp_kind": "NT-proBNP",
        "bnp_value": 5000,
    }, RULES)
    pol = case["derived"]["p_module_policy"]
    assert pol["levels"]["P06"] == 1
    assert pol["levels"]["P25"] == 1


def test_riociguat_guard_warns_outside_group1_or_4():
    case = build_case({
        "mpap_rest": 38,
        "pawp_rest": 10,
        "co_rest": 4.2,
        "ct_ild": True,
        "lufu_restrictive": True,
        "ph_known_dx": "Gruppe 3",
        "ph_tx_table": [
            ["Riociguat", "aktuell", "", "", "", ""],
        ],
    }, RULES)
    recs = _recommendations(case)
    assert "Riociguat ist als PH-Therapiepfad für PAH" in recs


def test_ccb_guard_requires_documented_vasoreactivity():
    case = build_case({
        "mpap_rest": 40,
        "pawp_rest": 10,
        "co_rest": 4.0,
        "ph_known_dx": "PAH",
        "ph_tx_table": [
            ["Kalziumantagonist", "aktuell", "", "", "", ""],
        ],
    }, RULES)
    recs = _recommendations(case)
    assert "Kalziumantagonisten-Pfad" in recs
