#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – Report Builder (split from rhk_app_web_master.py).

Enthält:
- Arztbericht, Patientenbericht, interner Bericht
- Input-Summary, JSON Export/Import

Hinweis: Inhalt ist weitgehend 1:1 aus der Master-Datei extrahiert.
"""

from __future__ import annotations

from rhk_base import *  # noqa: F401,F403

# Einige Render-Helpers liegen im Case-Modul (im Flat-Master waren sie vorher "weiter oben").
from rhk_case import build_render_ctx, render_p01_dynamic, filter_module_text  # noqa: F401

# =============================================================================
# Befund – input summary block
# =============================================================================


def _md_kv(label: str, value: str) -> str:
    return f"- **{label}:** {value}"


def _md_section(title: str, lines: List[str]) -> str:
    """Small helper to build a Markdown section from a list of list-items."""
    if not lines:
        return ""
    return f"### {title}\n" + "\n".join(lines)


def summarize_inputs(case: Dict[str, Any]) -> str:
    """Creates a compact, structured overview of the raw input data (Markdown)."""
    ui = case.get("ui") or {}
    env = case.get("env") or {}
    der = case.get("derived") or {}

    parts: List[str] = []

    # ---------------------------------------------------------------------
    # Klinik
    # ---------------------------------------------------------------------
    klinik_lines: List[str] = []
    story = (ui.get("story") or "").strip()
    if story:
        klinik_lines.append(_md_kv("Kurz-Anamnese", story))

    # Angeborener Herzfehler / Shunt (DD Gruppe 1)
    if ui.get("chd_pos") is True:
        chd_type = ui.get("chd_type")
        chd_desc = (ui.get("chd_desc") or "").strip()
        txt = "ja"
        if chd_type:
            txt += f" ({chd_type})"
        if chd_desc:
            txt += f" – {chd_desc}"
        klinik_lines.append(_md_kv("Angeborener Herzfehler/Shunt", txt))

    # Virologie/Infektiologie (z.B. HIV; DD Gruppe 1)
    if ui.get("virology_pos") is True:
        items = ui.get("virology_items")
        desc = (ui.get("virology_desc") or "").strip()
        parts: List[str] = []
        if isinstance(items, list) and items:
            parts.append(", ".join([str(x) for x in items if str(x).strip()]))
        elif isinstance(items, str) and items.strip():
            parts.append(items.strip())
        if desc:
            parts.append(desc)
        klinik_lines.append(_md_kv("Virologie/Infektiologie", " / ".join(parts) if parts else "positiv"))

    # Immunologie/Autoimmun (z.B. CTD; DD Gruppe 1)
    if ui.get("immunology_pos") is True:
        items = ui.get("immunology_items")
        desc = (ui.get("immunology_desc") or "").strip()
        parts = []
        if isinstance(items, list) and items:
            parts.append(", ".join([str(x) for x in items if str(x).strip()]))
        elif isinstance(items, str) and items.strip():
            parts.append(items.strip())
        if desc:
            parts.append(desc)
        klinik_lines.append(_md_kv("Immunologie/Autoimmun", " / ".join(parts) if parts else "positiv"))

    # Genetik/Mutation (DD Gruppe 1)
    if ui.get("mutation_pos") is True:
        items = ui.get("mutation_items")
        desc = (ui.get("mutation_desc") or "").strip()
        parts = []
        if isinstance(items, list) and items:
            parts.append(", ".join([str(x) for x in items if str(x).strip()]))
        elif isinstance(items, str) and items.strip():
            parts.append(items.strip())
        if desc:
            parts.append(desc)
        klinik_lines.append(_md_kv("Genetik/Mutation", " / ".join(parts) if parts else "positiv"))

    if ui.get("ph_known") is True:
        klinik_lines.append(_md_kv("PH-Diagnose", "bekannt"))

        # Details zur bekannten PH (falls angegeben)
        dx = (ui.get("ph_known_dx") or "").strip()
        if dx:
            klinik_lines.append(_md_kv("Bekannte PH-Diagnose", dx))

        first_dx = (ui.get("ph_first_dx") or "").strip()
        if first_dx:
            klinik_lines.append(_md_kv("Erstdiagnose", first_dx))

        reason = (ui.get("ph_reason_rhk") or "").strip()
        if reason:
            klinik_lines.append(_md_kv("Aktueller Anlass", reason))

        subtype = (ui.get("ph_known_subtype") or "").strip()
        if subtype:
            klinik_lines.append(_md_kv("Subtyp/Kontext", subtype))

        cur_meds = ui.get("ph_current_meds") or []
        if isinstance(cur_meds, list) and cur_meds:
            klinik_lines.append(_md_kv("Aktuelle Therapie", ", ".join([str(x) for x in cur_meds])))

        prev_meds = ui.get("ph_prev_meds") or []
        if isinstance(prev_meds, list) and prev_meds:
            klinik_lines.append(_md_kv("Frühere Therapie", ", ".join([str(x) for x in prev_meds])))

        interv = ui.get("ph_interventions") or []
        if isinstance(interv, list) and interv:
            klinik_lines.append(_md_kv("Interventionen", ", ".join([str(x) for x in interv])))

    elif ui.get("ph_suspected") is True:
        klinik_lines.append(_md_kv("PH-Verdachtsdiagnose", "ja"))

    # Vitals
    sbp = _safe_float(ui.get("bp_sys"))
    dbp = _safe_float(ui.get("bp_dia"))
    hr = _safe_float(ui.get("hr"))
    if sbp is not None or dbp is not None:
        if sbp is not None and dbp is not None:
            klinik_lines.append(_md_kv("Blutdruck", f"{fmt_int(sbp)}/{fmt_int(dbp)} mmHg"))
        elif sbp is not None:
            klinik_lines.append(_md_kv("Blutdruck", f"{fmt_int(sbp)} mmHg"))
        else:
            klinik_lines.append(_md_kv("Blutdruck", f"{fmt_int(dbp)} mmHg"))
    if hr is not None:
        klinik_lines.append(_md_kv("Herzfrequenz", f"{fmt_int(hr)}/min"))

    # Symptome / Funktion
    if ui.get("exertional_dyspnea") is True:
        klinik_lines.append(_md_kv("Belastungsdyspnoe", "ja"))

    syn = ui.get("syncope")
    syn_s: Optional[str] = None
    if isinstance(syn, bool):
        syn_s = "ja" if syn else None
    else:
        tmp = (syn or "").strip()
        if tmp and tmp.lower() not in ("keine", "nein"):
            syn_s = tmp
    if syn_s:
        klinik_lines.append(_md_kv("Synkope", syn_s))

    if ui.get("hemoptysis") is True:
        klinik_lines.append(_md_kv("Hämoptyse", "ja"))
    if ui.get("dizziness") is True:
        klinik_lines.append(_md_kv("Schwindel", "ja"))

    stairs = ui.get("stairs_flights")
    if stairs not in (None, "", 0):
        klinik_lines.append(_md_kv("Treppenstufen/Etagen (Alltag)", str(stairs)))

    who_fc = ui.get("who_fc")
    if who_fc:
        klinik_lines.append(_md_kv("WHO-FC", str(who_fc)))
    six = _safe_float(ui.get("six_mwd_m"))
    if six is not None:
        klinik_lines.append(_md_kv("6MWD", f"{_fmt(six,0)} m"))



    # Medikation / Zusatzangaben (falls erfasst)
    anticoag_status = (ui.get("anticoag_status") or "").strip()
    if anticoag_status:
        msg = anticoag_status
        if anticoag_status.lower() == "ja":
            bits: List[str] = []
            sub = (ui.get("anticoag_substance") or "").strip()
            ind = (ui.get("anticoag_indication") or "").strip()
            since = (ui.get("anticoag_since") or "").strip()
            if sub:
                bits.append(sub)
            if ind:
                bits.append(f"Indikation: {ind}")
            if since:
                bits.append(f"seit {since}")
            if bits:
                msg += " (" + "; ".join(bits) + ")"
        klinik_lines.append(_md_kv("Antikoagulation", msg))

    note = (ui.get("anticoag_note") or "").strip()
    if note:
        klinik_lines.append(_md_kv("Antikoagulation – Bem.", note))

    antif_status = (ui.get("antifibrotic_status") or "").strip()
    if antif_status:
        msg = antif_status
        if antif_status.lower() == "ja":
            bits: List[str] = []
            drug = (ui.get("antifibrotic_drug") or "").strip()
            since = (ui.get("antifibrotic_since") or "").strip()
            if drug:
                bits.append(drug)
            if since:
                bits.append(f"seit {since}")
            if bits:
                msg += " (" + "; ".join(bits) + ")"
        klinik_lines.append(_md_kv("Antifibrotische Therapie", msg))

    antif_note = (ui.get("antifibrotic_note") or "").strip()
    if antif_note:
        klinik_lines.append(_md_kv("Antifibrotika – Bem.", antif_note))

    ltx = (ui.get("ltx_eval") or "").strip()
    if ltx:
        extra = ""
        ltx_date = (ui.get("ltx_eval_date") or "").strip()
        if ltx_date:
            extra = f" (Datum: {ltx_date})"
        klinik_lines.append(_md_kv("LTX-Evaluation", f"{ltx}{extra}"))

    if not klinik_lines:
        klinik_lines.append("Keine klinischen Angaben erfasst.")

    parts.append(_md_section("Klinik", klinik_lines))

    # ---------------------------------------------------------------------
    # Labor (Fließtext; BNP/NT-proBNP separat)
    # ---------------------------------------------------------------------
    lab_items: List[str] = []
    lab_tail_lines: List[str] = []

    hb = _safe_float(ui.get("hb_g_dl"))
    if hb is not None:
        lab_items.append(f"Hb: {_fmt(hb,1)} g/dl" + (" (Anämie)" if der.get("anemia") else ""))

    crp = _safe_float(ui.get("crp_mg_l"))
    if crp is not None:
        lab_items.append(f"CRP: {_fmt(crp,1)} mg/l")

    crea = _safe_float(ui.get("creatinine_mg_dl"))
    if crea is not None:
        lab_items.append(f"Kreatinin: {_fmt(crea,2)} mg/dl")

    egfr = _safe_float(ui.get("egfr"))
    if egfr is not None:
        lab_items.append(f"eGFR: {fmt_int(egfr)} ml/min/1,73m²")

    inr = _safe_float(ui.get("inr"))
    if inr is not None:
        lab_items.append(f"INR: {_fmt(inr,2)}")

    ptt = _safe_float(ui.get("ptt_s"))
    if ptt is not None:
        lab_items.append(f"PTT: {_fmt(ptt,0)} s")

    thr = _safe_float(ui.get("platelets_g_l"))
    if thr is not None:
        lab_items.append(f"Thrombozyten: {_fmt(thr,0)} G/l")

    leuk = _safe_float(ui.get("leukocytes_g_l"))
    if leuk is not None:
        lab_items.append(f"Leukozyten: {_fmt(leuk,1)} G/l")

    # BNP/NT-proBNP bewusst separat unter dem Fließtext
    bnp_kind = ui.get("bnp_kind")
    bnp_val = _safe_float(ui.get("bnp_value"))
    if bnp_val is not None:
        extra = ""
        if ui.get("entresto") is True and isinstance(bnp_kind, str) and "BNP" in bnp_kind.upper() and "NT" not in bnp_kind.upper():
            extra = " (Hinweis: unter ARNI ist NT-proBNP typischerweise besser verwertbar)"
        lab_tail_lines.append(f"**{str(bnp_kind or 'BNP/NT-proBNP')}:** {_fmt(bnp_val,0)} pg/ml{extra}")

    cong_org = ui.get("congestive_organopathy")
    if isinstance(cong_org, str) and cong_org.lower().startswith("ja"):
        lab_tail_lines.append("Hinweis auf congestive Organopathie: ja")
    elif isinstance(cong_org, str) and cong_org.lower().startswith("nein"):
        lab_tail_lines.append("Hinweis auf congestive Organopathie: nein")

    lab_flow = "; ".join(lab_items) if lab_items else "Keine Laborwerte erfasst."
    lab_section = "### Labor\n" + lab_flow
    if lab_tail_lines:
        lab_section += "\n\n" + "\n".join(lab_tail_lines)

    parts.append(lab_section)

    # ---------------------------------------------------------------------
    # Bildgebung / Echo / CMR
    # ---------------------------------------------------------------------
    img_lines: List[str] = []

    if ui.get("ct_done"):
        findings = []
        for key, lab in [
            ("ct_ild", "ILD"),
            ("ct_emphysema", "Emphysem"),
            ("ct_embolie", "Embolie"),
            ("ct_mosaic", "Mosaikperfusion"),
            ("ct_koronarkalk", "Koronarkalk"),
        ]:
            if ui.get(key):
                findings.append(lab)
        if findings:
            img_lines.append(_md_kv("CT Thorax/Angio", ", ".join(findings)))
        else:
            img_lines.append(_md_kv("CT Thorax/Angio", "durchgeführt (keine pathologischen Befunde angegeben)"))
    else:
        img_lines.append(_md_kv("CT Thorax/Angio", "nicht angegeben"))

    if ui.get("vq_done"):
        vq_abn = "pathologisch" if ui.get("vq_defect") else "unauffällig/keine Defekte angegeben"
        img_lines.append(_md_kv("V/Q", vq_abn))
        vq_desc = (ui.get("vq_desc") or "").strip()
        if vq_desc:
            img_lines.append(_md_kv("V/Q Details", vq_desc))

    # Echo
    if ui.get("echo_done") or any(ui.get(k) not in (None, "", False) for k in ["lvef", "la_enlarged", "ee_ratio", "pasp_echo"]):
        echo_bits: List[str] = []
        lvef = _safe_float(ui.get("lvef"))
        if lvef is not None:
            echo_bits.append(f"LVEF {_fmt(lvef,0)}%")
        if ui.get("la_enlarged"):
            echo_bits.append("LA erweitert")
        ee = _safe_float(ui.get("ee_ratio"))
        if ee is not None:
            echo_bits.append(f"E/e' {_fmt(ee,1)}")
        pasp = _safe_float(ui.get("pasp_echo"))
        if pasp is not None:
            echo_bits.append(f"sPAP {_fmt(pasp,0)} mmHg")
        tapse = _safe_float(ui.get("tapse_mm"))
        if tapse is not None:
            echo_bits.append(f"TAPSE {_fmt(tapse,0)} mm")
        if der.get("tapse_spap") is not None:
            echo_bits.append(f"TAPSE/sPAP {_fmt(der.get('tapse_spap'),2)}")
        sprime = _safe_float(ui.get("s_prime_cm_s"))
        if sprime is not None:
            echo_bits.append(f"S' {_fmt(sprime,1)} cm/s")
        raesa = _safe_float(ui.get("ra_esa_cm2"))
        if raesa is not None:
            echo_bits.append(f"RA ESA {_fmt(raesa,0)} cm²")
        if der.get("raai") is not None:
            echo_bits.append(f"RAAI {_fmt(der.get('raai'),1)} cm²/m²")
        if der.get("s_prime_raai") is not None:
            echo_bits.append(f"S'/RAAI {_fmt(der.get('s_prime_raai'),2)}")
        ivcd = _safe_float(ui.get("ivc_diam_mm"))
        if ivcd is not None:
            echo_bits.append(f"IVC {_fmt(ivcd,0)} mm")
        ivcc = ui.get("ivc_collapse")
        if isinstance(ivcc, str) and ivcc:
            echo_bits.append(f"IVC Kollaps: {ivcc}")

        if echo_bits:
            img_lines.append(_md_kv("Echo", ", ".join(echo_bits)))
        else:
            img_lines.append(_md_kv("Echo", "durchgeführt (keine Details angegeben)"))

        echo_flags: List[str] = []
        if der.get("s_prime_raai_low") is True:
            echo_flags.append("S'/RAAI erniedrigt (<0,81)")
        if der.get("tapse_spap_reduced") is True:
            lbl = "TAPSE/sPAP vermindert"
            if der.get("tapse_spap_risk") == "hoch":
                lbl += " (hochgradig)"
            elif der.get("tapse_spap_risk") == "intermediär":
                lbl += " (mäßig)"
            echo_flags.append(lbl)
        if echo_flags:
            img_lines.append(_md_kv("Echo Zusatz", "; ".join(echo_flags)))

    # CMR
    if ui.get("cmr_done") or any(ui.get(k) not in (None, "", False) for k in ["rvef", "rvesvi"]):
        cmr_bits: List[str] = []
        rvef = _safe_float(ui.get("rvef"))
        if rvef is not None:
            cmr_bits.append(f"RVEF {_fmt(rvef,0)}%")
        rvesvi = _safe_float(ui.get("rvesvi"))
        if rvesvi is not None:
            cmr_bits.append(f"RVESVi {_fmt(rvesvi,0)} ml/m²")
        if cmr_bits:
            img_lines.append(_md_kv("CMR", ", ".join(cmr_bits)))
        else:
            img_lines.append(_md_kv("CMR", "durchgeführt (keine Details angegeben)"))

    if not img_lines:
        img_lines.append("Keine Bildgebung oder Echo oder CMR Angaben erfasst.")

    parts.append(_md_section("Bildgebung / Echo / CMR", img_lines))

    # ---------------------------------------------------------------------
    # Lungenfunktion (Fließtext; Kommentar separat)
    # ---------------------------------------------------------------------
    if ui.get("lufu_done"):
        phen: List[str] = []
        if ui.get("lufu_obstructive"):
            phen.append("obstruktiv")
        if ui.get("lufu_restrictive"):
            phen.append("restriktiv")
        if ui.get("lufu_diffusion"):
            phen.append("Diffusionsstörung")

        lufu_items: List[str] = []
        if phen:
            lufu_items.append("Phänotyp: " + ", ".join(phen))

        fev1 = _safe_float(ui.get("fev1_l"))
        fvc = _safe_float(ui.get("fvc_l"))

        if fev1 is not None:
            lufu_items.append(f"FEV1: {_fmt(fev1,2)} l")
        if fvc is not None:
            lufu_items.append(f"FVC: {_fmt(fvc,2)} l")

        # Tiffeneau-Index (FEV1/FVC)
        if fev1 is not None and fvc is not None and fvc > 0:
            tiff = fev1 / fvc
            lufu_items.append(f"Tiffeneau (FEV1/FVC): {_fmt(tiff,2)}")

        dlco = _safe_float(ui.get("dlco_sb"))
        if dlco is not None:
            lufu_items.append(f"DLCO: {_fmt(dlco,1)}")

        dlco_va = _safe_float(ui.get("dlco_va"))
        if dlco_va is not None:
            lufu_items.append(f"DLCO/VA: {_fmt(dlco_va,2)}")

        rv = _safe_float(ui.get("residual_volume_l"))
        if rv is not None:
            lufu_items.append(f"Residualvolumen (RV): {_fmt(rv,2)} l")

        lufu_flow = "; ".join(lufu_items) if lufu_items else "Lungenfunktion durchgeführt (Details nicht angegeben)."
        lufu_section = "### Lungenfunktion\n" + lufu_flow

        summ = (ui.get("lufu_summary") or "").strip()
        if summ:
            lufu_section += "\n\n**Kommentar:** " + summ

        parts.append(lufu_section)
    else:
        parts.append("### Lungenfunktion\nKeine Lungenfunktion erfasst.")

    # Join sections
    return "\n\n".join([p for p in parts if p]).strip()


# =============================================================================
# Doctor report (Markdown)
# =============================================================================

def build_doctor_report(case: Dict[str, Any], blocks: Dict[str, TextBlock]) -> str:
    ui = case["ui"]
    der = case["derived"]
    sc = case["scores"]
    dec = case["decision"]
    env = case["env"]

    ctx = build_render_ctx(case)

    # Bundle blocks
    b_id = f"{dec['bundle']}_B"
    e_id = f"{dec['bundle']}_E"
    beurteilung = render_block(blocks[b_id], ctx) if b_id in blocks else f"[Fehlender Textblock: {b_id}]"
    # --- Dynamische Ergänzungen (Zahlen/Fakten) ---
    extra_lines: List[str] = []
    # systemische Hämodynamik / Oxygenierung (falls im Textblock nicht enthalten)
    if ctx.get("systemic_sentence") and "System" not in beurteilung:
        extra_lines.append(ctx["systemic_sentence"].strip())
    if ctx.get("oxygen_sentence") and "ox" not in beurteilung.lower():
        extra_lines.append(ctx["oxygen_sentence"].strip())

    # numerische Ruhehämodynamik
    if der:
        rest_bits = []
        if der.get("mpap_rest") is not None: rest_bits.append(f"mPAP {fmt_int(der['mpap_rest'])} mmHg")
        if der.get("pawp_rest") is not None: rest_bits.append(f"PAWP {fmt_int(der['pawp_rest'])} mmHg")
        if der.get("rap_rest") is not None: rest_bits.append(f"RAP {fmt_int(der['rap_rest'])} mmHg")
        if der.get("ci_rest") is not None: rest_bits.append(f"CI {fmt_float(der['ci_rest'], 2)} l/min/m²")
        if der.get("hr_rest") is not None: rest_bits.append(f"HF {fmt_int(der['hr_rest'])}/min")
        if der.get("sv_rest_ml") is not None: rest_bits.append(f"SV {fmt_int(der['sv_rest_ml'])} ml")
        if der.get("svi_rest_ml_m2") is not None: rest_bits.append(f"SVI {fmt_int(der['svi_rest_ml_m2'])} ml/m²")
        if der.get("pp_pa_rest") is not None: rest_bits.append(f"PP (PA) {fmt_int(der['pp_pa_rest'])} mmHg")
        if der.get("pac_rest_ml_per_mmhg") is not None: rest_bits.append(f"PAC {fmt_int(der['pac_rest_ml_per_mmhg'])} ml/mmHg")
        if der.get("rc_time_rest_s") is not None: rest_bits.append(f"RC-Zeit {fmt_float(der['rc_time_rest_s'], 2)} s")
        if der.get("pvr_rest") is not None: rest_bits.append(f"PVR {fmt_float(der['pvr_rest'], 2)} WU")
        if der.get("tpg_rest") is not None: rest_bits.append(f"TPG {fmt_int(der['tpg_rest'])} mmHg")
        if rest_bits and "mPAP" not in beurteilung:
            extra_lines.append("Ruhehämodynamik: " + ", ".join(rest_bits) + ".")

    # Belastung
    if der and der.get("exercise_done"):
        if ctx.get("exercise_protocol_sentence"):
            extra_lines.append(ctx["exercise_protocol_sentence"].strip())
        mpap_s = der.get("mpap_co_slope")
        pawp_s = der.get("pawp_co_slope")
        if mpap_s is not None or pawp_s is not None:
            s_bits = []
            if mpap_s is not None: s_bits.append(f"mPAP/CO-Slope {fmt_float(mpap_s, 2)} mmHg/(L/min)")
            if pawp_s is not None: s_bits.append(f"PAWP/CO-Slope {fmt_float(pawp_s, 2)} mmHg/(L/min)")
            extra_lines.append("Belastungshämodynamik: " + " / ".join(s_bits) + ".")
        d_spap = der.get("delta_spap_peak_rest")
        if d_spap is not None:
            extra_lines.append(f"ΔsPAP (Peak–Ruhe): {fmt_int(d_spap)} mmHg.")
        peak_ci = der.get("peak_ci")
        if peak_ci is not None:
            extra_lines.append(f"Peak CI: {fmt_float(peak_ci, 2)} l/min/m².")
        patt_desc = ctx.get("exercise_pattern_desc") or ""
        if patt_desc:
            extra_lines.append(f"Belastungsmuster: {patt_desc}.")

    # Vergleich (wenn vorhanden, aber im Textblock nicht schon enthalten)
    if ctx.get("comparison_sentence") and "Im Vergleich" not in beurteilung:
        extra_lines.append(ctx["comparison_sentence"].strip())

    if extra_lines:
        beurteilung = (beurteilung.rstrip() + "\n\n" + "\n".join(extra_lines)).strip()

    empfehlung = render_block(blocks[e_id], ctx) if e_id in blocks else f"[Fehlender Textblock: {e_id}]"

    # RHK structured section
    rest_line = f"- sPAP {_fmt(ui.get('spap_rest'),0)} / dPAP {_fmt(ui.get('dpap_rest'),0)} / mPAP {_fmt(der.get('mpap'),0)} mmHg\n" \
                f"- PAWP {_fmt(ui.get('pawp_rest'),0)} mmHg, RAP {_fmt(ui.get('rap_rest'),0)} mmHg\n" \
                f"- CO {_fmt(der.get('co'),2)} l/min, CI {_fmt(der.get('ci'),2)} l/min/m²\n" \
                f"- PVR {_fmt(der.get('pvr'),1)} WU (PVRi {_fmt(der.get('pvri'),1)} WU·m²), TPG {_fmt(der.get('tpg'),0)} mmHg, DPG {_fmt(der.get('dpg'),0)} mmHg"

    exercise_block = ""
    if der.get("exercise_done"):
        ex_lines = []
        ex_lines.append(_md_kv("mPAP/CO-Slope", f"{_fmt(der.get('mpap_co_slope'),1)} WU"))
        ex_lines.append(_md_kv("PAWP/CO-Slope", f"{_fmt(der.get('pawp_co_slope'),1)} WU"))
        ex_lines.append(_md_kv("ΔsPAP (Peak–Ruhe)", f"{_fmt(der.get('delta_spap'),0)} mmHg"))
        ex_lines.append(_md_kv("peak CI", f"{_fmt(der.get('ci_peak'),2)} l/min/m²"))
        if der.get("adaptation_type"):
            ex_lines.append(_md_kv("Adaptionstyp", "homeometrisch" if der["adaptation_type"] == "homeometric" else "heterometrisch"))
        if der.get("exercise_pattern"):
            ex_lines.append(_md_kv("Belastungsmuster", describe_exercise_pattern(der.get("exercise_pattern"))))
        exercise_block = "#### Belastungshämodynamik\n" + "\n".join(ex_lines)

    volume_block = ""
    if der.get("volume_challenge_done"):
        vol_lines = []
        vol_lines.append(_md_kv("PAWP (Δ)", f"{_fmt(der.get('pawp_delta'),0)} mmHg"))
        vol_lines.append(_md_kv("mPAP (Δ)", f"{_fmt(der.get('mpap_delta'),0)} mmHg"))
        volume_block = "#### Volumenchallenge\n" + "\n".join(vol_lines)

    vaso_block = ""
    if der.get("vaso_test_done"):
        vaso_lines = []
        vaso_lines.append(_md_kv("Agent", str(ui.get("vaso_agent") or "—")))
        if ui.get("vaso_response_desc"):
            vaso_lines.append(_md_kv("Antwort", str(ui.get("vaso_response_desc"))))
        vaso_block = "#### Vasoreaktivität\n" + "\n".join(vaso_lines)

    stepox_block = ""
    if any(_safe_float(ui.get(k)) is not None for k in ["sat_svc", "sat_ivc", "sat_ra", "sat_rv", "sat_pa", "sat_ao"]):
        sat_lines = []
        for k, lab in [("sat_svc", "SVC"), ("sat_ivc", "IVC"), ("sat_ra", "RA"), ("sat_rv", "RV"), ("sat_pa", "PA"), ("sat_ao", "AO")]:
            v = _safe_float(ui.get(k))
            if v is not None:
                sat_lines.append(_md_kv(lab, f"{_fmt(v,0)}%"))
        sat_lines.append(_md_kv("Interpretation", der.get("step_up_sentence") or "—"))
        stepox_block = "#### Stufenoxymetrie\n" + "\n".join(sat_lines)

    curve_block = ""
    curve_flags = []
    if der.get("v_wave"):
        curve_flags.append("V-Welle (PAWP)")
    if der.get("a_wave"):
        curve_flags.append("A-Welle (PAWP)")
    if der.get("rap_a_wave_flag"):
        curve_flags.append("A-Welle (RAP)")
    if der.get("rap_v_wave_flag"):
        curve_flags.append("V-Welle (RAP)")
    if der.get("rv_pseudo_dip_flag"):
        curve_flags.append("Pseudo-Dip (RV)")
    if der.get("rv_dip_plateau_flag"):
        curve_flags.append("Dip-Plateau (RV)")
    if curve_flags:
        curve_block = "#### Kurvenmorphologie\n" + "\n".join([_md_kv("Befund", ", ".join(curve_flags))])

    # Risk lines (prominent, directly after dx)
    risk_lines = []
    if sc.get("esc_ers_4s"):
        risk_lines.append(_md_kv("ESC/ERS 4-Strata", sc["esc_ers_4s"]))
    if sc.get("esc_ers_3s"):
        risk_lines.append(_md_kv("ESC/ERS 3-Strata", sc["esc_ers_3s"]))
    if sc.get("reveal_lite2"):
        cat = sc.get("reveal_lite2")
        pts = sc.get("reveal_lite2_points")
        if cat == "nicht berechenbar":
            missing = sc.get("reveal_lite2_missing") or []
            miss_txt = ", ".join(missing) if missing else "Parameter unvollständig"
            risk_lines.append(_md_kv("REVEAL Lite 2", f"nicht berechenbar (fehlend: {miss_txt})"))
        else:
            cat_de = {"low": "niedrig", "intermediate": "intermediär", "high": "hoch"}.get(str(cat), str(cat))
            pts_txt = str(pts) if pts is not None else "—"
            risk_lines.append(_md_kv("REVEAL Lite 2", f"{pts_txt} Punkte ({cat_de})"))
    if der.get("hfpef_category"):
        risk_lines.append(_md_kv("HFpEF (H2FPEF)", f"{der['hfpef_category']} (~{_fmt(der.get('hfpef_percent'),0)}%)"))
    risk_block = "\n".join(risk_lines) if risk_lines else "Keine Risikostratifizierung möglich (Daten fehlen)."

    # Modules (engine + user selected) – fallbasiert sortiert + ggf. gefiltert
    selected = _normalize_module_ids(ui.get("modules") or [])
    auto_mods = _normalize_module_ids(dec.get("modules") or [])
    all_mods = list(dict.fromkeys(auto_mods + selected))

    policy = der.get("p_module_policy") or {}
    disabled_mods: Dict[str, str] = policy.get("disabled") or {}
    allowed_order: List[str] = policy.get("allowed") or list(_ALL_P_MODULE_IDS)

    skipped_mods = [m for m in all_mods if m in disabled_mods]
    all_mods = [m for m in all_mods if m not in disabled_mods]

    order_index = {mid: i for i, mid in enumerate(allowed_order)}
    all_mods = sorted(all_mods, key=lambda m: order_index.get(m, 10_000))

    modules_txts: List[str] = []
    for mid in all_mods:
        if mid == "P01":
            txt = render_p01_dynamic(env)
            modules_txts.append(f"**{mid} – {blocks.get(mid, TextBlock(mid, mid, '', 'module')).title}**\n{txt}")
            continue
        if mid in blocks:
            txt = render_block(blocks[mid], ctx)
            txt = filter_module_text(txt, env)
            if txt:
                modules_txts.append(f"**{mid} – {blocks[mid].title}**\n{txt}")

    recs = dec.get("recommendations") or []
    # Verlaufskonsequenz (falls Vor-RHK angegeben)
    tr_rec = (ctx.get("comparison_recommendation_doc") or "").strip()
    if tr_rec and (tr_rec not in recs):
        recs = list(recs) + [tr_rec]



    # Concluding sentence (kann multifaktoriell sein)
    eti = der.get("ph_etiology") if isinstance(der, dict) else None
    concluding = ""
    if isinstance(eti, dict) and str(eti.get("doc_conclusion") or "").strip():
        concluding = str(eti.get("doc_conclusion") or "").strip()
    else:
        leading_cause = dec.get("leading_cause") or "unklaren Genese"
        leading_action = dec.get("leading_action") or "eine strukturierte Komplettierung der Diagnostik"
        concluding = f"In der Zusammenschau der Befunde gehen wir von einer führenden **{leading_cause}** aus. Entsprechend empfehlen wir **{leading_action}**."


    # Build final report
    header = (
        "# Rechtsherzkatheter – Befundbericht\n\n"
        f"**Datum:** {_dt.date.today().strftime('%d.%m.%Y')}\n"
        f"**Tool-Version:** {APP_VERSION}\n\n"
    )
    patient_line = ""
    if ui.get("name") or ui.get("firstname"):
        patient_line = f"**Patient:** {ui.get('firstname','')} {ui.get('name','')}".strip() + "\n\n"

    summary_block = summarize_inputs(case)

    report = [
        header,
        patient_line,
        "## Befundübersicht\n",
        summary_block,
        "\n## Rechtsherzkatheter\n",
        "#### Ruhehämodynamik\n",
        rest_line,
    ]
    if exercise_block:
        report.append("\n" + exercise_block)
    if volume_block:
        report.append("\n" + volume_block)
    if vaso_block:
        report.append("\n" + vaso_block)
    if stepox_block:
        report.append("\n" + stepox_block)
    if curve_block:
        report.append("\n" + curve_block)

    # Verlauf / Vergleich (optional)
    if ctx.get("comparison_table_md"):
        report.append("\n#### Verlauf / Vergleich (Vorher → Jetzt)\n")
        report.append((ctx.get("comparison_table_md") or "").strip() + "\n")

    # Diagnosis + risk + assessment
    report.append("\n## Beurteilung\n")
    report.append(beurteilung.strip() + "\n")

    report.append("\n## Empfehlung\n")
    report.append(_md_kv("Diagnose/Einordnung", dec.get("primary_dx", "—")))
    report.append("\n" + risk_block + "\n")
    report.append(empfehlung.strip() + "\n")

    report.append(concluding + "\n")

    if modules_txts or skipped_mods or ui.get("procedere_free") or recs:
        report.append("\n## Procedere:\n")
        if modules_txts:
            report.append("\n\n".join(modules_txts))
        if skipped_mods:
            report.append("\n_Hinweis: Nicht übernommen (in dieser Konstellation nicht anwählbar): "
                          + ", ".join(skipped_mods) + "._")
        free = (ui.get("procedere_free") or "").strip()
        if free:
            report.append("\n**Freitext:**\n" + free)
        if recs:
            report.append("\n**Zusätzliche Hinweise:**\n")
            report.extend([f"- {r}" for r in recs])

    return "\n".join(report).strip()



# =============================================================================
# Patient report (plain language, no abbreviations/numbers)
# =============================================================================

def _stable_patient_seed(case: Dict[str, Any]) -> int:
    """Deterministic seed for patient text variants.

    Goal: different cases → different wording, but same case → stable wording
    across repeated generations.
    """
    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    dec = case.get("decision") or {}

    # Select only a few stable, clinically relevant discriminators.
    key = {
        "bundle": dec.get("bundle"),
        "primary_dx": dec.get("primary_dx"),
        "hemo_category": der.get("hemo_category"),
        "exercise_done": bool(der.get("exercise_done")),
        "exercise_pattern": der.get("exercise_pattern"),
        "step_up_present": bool(der.get("step_up_present")),
        "ct_ild": bool(ui.get("ct_ild")),
        "ct_emphysema": bool(ui.get("ct_emphysema")),
        "vq_defect": bool(ui.get("vq_defect")),
        "hfpef_category": der.get("hfpef_category"),
        "anemia": bool(der.get("anemia")),
        "congestion": bool(der.get("congestion_likely")),
    }
    s = json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _patient_name(ui: Dict[str, Any]) -> str:
    # Support multiple possible UI key names (historic variants)
    first = ""
    for k in ("firstname", "first_name", "vorname", "first"):
        v = ui.get(k)
        if isinstance(v, str) and v.strip():
            first = v.strip()
            break

    last = ""
    for k in ("name", "lastname", "last_name", "nachname", "surname"):
        v = ui.get(k)
        if isinstance(v, str) and v.strip():
            last = v.strip()
            break

    full = (first + " " + last).strip()
    return full



def _patient_salutation(ui: Dict[str, Any], rng: random.Random) -> str:
    """Returns a stable, formal salutation.

    Patient-facing report templates predominantly use formal address (Sie/Ihre).
    Randomly switching between "Hallo" and "Guten Tag" caused an inconsistent
    register (Hallo + Sie), which is confusing for patients.
    """
    name = _patient_name(ui)
    if name:
        return f"Guten Tag {name},"
    return "Guten Tag,"


def _load_patient_textdb() -> Tuple[Dict[str, Any], Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """Loads patient-facing text blocks if available (flat file, no folders)."""
    import sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    for mod_name in ("rhk_textdb_patient", "rhk_textdb_patient_v7"):
        try:
            mod = __import__(mod_name)  # type: ignore
            blocks = getattr(mod, "PATIENT_BLOCKS", None)
            bundles = getattr(mod, "PATIENT_BUNDLES", None)
            module_summary = getattr(mod, "PATIENT_MODULE_SUMMARY", {}) or {}
            glossary = getattr(mod, "PATIENT_GLOSSARY", {}) or {}
            if isinstance(blocks, dict) and isinstance(bundles, dict):
                if not isinstance(module_summary, dict):
                    module_summary = {}
                if not isinstance(glossary, dict):
                    glossary = {}
                return blocks, bundles, module_summary, glossary
        except Exception:
            continue
    return {}, {}, {}, {}


def _load_echo_patient_textdb() -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Loads echo patient-facing text blocks if available (flat file, no folders)."""
    import sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    for mod_name in ("rhk_textdb_echo_patient",):
        try:
            mod = __import__(mod_name)  # type: ignore
            blocks = getattr(mod, "ECHO_PATIENT_BLOCKS", None)
            glossary = getattr(mod, "ECHO_PATIENT_GLOSSARY", {}) or {}
            if isinstance(blocks, dict):
                if not isinstance(glossary, dict):
                    glossary = {}
                return blocks, glossary
        except Exception:
            continue
    return {}, {}


