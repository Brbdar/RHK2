#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPET UI rendering helpers (Gradio-independent)."""

from __future__ import annotations

import functools
import html
import json
from typing import Any, Dict, List, Optional

from rhk_base import _safe_float, calc_cpet_scores


def cache_json(payload: Dict[str, Any]) -> str:
    """Serialize payload in a stable way for LRU cache keys."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def build_cpet_risk_payload(
    cpet_done_v: Any,
    peak_vo2: Any,
    peak_vo2_pct: Any,
    vo2_peak_reached: Any,
    vt1_method: Any,
    vt1_manual_checked: Any,
    vt1_time_min: Any,
    vevco2_slope: Any,
    petco2_vt1: Any,
    vevco2_vt1: Any,
    o2pulse_pct: Any,
    vo2_wr_slope: Any,
    vo2_vt1: Any,
    spo2_nadir: Any,
    rer_peak: Any,
    hr_peak: Any,
    o2_pulse_pattern: Any,
) -> Dict[str, Any]:
    return {
        "cpet_done": bool(cpet_done_v),
        "cpet_peak_vo2_ml_kg_min": peak_vo2,
        "cpet_peak_vo2_pct_pred": peak_vo2_pct,
        "cpet_vo2_peak_reached": vo2_peak_reached,
        "cpet_vt1_method": vt1_method,
        "cpet_vt1_manual_checked": vt1_manual_checked,
        "cpet_vt1_time_min": vt1_time_min,
        "cpet_ve_vco2_slope": vevco2_slope,
        "cpet_petco2_vt1_mmhg": petco2_vt1,
        "cpet_ve_vco2_vt1": vevco2_vt1,
        "cpet_peak_o2_pulse_pct_pred": o2pulse_pct,
        "cpet_vo2_wr_slope_ml_min_w": vo2_wr_slope,
        "cpet_vo2_vt1_ml_kg_min": vo2_vt1,
        "cpet_spo2_nadir_pct": spo2_nadir,
        "cpet_rer_peak": rer_peak,
        "cpet_hr_peak_bpm": hr_peak,
        "cpet_o2_pulse_pattern": o2_pulse_pattern,
    }


@functools.lru_cache(maxsize=256)
def render_cpet_risk_html_cached(payload_json: str) -> str:
    payload = json.loads(payload_json or "{}")
    if not bool(payload.get("cpet_done")):
        return "<div class='docx-muted'>Keine CPET Daten erfasst.</div>"

    res = calc_cpet_scores(payload)
    chips: List[str] = []

    def _chip(label: str, value: str, level: Optional[str] = None) -> str:
        cls = "rhk-schip"
        if level == "good":
            cls += " rhk-schip--good"
        elif level == "warn":
            cls += " rhk-schip--warn"
        elif level == "bad":
            cls += " rhk-schip--bad"
        else:
            cls += " rhk-schip--info"
        return f"<span class='{cls}'><b>{label}</b>: {value}</span>"

    if res and res.esc_ers_3_strata:
        lev = "good" if res.esc_ers_3_strata == "low" else "warn" if res.esc_ers_3_strata == "intermediate" else "bad"
        chips.append(_chip("ESC/ERS CPET Risiko", res.esc_ers_3_strata, lev))
    else:
        chips.append(_chip("ESC/ERS CPET Risiko", "nicht berechenbar", "warn"))

    if res and res.cpet_score_4_strata:
        lev = "good" if res.cpet_score_4_strata == "low" else "warn" if res.cpet_score_4_strata in ("intermediate-low", "intermediate-high") else "bad"
        chips.append(_chip("CPET Score", res.cpet_score_4_strata, lev))

    if res and res.effort_ok is not None:
        chips.append(_chip("Effort", "ausreichend" if res.effort_ok else "limitiert", "good" if res.effort_ok else "warn"))

    peak_vo2 = payload.get("cpet_peak_vo2_ml_kg_min")
    vevco2_slope = payload.get("cpet_ve_vco2_slope")
    petco2_vt1 = payload.get("cpet_petco2_vt1_mmhg")
    if _safe_float(peak_vo2) is not None:
        chips.append(_chip("Peak VO2", f"{_safe_float(peak_vo2):.1f} ml/min/kg", "info"))
    if _safe_float(vevco2_slope) is not None:
        chips.append(_chip("VE/VCO2 slope", f"{_safe_float(vevco2_slope):.1f}", "info"))
    if _safe_float(petco2_vt1) is not None:
        chips.append(_chip("PETCO2@VT1", f"{_safe_float(petco2_vt1):.0f} mmHg", "info"))

    notes_html = ""
    if res and res.notes:
        notes = " ".join([f"• {html.escape(str(n))}" for n in res.notes])
        notes_html = f"<span class='rhk-schip rhk-schip--hint'>{notes}</span>"

    return "<div class='rhk-summarybar'>" + "".join(chips) + notes_html + "</div>"


def render_cpet_risk_html(
    cpet_done_v: Any,
    peak_vo2: Any,
    peak_vo2_pct: Any,
    vo2_peak_reached: Any,
    vt1_method: Any,
    vt1_manual_checked: Any,
    vt1_time_min: Any,
    vevco2_slope: Any,
    petco2_vt1: Any,
    vevco2_vt1: Any,
    o2pulse_pct: Any,
    vo2_wr_slope: Any,
    vo2_vt1: Any,
    spo2_nadir: Any,
    rer_peak: Any,
    hr_peak: Any,
    o2_pulse_pattern: Any,
) -> str:
    payload = build_cpet_risk_payload(
        cpet_done_v,
        peak_vo2,
        peak_vo2_pct,
        vo2_peak_reached,
        vt1_method,
        vt1_manual_checked,
        vt1_time_min,
        vevco2_slope,
        petco2_vt1,
        vevco2_vt1,
        o2pulse_pct,
        vo2_wr_slope,
        vo2_vt1,
        spo2_nadir,
        rer_peak,
        hr_peak,
        o2_pulse_pattern,
    )
    return render_cpet_risk_html_cached(cache_json(payload))
