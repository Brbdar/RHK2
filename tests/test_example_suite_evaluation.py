import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case
from rhk_reports import build_summary_dict, example_suite_case

_RULES = load_rulebook(DEFAULT_RULEBOOK_PATH)


def _suite_index_by_id(max_scan: int = 96):
    mapping = {}
    for i in range(max_scan):
        ui = example_suite_case(i)
        # Seit v27.4.24+: suite_id ist das kanonische Identifikations-Feld.
        # Fallback auf Name ("Fall E01") für Rückwärtskompatibilität.
        eid = str(ui.get("suite_id") or "").strip()
        if not eid:
            name = str(ui.get("name") or "")
            m = re.match(r"^(?:Fall\s+)?(E\d+)\b", name)
            assert m is not None, f"Suite-Fall ohne erkennbare ID: name={name!r}"
            eid = m.group(1)
        if eid in mapping:
            break
        mapping[eid] = i
    return mapping


def _warning_codes(case: dict):
    out = []
    for w in (case.get("warnings") or []):
        if isinstance(w, dict):
            c = str(w.get("code") or "").strip()
            if c:
                out.append(c)
    return out


def test_example_suite_cases_flow_into_evaluation_and_summary():
    idx_map = _suite_index_by_id()
    # Erwartung: Suite wurde erweitert und enthält mindestens E01..E16
    assert len(idx_map) >= 16
    for eid in ("E14", "E15", "E16"):
        assert eid in idx_map

    for _eid, idx in idx_map.items():
        ui = example_suite_case(idx)
        case = build_case(dict(ui), _RULES)

        assert isinstance(case.get("decision"), dict)
        assert str((case.get("decision") or {}).get("bundle") or "").strip()
        assert isinstance(case.get("scores"), dict)

        warns = case.get("warnings") or []
        assert isinstance(warns, list)
        assert int((case.get("derived") or {}).get("warnings_count") or 0) == len(warns)
        assert int((case.get("env") or {}).get("warnings_count") or 0) == len(warns)

        for w in warns:
            if not isinstance(w, dict):
                continue
            # Neue Warning-Struktur muss in der Bewertung erhalten bleiben
            assert str(w.get("severity") or "").strip()
            assert str(w.get("triage") or "").strip() in {"hint", "important", "critical"}
            assert str(w.get("category") or "").strip()
            assert str(w.get("message") or "").strip()
            assert "suggestion" in w

        summary = build_summary_dict(case)
        assert isinstance(summary, dict)
        assert summary.get("schema") == "rhk_summary_v1"
        assert isinstance(summary.get("classification"), dict)
        assert summary["classification"].get("bundle") == (case.get("decision") or {}).get("bundle")
        assert isinstance(summary.get("warnings"), list)


def test_example_suite_e14_safety_interactions_are_captured():
    idx = _suite_index_by_id()["E14"]
    case = build_case(dict(example_suite_case(idx)), _RULES)
    codes = set(_warning_codes(case))

    assert {"safety_nitrate_interaction", "safety_pde5_sgc_combo", "safety_hardship_missing_reason"}.issubset(codes)

    summary = build_summary_dict(case)
    summary_codes = {str(w.get("code") or "") for w in (summary.get("warnings") or []) if isinstance(w, dict)}
    assert "safety_nitrate_interaction" in summary_codes


def test_example_suite_e15_measurement_quality_is_captured():
    idx = _suite_index_by_id()["E15"]
    case = build_case(dict(example_suite_case(idx)), _RULES)
    codes = set(_warning_codes(case))

    # Kernchecks für Messqualität/Konsistenz
    assert "hemo_spap_dpap_order" in codes
    assert "hemo_mpap_gt_spap" in codes
    assert ("hemo_co_unit_ml_min" in codes) or ("hemo_co_very_high" in codes)
    assert "sat_extreme_jump_sat_ra_sat_rv" in codes


def test_example_suite_e16_documented_hardship_and_volume_gap_are_captured():
    idx = _suite_index_by_id()["E16"]
    case = build_case(dict(example_suite_case(idx)), _RULES)
    codes = set(_warning_codes(case))

    assert "safety_hardship_documented" in codes
    assert "vol_challenge_incomplete" in codes
