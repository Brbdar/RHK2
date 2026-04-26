#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.48: rhk_case.py - Bool-Parsing zentralisiert (parse_boolish), Import-Edge-Cases robuster
# Refactor v1.24: rhk_case.py - Numerische Sanitization (unphys → None), fehlend ≠ 0, Imports entwirrt, Side-Effects reduziert
"""RHK Befundassistent – Case Builder.

Kernaufgaben
- Normalisierung UI-Inputs (ohne Imputation).
- Berechnung abgeleiteter Hämodynamik/Score-Parameter.
- Aufbau von `env` für das Regelwerk (YAML + SafeExpr).
- Aggregation von Warnungen (nicht blockierend).

Refactor v1.24 – klinische Sicherheits-Updates
- Zentralisierte Sanitization: `sanitize_ui_numbers()` (fehlend≠0, unphys→None).
- Defensiver Copy: `build_case` mutiert kein fremdes Dict mehr (Reproduzierbarkeit/Thread-Safety).
- Explizite Imports (kein `import *`), Type-Hints konsolidiert.
"""

from __future__ import annotations

from dataclasses import asdict
from html import escape as html_escape
from typing import Any, Dict, List, Optional, Tuple

from rhk_base import (
    APP_TITLE,
    SPRIME_RAAI_CUTOFF,
    TAPSE_SPAP_HIGH_RISK,
    TAPSE_SPAP_LOW_RISK,
    Decision,
    Rule,
    _as_list,
    _compare_rhk_trend,
    _fmt,
    _hemo_category,
    _infer_anemia,
    _normalize_module_ids,
    _safe_float,
    _safe_float_echo,
    _safe_int,
    analyze_exercise_slopes_2pt,
    apply_rule_engine_trace,
    calc_bmi,
    calc_bsa,
    calc_cpet_scores,
    calc_esc_ers_3_strata,
    calc_esc_ers_4_strata,
    calc_esc_ers_comprehensive_3_strata,
    calc_h2fpef_probability,
    calc_mpap_from_spap_dpap,
    calc_reveal_lite2,
    collect_plausibility_warnings,
    compute_p_module_policy,
    describe_exercise_pattern,
    detect_step_up,
    fmt_int,
)
from rhk_case_schema import BuiltCaseSchema, CaseLike, CaseSection
from rhk_echo_guidelines import compute_echo_ph_probability
from rhk_logging import log_exception
from rhk_ph_tx import (
    derive_rulebook_class_lists_from_episodes,
    legacy_lists_to_episodes,
    parse_ph_tx_table_rows,
)
from rhk_validation import parse_boolish, sanitize_ui_numbers

_UNICODE_DASH_TO_ASCII = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
})


def _normalize_med_class_list(v: Any) -> List[str]:
    """Normalize medication class-tag lists used by rule expressions."""
    if v is None:
        return []

    if isinstance(v, str):
        items = [v]
    elif isinstance(v, (list, tuple, set)):
        items = list(v)
    else:
        return []

    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item or "").translate(_UNICODE_DASH_TO_ASCII).strip()
        if not s:
            continue
        s = " ".join(s.split())
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _prepare_ui_for_case_build(ui: CaseSection) -> CaseSection:
    """Normalize and sanitize raw UI payload before derivations."""
    ui = dict(ui or {})

    for _mk in ("ph_current_meds", "ph_prev_meds", "ph_new_meds", "ph_stopped_meds"):
        if _mk in ui:
            ui[_mk] = _normalize_med_class_list(ui.get(_mk))

    try:
        _mods = ui.get("modules")
        if isinstance(_mods, list) and _mods:
            ui["modules"] = _normalize_module_ids(_mods)
        else:
            _acc: List[str] = []
            for _k in ("modules_lvl1", "modules_lvl2", "modules_lvl3"):
                _v = ui.get(_k)
                if isinstance(_v, list):
                    _acc.extend([str(x) for x in _v if x])
            ui["modules"] = _normalize_module_ids(_acc)
    except (KeyError, TypeError, IndexError) as exc:
        log_exception("RHK_CASE_MODULES", "Module normalization failed.", exc)

    return sanitize_ui_numbers(ui)


def build_case(ui: CaseSection, rules: List[Rule]) -> BuiltCaseSchema:
    """Public entrypoint kept stable for callers/tests."""
    return _build_case_impl(ui, rules)


