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
    "qc_intro": [
        "Hinweis:",
    ],
    "conclusion_start": [
        "Fazit:",
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
    exercise_hardstop = _sb(
        d.get("exercise_qc_hard_stop")
        if d.get("exercise_qc_hard_stop") is not None
        else d.get("exercise_hardstop")
    )
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
    _co_method = str(d.get("co_method") or "keine Angabe").strip().lower()  # noqa: F841
    step_up_present = _sb(d.get("step_up_present"))
    venous_congestion_flag = d.get("venous_congestion_flag")
    rap_v_wave_flag = _sb(d.get("rap_v_wave_flag"))
    rv_dip_plateau_flag = _sb(d.get("rv_dip_plateau_flag"))

    # Etiology helpers (conservative: only if explicit flags exist)
    # If a dedicated PH-Ätiologie/DD block is available (ph_etiology candidates),
    # avoid duplicating etiology sentences here.
    ph_etiology = d.get("ph_etiology")
    etiology_allowed = not (isinstance(ph_etiology, dict) and (ph_etiology.get("candidates") or []))
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
            "Belastungsauswertung nicht verwertbar (unplausible Rohdaten/vorzeitiger Abbruch); Steigungen nicht ausgewiesen."
        )
    if wedge_v_wave or atrial_fib:
        qc_lines.append(
            "PAWP-Interpretation limitiert durch V-Wellen/Vorhofflimmern; linksatriale Komponente nur im Kontext der Bildgebung einordnen."
        )
    # CO-Methode: kein generischer Disclaimer im Interpretationstext.
    # (CO-Methode kann im Methodenteil/Beurteilung dokumentiert werden; flussabhängige
    # Parameter werden ohnehin nur ausgewiesen, wenn Werte vorliegen.)
    if step_up_present:
        qc_lines.append(
            "Relevanter Step-up in der Stufenoxymetrie; Hämodynamik/Belastungsreaktion im Kontext einer möglichen Shunt-Konstellation einordnen."
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
        # No guideline definition in brackets in clinician-facing text.
        parts.append("Hämodynamisch präkapilläre PH.")
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp > 15) and (pvr is not None and pvr <= 2):
        parts.append(
            "Hämodynamisch isolierte postkapilläre PH (IpcPH) mit führender linksatrialer Druckübertragung ohne relevante präkapilläre Komponente."
        )
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp > 15) and (pvr is not None and pvr > 2):
        parts.append(
            "Hämodynamisch kombinierte post- und präkapilläre PH (CpcPH) mit linksatrialer Druckbelastung und zusätzlicher pulmonalvaskulärer Komponente."
        )
    elif (mpap is not None and mpap > 20) and (pawp is not None and pawp <= 15) and (pvr is not None and pvr <= 2):
        parts.append(
            "Erhöhtes mPAP bei normalem PAWP und nicht erhöhter PVR; am ehesten flussdominante/hyperdyname Konstellation. "
            "Kriterien einer präkapillären PH sind nicht erfüllt."
        )


    # =====================================================================
    # C) Mechanisms / severity (only if data exist)
    # =====================================================================
    if rap is not None and rap >= 10:
        parts.append("Erhöhter RAP als Hinweis auf rechtskardiale Füllungsdrucksteigerung/Volumenbelastung.")
    if venous_congestion_flag is False:
        parts.append("Kein Hinweis auf venöse Kongestion in den vorliegenden Druckwerten.")
    if pawp is not None and pawp > 15:
        parts.append("Hinweis auf pulmonalvenöse Stauung bei erhöhtem PAWP.")
    if ci is not None and ci < 2.0:
        parts.append("Low-output-Konstellation; PVR kann rechnerisch überhöht sein.")
    if pac is not None and pac < 2.0:
        parts.append("Verminderte pulmonalarterielle Compliance (PAC) als Hinweis auf erhöhte pulsatile RV-Nachlast.")
    if rc is not None and rc < 0.4:
        parts.append("Kritisch verkürzte RC-Zeit; der Verlust der Compliance dominiert gegenüber dem Widerstand.")
    if rap_v_wave_flag:
        parts.append("Ausgeprägte V-Welle in der RAP-Kurve, vereinbar mit relevanter Trikuspidalinsuffizienz.")
    if wedge_v_wave:
        parts.append(
            "Ausgeprägte V-Welle in PAWP-Kurve, vereinbar mit linksatrialer Volumen-/Druckbelastung "
            "(z.B. Mitralvitium oder reduzierte LA-Compliance)."
        )
    if rv_dip_plateau_flag:
        parts.append("Dip-Plateau-Muster in der RV-Kurve; DD restriktive/konstriktive Füllungsphysiologie.")

    # =====================================================================
    # D) Exercise: numeric always, interpretation only if ok and not blocked
    # =====================================================================
    if exercise_done and not exercise_hardstop:
        if dco is not None and dco > 0:
            # Numeric block only if core slope components exist
            if mpap_slope is not None and pawp_slope is not None and tpg_slope is not None:
                parts.append(
                    f"Belastung (semi-supine), 2-Punkt (Ruhe→Peak): dCO {dco:.1f} L/min; "
                    f"ΔmPAP/ΔCO {mpap_slope:.1f}; ΔPAWP/ΔCO {pawp_slope:.1f}; ΔTPG/ΔCO {tpg_slope:.1f} mmHg/(L/min)."
                )
            else:
                # If slopes missing, do not invent
                pass

        if dco is not None and 0 < dco < 1.0:
            parts.append("Steigungsinterpretation eingeschränkt bei geringer ΔCO-Spannweite (dCO < 1,0 L/min).")

        if pawp_slope is not None and pawp_slope > 2 and pawp_peak is not None and pawp_peak <= 15:
            parts.append("Numerisch erhöhte ΔPAWP/ΔCO bei normwertigem PAWP_peak; häufig Artefakt (ΔCO/Wedge).")

        # Interpretive pattern only if explicitly ok
        if (not qc_blocks_ex_interp) and exercise_interp == "ok":
            # Map existing pattern codes to V3 buckets
            bucket = ""
            if ex_pattern in ("exercise_2pt_normal", "normal"):
                bucket = "normal"
            elif ex_pattern in ("exercise_2pt_pv", "exercise_2pt_pv_dominant", "pulmonary_vascular_dominant"):
                bucket = "pulmonary_vascular_dominant"
            elif ex_pattern in ("exercise_2pt_la", "exercise_2pt_la_dominant", "left_atrial_dominant"):
                bucket = "left_atrial_dominant"
            elif ex_pattern in ("exercise_2pt_mixed", "mixed"):
                bucket = "mixed"

            if bucket == "normal":
                parts.append("Unter Belastung regelhafte Druck-Flow-Reaktion ohne Hinweis auf eine pathologische pulmonale Drucksteigerung.")
            elif bucket == "pulmonary_vascular_dominant":
                parts.append("Unter Belastung abnorme Druck-Flow-Reaktion mit pulmonalvaskulär dominanter Komponente.")
            elif bucket == "left_atrial_dominant":
                parts.append("Unter Belastung Hinweis auf eine belastungsassoziierte linksatriale Druckkomponente (PAWP-Anstieg führend).")
            elif bucket == "mixed":
                parts.append("Unter Belastung Hinweis auf eine gemischte Druck-Flow-Reaktion (kombiniert vaskulär/linksatrial).")

    # =====================================================================
    # E) Etiology ranking (only if allowed and not blocked)
    # =====================================================================
    if etiology_allowed and not qc_blocks_etiology:
        # Keep this conservative: only if flags say so.
        if cteph_suspected:
            parts.append("Ätiologische Einordnung: am ehesten CTEPH-Konstellation (Gruppe 4).")
        elif group3_supported:
            parts.append("Ätiologische Einordnung: am ehesten lungenerkrankungsassoziiert (Gruppe 3).")
        elif left_heart_supported:
            parts.append("Ätiologische Einordnung: Hinweise auf linksherzbedingte Komponente (Gruppe 2).")
        elif step_up_present:
            parts.append("Ätiologische Einordnung: bei Step-up primär Shunt-Konstellation berücksichtigen.")

    # =====================================================================
    # F) Course / trend
    # =====================================================================
    if comparison_available:
        if pvr_trend == "down" and ci_trend == "up":
            parts.append("Verlauf: PVR rückläufig bei steigender Vorwärtsleistung (vaskuläre Entlastung).")
        elif pvr_trend == "down" and ci_trend in ("stable", "stabil"):
            parts.append("Verlauf: PVR rückläufig bei weitgehend stabiler Vorwärtsleistung.")
        elif pawp_trend == "up" and ci_trend not in ("down", "abfall", "fallend"):
            parts.append("Verlauf: PAWP-Anstieg bei erhaltener Vorwärtsleistung; Volumenstatus und Messbedingungen berücksichtigen.")

    # =====================================================================
    # G) Conclusion
    # =====================================================================
    # Keep conclusions rare and non-redundant:
    # - Do NOT restate the already declared rest-classification (e.g., "präkapilläre PH").
    # - Avoid generic follow-up phrases ("Verlauf anhand ...") in clinician-facing text.
    concl = ""
    if mpap <= 20 and exercise_done and (exercise_interp == "ok") and ex_pattern and ex_pattern not in ("exercise_2pt_normal", "normal"):
        # This case adds new information (rest-normal, exercise-abnormal).
        concl = "In Ruhe kein Hinweis auf PH, unter Belastung jedoch abnorme Druck-Flow-Reaktion."

    if concl:
        start = _pick(_MICROPHRASES["conclusion_start"], 2, seed)
        parts.append(f"{start} {concl}")

    return _join_sentences(parts)
