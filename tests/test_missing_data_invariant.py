"""Property-based check that missing data never produces definitive negatives.

Background
----------
The "missing ≠ negative" bug we fixed in cv_stauung_phrase / pv_stauung_phrase
is a class of bug, not a one-off. Anywhere a clinical narrative says
"keine Hinweise auf X / no evidence of X / not elevated", that statement must
be backed by an actual measurement of X — never by the *absence* of an input.

This test renders the doctor and patient reports under increasingly empty
input dicts and checks that no NEGATIVE-FINDING phrase appears that is
unsupported by available data. The list of forbidden phrases is curated;
extend it whenever a new "no/not/keine" assertion is introduced into a
template.

If a new bug of this class shows up in the future, this test is the first
place to add a regression entry — see the FORBIDDEN_WHEN_MISSING table at
the bottom of this file.
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook, load_textdb_blocks
from rhk_case import build_case, build_render_ctx
from rhk_reports import build_doctor_report, build_patient_report

RULES = load_rulebook(DEFAULT_RULEBOOK_PATH)
BLOCKS = load_textdb_blocks()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_doctor(ui: dict) -> str:
    case = build_case(dict(ui), RULES)
    return build_doctor_report(case, BLOCKS)


def _render_patient(ui: dict) -> str:
    case = build_case(dict(ui), RULES)
    return build_patient_report(case)


# ---------------------------------------------------------------------------
# Forbidden-phrase tables
# ---------------------------------------------------------------------------
#
# Format: (parameter_key_omitted, [forbidden_phrases_in_lowercase])
#
# Add new rows when adding new "no X / keine X"-style sentences whose
# correctness depends on a specific parameter being measured.

FORBIDDEN_WHEN_MISSING: list[tuple[str, list[str]]] = [
    # When RAP and IVC info are both missing, the report must NOT assert
    # "no central venous congestion" — that's the bug we just fixed.
    (
        "rap_rest",
        [
            "keine hinweise auf venöse kongestion",
            "keine zentralvenöse stauung",
            "keine zentrale oder pulmonalvenöse stauung",
            "keine zentralvenöse oder pulmonalvenöse stauung",
        ],
    ),
    # When PAWP is missing, the report must NOT negate pulmonary venous stasis.
    (
        "pawp_rest",
        [
            "keine hinweise auf pulmonalvenöse stauung",
            "keine pulmonalvenöse stauung",
        ],
    ),
]


# Minimal UI for a "PH likely" patient — chosen so that the case engine
# actually fires bundle templates. Each test then deletes one parameter and
# verifies that the corresponding negative phrases never appear.
def _ui_for_ph_baseline() -> dict:
    return {
        "age": 65,
        "sex": "weiblich",
        "height_cm": 168,
        "weight_kg": 72,
        "spap_rest": 55,
        "dpap_rest": 25,
        "mpap_rest": 35,
        "pawp_rest": 12,
        "rap_rest": 7,
        "co_rest": 4.5,
        "ci_rest": 2.6,
        "co_method": "Thermodilution",
        "who_fc": "II",
    }


def _ui_no_ph_baseline() -> dict:
    return {
        "age": 60,
        "sex": "männlich",
        "height_cm": 175,
        "weight_kg": 80,
        "spap_rest": 28,
        "dpap_rest": 10,
        "mpap_rest": 16,
        "pawp_rest": 9,
        "rap_rest": 4,
        "co_rest": 5.5,
        "ci_rest": 2.9,
        "co_method": "Thermodilution",
        "who_fc": "I",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("baseline", [_ui_for_ph_baseline, _ui_no_ph_baseline])
@pytest.mark.parametrize("param,forbidden", FORBIDDEN_WHEN_MISSING)
def test_missing_param_does_not_produce_negative_finding_in_doctor_report(
    baseline, param, forbidden
):
    """For every parameter listed, removing it from UI must not yield
    any phrase that asserts "no X" requires that parameter to assert.
    """
    ui = baseline()
    ui.pop(param, None)
    # Also drop IVC fallback channels for the RAP test, since IVC info also
    # makes congestion assessable.
    if param == "rap_rest":
        ui.pop("ivc_diam_mm", None)
        ui.pop("ivc_collapse", None)

    rep = _render_doctor(ui).lower()
    for phrase in forbidden:
        assert phrase not in rep, (
            f"Doctor report asserted {phrase!r} despite {param!r} being "
            f"unmeasured. This is a 'missing ≠ negative' regression."
        )


@pytest.mark.parametrize("baseline", [_ui_for_ph_baseline, _ui_no_ph_baseline])
@pytest.mark.parametrize("param,forbidden", FORBIDDEN_WHEN_MISSING)
def test_missing_param_does_not_produce_negative_finding_in_patient_report(
    baseline, param, forbidden
):
    ui = baseline()
    ui.pop(param, None)
    if param == "rap_rest":
        ui.pop("ivc_diam_mm", None)
        ui.pop("ivc_collapse", None)

    rep = _render_patient(ui).lower()
    for phrase in forbidden:
        assert phrase not in rep, (
            f"Patient report asserted {phrase!r} despite {param!r} being "
            f"unmeasured. This is a 'missing ≠ negative' regression."
        )


def test_assessability_flag_is_set_correctly_when_only_ivc_is_present():
    """RAP missing but IVC information present → still assessable."""
    ui = _ui_no_ph_baseline()
    ui.pop("rap_rest", None)
    ui["ivc_collapse"] = "ja"
    case = build_case(dict(ui), RULES)
    der = case.get("derived") or {}
    assert der.get("congestion_assessable") is True
    assert der.get("congestion_likely") is False


def test_assessability_flag_is_false_when_neither_rap_nor_ivc_present():
    ui = _ui_no_ph_baseline()
    ui.pop("rap_rest", None)
    ui.pop("ivc_diam_mm", None)
    ui.pop("ivc_collapse", None)
    case = build_case(dict(ui), RULES)
    der = case.get("derived") or {}
    assert der.get("congestion_assessable") is False


def test_render_ctx_does_not_emit_unconditional_negative_phrase_without_data():
    """Direct check at the ctx level — the central guard."""
    ui = _ui_no_ph_baseline()
    ui.pop("rap_rest", None)
    ui.pop("ivc_diam_mm", None)
    ui.pop("ivc_collapse", None)
    case = build_case(dict(ui), RULES)
    ctx = build_render_ctx(case)
    cv = (ctx.get("cv_stauung_phrase") or "").strip()
    assert cv == "", (
        f"cv_stauung_phrase must be empty when not assessable, got: {cv!r}"
    )
