#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P-Module V3 – erweiterte, aktionsorientierte Vorschläge.

Scope
- Erweitert die Vorschlagsliste (decision.modules) um V3 Module.
- Limitiert die Vorschläge auf maximal 6 Module, priorisiert nach klinischer Sicherheit.

Wichtig
- UI Auswahl (ui['modules']) wird niemals überschrieben.
- Fehlende Werte gelten als nicht vorhanden.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from rhk_validation import parse_boolish


def _sf(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        v = float(x)
        if v != v:
            return None
        return v
    except Exception:
        return None


def _sb(x: Any) -> bool:
    return parse_boolish(x)


def _ge_num(x: Any, threshold: float) -> bool:
    v = _sf(x)
    return v is not None and v >= threshold


def _gt_num(x: Any, threshold: float) -> bool:
    v = _sf(x)
    return v is not None and v > threshold


def _lt_num(x: Any, threshold: float) -> bool:
    v = _sf(x)
    return v is not None and v < threshold


def _iron_deficiency_trigger(ui: Dict[str, Any]) -> bool:
    ferritin = _sf(ui.get("ferritin"))
    tsat = _sf(ui.get("tsat"))
    if ferritin is None:
        return False
    if ferritin < 100:
        return True
    return tsat is not None and ferritin < 300 and tsat < 20


Spec = Tuple[str, int, Callable[[Dict[str, Any], Dict[str, Any]], bool]]


def _specs() -> List[Spec]:
    # id, priority, trigger(ui, derived) -> bool
    return [
        ("P33", 95, lambda ui, d: _sb(d.get("wedge_v_wave")) or _sb(d.get("rap_v_wave_flag")) or _sb(d.get("echo_valve_relevant"))),
        ("P34", 95, lambda ui, d: _sb(d.get("cteph_suspected")) or _sb(d.get("vq_defect"))),
        ("P35", 92, lambda ui, d: _sb(d.get("step_up_present"))),
        ("P36", 88, lambda ui, d: _sb(d.get("rv_dip_plateau_flag"))),
        ("P37", 85, lambda ui, d: _sb(d.get("cteph_suspected")) and (_sb(d.get("ct_angiography_available")) is False)),
        ("P38", 82, lambda ui, d: _sb(d.get("high_flow")) or _sb(d.get("hypercirculation_suspected"))),
        ("P39", 80, lambda ui, d: _ge_num(d.get("aorta_asc_mm"), 45)),
        ("P40", 78, lambda ui, d: _sb(d.get("venous_congestion_flag")) or _ge_num(d.get("rap_rest"), 10)),
        ("P41", 76, lambda ui, d: _sb(d.get("transaminases_high"))),
        ("P42", 75, lambda ui, d: _iron_deficiency_trigger(ui)),
        ("P43", 75, lambda ui, d: _sb(d.get("dyspnea_present")) and (_sb(d.get("cpet_available")) is False)),
        ("P44", 74, lambda ui, d: _sb(d.get("ph_present")) and (_sb(d.get("sixmwd_available")) is False)),
        ("P45", 72, lambda ui, d: _sb(d.get("group3_supported")) and (_sb(d.get("lung_imaging_reviewed")) is False)),
        ("P46", 71, lambda ui, d: _gt_num(d.get("bmi"), 30) or _sb(d.get("sleep_apnea_suspected"))),
        ("P47", 70, lambda ui, d: _sb(d.get("precap_ph_present")) and (_sb(d.get("autoimmun_labs_available")) is False)),
        ("P48", 65, lambda ui, d: _sb(d.get("ltot_prescribed"))),
        ("P49", 62, lambda ui, d: _sb(d.get("ph_present")) and _sb(d.get("high_risk"))),
        ("P50", 60, lambda ui, d: _sb(d.get("systemic_bp_high"))),
        ("P51", 55, lambda ui, d: _sb(d.get("ph_present")) and (_sb(d.get("high_risk")) is False)),
        ("P52", 55, lambda ui, d: _sb(d.get("study_patient"))),
    ]


def apply_p_modules_v3(ui: Dict[str, Any], derived: Dict[str, Any], base_modules: List[str]) -> List[str]:
    """Merge V3 modules into base_modules and enforce max 6 output."""
    mods: List[str] = []
    seen = set()

    for m in (base_modules or []):
        mid = str(m or "").strip()
        if not mid:
            continue
        if mid not in seen:
            seen.add(mid)
            mods.append(mid)

    # Add V3 modules by trigger
    additions: List[Tuple[str, int]] = []
    for mid, prio, trig in _specs():
        try:
            if trig(ui or {}, derived or {}):
                additions.append((mid, int(prio)))
        except Exception:
            continue

    for mid, _prio in additions:
        if mid not in seen:
            seen.add(mid)
            mods.append(mid)

    # Apply priority cap (max 6). Unknown modules get low priority.
    prio_map = {mid: prio for mid, prio, _trig in _specs()}
    # Keep original ordering stable by adding index as tie breaker
    ranked = []
    for i, mid in enumerate(mods):
        p = int(prio_map.get(mid, 10))
        ranked.append((p, -i, mid))
    ranked.sort(reverse=True)

    out = [mid for _p, _i, mid in ranked[:6]]
    return out
