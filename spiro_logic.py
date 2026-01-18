Filename: spiro_logic.py
Full Content:
"""Spiro-Logic: deterministic CPET expert logic (Wasserman, ESC 2022, Guazzi).

MASTERMIND EDITION:
- Data Layer: Immutable `CpetData` dataclass with centralized parsing & sanitization.
- Logic Layer: Pure functional modules using named constants (`CpetThresholds`).
- Validation Layer: Physics Engine checks for biological plausibility before analysis.
- Presentation Layer: Decoupled HTML rendering for clean separation of concerns.

Clinical design goals
---------------------
- Deterministic, testable, reproducible (no LLM dependencies)
- Immediate plausibility checks and pattern recognition
- Live education text for each module
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Final

# --- 1. Central Clinical Configuration ---

class CpetThresholds:
    """Central definition of clinical cutoffs (ESC 2022, Wasserman, Guazzi)."""
    # Effort
    RER_MAX = 1.10
    RER_HIGH = 1.05
    BORG_RPE_MAX = 9  # Scale 0-10
    
    # Chronotropy
    HR_PRED_LOW = 85.0  # %
    
    # Mechanics
    BR_LOW = 15.0  # % (Breathing Reserve)
    BR_NORMAL = 20.0  # %
    VE_MVV_RATIO_HIGH = 0.85
    
    # Gas Exchange (PH/Vascular)
    VE_VCO2_SLOPE_HIGH = 35.0
    VE_VCO2_SLOPE_ELEVATED = 30.0
    PETCO2_LOW = 30.0  # mmHg
    PETCO2_DROP = 2.0  # mmHg
    SPO2_DESAT_ABS = 88.0  # %
    SPO2_DROP_DELTA = 4.0  # %
    
    # Prognosis (VO2peak)
    VO2_LOW_RISK = 15.0  # ml/min/kg
    VO2_INTERMEDIATE = 11.0
    
    # Safety
    BP_SYS_CRITICAL = 220
    BP_DIA_CRITICAL = 110
    BP_SYS_DROP = 10


# --- 2. Data Processing Layer ---

# Keys where 0.0 is structurally impossible and means "missing"
_ZERO_IS_MISSING_KEYS: Final[Set[str]] = {
    "cpet_rer_peak", "cpet_hr_peak_bpm", "cpet_hr_pct_pred",
    "cpet_peak_vo2_ml_kg_min", "cpet_peak_vo2_pct_pred",
    "cpet_peak_o2_pulse_ml", "cpet_o2_pulse_slope",
    "cpet_vo2_wr_slope_ml_min_w", "cpet_bp_sys_rest",
    "cpet_bp_dia_rest", "cpet_bp_sys_peak", "cpet_bp_dia_peak",
    "cpet_ve_vco2_slope", "cpet_petco2_rest_mmhg",
    "cpet_petco2_peak_mmhg", "cpet_petco2_vt1_mmhg",
    "cpet_breathing_reserve_pct", "cpet_ve_vco2_vt1",
    "cpet_spo2_rest_pct", "cpet_spo2_peak_pct",
    "cpet_spo2_nadir_pct", "cpet_o2_supp_l_min",
    "cpet_ve_peak_l_min", "cpet_mvv_l_min",
    "cpet_vo2_vt1_ml_kg_min", "cpet_vo2_vt2_ml_kg_min",
    "cpet_vo2_vt1_ml_min", "cpet_vo2_vt2_ml_min",
}

@dataclass(frozen=True)
class CpetData:
    """Immutable, validated container for CPET readings."""
    done: bool
    
    # Physiology
    rer: Optional[float]
    hr_peak: Optional[float]
    hr_pct: Optional[float]
    ve_peak: Optional[float]
    mvv: Optional[float]
    mvv_source: str
    br_pct: Optional[float]
    ve_vco2_slope: Optional[float]
    pet_rest: Optional[float]
    pet_peak: Optional[float]
    pet_vt1: Optional[float]
    vo2_peak_rel: Optional[float] # ml/kg/min
    vo2_pct: Optional[float]
    o2_pulse_peak: Optional[float]
    o2_pulse_slope: Optional[float]
    o2_pulse_pattern: str
    vo2_wr_slope: Optional[float]
    spo2_rest: Optional[float]
    spo2_peak: Optional[float]
    spo2_nadir: Optional[float]
    o2_supp: Optional[float]
    
    # BP & Safety
    bp_sys_rest: Optional[float]
    bp_dia_rest: Optional[float]
    bp_sys_peak: Optional[float]
    bp_dia_peak: Optional[float]
    angina: bool
    dizziness: bool
    syncope: bool
    palpitations: bool
    arrhythmia: bool
    arrhythmia_text: str
    st_changes: str
    
    # Quality / Subj
    borg_rpe: Optional[float]
    borg_dysp: Optional[float]
    borg_leg: Optional[float]
    stop_reason: str
    stop_reason_text: str
    hyperventilation: bool
    beta_blocker: bool
    sinus_node_disorder: bool
    
    # 9-Panel Visuals
    panel_available: bool
    vt1_id: str
    vt1_method: str
    rcp_id: str
    eov: bool
    flow_limit_visual: str
    vo2wr_pattern: str
    veeq_pattern: str
    panel_comment: str
    
    # Overrides
    override_label: str
    override_text: str
    manual_steps: str

    @staticmethod
    def parse(ui: Dict[str, Any]) -> CpetData:
        """Factory: Parses UI dict into strict CpetData object with sanitization."""
        
        def _f(key: str) -> Optional[float]:
            val = ui.get(key)
            if val is None or val == "": return None
            try:
                # Handle european float format just in case
                if isinstance(val, str): val = val.replace(",", ".")
                f = float(val)
                # Filter '0' where 0 is impossible
                if f == 0 and key in _ZERO_IS_MISSING_KEYS: return None
                return f
            except (ValueError, TypeError): return None
            
        def _s(key: str) -> str:
            val = ui.get(key)
            return str(val).strip() if val is not None else ""
            
        def _b(key: str) -> bool:
            return bool(ui.get(key))

        return CpetData(
            done=_b("cpet_done"),
            rer=_f("cpet_rer_peak"),
            hr_peak=_f("cpet_hr_peak_bpm"),
            hr_pct=_f("cpet_hr_pct_pred"),
            ve_peak=_f("cpet_ve_peak_l_min"),
            mvv=_f("cpet_mvv_l_min"),
            mvv_source=_s("cpet_mvv_source"),
            br_pct=_f("cpet_breathing_reserve_pct"),
            ve_vco2_slope=_f("cpet_ve_vco2_slope"),
            pet_rest=_f("cpet_petco2_rest_mmhg"),
            pet_peak=_f("cpet_petco2_peak_mmhg"),
            pet_vt1=_f("cpet_petco2_vt1_mmhg"),
            vo2_peak_rel=_f("cpet_peak_vo2_ml_kg_min"),
            vo2_pct=_f("cpet_peak_vo2_pct_pred"),
            o2_pulse_peak=_f("cpet_peak_o2_pulse_ml"),
            o2_pulse_slope=_f("cpet_o2_pulse_slope"),
            o2_pulse_pattern=_s("cpet_o2_pulse_pattern").lower(),
            vo2_wr_slope=_f("cpet_vo2_wr_slope_ml_min_w"),
            spo2_rest=_f("cpet_spo2_rest_pct"),
            spo2_peak=_f("cpet_spo2_peak_pct"),
            spo2_nadir=_f("cpet_spo2_nadir_pct"),
            o2_supp=_f("cpet_o2_supp_l_min"),
            bp_sys_rest=_f("cpet_bp_sys_rest"),
            bp_dia_rest=_f("cpet_bp_dia_rest"),
            bp_sys_peak=_f("cpet_bp_sys_peak"),
            bp_dia_peak=_f("cpet_bp_dia_peak"),
            angina=_b("cpet_angina"),
            dizziness=_b("cpet_dizziness"),
            syncope=_b("cpet_syncope"),
            palpitations=_b("cpet_palpitations"),
            arrhythmia=_b("cpet_arrhythmia"),
            arrhythmia_text=_s("cpet_arrhythmia_text"),
            st_changes=_s("cpet_st_changes").lower(),
            borg_rpe=_f("cpet_borg_rpe"),
            borg_dysp=_f("cpet_borg_dyspnea"),
            borg_leg=_f("cpet_borg_leg"),
            stop_reason=_s("cpet_stop_reason"),
            stop_reason_text=_s("cpet_stop_reason_text"),
            hyperventilation=_b("cpet_hyperventilation"),
            beta_blocker=_b("cpet_beta_blocker"),
            sinus_node_disorder=_b("cpet_sinus_node_disorder"),
            panel_available=_b("cpet_9panel_available"),
            vt1_id=_s("cpet_9panel_vt1_identified").lower(),
            vt1_method=_s("cpet_9panel_vt1_method"),
            rcp_id=_s("cpet_9panel_rcp_identified").lower(),
            eov=_b("cpet_9panel_eov"),
            flow_limit_visual=_s("cpet_9panel_flowvol_limit").lower(),
            vo2wr_pattern=_s("cpet_9panel_vo2wr_pattern").lower(),
            veeq_pattern=_s("cpet_9panel_veeq_pattern").lower(),
            panel_comment=_s("cpet_9panel_comment"),
            override_label=_s("cpet_limitation_override").lower(),
            override_text=_s("cpet_limitation_override_text"),
            manual_steps=_s("cpet_next_steps_manual"),
        )

@dataclass
class ModuleResult:
    """Result of a single logic module analysis."""
    title: str
    status: str
    severity: str  # info, warn, bad
    feedback: str
    teaching: str
    followups: List[str] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SpiroLogicResult:
    """Aggregated analysis result."""
    module0: ModuleResult
    module1: ModuleResult
    module2: ModuleResult
    module3: ModuleResult
    module4: ModuleResult
    module5_mech: ModuleResult
    module6_gas: ModuleResult
    module7_safety: ModuleResult
    module9: ModuleResult
    module_final: ModuleResult
    overall_summary: str
    headline: str
    clinical_summary: str
    report_text: str
    derived: Dict[str, Any]


# --- 3. Physics Engine (Validation) ---

def _validate_physics(d: CpetData) -> List[str]:
    """Checks for biological impossibilities or major inconsistencies."""
    alerts = []
    
    # VE > MVV (Physiologically impossible if effort is strictly volitional)
    if d.ve_peak and d.mvv and d.mvv > 0 and d.ve_peak > (d.mvv * 1.2):
        alerts.append(f"⚠️ Plausibilität: VEpeak ({d.ve_peak:.0f}) > 120% MVV ({d.mvv:.0f}). Messfehler?")

    # RER < 0.6 (Impossible)
    if d.rer and d.rer < 0.6:
        alerts.append(f"⚠️ Plausibilität: RER {d.rer:.2f} ist physiologisch unmöglich (Kalibration?).")

    # HR extreme
    if d.hr_peak and d.hr_peak > 250:
        alerts.append(f"⚠️ Plausibilität: HF Peak {d.hr_peak:.0f} bpm ist extrem hoch.")

    # BP Diastolic > Systolic
    if d.bp_sys_peak and d.bp_dia_peak and d.bp_dia_peak > d.bp_sys_peak:
        alerts.append("⛔ Fehler: Diastolischer RR höher als systolischer RR.")
        
    return alerts


# --- 4. Logic Modules ---

def _fmt(x: Optional[float], nd: int = 1) -> str:
    return f"{x:.{nd}f}" if x is not None else ""

def analyze_module_0_quality(d: CpetData, physics_alerts: List[str]) -> ModuleResult:
    parts = []
    followups = []
    
    # Append physics alerts first
    for alert in physics_alerts:
        parts.append(alert)
        
    # Maximality
    rer_ok = d.rer is not None and d.rer >= CpetThresholds.RER_MAX
    rer_high = d.rer is not None and d.rer >= CpetThresholds.RER_HIGH
    borg_ok = d.borg_rpe is not None and d.borg_rpe >= CpetThresholds.BORG_RPE_MAX
    
    effort_status = "unklar"
    effort_ok = None
    
    if rer_ok or borg_ok:
        effort_status = "maximal wahrscheinlich"
        effort_ok = True
    elif rer_high:
        effort_status = "hoch, maximal möglich"
        effort_ok = True
    elif d.rer is not None or d.borg_rpe is not None:
        effort_status = "eher submaximal"
        effort_ok = False
        
    # Safety Stop
    safe_keys = {"angina", "ischämie", "synkope", "arrhythmie", "hypotonie", "desaturation"}
    is_safe_stop = any(k in d.stop_reason.lower() for k in safe_keys)
    
    if d.stop_reason: parts.append(f"Testende: {d.stop_reason}.")
    if d.stop_reason_text: parts.append(f"Details: {d.stop_reason_text}.")
    if d.rer: parts.append(f"RER Peak {_fmt(d.rer, 2)}.")
    if d.hr_pct: parts.append(f"HF Peak {_fmt(d.hr_pct, 0)} % Soll.")
    if d.borg_rpe: parts.append(f"Borg RPE {_fmt(d.borg_rpe, 0)}.")
    if effort_status != "unklar": parts.append(f"Ausbelastung: {effort_status}.")
    
    if is_safe_stop:
        parts.append("Sicherheitsabbruch (validiert submaximale Leistung).")
    elif effort_ok is False:
        followups.append("Submaximale Leistung limitiert die Interpretation.")
        
    if d.hyperventilation and rer_ok:
        followups.append("Hyperventilation: RER ggf. falsch hoch.")
        
    sev = "warn" if (effort_ok is False and not is_safe_stop) else "info"
    if physics_alerts: sev = "bad"
    
    return ModuleResult(
        title="Modul 0: Qualität", status=effort_status, severity=sev,
        feedback=" ".join(parts),
        teaching="RER ≥ 1.10 beweist metabolische Maximalleistung. Sicherheitsabbruch ist ein valider Endpunkt.",
        followups=followups,
        flags={"cpet_test_effort_ok_local": effort_ok, "cpet_stop_safety_local": is_safe_stop, "cpet_test_quality_status": effort_status}
    )

def analyze_module_1_drive(d: CpetData, m0: ModuleResult) -> ModuleResult:
    parts = []
    followups = []
    
    # Chronotropy Logic
    chrono_susp = False
    if d.rer and d.rer >= CpetThresholds.RER_MAX and d.hr_pct and d.hr_pct < CpetThresholds.HR_PRED_LOW:
        chrono_susp = True
        parts.append("Chronotrope Inkompetenz verdächtig (Maximaler RER, niedrige HF-Reserve).")
        followups.append("Betablocker? Sinusknoten?")
    elif d.hr_pct and d.hr_pct < CpetThresholds.HR_PRED_LOW and d.rer and d.rer >= CpetThresholds.RER_HIGH:
         parts.append("HF-Anstieg niedrig im Verhältnis zur metabolischen Last.")

    if d.hr_peak: parts.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm.")
    if d.hr_pct: parts.append(f"({_fmt(d.hr_pct, 0)} % Soll).")
    if d.beta_blocker: parts.append("Unter Betablockade.")
    
    return ModuleResult(
        title="Modul 1: Antrieb", status="chrono_fail" if chrono_susp else "ok",
        severity="warn" if chrono_susp else "info",
        feedback=" ".join(parts),
        teaching="Chronotrope Inkompetenz (HF < 85% Soll bei RER > 1.10) limitiert das HZV.",
        followups=followups,
        flags={"cpet_chronotropic_suspected": chrono_susp}
    )

def analyze_module_2_capacity(d: CpetData) -> ModuleResult:
    vo2 = d.vo2_peak_rel
    if vo2 is None:
        return ModuleResult("Modul 2: Aerobe Kapazität", "missing", "warn", "Keine VO2 Daten.", "VO2peak ist Prognosemarker.", [], {})
        
    risk = "high"
    if vo2 > CpetThresholds.VO2_LOW_RISK: risk = "low"
    elif vo2 >= CpetThresholds.VO2_INTERMEDIATE: risk = "intermediate"
    
    txt = f"V'O2peak {_fmt(vo2, 1)} mL/min/kg."
    if d.vo2_pct: txt += f" ({_fmt(d.vo2_pct, 0)}% Soll)."
    txt += f" Risiko (ESC PH): {risk.upper()}."
    
    sev = "bad" if risk == "high" else ("warn" if risk == "intermediate" else "info")
    return ModuleResult(
        title="Modul 2: Kapazität", status=risk, severity=sev, feedback=txt,
        teaching="VO2peak < 11 ml/min/kg gilt als Hochrisiko bei PH (ESC 2022).",
        flags={"cpet_vo2_risk_band_local": risk}
    )

def analyze_module_3_circ(d: CpetData) -> ModuleResult:
    parts = []
    followups = []
    
    plateau = d.o2_pulse_pattern in ("plateau", "fallend")
    high_al = d.bp_dia_peak and d.bp_dia_peak >= 100
    mismatch = plateau and high_al
    
    if d.o2_pulse_peak: parts.append(f"O2-Puls {_fmt(d.o2_pulse_peak, 1)} mL.")
    if d.o2_pulse_pattern: parts.append(f"Verlauf: {d.o2_pulse_pattern}.")
    if d.bp_sys_peak: parts.append(f"RR Peak {_fmt(d.bp_sys_peak,0)}/{_fmt(d.bp_dia_peak,0)} mmHg.")
    
    if mismatch:
        parts.append("Afterload Mismatch (Plateau + hohe Nachlast).")
        followups.append("Hypertonie-Management.")
    elif plateau:
        parts.append("Schlagvolumen-Limitierung (Plateau).")
        
    sev = "warn" if (plateau or high_al) else "info"
    return ModuleResult(
        title="Modul 3: Zirkulation", status="mismatch" if mismatch else "ok", severity=sev,
        feedback=" ".join(parts),
        teaching="O2-Puls-Plateau deutet auf SV-Limitierung hin.",
        followups=followups,
        flags={"cpet_afterload_mismatch": mismatch, "cpet_o2_pulse_plateau": plateau}
    )

def analyze_module_4_vent(d: CpetData) -> ModuleResult:
    ve_high = d.ve_vco2_slope and d.ve_vco2_slope >= CpetThresholds.VE_VCO2_SLOPE_HIGH
    pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
    pet_low = pet_start and pet_start < CpetThresholds.PETCO2_LOW
    pet_drop = False
    if pet_start and d.pet_peak:
        if d.pet_peak < (pet_start - CpetThresholds.PETCO2_DROP):
            pet_drop = True
            
    mech_ok = d.br_pct is None or d.br_pct >= CpetThresholds.BR_NORMAL
    ph_pattern = bool(ve_high and (pet_drop or pet_low) and mech_ok)
    
    parts = []
    if d.ve_vco2_slope: parts.append(f"V'E/V'CO2 Slope {_fmt(d.ve_vco2_slope, 0)}.")
    if pet_start: parts.append(f"PETCO2 Start {_fmt(pet_start, 0)} mmHg.")
    if d.pet_peak: parts.append(f"Peak {_fmt(d.pet_peak, 0)} mmHg.")
    
    if ph_pattern: parts.append("Muster: Pulmonal-vaskulär (PH-Verdacht).")
    elif ve_high: parts.append("Ventilatorisch ineffizient.")
    
    sev = "bad" if ph_pattern else ("warn" if ve_high else "info")
    return ModuleResult(
        title="Modul 4: Gasaustausch", status="ph" if ph_pattern else "ok", severity=sev,
        feedback=" ".join(parts),
        teaching="Hoher Slope + fallendes PETCO2 bei freier Mechanik ist typisch für PH.",
        flags={"cpet_pulm_vasc_pattern": ph_pattern}
    )

def analyze_module_5_mech(d: CpetData) -> ModuleResult:
    parts = []
    mech_lim = False
    
    # Calc ratio
    ratio = None
    if d.ve_peak and d.mvv and d.mvv > 0:
        ratio = d.ve_peak / d.mvv
        if ratio >= CpetThresholds.VE_MVV_RATIO_HIGH: mech_lim = True
    
    br_val = d.br_pct
    if br_val is None and ratio is not None:
         br_val = (1.0 - ratio) * 100.0

    if br_val is not None and br_val < CpetThresholds.BR_LOW:
        mech_lim = True
    if d.flow_limit_visual == "ja":
        mech_lim = True
        
    if br_val is not None: parts.append(f"Atemreserve {_fmt(br_val, 0)}%.")
    if ratio: parts.append(f"V'E/MVV {_fmt(ratio, 2)}.")
    if d.flow_limit_visual == "ja": parts.append("Flow-Loop limitiert.")
    
    if mech_lim: parts.append("Ventilatorische Limitation.")
    
    return ModuleResult(
        title="Modul 5: Mechanik", status="mech_lim" if mech_lim else "ok", severity="warn" if mech_lim else "info",
        feedback=" ".join(parts),
        teaching="Atemreserve < 15% spricht für mechanische Limitation.",
        flags={"cpet_mechanical_limited_local": mech_lim, "cpet_ve_mvv_ratio_local": ratio}
    )

def analyze_module_6_gas(d: CpetData) -> ModuleResult:
    parts = []
    spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
    desat = False
    
    if d.spo2_rest: parts.append(f"Ruhe {_fmt(d.spo2_rest,0)}%.")
    if spo2_min: parts.append(f"Min {_fmt(spo2_min,0)}%.")
    
    if spo2_min and spo2_min < CpetThresholds.SPO2_DESAT_ABS: desat = True
    if d.spo2_rest and spo2_min and (d.spo2_rest - spo2_min) >= CpetThresholds.SPO2_DROP_DELTA: desat = True
    
    if desat: parts.append("Relevante Desaturation.")
    if d.o2_supp: parts.append(f"unter {_fmt(d.o2_supp, 1)}L O2.")
    
    return ModuleResult(
        title="Modul 6: Oxygenierung", status="desat" if desat else "ok", severity="warn" if desat else "info",
        feedback=" ".join(parts),
        teaching="Desaturation < 88% oder Abfall > 4% ist pathologisch.",
        flags={"cpet_desaturation_local": desat}
    )

def analyze_module_7_safety(d: CpetData) -> ModuleResult:
    parts = []
    
    htn = (d.bp_sys_peak and d.bp_sys_peak >= CpetThresholds.BP_SYS_CRITICAL) or \
          (d.bp_dia_peak and d.bp_dia_peak >= CpetThresholds.BP_DIA_CRITICAL)
    hypo = False
    if d.bp_sys_rest and d.bp_sys_peak and d.bp_sys_peak < (d.bp_sys_rest - CpetThresholds.BP_SYS_DROP):
        hypo = True
    if d.syncope: hypo = True
    
    ischemia = d.angina or ("senk" in d.st_changes) or ("elev" in d.st_changes)
    
    if htn: parts.append("Exzessive Hypertonie.")
    if hypo: parts.append("Belastungshypotonie!")
    if d.arrhythmia: parts.append(f"Arrhythmie ({d.arrhythmia_text}).")
    if ischemia: parts.append("Ischämiezeichen.")
    
    red_flag = hypo or d.arrhythmia or ischemia
    
    return ModuleResult(
        title="Modul 7: Sicherheit", status="bad" if red_flag else "ok", severity="bad" if red_flag else ("warn" if htn else "info"),
        feedback=" ".join(parts) if parts else "Keine Akut-Events.",
        teaching="Hypotonie, Ischämie oder maligne Arrhythmien sind Abbruchkriterien.",
        flags={"cpet_safety_red_flag": red_flag, "cpet_severe_htn_local": htn}
    )

def analyze_module_9(d: CpetData) -> ModuleResult:
    parts = []
    if not d.panel_available:
        parts.append("Nicht dokumentiert.")
    else:
        if d.eov: parts.append("EOV vorhanden (Cave!).")
        if d.vt1_id == "ja": parts.append(f"VT1 erkannt ({d.vt1_method}).")
        if d.rcp_id == "ja": parts.append("RCP erkannt.")
        if d.vo2wr_pattern in ("plateau", "flach"): parts.append("VO2/W flach/Plateau.")
        if d.flow_limit_visual == "ja": parts.append("Flow-Loop limitiert.")
        if d.panel_comment: parts.append(f"Kommentar: {d.panel_comment}.")
        
    return ModuleResult(
        title="Modul 9: Panel", status="eov" if d.eov else "ok", severity="warn" if d.eov else "info",
        feedback=" ".join(parts),
        teaching="EOV ist ein schlechter prognostischer Marker.",
        flags={"cpet_eov_present": d.eov}
    )

def analyze_module_final(d: CpetData, modules: Dict[str, ModuleResult]) -> ModuleResult:
    m0, m1, m3, m4, m5, m6, m7 = [modules[k] for k in ["m0", "m1", "m3", "m4", "m5", "m6", "m7"]]
    
    label = "Gemischt / Unklar"
    conf = "niedrig"
    rec = []
    
    if m7.flags.get("cpet_safety_red_flag") or m0.flags.get("cpet_stop_safety_local"):
        label = "Sicherheitslimitiert"
        conf = "hoch"
        rec.append("Kardiologische Abklärung.")
    elif m4.flags.get("cpet_pulm_vasc_pattern"):
        label = "Pulmonal-vaskulär (PH-Verdacht)"
        conf = "hoch"
        rec.append("RHK / Echo / V/Q.")
    elif m5.flags.get("cpet_mechanical_limited_local"):
        label = "Ventilatorisch (mechanisch)"
        conf = "mittel"
        rec.append("Lufu / CT.")
    elif m3.flags.get("cpet_afterload_mismatch") or m3.flags.get("cpet_o2_pulse_plateau"):
        label = "Zirkulatorisch (Nachlast/SV)"
        conf = "mittel"
    elif m1.flags.get("cpet_chronotropic_suspected"):
        label = "Chronotrope Inkompetenz"
        conf = "mittel"
    elif d.vo2_peak_rel and d.vo2_peak_rel < CpetThresholds.VO2_LOW_RISK:
        label = "Peripher / Deconditioning"
        conf = "mittel"
        
    if d.override_label:
        label = f"{label} (Manuell: {d.override_label})"
        conf = "ärztlich"
        
    feedback = f"Typ: {label} (Konfidenz: {conf})."
    if rec: feedback += " " + " ".join(rec)
    if d.manual_steps: feedback += f" Zusatz: {d.manual_steps}"
    
    return ModuleResult(
        title="Synthese", status="final", severity="info", feedback=feedback,
        teaching="Gesamtintegration.", flags={"cpet_limitation_type_final": label, "cpet_limitation_confidence": conf}
    )

# --- 6. Orchestrator ---

def analyze(ui: Dict[str, Any]) -> Optional[SpiroLogicResult]:
    # 1. Parse Data
    d = CpetData.parse(ui)
    if not d.done: return None
    
    # 2. Physics Check
    alerts = _validate_physics(d)
    
    # 3. Run Logic
    m0 = analyze_module_0_quality(d, alerts)
    m1 = analyze_module_1_drive(d, m0)
    m2 = analyze_module_2_capacity(d)
    m3 = analyze_module_3_circ(d)
    m4 = analyze_module_4_vent(d)
    m5 = analyze_module_5_mech(d)
    m6 = analyze_module_6_gas(d)
    m7 = analyze_module_7_safety(d)
    m9 = analyze_module_9(d)
    
    module_map = {
        "m0": m0, "m1": m1, "m2": m2, "m3": m3, 
        "m4": m4, "m5": m5, "m6": m6, "m7": m7, "m9": m9
    }
    m_final = analyze_module_final(d, module_map)
    
    # 4. Generate Reports
    summary = m_final.feedback
    if m7.severity == "bad": summary = "SICHERHEITSWARNUNG! " + summary
    
    report_lines = [
        "Spiroergometrie (Strukturiert):",
        f"- {m0.feedback}",
        f"- {m3.feedback}",
        f"- {m4.feedback}",
        f"=> {m_final.feedback}"
    ]
    
    return SpiroLogicResult(
        module0=m0, module1=m1, module2=m2, module3=m3,
        module4=m4, module5_mech=m5, module6_gas=m6,
        module7_safety=m7, module9=m9, module_final=m_final,
        overall_summary=summary,
        headline=f"CPET: {m_final.flags['cpet_limitation_type_final']}",
        clinical_summary=summary,
        report_text="\n".join(report_lines),
        derived={**m_final.flags, **m4.flags}
    )

def build_wizard_outputs(ui: Dict[str, Any]) -> Dict[str, Any]:
    res = analyze(ui)
    if not res: return {"report_text": ""}
    
    def _html(m: ModuleResult) -> str:
        badge = "🔴" if m.severity == "bad" else ("🟠" if m.severity == "warn" else "🟢")
        return (f"<div class='spiro-box'><div class='spiro-title'>{badge} {m.title}</div>"
                f"<div class='spiro-content'>{m.feedback}</div>"
                f"<div class='spiro-teach'>{m.teaching}</div></div>")
                
    return {
        "mod0_html": _html(res.module0),
        "mod1_html": _html(res.module1),
        "mod2_html": _html(res.module2),
        "mod3_html": _html(res.module3),
        "mod4_html": _html(res.module4),
        "mod5_html": _html(res.module5_mech),
        "mod6_html": _html(res.module6_gas),
        "mod7_html": _html(res.module7_safety),
        "mod9_html": _html(res.module9),
        "modfinal_html": _html(res.module_final),
        "overall_html": f"<b>{res.headline}</b><br>{res.clinical_summary}",
        "headline": res.headline,
        "clinical_summary": res.clinical_summary,
        "report_text": res.report_text,
        "derived": res.derived,
        "need_chrono_followups": res.module1.status == "chrono_fail",
        "suspect_ph": res.module4.status == "ph",
        "eov_present": res.module9.flags.get("cpet_eov_present", False),
    }