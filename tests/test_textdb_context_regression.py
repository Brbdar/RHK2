import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook, load_textdb_blocks, render_block
from rhk_case import build_case, build_render_ctx
from rhk_reports import random_example

_PH_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _collect_placeholders(blocks):
    keys = set()
    for blk in (blocks or {}).values():
        keys.update(_PH_RE.findall(str(getattr(blk, "template", "") or "")))
    return keys


def test_k20_is_low_pvr_bundle_and_k21_is_secondary_causes_bundle():
    blocks = load_textdb_blocks()

    assert "K20_B" in blocks and "K20_E" in blocks
    assert "normaler PVR" in blocks["K20_B"].title
    assert "keine präkapilläre PH" in blocks["K20_B"].title

    assert "K21_B" in blocks and "K21_E" in blocks
    assert "Sekundäre Ursachen" in blocks["K21_B"].title


def test_render_context_covers_all_textdb_placeholders():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    blocks = load_textdb_blocks()

    ui = random_example(scenario="pah_pre", seed=42)
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)

    missing = sorted(_collect_placeholders(blocks) - set((ctx or {}).keys()))
    assert missing == []


def test_k11_recommendation_has_no_empty_cteph_fragment():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    blocks = load_textdb_blocks()

    ui = random_example(scenario="cteph", seed=42)
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)
    txt = render_block(blocks["K11_E"], ctx)

    assert "bei ." not in txt


def _ui_skeleton_for_congestion_test():
    """Return a minimal but plausible UI dict.

    We need enough core values for the case pipeline to classify a finding —
    `random_example` would over-specify and inject IVC/RAP defaults that mask
    the exact behavior we want to test. Hardcoding the smallest viable UI
    makes the test target the assessability gating, not example synthesis.
    """
    return {
        "age": 65,
        "sex": "weiblich",
        "height_cm": 168,
        "weight_kg": 72,
        "spap_rest": 38,
        "dpap_rest": 14,
        "mpap_rest": 22,
        "pawp_rest": 10,
        "co_rest": 5.0,
        "ci_rest": 2.8,
        "co_method": "Thermodilution",
    }


def test_cv_stauung_phrase_is_silent_when_neither_rap_nor_ivc_available():
    """Without RAP and without IVC information, the report must NOT assert
    "Keine Hinweise auf venöse Kongestion" — that would be a false negative.
    """
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    ui = _ui_skeleton_for_congestion_test()
    # Explicitly leave rap_rest, ivc_diam_mm, ivc_collapse all unset
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)

    cv = str(ctx.get("cv_stauung_phrase") or "")
    assert "venöse Kongestion" not in cv, (
        "Without RAP/IVC data the report must not make any statement about "
        f"central venous congestion, but produced: {cv!r}"
    )
    assert cv.strip() == "", (
        f"Expected empty cv_stauung_phrase when not assessable, got: {cv!r}"
    )

    der = case.get("derived") or {}
    assert der.get("congestion_assessable") is False
    assert der.get("congestion_likely") is False


def test_pv_stauung_phrase_is_silent_when_pawp_missing():
    """Without PAWP, no "Keine Hinweise auf pulmonalvenöse Stauung"."""
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    ui = _ui_skeleton_for_congestion_test()
    ui.pop("pawp_rest")  # PAWP unknown
    ui["rap_rest"] = 6  # RAP normal → cv_stauung must NOT mention pv
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)

    pv = str(ctx.get("pv_stauung_phrase") or "")
    cv = str(ctx.get("cv_stauung_phrase") or "")
    assert pv.strip() == "", f"Expected empty pv_stauung_phrase, got: {pv!r}"
    # cv may legitimately say "Keine Hinweise auf venöse Kongestion." (RAP given, normal),
    # but must NOT include the combined phrase that also negates pv.
    assert "pulmonalvenöse Stauung" not in cv, (
        "Without PAWP we must not also negate pulmonalvenöse Stauung in the "
        f"combined phrase, but cv_stauung_phrase was: {cv!r}"
    )


def test_cv_stauung_phrase_negates_only_when_rap_or_ivc_available():
    """If RAP is given and normal, the report should explicitly state
    "Keine Hinweise auf venöse Kongestion" — that's an actual measurement-
    backed negative, not a missing-data artifact.
    """
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    ui = _ui_skeleton_for_congestion_test()
    ui["rap_rest"] = 4  # explicitly normal
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)

    cv = str(ctx.get("cv_stauung_phrase") or "")
    pv = str(ctx.get("pv_stauung_phrase") or "")
    # When BOTH cv and pv are assessable AND negative, the code collapses into
    # the combined phrase on cv with empty pv.
    assert "Keine Hinweise auf venöse Kongestion" in cv
    assert pv.strip() in {"", "Keine Hinweise auf pulmonalvenöse Stauung."}


def test_cv_stauung_phrase_positive_when_rap_elevated():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    ui = _ui_skeleton_for_congestion_test()
    ui["rap_rest"] = 14  # >= 12 → congestion_likely True
    case = build_case(dict(ui), rules)
    ctx = build_render_ctx(case)

    cv = str(ctx.get("cv_stauung_phrase") or "")
    assert cv.startswith("Hinweise auf venöse Kongestion"), (
        f"Expected positive cv_stauung_phrase when RAP elevated, got: {cv!r}"
    )
