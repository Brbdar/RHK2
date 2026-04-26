import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import Decision, compute_p_module_policy
from rhk_pmodules import apply_p_modules


def test_compute_p_module_policy_handles_ja_nein_strings() -> None:
    ui = {
        "sex": "weiblich",
        "age": 55,
        "hb_g_dl": 13.5,
        "ct_ild": "nein",
        "lufu_restrictive": "nein",
        "ild_type": "",
        "antifibrotic_status": "nein",
        "anticoag_status": "nein",
        "atrial_fib": "nein",
        "vq_defect": "nein",
        "ct_embolie": "nein",
        "lufu_done": "ja",
        "lufu_obstructive": "nein",
        "lufu_diffusion": "nein",
        "exercise_done": "nein",
        "immunology_pos": "nein",
        "virology_pos": "nein",
        "mutation_pos": "nein",
        "chd_pos": "nein",
        "ct_koronarkalk": "nein",
        "ct_done": "nein",
        "ltot": "nein",
        "who_fc": "III",
    }
    derived = {
        "ph_etiology": {"candidates": [], "clear_leader": False, "leading_group": None},
        "hemo_category": "unknown",
        "risk_category": "intermediate",
        "congestion_likely": "nein",
    }

    policy = compute_p_module_policy(ui, derived, Decision())
    disabled = policy.get("disabled") or {}
    levels = policy.get("levels") or {}

    # "nein" must not be treated as truthy.
    assert "P08" in disabled
    assert "P10" in disabled
    assert "P12" in disabled
    assert "P15" not in disabled
    assert "P17" in disabled
    assert "P18" in disabled
    assert "P20" in disabled
    assert levels.get("P01") == 3


def test_apply_p_modules_handles_boolish_strings() -> None:
    mods = apply_p_modules(
        ui={},
        derived={
            "dyspnea_present": "ja",
            "cpet_available": "nein",
            "ph_present": "ja",
            "high_risk": "nein",
        },
        base_modules=[],
    )

    assert "P43" in mods
    assert "P51" in mods

    mods_with_cpet = apply_p_modules(
        ui={},
        derived={"dyspnea_present": "ja", "cpet_available": "ja"},
        base_modules=[],
    )
    assert "P43" not in mods_with_cpet
