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
import html
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
    parts: List[str] = []
    followups: List[str] = []

    for alert in physics_alerts:
        parts.append(alert)

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

    safe_keys = {"angina", "ischämie", "synkope", "arrhythmie", "hypotonie", "desaturation"}
    is_safe_stop = any(k in (d.stop_reason or "").lower() for k in safe_keys)

    if d.stop_reason:
        parts.append(f"Testende: {d.stop_reason}.")
    if d.stop_reason_text:
        parts.append(f"Details: {d.stop_reason_text}.")
    if d.rer is not None:
        parts.append(f"RER Peak {_fmt(d.rer, 2)}.")
    if d.hr_pct is not None:
        parts.append(f"HF Peak {_fmt(d.hr_pct, 0)} % Soll.")
    if d.borg_rpe is not None:
        parts.append(f"Borg RPE {_fmt(d.borg_rpe, 0)}.")
    if effort_status != "unklar":
        parts.append(f"Ausbelastung: {effort_status}.")

    if is_safe_stop:
        parts.append("Sicherheitsabbruch. Submaximale Leistung ist dann plausibel.")
    elif effort_ok is False:
        followups.append("Submaximale Leistung limitiert die Interpretation.")
        followups.append("Abbruchgrund, RER und Borg konsistent dokumentieren.")

    if d.hyperventilation and rer_ok:
        followups.append("Hyperventilation möglich. RER kann falsch hoch sein.")

    if not d.stop_reason and effort_ok is None:
        followups.append("Abbruchgrund ergänzen, sonst ist die Qualitätsbewertung unklar.")

    sev = "warn" if (effort_ok is False and not is_safe_stop) else "info"
    if physics_alerts:
        sev = "bad"

    return ModuleResult(
        title="Modul 0: Qualität",
        status=effort_status,
        severity=sev,
        feedback=" ".join(parts) if parts else "Keine Qualitätsangaben.",
        teaching="Ausbelastung wird über RER, Borg und Abbruchgrund beurteilt. Submaximale Tests sind interpretierbar, aber nur mit klarer Begründung. Sicherheitsabbruch ist ein valider Endpunkt.",
        followups=followups,
        flags={"cpet_test_effort_ok_local": effort_ok, "cpet_stop_safety_local": is_safe_stop, "cpet_test_quality_status": effort_status},
    )

def analyze_module_1_drive(d: CpetData, m0: ModuleResult) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    chrono_susp = False

    if d.rer is not None and d.rer >= CpetThresholds.RER_MAX and d.hr_pct is not None and d.hr_pct < CpetThresholds.HR_PRED_LOW:
        chrono_susp = True
        parts.append("Chronotrope Inkompetenz verdächtig. Hoher RER bei niedriger HF Reserve.")
        followups.append("Betablocker und andere frequenzsenkende Medikation prüfen.")
        followups.append("Sinusknotenerkrankung oder Schrittmacherstatus prüfen.")
    elif d.hr_pct is not None and d.hr_pct < CpetThresholds.HR_PRED_LOW and d.rer is not None and d.rer >= CpetThresholds.RER_HIGH:
        parts.append("HF Anstieg niedrig im Verhältnis zur metabolischen Last.")

    if d.hr_peak is not None:
        parts.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm.")
    if d.hr_pct is not None:
        parts.append(f"({_fmt(d.hr_pct, 0)} % Soll).")
    if d.beta_blocker:
        parts.append("Unter Betablockade.")

    if chrono_susp and m0.flags.get("cpet_test_effort_ok_local") is False:
        followups.append("Wenn Ausbelastung submaximal: chronotrope Aussage ist unsicher.")

    return ModuleResult(
        title="Modul 1: Antrieb",
        status="chrono_fail" if chrono_susp else "ok",
        severity="warn" if chrono_susp else "info",
        feedback=" ".join(parts) if parts else "Keine Chronotropie Angaben.",
        teaching="Chronotrope Inkompetenz ist wahrscheinlich, wenn bei RER über 1.10 weniger als 85% der Soll HF erreicht werden. Sie limitiert das Herzzeitvolumen und kann Symptome erklären.",
        followups=followups,
        flags={"cpet_chronotropic_suspected": chrono_susp},
    )

def analyze_module_2_capacity(d: CpetData) -> ModuleResult:
    followups: List[str] = []
    vo2 = d.vo2_peak_rel
    if vo2 is None:
        followups.append("VO2peak ergänzen, sonst keine Risiko Einordnung möglich.")
        return ModuleResult(
            title="Modul 2: Kapazität",
            status="missing",
            severity="warn",
            feedback="Keine VO2 Daten.",
            teaching="VO2peak ist Prognosemarker. Interpretation setzt eine nachvollziehbare Ausbelastung voraus.",
            followups=followups,
            flags={},
        )

    risk = "high"
    if vo2 > CpetThresholds.VO2_LOW_RISK:
        risk = "low"
    elif vo2 >= CpetThresholds.VO2_INTERMEDIATE:
        risk = "intermediate"

    txt = f"V'O2peak {_fmt(vo2, 1)} mL/min/kg."
    if d.vo2_pct:
        txt += f" ({_fmt(d.vo2_pct, 0)}% Soll)."
    txt += f" Risiko (ESC PH): {risk.upper()}."

    if risk == "high":
        followups.append("Wenn Ausbelastung unklar: Modul 0 prüfen, sonst Risiko kann überschätzt sein.")
        followups.append("Bei PH: klinischen Verlauf, 6 MWD, BNP, Echo und RHK Befund integrieren.")
    elif risk == "intermediate":
        followups.append("Verlaufskontrolle einplanen und mit Symptomen und Belastbarkeit abgleichen.")

    sev = "bad" if risk == "high" else ("warn" if risk == "intermediate" else "info")
    return ModuleResult(
        title="Modul 2: Kapazität",
        status=risk,
        severity=sev,
        feedback=txt,
        teaching="Bei PH ist VO2peak < 11 ml/min/kg ein Hochrisiko Kriterium. Werte immer im Kontext von Effort und Abbruchgrund bewerten.",
        followups=followups,
        flags={"cpet_vo2_risk_band_local": risk},
    )

