import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_ui_render_viz import (
    _build_rhk_plots_html_cached,
    _cache_json,
    _plots_cache_payload,
    build_rhk_plots_html,
)


def _sample_case():
    return {
        "raw": {"exercise_done": True},
        "derived": {
            "mpap": 30,
            "pawp": 12,
            "co": 4.5,
            "mpap_peak": 45,
            "pawp_peak": 22,
            "co_peak": 6.1,
            "mpap_rest": 28,
            "pvr_rest": 4.1,
            "ci_rest": 2.1,
        },
        "ui": {"prev_mpap": 24, "prev_pvr": 3.2, "prev_ci": 2.3},
    }


def _sample_docx_cur():
    return {
        "phases": {
            "base1": {"pressures": {"pa": {"mean": 26}}, "co": {"td_co": 4.1}},
            "exercise": {"pressures": {"pa": {"mean": 44}}, "co": {"td_co": 6.3}},
            "post": {"pressures": {"pa": {"mean": 30}}, "co": {"td_co": 4.7}},
        }
    }


def test_viz_renderer_cache_hits_on_identical_payloads() -> None:
    case = _sample_case()
    docx_cur = _sample_docx_cur()
    docx_prev = None

    _build_rhk_plots_html_cached.cache_clear()
    html_a = build_rhk_plots_html(case, docx_cur, docx_prev)
    html_b = build_rhk_plots_html(case, docx_cur, docx_prev)
    cache_info = _build_rhk_plots_html_cached.cache_info()

    assert "rhk-viz-grid" in html_a
    assert html_a == html_b
    assert cache_info.hits >= 1


def test_viz_cache_payload_ignores_irrelevant_case_keys() -> None:
    case_a = _sample_case()
    case_b = _sample_case()
    case_b["ui"]["transient_focus_field"] = "mpap_rest"
    case_b["debug"] = {"last_click": "plot_button"}

    payload_a = _plots_cache_payload(case_a, _sample_docx_cur(), None)
    payload_b = _plots_cache_payload(case_b, _sample_docx_cur(), None)

    assert _cache_json(payload_a) == _cache_json(payload_b)
