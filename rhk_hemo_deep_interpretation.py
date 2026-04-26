""""Deep hemodynamic interpretation blocks (Executive Clinical Grade).

Purpose
- High-Impact Decision Support: Responder-Phenotyping, Risk Stratification, Pitfall-Avoidance.
- Design: Deterministic, noise-gated, safety-checked (Physical Plausibility).
- Style: Concise, abbreviation-heavy (CI, PVR, RAP), action-oriented.
- Role: Senior Clinical Software Architect & Hemodynamic Expert.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Final, List, Optional

from rhk_thresholds import (
    CI_HIGH_RISK,
    CI_INTERMEDIATE_HIGH,
    DPG_HIGH,
    NOISE_ABS_CI,
    NOISE_ABS_MPAP,
    NOISE_ABS_PAWP,
    NOISE_ABS_PVR,
    NOISE_REL_CI,
    NOISE_REL_MPAP,
    NOISE_REL_PAWP,
    NOISE_REL_PVR,
    OVERWEDGE_BUFFER,
    PH_PAWP_POSTCAPILLARY,
    PH_PVR_PRECAPILLARY,
    RAP_CONGEST_NARRATIVE,
    RAP_SEVERE_NARRATIVE,
    RC_TIME_LOW,
    SVI_HIGH_RISK,
)
from rhk_validation import safe_float as _safe_float

# -----------------------------------------------------------------------------
# 1. THRESHOLDS & CONFIGURATION
# -----------------------------------------------------------------------------
# All clinical cutoffs are imported from rhk_thresholds.py — that module is
# the single source of truth and carries the full guideline citations.
# Local aliases below preserve the readable names used throughout this file.
# -----------------------------------------------------------------------------

# Noise Gates: Change is only reported if ABS > thr OR (REL > thr AND ABS is relevant)
THR_REL_PVR: Final[float]  = NOISE_REL_PVR
THR_ABS_PVR: Final[float]  = NOISE_ABS_PVR
THR_REL_MPAP: Final[float] = NOISE_REL_MPAP
THR_ABS_MPAP: Final[float] = NOISE_ABS_MPAP
THR_REL_PAWP: Final[float] = NOISE_REL_PAWP
THR_ABS_PAWP: Final[float] = NOISE_ABS_PAWP
THR_REL_CI: Final[float]   = NOISE_REL_CI
THR_ABS_CI: Final[float]   = NOISE_ABS_CI

# Critical Cutoffs (Red Flags) — see rhk_thresholds.py for source citations.
CUT_CI_SHOCK: Final[float]     = CI_HIGH_RISK            # 2.0 — ESC/ERS 2022 high-risk
CUT_CI_LOW: Final[float]       = CI_INTERMEDIATE_HIGH    # 2.5 — ESC/ERS 2022 IM-high boundary
CUT_SVI_RISK: Final[float]     = SVI_HIGH_RISK           # 31  — ESC/ERS 2022 high-risk
CUT_RAP_CONGEST: Final[float]  = RAP_CONGEST_NARRATIVE   # 10  — narrative congestion
CUT_RAP_SEVERE: Final[float]   = RAP_SEVERE_NARRATIVE    # 15  — narrative RV failure
CUT_PAWP_LHD: Final[float]     = PH_PAWP_POSTCAPILLARY   # 15  — post-cap definition
CUT_PVR_PH: Final[float]       = PH_PVR_PRECAPILLARY     # 2   — pre-cap PH definition
CUT_DPG_HIGH: Final[float]     = DPG_HIGH                # 7   — CpcPH support marker
CUT_RC_TIME_LOW: Final[float]  = RC_TIME_LOW             # 0.4 — uncoupling marker

# Safety Buffer
BUFFER_OVERWEDGE: Final[float] = OVERWEDGE_BUFFER        # 2.0 mmHg PAWP > dPAP overwedge

# -----------------------------------------------------------------------------
# 2. TEMPLATES (Precision Wording with Abbreviations)
# -----------------------------------------------------------------------------

class Trend(Enum):
    NA = "na"
    STABLE = "stable"
    UP = "up"
    DOWN = "down"

WARNING_TEMPLATES: Dict[str, str] = {
    "Impossible_Gradient": 
        "ACHTUNG (Datenqualität): PAWP > diastolischer PAP – physikalisch unplausibel (V.a. 'Overwedging').",
}

PRIMARY_TEMPLATES: Dict[str, str] = {
    # --- A. RESPONDER: VASCULAR (Target: Pulmonary Vessels) ---
    "Vasc_Responder_Optimal": 
        "Exzellentes Ansprechen: Effektive vaskuläre Entlastung (PVR ↓) führt zu relevanter Steigerung der Vorwärtsleistung (CI ↑).",
    "Vasc_Responder_Good": 
        "Erfolgreiches vaskuläres Remodeling: Deutliche Nachlastsenkung (PVR & mPAP ↓) bei stabiler Herzleistung.",
    "Vasc_Responder_Flow": 
        "Funktioneller Gewinn: PVR-Senkung wurde primär in Flusssteigerung (CI ↑) umgesetzt, daher Druckwerte (mPAP) stabil.",
    "PVR_down_PCWP_up":
        "Dissoziierte Entwicklung: Vaskuläre Entlastung (PVR ↓) bei gleichzeitigem Anstieg der Linksherzlast (PAWP ↑).",
    
    # --- B. RESPONDER: VOLUMETRIC (Target: Fluid Status) ---
    "Vol_Responder_Optimal": 
        "Synergistische Besserung: Simultane Entlastung der pulmonalvaskulären (PVR) und linksatrialen Komponente (PAWP).",
    "Vol_Responder_Pure": 
        "Vorwiegend volumenabhängige Besserung: Drucksenkung folgt passiv der Linksherzentlastung (PAWP ↓), PVR stabil.",

    # --- C. WARNINGS: FAILURE & ARTIFACTS ---
    "Warn_Pseudonormal": 
        "WARNUNG - Pseudonormalisierung: Druckabfall ist trügerisch und Folge eines kritischen CI-Einbruchs (Pumpversagen).",
    "Warn_Uncoupling": 
        "Drohende Entkopplung: Trotz stabiler Drücke fällt das SV ab – Hinweis auf erschöpfte RV-Reserve.",
    "Warn_Fake_PVR_Drop": 
        "Vorsicht (Recheneffekt): Der PVR-Abfall ist primär durch den Anstieg des PAWP bedingt und beweist keine vaskuläre Besserung.",
    "Warn_Afterload_Mismatch": 
        "Manifeste Progression: Nachlastanstieg führt zu Abfall der Pumpfunktion (Afterload Mismatch).",

    # --- D. PROGRESSION / LEFT HEART ---
    "Prog_Vascular": 
        "Vaskuläre Progression: Anstieg des pulmonalen Widerstands (PVR) bei stabilen Linksherzdrücken.",
    "Prog_LeftHeart": 
        "Postkapilläre Verschlechterung: Pulmonaler Druckanstieg ist durch Zunahme der Linksherzbelastung (PAWP ↑) getrieben.",
    "Prog_Double_Hit": 
        "Kombinierte Verschlechterung: Exazerbation der Linksherzsituation bei persistierend hohem Gefäßwiderstand.",
    "Demasking":
        "Demaskierung: Unter Senkung der Füllungsdrücke (PAWP ↓) tritt die fixierte vaskuläre Widerstandskomponente (PVR ↑) hervor.",

    # --- E. STATIC STATES ---
    "Static_High_Risk": 
        "Persistierendes Hochrisiko-Profil (Low Flow / High Resistance).",
    "Static_PreCap": 
        "Bestätigung der präkapillären PH: Erhöhter PVR bei normwertigem PAWP.",
    "Static_CpcPH": 
        "Kombinierte PH (Cpc-PH): Führende Linksherzbelastung mit zusätzlicher vaskulärer Komponente.",
    "Static_High_Flow":
        "High-Output Konstellation: Erhöhte Drücke durch hohes HZV getrieben.",
    "Static_Stable": 
        "Hämodynamisches Steady-State im Zielbereich.",
    "Uncertain": 
        "Gegenläufige Parameterdynamik – klinische Korrelation (Volumenstatus) erforderlich.",
}

SECONDARY_TEMPLATES: Dict[str, str] = {
    # Hierarchy: Mortality Risk > Congestion > Specific Phenotype
    
    # 1. Mortality & Shock
    "Shock_Alert": 
        "ACHTUNG: CI < 2.0 l/min/m² (Kardiogener Schockbereich).",
    "SVI_Risk": 
        "SVI < 31 ml/m² ist ein starker prognostischer Warnmarker (Mortalität).",
    "Low_Flow_High_RAP":
        "Klassische Versagens-Konstellation: Low Flow (CI ↓) plus Stauung (RAP ↑).",
    
    # 2. Volume Management
    "Congestion_Severe": 
        "Massive Rechtsherzbelastung mit ZVD > 15 mmHg (Rechtsherzversagen).",
    "Congestion_High": 
        "Erhöhter ZVD weist auf relevante Volumenbelastung hin.",
    "Decongestion_Success": 
        "Erfolgreiche venöse Entstauung (ZVD ↓).",
    
    # 3. Hidden Compensations & Phenotypes
    "Hidden_Failure": 
        "Latente Verschlechterung: HZV nur noch über Frequenzsteigerung kompensiert (SV fällt).",
    "Unmasking_Alert": 
        "Hinweis auf Demaskierung: Unter PAWP-Senkung steigt der rechnerische PVR.",
    "RC_Time_Crit":
        "Kritisch verkürzte RC-Zeit: Der Compliance-Verlust dominiert gegenüber dem Widerstand.",
    "Gradient_High": 
        "Hoher diastolischer Gradient (DPG ≥ 7 mmHg) bestätigt relevantes vaskuläres Remodeling.",
    "TPG_High":
        "Erhöhter TPG spricht für präkapilläre Dominanz.",
}

# -----------------------------------------------------------------------------
# 3. LOGIC ENGINE
# -----------------------------------------------------------------------------

def _detect_trend(prev: Optional[float], cur: Optional[float], *, rel_thr: float, abs_thr: float) -> Trend:
    """Robust trend detection with noise gate."""
    if prev is None or cur is None: return Trend.NA
    delta = cur - prev
    # 1. Absolute Noise Gate
    if abs(delta) < abs_thr: return Trend.STABLE
    # 2. Relative Noise Gate (handles division by zero safe-ish via abs check)
    if abs(prev) < 1e-6: 
        return Trend.UP if delta > 0 else Trend.DOWN
    pct = delta / abs(prev)
    if abs(pct) < rel_thr: return Trend.STABLE
    return Trend.UP if delta > 0 else Trend.DOWN

@dataclass(frozen=True)
class HemoInputs:
    mpap: Optional[float]; pawp: Optional[float]; pvr: Optional[float]; ci: Optional[float]
    rap: Optional[float]; sv: Optional[float]; svi: Optional[float]; dpg: Optional[float]
    tpg: Optional[float]; pp: Optional[float]; pac: Optional[float]; dpap: Optional[float]
    
    prev_mpap: Optional[float]; prev_pawp: Optional[float]; prev_pvr: Optional[float]
    prev_ci: Optional[float]; prev_rap: Optional[float]
    has_prev: bool

def _collect_inputs(ui: Dict[str, Any], der: Dict[str, Any]) -> HemoInputs:
    get = lambda d, k: _safe_float(d.get(k))
    
    # Try to find diastolic PAP for safety check
    dpap = get(der, "pap_diast_rest") or get(der, "dpap_rest")
    
    # Strict validation: Date + Core Params
    has_date = bool((ui.get("prev_rhk_date") or "").strip())
    prev_pvr = get(ui, "prev_pvr")
    valid_prev = has_date and (prev_pvr is not None)

    return HemoInputs(
        mpap=get(der, "mpap_rest"), pawp=get(der, "pawp_rest"), pvr=get(der, "pvr_rest"),
        ci=get(der, "ci_rest"), rap=get(der, "rap_rest"), sv=get(der, "sv_rest_ml"),
        svi=get(der, "svi_rest_ml_m2"), dpg=get(der, "dpg_rest"), tpg=get(der, "tpg_rest"),
        pp=get(der, "pp_pa_rest"), pac=get(der, "pac_rest_ml_per_mmhg"), dpap=dpap,
        prev_mpap=get(ui, "prev_mpap"), prev_pawp=get(ui, "prev_pawp"), prev_pvr=prev_pvr, 
        prev_ci=get(ui, "prev_ci"), prev_rap=get(ui, "prev_rap"),
        has_prev=valid_prev
    )

def _check_plausibility(h: HemoInputs) -> Optional[str]:
    """Genius-Level Safety: Checks for physical impossibilities (Overwedging)."""
    if h.pawp is not None and h.dpap is not None:
        if h.pawp > (h.dpap + BUFFER_OVERWEDGE):
            return WARNING_TEMPLATES["Impossible_Gradient"]
    return None

def _analyze_rc_time(h: HemoInputs) -> Optional[str]:
    """
    Expert Feature: Calculates RC-Time constant (Tau = R * C).
    Units: PVR [WU] * PAC [ml/mmHg] * 0.06 = Seconds.
    Physiology: Drop below 0.4s indicates severe stiffness/uncoupling.
    """
    if h.pvr is None or h.pac is None: return None
    # 1 WU = 80 dyn*s/cm5; Conversion factor for PVR(WU)*PAC(ml/mmHg) to seconds is ~0.06
    # (mmHg*min/L) * (ml/mmHg) = min*ml/L = 60s * 0.001 = 0.06s
    rc_seconds = h.pvr * h.pac * 0.06
    if rc_seconds < CUT_RC_TIME_LOW:
        return SECONDARY_TEMPLATES["RC_Time_Crit"]
    return None

def _pick_primary(h: HemoInputs) -> Optional[str]:
    """Determines the dominant clinical storyline."""
    if not h.has_prev: return None
    if h.pvr is None or h.ci is None: return None

    # Trends
    t_pvr  = _detect_trend(h.prev_pvr, h.pvr, rel_thr=THR_REL_PVR, abs_thr=THR_ABS_PVR)
    t_ci   = _detect_trend(h.prev_ci, h.ci, rel_thr=THR_REL_CI, abs_thr=0.25)
    t_mpap = _detect_trend(h.prev_mpap, h.mpap, rel_thr=THR_REL_MPAP, abs_thr=THR_ABS_MPAP)
    t_pawp = _detect_trend(h.prev_pawp, h.pawp, rel_thr=THR_REL_PAWP, abs_thr=THR_ABS_PAWP)

    # Context Flags
    is_ci_crit  = (h.ci < CUT_CI_LOW)
    is_postcap  = (h.pawp is not None and h.pawp > CUT_PAWP_LHD)
    is_precap   = (h.pvr > CUT_PVR_PH)

    # --- PRIORITY 1: SAFETY & TRAPS ---
    
    # Shock Check (CI < 2.0) - Override Primary if catastrophic
    if h.ci < CUT_CI_SHOCK:
         # Usually handled by Secondary Shock_Alert, but if stable otherwise, we flag High Risk here
         return PRIMARY_TEMPLATES["Static_High_Risk"]

    # Pseudonormalization Check (PVR down/stable, but CI crashes)
    if t_ci == Trend.DOWN:
        if t_pvr == Trend.DOWN or t_mpap == Trend.DOWN:
            return PRIMARY_TEMPLATES["Warn_Pseudonormal"]
        if t_pvr == Trend.UP:
            return PRIMARY_TEMPLATES["Warn_Afterload_Mismatch"]
        if is_precap and t_pvr == Trend.STABLE:
             return PRIMARY_TEMPLATES["Warn_Uncoupling"]

    # Fake PVR Drop Check (Math Artifact: PVR drops only because PAWP went up)
    if t_pvr == Trend.DOWN and t_pawp == Trend.UP:
        if t_mpap != Trend.DOWN and t_ci != Trend.UP:
            return PRIMARY_TEMPLATES["Warn_Fake_PVR_Drop"]
        # If CI improved, it might be real mixed effect -> Vasc Responder logic below catches this

    # --- PRIORITY 2: IMPROVEMENT (Responders) ---
    if t_pvr == Trend.DOWN:
        if t_ci == Trend.UP:
            return PRIMARY_TEMPLATES["Vasc_Responder_Optimal"]
        if t_pawp == Trend.DOWN:
            return PRIMARY_TEMPLATES["Vol_Responder_Optimal"]
        if t_ci == Trend.STABLE:
            # Special check: PVR down, but PAWP up (Mixed)
            if t_pawp == Trend.UP: 
                return PRIMARY_TEMPLATES["PVR_down_PCWP_up"]
            return PRIMARY_TEMPLATES["Vasc_Responder_Good"]

    if t_ci == Trend.UP and t_pvr == Trend.STABLE:
         return PRIMARY_TEMPLATES["Vasc_Responder_Flow"]
    
    if t_pawp == Trend.DOWN and t_mpap == Trend.DOWN and t_pvr == Trend.STABLE:
        return PRIMARY_TEMPLATES["Vol_Responder_Pure"]

    # --- PRIORITY 3: DETERIORATION ---
    if t_pawp == Trend.UP:
        if is_precap:
            return PRIMARY_TEMPLATES["Prog_Double_Hit"]
        return PRIMARY_TEMPLATES["Prog_LeftHeart"]
    
    if t_pvr == Trend.UP:
        if t_pawp == Trend.DOWN:
            return PRIMARY_TEMPLATES["Demasking"]
        return PRIMARY_TEMPLATES["Prog_Vascular"]

    # --- PRIORITY 4: STATIC STATES ---
    if is_ci_crit and is_precap:
        return PRIMARY_TEMPLATES["Static_High_Risk"]
    if is_postcap and (h.tpg is not None and h.tpg >= 12):
        return PRIMARY_TEMPLATES["Static_CpcPH"]
    if is_precap and not is_postcap:
        return PRIMARY_TEMPLATES["Static_PreCap"]
    if not is_precap and t_ci == Trend.UP:
        return PRIMARY_TEMPLATES["Static_High_Flow"]
    if not is_precap and not is_postcap and not is_ci_crit:
        return PRIMARY_TEMPLATES["Static_Stable"]

    return PRIMARY_TEMPLATES["Uncertain"]


def _pick_secondary(h: HemoInputs, primary: Optional[str]) -> List[str]:
    """Adds critical context. Strictly hierarchical."""
    out: List[str] = []

    # 1. MORTALITY RISK (The "Red Phone")
    if h.ci is not None and h.ci < CUT_CI_SHOCK:
        out.append(SECONDARY_TEMPLATES["Shock_Alert"])
        return out # If shock, stop here.

    if h.svi is not None and h.svi < CUT_SVI_RISK:
        out.append(SECONDARY_TEMPLATES["SVI_Risk"])
    elif h.ci is not None and h.ci < CUT_CI_LOW:
        if h.rap is not None and h.rap >= CUT_RAP_CONGEST:
            out.append(SECONDARY_TEMPLATES["Low_Flow_High_RAP"])

    # 2. CONGESTION / VOLUME
    if len(out) < 2:
        if h.rap is not None and h.rap >= CUT_RAP_SEVERE:
            out.append(SECONDARY_TEMPLATES["Congestion_Severe"])
        elif h.has_prev and h.rap is not None and h.prev_rap is not None:
             rap_trend = _detect_trend(h.prev_rap, h.rap, rel_thr=0.2, abs_thr=2.0)
             if rap_trend == Trend.DOWN:
                 out.append(SECONDARY_TEMPLATES["Decongestion_Success"])
             elif h.rap >= CUT_RAP_CONGEST:
                 out.append(SECONDARY_TEMPLATES["Congestion_High"])
    
    # 3. HIDDEN DYNAMICS & PHENOTYPES
    if len(out) < 2:
        # Check RC-Time (Expert Feature)
        rc_msg = _analyze_rc_time(h)
        if rc_msg:
            out.append(rc_msg)

    if len(out) < 2 and h.has_prev:
        # Hidden Failure: CI stable but SV down (HR comp)
        if h.has_prev and h.prev_ci is not None:
            ci_tr = _detect_trend(h.prev_ci, h.ci, rel_thr=0.1, abs_thr=0.2)
            sv_low = (h.sv is not None and h.sv < 55)
            if ci_tr == Trend.STABLE and sv_low:
                 out.append(SECONDARY_TEMPLATES["Hidden_Failure"])

        # Unmasking Check
        if h.has_prev and h.prev_pvr is not None and h.prev_pawp is not None:
            pvr_tr = _detect_trend(h.prev_pvr, h.pvr, rel_thr=THR_REL_PVR, abs_thr=THR_ABS_PVR)
            pawp_tr = _detect_trend(h.prev_pawp, h.pawp, rel_thr=THR_REL_PAWP, abs_thr=THR_ABS_PAWP)
            if pawp_tr == Trend.DOWN and pvr_tr == Trend.UP:
                out.append(SECONDARY_TEMPLATES["Unmasking_Alert"])
        
        # Gradient
        if len(out) < 2:
            if h.dpg is not None and h.dpg >= CUT_DPG_HIGH and (h.pawp or 0) > 12:
                out.append(SECONDARY_TEMPLATES["Gradient_High"])
            elif h.tpg is not None and h.tpg > 12 and (h.pawp or 0) > 12:
                out.append(SECONDARY_TEMPLATES["TPG_High"])

    return out[:2]


def build_hemo_deep_interpretation(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    """Generates the final clinical interpretation string."""
    ui = ui or {}
    der = der or {}
    h = _collect_inputs(ui, der)

    # 1. Safety Check
    plausibility_warning = _check_plausibility(h)
    if plausibility_warning:
        return plausibility_warning

    # 2. Primary Logic
    primary = _pick_primary(h)
    if not primary:
        # Fallback if no primary triggered but risk exists
        secondary_only = _pick_secondary(h, None)
        if secondary_only:
             return " ".join([x.strip() for x in secondary_only if x]).strip()
        return ""

    # 3. Secondary Logic
    secondary = _pick_secondary(h, primary)

    lines: List[str] = ["Hämodynamische Verlaufseinordnung:", primary]
    lines.extend(secondary)
    
    return " ".join([x.strip() for x in lines if x]).strip()