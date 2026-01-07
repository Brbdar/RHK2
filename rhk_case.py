#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – Case Builder (split from rhk_app_web_master.py).

Enthält:
- build_case() + Helfer (Normalisierung, Ableitungen, Dashboard-HTML, Render-Context, dynamische Module)

Hinweis: Inhalt ist 1:1 aus der Master-Datei extrahiert, um Verhalten unverändert zu lassen.
"""

from __future__ import annotations

# Import *inkl. underscore-Helpers* aus rhk_base (rhk_base setzt __all__ entsprechend).
from rhk_base import *  # noqa: F401,F403

def build_case(ui: Dict[str, Any], rules: List[Rule]) -> Dict[str, Any]:
    # Normalize modules (UI-Labels -> IDs)
    try:
        # P-Module: Levels (v24) + Legacy-Feld "modules" zusammenführen
        _mods: List[str] = []
        for _k in ("modules_lvl1", "modules_lvl2", "modules_lvl3", "modules"):
            _v = ui.get(_k)
            if isinstance(_v, list):
                _mods.extend([str(x) for x in _v if x])
        ui["modules"] = _normalize_module_ids(_mods)
    except Exception:
        pass

    # ---- basic anthropometrics ----
    height_cm = _safe_float(ui.get("height_cm"))
    weight_kg = _safe_float(ui.get("weight_kg"))
    age = _safe_float(ui.get("age"))
    sex = ui.get("sex")

    bsa = calc_bsa(height_cm, weight_kg)
    bmi = calc_bmi(height_cm, weight_kg)

    # ---- Rest hemodynamics (allow optional direct entries) ----
    spap = _safe_float(ui.get("spap_rest"))
    dpap = _safe_float(ui.get("dpap_rest"))
    mpap_in = _safe_float(ui.get("mpap_rest"))  # optional
    pawp = _safe_float(ui.get("pawp_rest"))
    rap = _safe_float(ui.get("rap_rest"))

    co_in = _safe_float(ui.get("co_rest"))
    ci_in = _safe_float(ui.get("ci_rest"))  # optional

    # NOTE (v26): In some Gradio builds, empty gr.Number fields may roundtrip as 0.
    # mPAP=0 is physiologisch nicht plausibel, wenn sPAP/dPAP valide Werte tragen.
    # Deshalb behandeln wir mpap=0 in diesem Kontext als "nicht angegeben" und
    # berechnen mPAP aus sPAP/dPAP.
    if (
        mpap_in is not None
        and mpap_in == 0
        and spap is not None
        and spap > 10
        and dpap is not None
        and dpap >= 0
    ):
        mpap_in = None

    mpap_calc = calc_mpap_from_spap_dpap(spap, dpap)
    mpap = mpap_in if mpap_in is not None else mpap_calc

    # CO/CI consistency: prefer CO; else infer CO from CI
    co = co_in
    if co is None and ci_in is not None and bsa is not None:
        co = ci_in * bsa

    ci = ci_in
    if ci is None and co is not None and bsa is not None:
        ci = co / bsa

    # PVR optional input
    pvr_in = _safe_float(ui.get("pvr_rest"))
    pvr_calc = None
    if mpap is not None and pawp is not None and co is not None and co > 0:
        pvr_calc = (mpap - pawp) / co
    pvr = pvr_in if pvr_in is not None else pvr_calc

    # Indexed PVR
    pvri = None
    if mpap is not None and pawp is not None and ci is not None and ci > 0:
        pvri = (mpap - pawp) / ci

    tpg = (mpap - pawp) if (mpap is not None and pawp is not None) else None
    dpg = (dpap - pawp) if (dpap is not None and pawp is not None) else None

    # ---- Exercise hemodynamics (optional) ----
    spap_pk = _safe_float(ui.get("spap_peak"))
    dpap_pk = _safe_float(ui.get("dpap_peak"))
    mpap_pk_in = _safe_float(ui.get("mpap_peak"))
    if (
        mpap_pk_in is not None
        and mpap_pk_in == 0
        and spap_pk is not None
        and spap_pk > 10
        and dpap_pk is not None
        and dpap_pk >= 0
    ):
        mpap_pk_in = None
    mpap_pk_calc = calc_mpap_from_spap_dpap(spap_pk, dpap_pk)
    mpap_peak = mpap_pk_in if mpap_pk_in is not None else mpap_pk_calc

    pawp_peak = _safe_float(ui.get("pawp_peak"))
    co_peak = _safe_float(ui.get("co_peak"))
    ci_peak_in = _safe_float(ui.get("ci_peak"))
    # Optional: allow entering CI directly (if CO not documented).
    if co_peak is None and ci_peak_in is not None and bsa is not None:
        co_peak = ci_peak_in * bsa
    ci_peak = None
    if ci_peak_in is not None:
        ci_peak = ci_peak_in
    elif co_peak is not None and bsa is not None:
        ci_peak = co_peak / bsa

    exercise_done = bool(ui.get("exercise_done")) or (co_peak is not None or mpap_peak is not None or pawp_peak is not None)

    # Slopes: robust against tiny numerical differences
    mpap_co_slope = None
    pawp_co_slope = None
    if exercise_done and co is not None and co_peak is not None:
        dco = co_peak - co
        if abs(dco) >= 0.05:  # avoid division by ~0 due to rounding / partial documentation
            if mpap is not None and mpap_peak is not None:
                mpap_co_slope = (mpap_peak - mpap) / dco
            if pawp is not None and pawp_peak is not None:
                pawp_co_slope = (pawp_peak - pawp) / dco

    exercise_pattern = classify_exercise_pattern(mpap_co_slope, pawp_co_slope) if exercise_done else None

    delta_spap = (spap_pk - spap) if (spap is not None and spap_pk is not None) else None

    # Adaptation type (klinische Kurzregel / Wunschlogik)
    # User request: ΔsPAP < 30 mmHg → heterometrischer Adaptionstyp
    # (symmetrisch dazu: ΔsPAP ≥ 30 mmHg → homeometrischer Adaptionstyp)
    adaptation_type = None
    if exercise_done and delta_spap is not None:
        adaptation_type = "heterometric" if delta_spap < 30 else "homeometric"

    # ---- Volume challenge ----
    volume_done = bool(ui.get("volume_challenge_done"))
    pawp_pre = _safe_float(ui.get("pawp_pre"))
    pawp_post = _safe_float(ui.get("pawp_post"))
    mpap_pre = _safe_float(ui.get("mpap_pre"))
    mpap_post = _safe_float(ui.get("mpap_post"))
    pawp_delta = (pawp_post - pawp_pre) if (pawp_pre is not None and pawp_post is not None) else None
    mpap_delta = (mpap_post - mpap_pre) if (mpap_pre is not None and mpap_post is not None) else None

    # ---- Vasoreactivity ----
    vaso_done = bool(ui.get("vaso_test_done"))
    vaso_response = ui.get("vaso_response_desc") or None
    vaso_agent = ui.get("vaso_agent") or None
    vaso_mpap_pre = _safe_float(ui.get("vaso_mpap_pre"))
    vaso_co_pre = _safe_float(ui.get("vaso_co_pre"))
    vaso_mpap_post = _safe_float(ui.get("vaso_mpap_post"))
    vaso_co_post = _safe_float(ui.get("vaso_co_post"))
    vaso_responder = None
    if vaso_done and vaso_mpap_pre is not None and vaso_mpap_post is not None and vaso_co_pre is not None and vaso_co_post is not None:
        # Acute vasoreactivity responder (classic criterion): mPAP drop ≥10 to ≤40 with preserved/increased CO
        vaso_responder = (vaso_mpap_pre - vaso_mpap_post >= 10) and (vaso_mpap_post <= 40) and (vaso_co_post >= vaso_co_pre)

    # ---- Echo / imaging context ----
    lvef = _safe_float(ui.get("lvef"))
    la_enlarged = bool(ui.get("la_enlarged"))
    ee_ratio = _safe_float(ui.get("ee_ratio"))
    pasp_echo = _safe_float(ui.get("pasp_echo"))
    trv = _safe_float(ui.get("trv_ms"))
    pa_diam = _safe_float(ui.get("pa_diam_mm"))
    rv_lv_ratio = _safe_float(ui.get("rv_lv_ratio"))
    septal_flattening = bool(ui.get("septal_flattening")) if ui.get("septal_flattening") is not None else None
    af = bool(ui.get("atrial_fib")) if ui.get("atrial_fib") is not None else None

    # IVC congestion proxy – categorical collapse yes/no
    ivc_diam = _safe_float(ui.get("ivc_diam_mm"))
    ivc_collapse = ui.get("ivc_collapse")  # "ja"/"nein"/None
    ivc_collapse_yes = True if (isinstance(ivc_collapse, str) and ivc_collapse.lower().startswith("ja")) else False if (isinstance(ivc_collapse, str) and ivc_collapse.lower().startswith("nein")) else None

    congestion_likely = False
    # Practical congestion heuristics:
    # - Elevated RAP supports congestion
    # - Absent IVC collapse (categorical "nein") is treated as a sign of venous congestion
    if rap is not None and rap >= 12:
        congestion_likely = True
    if ivc_collapse_yes is False:
        congestion_likely = True
    if ivc_diam is not None and ivc_diam >= 21 and ivc_collapse_yes is False:
        congestion_likely = True

    # ---- Step oximetry ----
    sat_svc = _safe_float(ui.get("sat_svc"))
    sat_ivc = _safe_float(ui.get("sat_ivc"))
    sat_ra = _safe_float(ui.get("sat_ra"))
    sat_rv = _safe_float(ui.get("sat_rv"))
    sat_pa = _safe_float(ui.get("sat_pa"))
    sat_ao = _safe_float(ui.get("sat_ao"))
    stepup = detect_step_up(sat_svc, sat_ivc, sat_ra, sat_rv, sat_pa, sat_ao)

    # ---- Curve morphology flags ----
    wedge_v_wave = bool(ui.get("wedge_v_wave"))
    wedge_a_wave = bool(ui.get("wedge_a_wave"))
    rap_a_wave = bool(ui.get("rap_a_wave"))
    rap_v_wave = bool(ui.get("rap_v_wave"))
    rv_pseudo_dip = bool(ui.get("rv_pseudo_dip"))
    rv_dip_plateau = bool(ui.get("rv_dip_plateau"))

    # ---- S'/RAAI ----
    s_prime = _safe_float(ui.get("s_prime_cm_s"))
    ra_esa_cm2 = _safe_float(ui.get("ra_esa_cm2"))
    raai = None
    sprime_raai = None
    if ra_esa_cm2 is not None and bsa is not None and bsa > 0:
        raai = ra_esa_cm2 / bsa
    if s_prime is not None and raai is not None and raai > 0:
        sprime_raai = s_prime / raai

    sprime_raai_low = None
    if sprime_raai is not None:
        sprime_raai_low = sprime_raai < SPRIME_RAAI_CUTOFF

    # ---- TAPSE/sPAP ----
    tapse = _safe_float(ui.get("tapse_mm"))
    tapse_spap = None
    tapse_spap_risk = None       # ESC/ERS 2022 – 3-Strata Einordnung
    tapse_spap_reduced = None
    if tapse is not None and pasp_echo is not None and pasp_echo > 0:
        tapse_spap = tapse / pasp_echo
        if tapse_spap > TAPSE_SPAP_LOW_RISK:
            tapse_spap_risk = "niedrig"
            tapse_spap_reduced = False
        elif tapse_spap >= TAPSE_SPAP_HIGH_RISK:
            tapse_spap_risk = "intermediär"
            tapse_spap_reduced = True
        else:
            tapse_spap_risk = "hoch"
            tapse_spap_reduced = True


    # ---- Labs ----

    hb = _safe_float(ui.get("hb_g_dl"))
    anemia = _infer_anemia(sex, hb)

    # BNP / NT-proBNP
    bnp_kind = ui.get("bnp_kind") or None
    bnp_val = _safe_float(ui.get("bnp_value"))
    bnp_pg_ml = None
    ntprobnp_pg_ml = None
    if bnp_val is not None:
        if isinstance(bnp_kind, str) and "NT" in bnp_kind.upper():
            ntprobnp_pg_ml = bnp_val
        else:
            bnp_pg_ml = bnp_val

    # ---- HFpEF probability (H2FPEF) ----
    hfpef_res = calc_h2fpef_probability(
        age=age,
        bmi=bmi,
        ee=ee_ratio,
        pasp=pasp_echo,
        af=af,
    )

    hemo_cat = _hemo_category(mpap, pawp, pvr)
    # ---- Heart rate, stroke volume, pulsatile hemodynamics (PAC/RC-time) ----
    hr = _safe_float(ui.get("hr"))
    sv_rest_ml = None
    svi_rest_ml_m2 = None
    pp_pa_rest = None
    pac_rest_ml_per_mmhg = None
    rc_time_rest_s = None
    if co is not None and hr is not None and hr > 0:
        # CO [L/min], HR [1/min] -> SV [L/beat] -> [mL/beat]
        sv_rest_ml = (co / hr) * 1000.0
        if bsa is not None and bsa > 0:
            svi_rest_ml_m2 = sv_rest_ml / bsa
    if spap is not None and dpap is not None:
        pp_pa_rest = spap - dpap
    if sv_rest_ml is not None and pp_pa_rest is not None and pp_pa_rest > 0:
        pac_rest_ml_per_mmhg = sv_rest_ml / pp_pa_rest
        # RC-time: PVR [WU = mmHg·min/L] * PAC [mL/mmHg] -> seconds
        if pvr is not None and pvr >= 0:
            rc_time_rest_s = pvr * pac_rest_ml_per_mmhg * 0.06  # = PVR * PAC * (60/1000)



    # ---- Echo probability of PH (ESC/ERS 2022 diagnostic approach; TRV + additional signs) ----
    echo_signs_n = 0
    ra_esa_val = _safe_float(ui.get("ra_esa_cm2"))
    if rv_lv_ratio is not None and rv_lv_ratio > 1.0:
        echo_signs_n += 1
    if septal_flattening is True:
        echo_signs_n += 1
    if pa_diam is not None and pa_diam > 25:
        echo_signs_n += 1
    if ra_esa_val is not None and ra_esa_val > 18:
        echo_signs_n += 1
    if ivc_diam is not None and ivc_diam > 21 and ivc_collapse_yes is False:
        echo_signs_n += 1

    echo_probability = None
    if trv is not None and trv > 0:
        if trv > 3.4:
            echo_probability = "hoch"
        elif trv >= 2.9:
            echo_probability = "hoch" if echo_signs_n >= 1 else "intermediär"
        else:
            echo_probability = "intermediär" if echo_signs_n >= 1 else "niedrig"
    derived: Dict[str, Any] = {
        "bsa_m2": bsa,
        "bmi": bmi,
        "mpap": mpap,
        "mpap_calc": mpap_calc,
        "tpg": tpg,
        "dpg": dpg,
        "co": co,
        "ci": ci,
        "pvr": pvr,
        "pvr_calc": pvr_calc,
        "pvri": pvri,
        "hemo_category": hemo_cat,
        "exercise_done": exercise_done,
        "mpap_peak": mpap_peak,
        "co_peak": co_peak,
        "ci_peak": ci_peak,
        "mpap_co_slope": mpap_co_slope,
        "pawp_co_slope": pawp_co_slope,
        "exercise_pattern": exercise_pattern,
        "delta_spap": delta_spap,
        "adaptation_type": adaptation_type,
        "volume_challenge_done": volume_done,
        "pawp_delta": pawp_delta,
        "mpap_delta": mpap_delta,
        "vaso_test_done": vaso_done,
        "vaso_agent": vaso_agent,
        "vaso_responder": vaso_responder,
        "vaso_mpap_pre": vaso_mpap_pre,
        "vaso_mpap_post": vaso_mpap_post,
        "vaso_co_pre": vaso_co_pre,
        "vaso_co_post": vaso_co_post,
        "congestion_likely": congestion_likely,
        "ivc_collapse_yes": ivc_collapse_yes,
        "step_up_present": stepup.present,
        "step_up_from_to": stepup.from_to,
        "step_up_location": stepup.location,
        "step_up_delta": stepup.delta,
        "step_up_sentence": stepup.sentence,
        "v_wave": wedge_v_wave,
        "a_wave": wedge_a_wave,
        "rap_a_wave_flag": rap_a_wave,
        "rap_v_wave_flag": rap_v_wave,
        "rv_pseudo_dip_flag": rv_pseudo_dip,
        "rv_dip_plateau_flag": rv_dip_plateau,
                "trv_ms": trv,
        "pa_diam_mm": pa_diam,
        "rv_lv_ratio": rv_lv_ratio,
        "septal_flattening": septal_flattening,
        "echo_signs_n": echo_signs_n,
        "echo_probability": echo_probability,
        # Echo-Add-ons
        "s_prime_raai": sprime_raai,
        "sprime_raai": sprime_raai,  # Alias für Regelwerk
        "s_prime_raai_cutoff": SPRIME_RAAI_CUTOFF,
        "s_prime_raai_low": sprime_raai_low,
        "raai": raai,
        "raai_cm2_m2": raai,
        "tapse_spap": tapse_spap,        "tapse_spap_risk": tapse_spap_risk,
        "tapse_spap_reduced": tapse_spap_reduced,
        "anemia": anemia,
        "hfpef_percent": hfpef_res.percent,
        "hfpef_category": hfpef_res.category,
    }

    
    # ---- Derived aliases (explicit naming & compatibility for templates) ----
    # Keep the original keys (mpap, pvr, ci, ...) for the rule engine,
    # but also provide explicit *_rest / *_peak names for clarity in reports.
    derived.update({
        # Rest aliases
        "mpap_rest": mpap,
        "pawp_rest": pawp,
        "rap_rest": rap,
        "co_rest": co,
        "ci_rest": ci,
        "hr_rest": hr,
        "sv_rest_ml": sv_rest_ml,
        "svi_rest_ml_m2": svi_rest_ml_m2,
        "pp_pa_rest": pp_pa_rest,
        "pac_rest_ml_per_mmhg": pac_rest_ml_per_mmhg,
        "rc_time_rest_s": rc_time_rest_s,
        "pvr_rest": pvr,
        "tpg_rest": tpg,
        "dpg_rest": dpg,

        # Exercise aliases
        "delta_spap_peak_rest": delta_spap,
        "peak_ci": ci_peak,

        # Provocation aliases (used by rhk_textdb templates)
        "vol_challenge_delta_pawp": pawp_delta,
        "vol_challenge_delta_mpap": mpap_delta,
        "vasoreactivity_done": vaso_done,
    })

    # ---- Lungenfunktion: Ableitungen ----
    fev1 = _safe_float(ui.get("fev1_l"))
    fvc = _safe_float(ui.get("fvc_l"))
    tiff = None
    if fev1 is not None and fvc is not None and fvc > 0:
        tiff = fev1 / fvc
    derived["tiffeneau"] = tiff
    derived["tiffeneau_low"] = (tiff is not None and tiff < 0.70)

    # ---- Therapie-/Medikations-Flags (für Plausibilität/Logik) ----
    anticoag_status = str(ui.get("anticoag_status") or "").strip().lower()
    derived["anticoag_on"] = (anticoag_status == "ja")

    antifib_status = str(ui.get("antifibrotic_status") or "").strip().lower()
    derived["antifibrotic_on"] = (antifib_status == "ja")

    # Richer text for provocation placeholders (used in some K-packages)
    pawp_pre_v = _safe_float(ui.get("pawp_pre"))
    pawp_post_v = _safe_float(ui.get("pawp_post"))
    if pawp_pre_v is not None and pawp_post_v is not None:
        derived["vol_challenge_pawp_pre"] = pawp_pre_v
        derived["vol_challenge_pawp_post"] = pawp_post_v
        derived["vol_challenge_resp"] = f"PAWP pre {_fmt(pawp_pre_v,0)} → post {_fmt(pawp_post_v,0)} mmHg"
    else:
        derived["vol_challenge_resp"] = ""

    agent = (ui.get("vaso_agent") or "").strip()
    vaso_resp = (ui.get("vaso_response_desc") or "").strip()
    if agent or vaso_resp:
        derived["vasoreactivity_resp"] = "; ".join([x for x in [agent, vaso_resp] if x])
    else:
        derived["vasoreactivity_resp"] = ""
# ---- Scores ----
    who_fc = ui.get("who_fc") or None
    sixmwd = _safe_float(ui.get("six_mwd_m"))
    esc4 = calc_esc_ers_4_strata(who_fc, sixmwd, bnp_pg_ml, ntprobnp_pg_ml)
    esc3 = calc_esc_ers_3_strata(who_fc, sixmwd, bnp_pg_ml, ntprobnp_pg_ml)
    reveal_lite2 = calc_reveal_lite2(ui)
    esc_comp = calc_esc_ers_comprehensive_3_strata(ui, derived)
    cpet = calc_cpet_scores(ui)

    scores: Dict[str, Any] = {
        "esc_ers_4s": esc4,
        "esc_ers_3s": esc3,
        "esc_ers_comprehensive": esc_comp.category if esc_comp else None,
        "esc_ers_comprehensive_mean": round(esc_comp.mean_grade, 2) if (esc_comp and esc_comp.mean_grade is not None) else None,
        "esc_ers_comprehensive_n": esc_comp.n_params if esc_comp else None,
        "esc_ers_comprehensive_grades": esc_comp.grades if esc_comp else None,
        "esc_ers_comprehensive_missing": esc_comp.missing if esc_comp else None,
        "reveal_lite2": reveal_lite2.category if reveal_lite2 else None,
        "reveal_lite2_points": reveal_lite2.points if reveal_lite2 else None,
            "reveal_lite2_missing": reveal_lite2.missing if reveal_lite2 else None,
        "cpet_esc_ers_3s": cpet.esc_ers_3_strata if cpet else None,
        "cpet_score_4s": cpet.cpet_score_4_strata if cpet else None,
        "cpet_score_mean": round(cpet.mean_grade, 2) if (cpet and cpet.mean_grade is not None) else None,
        "cpet_effort_ok": cpet.effort_ok if cpet else None,
        "cpet_notes": cpet.notes if cpet else None,
        "hfpef": hfpef_res.category if hfpef_res else None,
        "hfpef_prob": round(hfpef_res.percent, 1) if (hfpef_res and hfpef_res.percent is not None) else None,
    }

    
    # ---- Convenience risk category (for follow-up phrasing in templates) ----
    # We normalize to: "low" | "intermediate" | "high" (or None).
    risk_category: Optional[str] = None

    # 1) REVEAL Lite 2 (German labels in this app)
    rl2 = scores.get("reveal_lite2")
    if isinstance(rl2, str) and rl2 and rl2 != "nicht berechenbar":
        _l = rl2.strip().lower()
        if _l.startswith("hoch") or _l == "high":
            risk_category = "high"
        elif _l.startswith("inter"):
            risk_category = "intermediate"
        elif _l.startswith("nied") or _l == "low":
            risk_category = "low"

    # 2) ESC/ERS 3-strata
    if risk_category is None:
        esc3s = scores.get("esc_ers_3s")
        if isinstance(esc3s, str) and esc3s in ("low", "intermediate", "high"):
            risk_category = esc3s

    # 3) CPET (falls vorhanden) als Ergänzung / Fallback
    if risk_category is None:
        cpet3 = scores.get("cpet_esc_ers_3s")
        if isinstance(cpet3, str) and cpet3 in ("low", "intermediate", "high"):
            risk_category = cpet3

    derived["risk_category"] = risk_category
# ---- Env for rules ----
    env: Dict[str, Any] = {}
    env.update(ui)
    env.update(derived)
    env.update(scores)

    # kurze Alias-Keys für Regelwerk-Kompatibilität (mpap/pvr/etc.)
    # Hinweis: Das Regelwerk nutzt historisch die Kurzkeys mpap/pvr; daher hier bewusst beides.
    env["mpap"] = mpap
    env["pvr"] = pvr
    env["co"] = co
    env["ci"] = ci

    # convenience booleans for rules
    env["has_ph"] = (mpap is not None and mpap > 20)
    env["precap"] = (hemo_cat == "precap")
    env["ipcph"] = (hemo_cat == "ipcph")
    env["cpcph"] = (hemo_cat == "cpcph")

    # PH-guideline aligned PVR threshold (precap/cpc uses PVR>2)
    env["pvr_gt2"] = (pvr is not None and pvr > 2)
    env["pawp_gt15"] = (pawp is not None and pawp > 15)
    env["lvef_ge50"] = (lvef is not None and lvef >= 50)

    # apply rules (mit Trace für Debug/Regression-Tests)
    decision, rule_trace = apply_rule_engine_trace(env, rules)

    # missing fields required
    missing: List[str] = []
    for fld in decision.require_fields:
        v = env.get(fld)
        if v is None or v == "" or v is False:
            missing.append(fld)
    decision.missing_fields = missing


    # Plausibilitätschecks (blockieren nicht)
    warnings = collect_plausibility_warnings(ui, derived)
    derived["warnings_count"] = len(warnings)
    env["warnings_count"] = len(warnings)

    # Debug payload: Rule-Trace + Warnungen
    debug_payload = {
        "warnings": warnings,
        "rule_trace": asdict(rule_trace),
    }


    # Ätiologie-Helfer (mehrere Ursachen können parallel bestehen)
    try:
        ph_etiology = infer_ph_etiology(env, decision)
    except Exception:
        ph_etiology = {}
    derived["ph_etiology"] = ph_etiology
    env["ph_etiology"] = ph_etiology

    # P-Module Policy: Priorisierung + nicht anwählbar
    derived["p_module_policy"] = compute_p_module_policy(ui, derived, decision)
    env["p_module_policy"] = derived["p_module_policy"]
    # Expose key etiology signals to the rule engine (top-level only; SafeExpr has no dict subscripts)
    _pol = derived.get("p_module_policy") or {}
    env["leading_group"] = _pol.get("leading_group")
    env["clear_leader"] = _pol.get("clear_leader")
    _gs = _pol.get("group_scores") or {}
    env["g1_score"] = _gs.get(1)
    env["g2_score"] = _gs.get(2)
    env["g3_score"] = _gs.get(3)
    env["g4_score"] = _gs.get(4)


    # infer leading cause/action if rulebook didn't set them
    if not decision.leading_cause or not decision.leading_action:
        lc, la = infer_leading_conclusion(env, decision)
        decision.leading_cause = decision.leading_cause or lc
        decision.leading_action = decision.leading_action or la

    case: Dict[str, Any] = {
        "ui": ui,
        "derived": derived,
        "scores": scores,
        "decision": asdict(decision),
        "hfpef": asdict(hfpef_res),
        "env": env,
        "warnings": warnings,
        "debug": debug_payload,
    }
    return case


# =============================================================================
# Leading cause/action inference (fallback)
# =============================================================================

def infer_leading_conclusion(env: Dict[str, Any], decision: Decision) -> Tuple[str, str]:
    """
    Produces a short "führende ..." cause and a matching main action for the concluding sentence.
    """
    # Shunt
    if env.get("step_up_present"):
        return ("kongenitalen Links-Rechts-Shunt", "eine gezielte Abklärung des Shunts (Echokardiographie inkl. Kontrast/TEE und ggf. kardiale Bildgebung)")

    # CTEPH/CTEPD
    if env.get("vq_defect") or env.get("ct_embolie") or env.get("ct_mosaic"):
        if env.get("precap") or env.get("has_ph"):
            return ("chronisch thromboembolischen Genese (CTEPD/CTEPH, Gruppe 4)", "die Vorstellung im CTEPH-/PH-Board und die weitere spezifische Abklärung (V/Q, CT-/Angio-Review, ggf. Pulmonalisangiographie)")

    # Group 3 (ILD/COPD)
    if env.get("ct_ild") or env.get("ct_emphysema") or env.get("lufu_obstructive") or env.get("lufu_restrictive") or env.get("lufu_diffusion"):
        if env.get("precap") or env.get("has_ph"):
            return ("Lungenerkrankung/Hypoxie (Gruppe 3)", "die konsequente pneumologische Therapie inkl. Optimierung der Oxygenierung und ILD-/COPD-spezifischer Mitbehandlung")

    # HFpEF / left-heart
    if env.get("pawp_gt15") or (env.get("hfpef_category") in ("possible", "likely")) or env.get("la_enlarged"):
        if env.get("lvef_ge50"):
            return ("linkskardialen Ursache im Sinne einer diastolischen Funktionsstörung/HFpEF (Gruppe 2)", "die kardiologische Therapieoptimierung (Volumenmanagement, Rhythmus-/RR-Kontrolle und HFpEF-spezifische Therapie nach Leitlinie)")
        return ("linkskardialen Ursache (Gruppe 2)", "die kardiologische Therapieoptimierung und Behandlung der linksventrikulären Dysfunktion")

    # Default: PAH / pulmonary vascular
    if env.get("precap"):
        return ("pulmonalvaskulären Ursache (PAH/Gruppe 1, DD andere präkapilläre Ursachen)", "die weiterführende Abklärung präkapillärer Ursachen (u.a. Autoimmunität, HIV/Leber, ggf. Genetik) und die PH-spezifische Therapie nach Risikostratifizierung")

    return ("unklaren Genese", "eine strukturierte Komplettierung der Diagnostik und interdisziplinäre Einordnung")


# =============================================================================
# Dashboard HTML
# =============================================================================


def infer_ph_etiology(env: Dict[str, Any], decision: Optional[Decision] = None) -> Dict[str, Any]:
    """Leitet mögliche PH-Ätiologien (Gruppen) aus Befund-/Kontextdaten ab.

    Hintergrund:
    - In der Praxis können **mehrere Ursachen gleichzeitig** vorliegen (z.B. Linksherz + Lunge + CTEPH).
    - Eine *führende* Zuordnung sollte nur erfolgen, wenn die Befundlage dies klar nahelegt.

    Rückgabe (dict):
    - candidates: Liste möglicher Gruppen inkl. Score & Evidenzen
    - leading_group / clear_leader
    - doc_conclusion: nuancierte Formulierung für Arztbericht
    - patient_cause_line: kurze, patientenfreundliche Einordnung (ohne Gruppennummern)
    """

    def _as_list(x: Any) -> List[str]:
        if x is None:
            return []
        if isinstance(x, list):
            return [str(i) for i in x if i not in (None, "")]
        if isinstance(x, tuple):
            return [str(i) for i in x if i not in (None, "")]
        if isinstance(x, str):
            s = x.strip()
            return [s] if s else []
        return [str(x)]

    def _has(items: List[str], token: str) -> bool:
        t = token.strip().lower()
        return any(t in str(i).lower() for i in items)

    # Normalisierte Listen aus Multi-Select Feldern
    viro_items = _as_list(env.get("virology_items"))
    immun_items = _as_list(env.get("immunology_items"))
    mut_items = _as_list(env.get("mutation_items"))

    # Basis
    pawp = _safe_float(env.get("pawp_rest"))
    pawp_gt15 = bool(env.get("pawp_gt15")) if env.get("pawp_gt15") is not None else (pawp is not None and pawp > 15)
    hemo_cat = str(env.get("hemo_category") or "")
    has_ph = bool(env.get("has_ph"))

    # Hinweise / Evidenzen je Gruppe (Scoring heuristisch)
    candidates: List[Dict[str, Any]] = []

    def _add_candidate(group: int, score: int, label_doc: str, label_patient: str, evidence: List[str]) -> None:
        if score <= 0:
            return
        candidates.append({
            "group": group,
            "score": int(score),
            "label_doc": label_doc,
            "label_patient": label_patient,
            "evidence": evidence,
        })

    # ---------- Gruppe 4 (CTEPD/CTEPH) ----------
    g4_evi: List[str] = []
    g4 = 0
    if bool(env.get("vq_defect")):
        g4 += 3
        g4_evi.append("V/Q: segmentale Perfusionsdefekte")
    if bool(env.get("ct_embolie")):
        g4 += 2
        g4_evi.append("CT: Hinweise auf (chronische) Embolie/Thromben")
    if bool(env.get("ct_mosaic")):
        g4 += 1
        g4_evi.append("CT: Mosaikperfusion")
    ph_known_dx = str(env.get("ph_known_dx") or "")
    if "CTEPH" in ph_known_dx or "Gruppe 4" in ph_known_dx or "CTEPD" in ph_known_dx:
        g4 += 2
        g4_evi.append("PH bekannt: CTEPH/CTEPD")
    anticoag_ind = str(env.get("anticoag_indication") or "")
    if "CTEPH" in anticoag_ind or "CTEPD" in anticoag_ind:
        g4 += 1
        g4_evi.append("Antikoagulation: Indikation CTEPH/CTEPD")

    # Hämodynamischer "Fit": CTEPH ist typischerweise präkapillär, kann aber mit Ko-Morbiditäten koexistieren
    if pawp_gt15 and g4 > 0:
        g4 = max(1, g4 - 1)
        g4_evi.append("Hinweis: PAWP > 15 mmHg – Ko-Mechanismen möglich")

    _add_candidate(
        4,
        g4,
        "chronisch thromboembolischen Genese (CTEPD/CTEPH, Gruppe 4)",
        "Hinweise auf ältere Blutgerinnsel/Embolien in den Lungengefäßen (chronische Thromboembolie)",
        g4_evi,
    )

    # ---------- Gruppe 2 (Linksherz) ----------
    g2_evi: List[str] = []
    g2 = 0
    if pawp_gt15:
        g2 += 3
        g2_evi.append("PAWP > 15 mmHg (postkapilläre Komponente)")
    hfpef_cat = str(env.get("hfpef_category") or "")
    if hfpef_cat in ("possible", "likely"):
        g2 += 1 if hfpef_cat == "possible" else 2
        g2_evi.append(f"H2FPEF: {hfpef_cat}")
    if "Gruppe 2" in ph_known_dx:
        g2 += 2
        g2_evi.append("PH bekannt: Gruppe 2")
    if bool(env.get("la_enlarged")):
        g2 += 1
        g2_evi.append("Echo: LA vergrößert")
    lvef = _safe_float(env.get("lvef"))
    if lvef is not None and lvef < 50:
        g2 += 1
        g2_evi.append("Echo: LVEF reduziert")

    # Hämodynamischer Fit: reine Linksherz-PH ist weniger wahrscheinlich bei klar präkapillärem Muster
    if (not pawp_gt15) and g2 > 0 and ("precap" in hemo_cat):
        g2 = max(1, g2 - 1)
        g2_evi.append("Hinweis: präkapilläres Muster – Linksherz-Komponente als DD")

    # HFpEF-spezifische Formulierung wenn möglich
    g2_label = "linksherzbedingten Genese (Gruppe 2)"
    if (decision and decision.bundle and "HFpEF" in decision.bundle) or hfpef_cat == "likely":
        g2_label = "linksherzbedingten Genese im Sinne einer HFpEF/DD (Gruppe 2)"

    _add_candidate(
        2,
        g2,
        g2_label,
        "Hinweise auf einen Rückstau durch das linke Herz (Linksherz-Beteiligung)",
        g2_evi,
    )

    # ---------- Gruppe 3 (Lunge/Hypoxie) ----------
    g3_evi: List[str] = []
    g3 = 0
    if bool(env.get("ct_ild")):
        g3 += 2
        g3_evi.append("CT: interstitielle Lungenerkrankung (ILD)")
    if bool(env.get("ct_emphysema")):
        g3 += 2
        g3_evi.append("CT: Emphysem")
    if bool(env.get("ltot")):
        g3 += 1
        g3_evi.append("Langzeit-Sauerstofftherapie")

    # Lufu grob
    if bool(env.get("tiffeneau_low")):
        g3 += 1
        g3_evi.append("Lufu: Obstruktion (Tiffeneau erniedrigt)")
    dlco = _safe_float(env.get("dlco_percent_pred"))
    if dlco is not None and dlco < 60:
        g3 += 1
        g3_evi.append("Lufu: DLCO vermindert")
    if "Gruppe 3" in ph_known_dx:
        g3 += 2
        g3_evi.append("PH bekannt: Gruppe 3")

    # Hämodynamischer Fit: Gruppe 3 meist präkapillär, aber Ko-Mechanismen möglich
    if pawp_gt15 and g3 > 0:
        g3 = max(1, g3 - 1)
        g3_evi.append("Hinweis: PAWP > 15 mmHg – Ko-Mechanismen möglich")

    _add_candidate(
        3,
        g3,
        "lungenerkrankungsassoziierten Genese (Gruppe 3)",
        "Hinweise auf eine relevante Lungenerkrankung (die den Druck in den Lungengefäßen mit beeinflussen kann)",
        g3_evi,
    )

    # ---------- Gruppe 1 (PAH / pulmonalvaskulär; inkl. CHD/Genetik/CTD/HIV) ----------
    g1_evi: List[str] = []
    g1 = 0
    g1_bits: List[str] = []

    # Angeborener Herzfehler / Shunt
    if bool(env.get("step_up_present")):
        g1 += 3
        g1_bits.append("Shunt/Step-up")
        g1_evi.append("Oximetrie: Step-up (Shuntzeichen)")
    if bool(env.get("chd_pos")):
        g1 += 2
        g1_bits.append("angeborener Herzfehler")
        chd_type = str(env.get("chd_type") or "").strip()
        g1_evi.append("Anamnese: angeborener Herzfehler/Shunt")
        if chd_type:
            g1_evi.append(f"CHD: {chd_type}")

    # Genetik / Mutation
    if bool(env.get("mutation_pos")):
        g1 += 2
        g1_bits.append("Genetik/Mutation")
        if mut_items:
            g1_evi.append("Genetik: " + ", ".join(mut_items[:4]) + ("…" if len(mut_items) > 4 else ""))
        else:
            g1_evi.append("Genetik/Mutation: positiv/angegeben")

    # Virologie/Infektiologie (v.a. HIV)
    if bool(env.get("virology_pos")):
        viro_desc = str(env.get("virology_desc") or "")
        if _has(viro_items, "HIV") or _has([viro_desc], "HIV"):
            g1 += 2
            g1_bits.append("HIV")
            g1_evi.append("Infektiologie: HIV")
        elif viro_items:
            g1 += 1
            g1_bits.append("Infektiologie")
            g1_evi.append("Infektiologie: " + ", ".join(viro_items[:4]) + ("…" if len(viro_items) > 4 else ""))
        elif viro_desc.strip():
            g1 += 1
            g1_bits.append("Infektiologie")
            g1_evi.append("Infektiologie: " + viro_desc.strip())
        else:
            g1 += 1
            g1_bits.append("Infektiologie")
            g1_evi.append("Infektiologie: positiv/unklar")

    # Immunologie/Autoimmun (CTD)
    if bool(env.get("immunology_pos")):
        immun_desc = str(env.get("immunology_desc") or "")
        ctd_tokens = [
            "Sklerose", "Sklerodermie", "SLE", "Lupus", "MCTD", "Sjögren", "Arthritis", "Myositis", "Vaskul",
        ]
        ctd_hit = any(_has(immun_items, t) for t in ctd_tokens) or any(_has([immun_desc], t) for t in ctd_tokens)
        if ctd_hit:
            g1 += 2
            g1_bits.append("Autoimmun/CTD")
            if immun_items:
                g1_evi.append("Autoimmun/CTD: " + ", ".join(immun_items[:4]) + ("…" if len(immun_items) > 4 else ""))
            else:
                g1_evi.append("Autoimmun/CTD: positiv/angegeben")
        elif immun_items:
            g1 += 1
            g1_bits.append("Immunologie")
            g1_evi.append("Immunologie: " + ", ".join(immun_items[:4]) + ("…" if len(immun_items) > 4 else ""))
        elif immun_desc.strip():
            g1 += 1
            g1_bits.append("Immunologie")
            g1_evi.append("Immunologie: " + immun_desc.strip())
        else:
            g1 += 1
            g1_bits.append("Immunologie")
            g1_evi.append("Immunologie: positiv/unklar")

    if "Gruppe 1" in ph_known_dx or "PAH" in ph_known_dx:
        g1 += 2
        g1_evi.append("PH bekannt: PAH/Gruppe 1")

    # Hämodynamischer Fit: PAH typischerweise präkapillär; bei klar postkapillär abwerten
    if pawp_gt15 and g1 > 0 and ("ipcph" in hemo_cat):
        g1 = max(1, g1 - 1)
        g1_evi.append("Hinweis: iPcPH-Muster – PAH als DD, Ko-Morbiditäten möglich")

    if g1 > 0:
        label_doc = "pulmonalvaskulären Ursache (PAH, Gruppe 1)"
        if g1_bits:
            # Unique, order-preserving
            uniq = []
            for b in g1_bits:
                if b not in uniq:
                    uniq.append(b)
            label_doc += " – DD/assoziiert mit " + ", ".join(uniq)
        _add_candidate(
            1,
            g1,
            label_doc,
            "Hinweise auf eine (seltenere) Erkrankung der Lungengefäße (PAH) bzw. entsprechende Risikofaktoren",
            g1_evi,
        )

    # Sortierung & Entscheidung "führend?"
    candidates_sorted = sorted(candidates, key=lambda d: d.get("score", 0), reverse=True)
    leading_group: Optional[int] = candidates_sorted[0]["group"] if candidates_sorted else None
    clear_leader = False
    if candidates_sorted:
        if len(candidates_sorted) == 1:
            clear_leader = True
        else:
            top = candidates_sorted[0]["score"]
            second = candidates_sorted[1]["score"]
            # klar führend nur bei deutlichem Abstand
            clear_leader = bool(top >= second + 2 and top >= 3)

    # Baue Textbausteine
    doc_labels = [c["label_doc"] for c in candidates_sorted]
    patient_labels = [c["label_patient"] for c in candidates_sorted]

    def _actions_for(groups: List[int]) -> List[str]:
        parts: List[str] = []
        if 4 in groups:
            parts.append("Vorstellung im CTEPH-/PH-Board und spezifische Abklärung (V/Q, CT-/Angio-Review, ggf. Pulmonalisangiographie).")
        if 2 in groups:
            parts.append("Kardiologische Mitbeurteilung und Therapieoptimierung der Linksherzerkrankung/HFpEF.")
        if 3 in groups:
            parts.append("Pneumologische Mitbeurteilung und Optimierung/Abklärung der Lungenerkrankung (inkl. Lufu/CT-Korrelation, O2-Bedarf).")
        if 1 in groups:
            parts.append("PH-Zentrum: komplette PAH-DD/Abklärung (Autoimmunität, HIV/Infektiologie, Genetik/angeborene Herzfehler) und Therapie nach Risikoprofil.")
        return parts

    groups = [c["group"] for c in candidates_sorted]
    action_parts = _actions_for(groups)

    if not candidates_sorted:
        doc_conclusion = (
            "In der Zusammenschau der Befunde bleibt die zugrunde liegende Ursache einer pulmonalen Druckerhöhung unklar. "
            "Eine interdisziplinäre Einordnung (PH-Board) und ggf. ergänzende Diagnostik werden empfohlen."
        )
        patient_cause_line = (
            "Die Ursache ist anhand der vorliegenden Angaben nicht sicher. "
            "Oft sind ergänzende Untersuchungen nötig, um die wichtigsten Auslöser zu finden."
        )
    else:
        if clear_leader and leading_group is not None:
            lead_label = candidates_sorted[0]["label_doc"]
            other = [c["label_doc"] for c in candidates_sorted[1:]]
            if other:
                doc_conclusion = (
                    f"In der Zusammenschau der Befunde sprechen die Befunde am ehesten für eine **führende** {lead_label}. "
                    f"**Zusätzlich** bestehen Hinweise auf {', '.join(other)}. "
                    "Mehrere Mechanismen können gleichzeitig zur PH beitragen."
                )
            else:
                doc_conclusion = f"In der Zusammenschau der Befunde sprechen die Befunde am ehesten für eine führende {lead_label}."
        else:
            doc_conclusion = (
                "In der Zusammenschau der Befunde ergeben sich Hinweise auf **mehrere mögliche Ursachen/Mechanismen** "
                f"({', '.join(doc_labels)}). Eine eindeutige führende Zuordnung ist anhand der vorliegenden Angaben nicht sicher."
            )

        # Empfehlung anhängen (kompakt)
        if action_parts:
            doc_conclusion += " Empfohlen: " + " ".join(action_parts)

        # Patiententext kurz
        if clear_leader and patient_labels:
            lead_p = patient_labels[0]
            others_p = patient_labels[1:]
            if others_p:
                patient_cause_line = (
                    f"Am ehesten passen die Befunde zu: {lead_p}. "
                    f"Zusätzlich gibt es Hinweise auf: {', '.join(others_p)}."
                )
            else:
                patient_cause_line = f"Am ehesten passen die Befunde zu: {lead_p}."
        else:
            patient_cause_line = (
                "Es gibt Hinweise auf mehrere mögliche Ursachen, die gleichzeitig eine Rolle spielen können: "
                f"{'; '.join(patient_labels)}. "
                "Welche Ursache überwiegt, lässt sich aus den Angaben nicht sicher sagen."
            )

    return {
        "candidates": candidates_sorted,
        "leading_group": leading_group,
        "clear_leader": clear_leader,
        "doc_conclusion": doc_conclusion,
        "patient_cause_line": patient_cause_line,
    }

def build_dashboard_html(case: Optional[Dict[str, Any]]) -> str:
    if not case:
        return f"""
        <div class="card">
          <div class="card-title">{APP_TITLE}</div>
          <div class="muted">Noch kein Befund generiert. Bitte „Beispiel laden“ oder Daten eingeben und „Befund erstellen/aktualisieren“ klicken.</div>
        </div>
        """

    d = case["decision"]
    der = case["derived"]
    sc = case["scores"]

    def badge(text: str, cls: str = "badge", title: Optional[str] = None) -> str:
        tattr = ""
        if title:
            try:
                tattr = f' title="{html_escape(title)}"'
            except Exception:
                tattr = ""
        return f'<span class="{cls}"{tattr}>{text}</span>'

    risk_badges = []
    # REVEAL Lite 2 (wenn möglich prominent anzeigen)
    if sc.get("reveal_lite2"):
        cat = sc.get("reveal_lite2")
        pts = sc.get("reveal_lite2_points")
        if cat == "nicht berechenbar":
            missing = sc.get("reveal_lite2_missing") or []
            miss_txt = ", ".join(missing) if missing else "Parameter unvollständig"
            risk_badges.append(badge(f"REVEAL Lite 2: nicht berechenbar (fehlend: {miss_txt})", "badge badge-orange"))
        else:
            cat_de = {"low": "niedrig", "intermediate": "intermediär", "high": "hoch"}.get(str(cat), str(cat))
            pts_txt = f"{pts} Pkt." if pts is not None else "—"
            risk_badges.append(badge(f"REVEAL Lite 2: {pts_txt} ({cat_de})", "badge badge-purple"))
    if sc.get("esc_ers_4s"):
        risk_badges.append(badge(f"ESC/ERS 4-Strata: {sc['esc_ers_4s']}", "badge badge-blue"))
    if sc.get("esc_ers_3s"):
        risk_badges.append(badge(f"ESC/ERS 3-Strata: {sc['esc_ers_3s']}", "badge badge-blue"))
    if der.get("hfpef_percent") is not None and der.get("hfpef_category"):
        risk_badges.append(badge(f"HFpEF (H2FPEF): {der['hfpef_category']} ({_fmt(der['hfpef_percent'],0)}%)", "badge badge-purple"))

    if der.get("congestion_likely"):
        risk_badges.append(badge("Hinweis venöse Kongestion", "badge badge-orange"))

    # Plausibilitätswarnungen (nicht blockierend)
    warns = case.get("warnings") or []
    if warns:
        sev = {str(w.get('severity')) for w in warns if isinstance(w, dict)}
        cls = "badge badge-orange"
        if "error" in sev:
            cls = "badge badge-red"
        # Tooltip with full warning list
        w_msgs = []
        for w in warns:
            if isinstance(w, dict) and str(w.get("message") or "").strip():
                w_msgs.append(str(w.get("message")).strip())
        tooltip = "\n".join([f"- {m}" for m in w_msgs]) if w_msgs else None
        risk_badges.append(badge(f"Warnungen: {len(warns)}", cls, tooltip))

    if der.get("exercise_pattern"):
        risk_badges.append(badge(f"Belastungsmuster: {describe_exercise_pattern(der['exercise_pattern'])}", "badge badge-teal"))

    if der.get("adaptation_type"):
        ad = str(der.get("adaptation_type"))
        ad_de = "homeometrisch" if ad == "homeometric" else "heterometrisch" if ad == "heterometric" else ad
        d_spap = der.get("delta_spap")
        d_txt = f" (ΔsPAP {_fmt(d_spap,0)} mmHg)" if d_spap is not None else ""
        risk_badges.append(badge(f"Adaptionstyp: {ad_de}{d_txt}", "badge badge-teal"))

    # Echo-Prognosemarker
    if der.get("s_prime_raai_low") is True:
        risk_badges.append(badge("S'/RAAI erniedrigt", "badge badge-orange"))
    if der.get("tapse_spap_reduced") is True:
        risk_badges.append(badge("TAPSE/sPAP vermindert", "badge badge-orange"))

    if der.get("step_up_present"):
        risk_badges.append(badge("Shuntverdacht (Sättigungssprung)", "badge badge-red"))

    tags = d.get("tags") or []
    missing = d.get("missing_fields") or []
    warns_summary = '<span class="muted">keine</span>'
    try:
        if warns:
            msgs_all = [str(w.get("message") or "").strip() for w in warns if isinstance(w, dict) and str(w.get("message") or "").strip()]
            if msgs_all:
                # Show all warnings as a compact bullet list (copy/paste friendly)
                li = "".join([f"<li>{html_escape(m)}</li>" for m in msgs_all])
                warns_summary = f"<ul style='margin:0.25rem 0 0.25rem 1.25rem;padding:0'>{li}</ul>"
    except Exception:
        warns_summary = '<span class="muted">keine</span>'


    return f"""
    <div class="card">
      <div class="card-title">{APP_TITLE}</div>
      <div class="row">
        <div><b>Bundle:</b> {d.get('bundle','–')}</div>
        <div><b>Primäre Einordnung:</b> {d.get('primary_dx','–')}</div>
      </div>
      <div class="badges">{''.join(risk_badges) if risk_badges else '<span class="muted">Keine Scores verfügbar.</span>'}</div>
      <div class="row">
        <div><b>Tags:</b> {', '.join(tags) if tags else '<span class="muted">–</span>'}</div>
      </div>
      <div class="row">
        <div><b>Fehlende Angaben (für Regelwerk):</b> {', '.join(missing) if missing else '<span class="muted">keine</span>'}</div>
      </div>
      <div class="row">
        <div><b>Plausibilitätswarnungen:</b> {warns_summary}</div>
      </div>
    </div>
    """


# =============================================================================
# Render context for template blocks
# =============================================================================

def build_render_ctx(case: Dict[str, Any]) -> Dict[str, Any]:
    ui = case["ui"]
    der = case["derived"]
    env = case["env"]

    mpap = der.get("mpap")
    pawp = _safe_float(ui.get("pawp_rest"))
    rap = _safe_float(ui.get("rap_rest"))
    pvr = der.get("pvr")
    ci = der.get("ci")
    tpg = der.get("tpg")
    dpg = der.get("dpg")


    # prior RHK comparison / Verlauf (optional)
    trend_info = _compare_rhk_trend(ui, der)
    comparison_sentence = ""
    comparison_table_md = ""
    comparison_detail_doc = ""
    comparison_detail_patient_md = ""
    comparison_recommendation_doc = ""
    comparison_recommendation_patient = ""
    if trend_info.get("has_prev"):
        comparison_sentence = trend_info.get("sentence_doc") or ""
        comparison_table_md = trend_info.get("table_md") or ""
        comparison_detail_doc = trend_info.get("detail_doc") or ""
        comparison_detail_patient_md = trend_info.get("detail_patient") or ""
        comparison_recommendation_doc = trend_info.get("rec_doc") or ""
        comparison_recommendation_patient = trend_info.get("rec_patient") or ""

    # Step-up sentence
    step_up_sentence = der.get("step_up_sentence") or ""

    # V-wave short
    V_wave_short = "Prominente V-Welle in PAWP-Kurve." if der.get("v_wave") else "Keine prominente V-Welle in PAWP-Kurve."
    A_wave_short = "Prominente A-Welle in PAWP-Kurve." if der.get("a_wave") else "Keine prominente A-Welle in PAWP-Kurve."
    RA_A_wave_short = "Prominente A-Welle in RAP-Kurve." if der.get("rap_a_wave_flag") else "Keine prominente A-Welle in RAP-Kurve."
    RA_V_wave_short = "Prominente V-Welle in RAP-Kurve." if der.get("rap_v_wave_flag") else "Keine prominente V-Welle in RAP-Kurve."
    RV_pseudo_dip_short = "Pseudo-Dip in RV-Kurve." if der.get("rv_pseudo_dip_flag") else "Kein Pseudo-Dip in RV-Kurve."
    RV_dip_plateau_short = "Dip-Plateau in RV-Kurve." if der.get("rv_dip_plateau_flag") else "Kein Dip-Plateau in RV-Kurve."

    # Phrases used by rhk_textdb templates
    mpap_phrase = f"mPAP {str(_fmt(mpap,0)) } mmHg" if mpap is not None else "mPAP nicht angegeben"
    pawp_phrase = f"PAWP {str(_fmt(pawp,0)) } mmHg" if pawp is not None else "PAWP nicht angegeben"
    pvr_phrase = f"PVR {str(_fmt(pvr,1)) } WU" if pvr is not None else "PVR nicht angegeben"
    ci_phrase = f"CI {str(_fmt(ci,2)) } l/min/m²" if ci is not None else "CI nicht angegeben"

    hfpef_hint = ""
    if der.get("hfpef_category") in ("possible", "likely"):
        hfpef_hint = f"HFpEF-Wahrscheinlichkeit (H2FPEF) {der.get('hfpef_category')} (~{_fmt(der.get('hfpef_percent'),0)}%)."

    # Slopes hint only if exercise done
    slope_hint = ""
    if der.get("exercise_done") and der.get("mpap_co_slope") is not None and der.get("pawp_co_slope") is not None:
        slope_hint = f"mPAP/CO-Slope {str(_fmt(der.get('mpap_co_slope'),1)) } WU, PAWP/CO-Slope {str(_fmt(der.get('pawp_co_slope'),1)) } WU."

    tpg_hint = f"TPG {str(_fmt(tpg,0)) } mmHg" if tpg is not None else ""
    dpg_hint = f"DPG {str(_fmt(dpg,0)) } mmHg" if dpg is not None else ""

    pressure_resistance_short = ", ".join([x for x in [mpap_phrase, pawp_phrase, pvr_phrase, ci_phrase, tpg_hint, dpg_hint, slope_hint] if x])

    # Additional helper sentences for rhk_textdb templates (missing keys are filled with '' via SafeDict)
    # CO-Methode ist klinisch relevant; wenn nicht angegeben, neutral formulieren.
    co_method_desc = "Thermodilution oder Fick-Prinzip (nicht angegeben)"
    _cm = ui.get("co_method")
    co_method_raw = str(_cm or "").strip().lower()
    if co_method_raw in ("thermodilution", "thermo", "td") or str(_cm or "") == "Thermodilution":
        co_method_desc = "Thermodilution"
    elif co_method_raw in ("fick", "fick-prinzip") or str(_cm or "") == "Fick":
        co_method_desc = "Fick-Prinzip"

    cv_stauung_phrase = "Hinweise auf venöse Kongestion." if der.get("congestion_likely") else "Keine Hinweise auf venöse Kongestion."
    pv_stauung_phrase = "Hinweise auf pulmonalvenöse Stauung." if env.get("pawp_gt15") else "Keine Hinweise auf pulmonalvenöse Stauung."

    sbp = _safe_float(ui.get("bp_sys"))
    hr = _safe_float(ui.get("hr"))
    systemic_sentence = ""
    if sbp is not None or hr is not None:
        parts = []
        if sbp is not None:
            parts.append(f"RR {_fmt(sbp,0)} mmHg")
        if hr is not None:
            parts.append(f"HF {_fmt(hr,0)}/min")
        systemic_sentence = "Systemische Hämodynamik: " + ", ".join(parts) + "."

    oxygen_sentence = ""
    om = ui.get("oxygen_mode")
    if isinstance(om, str) and om:
        if om == "keine":
            oxygen_sentence = "Messung in Raumluft."
        elif om == "O2":
            flow = _safe_float(ui.get("oxygen_flow_l_min"))
            oxygen_sentence = "Messung unter Sauerstoffgabe" + (f" {_fmt(flow,1)} l/min" if flow is not None else "") + "."
        elif om == "LTOT":
            flow = _safe_float(ui.get("ltot_flow_l_min")) or _safe_float(ui.get("oxygen_flow_l_min"))
            oxygen_sentence = "Messung unter Langzeitsauerstoff" + (f" {_fmt(flow,1)} l/min" if flow is not None else "") + "."
        elif om == "NIV":
            oxygen_sentence = "Messung unter NIV."

    exam_type_desc = "RHK in Ruhe"
    _parts = []
    if der.get("exercise_done"):
        _parts.append("Belastung")
    if der.get("volume_challenge_done"):
        _parts.append("Volumenchallenge")
    if der.get("vasoreactivity_done"):
        _parts.append("Vasoreaktivitätstest")
    if _parts:
        exam_type_desc = "RHK in Ruhe + " + " + ".join(_parts)

    provocation_sentence = ""
    provocation_type_desc = ""
    provocation_result_sentence = ""
    if der.get("volume_challenge_done"):
        provocation_type_desc = "Volumenchallenge"
        delta = der.get("vol_challenge_delta_pawp")
        resp = der.get("vol_challenge_resp")
        if delta is not None:
            provocation_sentence = f"Nach Volumenchallenge ΔPAWP {_fmt(delta,0)} mmHg"
            if resp:
                provocation_sentence += f" ({resp})"
            provocation_sentence += "."
            provocation_result_sentence = provocation_sentence
    elif der.get("vasoreactivity_done"):
        provocation_type_desc = "Vasoreaktivitätstest"
        resp = der.get("vasoreactivity_resp") or ""
        provocation_sentence = f"Vasoreaktivitätstest: {resp}."
        provocation_result_sentence = provocation_sentence
    elif der.get("exercise_done"):
        provocation_type_desc = "Belastung"

    # Follow-up placeholders (used in P11)
    risk = der.get("risk_category")
    followup_timing_desc = "einem geeigneten Intervall"
    if risk == "high":
        followup_timing_desc = "4–12 Wochen"
    elif risk == "intermediate":
        followup_timing_desc = "3–6 Monaten"
    elif risk == "low":
        followup_timing_desc = "6–12 Monaten"

    invasive_followup_desc = "einem passenden Intervall"
    if risk == "high" and der.get("has_ph"):
        invasive_followup_desc = "3–6 Monaten"
    elif risk == "intermediate" and der.get("has_ph"):
        invasive_followup_desc = "6–12 Monaten"

    # Valve focus placeholder (used in P09)
    valve_focus_desc = "Klappenvitien"
    if der.get("v_wave"):
        valve_focus_desc = "Mitralinsuffizienz/linksatriale Druckspitzen"
    elif der.get("rap_v_wave_flag"):
        valve_focus_desc = "Trikuspidalinsuffizienz"
    elif env.get("pawp_gt15"):
        valve_focus_desc = "diastolischer Funktion und Mitralklappe"
    elif der.get("hemo_category") == "precap":
        valve_focus_desc = "Rechtsherz und Trikuspidalklappe"
    elif der.get("a_wave"):
        valve_focus_desc = "diastolischer Funktion"

    # Anemia placeholder (used in P13)
    anemia_context_desc = None
    if der.get("anemia"):
        at = (ui.get("anemia_type") or "").strip().lower()
        if at.startswith("mikro"):
            anemia_context_desc = "mikrozytär (z.B. Eisenmangel/chron. Blutverlust)"
        elif at.startswith("makro"):
            anemia_context_desc = "makrozytär (z.B. Vitamin-B12-/Folat-Mangel, Leber, Alkohol)"
        elif at.startswith("normo"):
            anemia_context_desc = "normozytär (z.B. Entzündung/chron. Erkrankung, Niere)"
        elif "hämol" in at:
            anemia_context_desc = "hämolytisch (Hinweis auf Hämolyse)"
        elif "blut" in at:
            anemia_context_desc = "akute Blutung/Blutverlust" 
        elif at:
            anemia_context_desc = f"Anämie ({at})"
        else:
            anemia_context_desc = "Anämie (Typ unklar)"
    exercise_pattern_desc = describe_exercise_pattern(der.get("exercise_pattern")) if der else ""
    exercise_protocol = (ui.get("exercise_protocol") or "").strip()
    exercise_peak_watts = _safe_float(ui.get("exercise_peak_watts"))
    exercise_protocol_sentence = ""
    if (ui.get("exercise_done") or (der.get("exercise_done") if der else False)) and (exercise_protocol or exercise_peak_watts is not None):
        if exercise_protocol and exercise_peak_watts is not None:
            exercise_protocol_sentence = f"In der Ergometrie nach {exercise_protocol} bis {fmt_int(exercise_peak_watts)} W."
        elif exercise_protocol:
            exercise_protocol_sentence = f"In der Ergometrie nach {exercise_protocol}."
        else:
            exercise_protocol_sentence = f"In der Ergometrie bis {fmt_int(exercise_peak_watts)} W."

    return {
        **env,
        "comparison_sentence": comparison_sentence,
        "comparison_trend": (trend_info.get("trend") if trend_info.get("has_prev") else ""),
        "comparison_table_md": comparison_table_md,
        "comparison_detail_doc": comparison_detail_doc,
        "comparison_detail_patient_md": comparison_detail_patient_md,
        "comparison_recommendation_doc": comparison_recommendation_doc,
        "comparison_recommendation_patient": comparison_recommendation_patient,
        "step_up_sentence": step_up_sentence,
        "step_up_from_to": der.get("step_up_from_to") or "",
        "V_wave_short": V_wave_short,
        "A_wave_short": A_wave_short,
        "RA_A_wave_short": RA_A_wave_short,
        "RA_V_wave_short": RA_V_wave_short,
        "RV_pseudo_dip_short": RV_pseudo_dip_short,
        "RV_dip_plateau_short": RV_dip_plateau_short,
        "mpap_phrase": mpap_phrase,
        "pawp_phrase": pawp_phrase,
        "pvr_phrase": pvr_phrase,
        "ci_phrase": ci_phrase,
        "pressure_resistance_short": pressure_resistance_short,
        "hfpef_hint": hfpef_hint,
        "co_method_desc": co_method_desc,
        "cv_stauung_phrase": cv_stauung_phrase,
        "pv_stauung_phrase": pv_stauung_phrase,
        "systemic_sentence": systemic_sentence,
        "oxygen_sentence": oxygen_sentence,
        "exam_type_desc": exam_type_desc,
        "exercise_protocol_sentence": exercise_protocol_sentence,
        "exercise_pattern_desc": exercise_pattern_desc,
        "provocation_sentence": provocation_sentence,
        "provocation_type_desc": provocation_type_desc,
        "provocation_result_sentence": provocation_result_sentence,
        "followup_timing_desc": followup_timing_desc,
        "invasive_followup_desc": invasive_followup_desc,
        "valve_focus_desc": valve_focus_desc,
        "anemia_context_desc": anemia_context_desc,
    }


# =============================================================================
# Procedere/module rendering with "already done" filtering
# =============================================================================

def _done_flags(env: Dict[str, Any]) -> Dict[str, bool]:
    # These flags are used to remove "already done" items from module texts
    return {
        "vq": bool(env.get("vq_done")),
        "ct": bool(env.get("ct_done")),
        "echo": bool(env.get("echo_done")),
        "cmr": bool(env.get("cmr_done")),
        "lufu": bool(env.get("lufu_done")),
        "cpet": bool(env.get("cpet_done")),
        "ccta": False,
    }


def render_p01_dynamic(env: Dict[str, Any]) -> str:
    """
    P01 is often a broad checklist; we make it dynamic so 'done' items are not repeated.
    """
    done = _done_flags(env)
    lines = []

    # echo
    if not done["echo"]:
        lines.append("• Echokardiographie (inkl. diastolischer Parameter, IVC, ggf. Kontrast)")
    # lufu
    if not done["lufu"]:
        lines.append("• Lungenfunktion inkl. DLCO und ggf. BGA")
    # CT / imaging
    if not done["ct"]:
        lines.append("• CT Thorax / CT-Angio (je nach DD, inkl. Parenchymbeurteilung)")
    # V/Q
    if not done["vq"]:
        lines.append("• V/Q-Szintigraphie zum Ausschluss einer chronisch thromboembolischen Genese")
    # labs
    lines.append("• Laborbasis (BB, Nierenwerte, Entzündung, BNP/NT-proBNP, Gerinnung je nach Kontext)")
    # functional
    lines.append("• Funktionelle Einordnung (WHO-FC, 6MWD ± CPET)")

    if not lines:
        lines = ["• Basisdiagnostik ist weitgehend komplettiert – Verlauf/Follow-up nach Klinik."]

    return "\n".join(lines)


def filter_module_text(text: str, env: Dict[str, Any]) -> str:
    """
    Removes obvious 'already done' bullet lines from module text.
    Keeps the rest unchanged.
    """
    done = _done_flags(env)

    def _skip(line: str) -> bool:
        l = line.lower()
        if done["vq"] and ("v/q" in l or "vq" in l or "ventilations" in l):
            return True
        if done["ct"] and ("ct" in l or "computertom" in l or "angio" in l):
            # careful: don't remove "CCTA" or "CTEPH" words incorrectly
            if "cteph" in l:
                return False
            return True
        if done["echo"] and ("echo" in l or "echokard" in l):
            return True
        if done["lufu"] and ("lungenfun" in l or "dlco" in l):
            return True
        if done["cmr"] and ("mrt" in l or "cmr" in l or "kardio-mrt" in l):
            return True
        return False

    out_lines = []
    for ln in text.splitlines():
        if _skip(ln.strip()):
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).strip()