def _pick_echo_patient_template(block: Any, rng: random.Random) -> str:
    """Pick a template variant for echo patient blocks."""
    if block is None:
        return ""
    if isinstance(block, dict):
        temps = block.get("templates")
        if isinstance(temps, (list, tuple)) and temps:
            return str(rng.choice(list(temps)))
        if isinstance(temps, str) and temps.strip():
            return str(temps)
        if isinstance(block.get("template"), str):
            return str(block.get("template"))
        return ""

    temps = getattr(block, "templates", None)
    if isinstance(temps, (list, tuple)) and temps:
        return str(rng.choice(list(temps)))
    if isinstance(temps, str) and temps.strip():
        return temps
    templ = getattr(block, "template", None)
    if isinstance(templ, str):
        return templ
    return ""


def _render_echo_patient_text(block_id: str, blocks: Dict[str, Any], ctx: Dict[str, Any], rng: random.Random) -> str:
    block = blocks.get(block_id)
    templ = _pick_echo_patient_template(block, rng)
    if not templ:
        return ""
    txt = templ.format_map(SafeDict(ctx)).strip()
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


def build_echo_patient_report(case: Dict[str, Any]) -> str:
    """Erstellt einen patientenfreundlichen Echo Bericht.

    Ziel: Echokardiographische Werte in verständlicher Sprache einordnen.
    Das ist ein Startbaustein und wird schrittweise erweitert.
    """
    ui: Dict[str, Any] = case.get("ui", {}) or {}
    der: Dict[str, Any] = case.get("derived", {}) or {}

    if not ui.get("echo_done") and not ui.get("cmr_done"):
        return "## Echo Patientenbericht\n\nFür diesen Fall sind aktuell keine Herzultraschall oder CMR Werte dokumentiert."

    blocks, glossary = _load_echo_patient_textdb()
    rng = random.Random(_stable_patient_seed(case) + 17)

    def _fmt_val(v: Any, digits: int = 0) -> str:
        vv = _safe_float(v)
        if vv is None:
            return "—"
        return _fmt(vv, digits)

    # --- Values ---
    name = _patient_name(ui)
    sal = _patient_salutation(ui, rng)

    lvef = _safe_float(ui.get("lvef"))
    tapse = _safe_float(ui.get("tapse_mm"))
    sprime = _safe_float(ui.get("s_prime_cm_s"))
    pasp = _safe_float(ui.get("pasp_echo"))
    trv = _safe_float(ui.get("trv_ms"))
    ee = _safe_float(ui.get("ee_ratio"))
    ra_esa = _safe_float(ui.get("ra_esa_cm2"))
    rv_ef = _safe_float(ui.get("rv_3d_ef"))
    if rv_ef is None:
        rv_ef = _safe_float(ui.get("rvef"))

    ivc_diam = _safe_float(ui.get("ivc_diam_mm"))
    ivc_collapse = (ui.get("ivc_collapse") or "").strip().lower()  # "ja" / "nein"

    echo_prob = (der.get("echo_probability") or "").strip().lower() or None

    # --- Classifications ---
    def _class_lvef(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v >= 55:
            return "lv_normal"
        if v >= 45:
            return "lv_mild"
        if v >= 35:
            return "lv_moderate"
        return "lv_severe"

    def _class_rvef(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v >= 45:
            return "rv_ef_normal"
        if v >= 40:
            return "rv_ef_mild"
        if v >= 30:
            return "rv_ef_moderate"
        return "rv_ef_severe"

    def _class_tapse(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v >= 17:
            return "rv_tapse_normal"
        if v >= 14:
            return "rv_tapse_mild"
        if v >= 10:
            return "rv_tapse_moderate"
        return "rv_tapse_severe"

    def _class_sprime(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v >= 9.5:
            return "rv_sprime_normal"
        if v >= 8.0:
            return "rv_sprime_border"
        if v >= 6.0:
            return "rv_sprime_reduced"
        return "rv_sprime_severe"

    def _class_pasp(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v < 35:
            return "pasp_normal"
        if v < 50:
            return "pasp_mild"
        if v < 70:
            return "pasp_moderate"
        return "pasp_severe"

    def _class_ee(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if v < 8:
            return "ee_normal"
        if v <= 14:
            return "ee_intermediate"
        return "ee_high"

    def _class_ra(v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        return "ra_enlarged" if v > 18 else "ra_normal"

    def _class_ivc(d: Optional[float], c: str) -> Optional[str]:
        if d is None and not c:
            return None
        # grobe klinische Logik
        if d is not None and d > 21 and c == "nein":
            return "ivc_high_rap"
        if d is not None and d <= 21 and c == "ja":
            return "ivc_normal"
        return "ivc_unclear"

    ctx = {
        "salutation": sal,
        "name": name,
        "lvef": lvef,
        "lvef_fmt": _fmt_val(lvef, 0),
        "tapse": tapse,
        "tapse_fmt": _fmt_val(tapse, 0),
        "sprime": sprime,
        "sprime_fmt": _fmt_val(sprime, 1),
        "pasp": pasp,
        "pasp_fmt": _fmt_val(pasp, 0),
        "trv": trv,
        "trv_fmt": _fmt_val(trv, 2),
        "ee": ee,
        "ee_fmt": _fmt_val(ee, 1),
        "ra_esa": ra_esa,
        "ra_esa_fmt": _fmt_val(ra_esa, 0),
        "rv_ef": rv_ef,
        "rv_ef_fmt": _fmt_val(rv_ef, 0),
        "echo_prob": echo_prob or "—",
        "ivc_diam": ivc_diam,
        "ivc_diam_fmt": _fmt_val(ivc_diam, 0),
        "ivc_collapse": ivc_collapse or "—",
    }

    parts: List[str] = []
    parts.append("## Echo Patientenbericht")
    parts.append(
        _render_echo_patient_text("intro", blocks, ctx, rng)
        or (
            f"{sal}\n\nHier finden Sie eine verständliche Einordnung der Werte aus dem Herzultraschall. "
            "Das hilft beim Mitlesen und Einordnen. Die endgültige Bewertung ergibt sich immer aus Beschwerden, "
            "Laborwerten und weiteren Untersuchungen."
        )
    )

    parts.append("### Linke Herzkammer")
    bid = _class_lvef(lvef)
    if bid:
        parts.append(_render_echo_patient_text(bid, blocks, ctx, rng))
    else:
        parts.append("Zur Pumpfunktion der linken Herzkammer liegt aktuell kein Zahlenwert vor.")

    parts.append("### Rechte Herzkammer")
    parts.append(_render_echo_patient_text("rv_section_intro", blocks, ctx, rng) or "")

    for bid in (_class_tapse(tapse), _class_sprime(sprime), _class_rvef(rv_ef)):
        if bid:
            txt = _render_echo_patient_text(bid, blocks, ctx, rng)
            if txt:
                parts.append(txt)

    if not any([tapse is not None, sprime is not None, rv_ef is not None]):
        parts.append("Zur Funktion der rechten Herzkammer liegen aktuell keine Zahlenwerte vor.")

    parts.append("### Abschätzung des Drucks in den Lungengefäßen")
    parts.append(_render_echo_patient_text("pasp_section_intro", blocks, ctx, rng) or "")

    bid = _class_pasp(pasp)
    if bid:
        parts.append(_render_echo_patient_text(bid, blocks, ctx, rng))
    if echo_prob:
        prob_id = f"echo_prob_{echo_prob}" if echo_prob in ("niedrig", "intermediär", "hoch") else None
        if prob_id:
            txt = _render_echo_patient_text(prob_id, blocks, ctx, rng)
            if txt:
                parts.append(txt)
    if trv is not None:
        parts.append(f"Die maximale TRV beträgt {ctx['trv_fmt']} m/s. Dieser Messwert wird im Ultraschall genutzt, um den Druck abzuschätzen.")
    if pasp is None and trv is None and not echo_prob:
        parts.append("Für die Abschätzung des Drucks liegen aktuell keine verwertbaren Echo Angaben vor.")

    parts.append("### Vorhöfe und Stauungszeichen")
    parts.append(_render_echo_patient_text("stau_section_intro", blocks, ctx, rng) or "")

    bid = _class_ra(ra_esa)
    if bid:
        parts.append(_render_echo_patient_text(bid, blocks, ctx, rng))
    bid = _class_ivc(ivc_diam, ivc_collapse)
    if bid:
        txt = _render_echo_patient_text(bid, blocks, ctx, rng)
        if txt:
            parts.append(txt)

    parts.append("### Einordnung der Füllungsdrücke")
    parts.append(_render_echo_patient_text("ee_section_intro", blocks, ctx, rng) or "")

    bid = _class_ee(ee)
    if bid:
        parts.append(_render_echo_patient_text(bid, blocks, ctx, rng))
    else:
        parts.append("E/e ist aktuell nicht dokumentiert.")

    parts.append(
        _render_echo_patient_text("outro", blocks, ctx, rng)
        or (
            "### Wie geht es weiter\n\n"
            "Wir betrachten Ultraschallwerte immer im Zusammenhang mit Beschwerden, Belastbarkeit, Laborwerten "
            "und, wenn nötig, der Messung im Rechtsherzkatheter. Wenn Sie einzelne Begriffe nicht verstehen, "
            "sprechen Sie uns bitte an."
        )
    )

    # Optional: Mini Glossar (als kompakte Liste, ohne leere Zeilen zwischen Items)
    if glossary:
        gloss_lines: List[str] = []
        for k in ("LVEF", "TAPSE", "sPAP", "E/e", "S'", "TRV"):
            if k in glossary:
                gloss_lines.append(f"• {k}: {glossary[k]}")
        if gloss_lines:
            parts.append("### Begriffe kurz erklärt\n" + "\n".join(gloss_lines))

    txt = "\n\n".join([p for p in parts if isinstance(p, str) and p.strip()])
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def _pick_patient_template(block: Any, rng: random.Random) -> str:
    """Pick a block template variant.

    Supports:
    - dataclass with .templates: list[str] or tuple[str]
    - dataclass with .template: str
    - dict-like entries
    """
    if block is None:
        return ""

    # dict-like
    if isinstance(block, dict):
        temps = block.get("templates")
        if isinstance(temps, (list, tuple)) and temps:
            return str(rng.choice(list(temps)))
        if isinstance(temps, str) and temps.strip():
            return temps
        if isinstance(block.get("template"), str):
            return str(block.get("template"))
        return ""

    temps = getattr(block, "templates", None)
    if isinstance(temps, (list, tuple)) and temps:
        return str(rng.choice(list(temps)))
    if isinstance(temps, str) and temps.strip():
        return temps

    templ = getattr(block, "template", None)
    if isinstance(templ, str):
        return templ

    return ""


def _render_patient_text(block_id: str, blocks: Dict[str, Any], ctx: Dict[str, Any], rng: random.Random) -> str:
    block = blocks.get(block_id)
    templ = _pick_patient_template(block, rng)
    if not templ:
        return ""
    txt = templ.format_map(SafeDict(ctx)).strip()

    # Normalize whitespace a bit
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


def build_patient_report(case: Dict[str, Any]) -> str:
    """Erstellt einen patientenfreundlichen Bericht (drucktauglich, mit echtem Mehrwert).

    Leitlinien für den Patientenbericht:
    - **Klarer Nutzen**: Was bedeutet der Befund konkret? Was passiert als Nächstes? Was kann ich selbst tun?
    - **Wenig Floskeln**: lieber kurze, konkrete Sätze.
    - **Keine verwirrenden Score-Labels** (z. B. "HFpEF-likely" wird übersetzt).
    - **Zahlen nur als Orientierung**: wenige Kernwerte + verständliche Einordnung.
    - **Dynamik**: Wenn ein Vor-RHK vorliegt → Verlauf (besser/stabil/schlechter) + Konsequenz.

    Hinweis: Dieser Text ersetzt kein ärztliches Gespräch.
    """

    ui: Dict[str, Any] = case.get("ui", {}) or {}
    der: Dict[str, Any] = case.get("derived", {}) or {}
    dec: Dict[str, Any] = case.get("decision", {}) or {}
    hf: Dict[str, Any] = case.get("hfpef", {}) or {}

    blocks, bundles, module_summary, glossary = _load_patient_textdb()
    rng = random.Random(_stable_patient_seed(case))

    # ------------------------------------------------------------------
    # Helfer
    # ------------------------------------------------------------------
    def _norm(x: Any) -> str:
        return str(x).strip() if x is not None else ""

    def _fmt_val(v: Any, digits: int = 1) -> str:
        vv = _safe_float(v)
        if vv is None:
            return "—"
        return _fmt(vv, digits)

    def _qual(label: str, v: Optional[float]) -> Optional[str]:
        if v is None:
            return None
        if label == "mPAP":
            if v <= 20:
                return "normal"
            if v <= 30:
                return "erhöht"
            return "deutlich erhöht"
        if label == "PAWP":
            if v <= 15:
                return "normal"
            if v <= 20:
                return "erhöht"
            return "deutlich erhöht"
        if label == "PVR":
            if v <= 2:
                return "normal"
            if v <= 3:
                return "leicht erhöht"
            if v <= 5:
                return "erhöht"
            return "deutlich erhöht"
        if label == "CI":
            # grobe Orientierung
            if v < 2.2:
                return "niedrig"
            if v < 2.5:
                return "grenzwertig"
            return "normal"
        if label == "RAP":
            if v <= 7:
                return "normal"
            if v <= 12:
                return "erhöht"
            return "deutlich erhöht"
        return None

    def _risk_txt(cat: Optional[str]) -> Optional[str]:
        if not cat:
            return None
        c = str(cat).strip().lower()
        if c.startswith("low") or c.startswith("niedrig"):
            return (
                "Die Gesamt-Einordnung wirkt derzeit eher stabil. "
                "Wenn Ihre Beschwerden ebenfalls stabil sind, reichen häufig Kontrollen im Abstand von einigen Monaten."
            )
        if c.startswith("inter") or "mittel" in c:
            return (
                "Die Gesamt-Einordnung spricht für einen mittleren Kontrollbedarf. "
                "Oft sind Kontrollen in Wochen bis wenigen Monaten sinnvoll, um Verlauf und Therapie gemeinsam zu überprüfen."
            )
        if c.startswith("high") or "hoch" in c:
            return (
                "Die Gesamt-Einordnung spricht für einen hohen Kontrollbedarf. "
                "Engmaschige Betreuung und ggf. intensivere Therapieoptionen im spezialisierten PH‑Zentrum sind wichtig."
            )
        return None

    def _bundle_patient_blocks(bundle_id: str) -> List[str]:
        """Welche Patienten-Bausteine (PX_*) passen zu welchem Bundle (Kxx)?"""
        bids = bundles.get(bundle_id) or []
        out: List[str] = []
        for bid in bids:
            if bid in blocks:
                out.append(bid)
        return out

    # ------------------------------------------------------------------
    # Kernwerte (Ruhe)
    # ------------------------------------------------------------------
    mpap = _safe_float(der.get("mpap_rest") if der.get("mpap_rest") is not None else der.get("mpap"))
    pawp = _safe_float(der.get("pawp_rest") if der.get("pawp_rest") is not None else der.get("pawp"))
    pvr = _safe_float(der.get("pvr_rest") if der.get("pvr_rest") is not None else der.get("pvr"))
    ci = _safe_float(der.get("ci_rest") if der.get("ci_rest") is not None else der.get("ci"))
    rap = _safe_float(der.get("rap_rest") if der.get("rap_rest") is not None else der.get("rap"))

    has_ph = bool(mpap is not None and mpap > 20)
    congestion = bool(der.get("congestion_likely"))

    # Grobe Einordnung (aus Regelwerk/Entscheidung)
    bundle = _norm(dec.get("bundle") or "")
    primary_dx = _norm(dec.get("primary_dx") or "")
    leading_cause = _norm(dec.get("leading_cause") or "")
    leading_action = _norm(dec.get("leading_action") or "")

    def _patientize_cause(txt: str) -> str:
        t = (txt or "").strip()
        if not t:
            return ""
        low = t.lower()
        # Vereinfachen: Gruppen-/Jargon entfernen und in Alltagssprache übersetzen
        if ("gruppe 2" in low) or ("linkskard" in low) or ("hfpef" in low):
            return "Hinweise, dass die linke Herzhälfte mitbeteiligt ist (Rückstau in die Lunge)."
        if ("gruppe 3" in low) or ("copd" in low) or ("ild" in low) or ("fibrose" in low) or ("hypox" in low):
            return "Hinweise, dass eine Lungenerkrankung/Atemwegsproblematik mitbeteiligt sein könnte."
        if ("gruppe 4" in low) or ("cteph" in low) or ("embol" in low) or ("thrombo" in low):
            return "Hinweise, dass ältere Blutgerinnsel in den Lungengefäßen eine Rolle spielen könnten."
        if ("gruppe 1" in low) or ("pah" in low) or ("pulmonal-arter" in low):
            return "Hinweise, dass vor allem die Lungengefäße selbst betroffen sind (pulmonal-arterielle Form)."
        # Fallback: Klammern mit "Gruppe" entfernen
        t = re.sub(r"\s*\(.*grupp(e)?\s*\d.*?\)\s*", " ", t, flags=re.IGNORECASE).strip()
        return t

    cause_patient = _patientize_cause(leading_cause or primary_dx)

    # Verlaufstrend (optional)
    trend_info = _compare_rhk_trend(ui, der)

    # Module: user-selected + auto (fallbasiert sortiert + ggf. gefiltert)
    selected_mods = _normalize_module_ids(ui.get("modules") or [])
    auto_mods = _normalize_module_ids(dec.get("modules") or [])
    all_mods = list(dict.fromkeys(auto_mods + selected_mods))

    policy = der.get("p_module_policy") or {}
    disabled_mods: Dict[str, str] = policy.get("disabled") or {}
    allowed_order: List[str] = policy.get("allowed") or list(_ALL_P_MODULE_IDS)

    all_mods = [m for m in all_mods if m not in disabled_mods]

    order_index = {mid: i for i, mid in enumerate(allowed_order)}
    all_mods = sorted(all_mods, key=lambda m: order_index.get(m, 10_000))

    # Warnhinweise aus Plausibilität (z. B. CTEPH/Antikoag)
    anticoag_status = (ui.get("anticoag_status") or "").strip().lower()
    clot_hint = bool(ui.get("vq_defect") or ui.get("ct_pe") or ui.get("pe_history"))
    ild = bool(ui.get("ct_ild"))
    antifib_status = (ui.get("antifib_status") or "").strip().lower()

    warn_lines: List[str] = []
    if clot_hint and anticoag_status and anticoag_status not in {"ja", "yes", "true"}:
        warn_lines.append(
            "Es gibt Hinweise, die (auch) zu älteren Gerinnseln in den Lungengefäßen passen könnten. "
            "Bitte klären Sie zeitnah mit Ihrem Behandlungsteam, ob eine Blutverdünnung (Antikoagulation) notwendig ist."
        )
    if ild and antifib_status in {"", "nein", "unklar"}:
        warn_lines.append(
            "Bei Hinweisen auf eine Lungenfibrose ist eine spezialisierte Mitbetreuung wichtig. "
            "Bitte klären Sie, ob eine antifibrotische Therapie in Ihrem Fall sinnvoll ist."
        )

    # HFpEF (übersetzt)
    hf_cat = _norm(der.get("hfpef_category") or hf.get("hfpef_category") or "")
    hf_prob = _safe_float(der.get("hfpef_prob") or hf.get("hfpef_prob"))

    hf_txt: Optional[str] = None
    if hf_cat:
        c = hf_cat.lower()
        if "high" in c or "likely" in c:
            hf_txt = "Es gibt Hinweise, dass die linke Herzhälfte sich unter Belastung nicht optimal füllt (das kann zu einem Rückstau in die Lunge beitragen)."
        elif "inter" in c or "mid" in c:
            hf_txt = "Es gibt gewisse Hinweise, dass die linke Herzhälfte unter Belastung mitbeteiligt sein könnte."
        elif "low" in c or "unlikely" in c:
            hf_txt = "Es gibt eher keine klaren Hinweise, dass die linke Herzhälfte die Hauptursache ist."
        # Prozentangabe nur, wenn vorhanden – aber nicht als Score-Label
        if hf_txt and hf_prob is not None:
            hf_txt = hf_txt + f" (Orientierend: {int(round(hf_prob))}%)."

    # Risiko (vereinfachte Sprache)
    risk_txt = _risk_txt(der.get("risk_category"))

    # ------------------------------------------------------------------
    # Bericht zusammensetzen
    # ------------------------------------------------------------------
    lines: List[str] = []
    pname = _patient_name(ui)
    salutation = _patient_salutation(ui, rng)

    lines.append("# Patientenbericht zum Rechtsherzkatheter")
    meta = []
    if pname:
        meta.append(f"**Name:** {pname}")
    meta.append(f"**Datum:** {_dt.date.today().strftime('%d.%m.%Y')}")
    meta.append(f"**Version:** {APP_VERSION}")
    lines.append(" · ".join(meta))
    lines.append("")

    # 1) Kurzfazit (Nutzen)
    lines.append("## Das Wichtigste auf einen Blick")
    # Hauptaussage patientengerecht
    if has_ph:
        main = "Die Messwerte sprechen für eine **Druckerhöhung in den Lungengefäßen (Lungenhochdruck)**."
    else:
        main = "In der Messung finden sich **keine klaren Hinweise auf eine relevante Druckerhöhung in den Lungengefäßen**."
    lines.append(f"- {main}")

    eti = der.get("ph_etiology") if isinstance(der, dict) else None
    eti_patient_line = str(eti.get("patient_cause_line") or "").strip() if isinstance(eti, dict) else ""

    if eti_patient_line:
        lines.append(f"- Einordnung (mögliche Ursachen): {eti_patient_line}")
    elif cause_patient:
        lines.append(f"- Wahrscheinlichste Einordnung: **{cause_patient}**.")

    if leading_action:
        lines.append(f"- Nächster Schwerpunkt: **{leading_action}**.")

    if trend_info.get("has_prev"):
        lines.append(f"- Verlauf im Vergleich: **{trend_info.get('trend','')}**.")

    # Zusatz-Hinweise
    if congestion:
        lines.append("- Zusätzlich gibt es Hinweise auf **Wasser-/Stauungsneigung** (das kann z. B. Schwellungen oder Gewichtszunahme erklären).")
    if risk_txt:
        lines.append(f"- {risk_txt}")
    lines.append("")

    # 2) Einordnung / Erklärung
    lines.append("## Was bedeutet das für Sie?")

    # Hinweis: Mehrere Ursachen können parallel bestehen (Herz/Lunge/alte Embolien etc.)
    eti = der.get("ph_etiology") if isinstance(der, dict) else None
    if isinstance(eti, dict) and isinstance(eti.get("candidates"), list) and len(eti.get("candidates")) > 1:
        lines.append("Wichtig: Ein Lungenhochdruck kann **mehrere Ursachen gleichzeitig** haben, die sich gegenseitig verstärken können.")
        lines.append("Daher wird die weitere Abklärung oft interdisziplinär geplant, um alle möglichen Beiträge gezielt zu behandeln.")
        lines.append("")
    ctx = {
        "name": pname,
        "salutation": salutation,
    }

    # Bausteine je nach Bundle (sparsam, um Redundanz zu vermeiden)
    rendered_bids: set = set()

    if bundle:
        for bid in _bundle_patient_blocks(bundle):
            t = _render_patient_text(bid, blocks, ctx, rng)
            if t:
                lines.append(t)
                lines.append("")
                rendered_bids.add(bid)
    else:
        # Fallback: kurzer Standardtext
        t = _render_patient_text("PX_INTERPRETATION", blocks, ctx, rng)
        if t:
            lines.append(t)
            lines.append("")
            rendered_bids.add("PX_INTERPRETATION")

    # Zusatz: Wenn mehrere Ursachen möglich sind, ergänzen wir kurze Hinweise (ohne Wiederholungen)
    extra_hint_ids: List[str] = []

    # Angeborener Herzfehler / Shunt (wenn explizit angegeben/auffällig)
    if bool(ui.get("chd_pos")) or bool(ui.get("step_up_present")):
        extra_hint_ids.append("PX_SHUNT_HINT")

    # Gruppenhinweise aus Kandidatenliste (max. 3 Ergänzungen)
    group1_specific = bool(ui.get("immunology_pos") or ui.get("virology_pos") or ui.get("mutation_pos") or ui.get("chd_pos") or ui.get("step_up_present"))
    group_to_bid = {
        1: "PX_GROUP1_HINT",  # nur wenn wirklich Anhaltspunkte (Autoimmun/Virologie/Genetik/CHD)
        2: "PX_GROUP2_HINT",
        3: "PX_GROUP3_HINT",
        4: "PX_GROUP4_HINT",
    }

    if isinstance(eti, dict) and isinstance(eti.get("candidates"), list):
        for c in (eti.get("candidates") or [])[:5]:
            try:
                g = int(c.get("group"))
            except Exception:
                continue
            if g == 1 and not group1_specific:
                continue
            bid = group_to_bid.get(g)
            if bid:
                extra_hint_ids.append(bid)

    seen: set = set()
    for bid in extra_hint_ids:
        if bid in seen or bid in rendered_bids:
            continue
        seen.add(bid)
        if bid not in blocks:
            continue
        t = _render_patient_text(bid, blocks, ctx, rng)
        if t:
            lines.append(t)
            lines.append("")
            rendered_bids.add(bid)
        if len(seen) >= 3:
            break

    if hf_txt:
        lines.append(hf_txt)
        lines.append("")

    # 3) Werte zur Orientierung (kompakt, aber konkret)
    lines.append("## Wichtige Werte zur Orientierung")
    hemo_items: List[str] = []
    if mpap is not None:
        hemo_items.append(f"- **Druck in den Lungengefäßen (mPAP):** { _fmt(mpap,0) } mmHg – {_qual('mPAP', mpap)} (Lungenhochdruck ab >20)")
    if pawp is not None:
        hemo_items.append(f"- **Füllungsdruck linkes Herz/Lungenvene (PAWP):** { _fmt(pawp,0) } mmHg – {_qual('PAWP', pawp)} (häufig erhöht ab >15)")
    if pvr is not None:
        hemo_items.append(f"- **Widerstand in den Lungengefäßen (PVR):** { _fmt(pvr,1) } WU – {_qual('PVR', pvr)} (oft erhöht ab >2)")
    if ci is not None:
        hemo_items.append(f"- **Herzzeitvolumen-Index (CI):** { _fmt(ci,2) } l/min/m² – {_qual('CI', ci)}")
    if rap is not None:
        hemo_items.append(f"- **Druck im rechten Vorhof (RAP):** { _fmt(rap,0) } mmHg – {_qual('RAP', rap)}")
    if hemo_items:
        lines.extend(hemo_items)
    else:
        lines.append("Keine Kernwerte verfügbar.")
    lines.append("")

    # Kurz erklärt: Was bedeuten diese Werte?
    t = _render_patient_text("PX_HEMO_EXPLAIN", blocks, ctx, rng)
    if t:
        lines.append(t)
        lines.append("")

    # 4) Verlauf / Vergleich (wenn vorhanden)
    if trend_info.get("has_prev"):
        lines.append("## Verlauf im Vergleich")
        # Kontext Therapie (falls angegeben)
        tx_txt = (trend_info.get("tx_txt") or "").strip()
        if ui.get("prev_is_initial"):
            lines.append("Diese Untersuchung dient (auch) als **Verlaufskontrolle nach einer Ausgangsmessung**.")
        if tx_txt:
            lines.append(f"Seit der Voruntersuchung wurde als Therapie angegeben: **{tx_txt}**.")
        lines.append(trend_info.get("sentence_patient") or "")
        if trend_info.get("detail_patient"):
            lines.append(trend_info.get("detail_patient"))
        recp = (trend_info.get("rec_patient") or "").strip()
        if recp:
            lines.append("")
            lines.append(f"**Was bedeutet das praktisch?** {recp}")
        lines.append("")

    # 5) Nächste Schritte / Module (konkret + Nutzen)
    lines.append("## Wie geht es weiter?")

    # Level/Sortierung aus Policy (v24.1+)
    levels_map: Dict[str, int] = (policy.get("levels") or {}) if isinstance(policy, dict) else {}

    # Kandidaten-Gruppen (für kurze, patientenfreundliche Begründungen)
    eti_groups: List[int] = []
    if isinstance(eti, dict) and isinstance(eti.get("candidates"), list):
        for c in (eti.get("candidates") or [])[:5]:
            try:
                eti_groups.append(int(c.get("group")))
            except Exception:
                continue

    risk_cat_local = str(der.get("risk_category") or "").lower()

    def _module_level(mid: str) -> int:
        try:
            lvl = int(levels_map.get(mid, 3))
        except Exception:
            lvl = 3
        return lvl if lvl in (1, 2, 3) else 3

    def _module_reason(mid: str) -> str:
        """Kurze, patientenfreundliche Begründung (nur wenn passend).

        Wichtig: Nicht jede Maßnahme hat eine eindeutige, einzelne Ursache.
        Die Gründe werden daher bewusst zurückhaltend formuliert.
        """
        # Rückstau / Wasser
        if mid == "P02" and congestion:
            return "weil es Hinweise auf Wassereinlagerungen bzw. Rückstau gibt"

        # Blutarmut
        if mid == "P13" and bool(der.get("anemia")):
            return "weil die Blutwerte auf eine Blutarmut hindeuten können"

        # Lunge/Atemwege
        if mid in ("P08", "P12") and (
            bool(der.get("ct_ild")) or bool(der.get("ct_emphysema")) or
            bool(der.get("lufu_restrictive")) or bool(der.get("lufu_obstructive")) or bool(der.get("lufu_diffusion"))
        ):
            return "weil Befunde an Lunge/Atemwegen auffällig sein können und wir das genauer einordnen möchten"

        # Linkes Herz
        if mid == "P09" and (2 in eti_groups or (pawp is not None and pawp > 15)):
            return "weil es Hinweise auf eine Beteiligung der linken Herzseite geben kann"

        # Gerinnsel/Embolien (CTEPH-/V/Q-Logik)
        if mid in ("P05", "P10") and (4 in eti_groups or bool(der.get("vq_defect")) or bool(der.get("ct_embolie")) or bool(der.get("ct_pe"))):
            return "weil Hinweise auf (ältere) Blutgerinnsel/Embolien eine Rolle spielen könnten"

        if mid == "P10" and (4 in eti_groups) and str(ui.get("anticoag_status") or "").lower() in ("nein", "unklar", ""):
            return "weil in diesem Zusammenhang die Frage nach einer Blutverdünnung besonders wichtig ist"

        # Autoimmun / Virologie / Genetik
        if mid == "P17" and bool(ui.get("immunology_pos")):
            return "weil bestimmte Autoimmun-/Rheuma-Erkrankungen Lungenhochdruck mit verursachen können"
        if mid == "P18" and bool(ui.get("virology_pos")):
            return "weil bestimmte Virusinfektionen in seltenen Fällen mit Lungenhochdruck zusammenhängen"
        if mid == "P20" and bool(ui.get("mutation_pos")):
            return "weil genetische Faktoren bei manchen Formen von Lungenhochdruck eine Rolle spielen können"

        # Advanced Therapies (nur wenn Gesamtlage eher schwer)
        if mid == "P25" and (risk_cat_local.startswith("high") or "hoch" in risk_cat_local):
            return "weil wir bei einer eher schweren Gesamtsituation frühzeitig auch weiterführende Optionen im Spezialzentrum mitdenken"

        return ""

    if all_mods:
        by_level: Dict[int, List[str]] = {1: [], 2: [], 3: []}
        for mid in all_mods:
            by_level[_module_level(mid)].append(mid)

        level_titles = {
            1: "Level I – prioritäre Empfehlungen",
            2: "Level II – sinnvolle Ergänzungen",
            3: "Level III – optional (je nach Kontext)",
        }

        lines.append(
            "Die folgenden Schritte sind – je nach Gesamtbild – geplant oder sinnvoll. "
            "Falls verfügbar, steht darunter kurz, warum das in Ihrer Situation relevant sein kann."
        )
        lines.append("")

        for lvl in (1, 2, 3):
            mids = by_level.get(lvl) or []
            if not mids:
                continue
            lines.append(f"### {level_titles.get(lvl, f'Level {lvl}')}")
            for mid in mids:
                txt = (module_summary.get(mid) or "").strip()
                if not txt:
                    # Fallback: Titel aus Arzt-TextDB
                    try:
                        from rhk_textdb import ALL_BLOCKS as _ALL
                        blk = _ALL.get(mid)
                        if blk is not None:
                            txt = str(blk.title)
                    except Exception:
                        txt = txt or mid

                reason = _module_reason(mid)
                if reason:
                    lines.append(f"- {txt}  \n  _Warum bei Ihnen:_ {reason}.")
                else:
                    lines.append(f"- {txt}")
            lines.append("")
    else:
        # generischer Baustein
        t = _render_patient_text("PX_NEXT_STEPS", blocks, ctx, rng)
        if t:
            lines.append(t)
            lines.append("")

# Wichtige Warnhinweise (z. B. Antikoag/ILD)
    if warn_lines:
        lines.append("**Wichtiger Hinweis:**")
        for w in warn_lines:
            lines.append(f"- {w}")
        lines.append("")

    # 6) Selbstmanagement (Stauung / Alltag)
    lines.append("## Was Sie selbst beobachten oder tun können")
    self_lines: List[str] = []
    # immer sinnvoll
    self_lines.append("- **Belastbarkeit notieren:** Was geht im Alltag gut, was nicht? (z. B. Treppen, Gehstrecke).")
    self_lines.append("- **Medikamentenliste aktuell halten:** inkl. Dosierungen und Beginn/Änderungen.")
    if congestion:
        self_lines.append("- **Gewicht täglich kontrollieren** (morgens, nach dem Wasserlassen, ähnliche Kleidung) und Verlauf notieren.")
        self_lines.append("- **Salz und Trinkmenge im Blick behalten:** Bei Wasseransammlung helfen oft Salzreduktion und eine individuell abgestimmte Trinkmenge. Die konkrete Empfehlung legen wir gemeinsam fest.")
        self_lines.append("- Bei rascher Gewichtszunahme/Schwellungen bitte frühzeitig melden – manchmal muss die Entwässerung angepasst werden.")
    else:
        self_lines.append("- Bei neuen Schwellungen, rascher Gewichtszunahme oder deutlich zunehmender Luftnot bitte frühzeitig melden.")
    lines.extend(self_lines)
    lines.append("")

    # 7) Safety net
    lines.append("## Wann sollten Sie sich sofort melden?")
    t = _render_patient_text("PX_SAFETY_NET", blocks, ctx, rng)
    if t:
        lines.append(t)
    else:
        lines.append("- starke oder plötzlich zunehmende Luftnot in Ruhe")
        lines.append("- Brustschmerz/Brustdruck")
        lines.append("- Ohnmacht oder beinahe Ohnmacht")
        lines.append("- blutiger Auswurf/Husten von Blut")
        lines.append("- rasche Gewichtszunahme oder stark zunehmende Schwellungen")
    lines.append("")

    # 8) Glossar (kurz)
    lines.append("## Begriffe kurz erklärt")
    used_terms: List[str] = []
    for term in ["mPAP", "PAWP", "PVR", "CI", "RAP", "Lungenhochdruck"]:
        if term.lower() in " ".join(lines).lower():
            used_terms.append(term)
    # add from glossary if available
    added = 0
    for term in used_terms:
        if term in glossary:
            lines.append(f"- **{term}:** {glossary[term]}")
            added += 1
    if added == 0:
        lines.append("Keine Begriffe zu erklären.")
    lines.append("")

    # 9) Disclaimer
    t = _render_patient_text("PX_DISCLAIMER", blocks, ctx, rng)
    if t:
        lines.append(t)

    # Clean spacing
    out = "\n".join([ln.rstrip() for ln in lines]).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out



def build_internal_report(case: Dict[str, Any]) -> str:
    env = case.get("env") or {}
    dec = case.get("decision") or {}
    debug = case.get("debug") or {}
    warns = case.get("warnings") or debug.get("warnings") or []
    rule_trace = debug.get("rule_trace") or {}
    fired = rule_trace.get("fired") or []
    errors = rule_trace.get("errors") or []

    lines = [
        "## Internal Debug",
        f"- Bundle: {dec.get('bundle')}",
        f"- Primary DX: {dec.get('primary_dx')}",
        f"- Tags: {', '.join(dec.get('tags') or [])}",
        f"- Missing (Regelwerk): {', '.join(dec.get('missing_fields') or [])}",
        f"- Warnungen (Plausibilität): {len(warns)}",
        "",
        "### Plausibilitätswarnungen (Auszug)",
    ]

    if not warns:
        lines.append("- keine")
    else:
        for w in warns[:12]:
            try:
                sev = str(w.get("severity") or "warn").upper()
                msg = str(w.get("message") or "").strip()
                flds = w.get("fields") or []
                ftxt = f" (Felder: {', '.join([str(x) for x in flds])})" if flds else ""
                lines.append(f"- [{sev}] {msg}{ftxt}")
            except Exception:
                continue
        if len(warns) > 12:
            lines.append(f"- … weitere {len(warns) - 12} Warnungen")

    lines += [
        "",
        "### Regelwerk – Trace",
        f"- Ausgelöste Regeln: {len(fired)}",
        f"- Regel-Fehler: {len(errors)}",
        "",
        "#### Ausgelöste Regeln (Auszug)",
    ]

    if not fired:
        lines.append("- keine")
    else:
        for r in fired[:20]:
            try:
                rid = r.get("id")
                pr = r.get("priority")
                wh = str(r.get("when") or "")
                wh_short = (wh[:160] + "…") if len(wh) > 160 else wh
                lines.append(f"- {rid} (prio {pr}): {wh_short}")
            except Exception:
                continue
        if len(fired) > 20:
            lines.append(f"- … weitere {len(fired) - 20} Regeln")

    if errors:
        lines += ["", "#### Regel-Fehler (Auszug)"]
        for e in errors[:12]:
            try:
                rid = e.get("id")
                pr = e.get("priority")
                err = str(e.get("error") or "")
                err_short = (err[:180] + "…") if len(err) > 180 else err
                lines.append(f"- {rid} (prio {pr}): {err_short}")
            except Exception:
                continue
        if len(errors) > 12:
            lines.append(f"- … weitere {len(errors) - 12} Fehler")

    lines += [
        "",
        "### Env (Auszug)",
    ]

    keys = [
        "mpap", "pawp_rest", "pvr", "ci", "tpg", "dpg",
        "hemo_category", "precap", "ipcph", "cpcph",
        "hfpef_category", "hfpef_percent",
        "congestion_likely", "step_up_present", "step_up_from_to",
        "mpap_co_slope", "pawp_co_slope", "exercise_pattern",
        "adaptation_type",
        "s_prime_raai",
        "warnings_count",
    ]
    for k in keys:
        lines.append(f"- {k}: {env.get(k)}")
    return "\n".join(lines)


# =============================================================================
# Random example generation (now with lab constellations)
# =============================================================================

def random_example(scenario: Optional[str] = None, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Liefert ein zufälliges, aber in sich stimmiges Beispiel.

    Ziel:
    - Beispiele sollen möglichst viele Features abdecken (RHK Ruhe/Belastung, Volumen, Vaso, Step-up,
      Echo/CT/VQ/Lufu, Labor-Konstellationen).
    - Module werden teils bewusst vorselektiert, um die Procedere-Logik sichtbar zu machen.
    """
    today = _dt.date.today()

    rng = random if seed is None else random.Random(int(seed))


    scenarios = [
        "no_ph",            # normale Hämodynamik
        "pah_pre",          # präkapilläre PH (PAH-typisch)
        "cteph",            # CTEPH-Konstellation
        "ild_ph",           # ILD/Hypoxie
        "hfpef_ipcph",      # iPcPH (HFpEF-typisch)
        "cpcph",            # cPcPH
        "shunt_asd",        # Shunt/Step-up
    ]
    scen = scenario if (isinstance(scenario, str) and scenario in scenarios) else rng.choice(scenarios)

    ui: Dict[str, Any] = {}

    # --- Demografie ---
    if scen in ("pah_pre", "shunt_asd"):
        age = rng.choice([28, 34, 41])
        sex = rng.choice(["weiblich", "weiblich", "männlich"])
    elif scen in ("hfpef_ipcph", "cpcph"):
        age = rng.choice([62, 68, 74, 79])
        sex = rng.choice(["weiblich", "männlich"])
    else:
        age = rng.choice([45, 52, 58, 66, 72])
        sex = rng.choice(["weiblich", "männlich"])

    ui["firstname"] = rng.choice(["Anna", "Max", "Sofia", "Leon", "Mara", "Jonas"])
    ui["name"] = rng.choice(["Beispiel", "Muster", "Patient", "Testfall"])
    ui["age"] = age
    ui["sex"] = sex
    ui["height_cm"] = rng.choice([160, 168, 175, 182])
    ui["weight_kg"] = rng.choice([58, 72, 86, 98])

    ui["bp_sys"] = rng.choice([105, 115, 125, 135, 145])
    ui["bp_dia"] = rng.choice([65, 70, 75, 80, 85])
    ui["hr"] = rng.choice([55, 65, 75, 85, 95])

    ui["story"] = rng.choice([
        "Belastungsdyspnoe seit Monaten, reduzierte Belastbarkeit.",
        "Zunehmende Luftnot, gelegentlich Schwindel.",
        "Kontrolle nach PH-Verdachtsdiagnose.",
        "Therapieevaluation bei bekannter PH.",
    ])

    ui["ph_known"] = scen in ("pah_pre", "cteph", "cpcph")
    ui["ph_suspected"] = not ui["ph_known"]

    # --- PH-Status Konsistenz + Details ---
    # In der Praxis schließen sich "PH-Diagnose bekannt" und "PH-Verdachtsdiagnose" gegenseitig aus.
    # Bei bekannter PH füllen wir deshalb zusätzliche Kontextfelder, damit die UI nicht "leer" wirkt.
    if ui.get("ph_known"):
        if scen == "pah_pre":
            ui["ph_known_dx"] = "PAH (Gruppe 1)"
            ui["ph_known_subtype"] = rng.choice([
                "SOP: Systemsklerose-assoziierte PAH",
                "idiopathische PAH",
                "portopulmonale Hypertonie",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["PDE‑5‑Hemmer", "Endothelin‑Rezeptorantagonist (ERA)"],
                ["PDE‑5‑Hemmer"],
                ["sGC‑Stimulator (Riociguat)", "Endothelin‑Rezeptorantagonist (ERA)"],
            ])
        elif scen == "cteph":
            ui["ph_known_dx"] = "CTEPH (Gruppe 4)"
            ui["ph_known_subtype"] = rng.choice([
                "inoperable CTEPH (BPA-Evaluation)",
                "Status nach LE mit Residuen",
                "CTED/CTEPH im Verlauf",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["sGC‑Stimulator (Riociguat)"],
                ["sGC‑Stimulator (Riociguat)", "Diuretikum"],
            ])
            ui["ph_interventions"] = rng.choice([
                ["BPA (Ballonangioplastie, Katheter)"],
                ["PEA (Pulmonalisendarteriektomie, OP)"],
                [],
            ])
        elif scen == "cpcph":
            ui["ph_known_dx"] = "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)"
            ui["ph_known_subtype"] = rng.choice([
                "HFpEF mit postkapillärer PH",
                "cPcPH bei HFpEF (Mischkomponente wahrscheinlich)",
                "Linksherzerkrankung im Verlauf",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["Diuretikum"],
                ["Diuretikum", "Sauerstofftherapie"],
            ])
        else:
            ui["ph_known_dx"] = "Sonstige/unklar (Gruppe 5)"
            ui["ph_known_subtype"] = "unklar"
            ui["ph_current_meds"] = []

        # Pflichtähnliche Felder (in Beispielen immer gefüllt)
        ui["ph_first_dx"] = rng.choice(["03/2020", "09/2021", "01/2022", "06/2023"])
        ui["ph_reason_rhk"] = rng.choice(["Verlaufskontrolle", "Therapieentscheidung", "Neusymptomatik"])
        ui["ph_prev_meds"] = ui.get("ph_prev_meds") or []
        # Bei bekannter Diagnose ist Verdacht nicht gesetzt
        ui["ph_suspected"] = False
    else:
        # Kein bekannter PH-Status: Verdacht ist möglich, Details bleiben leer
        ui["ph_known_dx"] = None
        ui["ph_known_subtype"] = ""
        ui["ph_first_dx"] = ""
        ui["ph_reason_rhk"] = None
        ui["ph_current_meds"] = ui.get("ph_current_meds") or []
        ui["ph_prev_meds"] = ui.get("ph_prev_meds") or []
        ui["ph_interventions"] = ui.get("ph_interventions") or []

    # --- Klinik/Funktion ---
    ui["who_fc"] = rng.choice(["II", "III"]) if scen != "no_ph" else rng.choice(["I", "II"])
    ui["six_mwd_m"] = rng.choice([240, 320, 420]) if scen != "no_ph" else rng.choice([420, 480, 520])
    ui["stairs_flights"] = rng.choice([0, 1, 2, 3])
    ui["syncope"] = rng.choices(["keine", "gelegentlich", "wiederholt"], weights=[0.83, 0.14, 0.03], k=1)[0]
    ui["hemoptysis"] = (scen == "cteph") and (rng.random() < 0.15)
    ui["dizziness"] = rng.choice([False, True])

    # --- Labor ---
    lab_mode = rng.choice(["normal", "inflammation", "anemia", "renal"])
    ui["crp_mg_l"] = rng.choice([2, 4, 6]) if lab_mode != "inflammation" else rng.choice([25, 60])
    ui["leukocytes_g_l"] = rng.choice([6.5, 7.8, 9.1]) if lab_mode != "inflammation" else rng.choice([12.0, 15.5])
    ui["creatinine_mg_dl"] = rng.choice([0.8, 1.0, 1.2]) if lab_mode != "renal" else rng.choice([1.8, 2.2])
    ui["egfr"] = rng.choice([65, 75, 85, 95]) if lab_mode != "renal" else rng.choice([25, 30, 35, 40, 45])
    ui["platelets_g_l"] = rng.choice([190, 240, 320])
    ui["inr"] = rng.choice([1.0, 1.1, 1.2])
    ui["ptt_s"] = rng.choice([28, 31, 34])

    # Hb gezielt setzen: in ~50% fehlt Hb, um "nicht anwählbar" Logik zu testen
    if rng.random() < 0.5:
        ui["hb_g_dl"] = None
        ui["anemia_type"] = None
    else:
        if lab_mode == "anemia":
            ui["hb_g_dl"] = rng.choice([9.8, 10.6, 11.4])
            ui["anemia_type"] = rng.choice(["mikrozytär", "normozytär", "makrozytär"])
        else:
            ui["hb_g_dl"] = rng.choice([12.6, 13.8, 15.1])
            ui["anemia_type"] = None

    ui["bnp_kind"] = rng.choice(["NT-proBNP", "BNP"])
    if scen in ("no_ph",):
        ui["bnp_value"] = rng.choice([40, 80, 120])
    elif scen in ("hfpef_ipcph", "cpcph"):
        ui["bnp_value"] = rng.choice([380, 900, 1800])
    else:
        ui["bnp_value"] = rng.choice([120, 380, 1200, 2400])

    # --- Bildgebung/Echo ---
    ui["ct_done"] = True
    ui["ct_koronarkalk"] = rng.choice([False, True])

    ui["ct_ild"] = (scen == "ild_ph")
    ui["ct_emphysema"] = (scen == "ild_ph") and rng.choice([False, True])
    ui["ct_embolie"] = (scen == "cteph")
    ui["ct_mosaic"] = (scen == "cteph")

    ui["vq_done"] = (scen == "cteph") or (rng.random() < 0.4)
    ui["vq_defect"] = (scen == "cteph") and ui["vq_done"]
    ui["vq_desc"] = "Mehrsegmentale Perfusionsdefekte." if ui["vq_defect"] else ""

    ui["echo_done"] = True
    ui["lvef"] = 60 if scen not in ("cpcph",) else 55
    ui["la_enlarged"] = True if scen in ("hfpef_ipcph", "cpcph") else rng.choice([False, True])
    ui["ee_ratio"] = 16 if scen in ("hfpef_ipcph", "cpcph") else rng.choice([9, 11, 13])
    ui["pasp_echo"] = rng.choice([35, 45, 60]) if scen != "no_ph" else 28
    ui["tapse_mm"] = 22 if scen == "no_ph" else rng.choice([14, 16, 18, 20])
    ui["atrial_fib"] = True if scen in ("hfpef_ipcph", "cpcph") else False


    # --- Zusatzfelder für Modul-Gating (damit "nicht anwählbar" Regeln sichtbar werden) ---

    # Antikoagulation
    if scen == "cteph" or ui.get("atrial_fib"):
        ui["anticoag_status"] = "ja"
        ui["anticoag_substance"] = rng.choice(["DOAC (Apixaban, Rivaroxaban)", "VKA (Phenprocoumon/Warfarin)"])
        ui["anticoag_indication"] = "CTEPH/CTEPD" if scen == "cteph" else "Vorhofflimmern"
        ui["anticoag_since"] = rng.choice(["09/2023", "03/2024", "11/2024"])
        ui["anticoag_note"] = ""
    else:
        ui["anticoag_status"] = "nein"
        ui["anticoag_substance"] = None
        ui["anticoag_indication"] = "keine Angabe"
        ui["anticoag_since"] = ""
        ui["anticoag_note"] = ""

    # Immunologie Autoimmun
    if scen in ("pah_pre",) and rng.random() < 0.35:
        ui["immunology_pos"] = True
        ui["immunology_items"] = rng.sample([
            "Systemische Sklerose (Sklerodermie)",
            "SLE (Lupus erythematodes)",
            "MCTD (Mixed connective tissue disease)",
            "Sjögren-Syndrom",
        ], k=1)
        ui["immunology_desc"] = "Autoimmunerkrankung bekannt."
    else:
        ui["immunology_pos"] = False
        ui["immunology_items"] = []
        ui["immunology_desc"] = ""

    # Virologie Infektiologie
    if scen in ("pah_pre",) and rng.random() < 0.15:
        ui["virology_pos"] = True
        ui["virology_items"] = rng.sample([
            "HIV",
            "Hepatitis B",
            "Hepatitis C",
            "Schistosomiasis (parasitär)",
        ], k=1)
        ui["virology_desc"] = "Infektiologischer Risikofaktor dokumentiert."
    else:
        ui["virology_pos"] = False
        ui["virology_items"] = []
        ui["virology_desc"] = ""

    # Mutation Genetik
    if (scen == "pah_pre") and (age is not None) and (age < 45) and (rng.random() < 0.18):
        ui["mutation_pos"] = True
        ui["mutation_items"] = rng.sample([
            "BMPR2 Mutation",
            "ALK1 ACVRL1 Mutation",
            "EIF2AK4 Mutation",
        ], k=1)
        ui["mutation_desc"] = "Hinweis auf hereditäre Konstellation."
    else:
        ui["mutation_pos"] = False
        ui["mutation_items"] = []
        ui["mutation_desc"] = ""

    # Abdomensonographie
    ui["abd_sono_done"] = rng.random() < 0.55
    if ui["abd_sono_done"]:
        if rng.random() < 0.12:
            ui["abd_sono_desc"] = "Hinweis auf Leberzirrhose und portale Hypertension."
        else:
            ui["abd_sono_desc"] = rng.choice(["Unauffällig.", "Normalbefund.", "Kein Hinweis auf Leberzirrhose."])
    else:
        ui["abd_sono_desc"] = ""
    ui["s_prime_cm_s"] = rng.choice([9.0, 11.0, 13.0])
    ui["ra_esa_cm2"] = rng.choice([16.0, 20.0, 26.0])

    # --- Lufu ---
    ui["lufu_done"] = True
    ui["lufu_obstructive"] = bool(ui["ct_emphysema"])
    ui["lufu_restrictive"] = bool(ui["ct_ild"])
    ui["lufu_diffusion"] = bool(ui["ct_ild"]) or (rng.random() < 0.35)
    ui["fev1_l"] = rng.choice([1.4, 2.1, 2.8])
    ui["fvc_l"] = rng.choice([2.0, 2.8, 3.6])
    ui["dlco_sb"] = rng.choice([35, 52, 68])
    ui["lufu_summary"] = rng.choice(["", "Leichte Diffusionsstörung.", "Obstruktives Muster."])


    # In einem Teil der Fälle explizit unauffällige Lufu setzen, damit P12 klar deaktiviert werden kann
    if scen == "no_ph" or rng.random() < 0.18:
        ui["lufu_obstructive"] = False
        ui["lufu_restrictive"] = False
        ui["lufu_diffusion"] = False
        ui["lufu_summary"] = rng.choice(["Unauffällig.", "Normalbefund.", "Keine relevanten Auffälligkeiten."])
    # --- Hämodynamik (Ruhe) ---
    if scen == "no_ph":
        spap, dpap, pawp, co, rap = 28, 10, 10, 5.2, 6
    elif scen == "hfpef_ipcph":
        spap, dpap, pawp, co, rap = 55, 25, 20, 4.5, 10
    elif scen == "cpcph":
        spap, dpap, pawp, co, rap = 70, 35, 22, 3.6, 14
    else:  # präkapillär
        spap, dpap, pawp, co, rap = 72, 30, 10, 4.0, 9

    ui["spap_rest"] = spap
    ui["dpap_rest"] = dpap
    ui["mpap_rest"] = None  # berechnen lassen
    ui["pawp_rest"] = pawp
    ui["rap_rest"] = rap
    ui["co_rest"] = co
    ui["ci_rest"] = None
    ui["pvr_rest"] = None

    # --- Belastung / Volumen ---
    ui["exercise_done"] = scen in ("pah_pre", "hfpef_ipcph", "cpcph") and (rng.random() < 0.75)
    if ui["exercise_done"]:
        ui["exercise_protocol"] = rng.choice(["WHO-Rampe", "Stufenprotokoll"])
        ui["exercise_peak_watts"] = rng.choice([75, 100, 125, 150, 175])
        ui["spap_peak"] = spap + rng.choice([25, 35])
        ui["dpap_peak"] = dpap + rng.choice([10, 15])
        ui["mpap_peak"] = None
        ui["pawp_peak"] = pawp + (rng.choice([3, 10, 15]) if scen in ("hfpef_ipcph", "cpcph") else rng.choice([2, 4, 6]))
        ui["co_peak"] = co + rng.choice([1.0, 1.8, 2.5])
    else:
        ui["exercise_protocol"] = ""
        ui["exercise_peak_watts"] = None
        ui["spap_peak"] = None
        ui["dpap_peak"] = None
        ui["mpap_peak"] = None
        ui["pawp_peak"] = None
        ui["co_peak"] = None

    ui["volume_challenge_done"] = (scen == "hfpef_ipcph") and (rng.random() < 0.6)
    if ui["volume_challenge_done"]:
        ui["volume_ml"] = rng.choice([500, 750])
        ui["pawp_post"] = pawp + rng.choice([5, 8, 12])
        ui["mpap_post"] = None
        ui["co_post"] = co + rng.choice([0.5, 1.0])
    else:
        ui["volume_ml"] = None
        ui["pawp_post"] = None
        ui["mpap_post"] = None
        ui["co_post"] = None

    # --- Vaso (nur PAH-Beispiel) ---
    ui["vaso_test_done"] = (scen == "pah_pre") and (rng.random() < 0.5)
    if ui["vaso_test_done"]:
        ui["vaso_substance"] = rng.choice(["NO", "Iloprost"])
        ui["vaso_mpap_pre"] = None
        ui["vaso_mpap_post"] = None
        ui["vaso_response_desc"] = rng.choice([
            "Kein signifikanter Abfall des mPAP.",
            "Vasoreaktivitätskriterium erreicht (Abfall mPAP, CO stabil).",
        ])
    else:
        ui["vaso_substance"] = ""
        ui["vaso_mpap_pre"] = None
        ui["vaso_mpap_post"] = None
        ui["vaso_response_desc"] = ""

    # --- Stufenoxymetrie/Step-up (Shunt) ---
    if scen == "shunt_asd":
        ui["sat_svc"] = 65
        ui["sat_ivc"] = 70
        ui["sat_ra"] = 80
        ui["sat_rv"] = 80
        ui["sat_pa"] = 80
        ui["sat_ao"] = 96
    else:
        ui["sat_svc"] = None
        ui["sat_ivc"] = None
        ui["sat_ra"] = None
        ui["sat_rv"] = None
        ui["sat_pa"] = None
        ui["sat_ao"] = None

    # --- Kurvenflags ---
    ui["wedge_v_wave"] = (scen in ("hfpef_ipcph", "cpcph")) and (rng.random() < 0.5)
    ui["wedge_a_wave"] = (scen in ("hfpef_ipcph", "cpcph")) and (rng.random() < 0.35)
    ui["rap_a_wave"] = rng.random() < 0.2
    ui["rap_v_wave"] = rng.random() < 0.15
    ui["rv_pseudo_dip"] = rng.random() < 0.1
    ui["rv_dip_plateau"] = rng.random() < 0.05

    # --- Infekt/Immunologie (v.a. ILD) ---
    ui["virology_pos"] = rng.choice([False, False, True])
    ui["virology_desc"] = "HIV positiv." if ui["virology_pos"] else ""
    ui["immunology_pos"] = (scen == "ild_ph") and rng.choice([False, True])
    ui["immunology_desc"] = "ANA/ENA auffällig." if ui["immunology_pos"] else ""

    # --- Procedere/Module ---
    ui["procedere_free"] = ""
    ui["modules"] = []

    # Sichtbare Demo-Auswahl: ein paar Module passend zum Beispiel
    if scen == "cteph":
        ui["modules"] = ["P10"]
    elif scen == "ild_ph":
        ui["modules"] = ["P12"]
    elif scen in ("hfpef_ipcph", "cpcph"):
        ui["modules"] = ["P09"]
    elif scen == "shunt_asd":
        ui["modules"] = ["P01"]
    elif scen == "pah_pre":
        ui["modules"] = ["P14"]

    # Optional: Schwangerschaft-Modul gelegentlich vorselektieren (nur wenn weiblich und <= 50)
    if sex == "weiblich" and age <= 50 and rng.random() < 0.15:
        ui["modules"] = list(dict.fromkeys(ui["modules"] + ["P21"]))

    # Optional: Anämie-Modul vorselektieren, wenn Hb tatsächlich niedrig ist
    hb = _safe_float(ui.get("hb_g_dl"))
    hb_low = 13.0 if sex == "männlich" else 12.0
    if hb is not None and hb < hb_low:
        ui["modules"] = list(dict.fromkeys(ui["modules"] + ["P13"]))

    # --- Vor-RHK (gelegentlich) ---
    if rng.random() < 0.35:
        ui["prev_rhk_date"] = rng.choice(["03/21", "11/22", "06/23"])
        ui["prev_label"] = rng.choice(["stabiler Verlauf", "leicht progredient", "gebessert"])
        ui["prev_mpap"] = rng.choice([18, 24, 30])
        ui["prev_pawp"] = rng.choice([7, 12, 18])
        ui["prev_ci"] = rng.choice([2.1, 2.8, 3.2])
        ui["prev_pvr"] = rng.choice([1.5, 2.6, 4.2])
    else:
        ui["prev_rhk_date"] = ""
        ui["prev_label"] = ""
        ui["prev_mpap"] = None
        ui["prev_pawp"] = None
        ui["prev_ci"] = None
        ui["prev_pvr"] = None

    return ui





# =============================================================================
# JSON export/import helpers
# =============================================================================

def markdown_to_plain(md: Any) -> str:
    """Best-effort Markdown -> plain text.

    Goal: copy/paste into Arztbrief systems without formatting artifacts.
    This is intentionally conservative and avoids clever formatting.
    """
    try:
        s = "" if md is None else str(md)
    except Exception:
        return ""

    # Normalize line endings
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Remove code fences (keep content)
    s = re.sub(r"```[a-zA-Z0-9_-]*\n", "", s)
    s = s.replace("```", "")

    # Tables: replace pipes with tabs and strip separator rows
    lines: List[str] = []
    for ln in s.split("\n"):
        if re.match(r"^\s*\|?\s*[:-]+\s*\|", ln):
            continue
        if "|" in ln:
            ln = ln.strip().strip("|")
            ln = "\t".join([c.strip() for c in ln.split("|")])
        lines.append(ln)
    s = "\n".join(lines)

    # Headings: strip leading hashes
    s = re.sub(r"^\s{0,3}#{1,6}\s+", "", s, flags=re.M)

    # Bold/italic/underline markers
    s = s.replace("**", "").replace("__", "").replace("*", "").replace("_", "")

    # Links: [text](url) -> text
    s = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1", s)

    # Inline code
    s = s.replace("`", "")

    # Collapse extra spaces but keep intentional newlines
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()



def markdown_to_word_html(md: Any) -> str:
    """Best-effort Markdown -> HTML fragment suitable for pasting into MS Word.

    Notes:
    - Preserves headings, paragraphs, simple lists, and simple tables.
    - Avoids italics (no <em>) by stripping single * / _ emphasis.
    - Uses minimal inline styling to match Word defaults.

    Returns a full HTML document string. For clipboard usage, it includes
    <!--StartFragment--> / <!--EndFragment--> markers.
    """
    import html as _html

    try:
        s = "" if md is None else str(md)
    except Exception:
        s = ""

    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # Remove code fences (keep content)
    s = re.sub(r"```[a-zA-Z0-9_-]*\n", "", s)
    s = s.replace("```", "")

    # Inline helpers
    def _inline(x: str) -> str:
        x = "" if x is None else str(x)

        # Links: [text](url) -> text
        x = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1", x)

        # Bold: **text** or __text__
        BOPEN = "@@BOPEN@@"
        BCLOSE = "@@BCLOSE@@"
        x = re.sub(r"\*\*(.+?)\*\*", lambda m: f"{BOPEN}{m.group(1)}{BCLOSE}", x)
        x = re.sub(r"__(.+?)__", lambda m: f"{BOPEN}{m.group(1)}{BCLOSE}", x)

        # Italics: *text* or _text_ (single markers only)
        x = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", lambda m: m.group(1), x)
        x = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", lambda m: m.group(1), x)

        # Inline code: `x` -> x
        x = x.replace("`", "")

        # Escape HTML
        x = _html.escape(x, quote=False)

        # Restore bold placeholders
        x = x.replace(BOPEN, "<strong>").replace(BCLOSE, "</strong>")
        return x

    lines = s.split("\n")

    out = []
    out.append("<html><body>")
    out.append("<!--StartFragment-->")
    out.append("<div style=\"font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.25;\">")

    i = 0
    in_ul = False
    in_ol = False
    in_table = False

    def _close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def _close_table():
        nonlocal in_table
        if in_table:
            out.append("</table>")
            in_table = False

    # Paragraph buffer
    para: list[str] = []

    def _flush_para():
        nonlocal para
        if not para:
            return
        _close_lists()
        _close_table()
        txt = _inline(" ".join([p.strip() for p in para if p.strip()]))
        if txt:
            out.append(f"<p>{txt}</p>")
        para = []

    def _is_table_sep(ln: str) -> bool:
        # e.g. |---|:---:|
        return bool(re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", ln))

    while i < len(lines):
        ln = lines[i]
        raw_ln = ln
        ln = ln.rstrip("\n")
        stripped = ln.strip()

        # Blank line flushes paragraph
        if stripped == "":
            _flush_para()
            i += 1
            continue

        # Headings
        hm = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", ln)
        if hm:
            _flush_para()
            _close_lists()
            _close_table()
            level = min(len(hm.group(1)), 4)
            text_h = _inline(hm.group(2).strip())
            out.append(f"<h{level}>{text_h}</h{level}>")
            i += 1
            continue

        # Tables (pipe tables)
        if "|" in stripped and stripped.count("|") >= 2:
            # detect contiguous table block
            # start only if next line is separator OR looks like table row and we are already in table
            nxt = lines[i+1].strip() if i + 1 < len(lines) else ""
            if in_table or _is_table_sep(nxt):
                _flush_para()
                _close_lists()
                if not in_table:
                    out.append("<table border=\"1\" cellspacing=\"0\" cellpadding=\"4\" style=\"border-collapse:collapse;\">")
                    in_table = True
                # Skip separator rows
                if _is_table_sep(stripped):
                    i += 1
                    continue
                row = stripped.strip("|")
                cells = [c.strip() for c in row.split("|")]
                # Header heuristic: if next line is separator and we're at start of table
                is_header = False
                if i + 1 < len(lines) and _is_table_sep(lines[i+1].strip()):
                    # This line is header
                    is_header = True
                tag = "th" if is_header else "td"
                out.append("<tr>" + "".join([f"<{tag}>{_inline(c)}</{tag}>" for c in cells]) + "</tr>")
                i += 1
                continue

        # Unordered list
        m_ul = re.match(r"^\s*[-•\*]\s+(.*)$", ln)
        if m_ul:
            _flush_para()
            _close_table()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(m_ul.group(1).strip())}</li>")
            i += 1
            continue

        # Ordered list
        m_ol = re.match(r"^\s*\d+\.\s+(.*)$", ln)
        if m_ol:
            _flush_para()
            _close_table()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(m_ol.group(1).strip())}</li>")
            i += 1
            continue

        # Default: paragraph line
        para.append(raw_ln)
        i += 1

    _flush_para()
    _close_lists()
    _close_table()

    out.append("</div>")
    out.append("<!--EndFragment-->")
    out.append("</body></html>")
    return "\n".join(out)


def extract_markdown_section(md: Any, start_heading: str, end_heading: Optional[str] = None) -> str:
    """Extract a section from markdown by headings (best-effort).

    Returns the substring starting at the first occurrence of start_heading
    (as a Markdown heading line) until end_heading (exclusive) if provided.
    """
    try:
        s = "" if md is None else str(md)
    except Exception:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Match headings like "## Rechtsherzkatheter"
    start_pat = re.compile(rf"^\s*#+\s*{re.escape(start_heading)}\s*$", re.M)
    m = start_pat.search(s)
    if not m:
        # fallback: plain substring search
        idx = s.find(start_heading)
        if idx < 0:
            return s
        s2 = s[idx:]
        if end_heading and end_heading in s2:
            return s2.split(end_heading, 1)[0]
        return s2

    start_idx = m.start()
    s2 = s[start_idx:]
    if end_heading:
        end_pat = re.compile(rf"^\s*#+\s*{re.escape(end_heading)}\s*$", re.M)
        m2 = end_pat.search(s2)
        if m2:
            return s2[:m2.start()].strip()
        # fallback substring
        if end_heading in s2:
            return s2.split(end_heading, 1)[0].strip()
    return s2.strip()


def build_summary_dict(case: Dict[str, Any], rulebook_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Structured, stable JSON summary for studies/registries/QA."""
    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    scores = case.get("scores") or {}
    dec = case.get("decision") or {}
    warns = case.get("warnings") or []

    def _num(x: Any) -> Optional[float]:
        try:
            if x is None or x == "":
                return None
            return float(x)
        except Exception:
            return None

    # Slim warnings (message + severity + code if present)
    wslim: List[Dict[str, Any]] = []
    if isinstance(warns, list):
        for w in warns:
            if not isinstance(w, dict):
                continue
            wslim.append(
                {
                    "severity": w.get("severity"),
                    "code": w.get("code"),
                    "message": w.get("message"),
                }
            )

    rb = rulebook_meta or {}
    rb_meta = {
        "version": (rb.get("version") if isinstance(rb, dict) else None),
        "updated": (rb.get("updated") if isinstance(rb, dict) else None),
    }

    # Dates
    today = _dt.datetime.now().isoformat(timespec="seconds")

    # Core hemodynamics
    hemo = {
        "rap_rest_mmHg": _num(der.get("rap_rest")),
        "spap_rest_mmHg": _num(der.get("spap_rest")),
        "dpap_rest_mmHg": _num(der.get("dpap_rest")),
        "mpap_rest_mmHg": _num(der.get("mpap_rest")),
        "pawp_rest_mmHg": _num(der.get("pawp_rest")),
        "co_rest_L_min": _num(der.get("co")),
        "ci_rest_L_min_m2": _num(der.get("ci")),
        "pvr_rest_WU": _num(der.get("pvr_rest")),
        "pvri_rest_WU_m2": _num(der.get("pvri")),
        "tpg_mmHg": _num(der.get("tpg")),
        "dpg_mmHg": _num(der.get("dpg")),
    }

    # Classification / risk
    classification = {
        "hemo_category": der.get("hemo_category"),
        "primary_dx": dec.get("primary_dx"),
        "bundle": dec.get("bundle"),
        "risk_category": der.get("risk_category"),
        "esc_ers_4s": scores.get("esc_ers_4s"),
        "esc_ers_3s": scores.get("esc_ers_3s"),
        "reveal_lite2": scores.get("reveal_lite2"),
        "reveal_lite2_points": scores.get("reveal_lite2_points"),
    }

    # Echo snapshot (only the main fields used in patient echo report)
    echo = {
        "lvef_percent": _num(ui.get("lvef")),
        "tapse_mm": _num(ui.get("tapse_mm")),
        "s_prime_cm_s": _num(ui.get("s_prime_cm_s")),
        "pasp_echo_mmHg": _num(ui.get("pasp_echo")),
        "ra_esa_cm2": _num(ui.get("ra_esa_cm2")),
        "ee_ratio": _num(ui.get("ee_ratio")),
        "trv_ms": _num(ui.get("trv_ms")),
    }

    labs = {
        "hb_g_dl": _num(ui.get("hb_g_dl")),
        "crp_mg_l": _num(ui.get("crp_mg_l")),
        "creatinine_mg_dl": _num(ui.get("creatinine_mg_dl")),
        "egfr_ml_min_1_73m2": _num(ui.get("egfr")),
        "bnp_kind": ui.get("bnp_kind"),
        "bnp_value_pg_ml": _num(ui.get("bnp_value")),
    }

    patient = {
        "firstname": ui.get("firstname"),
        "name": ui.get("name"),
        "age_years": _num(ui.get("age")),
        "sex": ui.get("sex"),
        "height_cm": _num(ui.get("height_cm")),
        "weight_kg": _num(ui.get("weight_kg")),
    }

    context = {
        "who_fc": ui.get("who_fc"),
        "six_mwd_m": _num(ui.get("six_mwd_m")),
        "story": ui.get("story"),
        "ph_known": ui.get("ph_known"),
        "ph_suspected": ui.get("ph_suspected"),
        "ph_known_dx": ui.get("ph_known_dx"),
    }

    procedere = {
        "modules_selected": ui.get("modules") or [],
        "procedere_free": ui.get("procedere_free") or "",
    }

    return {
        "schema": "rhk_summary_v1",
        "generated_at": today,
        "app_version": APP_VERSION,
        "rulebook": rb_meta,
        "patient": patient,
        "context": context,
        "hemodynamics": hemo,
        "classification": classification,
        "echo": echo,
        "labs": labs,
        "procedere": procedere,
        "warnings": wslim,
    }


def export_json(case: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    return path


def export_summary_json(summary: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path


def load_case_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

