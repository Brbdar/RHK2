#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-RHK one-page PDF overview (A4 landscape).

Purpose
- Print immediately BEFORE right-heart catheterization.
- Show only essential information already available pre-procedure.
- No recommendations, no therapy, no RHK result interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import os
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors


def _get(d: Any, key: str, default=None):
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def _fmt_num(val, ndigits: int = 0) -> Optional[str]:
    try:
        if val is None:
            return None
        f = float(val)
        if ndigits == 0:
            if abs(f - round(f)) < 1e-6:
                return str(int(round(f)))
            return f"{f:.1f}"
        return f"{f:.{ndigits}f}"
    except Exception:
        return None


def _fmt(val, unit: str = "", ndigits: int = 0) -> Optional[str]:
    s = _fmt_num(val, ndigits=ndigits)
    if s is None:
        return None
    return f"{s}{(' ' + unit) if unit else ''}"


def _arrow(flag: Optional[str]) -> str:
    # flag in {"up","down","warn","bad",None}
    return {"up": "↑", "down": "↓", "warn": "⚠", "bad": "⬆"}.get(flag or "", "")


def _is_truthy(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, bool):
        return bool(x)
    s = str(x).strip().lower()
    return s in {"1","true","yes","ja","y","j"}


def _pick_top(items: List[str], n: int) -> List[str]:
    out=[]
    for it in items:
        it=str(it).strip()
        if not it or it.lower() in {"keine","keine angabe","-"}:
            continue
        if it not in out:
            out.append(it)
        if len(out) >= n:
            break
    return out


def _draw_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str):
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 6*mm, y + h - 8*mm, title)


def _draw_kv_lines(c: canvas.Canvas, x: float, y_top: float, lines: List[Tuple[str,str]], line_h: float = 6.2*mm, max_lines: int = 10, font_size: int = 10):
    c.setFont("Helvetica", font_size)
    y = y_top
    shown=0
    for k,v in lines:
        if shown >= max_lines:
            break
        if not v:
            continue
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x, y, k)
        c.setFillColor(colors.black)
        c.drawRightString(x + 80*mm, y, v)
        y -= line_h
        shown += 1
    return y


def _chip(c: canvas.Canvas, x: float, y: float, text: str):
    # small rounded label
    pad_x = 3.2*mm
    pad_y = 1.6*mm
    c.setFont("Helvetica", 9)
    tw = c.stringWidth(text, "Helvetica", 9)
    w = tw + 2*pad_x
    h = 6.2*mm
    c.setFillColor(colors.HexColor("#f0f0f0"))
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.drawString(x + pad_x, y + pad_y, text)
    return x + w + 2*mm


