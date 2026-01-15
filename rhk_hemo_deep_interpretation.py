"""Deep hemodynamic interpretation blocks (doctor report).

Purpose
- Provide a concise, clinician-grade mechanistic interpretation for the *course* of hemodynamics.
- Designed as an *add-on* paragraph in the doctor report interpretation block.

Design principles
- Deterministic selection (no randomness).
- Primary sentence focuses on the main driver (PVR/CI/mPAP/PAWP) preferentially in *comparison* (prev → current).
- Up to 2 secondary sentences (SV, PAC/PP, TPG/DPG, RAP) are added *only if clearly abnormal / notable*.
- No silent assumptions: if core values are missing, return an empty string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        s = str(x).strip()
        if not s:
            return None
        return float(s.replace(",", "."))
    except Exception:
        return None


def _pct_change(prev: float, cur: float) -> Optional[float]:
    if prev is None or cur is None:
        return None
    if prev == 0:
        return None
    return (cur - prev) / abs(prev)


def _trend(prev: Optional[float], cur: Optional[float], *, rel_thr: float, abs_thr: float) -> str:
    """Return 'down'/'up'/'stable' if both values exist, else 'na'.

    We use a combined absolute + relative threshold to avoid noisy triggers.
    """
    if prev is None or cur is None:
        return "na"
    d = cur - prev
    if abs(d) < abs_thr:
        return "stable"
    pc = _pct_change(prev, cur)
    if pc is None:
        # fall back to absolute-only
        return "up" if d > 0 else "down"
    if abs(pc) < rel_thr:
        return "stable"
    return "up" if d > 0 else "down"


def _fmt(v: Optional[float], nd: int = 1) -> Optional[str]:
    if v is None:
        return None
    try:
        if nd == 0:
            return f"{v:.0f}"
        return f"{v:.{nd}f}"
    except Exception:
        return None


@dataclass(frozen=True)
class HemoInputs:
    # Current
    mpap: Optional[float]
    pawp: Optional[float]
    pvr: Optional[float]
    ci: Optional[float]
    co: Optional[float]
    rap: Optional[float]
    hr: Optional[float]
    sv: Optional[float]
    svi: Optional[float]
    pp: Optional[float]
    pac: Optional[float]
    tpg: Optional[float]
    dpg: Optional[float]
    # Previous (subset available in UI)
    prev_mpap: Optional[float]
    prev_pawp: Optional[float]
    prev_pvr: Optional[float]
    prev_ci: Optional[float]
    prev_rap: Optional[float]
    has_prev: bool


PRIMARY_TEMPLATES: Dict[str, str] = {
    # 1–30 (primary)
    "PVR_down_mPAP_down_CI_up": "Hämodynamisch zeigt sich eine deutliche Entlastung des pulmonalen Gefäßbetts mit Reduktion des PVR bei gleichzeitig sinkendem mPAP und gesteigerter Vorwärtsleistung.",
    "PVR_down_mPAP_down_CI_stable": "Die Verbesserung ist primär durch eine Reduktion des PVR und des mPAP bedingt, bei weitgehend unveränderter Vorwärtsleistung.",
    "PVR_down_mPAP_stable_CI_up": "Trotz stabiler Druckwerte zeigt sich eine relevante Verbesserung des PVR bei gesteigerter Vorwärtsleistung, vereinbar mit günstigerer pulmonalvaskulärer Kopplung.",
    "PVR_down_mPAP_slight_down_CI_up": "Die Hämodynamik ist insgesamt gebessert, wobei die Hauptveränderung in einer deutlichen Steigerung des Herzzeitvolumens mit begleitender Abnahme des PVR liegt.",
    "PVR_down_PCWP_up": "Trotz einer Zunahme des PCWP zeigt sich eine klare Reduktion des PVR, was für eine günstige Entwicklung der pulmonalvaskulären Komponente spricht.",
    "mPAP_down_PVR_stable_CI_up": "Die Abnahme des mPAP ist überwiegend durch eine verbesserte Vorwärtsleistung bei konstantem PVR erklärbar.",
    "mPAP_down_PCWP_down_PVR_stable": "Die Druckentlastung ist vor allem durch niedrigere linksatriale Füllungsdrücke erklärbar, während der PVR unverändert bleibt.",
    "mPAP_up_PVR_up_CI_down": "Es zeigt sich eine hämodynamische Verschlechterung mit zunehmender pulmonalvaskulärer Belastung und rückläufiger Vorwärtsleistung.",
    "PVR_up_PCWP_stable": "Bei stabilen linksseitigen Füllungsdrücken zeigt sich eine Progression der pulmonalvaskulären Komponente mit Anstieg des PVR.",
    "PCWP_up_mPAP_up_PVR_stable": "Die pulmonale Druckzunahme ist überwiegend durch erhöhte linksatriale Füllungsdrücke bedingt, ohne relevante Änderung des PVR.",
    "PCWP_up_TPG_high": "Die Konstellation spricht für ein Mischbild mit postkapillärer Druckkomponente und zusätzlicher pulmonalvaskulärer Beteiligung.",
    "PCWP_high_PVR_high": "Es zeigt sich eine kombinierte hämodynamische Belastung durch erhöhte linksatriale Füllungsdrücke und eine zusätzliche pulmonalvaskuläre Widerstandserhöhung.",
    "CI_down_PVR_high_mPAP_high": "Die Hämodynamik ist geprägt durch hohe pulmonale Druck und Widerstandslast bei eingeschränkter Vorwärtsleistung, vereinbar mit relevanter rechtsventrikulärer Belastung.",
    "CI_down_PCWP_normal_PVR_high": "Bei unauffälligen linksseitigen Füllungsdrücken zeigt sich eine präkapillär dominierte Widerstandserhöhung mit eingeschränkter Vorwärtsleistung.",
    "CI_up_mPAP_high_PVR_moderate": "Die erhöhten pulmonalen Drücke stehen im Kontext einer gesteigerten Vorwärtsleistung, bei nur moderater Widerstandserhöhung.",
    "PVR_down_PCWP_down": "Die Hämodynamik zeigt eine konsistente Verbesserung mit Abnahme sowohl der pulmonalvaskulären Belastung als auch der linksseitigen Füllungsdrücke.",
    "mPAP_up_CI_down_PVR_stable": "Die Druckzunahme ist im Wesentlichen durch eine reduzierte Vorwärtsleistung erklärbar, ohne klare Veränderung des PVR.",
    "PVR_up_CI_down_mPAP_stable": "Trotz stabiler Druckwerte zeigt sich eine ungünstige Entwicklung mit Anstieg des PVR und Abnahme der Vorwärtsleistung.",
    "mPAP_down_PVR_down_CI_down": "Die Entwicklung ist insgesamt uneinheitlich, da zwar Druck und PVR rückläufig sind, jedoch die Vorwärtsleistung ebenfalls abnimmt.",
    "mPAP_up_PVR_down_CI_down": "Gegenläufige Veränderungen limitieren die Gesamtinterpretation, bei fallendem PVR jedoch rückläufiger Vorwärtsleistung und steigenden Druckwerten.",
    "stable_all": "In Summe zeigt sich eine hämodynamische Stabilisierung ohne relevante Veränderungen von PVR, mPAP, PCWP und Herzzeitvolumen.",
    "PVR_down_mPAP_high_persistent": "Der PVR ist deutlich rückläufig, jedoch persistieren erhöhte pulmonale Drücke, sodass eine Restbelastung weiterhin anzunehmen ist.",
    "PVR_high_PCWP_up": "Die Hämodynamik zeigt eine zusätzliche Belastung durch steigende linksseitige Füllungsdrücke bei weiterhin erhöhter pulmonalvaskulärer Widerstandslast.",
    "PCWP_down_PVR_up": "Bei sinkenden linksseitigen Füllungsdrücken zeigt sich eine Zunahme der pulmonalvaskulären Widerstandskomponente.",
    "CI_up_PVR_up": "Trotz gesteigerter Vorwärtsleistung zeigt sich eine Zunahme des PVR, sodass eine pulmonalvaskuläre Mitbeteiligung weiterhin naheliegt.",
    "CI_down_PVR_down": "Der Rückgang des PVR ist im Kontext einer deutlich reduzierten Vorwärtsleistung zu interpretieren, sodass die Gesamtbelastung nicht zwingend gebessert ist.",
    "PCWP_up_PVR_stable_postcap": "Die Konstellation ist vereinbar mit einer Zunahme der postkapillären Druckkomponente bei unveränderter pulmonalvaskulärer Widerstandslast.",
    "PVR_high_PCWP_normal_pre": "Bei unauffälligem PCWP spricht die Konstellation für eine präkapilläre pulmonalvaskuläre Belastung.",
    "CI_up_PVR_slight_down": "Die klinisch relevante Veränderung liegt vor allem in der verbesserten Vorwärtsleistung, während der PVR nur gering rückläufig ist.",
    "uncertain_opposing": "Aufgrund teils gegenläufiger Parameterveränderungen ist die hämodynamische Entwicklung insgesamt vorsichtig zu bewerten, eine Bestätigung im klinischen Kontext ist sinnvoll.",
}


SECONDARY_TEMPLATES: Dict[str, str] = {
    # Secondary (only if clearly notable; max 2 sentences)
    "SV_low": "Auffällig ist ein reduziertes Schlagvolumen, was die Vorwärtsleistung limitiert und die rechtsventrikuläre Belastung plausibel erklärt.",
    "SV_up": "Das Schlagvolumen ist deutlich verbessert, was für eine gesteigerte effektive Vorwärtsleistung spricht.",
    "SV_down_CO_stable": "Bei relativ stabilem Herzzeitvolumen fällt ein Rückgang des Schlagvolumens auf, was im Kontext einer kompensatorisch erhöhten Herzfrequenz interpretiert werden kann.",
    "SV_low_pressure_flow_mismatch": "Die Druckwerte erscheinen disproportional zur Vorwärtsleistung, da das Schlagvolumen deutlich reduziert ist.",
    "SVI_low": "Der Schlagvolumenindex ist vermindert, was auf eine eingeschränkte effektive Vorwärtsleistung hinweist.",
    "CI_low": "Der Herzindex ist erniedrigt im Sinne einer Low output Konstellation.",
    "PP_high": "Die pulmonale Pulsdruckamplitude ist deutlich erhöht, vereinbar mit gesteigerter pulsatile RV Nachlast.",
    "PP_down": "Die Abnahme der pulmonalen Pulsdruckamplitude spricht für eine Entlastung der pulsatilem Druckkomponente.",
    "PAC_low": "Zusätzlich zeigt sich eine deutlich reduzierte pulmonalarterielle Compliance, vereinbar mit erhöhter pulsatile RV Nachlast.",
    "PAC_very_low": "Die pulmonalarterielle Compliance ist stark reduziert, was für eine ausgeprägte pulsatile Belastung spricht.",
    "PAC_up": "Die pulmonalarterielle Compliance ist deutlich gebessert, was als günstige Entwicklung der Gefäßelastizität gewertet werden kann.",
    "stiffness_pattern": "Die Kombination aus erhöhter Pulsdruckamplitude und reduzierter Compliance spricht für eine ausgeprägte pulmonale Gefäßsteifigkeit.",
    "PVR_down_PAC_low": "Trotz rückläufigem PVR bleibt die Compliance reduziert, sodass weiterhin eine relevante pulsatile Belastung anzunehmen ist.",
    "PVR_up_PAC_down": "Neben dem Anstieg des PVR fällt eine Abnahme der Compliance auf, was auf eine Zunahme der resistiven und pulsatilem Gefäßlast hinweist.",
    "TPG_high": "Der Transpulmonalgradient ist deutlich erhöht und unterstützt eine relevante präkapilläre Komponente im Mischbildkontext.",
    "TPG_down": "Der Transpulmonalgradient ist rückläufig, was für eine Entlastung der präkapillären Druckkomponente spricht.",
    "DPG_high": "Ein erhöhter diastolischer Druckgradient kann im Kontext für eine ausgeprägtere vaskuläre Beteiligung sprechen und sollte zusammen mit dem Gesamtbild bewertet werden.",
    "PCWP_high_DPG_ok": "Bei erhöhtem PAWP ohne auffälligen diastolischen Druckgradienten überwiegt eine linksherzdominierte Druckkomponente.",
    "RAP_high": "Erhöhte rechtsatriale Drücke sprechen für eine relevante systemische Stauungskomponente und sollten im klinischen Kontext mitbeurteilt werden.",
    "RAP_down": "Der Rückgang der rechtsatrialen Drücke spricht für eine hämodynamische Entstauung auf der venösen Seite.",
    "SV_low_RAP_high": "Die Kombination aus reduziertem Schlagvolumen und erhöhten rechtsatrialen Drücken ist vereinbar mit einer eingeschränkten rechtsventrikulären Vorwärtsleistung.",
}

def _collect_inputs(ui: Dict[str, Any], der: Dict[str, Any]) -> HemoInputs:
    mpap = _safe_float(der.get("mpap_rest"))
    pawp = _safe_float(der.get("pawp_rest"))
    pvr = _safe_float(der.get("pvr_rest"))
    ci = _safe_float(der.get("ci_rest"))
    co = _safe_float(der.get("co_rest"))
    rap = _safe_float(der.get("rap_rest"))
    hr = _safe_float(der.get("hr_rest"))
    sv = _safe_float(der.get("sv_rest_ml"))
    svi = _safe_float(der.get("svi_rest_ml_m2"))
    pp = _safe_float(der.get("pp_pa_rest"))
    pac = _safe_float(der.get("pac_rest_ml_per_mmhg"))
    tpg = _safe_float(der.get("tpg_rest"))
    dpg = _safe_float(der.get("dpg_rest"))

    prev_mpap = _safe_float(ui.get("prev_mpap"))
    prev_pawp = _safe_float(ui.get("prev_pawp"))
    prev_ci = _safe_float(ui.get("prev_ci"))
    prev_pvr = _safe_float(ui.get("prev_pvr"))
    prev_rap = _safe_float(ui.get("prev_rap"))

    has_prev = bool((ui.get("prev_rhk_date") or "").strip()) and any(v is not None for v in (prev_mpap, prev_pawp, prev_ci, prev_pvr, prev_rap))

    return HemoInputs(
        mpap=mpap, pawp=pawp, pvr=pvr, ci=ci, co=co, rap=rap, hr=hr, sv=sv, svi=svi,
        pp=pp, pac=pac, tpg=tpg, dpg=dpg,
        prev_mpap=prev_mpap, prev_pawp=prev_pawp, prev_pvr=prev_pvr, prev_ci=prev_ci, prev_rap=prev_rap,
        has_prev=has_prev,
    )


def _pick_primary(h: HemoInputs) -> Optional[str]:
    """Pick exactly one primary block if a comparison is available; else return None."""
    if not h.has_prev:
        return None
    # Core must exist
    if h.pvr is None or h.mpap is None or h.pawp is None or h.ci is None:
        return None
    if h.prev_pvr is None or h.prev_mpap is None or h.prev_pawp is None or h.prev_ci is None:
        # We still allow some comparison if at least PVR exists, but keep conservative
        return None

    pvr_tr = _trend(h.prev_pvr, h.pvr, rel_thr=0.20, abs_thr=0.5)
    mpap_tr = _trend(h.prev_mpap, h.mpap, rel_thr=0.15, abs_thr=3.0)
    pawp_tr = _trend(h.prev_pawp, h.pawp, rel_thr=0.15, abs_thr=3.0)
    ci_tr = _trend(h.prev_ci, h.ci, rel_thr=0.15, abs_thr=0.2)

    # Some helper flags
    pcwp_high = (h.pawp is not None and h.pawp > 15)
    pvr_high = (h.pvr is not None and h.pvr > 2)
    mpap_high = (h.mpap is not None and h.mpap > 20)
    tpg_high = (h.tpg is not None and h.tpg >= 12)

    # Priority rules (deterministic)
    # If everything is stable compared to the prior exam, say so first (avoid over-weighting absolute constellations).
    if pvr_tr == "stable" and mpap_tr == "stable" and pawp_tr == "stable" and ci_tr == "stable":
        return PRIMARY_TEMPLATES["stable_all"]

    if pvr_tr == "down" and mpap_tr == "down" and ci_tr == "up":
        return PRIMARY_TEMPLATES["PVR_down_mPAP_down_CI_up"]
    if pvr_tr == "down" and pawp_tr == "up":
        return PRIMARY_TEMPLATES["PVR_down_PCWP_up"]
    if pvr_tr == "down" and mpap_tr == "down" and ci_tr == "stable":
        return PRIMARY_TEMPLATES["PVR_down_mPAP_down_CI_stable"]
    if pvr_tr == "down" and mpap_tr == "stable" and ci_tr == "up":
        return PRIMARY_TEMPLATES["PVR_down_mPAP_stable_CI_up"]
    if mpap_tr == "down" and pvr_tr == "stable" and ci_tr == "up":
        return PRIMARY_TEMPLATES["mPAP_down_PVR_stable_CI_up"]
    if mpap_tr == "down" and pawp_tr == "down" and pvr_tr == "stable":
        return PRIMARY_TEMPLATES["mPAP_down_PCWP_down_PVR_stable"]
    if pvr_tr == "up" and mpap_tr == "up" and ci_tr == "down":
        return PRIMARY_TEMPLATES["mPAP_up_PVR_up_CI_down"]
    if pvr_tr == "up" and pawp_tr == "stable":
        return PRIMARY_TEMPLATES["PVR_up_PCWP_stable"]
    if pawp_tr == "up" and mpap_tr == "up" and pvr_tr == "stable":
        return PRIMARY_TEMPLATES["PCWP_up_mPAP_up_PVR_stable"]
    if pcwp_high and tpg_high:
        return PRIMARY_TEMPLATES["PCWP_up_TPG_high"]
    if pcwp_high and pvr_high:
        return PRIMARY_TEMPLATES["PCWP_high_PVR_high"]
    if ci_tr == "down" and pvr_high and mpap_high:
        return PRIMARY_TEMPLATES["CI_down_PVR_high_mPAP_high"]
    if ci_tr == "down" and (not pcwp_high) and pvr_high:
        return PRIMARY_TEMPLATES["CI_down_PCWP_normal_PVR_high"]
    if pvr_tr == "down" and pawp_tr == "down":
        return PRIMARY_TEMPLATES["PVR_down_PCWP_down"]
    if mpap_tr == "up" and ci_tr == "down" and pvr_tr == "stable":
        return PRIMARY_TEMPLATES["mPAP_up_CI_down_PVR_stable"]
    if pvr_tr == "up" and ci_tr == "down" and mpap_tr == "stable":
        return PRIMARY_TEMPLATES["PVR_up_CI_down_mPAP_stable"]
    if mpap_tr == "down" and pvr_tr == "down" and ci_tr == "down":
        return PRIMARY_TEMPLATES["mPAP_down_PVR_down_CI_down"]
    if mpap_tr == "up" and pvr_tr == "down" and ci_tr == "down":
        return PRIMARY_TEMPLATES["mPAP_up_PVR_down_CI_down"]
    if pawp_tr == "down" and pvr_tr == "up":
        return PRIMARY_TEMPLATES["PCWP_down_PVR_up"]
    if ci_tr == "up" and pvr_tr == "up":
        return PRIMARY_TEMPLATES["CI_up_PVR_up"]
    if ci_tr == "down" and pvr_tr == "down":
        return PRIMARY_TEMPLATES["CI_down_PVR_down"]
    if pawp_tr == "up" and pvr_tr == "stable":
        return PRIMARY_TEMPLATES["PCWP_up_PVR_stable_postcap"]
    if pvr_high and (not pcwp_high):
        return PRIMARY_TEMPLATES["PVR_high_PCWP_normal_pre"]
    if ci_tr == "up" and pvr_tr == "stable" and mpap_tr == "stable" and pvr_tr != "na":
        # small improvement dominated by CI
        return PRIMARY_TEMPLATES["CI_up_PVR_slight_down"]
    if pvr_tr == "down" and mpap_high:
        return PRIMARY_TEMPLATES["PVR_down_mPAP_high_persistent"]
    if pvr_high and pawp_tr == "up":
        return PRIMARY_TEMPLATES["PVR_high_PCWP_up"]
    return PRIMARY_TEMPLATES["uncertain_opposing"]


def _pick_secondary(h: HemoInputs, primary: Optional[str]) -> List[str]:
    """Pick up to 2 secondary sentences if clearly notable.

    Principles
    - Guideline-aligned cut-offs where available (ESC/ERS risk strata).
    - Prefer SVI/SV and CI first.
    - PAC/PP only if clearly abnormal.
    - TPG/DPG only if they add information (PAWP elevated or borderline).
    """
    out: List[str] = []

    # CI (ESC/ERS: <2.0 high risk)
    ci_low = (h.ci is not None and h.ci < 2.0)

    # SVI (ESC/ERS: <31 high risk)
    svi_low = (h.svi is not None and h.svi < 31)

    # SV (supportive; prefer SVI if present)
    sv_low = (h.sv is not None and h.sv < 60)
    sv_very_low = (h.sv is not None and h.sv < 45)

    # RAP (notable congestion)
    rap_high = (h.rap is not None and h.rap >= 10)
    rap_down = (h.prev_rap is not None and h.rap is not None and (_pct_change(h.prev_rap, h.rap) is not None) and (_pct_change(h.prev_rap, h.rap) <= -20))

    # PAC (use conservative "notable" thresholds)
    pac_low = (h.pac is not None and h.pac < 1.5)
    pac_very_low = (h.pac is not None and h.pac < 1.1)

    # PP (only if PAC not available or extreme)
    pp_high = (h.pp is not None and h.pp >= 35)

    # Gradients (only if PAWP elevated/borderline)
    tpg_high = (h.tpg is not None and h.tpg >= 12)
    dpg_high = (h.dpg is not None and h.dpg >= 7)
    pcwp_high = (h.pawp is not None and h.pawp > 15)
    pcwp_borderline = (h.pawp is not None and 13 <= h.pawp <= 15)
    gradients_allowed = bool(pcwp_high or pcwp_borderline)

    # 1) Flow / performance first (SVI/SV, CI)
    if svi_low:
        out.append(SECONDARY_TEMPLATES["SVI_low"])
    elif sv_very_low or (sv_low and ci_low):
        out.append(SECONDARY_TEMPLATES["SV_low"])
    elif ci_low:
        out.append(SECONDARY_TEMPLATES["CI_low"])

    # 2) Combine congestion + low flow if both present
    if len(out) < 2 and (rap_high and (svi_low or sv_low)):
        out.append(SECONDARY_TEMPLATES["SV_low_RAP_high"])

    # 3) Pulsatile afterload (PAC/PP) only if clearly abnormal
    if len(out) < 2:
        if pac_very_low:
            out.append(SECONDARY_TEMPLATES["PAC_very_low"])
        elif pac_low:
            # If primary indicates PVR down but PAC still low -> special phrasing
            pvr_down = (h.has_prev and h.prev_pvr is not None and h.pvr is not None and (_pct_change(h.prev_pvr, h.pvr) is not None) and (_pct_change(h.prev_pvr, h.pvr) <= -20))
            if pvr_down:
                out.append(SECONDARY_TEMPLATES["PVR_down_PAC_low"])
            else:
                out.append(SECONDARY_TEMPLATES["PAC_low"])
        elif h.pac is None and pp_high:
            out.append(SECONDARY_TEMPLATES["PP_high"])

    # Stiffness pattern (PP high + PAC low) if still room and both available
    if len(out) < 2 and (h.pp is not None and h.pac is not None) and (pp_high and pac_low):
        out.append(SECONDARY_TEMPLATES["stiffness_pattern"])

    # 4) TPG/DPG only if PAWP adds ambiguity (mixed/postcap)
    if len(out) < 2 and gradients_allowed:
        if tpg_high:
            out.append(SECONDARY_TEMPLATES["TPG_high"])
        elif dpg_high:
            out.append(SECONDARY_TEMPLATES["DPG_high"])
        elif pcwp_high and (h.dpg is not None and h.dpg < 7):
            out.append(SECONDARY_TEMPLATES["PCWP_high_DPG_ok"])

    # 5) RAP trend if still room
    if len(out) < 2 and rap_down:
        out.append(SECONDARY_TEMPLATES["RAP_down"])
    if len(out) < 2 and rap_high:
        out.append(SECONDARY_TEMPLATES["RAP_high"])

    return out[:2]


def build_hemo_deep_interpretation(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    """Return a short add-on paragraph (1 primary + 0–2 secondary sentences) or empty string."""
    ui = ui or {}
    der = der or {}
    h = _collect_inputs(ui, der)

    primary = _pick_primary(h)
    if not primary:
        return ""

    secondary = _pick_secondary(h, primary)

    # Build block; keep it clearly separated and short.
    lines: List[str] = ["Hämodynamische Verlaufseinordnung:", primary]
    lines.extend(secondary)
    return " ".join([x.strip() for x in lines if str(x).strip()]).strip()
