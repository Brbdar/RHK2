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


def test_mixed_pattern_sets_mixed_flag_and_ph_suspect():
    ui = {
        "cpet_done": True,
        "cpet_rer_peak": 1.12,
        "cpet_peak_vo2_ml_kg_min": 12.0,
        "cpet_ve_vco2_slope": 44.0,
        "cpet_petco2_rest_mmhg": 28.0,
        "cpet_petco2_peak_mmhg": 22.0,
        "cpet_breathing_reserve_pct": 10.0,  # mechanical limitation
        "cpet_ve_peak_l_min": 95.0,
        "cpet_mvv_l_min": 100.0,
        "cpet_9panel_available": False,
    }

    out = spiro_logic.build_wizard_outputs(ui)
    der = out.get("derived") or {}

    assert der.get("cpet_mixed_vent_pattern") is True
    assert out.get("suspect_ph") is True


def test_analyze_exposes_parsed_input_data():
    ui = {
        "cpet_done": True,
        "cpet_rer_peak": 1.10,
        "cpet_peak_vo2_ml_kg_min": 13.0,
        "cpet_ve_vco2_slope": 36.0,
    }
    res = spiro_logic.analyze(ui)
    assert res is not None
    assert getattr(res, "input_data", None) is not None
    assert res.input_data.done is True


def test_parse_handles_string_booleans_and_rejects_bool_as_number():
    ui = {
        "cpet_done": "ja",
        "cpet_rer_peak": True,  # must not be parsed as 1.0
        "cpet_peak_vo2_ml_kg_min": "14,2",
        "cpet_ve_vco2_slope": "35",
        "cpet_angina": "false",
        "cpet_arrhythmia": "0",
    }
    res = spiro_logic.analyze(ui)
    assert res is not None
    assert res.input_data.done is True
    assert res.input_data.rer is None
    assert res.input_data.vo2_peak_rel == 14.2
    assert res.input_data.angina is False
    assert res.input_data.arrhythmia is False


def test_preview_analysis_runs_when_done_flag_is_false_but_values_exist():
    ui = {
        "cpet_done": False,
        "cpet_rer_peak": 1.06,
        "cpet_peak_vo2_ml_kg_min": 13.5,
        "cpet_ve_vco2_slope": 36.0,
        "cpet_petco2_rest_mmhg": 31.0,
    }
    out = spiro_logic.build_wizard_outputs(ui)
    assert (out.get("report_text") or "").startswith("Spiroergometrie CPET:")


def test_chrono_possible_flag_with_beta_blocker_context():
    ui = {
        "cpet_done": True,
        "cpet_rer_peak": 1.12,
        "cpet_hr_pct_pred": 72,
        "cpet_beta_blocker": True,
        "cpet_peak_vo2_ml_kg_min": 11.8,
        "cpet_ve_vco2_slope": 34.0,
    }
    out = spiro_logic.build_wizard_outputs(ui)
    der = out.get("derived") or {}
    assert der.get("cpet_chronotropic_possible") is True
    assert out.get("need_chrono_followups") is True