def analyze_module_3_circ(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    plateau = str(d.o2_pulse_pattern or "").lower() in ("plateau", "fallend")
    high_al = d.bp_dia_peak is not None and d.bp_dia_peak >= 100
    mismatch = bool(plateau and high_al)

    if d.o2_pulse_peak is not None:
        parts.append(f"O2 Puls {_fmt(d.o2_pulse_peak, 1)} mL.")
    if d.o2_pulse_pattern:
        parts.append(f"Verlauf: {d.o2_pulse_pattern}.")
    if d.bp_sys_peak is not None or d.bp_dia_peak is not None:
        parts.append(f"RR Peak {_fmt(d.bp_sys_peak,0)}/{_fmt(d.bp_dia_peak,0)} mmHg.")

    if mismatch:
        parts.append("Afterload Mismatch. Plateau plus hohe Nachlast.")
        followups.append("Belastungsblutdruck und antihypertensive Therapie prüfen.")
        followups.append("Echo und ggf. RHK Kontext berücksichtigen.")
    elif plateau:
        parts.append("Schlagvolumen Limitierung möglich.")
        followups.append("Wenn gleichzeitig VE VCO2 Muster auffällig: zirkulatorisch pulmonal vaskulär abgrenzen.")

    if not plateau and high_al:
        followups.append("Isolierte hohe Nachlast kann die Limitation mitprägen.")

    sev = "warn" if (plateau or high_al) else "info"
    return ModuleResult(
        title="Modul 3: Zirkulation",
        status="mismatch" if mismatch else "ok",
        severity=sev,
        feedback=" ".join(parts) if parts else "Keine Zirkulationsangaben.",
        teaching="Ein O2 Puls Plateau spricht für eine Schlagvolumen Limitierung. Ein gleichzeitiger hoher diastolischer RR stützt eine Nachlast Problematik.",
        followups=followups,
        flags={"cpet_afterload_mismatch": mismatch, "cpet_o2_pulse_plateau": plateau},
    )

def analyze_module_4_vent(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    ve_high = d.ve_vco2_slope is not None and d.ve_vco2_slope >= CpetThresholds.VE_VCO2_SLOPE_HIGH
    pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
    pet_low = pet_start is not None and pet_start < CpetThresholds.PETCO2_LOW

    pet_drop = False
    if pet_start is not None and d.pet_peak is not None:
        if d.pet_peak < (pet_start - CpetThresholds.PETCO2_DROP):
            pet_drop = True

    mech_ok = d.br_pct is None or d.br_pct >= CpetThresholds.BR_NORMAL
    ph_pattern = bool(ve_high and (pet_drop or pet_low) and mech_ok)

    if d.ve_vco2_slope is not None:
        parts.append(f"VE VCO2 Slope {_fmt(d.ve_vco2_slope, 0)}.")
    if pet_start is not None:
        parts.append(f"PETCO2 Start {_fmt(pet_start, 0)} mmHg.")
    if d.pet_peak is not None:
        parts.append(f"Peak {_fmt(d.pet_peak, 0)} mmHg.")

    if ph_pattern:
        parts.append("Muster pulmonal vaskulär. PH Verdacht.")
        followups.append("Abgleich mit Echo und RHK. Bei Bedarf V Q und CT Diagnostik.")
        followups.append("Wenn Mechanik doch limitiert: gemischte Limitation erwägen.")
    elif ve_high:
        parts.append("Ventilatorisch ineffizient.")
        followups.append("VE VCO2 Slope im Verlauf einordnen und mit PETCO2 Verlauf plausibilisieren.")

    sev = "bad" if ph_pattern else ("warn" if ve_high else "info")
    return ModuleResult(
        title="Modul 4: Gasaustausch",
        status="ph" if ph_pattern else "ok",
        severity=sev,
        feedback=" ".join(parts) if parts else "Keine Gasaustauschangaben.",
        teaching="Ein hoher VE VCO2 Slope zusammen mit niedrigem oder fallendem PETCO2 bei freier Mechanik ist typisch für ein pulmonal vaskuläres Muster.",
        followups=followups,
        flags={"cpet_pulm_vasc_pattern": ph_pattern},
    )

def analyze_module_5_mech(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []
    mech_lim = False

    ratio = None
    if d.ve_peak and d.mvv and d.mvv > 0:
        ratio = d.ve_peak / d.mvv
        if ratio >= CpetThresholds.VE_MVV_RATIO_HIGH:
            mech_lim = True

    br_val = d.br_pct
    if br_val is None and ratio is not None:
        br_val = (1.0 - ratio) * 100.0

    if br_val is not None and br_val < CpetThresholds.BR_LOW:
        mech_lim = True

    if d.flow_limit_visual == "ja":
        mech_lim = True

    if br_val is not None:
        parts.append(f"Atemreserve {_fmt(br_val, 0)}%.")
    if ratio is not None:
        parts.append(f"V'E/MVV {_fmt(ratio, 2)}.")
    if d.flow_limit_visual == "ja":
        parts.append("Flow Volume Loops limitiert.")

    if mech_lim:
        followups.append("Mechanische Limitation: Lufu, Flow Volume Loops und ggf. Dynamik (Hyperinflation) prüfen.")
        followups.append("Wenn gleichzeitig hoher VE VCO2 Slope: gemischte Limitation möglich.")

    return ModuleResult(
        title="Modul 5: Mechanik",
        status="mech_lim" if mech_lim else "ok",
        severity="warn" if mech_lim else "info",
        feedback=" ".join(parts) if parts else "Keine mechanische Limitation dokumentiert.",
        teaching="Atemreserve unter 15% oder VE zu MVV über 0.85 spricht für mechanische Limitation. Visuelle Flow Volume Limitierung verstärkt den Befund.",
        followups=followups,
        flags={"cpet_mechanical_limited_local": mech_lim, "cpet_ve_mvv_ratio_local": ratio},
    )

def analyze_module_6_gas(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
    desat = False

    if d.spo2_rest is not None:
        parts.append(f"Ruhe {_fmt(d.spo2_rest, 0)}%.")
    if spo2_min is not None:
        parts.append(f"Minimum {_fmt(spo2_min, 0)}%.")

    if spo2_min is not None and spo2_min < CpetThresholds.SPO2_DESAT_ABS:
        desat = True
    if d.spo2_rest is not None and spo2_min is not None and (d.spo2_rest - spo2_min) >= CpetThresholds.SPO2_DROP_DELTA:
        desat = True

    if desat:
        parts.append("Relevante Desaturation.")
        followups.append("Wenn Desaturation: Differenzialdiagnostik (Lufu, Diffusion, Bildgebung) und O2 Bedarf klären.")
        if d.o2_supp is None:
            followups.append("O2 Gabe während Test dokumentieren, sonst ist die Interpretation unsicher.")

    if d.o2_supp is not None and d.o2_supp > 0:
        parts.append(f"unter {_fmt(d.o2_supp, 1)} L O2.")

    return ModuleResult(
        title="Modul 6: Oxygenierung",
        status="desat" if desat else "ok",
        severity="warn" if desat else "info",
        feedback=" ".join(parts) if parts else "Keine Oxygenierungsdaten dokumentiert.",
        teaching="Desaturation unter 88% oder ein Abfall um mindestens 4% gilt als pathologisch. O2 Gabe verändert die Aussage und muss dokumentiert sein.",
        followups=followups,
        flags={"cpet_desaturation_local": desat},
    )

def analyze_module_7_safety(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    htn = (d.bp_sys_peak is not None and d.bp_sys_peak >= CpetThresholds.BP_SYS_CRITICAL) or (
        d.bp_dia_peak is not None and d.bp_dia_peak >= CpetThresholds.BP_DIA_CRITICAL
    )

    hypo = False
    if d.bp_sys_rest is not None and d.bp_sys_peak is not None and d.bp_sys_peak < (d.bp_sys_rest - CpetThresholds.BP_SYS_DROP):
        hypo = True
    if d.syncope:
        hypo = True

    ischemia = d.angina or ("senk" in (d.st_changes or "")) or ("hebung" in (d.st_changes or ""))

    if htn:
        parts.append("Exzessive Hypertonie.")
    if hypo:
        parts.append("Belastungshypotonie oder Synkope.")
    if d.arrhythmia:
        parts.append("Arrhythmie dokumentiert.")
        if d.arrhythmia_text:
            parts.append(f"Details: {d.arrhythmia_text}.")
    if ischemia:
        parts.append("Ischämiezeichen.")

    red_flag = bool(hypo or d.arrhythmia or ischemia)

    if red_flag:
        followups.append("Safety Event: klinische Abklärung und Dokumentation im Befund priorisieren.")
        followups.append("EKG Befund, Rhythmus und ggf. Troponin Verlauf berücksichtigen.")
    elif htn:
        followups.append("Hypertonie unter Belastung einordnen, Blutdruckmanagement prüfen.")

    return ModuleResult(
        title="Modul 7: Sicherheit",
        status="bad" if red_flag else "ok",
        severity="bad" if red_flag else ("warn" if htn else "info"),
        feedback=" ".join(parts) if parts else "Keine Akut Events dokumentiert.",
        teaching="Hypotonie, Ischämiezeichen oder relevante Arrhythmien sind Abbruchkriterien. Diese Befunde sind unabhängig von VO2 prognostisch und therapieentscheidend.",
        followups=followups,
        flags={"cpet_safety_red_flag": red_flag, "cpet_severe_htn_local": htn},
    )

def analyze_module_9(d: CpetData) -> ModuleResult:
    parts: List[str] = []
    followups: List[str] = []

    if not d.panel_available:
        parts.append("Nicht dokumentiert.")
        followups.append("Wenn 9 Felder Grafik vorliegt: Checkbox aktivieren und die Muster strukturiert setzen.")
    else:
        if d.eov:
            parts.append("EOV vorhanden.")
            followups.append("EOV ist prognostisch ungünstig. Abgleich mit klinischem Verlauf und Risiko Scores.")

        if d.vt1_id:
            if d.vt1_id == "ja":
                parts.append(f"VT1 erkannt ({d.vt1_method}).")
            else:
                parts.append(f"VT1 {d.vt1_id}.")
                if d.vt1_id == "unklar":
                    followups.append("VT1 mit V Slope und VE VO2 Verlauf gegentesten, sonst unklar belassen.")

        if d.rcp_id:
            if d.rcp_id == "ja":
                parts.append("RCP erkannt.")
            else:
                parts.append(f"RCP {d.rcp_id}.")

        if d.vo2wr_pattern in ("plateau", "flach"):
            parts.append("VO2 zu Leistung flach oder Plateau.")
            followups.append("VO2 zu Leistung flach: zirkulatorische Limitation oder Afterload Mismatch erwägen.")

        if d.flow_limit_visual:
            if d.flow_limit_visual == "ja":
                parts.append("Flow Volume Loops limitiert.")
            elif d.flow_limit_visual == "unklar":
                parts.append("Flow Volume Loops unklar.")

        if d.veeq_pattern:
            parts.append(f"Ventilatorische Äquivalente: {d.veeq_pattern}.")

        if d.panel_comment:
            parts.append(f"Kommentar: {d.panel_comment}.")

    return ModuleResult(
        title="Modul 9: 9 Felder Grafik",
        status="eov" if d.eov else "ok",
        severity="warn" if d.eov else "info",
        feedback=" ".join(parts) if parts else "Keine Angaben.",
        teaching="Die 9 Felder Grafik dient als visuelle Plausibilisierung. Schwellen (VT1, RCP) sind Ankerpunkte. EOV ist ein ungünstiger Prognosemarker.",
        followups=followups,
        flags={
            "cpet_eov_present": d.eov,
            "cpet_panel_available": bool(d.panel_available),
            "cpet_panel_vt1": d.vt1_id,
            "cpet_panel_vt1_method": d.vt1_method,
            "cpet_panel_rcp": d.rcp_id,
            "cpet_panel_eov": bool(d.eov),
            "cpet_panel_flow_limit": d.flow_limit_visual,
            "cpet_panel_vo2wr_pattern": d.vo2wr_pattern,
            "cpet_panel_veeq_pattern": d.veeq_pattern,
            "cpet_panel_comment": d.panel_comment,
        },
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
    
    # Deutscher Befundungsablauf, maschinenstabil und ohne Annahmen.
    report_lines: List[str] = ["Spiroergometrie CPET:"]

    # Qualität
    q = []
    if d.stop_reason:
        q.append(f"Testende {d.stop_reason}.")
    if d.rer is not None:
        q.append(f"RER {_fmt(d.rer, 2)}.")
    if d.borg_rpe is not None:
        q.append(f"Borg {_fmt(d.borg_rpe, 0)}.")
    if m0.status and m0.status != "unklar":
        q.append(f"Ausbelastung {m0.status}.")
    if q:
        report_lines.append("Qualität: " + " ".join(q))

    # Kapazität
    k = []
    if d.vo2_peak_rel is not None:
        k.append(f"V'O2peak {_fmt(d.vo2_peak_rel, 1)} mL/min/kg.")
    if d.vo2_pct is not None:
        k.append(f"{_fmt(d.vo2_pct, 0)}% Soll.")
    if m2.status and m2.status != "missing":
        k.append(f"Risiko {m2.status.upper()}.")
    if k:
        report_lines.append("Kapazität: " + " ".join(k))

    # Ventilation
    v = []
    if d.ve_vco2_slope is not None:
        v.append(f"V'E V'CO2 Slope {_fmt(d.ve_vco2_slope, 0)}.")
    pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
    if pet_start is not None:
        v.append(f"PETCO2 Start {_fmt(pet_start, 0)} mmHg.")
    if d.pet_peak is not None:
        v.append(f"Peak {_fmt(d.pet_peak, 0)} mmHg.")
    if d.br_pct is not None:
        v.append(f"Atemreserve {_fmt(d.br_pct, 0)}%.")
    if v:
        report_lines.append("Ventilation: " + " ".join(v))

    # Oxygenierung
    o = []
    if d.spo2_rest is not None:
        o.append(f"SpO2 Ruhe {_fmt(d.spo2_rest, 0)}%.")
    spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
    if spo2_min is not None:
        o.append(f"Min {_fmt(spo2_min, 0)}%.")
    if d.o2_supp is not None and d.o2_supp > 0:
        o.append(f"O2 {_fmt(d.o2_supp, 1)} L.")
    if o:
        report_lines.append("Oxygenierung: " + " ".join(o))

    # Zirkulation
    z = []
    if d.o2_pulse_peak is not None:
        z.append(f"O2 Puls {_fmt(d.o2_pulse_peak, 1)} mL.")
    if d.o2_pulse_pattern:
        z.append(f"Verlauf {d.o2_pulse_pattern}.")
    if d.bp_sys_peak is not None or d.bp_dia_peak is not None:
        z.append(f"RR Peak {_fmt(d.bp_sys_peak, 0)}/{_fmt(d.bp_dia_peak, 0)} mmHg.")
    if d.hr_peak is not None and d.hr_pct is not None:
        z.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm ({_fmt(d.hr_pct, 0)}% Soll).")
    elif d.hr_peak is not None:
        z.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm.")
    if z:
        report_lines.append("Zirkulation: " + " ".join(z))

    # Sicherheit
    if m7.severity == "bad":
        report_lines.append("Sicherheit: Safety Event.")

    # Kombinationshinweise (nur bei Datenlage)
    hints: List[str] = []
    pet_low = pet_start is not None and pet_start < CpetThresholds.PETCO2_LOW
    pet_drop = False
    if pet_start is not None and d.pet_peak is not None:
        pet_drop = d.pet_peak < (pet_start - CpetThresholds.PETCO2_DROP)

    ve_high = d.ve_vco2_slope is not None and d.ve_vco2_slope >= CpetThresholds.VE_VCO2_SLOPE_HIGH
    ratio = None
    if d.ve_peak is not None and d.mvv is not None and d.mvv > 0:
        ratio = d.ve_peak / d.mvv
    br_val = d.br_pct
    if br_val is None and ratio is not None:
        br_val = (1.0 - ratio) * 100.0
    mech_ok = br_val is None or br_val >= CpetThresholds.BR_NORMAL
    if ve_high and mech_ok and (pet_low or pet_drop):
        hints.append("Hinweis: Muster pulmonal vaskulär.")
    plateau = str(d.o2_pulse_pattern or "").lower() in ("plateau", "fallend")
    afterload = d.bp_dia_peak is not None and d.bp_dia_peak >= 100
    if plateau and afterload:
        hints.append("Hinweis: Afterload Mismatch möglich.")
    elif plateau:
        hints.append("Hinweis: SV Limitierung möglich.")

    if hints:
        report_lines.append("Hinweise: " + " ".join(hints))

    report_lines.append(f"Synthese: {m_final.feedback}")
    
    # Fail-safe: never assume a flag is present.
    lim_label = str((m_final.flags or {}).get('cpet_limitation_type_final') or 'unbestimmt')

    return SpiroLogicResult(
        module0=m0, module1=m1, module2=m2, module3=m3,
        module4=m4, module5_mech=m5, module6_gas=m6,
        module7_safety=m7, module9=m9, module_final=m_final,
        overall_summary=summary,
        headline=f"CPET: {lim_label}",
        clinical_summary=summary,
        report_text="\n".join(report_lines),
        derived={**(m_final.flags or {}), **(m4.flags or {})}
    )


def build_wizard_outputs(ui: Dict[str, Any]) -> Dict[str, Any]:
    """Build all UI outputs for the CPET Wizard.

    Requirements
    - Fail-safe: MUST NOT raise, because the surrounding clinical UI must keep running.
    - Didactic: if minimum inputs are missing, show deterministic guidance instead of empty output.
    """

    def _teaching_vo2_html() -> str:
        """Didactic, read-only CPET teaching blocks for CPET beginners.

        Strict rules:
        - No assumptions about the individual case.
        - No diagnoses.
        - No auto-filled values.
        """
        # Use HTML <details> to keep UI compact. No italics.
        return (
            "<details class='spiro-edu__details' open>"
            "<summary class='spiro-edu__summary'>Lernmodul V'O2 (Sauerstoffaufnahme)</summary>"
            "<div class='spiro-edu__teach'>"
            "<div class='spiro-edu__sub'>Kernaussage</div>"
            "<div>V'O2 ist der zentrale integrative Parameter der CPET. Er bildet das Zusammenspiel von Lunge, Kreislauf und Muskulatur ab.</div>"
            "<div class='spiro-edu__sub'>Fick Prinzip</div>"
            "<div>V'O2 = Herzzeitvolumen × C(a v)O2.</div>"
            "<ul>"
            "<li>Herzzeitvolumen steigt durch Herzfrequenzanstieg und Schlagvolumenanstieg.</li>"
            "<li>C(a v)O2 steigt durch gesteigerte periphere Sauerstoffextraktion in der arbeitenden Muskulatur.</li>"
            "</ul>"
            "<div class='spiro-edu__sub'>Kinetik und Effizienz (Fahrradergometer)</div>"
            "<div>Unter standardisierten Bedingungen steigt V'O2 mit der Leistung meist annähernd linear. Als grobe Orientierung werden etwa 10 ml pro Minute und Watt angegeben. Abweichungen können durch Effizienz, Protokoll, Trainingszustand, Körperzusammensetzung oder frühes Abbrechen entstehen.</div>"
            "<div class='spiro-edu__sub'>Normierung</div>"
            "<div>V'O2 kann absolut (L/min) oder relativ (ml/min/kg) angegeben werden. Bei Adipositas kann die kg Normierung die Einordnung verzerren. Ergänzend sind Prozent vom Sollwert oder andere Referenzen hilfreich.</div>"
            "<div class='spiro-edu__sub'>Ausbelastung, Mindesthinweise</div>"
            "<div>V'O2 Werte sind nur als maximal zu interpretieren, wenn Hinweise auf ausreichende Ausbelastung vorliegen, z. B. RER, subjektive Erschöpfung, Herzfrequenzverhalten und Verlauf der Laststeigerung. Diese Hinweise ersetzen keine klinische Beurteilung.</div>"
            "</div>"
            "</details>"

            "<details class='spiro-edu__details'>"
            "<summary class='spiro-edu__summary'>Lernmodul O2 Puls (V'O2 / Herzfrequenz)</summary>"
            "<div class='spiro-edu__teach'>"
            "<div class='spiro-edu__sub'>Definition</div>"
            "<div>O2 Puls = V'O2 / Herzfrequenz zu einem Zeitpunkt der Untersuchung. Er entspricht der aufgenommenen Sauerstoffmenge pro Herzschlag.</div>"
            "<div class='spiro-edu__sub'>Physiologischer Bezug</div>"
            "<div>O2 Puls ist näherungsweise das Produkt aus Schlagvolumen und C(a v)O2. Er korreliert häufig mit dem Schlagvolumen, ist jedoch ohne direkte Messung der arteriovenösen Differenz nicht exakt quantifizierbar.</div>"
            "<div class='spiro-edu__sub'>Typische Muster</div>"
            "<ul>"
            "<li>Bei Gesunden sollte der O2 Puls unter Belastung kontinuierlich ansteigen.</li>"
            "<li>Eine frühe Plateau Bildung oder ein Abfall kann auf eine fehlende Schlagvolumenreserve oder eine begrenzte periphere Extraktion hinweisen. Die Einordnung erfordert immer Kontext und Plausibilitätsprüfung.</li>"
            "</ul>"
            "<div class='spiro-edu__sub'>Einflussgrößen</div>"
            "<div>Anämie oder arterielle Hypoxämie können den O2 Puls deutlich vermindern, da die Sauerstofftransportkapazität reduziert ist.</div>"
            "</div>"
            "</details>"

            "<details class='spiro-edu__details'>"
            "<summary class='spiro-edu__summary'>Lernmodul V'O2max und V'O2peak</summary>"
            "<div class='spiro-edu__teach'>"
            "<div class='spiro-edu__sub'>Begriffe</div>"
            "<ul>"
            "<li>V'O2max: höchstmögliche O2 Aufnahme, die trotz weiterer Laststeigerung und maximaler Anstrengung nicht weiter steigt (Plateau).</li>"
            "<li>V'O2peak: höchster gemessener Wert in der Untersuchung, klinischer Standard.</li>"
            "</ul>"
            "<div class='spiro-edu__sub'>Praktischer Hinweis</div>"
            "<div>Eine einzelne CPET bestimmt in der Regel V'O2peak. Ob dieser Wert die tatsächliche maximale Leistungsfähigkeit widerspiegelt, hängt von der erreichten Ausbelastung ab. Der Hauptgrund für den Belastungsabbruch sollte immer dokumentiert werden.</div>"
            "</div>"
            "</details>"

            "<details class='spiro-edu__details'>"
            "<summary class='spiro-edu__summary'>Lernmodul V'CO2 (Kohlendioxidabgabe)</summary>"
            "<div class='spiro-edu__teach'>"
            "<div class='spiro-edu__sub'>Grundprinzip</div>"
            "<div>V'CO2 spiegelt die CO2 Abgabe über die Lunge wider. CO2 entsteht als Endprodukt des Stoffwechsels und dient unter Belastung auch der Elimination von Säureäquivalenten, um den pH Wert zu stabilisieren.</div>"
            "<div class='spiro-edu__sub'>Warum V'CO2 komplexer ist als V'O2</div>"
            "<div>Zwischen zellulärer CO2 Produktion und Abatmung liegen Puffersysteme (v. a. Bicarbonat). Deshalb ist V'CO2 meist stärker atemvariabel als V'O2.</div>"
            "<div class='spiro-edu__sub'>Substrate und Anaerobie</div>"
            "<div>Der respiratorische Quotient hängt von den verwendeten Substraten ab. Bei anaeroben Anteilen entsteht zusätzlich CO2 durch Bicarbonatpufferung von Säure, was für die Schwellenbestimmung genutzt wird.</div>"
            "</div>"
            "</details>"

            "<details class='spiro-edu__details'>"
            "<summary class='spiro-edu__summary'>Lernmodul AT, VAT und VCP</summary>"
            "<div class='spiro-edu__teach'>"
            "<div class='spiro-edu__sub'>AT und VAT</div>"
            "<div>Die anaerobe Schwelle (AT) beschreibt den Übergang zu relevantem anaerobem Stoffwechsel, wenn das Sauerstoffangebot den Bedarf der Muskulatur nicht mehr vollständig deckt. Die ventilatorische anaerobe Schwelle (VAT) ist die indirekte Bestimmung über den Atemgasverlauf und bildet häufig einen Bereich des aerob anaeroben Übergangs ab.</div>"
            "<div class='spiro-edu__sub'>V Slope Methode</div>"
            "<div>Im aeroben Bereich besteht zwischen V'O2 und V'CO2 ein annähernd linearer Zusammenhang. Mit zunehmender Säurepufferung steigt V'CO2 überproportional. Der Knickpunkt in der V'CO2 zu V'O2 Beziehung wird zur VAT Bestimmung genutzt.</div>"
            "<div class='spiro-edu__sub'>VCP</div>"
            "<div>Oberhalb eines weiteren Punktes (VCP) steigt die Ventilation im Verhältnis zu V'CO2 überproportional an, da der Atemantrieb zusätzlich durch die Säurelast stimuliert wird. Graphisch lässt sich dies z. B. in der Beziehung Ventilation zu V'CO2 darstellen.</div>"
            "<div class='spiro-edu__sub'>Klinischer Nutzen</div>"
            "<div>Die AT ist im Vergleich zur maximalen Leistung weniger motivationsabhängig und eignet sich zur Beurteilung der Dauerleistungsfähigkeit. Sehr niedrige AT Werte im Verhältnis zu Referenzen können auf eine frühe Limitierung des Sauerstofftransportes hinweisen und sollten im Gesamtkontext eingeordnet werden.</div>"
            "</div>"
            "</details>"
        )



    def _empty(msg: str) -> Dict[str, Any]:
        teaching_html = _teaching_vo2_html()
        msg_html = f"<div class='docx-muted'>{html.escape(msg)}</div>"
        return {
            "mod0_html": msg_html,
            "mod1_html": "",
            "mod2_html": "",
            "mod3_html": "",
            "mod4_html": "",
            "mod5_html": "",
            "mod6_html": "",
            "mod7_html": "",
            "mod9_html": "",
            "modfinal_html": "",
            "live_html": msg_html,
            "overall_html": msg_html,
            "teaching_html": teaching_html,
            "headline": "CPET",
            "clinical_summary": "",
            "report_text": "",
            "derived": {},
            "need_chrono_followups": False,
            "suspect_ph": False,
            "eov_present": False,
        }

    try:
        res = analyze(ui)
        if not res:
            # Minimum input guidance: keep it deterministic and non-committal.
            return _empty(
                "CPET Wizard: Bitte mindestens RER, HF Peak, V'O2peak, V'E V'CO2 Slope und PETCO2 (Ruhe/V'T1 oder Peak) eingeben. "
                "Fehlende Werte werden ausgeschlossen und nicht als 0 interpretiert."
            )
    except Exception as e:
        # Do not crash clinical UI. Log to console for admins.
        import traceback
        print("SPIRO_LOGIC_ERROR: analyze() failed:", repr(e))
        traceback.print_exc()
        return _empty("CPET Wizard Fehler: Analyse konnte nicht ausgeführt werden (Details in Konsole).")

    # Re-parse for deterministic, value based rendering blocks.
    # This keeps reporting independent from any preformatted module strings.
    try:
        d = CpetData.parse(ui)
    except Exception as e:
        import traceback
        print("SPIRO_LOGIC_ERROR: parse() failed:", repr(e))
        traceback.print_exc()
        return _empty("CPET Wizard Fehler: Eingaben konnten nicht geparst werden (Details in Konsole).")

    def _sev_icon(sev: str) -> str:
        if sev == "bad":
            return "🔴"
        if sev == "warn":
            return "🟠"
        return "🟢"

    def _esc(x: str) -> str:
        return html.escape(str(x or ""))

    def _render_followups(items: List[str]) -> str:
        items = [str(i).strip() for i in (items or []) if str(i).strip()]
        if not items:
            return ""
        lis = "".join(f"<li>{_esc(i)}</li>" for i in items[:6])
        return (
            "<div class='spiro-edu__sub'>Nächste Schritte</div>"
            "<div class='spiro-edu__follow'><ul>" + lis + "</ul></div>"
        )

    def _render_befundungsabfolge(d: CpetData, res: SpiroLogicResult) -> str:
        # Deutscher Befundungsablauf: kurz, strukturiert, ohne Annahmen.
        rows: List[str] = []

        def _add(title: str, parts: List[str]) -> None:
            parts = [str(p).strip() for p in (parts or []) if str(p).strip()]
            if not parts:
                return
            rows.append(
                "<li>" +
                f"<span class='cpet9-k'>{_esc(title)}</span> " +
                "<span class='cpet9-v'>" + _esc(" ".join(parts)) + "</span>" +
                "</li>"
            )

        # 1 Qualität
        q = []
        if d.stop_reason:
            q.append(f"Testende {d.stop_reason}.")
        if d.rer is not None:
            q.append(f"RER {_fmt(d.rer, 2)}.")
        if d.borg_rpe is not None:
            q.append(f"Borg {_fmt(d.borg_rpe, 0)}.")
        if res.module0.status and res.module0.status != "unklar":
            q.append(f"Ausbelastung {res.module0.status}.")
        _add("Qualität", q)

        # 2 Kapazität
        k = []
        if d.vo2_peak_rel is not None:
            k.append(f"V'O2peak {_fmt(d.vo2_peak_rel, 1)} mL/min/kg.")
        if d.vo2_pct is not None:
            k.append(f"{_fmt(d.vo2_pct, 0)}% Soll.")
        if res.module2.status and res.module2.status != "missing":
            k.append(f"Risiko {res.module2.status.upper()}.")
        _add("Kapazität", k)

        # 3 Ventilation Mechanik
        m = []
        if d.br_pct is not None:
            m.append(f"Atemreserve {_fmt(d.br_pct, 0)}%.")
        if d.ve_peak is not None and d.mvv is not None and d.mvv > 0:
            m.append(f"V'E MVV {_fmt(d.ve_peak / d.mvv, 2)}.")
        if d.flow_limit_visual:
            m.append(f"Flow Loops {d.flow_limit_visual}.")
        if m:
            _add("Ventilation Mechanik", m)

        # 4 Ventilation Effizienz und PETCO2
        g = []
        if d.ve_vco2_slope is not None:
            g.append(f"V'E V'CO2 Slope {_fmt(d.ve_vco2_slope, 0)}.")
        if d.pet_vt1 is not None or d.pet_rest is not None:
            pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
            if pet_start is not None:
                g.append(f"PETCO2 Start {_fmt(pet_start, 0)} mmHg.")
        if d.pet_peak is not None:
            g.append(f"Peak {_fmt(d.pet_peak, 0)} mmHg.")
        _add("Ventilation Effizienz", g)

        # 5 Oxygenierung
        o = []
        if d.spo2_rest is not None:
            o.append(f"SpO2 Ruhe {_fmt(d.spo2_rest, 0)}%.")
        spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
        if spo2_min is not None:
            o.append(f"Min {_fmt(spo2_min, 0)}%.")
        if d.o2_supp is not None and d.o2_supp > 0:
            o.append(f"O2 {_fmt(d.o2_supp, 1)} L.")
        _add("Oxygenierung", o)

        # 6 Zirkulation
        z = []
        if d.o2_pulse_peak is not None:
            z.append(f"O2 Puls {_fmt(d.o2_pulse_peak, 1)} mL.")
        if d.o2_pulse_pattern:
            z.append(f"Verlauf {d.o2_pulse_pattern}.")
        if d.bp_sys_peak is not None or d.bp_dia_peak is not None:
            z.append(f"RR Peak {_fmt(d.bp_sys_peak, 0)}/{_fmt(d.bp_dia_peak, 0)} mmHg.")
        if d.hr_peak is not None:
            if d.hr_pct is not None:
                z.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm ({_fmt(d.hr_pct, 0)}% Soll).")
            else:
                z.append(f"HF Peak {_fmt(d.hr_peak, 0)} bpm.")
        _add("Zirkulation", z)

        # 7 Sicherheit
        s = []
        # Result field name is module7_safety (historically some renderers used module7).
        _m7 = getattr(res, "module7_safety", None)
        if _m7 is not None and getattr(_m7, "severity", None) == "bad":
            s.append("Safety Event.")
        if d.angina:
            s.append("Angina.")
        if d.syncope:
            s.append("Synkope.")
        if d.arrhythmia:
            s.append("Arrhythmie.")
        if d.st_changes:
            s.append(f"ST {d.st_changes}.")
        _add("Sicherheit", s)

        # 8 Synthese
        _add("Synthese", [res.module_final.feedback])

        if not rows:
            return ""

        return (
            "<div class='spiro-edu__sub'>Befundungsabfolge</div>"
            "<div class='spiro-edu__follow'><ol>" + "".join(rows) + "</ol></div>"
        )

    def _render_interaktionshinweise(d: CpetData) -> str:
        # Deterministische Hinweise aus Kombinationen von Eingaben.
        hints: List[str] = []

        # Pulmonal vaskulär Muster
        pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
        pet_low = pet_start is not None and pet_start < CpetThresholds.PETCO2_LOW
        pet_drop = False
        if pet_start is not None and d.pet_peak is not None:
            pet_drop = d.pet_peak < (pet_start - CpetThresholds.PETCO2_DROP)

        ve_high = d.ve_vco2_slope is not None and d.ve_vco2_slope >= CpetThresholds.VE_VCO2_SLOPE_HIGH
        # Mechanik frei
        ratio = None
        if d.ve_peak is not None and d.mvv is not None and d.mvv > 0:
            ratio = d.ve_peak / d.mvv
        br_val = d.br_pct
        if br_val is None and ratio is not None:
            br_val = (1.0 - ratio) * 100.0
        mech_ok = br_val is None or br_val >= CpetThresholds.BR_NORMAL

        if ve_high and mech_ok and (pet_low or pet_drop):
            parts = []
            parts.append(f"V'E V'CO2 Slope {_fmt(d.ve_vco2_slope, 0)}")
            if pet_start is not None:
                parts.append(f"PETCO2 Start {_fmt(pet_start, 0)}")
            if d.pet_peak is not None:
                parts.append(f"Peak {_fmt(d.pet_peak, 0)}")
            if br_val is not None:
                parts.append(f"Atemreserve {_fmt(br_val, 0)}%")
            hints.append(" ".join(parts) + " Hinweis für pulmonal vaskuläres Muster.")

        # Mechanische Limitation
        if br_val is not None and br_val < CpetThresholds.BR_LOW:
            hints.append(f"Atemreserve {_fmt(br_val, 0)}% Hinweis für mechanische Limitation.")
        elif ratio is not None and ratio >= CpetThresholds.VE_MVV_RATIO_HIGH:
            hints.append(f"V'E MVV {_fmt(ratio, 2)} Hinweis für mechanische Limitation.")
        if str(d.flow_limit_visual or "").lower() == "ja":
            hints.append("Flow Volume Loops limitiert Hinweis für mechanische Limitation.")

        # Zirkulation Afterload und SV
        plateau = str(d.o2_pulse_pattern or "").lower() in ("plateau", "fallend")
        afterload = d.bp_dia_peak is not None and d.bp_dia_peak >= 100
        if plateau and afterload:
            hints.append("O2 Puls Plateau plus hoher diast RR Hinweis für Afterload Mismatch.")
        elif plateau:
            hints.append("O2 Puls Plateau Hinweis für SV Limitierung.")

        # Chronotropie
        if d.rer is not None and d.rer >= CpetThresholds.RER_MAX and d.hr_pct is not None and d.hr_pct < CpetThresholds.HR_PRED_LOW:
            hints.append(f"RER {_fmt(d.rer, 2)} bei HF {_fmt(d.hr_pct, 0)}% Soll Hinweis für chronotrope Inkompetenz.")

        # Oxygenierung
        spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
        if spo2_min is not None:
            if spo2_min < CpetThresholds.SPO2_DESAT_ABS:
                hints.append(f"SpO2 Minimum {_fmt(spo2_min, 0)}% Hinweis für Desaturation.")
            elif d.spo2_rest is not None and (d.spo2_rest - spo2_min) >= CpetThresholds.SPO2_DROP_DELTA:
                hints.append(f"SpO2 Abfall {_fmt(d.spo2_rest - spo2_min, 0)}% Hinweis für Desaturation.")

        if not hints:
            return ""

        lis = "".join(f"<li>{_esc(h)}</li>" for h in hints[:10])
        return (
            "<div class='spiro-edu__sub'>Hinweise aus Eingaben</div>"
            "<div class='spiro-edu__follow'><ul>" + lis + "</ul></div>"
        )

    def _render_9panel_grid(m: ModuleResult, d: CpetData) -> str:
        f = m.flags or {}
        if not bool(f.get("cpet_panel_available")):
            return "<div class='docx-muted'>9 Felder Grafik nicht dokumentiert.</div>"

        vt1 = str(f.get("cpet_panel_vt1") or "").strip().lower()
        vt1m = str(f.get("cpet_panel_vt1_method") or "").strip()
        rcp = str(f.get("cpet_panel_rcp") or "").strip().lower()
        eov = bool(f.get("cpet_panel_eov"))
        flow = str(f.get("cpet_panel_flow_limit") or "").strip().lower()
        vo2wr = str(f.get("cpet_panel_vo2wr_pattern") or "").strip().lower()
        veeq = str(f.get("cpet_panel_veeq_pattern") or "").strip().lower()
        comment = str(f.get("cpet_panel_comment") or "").strip()

        def _n(x: Optional[float], nd: int = 0) -> str:
            if x is None:
                return "nicht erhoben"
            try:
                return f"{x:.{nd}f}"
            except Exception:
                return "nicht erhoben"

        # Derived convenience values used in classic nine panel reading.
        pet_start = d.pet_rest if d.pet_rest is not None else d.pet_vt1
        pet_low = pet_start is not None and pet_start < CpetThresholds.PETCO2_LOW
        pet_drop = False
        if pet_start is not None and d.pet_peak is not None:
            pet_drop = d.pet_peak < (pet_start - CpetThresholds.PETCO2_DROP)

        ve_slope = d.ve_vco2_slope
        ve_high = ve_slope is not None and ve_slope >= CpetThresholds.VE_VCO2_SLOPE_HIGH
        ve_elev = ve_slope is not None and ve_slope >= CpetThresholds.VE_VCO2_SLOPE_ELEVATED

        ratio = None
        if d.ve_peak is not None and d.mvv is not None and d.mvv > 0:
            ratio = d.ve_peak / d.mvv
        br_val = d.br_pct
        if br_val is None and ratio is not None:
            br_val = (1.0 - ratio) * 100.0
        mech_lim = False
        if ratio is not None and ratio >= CpetThresholds.VE_MVV_RATIO_HIGH:
            mech_lim = True
        if br_val is not None and br_val < CpetThresholds.BR_LOW:
            mech_lim = True
        if flow == "ja":
            mech_lim = True

        spo2_min = d.spo2_nadir if d.spo2_nadir is not None else d.spo2_peak
        desat = False
        if spo2_min is not None and spo2_min < CpetThresholds.SPO2_DESAT_ABS:
            desat = True
        if d.spo2_rest is not None and spo2_min is not None and (d.spo2_rest - spo2_min) >= CpetThresholds.SPO2_DROP_DELTA:
            desat = True

        plateau = str(d.o2_pulse_pattern or "").lower() in ("plateau", "fallend")
        afterload = bool(d.bp_dia_peak is not None and d.bp_dia_peak >= 100)
        circ_warn = bool(plateau or afterload)

        def _cell(title: str, value: str, sev: str = "info") -> str:
            cls = "cpet9-cell"
            if sev == "warn":
                cls += " cpet9-cell--warn"
            elif sev == "bad":
                cls += " cpet9-cell--bad"
            elif sev == "good":
                cls += " cpet9-cell--good"
            return (
                f"<div class='{cls}'>"
                f"<div class='cpet9-k'>{_esc(title)}</div>"
                f"<div class='cpet9-v'>{_esc(value)}</div>"
                "</div>"
            )

        # Classic 3x3 didactic mapping: show the values that drive the interpretation.
        # This is a teaching layer only. It must not overwrite manual clinical judgement.
        c = []
        c.append(_cell("V'E Verlauf", "EOV vorhanden" if eov else "kein EOV dokumentiert", "warn" if eov else "good"))

        hr_txt = ""
        if d.hr_peak is not None:
            hr_txt += f"HF Peak {_n(d.hr_peak, 0)}"
            if d.hr_pct is not None:
                hr_txt += f" ({_n(d.hr_pct, 0)}% Soll)"
        if d.o2_pulse_peak is not None:
            if hr_txt:
                hr_txt += "; "
            hr_txt += f"O2 Puls {_n(d.o2_pulse_peak, 1)}"
            if d.o2_pulse_pattern:
                hr_txt += f" ({d.o2_pulse_pattern})"
        if not hr_txt:
            hr_txt = "nicht erhoben"
        c.append(_cell("HF und O2 Puls", hr_txt, "warn" if circ_warn else "good"))

        pet_txt = ""
        if pet_start is not None:
            pet_txt += f"Start {_n(pet_start, 0)}"
        if d.pet_peak is not None:
            pet_txt += f" Peak {_n(d.pet_peak, 0)}"
        if not pet_txt:
            pet_txt = "nicht erhoben"
        pet_sev = "bad" if (pet_low and pet_drop) else ("warn" if (pet_low or pet_drop) else "good")
        c.append(_cell("PETCO2 Verlauf", pet_txt, pet_sev))

        sev_vo2wr = "warn" if vo2wr in ("flach", "plateau") else ("info" if vo2wr == "unklar" else "good")
        vo2wr_txt = "unklar" if not vo2wr else vo2wr
        if d.vo2_wr_slope is not None:
            vo2wr_txt = f"{vo2wr_txt}; Slope {_n(d.vo2_wr_slope, 1)}"
        c.append(_cell("VO2 zu Leistung", vo2wr_txt, sev_vo2wr))

        ve_txt = "nicht erhoben"
        if ve_slope is not None:
            ve_txt = f"Slope {_n(ve_slope, 0)}"
        ve_sev = "bad" if ve_high else ("warn" if ve_elev else "good")
        c.append(_cell("V'E zu V'CO2", ve_txt, ve_sev))

        sev_veeq = "warn" if veeq in ("frueh", "kein") else ("info" if veeq == "unklar" else "good")
        veeq_txt = "unklar" if not veeq else veeq
        c.append(_cell("Ventilatorische Äquivalente", veeq_txt, sev_veeq))

        spo2_txt = ""
        if d.spo2_rest is not None:
            spo2_txt += f"Ruhe {_n(d.spo2_rest,0)}%"
        if spo2_min is not None:
            if spo2_txt:
                spo2_txt += "; "
            spo2_txt += f"Min {_n(spo2_min,0)}%"
        if d.o2_supp is not None and d.o2_supp > 0:
            spo2_txt += f"; O2 {_n(d.o2_supp,1)} L"
        if not spo2_txt:
            spo2_txt = "nicht erhoben"
        c.append(_cell("SpO2 und O2", spo2_txt, "warn" if desat else "good"))

        flow_txt = "unklar" if not flow else flow
        mech_txt = ""
        if br_val is not None:
            mech_txt += f"Atemreserve {_n(br_val,0)}%"
        if ratio is not None:
            if mech_txt:
                mech_txt += "; "
            mech_txt += f"V'E MVV {_n(ratio,2)}"
        if flow in ("ja", "unklar"):
            if mech_txt:
                mech_txt += "; "
            mech_txt += f"Flow Loops {flow_txt}"
        if not mech_txt:
            mech_txt = "nicht erhoben"
        c.append(_cell("Mechanik", mech_txt, "warn" if mech_lim else "good"))

        thr = []
        if vt1 == "ja":
            thr.append("VT1 erkannt")
            if vt1m:
                thr.append(f"Methode {vt1m}")
        elif vt1 in ("nein", "unklar"):
            thr.append(f"VT1 {vt1 if vt1 else 'unklar'}")
        if rcp == "ja":
            thr.append("RCP erkannt")
        elif rcp in ("nein", "unklar"):
            thr.append(f"RCP {rcp if rcp else 'unklar'}")
        thr_txt = ", ".join(thr) if thr else "keine Schwellenangabe"
        c.append(_cell("Schwellen", thr_txt, "info"))

        grid = "<div class='cpet9-grid'>" + "".join(c) + "</div>"
        if comment:
            grid += "<div class='spiro-edu__sub'>Kommentar</div><div class='spiro-edu__feedback'>" + _esc(comment) + "</div>"
        return grid

    def _html(m: ModuleResult) -> str:
        icon = _sev_icon(m.severity)
        extra = ""
        if m.title.lower().startswith("modul 9"):
            extra = _render_9panel_grid(m, d)

        fb = _esc(m.feedback)
        teach = _esc(m.teaching)

        out = (
            "<div class='spiro-edu'>"
            f"<div class='spiro-edu__title'>{icon} {_esc(m.title)}</div>"
            f"<div class='spiro-edu__feedback'>{fb}</div>"
        )
        if extra:
            out += "<div class='spiro-edu__sub'>9 Felder Übersicht</div>" + extra
        if teach:
            out += "<div class='spiro-edu__sub'>Didaktik</div>" + f"<div class='spiro-edu__teach'>{teach}</div>"
        out += _render_followups(m.followups)
        out += "</div>"
        return out

    try:
        # Prominent plausibility block (users should see this immediately).
        physics_alerts = _validate_physics(d)
        physics_html = ""
        if physics_alerts:
            lis = "".join(f"<li>{_esc(a)}</li>" for a in physics_alerts[:10])
            physics_html = (
                "<div class='spiro-edu__sub'>Plausibilitätschecks</div>"
                "<div class='spiro-edu__follow'><ul>" + lis + "</ul></div>"
            )

        def _render_overall_structured() -> str:
            # Arzt zu Arzt, kurz, strukturiert. Keine Didaktik hier.
            lines_q = []
            sr = ui.get("cpet_stop_reason")
            sr_txt = _esc(str(sr)) if _is_filled(sr) else "nicht angegeben"
            rer = _try_num(ui.get("cpet_rer_peak"))
            if rer is not None:
                lines_q.append(f"Testende: {sr_txt}. RER {_n(rer,2)}")
            else:
                lines_q.append(f"Testende: {sr_txt}. RER nicht angegeben")

            vo2 = _try_num(ui.get("cpet_peak_vo2_ml_kg_min"))
            vo2pct = _try_num(ui.get("cpet_peak_vo2_pct_pred"))
            v_reached = str(ui.get("cpet_vo2_peak_reached") or "unklar").strip().lower()
            cap = []
            if vo2 is not None:
                cap.append(f"V'O2peak {_n(vo2,1)} mL/min/kg")
            if vo2pct is not None:
                cap.append(f"{_n(vo2pct,0)}% Soll")
            if cap:
                lines_cap = [". ".join(cap) + "."]
            else:
                lines_cap = ["V'O2peak nicht angegeben."]
            lines_cap.append(f"Peak V'O2 erreicht: {v_reached if v_reached else 'unklar' }.")

            vevco2 = _try_num(ui.get("cpet_ve_vco2_slope"))
            pet = _try_num(ui.get("cpet_petco2_vt1_mmhg"))
            vent = []
            if vevco2 is not None:
                vent.append(f"V'E V'CO2 Slope {_n(vevco2,0)}")
            if pet is not None:
                vent.append(f"PETCO2 VT1 {_n(pet,0)} mmHg")
            lines_vent = [(". ".join(vent) + ".") if vent else "Ventilationsparameter nicht vollständig angegeben."]

            spo2 = _try_num(ui.get("cpet_spo2_nadir_pct"))
            lines_ox = [f"SpO2 Nadir {_n(spo2,0)}%." if spo2 is not None else "SpO2 Nadir nicht angegeben."]

            hr = _try_num(ui.get("cpet_hr_peak_bpm"))
            o2p_pat = ui.get("cpet_o2_pulse_pattern")
            circ = []
            if hr is not None:
                circ.append(f"HF Peak {_n(hr,0)} bpm")
            if _is_filled(o2p_pat):
                circ.append(f"O2 Puls Muster { _esc(str(o2p_pat)) }")
            lines_circ = [(". ".join(circ) + ".") if circ else "Zirkulationsparameter nicht vollständig angegeben."]

            # Kurze, kriteriumsbasierte Einordnung ohne Diagnose.
            synth = []
            if (vo2pct is not None) and (v_reached != "ja"):
                synth.append("Interpretation eingeschränkt, da Peak V'O2 nicht sicher erreicht.")
            if vo2pct is not None:
                if vo2pct >= 85:
                    synth.append("Kapazität normwertig nach %Soll.")
                elif 65 <= vo2pct <= 84:
                    synth.append("Kapazität leicht vermindert nach %Soll.")
                elif 50 <= vo2pct <= 64:
                    synth.append("Kapazität mäßig vermindert nach %Soll.")
                elif vo2pct < 50:
                    synth.append("Kapazität schwer vermindert nach %Soll.")
            else:
                synth.append("%Soll fehlt, Graduierung nicht möglich.")

            # Follow-ups (nur wenn Daten fehlen).
            follow = []
            if str(ui.get("cpet_vo2_peak_reached") or "unklar").strip().lower() == "unklar" and (ui.get("cpet_done") is True):
                follow.append("Peak V'O2 erreicht bestätigen/verneinen.")
            if (vo2 is None) and (ui.get("cpet_done") is True):
                follow.append("V'O2peak ergänzen.")
            if (vo2pct is None) and (ui.get("cpet_done") is True):
                follow.append("V'O2peak %Soll ergänzen.")

            def _blk(title: str, lines: list) -> str:
                li = "".join(f"<li>{_esc(str(x))}</li>" for x in lines if _is_filled(x))
                return f"<div class='spiro-edu__sub'>{_esc(title)}</div><div class='spiro-edu__follow'><ul>{li}</ul></div>"

            out = (
                "<div class='spiro-edu spiro-edu--overall'>"
                f"<div class='spiro-edu__title'>{_esc(res.headline)}</div>"
                + _blk("Qualität", lines_q)
                + _blk("Kapazität", lines_cap)
                + _blk("Ventilation", lines_vent)
                + _blk("Oxygenierung", lines_ox)
                + _blk("Zirkulation", lines_circ)
            )
            if synth:
                out += _blk("Synthese", synth)
            if physics_html:
                out += physics_html
            if follow:
                out += _blk("Follow-ups", follow)
            out += "</div>"
            return out

        overall_html = _render_overall_structured()

        live_html = (
            "<div class='spiro-edu spiro-edu--live'>"
            f"<div class='spiro-edu__title'>{_esc(res.headline)}</div>"
            f"<div class='spiro-edu__feedback'>{_esc(res.clinical_summary)}</div>"
            + physics_html
            + "</div>"
        )
        # Step 1 Pflicht-Check: Peak VO2 erreicht? (manuelle Bestätigung)
        try:
            if (ui.get("cpet_done") is True) and (str(ui.get("cpet_vo2_peak_reached") or "unklar").strip().lower() == "unklar"):
                warn = "<div class='spiro-edu__follow'><b>Follow-up:</b> Feld „Peak V'O2 erreicht?“ prüfen und bestätigen/verneinen. Interpretation ggf. eingeschränkt.</div>"
                live_html = live_html.replace("</div>", warn + "</div>", 1)
                overall_html = overall_html.replace("</div>", warn + "</div>", 1)
        except Exception:
            pass


        # Teaching: didaktische Inhalte, inkl. Befundungsabfolge/Interaktionshinweise.
        teaching_html = _teaching_vo2_html() + _render_befundungsabfolge(d, res) + _render_interaktionshinweise(d)

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
            "live_html": live_html,
            "overall_html": overall_html,
            "teaching_html": teaching_html,
            "headline": res.headline,
            "clinical_summary": res.clinical_summary,
            "report_text": res.report_text,
            "derived": res.derived,
            "need_chrono_followups": res.module1.status == "chrono_fail",
            "suspect_ph": res.module4.status == "ph",
            "eov_present": (res.module9.flags or {}).get("cpet_eov_present", False),
        }
    except Exception as e:
        import traceback
        print("SPIRO_LOGIC_ERROR: render() failed:", repr(e))
        traceback.print_exc()
        return _empty("CPET Wizard Fehler: Ausgabe konnte nicht gerendert werden (Details in Konsole).")


def build_cpet_outputs(data: Dict[str, Any]) -> Dict[str, Any]:
    """Single CPET builder for UI output blocks.

    Returns dict with keys:
      - live_html (kompakt, klinisch)
      - overall_html (strukturierter klinischer Block)
      - teaching_html (Lernmodule, nie in live/overall doppelt)
      - optional flags/followups
    Fail-safe: Exceptions must not block the UI.
    """
    try:
        out = build_wizard_outputs(data or {})
        # Ensure required keys exist
        out.setdefault("live_html", out.get("overall_html") or "")
        out.setdefault("overall_html", out.get("overall_html") or "")
        out.setdefault("teaching_html", out.get("teaching_html") or "")
        return out
    except Exception as e:
        msg = f"<div class='docx-muted'>CPET-Ausgabe konnte nicht erstellt werden. Details in Log. ({type(e).__name__})</div>"
        return {
            "live_html": msg,
            "overall_html": msg,
            "teaching_html": "",
            "report_text": "",
            "need_chrono_followups": False,
            "suspect_ph": False,
            "eov_present": False,
        }
