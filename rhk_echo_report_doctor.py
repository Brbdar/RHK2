#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo Report Builder – Arztbericht (Echo-Teil).

WICHTIG
- Diese Datei enthält ausschließlich die Logik zur Textgenerierung des Echo-Reports.
- Keine UI/Import-Logik, keine stillen Datenübernahmen, keine Überschreibung manueller Eingaben.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

from rhk_echo_guidelines import (
    severity,
    fmt_value,
    label_for,
    unit_for,
)

_SEV_TXT = {
    "g": "unauffällig",
    "y": "grenzwertig",
    "r": "auffällig",
}


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        x = float(v)
        if x != x:  # NaN
            return None
        # Echo: 0/0.0 wird als fehlend behandelt (kein stilles "0")
        if abs(x) < 1e-12:
            return None
        return x
    except Exception:
        return None


def _fmt(key: str, v: Any, digits: int = 0) -> str:
    u = unit_for(key)
    s = fmt_value(v, digits=digits)
    if u:
        return f"{s} {u}".strip()
    return s


def _sev_phrase(key: str, v: Any) -> str:
    s = severity(key, v)
    if not s:
        return ""
    return _SEV_TXT.get(s, "")


def _rap_estimate(ivc_diam_mm: Any, ivc_collapse: Any, ivc_collapse_index_pct: Any) -> Tuple[Optional[int], str]:
    """Very conservative RAP estimate (mmHg) based on IVC size/collapse.
    Returns (rap_mmHg, note).
    """
    d = _as_float(ivc_diam_mm)
    ci = _as_float(ivc_collapse_index_pct)
    # ivc_collapse is usually yes/no; in guidelines: yes -> g, no -> r.
    collapse_yes = None
    if isinstance(ivc_collapse, str):
        c = ivc_collapse.strip().lower()
        if c in {"ja", "yes", "y", "true", "1"}:
            collapse_yes = True
        elif c in {"nein", "no", "n", "false", "0"}:
            collapse_yes = False
    elif isinstance(ivc_collapse, bool):
        collapse_yes = bool(ivc_collapse)

    # If collapse index provided, derive yes/no with common cutoff ~50%
    if collapse_yes is None and ci is not None:
        collapse_yes = True if ci >= 50 else False

    if d is None and collapse_yes is None:
        return None, "RAP nicht abschätzbar (IVC-Daten fehlen)."

    # ASE-ish: small + collapsible -> 3, large + not collapsible -> 15, else 8
    if d is not None and d <= 21 and collapse_yes is True:
        return 3, "RAP-Schätzung über IVC: klein und kollabierend."
    if d is not None and d > 21 and collapse_yes is False:
        return 15, "RAP-Schätzung über IVC: dilatiert und nicht kollabierend."
    return 8, "RAP-Schätzung über IVC: intermediär/unklar (Standardannahme)."


