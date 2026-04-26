import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, _compare_rhk_trend, load_rulebook, load_textdb_blocks
from rhk_case import build_case
from rhk_reports import (
    build_doctor_report,
    build_doctor_report_template,
    build_internal_report,
    build_patient_report,
    build_summary_dict,
    random_example,
)

_RULES = load_rulebook(DEFAULT_RULEBOOK_PATH)
_BLOCKS = load_textdb_blocks()


def _render_pipeline(ui):
    case = build_case(dict(ui), _RULES)
    doc_t = build_doctor_report_template(case, _BLOCKS)
    doc = build_doctor_report(case, _BLOCKS)
    pat = build_patient_report(case)
    internal = build_internal_report(case)
    summary = build_summary_dict(case)
    return case, doc_t, doc, pat, internal, summary


def test_pipeline_accepts_non_string_prev_rhk_date():
    ui = random_example("pah_pre", seed=17)
    ui.update(
        {
            "prev_rhk_date": ["12/2025"],
            "prev_mpap": "42",
            "prev_pawp": "10",
            "prev_ci": "2.0",
            "prev_pvr": "5.2",
            "prev_rap": "8",
        }
    )

    case, doc_t, doc, pat, internal, summary = _render_pipeline(ui)
    trend = _compare_rhk_trend(case.get("ui") or {}, case.get("derived") or {})

    assert trend.get("has_prev") is True
    assert trend.get("prev_date") == "12/2025"
    assert "[" not in str(trend.get("sentence_doc") or "")
    assert isinstance(summary, dict) and summary
    for out in (doc_t, doc, pat, internal):
        assert isinstance(out, str) and len(out.strip()) > 0


def test_pipeline_survives_mixed_types_and_cleared_fields():
    base = random_example("pah_pre", seed=23)
    base.update(
        {
            "prev_rhk_date": "01/2025",
            "prev_mpap": 40,
            "prev_pawp": 11,
            "prev_ci": 2.1,
            "prev_pvr": 4.8,
        }
    )

    patches = [
        {
            "who_fc": ["III"],
            "prev_rhk_date": {"value": "11/2024"},
            "prev_tx_free": ["Sotatercept"],
            "prev_tx_added": {"value": "ERA"},
        },
        {
            "co_method": {"label": "Thermodilution"},
            "anticoag_status": {"value": "ja"},
            "ct_desc": ["Mosaik"],
            "abd_sono_desc": {"text": "unauffällig"},
        },
        {
            "prev_rhk_date": "",
            "prev_tx_free": "",
            "co_method": "",
            "who_fc": "",
            "eif2ak4_result": ["negativ"],
            "vaso_response_desc": {"label": "positiv"},
        },
        {
            "mpap_peak": None,
            "pawp_peak": None,
            "co_peak": None,
            "ci_peak": None,
            "sat_ra": None,
            "sat_rv": None,
            "sat_pa": None,
            "sat_ao": None,
            "ct_desc": "",
            "abd_sono_desc": "",
        },
    ]

    for patch in patches:
        ui = dict(base)
        ui.update(patch)
        case, doc_t, doc, pat, internal, summary = _render_pipeline(ui)

        assert isinstance(case, dict) and case.get("derived") is not None
        assert isinstance(summary, dict) and summary
        for out in (doc_t, doc, pat, internal):
            assert isinstance(out, str) and len(out.strip()) > 0


def test_pipeline_randomized_type_fuzz_no_crash():
    base = random_example("pah_pre", seed=123)
    keys = sorted(base.keys())
    weird = [None, "", [], {}, ["x"], {"value": "x"}, 123, False]
    rnd = random.Random(20260209)

    for _ in range(120):
        ui = dict(base)
        for k in rnd.sample(keys, rnd.randint(5, min(15, len(keys)))):
            ui[k] = rnd.choice(weird)

        if rnd.random() < 0.4:
            ui["prev_rhk_date"] = rnd.choice(weird)
            ui["prev_mpap"] = rnd.choice([None, 28, "35", ["37"]])
            ui["prev_pawp"] = rnd.choice([None, 9, "12", {"value": "11"}])
            ui["prev_ci"] = rnd.choice([None, 2.0, "2.4"])
            ui["prev_pvr"] = rnd.choice([None, 3.2, "4.8"])

        _, doc_t, doc, pat, internal, summary = _render_pipeline(ui)
        assert isinstance(summary, dict)
        for out in (doc_t, doc, pat, internal):
            assert isinstance(out, str)
