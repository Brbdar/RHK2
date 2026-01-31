#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Intelligente Interpretation V3 (deterministische Textkette).

Strict principles
- Keine Annahmen: fehlende Werte werden nicht als 0 interpretiert.
- Externe Informationen nur als Vorschlag: hier nicht relevant.
- Deterministisch: Microphrases werden per stabiler Case-Signatur gewählt (keine echte Zufallsvariabilität).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional


def _sf(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        v = float(x)
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None


def _sb(x) -> bool:
    return bool(x is True)


def _seed_from_case(ui: Dict[str, Any], der: Dict[str, Any]) -> int:
    # Stable seed over a small, privacy-sparing subset.
    core = {
        "mpap": der.get("mpap_rest"),
        "pawp": der.get("pawp_rest"),
        "pvr": der.get("pvr_rest"),
        "ci": der.get("ci_rest"),
        "exercise_done": der.get("exercise_done"),
        "exercise_pattern": der.get("exercise_pattern"),
        "step_up": der.get("step_up_present"),
        "wedge_v_wave": der.get("wedge_v_wave"),
        "af": der.get("atrial_fib"),
    }
    js = str(sorted(core.items()))
    h = hashlib.blake2b(js.encode("utf-8", errors="ignore"), digest_size=8).hexdigest()
    return int(h, 16)


_MICROPHRASES = {
    "connectors": [
        "Zusätzlich zeigt sich",
        "Darüber hinaus",
        "Ergänzend imponiert",
        "Im weiteren Verlauf",
        "Unter Berücksichtigung der Messbedingungen",
    ],
    "hedges": [
        "Hinweis auf",
        "vereinbar mit",
        "konstellationstypisch für",
        "differenzialdiagnostisch",
        "am ehesten im Sinne einer",
    ],
    "qc_intro": [
        "Die Interpretation ist eingeschränkt:",
        "Methodisch limitiert:",
    ],
    "conclusion_start": [
        "In der Gesamtschau",
        "Zusammenfassend",
        "Klinisch hämodynamisches Fazit:",
    ],
}


def _pick(seq: List[str], k: int, seed: int) -> str:
    if not seq:
        return ""
    idx = (seed + (k * 1315423911)) % len(seq)
    return str(seq[idx])


def _join_sentences(parts: List[str]) -> str:
    out: List[str] = []
    for p in parts:
        p = str(p or "").strip()
        if not p:
            continue
        # Normalize whitespace
        p = " ".join(p.split())
        out.append(p)
    return " ".join(out).strip()


def build_intelligent_interpretation_v3(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    """Build V3 interpretation text.

    Output
    - A single clinician-friendly paragraph (may contain multiple sentences).
    - Deterministic selection of microphrases.
    """
    d = der or {}
    seed = _seed_from_case(ui or {}, d)

    # ---- Core values (safe) ----
    mpap = _sf(d.get("mpap_rest"))
    pawp = _sf(d.get("pawp_rest"))
    pvr = _sf(d.get("pvr_rest"))
    rap = _sf(d.get("rap_rest"))
    ci = _sf(d.get("ci_rest"))
    pac = _sf(d.get("pac_rest_ml_per_mmhg"))
    rc = _sf(d.get("rc_time_rest_s"))

    # Exercise
    exercise_done = _sb(d.get("exercise_done"))
    exercise_hardstop = _sb(d.get("exercise_hardstop"))
    dco = _sf(d.get("dco"))
    mpap_slope = _sf(d.get("mpap_co_slope"))
    pawp_slope = _sf(d.get("pawp_co_slope"))
    tpg_slope = _sf(d.get("tpg_co_slope"))
    pawp_peak = _sf(d.get("pawp_peak"))
    exercise_interp = str(d.get("exercise_interpretability") or "").strip().lower()
    ex_pattern = str(d.get("exercise_pattern") or "").strip()

    # QC flags
    wedge_v_wave = _sb(d.get("wedge_v_wave"))
    atrial_fib = _sb(d.get("atrial_fib"))
    co_method = str(d.get("co_method") or "keine Angabe").strip().lower()
    step_up_present = _sb(d.get("step_up_present"))
    venous_congestion_flag = d.get("venous_congestion_flag")
    rap_v_wave_flag = _sb(d.get("rap_v_wave_flag"))
    rv_dip_plateau_flag = _sb(d.get("rv_dip_plateau_flag"))

    # Etiology helpers (conservative: only if explicit flags exist)
    etiology_allowed = True
    cteph_suspected = _sb(d.get("cteph_suspected"))
    group3_supported = _sb(d.get("group3_supported"))
    left_heart_supported = _sb(d.get("left_heart_supported"))

    # Course
    comparison_available = _sb(d.get("comparison_available"))
    pvr_trend = str(d.get("pvr_trend") or "").strip().lower()
    ci_trend = str(d.get("ci_trend") or "").strip().lower()
    pawp_trend = str(d.get("pawp_trend") or "").strip().lower()

    # ---- Gatekeeper: if core triad missing, do not output an interpretation block ----
    if mpap is None or pawp is None:
        return ""

    parts: List[str] = []

    # =====================================================================
    # A) QC / Safety
    # =====================================================================
    qc_lines: List[str] = []
    if exercise_done and exercise_hardstop:
        qc_lines.append(
            "Belastungsauswertung aufgrund unplausibler Rohdaten oder vorzeitigem Abbruch nicht verwertbar. "
            "Zweipunkt Steigungen werden zur Vermeidung von Fehlinterpretationen nicht ausgewiesen."
        )
    if wedge_v_wave or atrial_fib:
        qc_lines.append(
            "Interpretation des PAWP durch V Wellen Phänomene oder Vorhofflimmern limitiert. "
            "Aussagen zur linksatrialen Druckkomponente sind nur im Gesamtkontext der Bildgebung valide."
        )
    if co_method in ("keine angabe", "", "unbekannt", "unknown"):
        qc_lines.append(
            "Methode der Herzzeitvolumenbestimmung ist nicht dokumentiert."
        )
    if ci is not None and ci < 2.0 and pvr is not None:
        qc_lines.append(
            "Bei erniedrigtem CI (< 2.0 l/min/m²) ist die PVR Einordnung vorsichtig vorzunehmen, "
            "da eine geringe Vorwärtsleistung rechnerische Widerstände überhöhen kann."
        )
    if step_up_present:
        qc_lines.append(
            "Relevanter Step up in der Stufenoxymetrie. "
            "Hämodynamik und Belastungsreaktion sind zwingend im Kontext einer möglichen Shunt Konstellation zu bewerten."
        )

    if qc_lines:
        intro = _pick(_MICROPHRASES["qc_intro"], 0, seed)
        parts.append(f"{intro} { _join_sentences(qc_lines) }")

    # QC affects downstream interpretability
    qc_blocks_etiology = bool(exercise_hardstop)  # hard stop is a strict blocker
    qc_blocks_ex_interp = bool(exercise_hardstop)

    # =====================================================================
    # B) Rest classification (guideline strict)
    # =====================================================================
    if mpap <= 20 and pawp <= 15:
        parts.append("Kein Hinweis auf eine pulmonale Hypertonie in Ruhe.")
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp <= 15) and (pvr is not None and pvr > 2):
        parts.append("Hämodynamisch präkapilläre PH.")
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp > 15) and (pvr is not None and pvr <= 2):
        parts.append(
            "Hämodynamisch isolierte postkapilläre PH (IpcPH). "
            "Führende linksatriale Druckübertragung ohne relevante präkapilläre Komponente (PVR ≤ 2 WU)."
        )
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp > 15) and (pvr is not None and pvr > 2):
        parts.append(
            "Hämodynamisch kombinierte post und präkapilläre PH (CpcPH). "
            "Linksatriale Druckbelastung mit zusätzlicher pulmonal vaskulärer Komponente (PVR > 2 WU)."
        )
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp <= 15) and (pvr is not None and pvr <= 2):
        parts.append(
            "Isolierte mPAP Erhöhung bei normalem PAWP und nicht erhöhter PVR (High Flow oder hyperdyname Konstellation). "
            "Kriterien einer manifesten präkapillären PH sind nicht erfüllt."
        )

    # =====================================================================
    # C) Mechanisms / severity (only if data exist)
    # =====================================================================
    mech: List[str] = []
    if rap is not None and rap >= 10:
        mech.append("Erhöhter RAP als Hinweis auf rechtskardiale Füllungsdrucksteigerung oder Volumenbelastung.")
    if venous_congestion_flag is False:
        mech.append("Kein Hinweis auf venöse Kongestion in den vorliegenden Druckwerten.")
    if pawp is not None and pawp > 15:
        mech.append("Hinweis auf pulmonalvenöse Stauung bei erhöhtem PAWP.")
    if ci is not None and ci < 2.0:
        mech.append("CI erniedrigt im Sinne einer Low Output Konstellation.")
    if pac is not None and pac < 2.0:
        mech.append("Verminderte pulmonalarterielle Compliance (PAC) als Hinweis auf erhöhte pulsatile RV Nachlast.")
    if rc is not None and rc < 0.4:
        mech.append("Kritisch verkürzte RC Zeit; der Compliance Verlust dominiert gegenüber dem Widerstand.")
    if rap_v_wave_flag:
        mech.append("Ausgeprägte V Welle im RAP, vereinbar mit relevanter Trikuspidalinsuffizienz.")
    if wedge_v_wave:
        mech.append(
            "Ausgeprägte V Welle in PAWP Position, vereinbar mit linksatrialer Volumen oder Druckbelastung "
            "(z.B. Mitralvitium oder Compliance Störung)."
        )
    if rv_dip_plateau_flag:
        mech.append("Dip Plateau Muster in der RV Kurve als Hinweis auf restriktive oder konstriktive Füllungsphysiologie.")

    if mech:
        conn = _pick(_MICROPHRASES["connectors"], 1, seed)
        parts.append(f"{conn} { _join_sentences(mech) }")

    # =====================================================================
    # D) Exercise: numeric always, interpretation only if ok and not blocked
    # =====================================================================
    if exercise_done and not exercise_hardstop:
        if dco is not None and dco > 0:
            # Numeric block only if core slope components exist
            if mpap_slope is not None and pawp_slope is not None and tpg_slope is not None:
                parts.append(
                    f"Belastung (semi supine), Zweipunkt Analyse Ruhe zu Peak: dCO {dco:.1f} l/min. "
                    f"Steigungen: ΔmPAP/ΔCO {mpap_slope:.1f}, ΔPAWP/ΔCO {pawp_slope:.1f}, ΔTPG/ΔCO {tpg_slope:.1f} mmHg/l/min. "
                    "Berechnung rein rechnerisch aus Ruhe und Peak Werten (keine Multipoint Regression)."
                )
            else:
                # If slopes missing, do not invent
                pass

            if 0 < dco < 1.0:
                parts.append("Interpretation der Steigungen eingeschränkt aufgrund geringer CO Spannweite (dCO < 1.0 l/min).")

        if pawp_slope is not None and pawp_slope > 2 and pawp_peak is not None and pawp_peak <= 15:
            parts.append(
                "Numerisch erhöhte ΔPAWP/ΔCO Steigung bei normwertigem PAWP Peak. "
                "Interpretation eingeschränkt (häufig dCO Artefakt oder Wedge Messunsicherheit), klinische Korrelation erforderlich."
            )

        # Interpretive pattern only if explicitly ok
        if (not qc_blocks_ex_interp) and exercise_interp == "ok":
            # Map existing pattern codes to V3 buckets
            bucket = ""
            if ex_pattern in ("exercise_2pt_normal", "normal"):
                bucket = "normal"
            elif ex_pattern in ("exercise_2pt_pv", "pulmonary_vascular_dominant"):
                bucket = "pulmonary_vascular_dominant"
            elif ex_pattern in ("exercise_2pt_la", "left_atrial_dominant"):
                bucket = "left_atrial_dominant"
            elif ex_pattern in ("exercise_2pt_mixed", "mixed"):
                bucket = "mixed"

            if bucket == "normal":
                parts.append("Unter Belastung regelhafte Druck Flow Reaktion ohne Hinweis auf eine pathologische pulmonale Drucksteigerung.")
            elif bucket == "pulmonary_vascular_dominant":
                parts.append("Unter Belastung abnorme Druck Flow Reaktion mit Hinweis auf pulmonal vaskulär dominanten Anteil.")
            elif bucket == "left_atrial_dominant":
                parts.append("Unter Belastung Hinweis auf eine belastungsassoziierte linksatriale Druckkomponente (PAWP Anstieg führend).")
            elif bucket == "mixed":
                parts.append("Unter Belastung Hinweis auf ein gemischtes Muster der Druck Flow Relation (kombiniert vaskulär linksatrial).")

    # =====================================================================
    # E) Etiology ranking (only if allowed and not blocked)
    # =====================================================================
    if etiology_allowed and not qc_blocks_etiology:
        # Keep this conservative: only if flags say so.
        if cteph_suspected:
            parts.append(
                "Ätiologische Einordnung: Die Konstellation spricht eher für eine chronisch thromboembolische Genese (CTEPH). "
                "Differenzialdiagnostisch andere präkapilläre Ursachen prüfen."
            )
        elif group3_supported:
            parts.append(
                "Ätiologische Einordnung: Am ehesten lungenerkrankungsassoziierte Genese (Gruppe 3). "
                "Differenzialdiagnostisch vaskuläre Komponente abgrenzen."
            )
        elif left_heart_supported:
            parts.append(
                "Ätiologische Einordnung: Überwiegend linksherzbedingte Genese (Gruppe 2). "
                "Pulmonal vaskuläre Beteiligung nach Kontext möglich."
            )
        elif step_up_present:
            parts.append(
                "Aufgrund des Step ups ist die ätiologische Zuordnung zurückhaltend vorzunehmen. "
                "Hämodynamik primär im Kontext der Shunt Volumenbelastung bewerten."
            )

    # =====================================================================
    # F) Course / trend
    # =====================================================================
    if comparison_available:
        if pvr_trend == "down" and ci_trend == "up":
            parts.append("Hämodynamische Verlaufseinordnung: Effektive vaskuläre Entlastung (Widerstandssenkung) mit Steigerung der Vorwärtsleistung.")
        elif pvr_trend == "down" and ci_trend in ("stable", "stabil"):
            parts.append("Hämodynamische Verlaufseinordnung: Vaskuläre Entlastung bei weitgehend stabiler Vorwärtsleistung.")
        elif pawp_trend == "up" and ci_trend not in ("down", "abfall", "fallend"):
            parts.append(
                "Hämodynamische Verlaufseinordnung: PAWP Anstieg bei erhaltener oder gesteigerter Vorwärtsleistung. "
                "Einordnung im Kontext von Volumenstatus, Messbedingungen und linksatrialer Compliance vornehmen."
            )
        else:
            parts.append(
                "Hämodynamische Verlaufseinordnung: Veränderungen von mPAP, PAWP, PVR und CI im Vergleich zur Voruntersuchung im Kontext der Therapieanpassung zu bewerten."
            )

    # =====================================================================
    # G) Conclusion
    # =====================================================================
    concl = ""
    if mpap <= 20 and exercise_done and (exercise_interp == "ok") and ex_pattern and ex_pattern not in ("exercise_2pt_normal", "normal"):
        concl = (
            "In der Gesamtschau kein Hinweis auf PH in Ruhe, unter Belastung jedoch abnorme Druck Flow Reaktion. "
            "Einordnung und weiteres Vorgehen gemäß Gesamtbefund."
        )
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp <= 15) and (pvr is not None and pvr > 2):
        concl = "Zusammenfassend präkapilläre PH. Verlauf anhand von Widerstand, Vorwärtsleistung und pulsatilem Anteil zu bewerten."
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp > 15) and (pvr is not None and pvr > 2):
        concl = (
            "Zusammenfassend CpcPH mit linksatrialer Druckkomponente und zusätzlicher pulmonal vaskulärer Beteiligung."
        )

    if concl:
        start = _pick(_MICROPHRASES["conclusion_start"], 2, seed)
        parts.append(f"{start} {concl}")

    return _join_sentences(parts)