def generate_prerhk_pdf(case_state: Dict[str, Any]) -> str:
    """Create the Pre-RHK overview PDF and return a file path."""
    if not isinstance(case_state, dict):
        raise ValueError("case_state must be a dict")

    ui = _get(case_state, "ui", {}) or {}
    der = _get(case_state, "derived", {}) or {}

    # --- Header essentials (datensparsam) ---
    # Prefer IDs over names; fall back to case filename.
    case_name = str(_get(case_state, "case_filename", "") or _get(case_state, "filename", "") or "").strip()
    pid = str(ui.get("patient_id") or ui.get("pat_id") or ui.get("register_nr") or ui.get("register") or "").strip()
    fid = str(ui.get("fall_id") or ui.get("case_id") or "").strip()
    id_line = " ".join([p for p in [pid and f"ID: {pid}", fid and f"Fall: {fid}"] if p]) or (case_name and f"Fall: {case_name}") or "Fall: (ohne ID)"

    age = ui.get("age") or ui.get("alter") or ui.get("patient_age")
    sex = ui.get("sex") or ui.get("geschlecht") or ui.get("patient_sex")
    demo_line = " ".join([p for p in [age and f"{_fmt_num(age)} J", sex and str(sex)] if p]).strip()

    indication = str(ui.get("rhk_indication") or ui.get("indication") or ui.get("anlass") or ui.get("fragestellung") or "RHK – Pre Check").strip()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # --- Clinic essentials (max 6 bullets) ---
    clinic_lines: List[str] = []

    who_fc = ui.get("who_fc") or ui.get("nyha") or ui.get("nyha_class") or ui.get("who_functional_class")
    if who_fc:
        clinic_lines.append(f"WHO FC: {who_fc}")
    syncope = ui.get("syncope") or ui.get("syncope_present")
    if syncope is not None and str(syncope).strip() != "":
        clinic_lines.append(f"Synkope: {'ja' if _is_truthy(syncope) else 'nein'}")
    edema = ui.get("edema") or ui.get("edema_present") or ui.get("oedema")
    if edema is not None and str(edema).strip() != "":
        clinic_lines.append(f"Ödeme: {'ja' if _is_truthy(edema) else 'nein'}")
    o2 = ui.get("o2_need") or ui.get("o2_l_min") or ui.get("o2_ltot") or ui.get("oxygen_l_min")
    if o2 is not None and str(o2).strip() != "":
        clinic_lines.append(f"O₂: {o2}")
    # comorbidities (try list-like fields)
    com_list = ui.get("comorbidities") or ui.get("preexisting") or ui.get("vordiagnosen") or ui.get("comorbidities_list") or []
    if isinstance(com_list, str):
        com_list = [s.strip() for s in com_list.split(",") if s.strip()]
    if isinstance(com_list, (list, tuple)):
        top = _pick_top([str(x) for x in com_list], 3)
        if top:
            clinic_lines.append("Vorerkr.: " + "; ".join(top))
    # meds (very compact)
    meds = ui.get("meds") or ui.get("medication") or ui.get("therapy") or ui.get("meds_list") or []
    if isinstance(meds, str):
        meds = [s.strip() for s in meds.split(",") if s.strip()]
    if isinstance(meds, (list, tuple)):
        topm = _pick_top([str(x) for x in meds], 3)
        if topm:
            clinic_lines.append("Meds: " + "; ".join(topm))

    clinic_lines = clinic_lines[:6]

    # --- Echo essentials (RH / PH) ---
    # Use only fields already present in UI and used elsewhere.
    def _echo_line(label: str, val: Any, unit: str = "", nd: int = 0):
        s = _fmt(val, unit=unit, ndigits=nd)
        return (label, s or "")

    echo_pairs: List[Tuple[str,str]] = []
    # RV function
    tapse = ui.get("tapse_mm")
    sprime = ui.get("s_prime_cm_s")
    rvfac = ui.get("rvfac_pct")
    rvef3d = ui.get("rv_3d_ef_pct")
    echo_pairs.append(_echo_line("TAPSE", tapse, "mm", 0))
    echo_pairs.append(_echo_line("S′", sprime, "cm/s", 1))
    if rvef3d is not None and str(rvef3d).strip() != "":
        echo_pairs.append(_echo_line("3D RVEF", rvef3d, "%", 0))
    else:
        echo_pairs.append(_echo_line("RV FAC", rvfac, "%", 0))

    # PH signs
    trv = ui.get("trv_ms")
    pasp = ui.get("pasp_echo")
    paat = ui.get("paat_ms")
    sept = ui.get("septal_flattening")
    notch = ui.get("rvot_notch")
    if trv is not None and str(trv).strip() != "":
        echo_pairs.append(_echo_line("TR Vmax", trv, "m/s", 1))
    if pasp is not None and str(pasp).strip() != "":
        echo_pairs.append(_echo_line("sPAP/RVSP", pasp, "mmHg", 0))
    if paat is not None and str(paat).strip() != "":
        echo_pairs.append(_echo_line("PAAT", paat, "ms", 0))
    if sept is not None and str(sept).strip() != "":
        echo_pairs.append(("Septum", str(sept)))
    if notch is not None and str(notch).strip() != "":
        echo_pairs.append(("RVOT notch", str(notch)))

    # congestion / RA IVC
    ra_esa = ui.get("ra_esa_cm2")
    ivc_d = ui.get("ivc_diam_mm")
    ivc_ci = ui.get("ivc_collapse_index_pct")
    rap_est = ui.get("rap_estimate") or ui.get("rap_est") or ui.get("rap_echo")
    if ra_esa is not None and str(ra_esa).strip() != "":
        echo_pairs.append(_echo_line("RA ESA", ra_esa, "cm²", 0))
    if ivc_d is not None and str(ivc_d).strip() != "":
        echo_pairs.append(_echo_line("IVC", ivc_d, "mm", 0))
    if ivc_ci is not None and str(ivc_ci).strip() != "":
        echo_pairs.append(_echo_line("IVC Kollaps", ivc_ci, "%", 0))
    if rap_est is not None and str(rap_est).strip() != "":
        echo_pairs.append(("RAP Schätzung", str(rap_est)))

    peri = ui.get("pericardial_effusion")
    if peri is not None and str(peri).strip() != "":
        echo_pairs.append(("Perikarderguss", "ja" if _is_truthy(peri) else "nein"))

    # remove empty
    echo_pairs = [(k,v) for k,v in echo_pairs if v]

    # limit to keep non-overloaded
    echo_pairs = echo_pairs[:10]

    # --- Lab & risk essentials ---
    lab_pairs: List[Tuple[str,str]] = []

    ntprobnp = ui.get("ntprobnp") or ui.get("nt_pro_bnp") or ui.get("ntprobnp_pg_ml") or der.get("ntprobnp") if isinstance(der, dict) else None
    hb = ui.get("hb") or ui.get("hemoglobin") or ui.get("hb_g_dl")
    crea = ui.get("creatinine_mg_dl")
    egfr = ui.get("egfr") or ui.get("egfr_ml_min_1_73")
    trop = ui.get("troponin") or ui.get("hs_troponin")
    inr = ui.get("inr")
    plt = ui.get("platelets_g_l")

    if ntprobnp is not None and str(ntprobnp).strip() != "":
        lab_pairs.append(_echo_line("NT-proBNP", ntprobnp, "", 0))
    if hb is not None and str(hb).strip() != "":
        lab_pairs.append(_echo_line("Hb", hb, "", 1))
    if egfr is not None and str(egfr).strip() != "":
        lab_pairs.append(_echo_line("eGFR", egfr, "", 0))
    elif crea is not None and str(crea).strip() != "":
        lab_pairs.append(_echo_line("Krea", crea, "mg/dL", 2))
    if trop is not None and str(trop).strip() != "":
        lab_pairs.append(_echo_line("Troponin", trop, "", 0))
    if inr is not None and str(inr).strip() != "":
        lab_pairs.append(_echo_line("INR", inr, "", 2))
    if plt is not None and str(plt).strip() != "":
        lab_pairs.append(_echo_line("Thrombos", plt, "G/L", 0))

    # anticoag / allergies in sticky header
    anticoag_status = ui.get("anticoag_status")
    anticoag_substance = ui.get("anticoag_substance")
    if anticoag_status and str(anticoag_status).strip().lower() not in {"keine angabe","-"}:
        s = str(anticoag_status)
        if anticoag_substance and str(anticoag_substance).strip().lower() not in {"keine angabe","-"}:
            s = f"{s} – {anticoag_substance}"
        lab_pairs.append(("Antikoag.", s))

    allergies_present = ui.get("allergies_present")
    allergies_list = ui.get("allergies_list") or []
    if _is_truthy(allergies_present):
        if isinstance(allergies_list, str):
            allergies_list = [s.strip() for s in allergies_list.split(",") if s.strip()]
        if isinstance(allergies_list, (list, tuple)):
            s = ", ".join(_pick_top([str(x) for x in allergies_list], 3)) or "ja"
        else:
            s = "ja"
        lab_pairs.append(("Allergien", s))

    lab_pairs = [(k,v) for k,v in lab_pairs if v][:10]

    # --- Flags (only if clearly relevant) ---
    flags: List[str] = []
    # Low forward output suspicion: CI or SVI low if present in UI/derived
    ci = ui.get("ci_rest") or ui.get("ci") or (der.get("ci_rest") if isinstance(der, dict) else None)
    svi = ui.get("svi_rest_ml_m2") or (der.get("svi_rest_ml_m2") if isinstance(der, dict) else None)
    try:
        if ci is not None and float(ci) < 2.0:
            flags.append("⚠ Low output")
    except Exception:
        pass
    try:
        if (svi is not None) and float(svi) < 31:
            if "⚠ Low output" not in flags:
                flags.append("⚠ Low output")
    except Exception:
        pass
    # Renal function
    try:
        if egfr is not None and float(egfr) < 45:
            flags.append("⚠ Niere")
    except Exception:
        pass
    # O2 need high
    try:
        if o2 is not None and float(str(o2).replace(",",".")) >= 4:
            flags.append("⚠ O₂")
    except Exception:
        pass
    # RV function flag if TAPSE very low
    try:
        if tapse is not None and float(tapse) < 14:
            flags.append("⚠ RV Funktion")
    except Exception:
        pass
    # anticoag active
    if anticoag_status and str(anticoag_status).lower() in {"ja","yes","true","1"}:
        flags.append("⚠ Antikoag.")

    flags = flags[:4]

    # --- Create PDF ---
    fd, out_path = tempfile.mkstemp(prefix="prerhk_", suffix=".pdf")
    os.close(fd)

    w, h = landscape(A4)
    c = canvas.Canvas(out_path, pagesize=(w, h))

    # Page margins
    mx = 12 * mm
    my = 10 * mm

    # Header band
    header_h = 20 * mm
    c.setFillColor(colors.HexColor("#f5f5f5"))
    c.rect(mx, h - my - header_h, w - 2*mx, header_h, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(mx + 6*mm, h - my - 7*mm, "Pre-RHK Kurzübersicht")

    c.setFont("Helvetica", 10)
    c.drawString(mx + 6*mm, h - my - 14*mm, id_line + (" · " + demo_line if demo_line else ""))

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w/2, h - my - 12*mm, indication)

    c.setFont("Helvetica", 10)
    c.drawRightString(w - mx - 6*mm, h - my - 14*mm, now)

    # Body layout
    body_top = h - my - header_h - 6*mm
    body_bottom = my + 18*mm
    col_gap = 6*mm
    col_w = (w - 2*mx - 2*col_gap) / 3.0
    col_h = body_top - body_bottom

    # Column boxes
    x1 = mx
    x2 = mx + col_w + col_gap
    x3 = mx + 2*(col_w + col_gap)

    y0 = body_bottom

    _draw_box(c, x1, y0, col_w, col_h, "Klinik")
    _draw_box(c, x2, y0, col_w, col_h, "Echo Essentials")
    _draw_box(c, x3, y0, col_w, col_h, "Labor & Risiko")

    # Clinic bullets
    c.setFont("Helvetica", 10)
    y = y0 + col_h - 16*mm
    for line in clinic_lines:
        c.drawString(x1 + 8*mm, y, f"• {line}")
        y -= 6.2*mm

    # Echo key values (compact)
    c.setFont("Helvetica", 10)
    y = y0 + col_h - 16*mm
    for k, v in echo_pairs:
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x2 + 8*mm, y, k)
        c.setFillColor(colors.black)
        c.drawRightString(x2 + col_w - 8*mm, y, v)
        y -= 6.0*mm

    # Lab values
    c.setFont("Helvetica", 10)
    y = y0 + col_h - 16*mm
    for k, v in lab_pairs:
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x3 + 8*mm, y, k)
        c.setFillColor(colors.black)
        c.drawRightString(x3 + col_w - 8*mm, y, v)
        y -= 6.0*mm

    # Flags bar
    bar_h = 12*mm
    c.setFillColor(colors.HexColor("#ffffff"))
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(mx, my, w - 2*mx, bar_h, 6, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(mx + 6*mm, my + 4*mm, "Flags vor RHK:")
    x = mx + 32*mm
    for f in flags:
        x = _chip(c, x, my + 3*mm, f)

    c.showPage()
    c.save()
    return out_path
