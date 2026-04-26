import os
import sys

# Ensure project root in path (flat repo)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case


def test_build_case_sets_spiro_ph_suspect_for_mixed_pattern():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    ui = {
        "cpet_done": True,
        "cpet_rer_peak": 1.12,
        "cpet_peak_vo2_ml_kg_min": 12.0,
        "cpet_ve_vco2_slope": 44.0,
        "cpet_petco2_rest_mmhg": 28.0,
        "cpet_petco2_peak_mmhg": 22.0,
        "cpet_breathing_reserve_pct": 10.0,
        "cpet_ve_peak_l_min": 95.0,
        "cpet_mvv_l_min": 100.0,
        "cpet_9panel_available": False,
    }

    case = build_case(dict(ui), rules)
    der = case.get("derived") or {}
    assert der.get("cpet_spiro_suspect_ph") is True