def _build_case_impl(ui: CaseSection, rules: List[Rule]) -> BuiltCaseSchema:
    # ---------------------------------------------------------------------
    # Input pre-processing
    # ---------------------------------------------------------------------
    # - defensive copy (no external mutations)
    # - module normalization (single source of truth: ui["modules"])
    # - medication class-tag normalization
    # - numeric sanitization (fehlend != 0, unphys -> None)
    ui = _prepare_ui_for_case_build(ui)
    _b = parse_boolish

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
    rap_pk = _safe_float(ui.get("rap_peak"))
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

    # Exercise hemodynamics should be interpreted ONLY if explicitly marked as performed.
    # It is common that peak values are imported/typed although a true exercise protocol
    # was not done; we must not silently include these into interpretation.
    exercise_checked = _b(ui.get("exercise_done"))
    exercise_values_present = any(
        v is not None for v in [co_peak, mpap_peak, pawp_peak, spap_pk, dpap_pk, rap_pk]
    )
    exercise_done = exercise_checked

    # Exercise (semi supine, only rest + peak): two-point slopes (Δ/ΔCO)
    ex2 = analyze_exercise_slopes_2pt(
        exercise_done=exercise_done,
        mpap_rest=mpap,
        pawp_rest=pawp,
        co_rest=co,
        mpap_peak=mpap_peak,
        pawp_peak=pawp_peak,
        co_peak=co_peak,
        tpg_rest=tpg,
        tpg_peak=(mpap_peak - pawp_peak) if (mpap_peak is not None and pawp_peak is not None) else None,
        wedge_v_wave=_b(ui.get("wedge_v_wave")),
        wedge_a_wave=_b(ui.get("wedge_a_wave")),
        atrial_fib=_b(ui.get("atrial_fib")),
        co_method=str(ui.get("co_method") or "").strip(),
        age=_safe_int(ui.get("age")),
    )

    # expose numbers (backwards compatible keys stay populated)
    dco = ex2.get("dco")
    mpap_co_slope = ex2.get("mpap_co_slope_2pt")
    pawp_co_slope = ex2.get("pawp_co_slope_2pt")
    tpg_co_slope_2pt = ex2.get("tpg_co_slope_2pt")

    # pattern code only if QC gate is ok (still two-point)
    exercise_interpretability = ex2.get("interpretability")
    p2 = ex2.get("pattern_2pt")
    exercise_pattern = None
    if exercise_interpretability == "ok":
        if p2 == "normal":
            exercise_pattern = "exercise_2pt_normal"
        elif p2 == "pv_dominant":
            exercise_pattern = "exercise_2pt_pv_dominant"
        elif p2 == "la_dominant":
            exercise_pattern = "exercise_2pt_la_dominant"
        elif p2 == "mixed":
            exercise_pattern = "exercise_2pt_mixed"
        else:
            exercise_pattern = "exercise_2pt_unclear"
    # if numeric_only / hard_stop: keep exercise_pattern None (no pattern classification)


    delta_spap = (spap_pk - spap) if (spap is not None and spap_pk is not None) else None

    # Adaptation type (klinische Kurzregel / Wunschlogik)
    # User request: ΔsPAP < 30 mmHg → heterometrischer Adaptionstyp
    # (symmetrisch dazu: ΔsPAP ≥ 30 mmHg → homeometrischer Adaptionstyp)
    adaptation_type = None
    if exercise_done and delta_spap is not None:
        adaptation_type = "heterometric" if delta_spap < 30 else "homeometric"

    # ---- Volume challenge ----
    volume_done = _b(ui.get("volume_challenge_done"))
    pawp_pre = _safe_float(ui.get("pawp_pre"))
    pawp_post = _safe_float(ui.get("pawp_post"))
    mpap_pre = _safe_float(ui.get("mpap_pre"))
    mpap_post = _safe_float(ui.get("mpap_post"))
    pawp_delta = (pawp_post - pawp_pre) if (pawp_pre is not None and pawp_post is not None) else None
    mpap_delta = (mpap_post - mpap_pre) if (mpap_pre is not None and mpap_post is not None) else None

    # ---- Vasoreactivity ----
    vaso_done = _b(ui.get("vaso_test_done"))
    _vaso_response = ui.get("vaso_response_desc") or None  # noqa: F841 – reserved
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
    _la_enlarged = _b(ui.get("la_enlarged"))  # noqa: F841 – reserved
    ee_ratio = _safe_float_echo(ui.get("ee_ratio"))
    pasp_echo = _safe_float_echo(ui.get("pasp_echo"))
    trv = _safe_float(ui.get("trv_ms"))
    pa_diam = _safe_float(ui.get("pa_diam_mm"))
    rv_lv_ratio = _safe_float(ui.get("rv_lv_ratio"))
    septal_flattening = _b(ui.get("septal_flattening")) if ui.get("septal_flattening") is not None else None
    af = _b(ui.get("atrial_fib")) if ui.get("atrial_fib") is not None else None

    # IVC congestion proxy – categorical collapse yes/no
    ivc_diam = _safe_float(ui.get("ivc_diam_mm"))
    ivc_collapse = ui.get("ivc_collapse")  # "ja"/"nein"/None
    ivc_collapse_yes = True if (isinstance(ivc_collapse, str) and ivc_collapse.lower().startswith("ja")) else False if (isinstance(ivc_collapse, str) and ivc_collapse.lower().startswith("nein")) else None

    # Central venous congestion is only assessable if at least one of the
    # input proxies is present: RAP measurement OR an IVC qualitative/diam
    # statement. Without either, we must NOT assert "no congestion" — the
    # honest answer is "not assessable", which downstream phrases honor by
    # emitting an empty string (see cv_stauung_phrase below).
    congestion_assessable = (
        rap is not None
        or ivc_collapse_yes is not None
        or ivc_diam is not None
    )
    congestion_likely = False
    # Practical congestion heuristics (only meaningful when assessable):
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
    wedge_v_wave = _b(ui.get("wedge_v_wave"))
    wedge_a_wave = _b(ui.get("wedge_a_wave"))
    rap_a_wave = _b(ui.get("rap_a_wave"))
    rap_v_wave = _b(ui.get("rap_v_wave"))
    rv_pseudo_dip = _b(ui.get("rv_pseudo_dip"))
    rv_dip_plateau = _b(ui.get("rv_dip_plateau"))

    # ---- S'/RAAI ----
    s_prime = _safe_float_echo(ui.get("s_prime_cm_s"))
    ra_esa_cm2 = _safe_float_echo(ui.get("ra_esa_cm2"))
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
    tapse = _safe_float_echo(ui.get("tapse_mm"))
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

    # ---- Hyperzirkulation / High-output flags (no silent assumptions) ----
    # Thresholds are pragmatic and aligned with existing rulebook note (CO >= 8.0 L/min).
    HIGH_FLOW_CO_L_MIN = 8.0
    HIGH_FLOW_CI_L_MIN_M2 = 4.0

    high_flow: Optional[bool] = None
    if co is not None:
        high_flow = bool(co >= HIGH_FLOW_CO_L_MIN)
    elif ci is not None:
        high_flow = bool(ci >= HIGH_FLOW_CI_L_MIN_M2)

    liver_hint = False
    try:
        if str(ui.get("study_liver_pathologic") or "").strip() == "Ja":
            liver_hint = True
    except (KeyError, TypeError) as exc:
        log_exception("RHK_CASE_LIVER_STUDY", "Liver study flag lookup failed.", exc)
    try:
        if _b(ui.get("abd_sono_done")):
            abd_desc_l = str(ui.get("abd_sono_desc") or "").strip().lower()
            if any(w in abd_desc_l for w in ("zirrh", "portal", "portale", "tipp", "tips", "splen", "ascites", "aszites")):
                liver_hint = True
    except (KeyError, TypeError) as exc:
        log_exception("RHK_CASE_LIVER_SONO", "Abdominal sono liver hint lookup failed.", exc)

    low_pvr_mpap_elev = (mpap is not None and mpap > 20 and pawp is not None and pawp <= 15 and pvr is not None and pvr <= 2)
    flow_driven_pressure = bool(low_pvr_mpap_elev and (high_flow is True))
    poph_candidate = bool(liver_hint and mpap is not None and mpap > 20 and pawp is not None and pawp <= 15 and pvr is not None and pvr > 2)

    # ---- ILTS 2025 Leber Profile (für Textmodule, keine stillen Annahmen) ----
    liver_ph_profile_label = "Kein spezifisches Leber Profil."
    if liver_hint:
        _mpap = mpap
        _pawp = pawp
        _pvr = pvr
        if _pawp is not None and _pawp > 15:
            liver_ph_profile_label = (
                "Profil B (Volume Overload): Dominanz der postkapillären Komponente (PAWP > 15 mmHg). "
                "Fokus auf Volumenmanagement."
            )
        elif _mpap is not None and _mpap > 20 and _pawp is not None and _pawp <= 15 and _pvr is not None and _pvr <= 2:
            liver_ph_profile_label = (
                "Profil A (Hyperdynam): Hoher Fluss bei normalem PVR (≤ 2 WU). "
                "Keine pulmonalvaskuläre Erkrankung."
            )
        elif _mpap is not None and _mpap > 20 and _pawp is not None and _pawp <= 15 and _pvr is not None and _pvr > 2:
            risk_str = (
                "PVR 2 bis 3 WU (mild erhöht, präkapilläres Profil im Portal-/Leberkontext)"
                if _pvr <= 3
                else "PVR > 3 WU (deutlich erhöht, ausgeprägtere pulmonalvaskuläre Komponente)"
            )
            liver_ph_profile_label = (
                f"Profil C (PoPH DD): Präkapilläre Hämodynamik im Portal-/Leberkontext. {risk_str}. "
                "Engmaschiges Monitoring bzw. Abklärung erforderlich."
            )

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



    # ---- Echo probability of PH (ESC/ERS 2022: TRV + additional signs from >=2 categories) ----
    echo_prob = compute_echo_ph_probability(ui)
    echo_signs_n = echo_prob.sign_count
    echo_probability = echo_prob.probability
    echo_sign_categories_n = echo_prob.category_count
    echo_sign_categories = [k for k, vals in (echo_prob.category_reasons or {}).items() if vals]
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
        # Hyperzirkulation / High-output
        "high_flow": high_flow,
        "flow_driven_pressure": flow_driven_pressure,
        "low_pvr_mpap_elev": low_pvr_mpap_elev,
        "liver_hint": liver_hint,
        "liver_ph_profile_label": liver_ph_profile_label,
        "poph_candidate": poph_candidate,
        "exercise_done": exercise_done,
        "exercise_checked": exercise_checked,
        "exercise_values_present": exercise_values_present,
        "mpap_peak": mpap_peak,
        "pawp_peak": pawp_peak,
        "co_peak": co_peak,
        "ci_peak": ci_peak,
        "mpap_co_slope": mpap_co_slope,
        "pawp_co_slope": pawp_co_slope,
        "dco": dco,
        "d_mpap": ex2.get("d_mpap"),
        "d_pawp": ex2.get("d_pawp"),
        "d_tpg": ex2.get("d_tpg"),
        "tpg_peak": (mpap_peak - pawp_peak) if (mpap_peak is not None and pawp_peak is not None) else None,
        "tpg_co_slope_2pt": tpg_co_slope_2pt,
        "exercise_interpretability": exercise_interpretability,
        "exercise_hard_fail_flags": ex2.get("hard_fail_flags") or [],
        "exercise_soft_flags": ex2.get("soft_flags") or [],
        "exercise_qc_hard_stop": bool(exercise_interpretability == "hard_stop"),
        "exercise_qc_numeric_only": bool(exercise_interpretability == "numeric_only"),
        "exercise_hardstop": bool(exercise_interpretability == "hard_stop"),

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
        "congestion_assessable": congestion_assessable,
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
        "echo_sign_categories_n": echo_sign_categories_n,
        "echo_sign_categories": echo_sign_categories,
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

        # Guideline-based endpoint for fluid challenge is the *absolute* PAWP response.
        # Commonly used protocol: ~500 mL (7–10 mL/kg) NaCl over 5–10 min; PAWP ≥18 mmHg suggests occult LV diastolic dysfunction/HFpEF.
        # Note: Validation/long-term data are limited; data for PAH response are insufficient (ESC/ERS 2022).
        derived["vol_challenge_pawp_ge_18"] = bool(pawp_post_v >= 18.0)
    else:
        derived["vol_challenge_resp"] = ""
        derived["vol_challenge_pawp_ge_18"] = False

    agent = str(ui.get("vaso_agent") or "").strip()
    vaso_resp = str(ui.get("vaso_response_desc") or "").strip()
    if agent or vaso_resp:
        derived["vasoreactivity_resp"] = "; ".join([x for x in [agent, vaso_resp] if x])
    else:
        derived["vasoreactivity_resp"] = ""
    # ---- Scores ----
    who_fc = ui.get("who_fc") or None
    sixmwd = _safe_float(ui.get("six_mwd_m"))

    # ESC/ERS Follow-up Strata models: require a minimum of 2 of 3 parameters
    # (WHO-FC, 6MWD, BNP/NT-proBNP) to avoid misleading classifications.
    who_fc_val = (str(who_fc).strip() if who_fc is not None else "")
    has_who = bool(who_fc_val)
    has_6mwd = sixmwd is not None
    has_bio = (bnp_pg_ml is not None) or (ntprobnp_pg_ml is not None)

    esc_min_n = 2
    esc_missing: List[str] = []
    if not has_who:
        esc_missing.append("WHO-FC")
    if not has_6mwd:
        esc_missing.append("6MWD")
    if not has_bio:
        esc_missing.append("BNP/NT-proBNP")

    esc_n = int(has_who) + int(has_6mwd) + int(has_bio)

    esc4 = calc_esc_ers_4_strata(who_fc, sixmwd, bnp_pg_ml, ntprobnp_pg_ml) if esc_n >= esc_min_n else None
    esc3 = calc_esc_ers_3_strata(who_fc, sixmwd, bnp_pg_ml, ntprobnp_pg_ml) if esc_n >= esc_min_n else None

    reveal_lite2 = calc_reveal_lite2(ui)
    esc_comp = calc_esc_ers_comprehensive_3_strata(ui, derived)
    cpet = calc_cpet_scores(ui)
    # CPET Spiro-Logic (deterministic expert patterns; does not change risk scoring)
    try:
        import spiro_logic as _spiro
        spiro_res = _spiro.analyze(ui)
        if spiro_res:
            # Store only compact, rule-friendly signals (no long text blocks)
            try:
                derived.update(spiro_res.derived or {})
            except (KeyError, TypeError, AttributeError) as exc:
                log_exception("RHK_CASE_SPIRO_DERIVED", "Spiro derived update failed.", exc)
            _sp_derived = spiro_res.derived or {}
            derived["cpet_spiro_suspect_ph"] = bool(
                _sp_derived.get("cpet_pulm_vasc_signal")
                or _sp_derived.get("cpet_pulm_vasc_pattern")
            )
            derived["cpet_spiro_summary"] = spiro_res.overall_summary
        else:
            derived["cpet_spiro_suspect_ph"] = False
            derived["cpet_spiro_summary"] = ""
    except (ImportError, KeyError, TypeError, AttributeError) as exc:
        log_exception("RHK_CASE_SPIRO", "Spiro logic analysis failed.", exc)
        derived["cpet_spiro_suspect_ph"] = False
        derived["cpet_spiro_summary"] = ""

    scores: Dict[str, Any] = {
        "esc_ers_4s": esc4,
        "esc_ers_4s_n": esc_n,
        "esc_ers_4s_missing": esc_missing,
        "esc_ers_3s": esc3,
        "esc_ers_3s_n": esc_n,
        "esc_ers_3s_missing": esc_missing,
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

    derived.update({
        "esc_ers_4s": scores["esc_ers_4s"],
        "esc_ers_3s": scores["esc_ers_3s"],
        "esc_ers_4s_n": scores["esc_ers_4s_n"],
        "esc_ers_3s_n": scores["esc_ers_3s_n"],
    })

    
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

    # ---- PVOD/PCH: Red-Flag Synthese (subtil, nicht-diagnostisch) ----
    # Ziel: Hinweise nicht verpassen, ohne automatisch Diagnosen/Procedere zu erzwingen.
    try:
        dlco = _safe_float(ui.get("dlco_sb"))
        fvc_pct = _safe_float(ui.get("fvc_l"))

        ct_gg = _b(ui.get("ct_pvod_gg"))
        ct_septal = _b(ui.get("ct_pvod_septal"))
        ct_ln = _b(ui.get("ct_pvod_ln"))
        ct_cnt = int(ct_gg) + int(ct_septal) + int(ct_ln)

        dispro = _b(ui.get("pvod_dlco_disproportionate"))
        # konservativer Auto-Hinweis: Volumina weitgehend erhalten, Diffusion deutlich reduziert
        if (not dispro) and (dlco is not None) and (fvc_pct is not None):
            if (dlco < 50.0) and (fvc_pct >= 70.0):
                dispro = True

        rest_hypox = _b(ui.get("pvod_rest_hypoxemia"))
        ex_desat = _b(ui.get("pvod_ex_desat"))
        cpet_nadir = _safe_float(ui.get("cpet_spo2_nadir_pct"))
        if (not ex_desat) and (cpet_nadir is not None) and (cpet_nadir < 88.0):
            ex_desat = True

        edema = _b(ui.get("pvod_edema_on_vaso"))

        eif_done = _b(ui.get("eif2ak4_test_done"))
        eif_res = str(ui.get("eif2ak4_result") or "").strip().lower()
        eif_pos = bool(eif_done and eif_res == "positiv")

        # Level: 0 none | 1 soft | 2 suspicion | 3 genetic confirmation
        level = 0
        if eif_pos:
            level = 3
        else:
            if (dlco is not None and dlco < 35.0):
                level = max(level, 2)
            if (ct_cnt >= 2 and (((dlco is not None) and (dlco < 50.0)) or dispro)):
                level = max(level, 2)
            if ((dlco is not None and dlco < 50.0) or (ct_cnt >= 2) or dispro or edema):
                level = max(level, 1)

            # Eskalation zu "Verdacht" bei multi-axialer Konstellation
            axes = 0
            if (dlco is not None and dlco < 50.0) or dispro:
                axes += 1
            if ct_cnt >= 2:
                axes += 1
            if rest_hypox or ex_desat:
                axes += 1
            if edema:
                axes += 1
            if axes >= 2 and level >= 1:
                level = max(level, 2)

        hints = []
        if dlco is not None and dlco < 50.0:
            hints.append(f"DLCO {_fmt(dlco,0)}%")
        if dispro:
            hints.append("DLCO disproportional niedrig")
        if ct_cnt >= 2:
            hints.append("CT Red Flags")
        elif ct_cnt == 1:
            hints.append("CT Einzelzeichen")
        if rest_hypox:
            hints.append("Ruhe-Hypoxämie")
        if ex_desat:
            hints.append("Belastungs-Desaturation")
        if edema:
            hints.append("Ödem/Verschlechterung unter Vasodilatation")
        if eif_done and eif_res in ("positiv", "negativ"):
            hints.append(f"EIF2AK4 {eif_res}")

        derived["pvod_hint_level"] = int(level)
        derived["pvod_ct_count"] = int(ct_cnt)
        derived["pvod_hint_desc"] = ", ".join([h for h in hints if str(h).strip()])
        derived["pvod_suspect"] = bool(level >= 2)

    except (KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_CASE_PVOD", "PVOD red-flag synthesis failed.", exc)
        derived["pvod_hint_level"] = 0
        derived["pvod_ct_count"] = 0
        derived["pvod_hint_desc"] = ""
        derived["pvod_suspect"] = False

    # ------------------------------------------------------------------
    # PH Therapieepisoden
    # - UI speichert Tabelle als list[list] in ui['ph_tx_table'].
    # - Für Berichte: derived['ph_tx_episodes'] wird bereitgestellt.
    # - Für Regelwerk: Klassen-Tags werden aus Episoden abgeleitet und
    #   in derived unter den Legacy-Keys ph_current_meds/... bereitgestellt.
    #   Dadurch werden UI-Felder nicht überschrieben.
    # ------------------------------------------------------------------
    try:
        _rows = ui.get("ph_tx_table")
        eps_explicit = parse_ph_tx_table_rows(_rows)
        # Report-Fallback: wenn keine expliziten Episoden, nutze Legacy-Listen
        eps_for_report = eps_explicit if eps_explicit else legacy_lists_to_episodes(ui)
        derived["ph_tx_episodes"] = eps_for_report
        # Rulebook-Abbild nur bei expliziter Episoden-Erfassung
        if eps_explicit:
            derived.update(derive_rulebook_class_lists_from_episodes(eps_explicit))
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        log_exception("RHK_CASE_PH_TX", "PH therapy episode parsing failed.", exc)
        derived["ph_tx_episodes"] = legacy_lists_to_episodes(ui)

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

    # apply rules (first pass) to get the baseline classification
    decision_seed, _rule_trace_seed = apply_rule_engine_trace(env, rules)


    # Ätiologie-Helfer (mehrere Ursachen können parallel bestehen)
    try:
        ph_etiology = infer_ph_etiology(env, decision_seed)
    except (KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_CASE_ETIOLOGY", "PH etiology inference failed.", exc)
        ph_etiology = {}
    derived["ph_etiology"] = ph_etiology
    env["ph_etiology"] = ph_etiology

    # ------------------------------------------------------------------
    # Patientenbericht-Archetypen (strukturelle Vorbereitung)
    # ------------------------------------------------------------------
    # IMPORTANT:
    # - This is a *purely structural* layer.
    # - It must NOT change any existing report text or bundle selection.
    # - Downstream usage is introduced in later steps.
    try:
        arch = classify_patient_archetype(ui=ui, derived=derived, decision=decision_seed, env=env)
    except (KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_CASE_ARCHETYPE", "Patient archetype classification failed.", exc)
        arch = {"p_archetype_id": "H0", "p_archetype_label": "Standard", "p_archetype_reason": ""}
    # Store in derived + env for future use; no current templates rely on this.
    derived.update(arch)
    env.update(arch)

    # P-Module Policy: first pass to expose leading_group/clear_leader to the rule engine.
    provisional_policy = compute_p_module_policy(ui, derived, decision_seed)
    derived["p_module_policy"] = provisional_policy
    env["p_module_policy"] = provisional_policy
    # Expose key etiology signals to the rule engine (top-level only; SafeExpr has no dict subscripts)
    _pol = provisional_policy or {}
    env["leading_group"] = _pol.get("leading_group")
    env["clear_leader"] = _pol.get("clear_leader")
    _gs = _pol.get("group_scores") or {}
    env["g1_score"] = _gs.get(1)
    env["g2_score"] = _gs.get(2)
    env["g3_score"] = _gs.get(3)
    env["g4_score"] = _gs.get(4)

    # apply rules again with etiology/leading_group signals available
    decision, rule_trace = apply_rule_engine_trace(env, rules)

    # missing fields required
    missing: List[str] = []
    for fld in decision.require_fields:
        v = env.get(fld)
        if v is None or v == "" or v is False:
            missing.append(fld)
    decision.missing_fields = missing

    # P-Module V3: erweiterte, sicherheitsorientierte Vorschläge (maximal 6).
    # UI Auswahl (ui['modules']) wird niemals überschrieben.
    try:
        from rhk_pmodules_v3 import apply_p_modules_v3
        decision.modules = apply_p_modules_v3(ui, derived, list(decision.modules or []))
    except (ImportError, KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_CASE_PMODULES", "P-modules v3 application failed.", exc)

    # Plausibilitätschecks (blockieren nicht)
    warnings = collect_plausibility_warnings(ui, derived)
    derived["warnings_count"] = len(warnings)
    env["warnings_count"] = len(warnings)

    # Debug payload: Rule-Trace + Warnungen
    debug_payload = {
        "warnings": warnings,
        "rule_trace": asdict(rule_trace),
    }

    # Final policy recompute after the enriched rule pass.
    derived["p_module_policy"] = compute_p_module_policy(ui, derived, decision)
    env["p_module_policy"] = derived["p_module_policy"]
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

    case: BuiltCaseSchema = {
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
        has_ph = bool(env.get("precap") or env.get("has_ph"))
        dx = "CTEPH" if has_ph else "CTEPD ohne PH"

        # Wenn bereits ein Konferenzbeschluss vorliegt, keine redundanten Empfehlungen.
        if bool(env.get("vq_cteph_conf_done")):
            dt = str(env.get("vq_cteph_conf_date") or "").strip()
            return (
                f"chronisch thromboembolische Genese ({dx}, Gruppe 4)",
                ("das weitere Procedere gemäß CTEPH Konferenzbeschluss" + (f" vom {dt}" if dt else ""))
            )

        bits: List[str] = []
        if not bool(env.get("vq_done")):
            bits.append("V/Q")
        bits.append("CT oder Angio Review")
        if not bool(env.get("vq_pa_angio_done")):
            bits.append("ggf. PA Angio")
        action = "die Vorstellung im CTEPH PH Board und die weitere spezifische Abklärung (" + ", ".join(bits) + ")"
        return (f"chronisch thromboembolische Genese ({dx}, Gruppe 4)", action)

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
        return (
            "pulmonalvaskuläre Ursache (PAH/Gruppe 1; DD andere präkapilläre Ursachen)",
            "die weiterführende Abklärung präkapillärer Ursachen (u.a. Autoimmunität, HIV/Leber, ggf. Genetik) und die PH-spezifische Therapie nach Risikostratifizierung",
        )

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

    g4_dx = "CTEPH" if has_ph else "CTEPD ohne PH"

    _add_candidate(
        4,
        g4,
        f"chronisch thromboembolische Genese ({g4_dx}, Gruppe 4)",
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
        # Bei klar präkapillärem Muster wird Gruppe 2 als führende Ursache weniger wahrscheinlich,
        # bleibt aber als DD bestehen.
        g2 = max(1, g2 - 1)

    # HFpEF-spezifische Formulierung wenn möglich
    g2_label = "linksherzbedingte Genese (Gruppe 2)"
    if (decision and decision.bundle and "HFpEF" in decision.bundle) or hfpef_cat == "likely":
        g2_label = "linksherzbedingte Genese im Sinne einer HFpEF/DD (Gruppe 2)"

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
        "lungenerkrankungsassoziierte Genese (Gruppe 3)",
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
        # Keep label short (risk factors belong into evidence lines, not the label itself).
        label_doc = "pulmonalvaskuläre Ursache (PAH, Gruppe 1)"
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
            # Wenn bereits ein CTEPH Konferenzbeschluss vorliegt, keine redundanten Empfehlungen.
            if bool(env.get("vq_cteph_conf_done")):
                dt = str(env.get("vq_cteph_conf_date") or "").strip()
                dec_txt = str(env.get("vq_cteph_conf_decision") or "").strip()
                s = "Das weitere Procedere richtet sich nach dem vorliegenden CTEPH Konferenzbeschluss"
                if dt:
                    s += f" vom {dt}"
                s += "."
                if dec_txt:
                    # keine stillen Annahmen zur Form; Text wird unverändert übernommen
                    s += " Konferenzbeschluss: " + dec_txt.rstrip(".") + "."
                parts.append(s)
            else:
                bits: List[str] = []
                if not bool(env.get("vq_done")):
                    bits.append("V/Q")
                bits.append("CT oder Angio Review")
                if not bool(env.get("vq_pa_angio_done")):
                    bits.append("ggf. PA Angio")
                inside = ", ".join([b for b in bits if b])
                parts.append(
                    "Vorstellung im CTEPH PH Board und spezifische Abklärung" + (f" ({inside})." if inside else ".")
                )
        if 2 in groups:
            parts.append("Kardiologische Mitbeurteilung und Therapieoptimierung der Linksherzerkrankung/HFpEF.")
        if 3 in groups:
            parts.append("Pneumologische Mitbeurteilung und Optimierung/Abklärung der Lungenerkrankung (inkl. Lufu/CT-Korrelation, O2-Bedarf).")
        if 1 in groups:
            parts.append("PH-Zentrum: komplette PAH-DD/Abklärung (Autoimmunität, HIV/Infektiologie, Genetik/angeborene Herzfehler) und Therapie nach Risikoprofil.")
        return parts

    groups = [c["group"] for c in candidates_sorted]
    action_parts = _actions_for(groups)
    cteph_conf_done = bool(env.get("vq_cteph_conf_done"))

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
                doc_conclusion = f"Ätiologische Einordnung: Am ehesten {lead_label}. DD: {', '.join(other)}."
            else:
                doc_conclusion = f"Ätiologische Einordnung: Am ehesten {lead_label}."
        else:
            doc_conclusion = (
                "Ätiologische Einordnung: Hinweise auf mehrere mögliche Ursachen/Mechanismen ("
                f"{', '.join(doc_labels)}). Führende Zuordnung anhand der vorliegenden Angaben nicht sicher."
            )

        # Empfehlung anhängen (kompakt)
        if action_parts:
            # Bei vorhandenem Konferenzbeschluss in klarer Gruppe 4 Konstellation keine "Empfohlen"-Redundanz.
            if cteph_conf_done and clear_leader and leading_group == 4 and len(groups) == 1:
                doc_conclusion += " " + " ".join(action_parts)
            else:
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


# =============================================================================
# Patientenbericht-Archetypen (strukturelle Vorbereitung)
# =============================================================================

def classify_patient_archetype(
    *,
    ui: Dict[str, Any],
    derived: Dict[str, Any],
    decision: Optional[Decision] = None,
    env: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a patient-report archetype classification.

    IMPORTANT (v28.9):
    - This layer is intentionally conservative and *must not* change existing outputs.
    - It only exposes a future-facing structure so downstream narrative selection can
      be implemented incrementally without refactoring the whole report builder.

    Output keys:
    - p_archetype_id: "H0".."H6"
    - p_archetype_label: short German label
    - p_archetype_reason: short, internal explanation (no PHI)
    """

    d = derived or {}
    u = ui or {}
    e = env or {}

    mpap = _safe_float(d.get("mpap_rest") if d.get("mpap_rest") is not None else d.get("mpap"))
    pawp = _safe_float(d.get("pawp_rest") if d.get("pawp_rest") is not None else u.get("pawp_rest"))
    pvr = _safe_float(d.get("pvr_rest") if d.get("pvr_rest") is not None else d.get("pvr"))
    ci = _safe_float(d.get("ci_rest") if d.get("ci_rest") is not None else d.get("ci"))
    rap = _safe_float(d.get("rap_rest") if d.get("rap_rest") is not None else u.get("rap_rest"))

    has_ph = bool(mpap is not None and mpap > 20)
    _hemo_cat = str(d.get("hemo_category") or e.get("hemo_category") or "").strip().lower()  # noqa: F841

    # --- context / risk flags ---
    ph_known = bool(u.get("ph_known"))
    ph_suspected = bool(u.get("ph_suspected"))
    viro_pos = bool(u.get("virology_pos"))
    immun_pos = bool(u.get("immunology_pos"))
    chd_pos = bool(u.get("chd_pos"))
    prev_meds = u.get("ph_prev_meds")
    prev_meds_any = bool(isinstance(prev_meds, list) and len([x for x in prev_meds if x]) > 0)

    clot_hint = bool(u.get("vq_defect") or u.get("ct_embolie") or u.get("ct_mosaic") or u.get("pe_history") or u.get("ct_pe"))

    # --- archetype rules (conservative heuristics) ---
    # H5: CTEPH / thromboembolic constellation
    if clot_hint:
        return {
            "p_archetype_id": "H5",
            "p_archetype_label": "Thromboembolische Konstellation",
            "p_archetype_reason": "Trigger: V/Q/CT/Anamnese Hinweis auf Thromboembolie/CTEPH",
        }

    # H4: Postcap / combined PH
    if pawp is not None and pawp > 15:
        return {
            "p_archetype_id": "H4",
            "p_archetype_label": "Linksherz-Beteiligung",
            "p_archetype_reason": "Trigger: PAWP > 15 mmHg (postkapilläre/kom. Komponente)",
        }

    # H3: Established precapillary PH
    if has_ph and (pvr is not None and pvr > 2) and (pawp is None or pawp <= 15):
        return {
            "p_archetype_id": "H3",
            "p_archetype_label": "Etablierte präkapilläre PH",
            "p_archetype_reason": "Trigger: mPAP > 20 + PVR > 2 bei PAWP ≤ 15",
        }

    # H2: Borderline / early PH-like constellation
    if (mpap is not None and 18 <= mpap <= 22) and (pvr is not None and 2 <= pvr <= 3) and (ci is None or ci >= 2.5):
        return {
            "p_archetype_id": "H2",
            "p_archetype_label": "Grenzwerte / frühes Stadium",
            "p_archetype_reason": "Trigger: mPAP 18–22 + PVR 2–3 (CI nicht niedrig)",
        }

    # H6: Right-heart impairment dominates despite moderate pressures
    # Note: we only flag this if PH is not clearly severe and there are hints of RV/RA strain.
    rv_strain = bool(
        (rap is not None and rap >= 12)
        or bool(d.get("tapse_spap_reduced"))
        or bool(d.get("tapse_spap_reduced") is True)
        or bool(d.get("echo_probability") == "hoch")
        or (ci is not None and ci < 2.2)
    )
    if (mpap is not None and 20 < mpap <= 30) and rv_strain:
        return {
            "p_archetype_id": "H6",
            "p_archetype_label": "Rechtsherz-Funktion im Vordergrund",
            "p_archetype_reason": "Trigger: moderater Druck + Hinweise auf RA/RV-Belastung (RAP/CI/Echo)",
        }

    # H1: No PH at rest but elevated risk / prior context
    no_ph_rest = bool(mpap is not None and mpap <= 20)
    risk_context = bool(ph_known or ph_suspected or viro_pos or immun_pos or chd_pos or prev_meds_any)
    if no_ph_rest and risk_context:
        return {
            "p_archetype_id": "H1",
            "p_archetype_label": "Kein PH in Ruhe, aber Risiko",
            "p_archetype_reason": "Trigger: mPAP ≤ 20 + Risiko-/Vorerkrankungs-Kontext",
        }

    return {
        "p_archetype_id": "H0",
        "p_archetype_label": "Standard",
        "p_archetype_reason": "",
    }

def build_dashboard_html(case: Optional[CaseLike]) -> str:
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
            except (TypeError, ValueError) as exc:
                log_exception("RHK_CASE_BADGE", "Badge title escaping failed.", exc)
                tattr = ""
        return f'<span class="{cls}"{tattr}>{text}</span>'

    risk_badges = []
    # REVEAL Lite 2 (wenn möglich prominent anzeigen)
    if sc.get("reveal_lite2"):
        cat = sc.get("reveal_lite2")
        pts = sc.get("reveal_lite2_points")
        missing = sc.get("reveal_lite2_missing") or []
        tip = None
        if isinstance(missing, list) and missing:
            tip = "Fehlend: " + ", ".join([str(x) for x in missing]) + " | Mindestparameter: 6/6 (WHO-FC, 6MWD, BNP/NT-proBNP, RR syst, HF, eGFR)"
        if cat == "nicht berechenbar":
            risk_badges.append(badge("REVEAL Lite 2: nicht berechenbar", "badge badge-na", tip))
        else:
            cat_de = {"low": "niedrig", "intermediate": "intermediär", "high": "hoch"}.get(str(cat), str(cat))
            pts_txt = f"{pts} Pkt." if pts is not None else "—"
            cls = {"low": "badge badge-low", "intermediate": "badge badge-intermediate", "high": "badge badge-high"}.get(str(cat), "badge badge-na")
            risk_badges.append(badge(f"REVEAL Lite 2: {pts_txt} ({cat_de})", cls, tip))
    # ESC/ERS Follow-up strata badges with hover missing-parameter info
    esc4 = sc.get("esc_ers_4s")
    esc4_missing = sc.get("esc_ers_4s_missing") or []
    if esc4:
        tip = None
        if isinstance(esc4_missing, list) and esc4_missing:
            tip = "Nicht eingeflossen (fehlend): " + ", ".join([str(x) for x in esc4_missing]) + " | Mindestparameter: 2/3 (WHO-FC, 6MWD, BNP/NT-proBNP)"
        cls = {"low": "badge badge-low", "intermediate-low": "badge badge-intermediate", "intermediate-high": "badge badge-intermediate-high", "high": "badge badge-high"}.get(str(esc4), "badge badge-na")
        risk_badges.append(badge(f"ESC/ERS 4-Strata: {esc4}", cls, tip))
    elif isinstance(esc4_missing, list) and esc4_missing:
        tip = "Fehlend: " + ", ".join([str(x) for x in esc4_missing]) + " | Mindestparameter: 2/3 (WHO-FC, 6MWD, BNP/NT-proBNP)"
        risk_badges.append(badge("ESC/ERS 4-Strata: nicht berechenbar", "badge badge-na", tip))

    esc3 = sc.get("esc_ers_3s")
    esc3_missing = sc.get("esc_ers_3s_missing") or []
    if esc3:
        tip = None
        if isinstance(esc3_missing, list) and esc3_missing:
            tip = "Nicht eingeflossen (fehlend): " + ", ".join([str(x) for x in esc3_missing]) + " | Mindestparameter: 2/3 (WHO-FC, 6MWD, BNP/NT-proBNP)"
        cls = {"low": "badge badge-low", "intermediate": "badge badge-intermediate", "high": "badge badge-high"}.get(str(esc3), "badge badge-na")
        risk_badges.append(badge(f"ESC/ERS 3-Strata: {esc3}", cls, tip))
    elif isinstance(esc3_missing, list) and esc3_missing:
        tip = "Fehlend: " + ", ".join([str(x) for x in esc3_missing]) + " | Mindestparameter: 2/3 (WHO-FC, 6MWD, BNP/NT-proBNP)"
        risk_badges.append(badge("ESC/ERS 3-Strata: nicht berechenbar", "badge badge-na", tip))
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
        # Belastungsmuster ist ein klinischer Risikoindikator:
        # - postkapilläre Demaskierung oder linksatrialer Druckanstieg unter Belastung: rot
        # - präkapilläre Auffälligkeit unter Belastung: orange
        # - regelhafte Reaktion: grün
        patt = str(der.get("exercise_pattern") or "")
        cls = {
            "postcap_pattern": "badge badge-high",
            "left_pressure_pattern": "badge badge-high",
            "precap_pattern": "badge badge-intermediate-high",
            "normal_pattern": "badge badge-low",
        }.get(patt, "badge badge-na")
        risk_badges.append(badge(f"Belastungsmuster: {describe_exercise_pattern(patt)}", cls))

    if der.get("adaptation_type"):
        ad = str(der.get("adaptation_type"))
        ad_de = "homeometrisch" if ad == "homeometric" else "heterometrisch" if ad == "heterometric" else ad
        d_spap = der.get("delta_spap")
        d_txt = f" (ΔsPAP {_fmt(d_spap,0)} mmHg)" if d_spap is not None else ""
        # Adaptionstyp:
        # - homeometrisch: grün
        # - heterometrisch: rot
        cls = {
            "homeometric": "badge badge-low",
            "heterometric": "badge badge-high",
        }.get(ad, "badge badge-na")
        risk_badges.append(badge(f"Adaptionstyp: {ad_de}{d_txt}", cls))

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
    except (KeyError, TypeError, IndexError) as exc:
        log_exception("RHK_CASE_WARNS_HTML", "Warning summary HTML generation failed.", exc)
        warns_summary = '<span class="muted">keine</span>'


    # Verlauf (RHK) – kompakt, aber klinisch hilfreich
    trend_html = ""
    try:
        t = _compare_rhk_trend(case.get("ui") or {}, case.get("derived") or {})
        if isinstance(t, dict) and t.get("has_prev"):
            # Convert the markdown table to a compact HTML table
            def _md_table_to_html(md: str) -> str:
                lines = [ln.strip() for ln in (md or "").splitlines() if ln.strip()]
                rows = [ln for ln in lines if ln.startswith("|") and ln.endswith("|")]
                if len(rows) < 3:
                    return ""
                body = rows[2:]
                tr = []
                for r in body:
                    parts = [p.strip() for p in r.strip("|").split("|")]
                    if len(parts) < 4:
                        continue
                    tr.append(
                        "<tr>" +
                        f"<td><b>{html_escape(parts[0])}</b></td>" +
                        f"<td style='text-align:right'>{html_escape(parts[1])}</td>" +
                        f"<td style='text-align:right'>{html_escape(parts[2])}</td>" +
                        f"<td style='text-align:center'>{html_escape(parts[3])}</td>" +
                        "</tr>"
                    )
                if not tr:
                    return ""
                return (
                    "<table class='rhk-trend-table'>"
                    "<thead><tr><th>Parameter</th><th>Vorher</th><th>Jetzt</th><th>Trend</th></tr></thead>"
                    "<tbody>" + "".join(tr) + "</tbody></table>"
                )

            tbl = _md_table_to_html(t.get("table_md") or "")
            if tbl:
                trend_html = (
                    "<div class='card' style='margin-top:10px'>"
                    "<div class='card-title'>Verlauf – RHK (Ruhe)</div>"
                    f"<div class='muted' style='margin-bottom:8px'>{html_escape(str(t.get('sentence_doc') or '').replace('**',''))}</div>"
                    f"{tbl}"
                    "</div>"
                )
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        log_exception("RHK_CASE_TREND_HTML", "Trend HTML generation failed.", exc)
        trend_html = ""

    bundle_txt = html_escape(str(d.get("bundle", "–")))
    primary_dx_txt = html_escape(str(d.get("primary_dx", "–")))
    tags_txt = ", ".join(html_escape(str(t)) for t in tags) if tags else '<span class="muted">–</span>'

    # Human-readable labels for commonly missing fields
    _MISSING_LABELS: Dict[str, str] = {
        "mpap": "mPAP", "pawp": "PAWP", "pvr": "PVR", "co": "CO", "ci": "CI",
        "spap_rest": "sPAP", "dpap_rest": "dPAP", "mpap_rest": "mPAP",
        "pawp_rest": "PAWP", "rap_rest": "RAP", "co_rest": "CO", "ci_rest": "CI",
        "pvr_rest": "PVR", "age": "Alter", "height_cm": "Größe", "weight_kg": "Gewicht",
        "who_fc": "WHO-FC", "six_mwd": "6MWD", "bnp_value": "BNP/NT-proBNP",
        "bp_sys": "RR syst.", "hr": "HF", "hb_g_dl": "Hb",
    }
    _CRITICAL_HEMO = {"mpap", "pawp", "pvr", "co", "ci", "spap_rest", "dpap_rest", "mpap_rest", "pawp_rest", "co_rest"}
    missing_labels = [_MISSING_LABELS.get(m, m) for m in missing]
    missing_txt = ", ".join(html_escape(str(m)) for m in missing_labels) if missing_labels else '<span class="muted">keine</span>'
    critical_missing = [m for m in missing if m in _CRITICAL_HEMO]
    missing_hint = ""
    if critical_missing:
        crit_labels = ", ".join(_MISSING_LABELS.get(m, m) for m in critical_missing)
        missing_hint = (
            f'<div style="color:#b91c1c; font-size:0.88em; margin-top:3px;">'
            f'⚠ Zentrale Hämodynamik-Werte fehlen ({html_escape(crit_labels)}) — '
            f'Klassifikation und Risikostratifizierung können unvollständig sein.</div>'
        )

    return f"""
    <div class="card">
      <div class="card-title">{APP_TITLE}</div>
      <div class="row">
        <div><b>Bundle:</b> {bundle_txt}</div>
        <div><b>Primäre Einordnung:</b> {primary_dx_txt}</div>
      </div>
      <div class="badges">{''.join(risk_badges) if risk_badges else '<span class="muted">Keine Scores verfügbar.</span>'}</div>
      <div class="row">
        <div><b>Tags:</b> {tags_txt}</div>
      </div>
      <div class="row">
        <div><b>Fehlende Angaben (für Regelwerk):</b> {missing_txt}{missing_hint}</div>
      </div>
      <div class="row">
        <div><b>Plausibilitätswarnungen:</b> {warns_summary}</div>
      </div>
    </div>
    {trend_html}
    """


# =============================================================================
# Render context for template blocks
# =============================================================================

def build_render_ctx(case: CaseLike) -> Dict[str, Any]:
    ui = case["ui"]
    der = case["derived"]
    env = case["env"]
    sc = case.get("scores") or {}

    mpap = der.get("mpap")
    pawp = _safe_float(ui.get("pawp_rest"))
    _rap = _safe_float(ui.get("rap_rest"))  # noqa: F841 – reserved
    pvr = der.get("pvr")
    ci = der.get("ci")
    tpg = der.get("tpg")
    dpg = der.get("dpg")

    # Compact numeric placeholders for templates
    CI_value = _fmt(ci, 2)


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

    # Slopes hint only if exercise done (semi supine, two-point rest→peak)
    slope_hint = ""
    if der.get("exercise_done") and der.get("dco") is not None and (der.get("mpap_co_slope") is not None) and (der.get("pawp_co_slope") is not None):
        slope_hint = (
            f"Belastung 2pt (Ruhe→Peak): dCO {str(_fmt(der.get('dco'),1)) } L/min; "
            f"ΔmPAP/ΔCO {str(_fmt(der.get('mpap_co_slope'),1)) } / "
            f"ΔPAWP/ΔCO {str(_fmt(der.get('pawp_co_slope'),1)) } / "
            f"ΔTPG/ΔCO {str(_fmt(der.get('tpg_co_slope_2pt'),1)) } mmHg/(L/min)."
        )

    tpg_hint = f"TPG {str(_fmt(tpg,0)) } mmHg" if tpg is not None else ""
    dpg_hint = f"DPG {str(_fmt(dpg,0)) } mmHg" if dpg is not None else ""

    pressure_resistance_short = ", ".join([x for x in [mpap_phrase, pawp_phrase, pvr_phrase, ci_phrase, tpg_hint, dpg_hint, slope_hint] if x])

    # Additional helper sentences for rhk_textdb templates (missing keys are filled with '' via SafeDict)
    # CO-Methode ist klinisch relevant. Wenn nicht dokumentiert: NICHT erwähnen.
    # (Keine stillen Annahmen; fehlende Angaben ≠ Default.)
    co_method_desc = ""
    # Phrase inkl. führendem Leerzeichen, um Templates wie "{ci_phrase}{co_method_phrase}." zu ermöglichen.
    co_method_phrase = ""
    _cm = ui.get("co_method")
    co_method_raw = str(_cm or "").strip().lower()
    if co_method_raw in ("thermodilution", "thermo", "td") or str(_cm or "") == "Thermodilution":
        co_method_desc = "Thermodilution"
        co_method_phrase = " nach Thermodilution"
    elif co_method_raw in ("fick", "fick-prinzip") or str(_cm or "") == "Fick":
        co_method_desc = "Fick-Prinzip"
        co_method_phrase = " nach Fick-Prinzip"

    # Congestion phrasing: each phrase is a standalone sentence so templates
    # that use only `{cv_stauung_phrase}` (e.g. in shunt- or postkap-bundles)
    # remain grammatically correct. Double-negative redundancy ("Keine Hinweise
    # auf venöse Kongestion. Keine Hinweise auf pulmonalvenöse Stauung.") is
    # collapsed into a single idiomatic sentence and the paired phrase is
    # emptied so templates using the `{cv_} {pv_}` pair don't duplicate content.
    #
    # Critical: a "Keine Hinweise auf …"-phrase may only be emitted when the
    # underlying parameter is actually available. Without RAP/IVC information
    # we cannot make any statement about central venous congestion; without
    # PAWP we cannot make any statement about pulmonalvenöse Stauung.
    # Otherwise the report would falsely reassure the reader.
    _cv_assessable = bool(der.get("congestion_assessable"))
    _pv_assessable = (pawp is not None)
    _cv_pos = bool(der.get("congestion_likely")) and _cv_assessable
    _pv_pos = bool(env.get("pawp_gt15")) and _pv_assessable

    if _cv_pos:
        cv_stauung_phrase = "Hinweise auf venöse Kongestion."
    elif _cv_assessable:
        cv_stauung_phrase = "Keine Hinweise auf venöse Kongestion."
    else:
        # No RAP and no IVC information → silent (do not assert anything).
        cv_stauung_phrase = ""

    if _pv_pos:
        pv_stauung_phrase = "Hinweise auf pulmonalvenöse Stauung."
    elif _pv_assessable:
        pv_stauung_phrase = "Keine Hinweise auf pulmonalvenöse Stauung."
    else:
        # No PAWP → silent.
        pv_stauung_phrase = ""

    # Idiomatic collapse only when BOTH are assessable AND both negative —
    # otherwise we'd be pretending to know more than we do.
    if (
        not _cv_pos
        and not _pv_pos
        and _cv_assessable
        and _pv_assessable
    ):
        cv_stauung_phrase = "Keine Hinweise auf venöse Kongestion oder pulmonalvenöse Stauung."
        pv_stauung_phrase = ""
    elif _cv_pos and _pv_assessable and not _pv_pos:
        # cv positive, pv assessable & negative → keep explicit pv negative
        # so paired-phrase templates carry both pieces of information.
        pv_stauung_phrase = "Keine Hinweise auf pulmonalvenöse Stauung."

    sbp = _safe_float(ui.get("bp_sys"))
    dbp = _safe_float(ui.get("bp_dia"))
    hr = _safe_float(ui.get("hr"))
    systemic_sentence = ""
    if sbp is not None or dbp is not None or hr is not None:
        parts = []
        if sbp is not None or dbp is not None:
            # Prefer RR syst/diast if available; otherwise keep single value.
            if sbp is not None and dbp is not None:
                parts.append(f"RR {_fmt(sbp,0)}/{_fmt(dbp,0)} mmHg")
            elif sbp is not None:
                parts.append(f"RR {_fmt(sbp,0)} mmHg")
            else:
                parts.append(f"RR {_fmt(dbp,0)} mmHg")
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

    # Build a natural-language description of which RHK add-on tests were performed.
    # The legacy " + " join produced clinically awkward output like
    # "RHK in Ruhe + Belastung + Vasoreaktivitätstest." which reads more like a
    # feature-flag dump than a medical report. We join with comma/"und" instead.
    exam_type_desc = "RHK in Ruhe"
    _parts = []
    if der.get("exercise_done"):
        _parts.append("Belastungsmessung")
    if der.get("volume_challenge_done"):
        _parts.append("Volumenchallenge")
    if der.get("vasoreactivity_done"):
        _parts.append("Vasoreaktivitätstestung")
    if len(_parts) == 1:
        exam_type_desc = f"RHK in Ruhe mit ergänzender {_parts[0]}"
    elif len(_parts) == 2:
        exam_type_desc = f"RHK in Ruhe mit ergänzender {_parts[0]} und {_parts[1]}"
    elif len(_parts) >= 3:
        exam_type_desc = "RHK in Ruhe mit " + ", ".join(_parts[:-1]) + f" und {_parts[-1]}"

    provocation_sentence = ""
    provocation_type_desc = ""
    provocation_result_sentence = ""
    if der.get("volume_challenge_done"):
        provocation_type_desc = "Volumenchallenge"
        pawp_pre = der.get("vol_challenge_pawp_pre")
        pawp_post = der.get("vol_challenge_pawp_post")
        delta = der.get("vol_challenge_delta_pawp")
        if pawp_pre is not None and pawp_post is not None:
            provocation_sentence = f"Nach Volumenchallenge PAWP {_fmt(pawp_pre,0)} → {_fmt(pawp_post,0)} mmHg"
            if delta is not None:
                provocation_sentence += f" (Δ {_fmt(delta,0)} mmHg)"
            if bool(der.get("vol_challenge_pawp_ge_18")):
                provocation_sentence += "; Endpunkt PAWP ≥18 mmHg (Hinweis okkulte HFpEF)."
            else:
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
        at = str(ui.get("anemia_type") or "").strip().lower()
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
    exercise_protocol = str(ui.get("exercise_protocol") or "").strip()
    exercise_peak_watts = _safe_float(ui.get("exercise_peak_watts"))
    exercise_protocol_sentence = ""
    if (parse_boolish(ui.get("exercise_done")) or parse_boolish((der.get("exercise_done") if der else False))) and (exercise_protocol or exercise_peak_watts is not None):
        if exercise_protocol and exercise_peak_watts is not None:
            exercise_protocol_sentence = f"In der Ergometrie nach {exercise_protocol} bis {fmt_int(exercise_peak_watts)} W."
        elif exercise_protocol:
            exercise_protocol_sentence = f"In der Ergometrie nach {exercise_protocol}."
        else:
            exercise_protocol_sentence = f"In der Ergometrie bis {fmt_int(exercise_peak_watts)} W."

    # ------------------------------------------------------------------
    # HFpEF-spezifische sprachliche Verfeinerung (nur wenn Konstellation passt)
    # Kriterien (konservativ): PAWP erhöht + LA vergrößert + E/e′ erhöht
    # Ziel: präzisere Interpretation ohne Therapie-/Procedere-Inhalte.
    # ------------------------------------------------------------------
    ee_ratio = _safe_float_echo(ui.get("ee_ratio"))
    ee_high = (ee_ratio is not None and ee_ratio >= 14)
    hfpef_language = bool(env.get("pawp_gt15")) and bool(env.get("la_enlarged")) and ee_high

    # Noun phrase used inside templates, e.g. "... bei {left_heart_context_desc}."
    # Must be clinically clear and stand alone.
    if hfpef_language:
        left_heart_context_desc = (
            "einer HFpEF typischen diastolischen Dysfunktion mit erhöhter linksatrialer Füllungsdrucklage, "
            "vergrößertem linken Vorhof und erhöhtem E/e′"
        )
    else:
        # Neutral default (keeps existing wording generic)
        left_heart_context_desc = "einer linksherzbedingten Druckerhöhung"

    # ------------------------------------------------------------------
    # Compatibility placeholders for K/B/E text blocks
    # ------------------------------------------------------------------
    mpap_s = _safe_float(der.get("mpap_co_slope"))
    pawp_s = _safe_float(der.get("pawp_co_slope"))
    mPAP_CO_slope = _fmt(mpap_s, 2) if mpap_s is not None else "nicht berechenbar"
    PAWP_CO_slope = _fmt(pawp_s, 2) if pawp_s is not None else "nicht berechenbar"
    if pawp_s is None:
        PAWP_CO_slope_phrase = "nicht sicher beurteilbarem PAWP/CO-Slope"
    elif pawp_s > 2.0:
        PAWP_CO_slope_phrase = "pathologisch erhöhtem PAWP/CO-Slope"
    elif pawp_s >= 1.5:
        PAWP_CO_slope_phrase = "grenzwertigem PAWP/CO-Slope"
    else:
        PAWP_CO_slope_phrase = "nicht führend erhöhtem PAWP/CO-Slope"

    hemo_cat = str(der.get("hemo_category") or "")
    if mpap is not None and mpap <= 20:
        rest_ph_sentence = "keine pulmonale Hypertonie in Ruhe"
    elif hemo_cat == "precap":
        rest_ph_sentence = "präkapilläre pulmonale Hypertonie in Ruhe"
    elif hemo_cat == "ipcph":
        rest_ph_sentence = "postkapilläre pulmonale Hypertonie in Ruhe"
    elif hemo_cat == "cpcph":
        rest_ph_sentence = "kombinierte prä- und postkapilläre pulmonale Hypertonie in Ruhe"
    else:
        rest_ph_sentence = "mPAP-Erhöhung ohne sichere präkapilläre Konstellation in Ruhe"

    if hemo_cat in ("high_flow_or_borderline", "ph_unclassified"):
        borderline_ph_sentence = "nicht-präkapilläre oder unklassifizierte pulmonale Druckerhöhung"
    elif mpap is not None and mpap <= 20:
        borderline_ph_sentence = "keine pulmonale Hypertonie in Ruhe"
    else:
        borderline_ph_sentence = "pulmonale Druckerhöhung"

    if pvr is not None and pvr >= 8:
        severity_ph_sentence = "schwergradige präkapilläre PH"
    elif pvr is not None and pvr >= 5:
        severity_ph_sentence = "mittelgradige präkapilläre PH"
    elif pvr is not None and pvr > 2:
        severity_ph_sentence = "milde bis mittelgradige präkapilläre PH"
    else:
        severity_ph_sentence = "pulmonale Druckerhöhung ohne ausgeprägte Widerstandskomponente"

    risk_profile_desc = "nicht sicher klassifiziertes Risikoprofil"
    esc4 = str(sc.get("esc_ers_4s") or "").strip().lower()
    esc_map = {
        "low": "niedriges",
        "intermediate-low": "intermediär-niedriges",
        "intermediate-high": "intermediär-hohes",
        "high": "hohes",
        "niedrig": "niedriges",
        "intermediär": "intermediäres",
        "hoch": "hohes",
    }
    if esc4 in esc_map:
        risk_profile_desc = f"{esc_map[esc4]} Risikoprofil"
    else:
        rc = str(der.get("risk_category") or "").strip().lower()
        rc_map = {"low": "niedriges", "intermediate": "intermediäres", "high": "hohes"}
        if rc in rc_map:
            risk_profile_desc = f"{rc_map[rc]} Risikoprofil"

    eps = der.get("ph_tx_episodes") or []
    current_meds: List[str] = []
    planned_meds: List[str] = []
    if isinstance(eps, list):
        for e in eps:
            if not isinstance(e, dict):
                continue
            drug = str(e.get("drug") or "").strip()
            st = str(e.get("status") or "").strip().lower()
            if not drug or not st:
                continue
            if st == "aktuell":
                current_meds.append(drug)
            elif st == "geplant":
                planned_meds.append(drug)
    current_meds = list(dict.fromkeys(current_meds))
    planned_meds = list(dict.fromkeys(planned_meds))

    therapy_current_desc = (
        "bestehender PH-spezifischer Therapie"
        + (f" ({', '.join(current_meds[:3])})" if current_meds else "")
    )
    if planned_meds:
        therapy_plan_sentence = "Geplante PH-spezifische Therapie: " + ", ".join(planned_meds[:3]) + "."
        therapy_escalation_sentence = (
            "Therapieeskalation vorgesehen ("
            + ", ".join(planned_meds[:3])
            + "); engmaschige klinische und laborchemische Verlaufskontrollen empfohlen."
        )
    elif current_meds:
        therapy_plan_sentence = "Fortführung und ggf. strukturierte Anpassung der aktuellen PH-spezifischen Therapie."
        therapy_escalation_sentence = (
            "Bei persistierender Symptomlast oder hohem Risiko Therapieeskalation im spezialisierten PH-Setting prüfen."
        )
    else:
        therapy_plan_sentence = "PH-spezifische Therapieentscheidung nach gesicherter Ätiologie und individueller Nutzen-Risiko-Abwägung."
        therapy_escalation_sentence = "Therapieeskalation im spezialisierten PH-Setting prüfen und zeitnah reevaluieren."
    therapy_neutral_sentence = (
        "PH-spezifische Therapie nur nach gesicherter Ätiologie und individueller Indikationsprüfung."
    )

    anticoag_status = str(ui.get("anticoag_status") or "").strip().lower()
    anticoag_sub = str(ui.get("anticoag_substance") or "").strip()
    anticoag_ind = str(ui.get("anticoag_indication") or "").strip()
    if anticoag_status in ("ja", "yes", "true"):
        anticoagulation_plan_sentence = (
            "Antikoagulation ist bereits etabliert"
            + (f" ({anticoag_sub})" if anticoag_sub else "")
            + "; Fortführung gemäß Indikation und Blutungs-/Thromboserisiko."
        )
    elif anticoag_status in ("nein", "no", "false"):
        anticoagulation_plan_sentence = "Antikoagulationsstrategie indikationsbezogen zeitnah prüfen."
    else:
        anticoagulation_plan_sentence = "Antikoagulationsstatus klären und Strategie indikationsbezogen festlegen."

    cteph_bits: List[str] = []
    if bool(ui.get("vq_defect")):
        cteph_bits.append("segmentalen Perfusionsdefekten")
    if bool(ui.get("ct_embolie")):
        cteph_bits.append("CT-Hinweisen auf chronische Embolie")
    if bool(ui.get("ct_mosaic")):
        cteph_bits.append("Mosaikperfusion")
    if not cteph_bits:
        vq_desc = str(ui.get("vq_desc") or "").strip()
        if vq_desc:
            cteph_bits.append(vq_desc)
    cteph_context_desc = ", ".join(cteph_bits) if cteph_bits else "klinischem und bildgebendem Kontext"
    vte_context_desc = cteph_context_desc if cteph_bits else "klinischem VTE-/Bildgebungskontext"

    ctd_desc = str(ui.get("ph_known_subtype") or "").strip()
    if not ctd_desc:
        known_dx = str(ui.get("ph_known_dx") or "").strip()
        if any(tok in known_dx.lower() for tok in ("ctd", "kollagen", "skleroderm", "crest")):
            ctd_desc = known_dx
    if not ctd_desc:
        ctd_desc = "möglicher CTD-/Kollagenose-Konstellation"

    lufu_bits: List[str] = []
    if bool(ui.get("lufu_obstructive")):
        lufu_bits.append("obstruktivem Muster")
    if bool(ui.get("lufu_restrictive")):
        lufu_bits.append("restriktivem Muster")
    if bool(ui.get("lufu_diffusion")):
        lufu_bits.append("Diffusionsstörung")
    dlco = _safe_float(ui.get("dlco_sb"))
    if dlco is not None and dlco < 60:
        lufu_bits.append(f"DLCO {_fmt(dlco,0)}%")
    if lufu_bits:
        lufu_context_sentence = "Lungenfunktion mit " + ", ".join(lufu_bits) + "."
    else:
        lufu_context_sentence = "Lungenfunktion/DLCO im Verlauf je nach klinischem Kontext ergänzen."

    pref_raw = str(ui.get("patient_preference") or "").strip()
    patient_preference_sentence = (
        f"Patient*innenpräferenz: {pref_raw}."
        if pref_raw
        else "Patient*innenpräferenz und Shared Decision Making im weiteren Vorgehen berücksichtigen."
    )

    vaso_agent = str(ui.get("vaso_agent") or ui.get("vaso_substance") or "iNO").strip()
    vasoreactivity_agent_desc = vaso_agent if vaso_agent else "iNO"
    iNO_response_desc = str(ui.get("vaso_response_desc") or "").strip() or "keine relevante Drucksenkung"

    volume_ml = _safe_float(ui.get("volume_ml"))
    infusion_type = str(ui.get("infusion_type") or "NaCl").strip()
    volume_challenge_desc = (
        (f"{_fmt(volume_ml,0)} ml {infusion_type}" if volume_ml is not None else infusion_type)
        if der.get("volume_challenge_done")
        else "Volumenchallenge"
    )
    volume_response_sentence = str(der.get("vol_challenge_resp") or "").strip()
    if not volume_response_sentence and der.get("volume_challenge_done"):
        volume_response_sentence = "kein klarer PAWP-Anstieg"

    V_wave_desc = "prominenter V-Welle" if bool(der.get("v_wave")) else "ohne prominente V-Welle"
    step_loc = str(der.get("step_up_location") or "").strip().lower()
    step_up_location_desc = {
        "atrial": "auf Vorhofebene",
        "ventricular": "auf Ventrikelebene",
        "pulmonary": "auf Pulmonalarterienebene",
    }.get(step_loc, str(der.get("step_up_from_to") or "").strip())

    measure_bits: List[str] = []
    if str(ui.get("co_method") or "").strip() == "":
        measure_bits.append("fehlender CO-Methode")
    if str(der.get("exercise_interpretability") or "") in ("hard_stop", "numeric_only"):
        measure_bits.append("eingeschränkter Belastungs-Interpretierbarkeit")
    if bool(ui.get("atrial_fib")):
        measure_bits.append("Vorhofflimmern")
    if bool(ui.get("wedge_v_wave")) or bool(ui.get("wedge_a_wave")):
        measure_bits.append("Wedge-Wellen")
    measurement_limitations = ", ".join(measure_bits)
    measurement_limitation_sentence = (
        f"Hinweis auf eingeschränkte Messqualität/Interpretierbarkeit aufgrund von {measurement_limitations}."
        if measurement_limitations
        else ""
    )

    PAWP_pre = _fmt(der.get("vol_challenge_pawp_pre"), 0) if der.get("vol_challenge_pawp_pre") is not None else "nicht angegeben"
    PAWP_post = _fmt(der.get("vol_challenge_pawp_post"), 0) if der.get("vol_challenge_pawp_post") is not None else "nicht angegeben"
    mPAP_pre = _fmt(_safe_float(ui.get("mpap_pre")), 0) if _safe_float(ui.get("mpap_pre")) is not None else "nicht angegeben"
    mPAP_post = _fmt(_safe_float(ui.get("mpap_post")), 0) if _safe_float(ui.get("mpap_post")) is not None else "nicht angegeben"

    oxygen_flow = _safe_float(ui.get("oxygen_flow_l_min")) or _safe_float(ui.get("ltot_flow_l_min"))
    oxygen_desc = (
        f"Sauerstoffgabe {_fmt(oxygen_flow,1)} l/min" if oxygen_flow is not None else "Raumluft"
    )
    oxygenation_status = "Normoxämie" if str(ui.get("oxygen_mode") or "") in ("keine", "LTOT", "O2") else "nicht sicher einzuordnen"
    bp_status = "stabil" if sbp is not None and 90 <= sbp <= 160 else "auffällig"
    hr_status_phrase = f"HF {_fmt(hr,0)}/min" if hr is not None else "HF nicht angegeben"
    rhythm_status = "Vorhofflimmern" if bool(ui.get("atrial_fib")) else "Sinusrhythmus oder nicht dokumentiert"

    perfusion_defect_desc = str(ui.get("vq_desc") or "").strip() or "kleiner Perfusionsdefekt"
    prev_date = str(ui.get("prev_rhk_date") or "").strip()
    comparison_desc = comparison_sentence or "kein valider Direktvergleich möglich"
    prev_values_desc = comparison_sentence or "keine belastbaren Vorwerte"
    current_values_desc = pressure_resistance_short

    osat = str(ui.get("anticoag_status") or "").strip()
    anticoag_context = anticoag_ind or osat or "klinischer Konstellation"
    declined_item = str(ui.get("declined_item") or ui.get("patient_preference") or "die vorgeschlagene Maßnahme").strip()
    study_sentence = "Studienevaluation je nach Ein- und Ausschlusskriterien."

    SP = _safe_float(der.get("sprime_raai"))
    sprime_raai_value = _fmt(SP, 2) if SP is not None else "nicht angegeben"
    sprime_raai_cutoff = _fmt(der.get("s_prime_raai_cutoff"), 2) if der.get("s_prime_raai_cutoff") is not None else "0,81"
    sprime_raai_interpretation_sentence = (
        "Wert unterhalb des orientierenden Cut-offs"
        if bool(der.get("s_prime_raai_low"))
        else "Wert nicht unterhalb des orientierenden Cut-offs"
    )

    delta_sPAP = _fmt(der.get("delta_spap"), 0) if der.get("delta_spap") is not None else "nicht berechenbar"
    CI_peak = _fmt(der.get("ci_peak"), 2) if der.get("ci_peak") is not None else "nicht angegeben"
    lufu_summary = str(ui.get("lufu_summary") or "").strip() or "keine strukturierten Lufu-Zusatzangaben"

    ctx = {
        **env,
        "CI_value": CI_value,
        "comparison_sentence": comparison_sentence,
        "comparison_trend": (trend_info.get("trend") if trend_info.get("has_prev") else ""),
        "comparison_table_md": comparison_table_md,
        "comparison_detail_doc": comparison_detail_doc,
        "comparison_detail_patient_md": comparison_detail_patient_md,
        "comparison_recommendation_doc": comparison_recommendation_doc,
        "comparison_recommendation_patient": comparison_recommendation_patient,
        "liver_ph_profile_label": der.get("liver_ph_profile_label") or "Kein spezifisches Leber Profil.",
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
        "co_method_phrase": co_method_phrase,
        "cv_stauung_phrase": cv_stauung_phrase,
        "pv_stauung_phrase": pv_stauung_phrase,
        "systemic_sentence": systemic_sentence,
        "oxygen_sentence": oxygen_sentence,
        "exam_type_desc": exam_type_desc,
        "exercise_protocol_sentence": exercise_protocol_sentence,
        "left_heart_context_desc": left_heart_context_desc,
        "exercise_pattern_desc": exercise_pattern_desc,
        "provocation_sentence": provocation_sentence,
        "provocation_type_desc": provocation_type_desc,
        "provocation_result_sentence": provocation_result_sentence,
        "followup_timing_desc": followup_timing_desc,
        "invasive_followup_desc": invasive_followup_desc,
        "valve_focus_desc": valve_focus_desc,
        "anemia_context_desc": anemia_context_desc,
        "mPAP_CO_slope": mPAP_CO_slope,
        "PAWP_CO_slope": PAWP_CO_slope,
        "PAWP_CO_slope_phrase": PAWP_CO_slope_phrase,
        "rest_ph_sentence": rest_ph_sentence,
        "borderline_ph_sentence": borderline_ph_sentence,
        "severity_ph_sentence": severity_ph_sentence,
        "risk_profile_desc": risk_profile_desc,
        "therapy_current_desc": therapy_current_desc,
        "therapy_plan_sentence": therapy_plan_sentence,
        "therapy_escalation_sentence": therapy_escalation_sentence,
        "therapy_neutral_sentence": therapy_neutral_sentence,
        "anticoagulation_plan_sentence": anticoagulation_plan_sentence,
        "cteph_context_desc": cteph_context_desc,
        "vte_context_desc": vte_context_desc,
        "ctd_desc": ctd_desc,
        "lufu_context_sentence": lufu_context_sentence,
        "patient_preference_sentence": patient_preference_sentence,
        "vasoreactivity_agent_desc": vasoreactivity_agent_desc,
        "iNO_response_desc": iNO_response_desc,
        "volume_challenge_desc": volume_challenge_desc,
        "volume_response_sentence": volume_response_sentence,
        "V_wave_desc": V_wave_desc,
        "step_up_location_desc": step_up_location_desc,
        "measurement_limitation_sentence": measurement_limitation_sentence,
        "measurement_limitations": measurement_limitations,
        "PAWP_pre": PAWP_pre,
        "PAWP_post": PAWP_post,
        "mPAP_pre": mPAP_pre,
        "mPAP_post": mPAP_post,
        "O2_flow": _fmt(oxygen_flow, 1) if oxygen_flow is not None else "0",
        "oxygen_desc": oxygen_desc,
        "oxygenation_status": oxygenation_status,
        "bp_status": bp_status,
        "hr_status_phrase": hr_status_phrase,
        "rhythm_status": rhythm_status,
        "perfusion_defect_desc": perfusion_defect_desc,
        "prev_date": prev_date,
        "comparison_desc": comparison_desc,
        "prev_values_desc": prev_values_desc,
        "current_values_desc": current_values_desc,
        "anticoag_context": anticoag_context,
        "declined_item": declined_item,
        "study_sentence": study_sentence,
        "Sprime_RAAI_value": sprime_raai_value,
        "Sprime_RAAI_cutoff": sprime_raai_cutoff,
        "Sprime_RAAI_interpretation_sentence": sprime_raai_interpretation_sentence,
        "delta_sPAP": delta_sPAP,
        "CI_peak": CI_peak,
        "lufu_summary": lufu_summary,
    }

    # Legacy placeholders with conservative defaults to avoid empty fragments.
    ctx.setdefault("CI_TD", "nicht angegeben")
    ctx.setdefault("CI_Fick", "nicht angegeben")
    ctx.setdefault("fick_desc", "Fick-Methode")
    ctx.setdefault("co_discrepancy_reason", "methodischer Limitation")
    ctx.setdefault("co_method_concordance_desc", "sind nicht vollständig dokumentiert")
    ctx.setdefault("iNO_ppm", "nicht angegeben")
    ctx.setdefault("iNO_o2_desc", "")
    ctx.setdefault("iNO_responder_statement", "nicht erfüllt")
    ctx.setdefault("PAWP_value", _fmt(pawp, 0) if pawp is not None else "nicht angegeben")
    ctx.setdefault("limiting_factor_desc", "klinischer Rahmenbedingungen")
    ctx.setdefault("primary_focus_desc", "Stabilisierung und Reevaluation")
    ctx.setdefault("lung_component_extra", "")
    ctx.setdefault("infusion_type", str(ui.get("infusion_type") or "NaCl"))
    ctx.setdefault("mpap_prev", _fmt(ui.get("prev_mpap"), 0) if ui.get("prev_mpap") is not None else "n.a.")
    ctx.setdefault("mpap_now", _fmt(der.get("mpap_rest"), 0) if der.get("mpap_rest") is not None else "n.a.")
    ctx.setdefault("pawp_prev", _fmt(ui.get("prev_pawp"), 0) if ui.get("prev_pawp") is not None else "n.a.")
    ctx.setdefault("pawp_now", _fmt(der.get("pawp_rest"), 0) if der.get("pawp_rest") is not None else "n.a.")
    ctx.setdefault("ci_prev", _fmt(ui.get("prev_ci"), 2) if ui.get("prev_ci") is not None else "n.a.")
    ctx.setdefault("ci_now", _fmt(der.get("ci_rest"), 2) if der.get("ci_rest") is not None else "n.a.")
    ctx.setdefault("pvr_prev", _fmt(ui.get("prev_pvr"), 2) if ui.get("prev_pvr") is not None else "n.a.")
    ctx.setdefault("pvr_now", _fmt(der.get("pvr_rest"), 2) if der.get("pvr_rest") is not None else "n.a.")
    ctx.setdefault("hemodynamic_course_desc", "einen im Verlauf zu bewertenden hämodynamischen Verlauf")
    ctx.setdefault("pulm_workup_focus_desc", "Lungenfunktion, Bildgebung und Oxygenierung")

    return ctx


# =============================================================================
# Procedere/module rendering with "already done" filtering
# =============================================================================

def _done_flags(env: Dict[str, Any]) -> Dict[str, bool]:
    # These flags are used to remove "already done" items from module texts
    return {
        "vq": bool(env.get("vq_done")),
        "pa_angio": bool(env.get("vq_pa_angio_done")),
        "ctep_conf": bool(env.get("vq_cteph_conf_done")),
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
        if done.get("ctep_conf") and ("cteph" in l) and ("board" in l or "konferenz" in l or "konferenzbeschluss" in l):
            return True
        if done.get("pa_angio") and ("pulmonalisangiographie" in l or "pa angio" in l or "pa-" in l):
            return True
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
