import copy
import os
import sys

# Ensure project root in path (flat repo)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_case import build_case


def _base_ui():
    # Minimal but stable baseline for build_case + risk scores
    return {
        "height_cm": 174,
        "weight_kg": 84,
        "age": 45,
        "sex": "männlich",
        # Rest hemodynamics
        "spap_rest": 60,
        "dpap_rest": 25,
        "mpap_rest": 38,
        "pawp_rest": 10,
        "rap_rest": 8,
        "co_rest": 4.5,
        "sat_pa": 64,
        # Echo/CMR
        "tapse_mm": 18,
        "ra_esa_cm2": 20,
        "pericardial_effusion": "kein",
        "cmr_rvef": 45,
        # Clinical / functional
        "who_fc": "III",
        "six_mwd_m": 320,
        "syncope": "keine",
        # Biomarkers
        "bnp_kind": "NT-proBNP",
        "bnp_value": 900,
        "entresto": False,
        # CPET
        "cpet_peak_vo2_ml_kg_min": 12,
        "cpet_peak_vo2_pct_pred": 45,
        "cpet_ve_vco2_slope": 40,
    }


def _scores(case: dict):
    scores = case.get("scores") or {}
    return {
        "esc3": scores.get("esc_ers_3s"),
        "esc4": scores.get("esc_ers_4s"),
        "reveal": scores.get("reveal_lite2"),
        "comp": scores.get("esc_ers_comprehensive"),
        "comp_n": scores.get("esc_ers_comprehensive_n"),
        "comp_mean": scores.get("esc_ers_comprehensive_mean"),
    }


def test_risk_inputs_change_scores_when_varied():
    base = _base_ui()

    base_case = build_case(copy.deepcopy(base), [])
    base_scores = _scores(base_case)
    assert base_scores["comp"] is not None, "Baseline comprehensive risk score should be computable"

    # key -> (low risk value, high risk value)
    variants = {
        "who_fc": ("II", "IV"),
        "six_mwd_m": (520, 120),
        "bnp_value": (150, 2500),
        "ra_esa_cm2": (15, 30),
        "pericardial_effusion": ("kein", "relevant"),
        "rap_rest": (6, 18),
        "co_rest": (6.5, 2.5),  # impacts CI
        "sat_pa": (68, 55),
        "cmr_rvef": (58, 30),
        "cpet_peak_vo2_ml_kg_min": (18, 8),
        "cpet_peak_vo2_pct_pred": (75, 25),
        "cpet_ve_vco2_slope": (32, 55),
    }

    # For each risk-relevant input, toggling it should change at least one score bucket or comprehensive mean/params.
    for key, (v_low, v_high) in variants.items():
        ui_low = copy.deepcopy(base)
        ui_high = copy.deepcopy(base)

        ui_low[key] = v_low
        ui_high[key] = v_high

        c_low = build_case(ui_low, [])
        c_high = build_case(ui_high, [])

        s_low = _scores(c_low)
        s_high = _scores(c_high)

        changed = (
            (s_low["esc3"] != s_high["esc3"])
            or (s_low["esc4"] != s_high["esc4"])
            or (s_low["reveal"] != s_high["reveal"])
            or (s_low["comp"] != s_high["comp"])
            or (s_low["comp_n"] != s_high["comp_n"])
            or (s_low.get("comp_mean") != s_high.get("comp_mean"))
        )
        assert changed, f"Risk-related input '{key}' did not change any risk output (possible dead input)"