def _ph_screening_summary(ui: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Return (headline, bullet_lines) for PH screening based on echo."""
    trv = _as_float(ui.get("trv_ms"))
    pasp = _as_float(ui.get("pasp_echo"))
    paat = _as_float(ui.get("paat_ms"))
    rvot_notch = ui.get("rvot_notch")
    sept_flat = ui.get("septal_flattening")
    peric = ui.get("pericardial_effusion")
    ivc_coll = ui.get("ivc_collapse")

    signs = 0
    def _is_yes(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"ja", "yes", "y", "true", "1"}
        return False

    # supportive signs (very conservative)
    if _is_yes(rvot_notch):
        signs += 1
    if isinstance(sept_flat, str) and sept_flat.strip():
        # any documented septal flattening counts
        signs += 1
    if paat is not None and paat < 105:
        signs += 1
    if _is_yes(peric):
        signs += 1
    if ivc_coll is not None:
        # ivc_collapse yes -> lower RAP; no -> higher RAP. Non-collapse supports congestion.
        if isinstance(ivc_coll, str) and ivc_coll.strip().lower() in {"nein", "no", "n", "false", "0"}:
            signs += 1

    if trv is None and pasp is None:
        return "PH Echo-Screening nicht beurteilbar", ["TRV/PASP nicht dokumentiert."]

    # ESC/ERS probability (simplified)
    if trv is not None:
        if trv > 3.4:
            level = "hohe Wahrscheinlichkeit"
        elif trv >= 2.9:
            level = "intermediäre Wahrscheinlichkeit" if signs == 0 else "intermediär bis hoch"
        else:
            level = "niedrige Wahrscheinlichkeit" if signs == 0 else "niedrig bis intermediär"
    else:
        # fallback to PASP only (less robust)
        if pasp is not None and pasp >= 50:
            level = "intermediär bis hoch (PASP-basiert)"
        elif pasp is not None and pasp >= 36:
            level = "intermediär (PASP-basiert)"
        else:
            level = "eher niedrig (PASP-basiert)"

    bullets: List[str] = []
    if trv is not None:
        bullets.append(f"TR Vmax: {_fmt('trv_ms', trv, digits=2)}")
    if pasp is not None:
        bullets.append(f"sPAP/PASP (Echo): {_fmt('pasp_echo', pasp)}")
    if paat is not None:
        bullets.append(f"PAAT: {_fmt('paat_ms', paat)}")
    if signs:
        bullets.append(f"Zusätzliche Druck/Belastungszeichen: {signs} Hinweis(e)")
    return f"Echo spricht {('für' if 'hoch' in level or 'intermediär' in level else 'eher gegen')} PH ({level})", bullets


def build_echo_doctor_report(case: Dict[str, Any]) -> str:
    """Build structured echo report for clinicians (German)."""
    ui: Dict[str, Any] = case.get("ui", {}) or {}
    if not ui.get("echo_done") and not ui.get("cmr_done"):
        return "## Echo (Arztbericht)\n\nEs sind aktuell keine Echo Werte dokumentiert.\n"

    out: List[str] = []
    out.append("## Echo (Arztbericht)")
    out.append("")
    out.append("Hinweis: Echo ist ein Screening-Instrument. Druck- und Widerstandsdiagnostik sowie Therapieentscheidungen bei PH benötigen die klinische Gesamtschau und, falls indiziert, den RHK.")
    out.append("")
    # --- RV size/function
    tapse = ui.get("tapse_mm")
    sp = ui.get("s_prime_cm_s")
    fac = ui.get("rvfac_pct")
    rvef3d = ui.get("rv_3d_ef_pct")
    fwls = ui.get("rv_fwls_pct")
    tapse_spap = ui.get("tapse_spap_ratio")

    rv_items = []
    if _as_float(tapse) is not None:
        rv_items.append(f"TAPSE: {_fmt('tapse_mm', tapse)} ({_sev_phrase('tapse_mm', tapse)})")
    if _as_float(fac) is not None:
        rv_items.append(f"RV FAC: {_fmt('rvfac_pct', fac)} ({_sev_phrase('rvfac_pct', fac)})")
    if _as_float(sp) is not None:
        rv_items.append(f"S' (TDI): {_fmt('s_prime_cm_s', sp, digits=1)} ({_sev_phrase('s_prime_cm_s', sp)})")
    if _as_float(rvef3d) is not None:
        rv_items.append(f"3D RVEF: {_fmt('rv_3d_ef_pct', rvef3d)} ({_sev_phrase('rv_3d_ef_pct', rvef3d)})")
    if _as_float(fwls) is not None:
        rv_items.append(f"RV FWLS: {_fmt('rv_fwls_pct', fwls)} ({_sev_phrase('rv_fwls_pct', fwls)})")
    if _as_float(tapse_spap) is not None:
        rv_items.append(f"TAPSE/sPAP: {_fmt('tapse_spap_ratio', tapse_spap, digits=2)} ({_sev_phrase('tapse_spap_ratio', tapse_spap)})")

    if rv_items:
        out.append("### RV Größe und Funktion")
        out.append("- " + "\n- ".join(rv_items))
        # short interpretation
        red = any(severity(k, ui.get(k)) == "r" for k in ["tapse_mm", "rvfac_pct", "s_prime_cm_s", "rv_3d_ef_pct", "rv_fwls_pct", "tapse_spap_ratio"] if ui.get(k) is not None)
        yel = any(severity(k, ui.get(k)) == "y" for k in ["tapse_mm", "rvfac_pct", "s_prime_cm_s", "rv_3d_ef_pct", "rv_fwls_pct", "tapse_spap_ratio"] if ui.get(k) is not None)
        if red:
            out.append("Interpretation: Mindestens ein Parameter spricht für eine relevante RV-Funktionsminderung. Aussage abhängig von Bildqualität und Messmethode.")
        elif yel:
            out.append("Interpretation: Hinweise auf eine grenzwertige RV-Funktion. Verlauf/Serienmessung und klinischer Kontext entscheidend.")
        else:
            out.append("Interpretation: Die dokumentierten RV-Funktionsparameter sind insgesamt unauffällig. Einzelwerte stets im Kontext der Bildqualität interpretieren.")
        out.append("")
    # --- RV pressure signs
    out.append("### RV Druckzeichen und PH Screening")
    headline, bullets = _ph_screening_summary(ui)
    out.append(f"{headline}.")
    if bullets:
        out.append("- " + "\n- ".join(bullets))

    # RVSP estimate
    trv = _as_float(ui.get("trv_ms"))
    rap, rap_note = _rap_estimate(ui.get("ivc_diam_mm"), ui.get("ivc_collapse"), ui.get("ivc_collapse_index_pct"))
    if trv is not None and rap is not None:
        rvsp = 4.0 * (trv ** 2) + float(rap)
        out.append(f"Geschätzte RVSP (aus TR Vmax + RAP): {fmt_value(rvsp, digits=0)} mmHg (RAP {rap} mmHg). {rap_note} Unsicherheit: Abhängigkeit von TR-Jet-Qualität und Annahmen.")
    elif rap_note:
        out.append(f"RAP/RVSP: {rap_note} (RVSP nur bei TR Vmax berechenbar).")

    # document other binary signs if present
    sf = (ui.get("septal_flattening") or "").strip() if isinstance(ui.get("septal_flattening"), str) else ""
    if sf:
        out.append(f"Septumkonfiguration: {sf} (Hinweis auf Druck/Volumenbelastung, unspezifisch).")

    rvot_notch = ui.get("rvot_notch")
    if rvot_notch is not None:
        out.append(f"RVOT Notch: {fmt_value(rvot_notch)} ({_sev_phrase('rvot_notch', rvot_notch)}) – Hinweis auf erhöhte pulmonale Gefäßimpedanz bei passender Konstellation.")
    out.append("")
    # --- RA / congestion
    ra_esa = ui.get("ra_esa_cm2")
    ivc_d = ui.get("ivc_diam_mm")
    ivc_ci = ui.get("ivc_collapse_index_pct")
    ivc_coll = ui.get("ivc_collapse")
    ra_items = []
    if _as_float(ra_esa) is not None:
        ra_items.append(f"RA ESA: {_fmt('ra_esa_cm2', ra_esa)} ({_sev_phrase('ra_esa_cm2', ra_esa)})")
    if _as_float(ivc_d) is not None:
        ra_items.append(f"IVC Durchmesser: {_fmt('ivc_diam_mm', ivc_d)} ({_sev_phrase('ivc_diam_mm', ivc_d)})")
    if _as_float(ivc_ci) is not None:
        ra_items.append(f"IVC Kollapsindex: {_fmt('ivc_collapse_index_pct', ivc_ci)} ({_sev_phrase('ivc_collapse_index_pct', ivc_ci)})")
    if ivc_coll is not None:
        ra_items.append(f"IVC Kollaps (qualitativ): {fmt_value(ivc_coll)} ({_sev_phrase('ivc_collapse', ivc_coll)})")
    if ra_items:
        out.append("### RA Größe und Stauungszeichen")
        out.append("- " + "\n- ".join(ra_items))
        if rap is not None:
            out.append(f"Interpretation: Stauungszeichen über IVC sprechen für RAP ca. {rap} mmHg (Schätzung). {rap_note}")
        else:
            out.append("Interpretation: Stauungsbeurteilung nur eingeschränkt möglich (RAP nicht abschätzbar).")

        out.append("")
    # --- valves (only TR/PR if present in captured fields; currently only TRV)
    out.append("### Klappen")
    if trv is not None:
        out.append("Trikuspidalklappe: TR-Jet vorhanden (TR Vmax dokumentiert). Der Regurgitationsgrad ist nicht dokumentiert und kann daher nicht sicher eingeordnet werden.")
    else:
        out.append("Trikuspidalklappe: Kein verwertbarer TR-Jet dokumentiert oder nicht gemessen (Limitation für Druckabschätzung).")

    out.append("")
    # --- pericardial effusion
    peric = ui.get("pericardial_effusion")
    if peric is not None:
        out.append("### Perikard")
        out.append(f"Perikarderguss: {fmt_value(peric)} ({_sev_phrase('pericardial_effusion', peric)}). Unsicherheit: Echogenität/Schallfenster abhängig.")
        out.append("")
    # --- final clinical wrap-up
    out.append("### Klinische Einordnung (Echo)")
    out.append("- Echo zeigt indirekte PH-Zeichen (TR Vmax, PASP, PAAT, Septum, RV Remodeling).") 
    out.append("- Bei Konstellation mit Symptomen/Belastungslimitierung: weitere Abklärung gemäß Gesamtkontext.")
    out.append("- Echo ersetzt keine hämodynamische Diagnose (RHK) und erlaubt keine sichere PVR-Bestimmung.")
    out.append("- Verlauf: Serienmessungen unter gleicher Methodik erhöhen die Aussagekraft.")
    out.append("")

    return "\n".join(out).strip() + "\n"
