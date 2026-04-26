import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_ui_cpet import build_cpet_risk_payload, cache_json, render_cpet_risk_html_cached


def test_cpet_risk_renderer_cache_hits_on_identical_payloads() -> None:
    payload = build_cpet_risk_payload(
        True,
        peak_vo2=13.8,
        peak_vo2_pct=58,
        vo2_peak_reached="ja",
        vt1_method="V-Slope",
        vt1_manual_checked=False,
        vt1_time_min=4.8,
        vevco2_slope=39.0,
        petco2_vt1=28.0,
        vevco2_vt1=33.0,
        o2pulse_pct=62,
        vo2_wr_slope=8.1,
        vo2_vt1=9.8,
        spo2_nadir=92,
        rer_peak=1.12,
        hr_peak=128,
        o2_pulse_pattern="flach",
    )
    payload_json = cache_json(payload)

    render_cpet_risk_html_cached.cache_clear()
    html_a = render_cpet_risk_html_cached(payload_json)
    html_b = render_cpet_risk_html_cached(payload_json)
    cache_info = render_cpet_risk_html_cached.cache_info()

    assert "ESC/ERS CPET Risiko" in html_a
    assert html_a == html_b
    assert cache_info.hits >= 1


def test_cpet_risk_renderer_reports_missing_data_when_not_done() -> None:
    payload = build_cpet_risk_payload(
        False,
        peak_vo2=None,
        peak_vo2_pct=None,
        vo2_peak_reached=None,
        vt1_method=None,
        vt1_manual_checked=None,
        vt1_time_min=None,
        vevco2_slope=None,
        petco2_vt1=None,
        vevco2_vt1=None,
        o2pulse_pct=None,
        vo2_wr_slope=None,
        vo2_vt1=None,
        spo2_nadir=None,
        rer_peak=None,
        hr_peak=None,
        o2_pulse_pattern=None,
    )

    html = render_cpet_risk_html_cached(cache_json(payload))
    assert "Keine CPET Daten erfasst" in html
