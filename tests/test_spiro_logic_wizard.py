"""Regression test: Spiro-Logic wizard stability.

Expectations
 - build_wizard_outputs returns all expected keys.
 - 9-panel module outputs are present.
 - Report text includes the 9-panel line when 9-panel is documented.
"""

import spiro_logic


def test_build_wizard_outputs_contains_9panel_keys_and_report_line():
    ui = {
        "cpet_done": True,
        # Modul 1
        "cpet_rer_peak": 1.15,
        "cpet_hr_peak_bpm": 120,
        "cpet_hr_pct_pred": 80,
        "cpet_beta_blocker": False,
        "cpet_sinus_node_disorder": False,
        "cpet_hyperventilation": False,
        "cpet_chrono_comment": "",
        # Modul 2
        "cpet_peak_vo2_ml_kg_min": 14.0,
        "cpet_peak_vo2_pct_pred": 60.0,
        # Modul 3
        "cpet_peak_o2_pulse_ml": 8.0,
        "cpet_o2_pulse_pattern": "plateau",
        "cpet_o2_pulse_slope": 7.5,
        "cpet_bp_sys_peak": 160,
        "cpet_bp_dia_peak": 105,
        # Modul 4
        "cpet_ve_vco2_slope": 40.0,
        "cpet_petco2_rest_mmhg": 30,
        "cpet_petco2_peak_mmhg": 24,
        "cpet_petco2_vt1_mmhg": 30,
        "cpet_breathing_reserve_pct": 40,
        "cpet_spo2_nadir_pct": 92,
        "cpet_vo2_wr_slope_ml_min_w": 7.0,
        # Modul 5 (9 Felder)
        "cpet_9panel_available": True,
        "cpet_9panel_vt1_identified": "ja",
        "cpet_9panel_vt1_method": "V Slope",
        "cpet_9panel_rcp_identified": "unklar",
        "cpet_9panel_eov": True,
        "cpet_9panel_flowvol_limit": "nein",
        "cpet_9panel_vo2wr_pattern": "flach",
        "cpet_9panel_veeq_pattern": "frueh",
        "cpet_9panel_comment": "Beispiel",
    }

    out = spiro_logic.build_wizard_outputs(ui)

    for k in (
        "mod0_html",
        "mod1_html",
        "mod2_html",
        "mod3_html",
        "mod4_html",
        "mod5_html",
        "mod6_html",
        "mod7_html",
        "mod9_html",
        "modfinal_html",
        "overall_html",
        "report_text",
    ):
        assert k in out

    assert isinstance(out["mod9_html"], str) and out["mod9_html"].strip() != ""
    assert out.get("eov_present") is True

    # report_text should include 9-panel line when documented
    assert "9 Felder Grafik" in (out.get("report_text") or "")
