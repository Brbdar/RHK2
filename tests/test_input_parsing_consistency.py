import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_case import build_case
from rhk_validation import parse_boolish, parse_floatish


def _ui_min():
    return {
        "height_cm": 174,
        "weight_kg": 84,
        "age": 45,
        "sex": "männlich",
        "spap_rest": 60,
        "dpap_rest": 25,
        "mpap_rest": 38,
        "pawp_rest": 10,
        "rap_rest": 8,
        "co_rest": 4.5,
        "sat_pa": 64,
    }


def test_parse_helpers_are_stable_for_common_ui_tokens():
    assert parse_boolish("ja") is True
    assert parse_boolish("true") is True
    assert parse_boolish("nein") is False
    assert parse_boolish("0") is False
    assert parse_floatish("14,2") == 14.2
    assert parse_floatish("nan") is None
    assert parse_floatish(True) is None
    assert parse_floatish("0", treat_zero_as_missing=True) is None


def test_build_case_uses_consistent_bool_parsing_for_done_flags():
    ui = _ui_min()
    ui.update(
        {
            "exercise_done": "false",
            "volume_challenge_done": "ja",
            "vaso_test_done": "0",
            "wedge_v_wave": "nein",
        }
    )
    case = build_case(dict(ui), [])
    der = case.get("derived") or {}
    assert der.get("exercise_done") is False
    assert der.get("volume_challenge_done") is True
    assert der.get("vaso_test_done") is False
    assert der.get("v_wave") is False
