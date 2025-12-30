#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RHK Befundassistent (Web) – v25.0 (flat)

- Ultra-interaktiver Gradio-Assistenzbogen für RHK-/PH-Befunde
- Deklaratives Regelwerk (YAML) zur Guideline-nahen Klassifikation, Modulen & Empfehlungen
- Separater Patientenbericht in einfacher, erklärender Sprache (ohne Abkürzungen/Zahlen)

Hinweis: Dieses Tool ist als Assistenzsystem gedacht und ersetzt keine ärztliche Beurteilung.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict
import datetime as _dt
import json
import hashlib
import html as _html
import math
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


# =============================================================================
# App Meta
# =============================================================================

APP_NAME = "RHK Befundassistent"
APP_VERSION = "v25.1"
APP_TITLE = f"{APP_NAME} – {APP_VERSION}"
WHATS_NEW = "Neu: Befunde leeren repariert · Tabs ohne ... Menü · Procedere/Module aktualisieren den Bericht sofort · Build 30.12.2025 19:45"


# =============================================================================
# RHK Glass Header v2.0 (Responsive Island Design)
# =============================================================================
RHK_HEADER_HTML = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
    --glass-border: rgba(255, 255, 255, 0.65);
    --glass-bg: rgba(255, 255, 255, 0.65);
    --primary-glow: rgba(37, 99, 235, 0.25);
    --text-main: #0f172a;
    --text-muted: rgba(15, 23, 42, 0.65);
}}

/* Reset & Base */
#rhk_topbar_wrapper, #rhk_topbar_wrapper * {{
    box-sizing: border-box;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    line-height: 1.3;
}}

/* Der Wrapper ist der Platzhalter im Layout */
#rhk_topbar_wrapper {{
    position: sticky;
    top: 16px; /* Mehr Abstand von oben für den Schwebenden Look */
    z-index: 10000;
    width: 100%;
    padding: 0 24px; /* Schutzabstand zum Rand auf kleinen Screens */
    margin-bottom: 32px;
    
    /* Flexbox zum Zentrieren des Headers auf großen Screens */
    display: flex;
    justify-content: center;
}}

/* Das eigentliche Glass-Element */
.rhk-glass-island {{
    width: 100%;
    /* Hier ist der Trick: Max-Width verhindert, dass er auf 4k Monitoren "dünn" aussieht */
    max-width: 1600px; 
    position: relative;
    overflow: hidden;

    display: grid;
    grid-template-columns: auto 1fr auto; /* Logo - Spacer - Status */
    align-items: center;
    gap: 32px;

    /* Padding dynamisch vergrößern auf großen Screens */
    padding: clamp(24px, 2.5vh, 36px) clamp(32px, 3vw, 48px);

    background: var(--glass-bg);
    backdrop-filter: blur(24px) saturate(160%);
    -webkit-backdrop-filter: blur(24px) saturate(160%);

    border: 1px solid var(--glass-border);
    border-radius: 24px;

    /* Tieferer Schatten für mehr Volumen */
    box-shadow: 
        0 4px 6px -1px rgba(0, 0, 0, 0.05),
        0 20px 40px -8px rgba(0, 0, 0, 0.12),
        inset 0 1px 1px rgba(255, 255, 255, 0.8);
        
    transition: all 0.3s ease;
}}

/* Hintergrund-Effekte (Aurora) */
.rhk-glass-island::before {{
    content: "";
    position: absolute;
    inset: -50%;
    background: 
        radial-gradient(circle at 0% 0%, var(--primary-glow), transparent 40%),
        radial-gradient(circle at 100% 100%, rgba(139, 92, 246, 0.15), transparent 40%);
    filter: blur(40px);
    z-index: -1;
    opacity: 0.8;
}}

/* --- Linke Sektion (Logo & Text) --- */
.rhk-left-section {{
    display: flex;
    align-items: center;
    gap: 24px;
}}

.rhk-logo-box {{
    /* Logo wächst leicht mit */
    width: clamp(64px, 5vw, 80px); 
    height: clamp(64px, 5vw, 80px);
    
    background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    color: #4338ca;
    flex-shrink: 0;
}}

.rhk-text-content {{
    display: flex;
    flex-direction: column;
    justify-content: center;
}}

.rhk-main-title {{
    /* Responsive Schriftgröße: Min 24px, Ziel 2vw, Max 32px */
    font-size: clamp(24px, 1.8vw, 32px);
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-main);
    white-space: nowrap;
}}

.rhk-sub-title {{
    font-size: clamp(15px, 1vw, 18px);
    font-weight: 600;
    color: var(--text-muted);
    margin-top: 2px;
}}

.rhk-meta-tag {{
    display: inline-flex;
    margin-top: 6px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
}}

/* --- Rechte Sektion (Status Badges) --- */
.rhk-right-section {{
    display: flex;
    align-items: center;
    gap: 16px;
    justify-content: flex-end;
    flex-wrap: wrap;
}}

.rhk-status-badge {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    
    padding: 10px 20px;
    min-width: 140px;
    
    background: rgba(255,255,255,0.4);
    border: 1px solid rgba(255,255,255,0.5);
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}}

.rhk-badge-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
    color: #64748b;
    margin-bottom: 2px;
}}

.rhk-badge-value {{
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 6px;
}}

/* Status Indikator Punkt */
.status-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #10b981;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
    animation: pulse 2s infinite;
}}

@keyframes pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }}
    70% {{ box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
}}

/* Mobile Anpassung */
@media (max-width: 900px) {{
    .rhk-glass-island {{
        grid-template-columns: 1fr;
        text-align: center;
        gap: 20px;
    }}
    .rhk-left-section {{ flex-direction: column; }}
    .rhk-right-section {{ justify-content: center; }}
}}
</style>

<div id="rhk_topbar_wrapper">
    <div class="rhk-glass-island">
        
        <div class="rhk-left-section">
            <div class="rhk-logo-box">
                <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
            </div>
            
            <div class="rhk-text-content">
                <div class="rhk-main-title">RHK Befundassistent</div>
                <div class="rhk-sub-title">System Status & Übersicht</div>
                <div class="rhk-meta-tag">PH Zentrum Universitätsklinikum Gießen</div>
            </div>
        </div>

        <div></div>

        <div class="rhk-right-section">
            
            <div class="rhk-status-badge">
                <span class="rhk-badge-label">Gateway Status</span>
                <span class="rhk-badge-value">
                    <span class="status-dot"></span> Online
                </span>
            </div>

            <div class="rhk-status-badge" style="background: rgba(37, 99, 235, 0.1); border-color: rgba(37, 99, 235, 0.2);">
                <span class="rhk-badge-label" style="color: #3b82f6;">Version</span>
                <span class="rhk-badge-value" style="color: #1d4ed8;">
                    {APP_VERSION}
                </span>
            </div>

        </div>

    </div>
</div>
"""

APP_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_RULEBOOK_PATH = os.environ.get("RHK_RULEBOOK", os.path.join(APP_DIR, "rhk_rules.yaml"))

# Clinical constants (ESC/ERS 2022)
# TAPSE/sPAP risk thresholds (Table 16)
TAPSE_SPAP_LOW_RISK = 0.32
TAPSE_SPAP_HIGH_RISK = 0.19

# S'/RAAI warning threshold (internal marker; guideline-unlisted)
SPRIME_RAAI_CUTOFF = 0.81



def _require_gradio_version(min_major: int = 5) -> None:
    """Fail fast with a human friendly error if Gradio is too old."""
    try:
        import gradio as _gr
        ver = getattr(_gr, "__version__", "0.0.0")
        major = int(str(ver).split(".")[0])
    except Exception:
        major = 0
        ver = "unbekannt"
    if major < min_major:
        raise RuntimeError(
            f"Gradio Version {min_major} oder höher wird benötigt. Installiert ist: {ver}. "
            "Bitte requirements.txt installieren, zum Beispiel: pip install -r requirements.txt"
        )

# =============================================================================
# Formatting helpers

# =============================================================================

def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        try:
            v = float(x)
            if math.isnan(v):
                return None
            return v
        except Exception:
            return None
    if isinstance(x, str):
        s = x.strip().replace(",", ".")
        if not s:
            return None
        try:
            v = float(s)
            if math.isnan(v):
                return None
            return v
        except Exception:
            return None
    return None


def _escape_html(s: Any) -> str:
    """Einfache HTML-Escaping-Hilfe (für UI-HTML)."""
    try:
        return _html.escape(str(s), quote=True)
    except Exception:
        return str(s)


def _fmt(x: Any, nd: int = 1) -> str:
    v = _safe_float(x)
    if v is None:
        return "–"
    # Avoid showing "-0.0"
    if abs(v) < 10 ** (-(nd + 1)):
        v = 0.0
    return f"{v:.{nd}f}".replace(".", ",")


def _fmt_int(x: Any) -> str:
    v = _safe_float(x)
    if v is None:
        return "–"
    return str(int(round(v)))


# ---------------------------------------------------------------------------
# Backwards-compatible aliases / helpers (v23+ refactor safety)
# ---------------------------------------------------------------------------

def fmt_int(x: Any) -> str:
    """Alias for _fmt_int (used by newer code paths)."""
    return _fmt_int(x)


def fmt_float(x: Any, nd: int = 1) -> str:
    """Alias for _fmt with explicit digits."""
    return _fmt(x, nd)


def calc_mpap(spap: Any, dpap: Any) -> Optional[float]:
    """Alias for calc_mpap_from_spap_dpap accepting raw values."""
    return calc_mpap_from_spap_dpap(_safe_float(spap), _safe_float(dpap))



def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# =============================================================================
# Simple physiologic calculations
# =============================================================================

def calc_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    if not height_cm or not weight_kg:
        return None
    h_m = height_cm / 100.0
    if h_m <= 0:
        return None
    return weight_kg / (h_m * h_m)


def calc_bsa(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    # Mosteller
    if not height_cm or not weight_kg:
        return None
    if height_cm <= 0 or weight_kg <= 0:
        return None
    return math.sqrt((height_cm * weight_kg) / 3600.0)


def calc_mpap_from_spap_dpap(spap: Optional[float], dpap: Optional[float]) -> Optional[float]:
    if spap is None or dpap is None:
        return None
    return (spap + 2.0 * dpap) / 3.0


# =============================================================================
# H2FPEF – continuous model (AHA Circulation 2018) (user provided)
# =============================================================================

@dataclass
class H2FPEFResult:
    percent: Optional[float]
    category: Optional[str]
    y: Optional[float] = None
    z: Optional[float] = None
    inputs_used: Dict[str, Any] = field(default_factory=dict)


def calc_h2fpef_probability(age: Optional[float],
                           bmi: Optional[float],
                           ee: Optional[float],
                           pasp: Optional[float],
                           af: Optional[bool]) -> H2FPEFResult:
    """
    Probability of heart failure with preserved EF (H2FPEF) using the continuous model:

    Probability = (Z / (1 + Z)) * 100, where Z = e^y and
    y = -9.1917 + 0.0451*age + 0.1307*BMI + 0.0859*(E/e') + 0.0520*PASP + 1.6997*AF
    AF: 1 if Yes else 0
    BMI capped at 50 to avoid extrapolation (user provided note).
    """
    inputs_used = {
        "age": age,
        "bmi": bmi,
        "e_over_eprime": ee,
        "pasp": pasp,
        "af": bool(af) if af is not None else None,
    }

    if age is None or bmi is None or ee is None or pasp is None or af is None:
        return H2FPEFResult(percent=None, category=None, inputs_used=inputs_used)

    bmi_c = _clamp(float(bmi), 10.0, 50.0)

    y = -9.1917 + 0.0451 * float(age) + 0.1307 * bmi_c + 0.0859 * float(ee) + 0.0520 * float(pasp) + 1.6997 * (1.0 if af else 0.0)
    z = math.exp(y)
    prob = (z / (1.0 + z)) * 100.0

    if prob < 20:
        cat = "unlikely"
    elif prob < 60:
        cat = "possible"
    else:
        cat = "likely"

    return H2FPEFResult(percent=prob, category=cat, y=y, z=z, inputs_used={**inputs_used, "bmi_capped": bmi_c})


# =============================================================================
# ESC/ERS risk (simple heuristic; not a full guideline calculator)
# =============================================================================

def _risk_bucket_from_points(points: List[Optional[int]], mode: str) -> Optional[str]:
    # mode: "3" or "4"
    pts = [p for p in points if isinstance(p, int)]
    if not pts:
        return None
    m = sum(pts) / len(pts)

    if mode == "3":
        # low, intermediate, high
        if m <= 1.5:
            return "low"
        if m <= 2.5:
            return "intermediate"
        return "high"

    # 4 strata
    if m <= 1.5:
        return "low"
    if m <= 2.0:
        return "intermediate-low"
    if m <= 2.5:
        return "intermediate-high"
    return "high"


def calc_esc_ers_4_strata(who_fc: Optional[str],
                          six_mwd_m: Optional[float],
                          bnp_pg_ml: Optional[float],
                          ntprobnp_pg_ml: Optional[float]) -> Optional[str]:
    """
    ESC/ERS 2022 – vereinfachtes Vier-Strata-Risikomodell (Follow-up).
    Variablen: WHO-FC, 6MWD, BNP oder NT-proBNP.
    Risiko = Mittelwert der Punktwerte, aufgerundet auf die nächste ganze Zahl (Table 18).
    """
    grades: List[int] = []

    # WHO-FC
    if who_fc:
        w = who_fc.strip().upper()
        if w in ("I", "II", "1", "2"):
            grades.append(1)
        elif w in ("III", "3"):
            grades.append(3)
        elif w in ("IV", "4"):
            grades.append(4)

    # 6MWD (m)
    if isinstance(six_mwd_m, (int, float)) and six_mwd_m > 0:
        if six_mwd_m > 440:
            grades.append(1)
        elif six_mwd_m >= 320:
            grades.append(2)
        elif six_mwd_m >= 165:
            grades.append(3)
        else:
            grades.append(4)

    # Biomarker (NT-proBNP bevorzugt)
    if ntprobnp_pg_ml is not None:
        v = ntprobnp_pg_ml
        if v < 300:
            grades.append(1)
        elif v <= 649:
            grades.append(2)
        elif v <= 1100:
            grades.append(3)
        else:
            grades.append(4)
    elif bnp_pg_ml is not None:
        v = bnp_pg_ml
        if v < 50:
            grades.append(1)
        elif v <= 199:
            grades.append(2)
        elif v <= 800:
            grades.append(3)
        else:
            grades.append(4)

    if not grades:
        return None

    mean = sum(grades) / len(grades)
    risk_grade = int(math.ceil(mean - 1e-9))
    return {
        1: "low",
        2: "intermediate-low",
        3: "intermediate-high",
        4: "high",
    }.get(risk_grade)


def calc_esc_ers_3_strata(who_fc: Optional[str],
                          six_mwd_m: Optional[float],
                          bnp_pg_ml: Optional[float],
                          ntprobnp_pg_ml: Optional[float]) -> Optional[str]:
    """
    ESC/ERS 2022 – Drei-Strata-Risikomodell (Initialbeurteilung; Table 16, vereinfacht).
    Variablen: WHO-FC, 6MWD, BNP oder NT-proBNP.
    """
    grades: List[int] = []

    # WHO-FC
    if who_fc:
        w = who_fc.strip().upper()
        if w in ("I", "II", "1", "2"):
            grades.append(1)
        elif w in ("III", "3"):
            grades.append(2)
        elif w in ("IV", "4"):
            grades.append(3)

    # 6MWD (m)
    if isinstance(six_mwd_m, (int, float)) and six_mwd_m > 0:
        if six_mwd_m > 440:
            grades.append(1)
        elif six_mwd_m >= 165:
            grades.append(2)
        else:
            grades.append(3)

    # Biomarker (NT-proBNP bevorzugt)
    if ntprobnp_pg_ml is not None:
        v = ntprobnp_pg_ml
        if v < 300:
            grades.append(1)
        elif v <= 1100:
            grades.append(2)
        else:
            grades.append(3)
    elif bnp_pg_ml is not None:
        v = bnp_pg_ml
        if v < 50:
            grades.append(1)
        elif v <= 800:
            grades.append(2)
        else:
            grades.append(3)

    if not grades:
        return None

    mean = sum(grades) / len(grades)
    if mean <= 1.5:
        return "low"
    if mean <= 2.5:
        return "intermediate"
    return "high"


# =============================================================================
# Exercise pattern heuristics
# =============================================================================

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Additional risk scores (ESC/ERS comprehensive 3-strata; REVEAL Lite 2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EscErsComprehensiveResult:
    category: str
    mean_grade: float
    n_params: int
    grades: Dict[str, int]
    missing: List[str]


def calc_esc_ers_comprehensive_3_strata(ui: Dict[str, Any], derived: Dict[str, Any]) -> Optional[EscErsComprehensiveResult]:
    """ESC/ERS 2022 comprehensive risk assessment (Table 16) – vereinfachte Umsetzung.

    Jede verfügbare Variable wird in drei Kategorien eingestuft:
      1 = niedriges Risiko
      2 = intermediäres Risiko
      3 = hohes Risiko

    Anschließend wird der Mittelwert gebildet und in (niedrig / intermediär / hoch) gemappt.

    Hinweis: Es werden nur Parameter bewertet, die tatsächlich vorliegen.
    """
    grades: Dict[str, int] = {}
    missing: List[str] = []

    # WHO-FC
    who = (ui.get("who_fc") or "").strip()
    if who in ("I", "II"):
        grades["WHO-FC"] = 1
    elif who == "III":
        grades["WHO-FC"] = 2
    elif who == "IV":
        grades["WHO-FC"] = 3
    else:
        missing.append("WHO-FC")

    # 6MWD
    six = _safe_float(ui.get("six_mwd_m"))
    if isinstance(six, (int, float)):
        if six > 440:
            grades["6MWD"] = 1
        elif six >= 165:
            grades["6MWD"] = 2
        else:
            grades["6MWD"] = 3
    else:
        missing.append("6MWD")

    # BNP / NT-proBNP (aus bnp_kind + bnp_value)
    bnp_kind = (ui.get("bnp_kind") or "").strip()
    bnp_val = _safe_float(ui.get("bnp_value"))
    bnp = None
    ntp = None
    if isinstance(bnp_val, (int, float)) and bnp_val > 0:
        if bnp_kind.upper().startswith("BNP"):
            bnp = bnp_val
        elif "NT" in bnp_kind.upper():
            ntp = bnp_val

    if bnp is not None:
        if bnp < 50:
            grades["BNP"] = 1
        elif bnp <= 800:
            grades["BNP"] = 2
        else:
            grades["BNP"] = 3
    elif ntp is not None:
        if ntp < 300:
            grades["NT-proBNP"] = 1
        elif ntp <= 1100:
            grades["NT-proBNP"] = 2
        else:
            grades["NT-proBNP"] = 3
    else:
        missing.append("BNP/NT-proBNP")

    # Synkope (keine / gelegentlich / wiederholt)
    syn = ui.get("syncope")
    if isinstance(syn, bool):
        grades["Synkope"] = 3 if syn else 1
    else:
        syn_s = (syn or "").strip().lower()
        if syn_s in ("", "keine", "nein", "0", "none"):
            grades["Synkope"] = 1
        elif syn_s in ("gelegentlich", "selten", "occasional"):
            grades["Synkope"] = 2
        elif syn_s in ("wiederholt", "häufig", "repeated"):
            grades["Synkope"] = 3
        else:
            missing.append("Synkope")

    # Echokardiographie: RA-ESA & Perikarderguss
    ra = _safe_float(ui.get("ra_esa_cm2"))
    if isinstance(ra, (int, float)) and ra > 0:
        if ra < 18:
            grades["RA-ESA"] = 1
        elif ra <= 26:
            grades["RA-ESA"] = 2
        else:
            grades["RA-ESA"] = 3
    else:
        missing.append("RA-ESA")

    pe = (ui.get("pericardial_effusion") or "").strip().lower()
    if pe in ("kein", "nein", "no", "none"):
        grades["Perikarderguss"] = 1
    elif pe in ("minimal", "klein"):
        grades["Perikarderguss"] = 2
    elif pe in ("relevant", "moderat", "gross", "groß", "großzügig"):
        grades["Perikarderguss"] = 3
    else:
        missing.append("Perikarderguss")

    # Hämodynamik: RAP, CI, SvO2
    rap = _safe_float(ui.get("rap_rest"))
    if isinstance(rap, (int, float)):
        if rap < 8:
            grades["RAP"] = 1
        elif rap <= 14:
            grades["RAP"] = 2
        else:
            grades["RAP"] = 3
    else:
        missing.append("RAP")

    ci = derived.get("ci")
    if not isinstance(ci, (int, float)) or ci <= 0:
        ci = _safe_float(ui.get("ci_rest"))
    if isinstance(ci, (int, float)) and ci > 0:
        if ci >= 2.5:
            grades["CI"] = 1
        elif ci >= 2.0:
            grades["CI"] = 2
        else:
            grades["CI"] = 3
    else:
        missing.append("CI")

    svo2 = _safe_float(ui.get("sat_pa"))
    if isinstance(svo2, (int, float)) and svo2 > 0:
        if svo2 > 65:
            grades["SvO2"] = 1
        elif svo2 >= 60:
            grades["SvO2"] = 2
        else:
            grades["SvO2"] = 3
    else:
        missing.append("SvO2")

    # TAPSE/sPAP ratio (aus derived)
    tsp = derived.get("tapse_spap")
    if isinstance(tsp, (int, float)) and tsp > 0:
        if tsp > 0.32:
            grades["TAPSE/sPAP"] = 1
        elif tsp >= 0.19:
            grades["TAPSE/sPAP"] = 2
        else:
            grades["TAPSE/sPAP"] = 3
    else:
        missing.append("TAPSE/sPAP")

    # CMR: RVEF
    rvef = _safe_float(ui.get("cmr_rvef"))
    if isinstance(rvef, (int, float)) and rvef > 0:
        if rvef > 54:
            grades["CMR-RVEF"] = 1
        elif rvef >= 37:
            grades["CMR-RVEF"] = 2
        else:
            grades["CMR-RVEF"] = 3
    else:
        missing.append("CMR-RVEF")

    if not grades:
        return None

    mean_grade = sum(grades.values()) / max(len(grades), 1)
    if mean_grade <= 1.5:
        cat = "niedrig"
    elif mean_grade <= 2.5:
        cat = "intermediär"
    else:
        cat = "hoch"

    return EscErsComprehensiveResult(
        category=cat,
        mean_grade=mean_grade,
        n_params=len(grades),
        grades=grades,
        missing=missing,
    )


@dataclass(frozen=True)
class RevealLite2Result:
    points: int
    category: str
    details: Dict[str, int]
    missing: List[str]


def calc_reveal_lite2(ui: Dict[str, Any]) -> Optional[RevealLite2Result]:
    """REVEAL Lite 2 – vereinfachte Implementierung (6 Parameter).

    Benötigt:
      - WHO-FC
      - 6MWD
      - BNP oder NT-proBNP (Angabe über 'bnp_kind' + 'bnp_value')
      - systolischer Blutdruck (bp_sys)
      - Herzfrequenz (hr)
      - eGFR (egfr)

    Rückgabe:
      - Punkte (Summe)
      - Risikokategorie (niedrig / intermediär / hoch)
    """
    missing: List[str] = []
    details: Dict[str, int] = {}

    who = (ui.get("who_fc") or "").strip()
    if who in ("I", "II"):
        details["WHO-FC"] = 0
    elif who == "III":
        details["WHO-FC"] = 1
    elif who == "IV":
        details["WHO-FC"] = 2
    else:
        missing.append("WHO-FC")

    six = _safe_float(ui.get("six_mwd_m"))
    if isinstance(six, (int, float)) and six > 0:
        if six >= 440:
            details["6MWD"] = 0
        elif six >= 320:
            details["6MWD"] = 1
        elif six >= 165:
            details["6MWD"] = 2
        else:
            details["6MWD"] = 3
    else:
        missing.append("6MWD")

    bnp_kind = (ui.get("bnp_kind") or "").strip()
    bnp_val = _safe_float(ui.get("bnp_value"))
    if not (isinstance(bnp_val, (int, float)) and bnp_val > 0 and bnp_kind):
        missing.append("BNP/NT-proBNP")
    else:
        if bnp_kind.upper().startswith("BNP"):
            if bnp_val < 50:
                details["BNP/NT-proBNP"] = 0
            elif bnp_val <= 199:
                details["BNP/NT-proBNP"] = 1
            elif bnp_val <= 800:
                details["BNP/NT-proBNP"] = 2
            else:
                details["BNP/NT-proBNP"] = 3
        else:
            # treat all non-BNP as NT-proBNP
            if bnp_val < 300:
                details["BNP/NT-proBNP"] = 0
            elif bnp_val <= 649:
                details["BNP/NT-proBNP"] = 1
            elif bnp_val <= 1100:
                details["BNP/NT-proBNP"] = 2
            else:
                details["BNP/NT-proBNP"] = 3

    sbp = _safe_float(ui.get("bp_sys"))
    if isinstance(sbp, (int, float)) and sbp > 0:
        if sbp >= 110:
            details["RRsys"] = 0
        elif sbp >= 100:
            details["RRsys"] = 1
        elif sbp >= 90:
            details["RRsys"] = 2
        else:
            details["RRsys"] = 3
    else:
        missing.append("RRsys")

    hr = _safe_float(ui.get("hr"))
    if isinstance(hr, (int, float)) and hr > 0:
        if hr < 96:
            details["HF"] = 0
        elif hr <= 105:
            details["HF"] = 1
        elif hr <= 115:
            details["HF"] = 2
        else:
            details["HF"] = 3
    else:
        missing.append("HF")

    egfr = _safe_float(ui.get("egfr"))
    if isinstance(egfr, (int, float)) and egfr > 0:
        if egfr >= 60:
            details["eGFR"] = 0
        elif egfr >= 45:
            details["eGFR"] = 1
        elif egfr >= 30:
            details["eGFR"] = 2
        else:
            details["eGFR"] = 3
    else:
        missing.append("eGFR")

    if missing:
        return RevealLite2Result(points=0, category="nicht berechenbar", details={}, missing=missing)

    points = int(sum(details.values()))
    if points <= 5:
        cat = "niedrig"
    elif points <= 7:
        cat = "intermediär"
    else:
        cat = "hoch"

    return RevealLite2Result(points=points, category=cat, details=details, missing=[])

def classify_exercise_pattern(mpap_co_slope: Optional[float], pawp_co_slope: Optional[float]) -> Optional[str]:
    """
    Heuristic:
    - mpap/CO slope > 3 WU suggests abnormal pulmonary pressure response
    - PAWP/CO slope > 2 WU suggests left-heart filling pressure component
    """
    if mpap_co_slope is None or pawp_co_slope is None:
        return None
    if mpap_co_slope > 3 and pawp_co_slope <= 2:
        return "precap_pattern"
    if mpap_co_slope > 3 and pawp_co_slope > 2:
        return "postcap_pattern"
    if mpap_co_slope <= 3 and pawp_co_slope > 2:
        return "left_pressure_pattern"
    return "normal_pattern"


EXERCISE_PATTERN_LABELS = {
    "normal_pattern": "Regelhafte Druck-/Fluss-Reaktion unter Belastung",
    "precap_pattern": "Auffällige pulmonalvaskuläre Reaktion unter Belastung (präkapillär)",
    "postcap_pattern": "Demaskierung einer postkapillären Komponente unter Belastung",
    "left_pressure_pattern": "Belastungsassoziierte linksatriale Druckerhöhung (PAWP/CO auffällig)",
}

def describe_exercise_pattern(code: Optional[str]) -> str:
    """Returns a human-readable German label for the exercise response pattern code."""
    if not code:
        return ""
    return EXERCISE_PATTERN_LABELS.get(code, str(code))


# =============================================================================
# Step oximetry – step-up detection
# =============================================================================

@dataclass
class StepUpResult:
    present: bool
    from_to: Optional[str] = None
    location: Optional[str] = None  # "atrial"|"ventricular"|"pulmonary"
    delta: Optional[float] = None
    sentence: Optional[str] = None


def detect_step_up(sat_svc: Optional[float],
                   sat_ivc: Optional[float],
                   sat_ra: Optional[float],
                   sat_rv: Optional[float],
                   sat_pa: Optional[float],
                   sat_ao: Optional[float],
                   thr_atrial: float = 7.0,
                   thr_ventricular: float = 5.0,
                   thr_pulmonary: float = 5.0) -> StepUpResult:
    """
    Very practical step-up detection using typical thresholds:
    - Atrial: RA - mean(SVC/IVC) >= ~7%
    - Ventricular: RV - RA >= ~5%
    - Pulmonary artery: PA - RV >= ~5%

    Returns the most likely location of a relevant step-up, if present.
    """
    # Normalize
    def _v(x):
        x = _safe_float(x)
        return None if x is None else float(x)

    svc = _v(sat_svc)
    ivc = _v(sat_ivc)
    ra = _v(sat_ra)
    rv = _v(sat_rv)
    pa = _v(sat_pa)
    ao = _v(sat_ao)

    venous_vals = [v for v in (svc, ivc) if v is not None]
    venous_ref = None
    if len(venous_vals) == 2:
        venous_ref = sum(venous_vals) / 2.0
    elif len(venous_vals) == 1:
        venous_ref = venous_vals[0]

    candidates: List[Tuple[str, float, str]] = []  # (from_to, delta, location)

    if venous_ref is not None and ra is not None:
        d = ra - venous_ref
        if d >= thr_atrial:
            candidates.append(("SVC/IVC → RA", d, "atrial"))

    if ra is not None and rv is not None:
        d = rv - ra
        if d >= thr_ventricular:
            candidates.append(("RA → RV", d, "ventricular"))

    if rv is not None and pa is not None:
        d = pa - rv
        if d >= thr_pulmonary:
            candidates.append(("RV → PA", d, "pulmonary"))

    if not candidates:
        return StepUpResult(
            present=False,
            sentence="Kein relevanter Sättigungssprung in der Stufenoxymetrie."
        )

    # pick the largest delta
    best = sorted(candidates, key=lambda t: t[1], reverse=True)[0]
    from_to, delta, loc = best

    loc_desc = {
        "atrial": "auf Vorhofebene",
        "ventricular": "auf Ventrikelebene",
        "pulmonary": "auf Pulmonalarterienebene",
    }.get(loc, "unklar")

    sentence = f"Relevanter Sättigungssprung {loc_desc} ({from_to}, Δ≈{_fmt(delta,1)}%). Shuntverdacht (Links-Rechts)."
    return StepUpResult(present=True, from_to=from_to, location=loc, delta=delta, sentence=sentence)


# =============================================================================
# TextDB loading (rhk_textdb.py)
# =============================================================================

@dataclass
class TextBlock:
    id: str
    title: str
    template: str
    kind: str  # "bundle"|"module"


class SafeDict(dict):
    """dict for str.format_map that returns an empty string for missing keys."""

    def __missing__(self, key: str) -> str:
        return ""


def load_textdb_blocks() -> Dict[str, TextBlock]:
    """
    Loads rhk_textdb.py if present.

    Expected in rhk_textdb: BLOCKS (dict[str, TextBlock-like]).
    The upstream rhk_textdb ships a TextBlock dataclass with attributes .id/.title/.template.
    We normalize into this app's local TextBlock to keep the rest of the code stable.

    Fallback: minimal built-in blocks.
    """
    import sys

    blocks: Dict[str, TextBlock] = {}

    # Ensure the directory of this script is importable (matches the v18 deployment pattern)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    try:
        import rhk_textdb  # type: ignore

        src = getattr(rhk_textdb, "ALL_BLOCKS", None)
        if isinstance(src, dict):
            for bid, b in src.items():
                bid_s = str(bid)

                # title/template may be attributes (dataclass) or dict keys
                title = getattr(b, "title", None)
                template = getattr(b, "template", None)
                if title is None and isinstance(b, dict):
                    title = b.get("title")
                if template is None and isinstance(b, dict):
                    template = b.get("template")

                kind = "module" if (bid_s.startswith("P") and "_" not in bid_s) else "bundle"
                blocks[bid_s] = TextBlock(
                    id=bid_s,
                    title=str(title or bid_s),
                    template=str(template or ""),
                    kind=kind,
                )

        # Safety: ensure at least minimal core blocks exist
        if "K00_B" not in blocks:
            blocks["K00_B"] = TextBlock(
                id="K00_B", title="Kein Hinweis auf PH", kind="bundle",
                template="Kein Hinweis auf eine pulmonale Hypertonie in den vorliegenden Daten."
            )
        if "K00_E" not in blocks:
            blocks["K00_E"] = TextBlock(
                id="K00_E", title="Empfehlung", kind="bundle",
                template="Kontrolle nach klinischer Indikation. Bei persistierendem Verdacht weitere Diagnostik."
            )
        if "P01" not in blocks:
            blocks["P01"] = TextBlock(
                id="P01", title="Basisdiagnostik komplettieren", kind="module",
                template="• Echokardiographie\n• Lungenfunktion\n• Bildgebung/V/Q\n• Labor inkl. BNP/NT-proBNP"
            )

        return blocks

    except Exception:
        # Minimal fallback
        blocks["K00_B"] = TextBlock(
            id="K00_B", title="Kein Hinweis auf PH", kind="bundle",
            template="Kein Hinweis auf eine pulmonale Hypertonie in den vorliegenden Daten."
        )
        blocks["K00_E"] = TextBlock(
            id="K00_E", title="Empfehlung", kind="bundle",
            template="Kontrolle nach klinischer Indikation. Bei persistierendem Verdacht weitere Diagnostik."
        )
        blocks["P01"] = TextBlock(
            id="P01", title="Basisdiagnostik komplettieren", kind="module",
            template="• Echokardiographie\n• Lungenfunktion\n• Bildgebung/V/Q\n• Labor inkl. BNP/NT-proBNP"
        )
        return blocks


# =============================================================================
# Rendering helpers
# =============================================================================

def render_block(block: TextBlock, ctx: Dict[str, Any]) -> str:
    try:
        return block.template.format_map(SafeDict(ctx))
    except Exception as e:
        return f"[Template-Fehler in {block.id}: {e}]"


# =============================================================================
# Declarative Rule Engine
# =============================================================================

@dataclass
class Rule:
    id: str
    when: str
    then: Dict[str, Any]
    priority: int = 100


@dataclass
class Decision:
    bundle: str = "K00"
    primary_dx: str = "—"
    modules: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    require_fields: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    leading_cause: Optional[str] = None
    leading_action: Optional[str] = None


# --- Safe boolean expression evaluator (no builtins, no calls) ----------------

class SafeExprError(Exception):
    pass


_ALLOWED_NODES = (
    "Expression", "BoolOp", "BinOp", "UnaryOp", "Compare", "Name", "Load",
    "Constant", "And", "Or", "Not", "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE",
    "Is", "IsNot", "In", "NotIn",
)


def safe_eval_bool(expr: str, env: Dict[str, Any]) -> bool:
    import ast

    if not expr or not expr.strip():
        return False

    tree = ast.parse(expr, mode="eval")

    for node in ast.walk(tree):
        if node.__class__.__name__ not in _ALLOWED_NODES:
            raise SafeExprError(f"Node not allowed: {node.__class__.__name__}")

    class _Eval(ast.NodeVisitor):
        def visit_Expression(self, node):  # type: ignore
            return self.visit(node.body)

        def visit_Name(self, node):  # type: ignore
            return env.get(node.id)

        def visit_Constant(self, node):  # type: ignore
            return node.value

        def visit_BoolOp(self, node):  # type: ignore
            if isinstance(node.op, ast.And):
                return all(self.visit(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(self.visit(v) for v in node.values)
            raise SafeExprError("Unsupported BoolOp")

        def visit_UnaryOp(self, node):  # type: ignore
            if isinstance(node.op, ast.Not):
                return not bool(self.visit(node.operand))
            raise SafeExprError("Unsupported UnaryOp")

        def visit_Compare(self, node):  # type: ignore
            left = self.visit(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self.visit(comp)
                ok = None
                try:
                    if isinstance(op, ast.Eq):
                        ok = (left == right)
                    elif isinstance(op, ast.NotEq):
                        ok = (left != right)
                    elif isinstance(op, ast.Lt):
                        ok = (left is not None and right is not None and left < right)
                    elif isinstance(op, ast.LtE):
                        ok = (left is not None and right is not None and left <= right)
                    elif isinstance(op, ast.Gt):
                        ok = (left is not None and right is not None and left > right)
                    elif isinstance(op, ast.GtE):
                        ok = (left is not None and right is not None and left >= right)
                    elif isinstance(op, ast.Is):
                        ok = (left is right)
                    elif isinstance(op, ast.IsNot):
                        ok = (left is not right)
                    elif isinstance(op, ast.In):
                        ok = (left in right) if right is not None else False
                    elif isinstance(op, ast.NotIn):
                        ok = (left not in right) if right is not None else False
                    else:
                        raise SafeExprError("Unsupported Compare op")
                except Exception:
                    ok = False
                if not ok:
                    return False
                left = right
            return True

    return bool(_Eval().visit(tree))


def load_rulebook(path: str) -> List[Rule]:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed. Please add pyyaml to requirements.")
    if not os.path.exists(path):
        # Empty rulebook fallback
        return []

    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    rules: List[Rule] = []
    for r in doc.get("rules", []):
        rules.append(
            Rule(
                id=str(r.get("id")),
                when=str(r.get("when")),
                then=dict(r.get("then") or {}),
                priority=int(r.get("priority", 100)),
            )
        )

    rules.sort(key=lambda rr: rr.priority)
    return rules


def apply_rule_engine(env: Dict[str, Any], rules: List[Rule]) -> Decision:
    d = Decision(bundle="K00", primary_dx="Kein Hinweis auf PH")
    for rule in rules:
        try:
            if safe_eval_bool(rule.when, env):
                then = rule.then or {}

                if "set_bundle" in then:
                    d.bundle = str(then["set_bundle"])
                if "set_primary_dx" in then:
                    d.primary_dx = str(then["set_primary_dx"])
                if "set_leading_cause" in then:
                    d.leading_cause = str(then["set_leading_cause"])
                if "set_leading_action" in then:
                    d.leading_action = str(then["set_leading_action"])

                if "add_modules" in then:
                    for m in then.get("add_modules") or []:
                        if m not in d.modules:
                            d.modules.append(m)

                if "add_recommendations" in then:
                    for rec in then.get("add_recommendations") or []:
                        if rec and rec not in d.recommendations:
                            d.recommendations.append(str(rec))

                if "require_fields" in then:
                    for fld in then.get("require_fields") or []:
                        if fld not in d.require_fields:
                            d.require_fields.append(str(fld))

                if "add_tags" in then:
                    for t in then.get("add_tags") or []:
                        if t and t not in d.tags:
                            d.tags.append(str(t))

        except Exception:
            # Never crash on rule evaluation.
            continue
    return d


# =============================================================================
# Case building (derived values + env for rule engine)
# =============================================================================

def _infer_anemia(sex: Optional[str], hb_g_dl: Optional[float]) -> bool:
    if hb_g_dl is None:
        return False
    s = (sex or "").lower()
    # pragmatic thresholds
    if "männ" in s:
        return hb_g_dl < 13.0
    if "weib" in s:
        return hb_g_dl < 12.0
    return hb_g_dl < 12.5


def _hemo_category(mpap: Optional[float], pawp: Optional[float], pvr: Optional[float]) -> str:
    if mpap is None:
        return "unknown"
    if mpap <= 20:
        return "no_ph"
    if pawp is None or pvr is None:
        return "ph_unclassified"
    if pawp <= 15 and pvr > 2:
        return "precap"
    if pawp > 15 and pvr <= 2:
        return "ipcph"
    if pawp > 15 and pvr > 2:
        return "cpcph"
    # unusual combos
    if pawp <= 15 and pvr <= 2:
        return "high_flow_or_borderline"
    return "ph_unclassified"




def _normalize_module_ids(selected: Any) -> List[str]:
    """Normalisiert UI-Auswahl der Zusatzmodule auf reine IDs (P01–P25).

    Robust gegenüber:
    - reinen IDs ("P03")
    - Labels ("[I] P03 – ...")
    - Tuple-Choices in Gradio (Value = "P03")
    """
    if selected is None:
        return []
    if isinstance(selected, (str, int, float)):
        sel_list = [selected]
    elif isinstance(selected, (list, tuple, set)):
        sel_list = list(selected)
    else:
        sel_list = [selected]

    pat = re.compile(r"\b(P\d{2})\b", re.IGNORECASE)

    out: List[str] = []
    for item in sel_list:
        if item is None:
            continue
        s = str(item).strip()
        m = pat.search(s)
        if m:
            out.append(m.group(1).upper())

    # Dedup (Order beibehalten)
    out = list(dict.fromkeys(out))
    return out


# =============================================================================
# P-Module: Fallbasierte Priorisierung + Nicht-Anwählbar-Logik
# =============================================================================

_ALL_P_MODULE_IDS: List[str] = [f"P{i:02d}" for i in range(1, 26)]


def compute_p_module_policy(ui: Dict[str, Any],
                            derived: Dict[str, Any],
                            decision: "Decision") -> Dict[str, Any]:
    """Ermittelt eine fallbasierte Sortierung/Level-Einordnung der P-Module.

    Ziel (User-Wunsch):
    - Module nach Sinnhaftigkeit sortieren (Level I/II/III)
    - Offensichtlich nicht sinnvolle/zugelassene Module **nicht anwählbar** machen
      (UI: hellgrau + Hinweis)

    Rückgabe:
    - allowed: List[str] (IDs) – auswählbar, sortiert
    - levels: Dict[str,int] – 1..3 (I..III)
    - disabled: Dict[str,str] – ID -> Begründung
    """

    eti = derived.get("ph_etiology") or {}
    cand = eti.get("candidates") or []

    score_by_group: Dict[int, int] = {}
    for c in cand:
        try:
            g = int(c.get("group"))
        except Exception:
            continue
        try:
            sc = int(c.get("score") or 0)
        except Exception:
            sc = 0
        score_by_group[g] = max(score_by_group.get(g, 0), sc)

    g1 = score_by_group.get(1, 0)
    g2 = score_by_group.get(2, 0)
    g3 = score_by_group.get(3, 0)
    g4 = score_by_group.get(4, 0)

    clear_leader = bool(eti.get("clear_leader"))
    leading_group = eti.get("leading_group")

    hemo_cat = str(derived.get("hemo_category") or "unknown")

    # --------- Disable-Logik (konservativ, aber nützlich) ----------
    disabled: Dict[str, str] = {}

    # ---- Modul-spezifische "nicht anwählbar"-Regeln (konservativ, aber praxisnah) ----
    # P21 Schwangerschaft/Verhütung:
    # - nur sinnvoll bei "weiblich" und reproduktivem Alter
    sex = str(ui.get("sex") or "").strip().lower()
    age = _safe_float(ui.get("age"))
    if sex != "weiblich":
        disabled["P21"] = "Nicht passend: Schwangerschaft/Verhütung betrifft in der Regel nur Patientinnen."
    elif age is None:
        disabled["P21"] = "Nicht bewertbar: Alter nicht angegeben. (Regel: > 50 Jahre → nicht anwählbar.)"
    elif age > 50:
        disabled["P21"] = "Nicht passend: Alter > 50 Jahre – Schwangerschaft/Verhütung ist hier in der Regel nicht relevant."

    # P13 Anämie/Eisenmangel:
    # - nur dann relevant/prioritär, wenn Hb angegeben und unter Norm
    hb = _safe_float(ui.get("hb_g_dl"))
    if hb is None:
        disabled["P13"] = "Nicht bewertbar: Hb nicht angegeben (kein Hinweis auf Anämie dokumentiert)."
    else:
        # sehr einfache, klinisch robuste Untergrenzen
        hb_low = 13.0 if sex == "männlich" else 12.0
        if hb >= hb_low:
            disabled["P13"] = f"Kein Hinweis auf Anämie: Hb {_fmt(hb,1)} g/dL (Untergrenze {hb_low:.1f})."


    # Weitere Modul-spezifische "nicht anwählbar"-Regeln
    # Hinweis: Wir deaktivieren nur dann, wenn aus den vorhandenen Angaben **kein** plausibler Nutzen ableitbar ist.

    # P08 ILD Konferenz oder Fibroseambulanz
    # - nur sinnvoll, wenn ILD Restriktion oder Fibrose Hinweise dokumentiert sind
    ct_ild = bool(ui.get("ct_ild"))
    lufu_restr = bool(ui.get("lufu_restrictive"))
    ild_type = str(ui.get("ild_type") or "").strip()
    antifib_status = str(ui.get("antifibrotic_status") or "").strip().lower()
    if not (ct_ild or lufu_restr or ild_type or (antifib_status == "ja")):
        disabled["P08"] = (
            "Kein Hinweis auf eine relevante ILD oder Fibrose in den Angaben, "
            "keine Restriktion und keine antifibrotische Therapie dokumentiert."
        )

    # P10 Antikoagulation und Gerinnungsambulanz
    # - deaktivieren, wenn keinerlei Indikation erkennbar ist
    antico = str(ui.get("anticoag_status") or "").strip().lower()
    if antico == "nein":
        if not bool(ui.get("atrial_fib")) and not bool(ui.get("vq_defect")) and not bool(ui.get("ct_embolie")):
            disabled["P10"] = (
                "Kein Hinweis auf eine Antikoagulationsindikation dokumentiert, "
                "kein Vorhofflimmern und kein Emboliehinweis."
            )

    # P12 Lungenfunktionelle Abklärung Restriktion oder DLCO
    # - deaktivieren, wenn Lufu als unauffällig markiert ist
    if bool(ui.get("lufu_done")) and not bool(ui.get("lufu_obstructive")) and not bool(ui.get("lufu_restrictive")) and not bool(ui.get("lufu_diffusion")):
        disabled["P12"] = (
            "Lungenfunktion als unauffällig markiert, keine Obstruktion, keine Restriktion und keine Diffusionsstörung dokumentiert."
        )

    # P15 Belastungsdiagnostik
    # - deaktivieren, wenn bereits durchgeführt
    if bool(ui.get("exercise_done")):
        disabled["P15"] = "Belastungsdiagnostik ist bereits dokumentiert."

    # P09 Kardiologische Mitbeurteilung
    # - deaktivieren, wenn keine Hinweise auf kardiale Mitursachen dokumentiert sind
    lvef = _safe_float(ui.get("lvef"))
    if (lvef is not None and lvef >= 55.0) and (not bool(ui.get("atrial_fib"))) and (not bool(ui.get("ct_koronarkalk"))):
        disabled["P09"] = "Kein Hinweis auf relevante kardiale Mitursachen dokumentiert, LVEF unauffällig, kein Vorhofflimmern und kein Koronarkalkhinweis."

    # P14 RV Prognosemarker
    # - deaktivieren, wenn RV Parameter unauffällig sind
    tapse = _safe_float(ui.get("tapse_mm"))
    rvef = _safe_float(ui.get("rvef"))
    rv_lv = _safe_float(ui.get("rv_lv_ratio"))
    rap_val = _safe_float(derived.get("rap_rest") if derived.get("rap_rest") is not None else derived.get("rap"))
    if (tapse is not None and tapse >= 18.0) and ((rvef is None) or (rvef >= 45.0)) and ((rv_lv is None) or (rv_lv <= 1.0)) and ((rap_val is None) or (rap_val <= 8.0)):
        disabled["P14"] = "Kein Hinweis auf relevante RV Dysfunktion in den Angaben, TAPSE und RV Parameter unauffällig."

    # P17 Autoimmun Screening
    # - deaktivieren, wenn die Konstellation nicht für PAH spricht und keine Autoimmun Hinweise dokumentiert sind
    if (not bool(ui.get("immunology_pos"))) and (leading_group != 1) and (g1 < 2):
        disabled["P17"] = "Kein Hinweis auf Autoimmunerkrankung dokumentiert und die Konstellation spricht nicht primär für PAH."

    # P18 Infektiologisches Screening
    # - deaktivieren, wenn keine Hinweise dokumentiert sind und keine PAH Konstellation vorliegt
    if (not bool(ui.get("virology_pos"))) and (leading_group != 1) and (g1 < 2):
        disabled["P18"] = "Kein Hinweis auf relevante infektiologische Auslöser dokumentiert und die Konstellation spricht nicht primär für PAH."

    # P19 Portopulmonale PH Abklärung
    # - deaktivieren, wenn Abdomensonographie ohne Hinweis auf Lebererkrankung dokumentiert ist
    if bool(ui.get("abd_sono_done")):
        abd_desc = str(ui.get("abd_sono_desc") or "").strip().lower()
        if abd_desc and any(w in abd_desc for w in ("unauffällig", "normal", "kein hinweis")):
            disabled["P19"] = "Abdomensonographie ohne Hinweis auf Leberzirrhose oder portale Hypertension dokumentiert."

    # P20 Genetik
    # - deaktivieren, wenn keine Hinweise dokumentiert sind und PAH nicht im Vordergrund steht
    if (not bool(ui.get("mutation_pos"))) and (leading_group != 1) and (g1 < 2) and (age is None or age >= 50):
        disabled["P20"] = "Kein Hinweis auf hereditäre PAH oder relevante Mutation dokumentiert, PAH steht nicht im Vordergrund."

    # P06 Prostacyclin Therapie und P25 Advanced Therapies
    # - deaktivieren bei klar niedrigem Risiko
    risk_cat = str(derived.get("risk_category") or "").strip().lower()
    who_fc = str(ui.get("who_fc") or "").strip().upper()
    if risk_cat == "low" and who_fc in ("I", "II"):
        disabled["P06"] = "Niedriges Risiko und WHO FC I bis II, eine Prostacyclin Eskalation ist daraus nicht ableitbar."
        disabled["P25"] = "Niedriges Risiko und WHO FC I bis II, keine Indikation für Advanced Therapies ableitbar."

    # Dominante Gruppe-2-Konstellation: v.a. iPcPH / cPcPH mit klarer Linksherzdominanz
    dominant_g2 = bool(clear_leader and leading_group == 2 and g1 < 2 and g4 < 2)

    if hemo_cat in ("no_ph", "unknown"):
        reason = ("Der Katheter zeigt keine gesicherte pulmonale Hypertonie (mPAP ≤ 20 mmHg) "
                  "bzw. unvollständige Angaben – PH-spezifische Therapien sind daraus nicht ableitbar.")
        for mid in ("P03", "P04", "P05", "P06"):
            disabled[mid] = reason

    elif dominant_g2 and hemo_cat in ("ipcph", "cpcph"):
        reason = ("Konstellation spricht überwiegend für eine postkapilläre PH/Linksherzdominanz (Gruppe 2). "
                  "PH-spezifische Therapien (PAH/CTEPH-Medikamente) sind hierfür i.d.R. nicht zugelassen – "
                  "bitte im PH-Board/Fachzentrum prüfen.")
        for mid in ("P03", "P04", "P05", "P06"):
            disabled[mid] = reason

    # --------- Level (I/II/III) ----------
    levels: Dict[str, int] = {mid: 3 for mid in _ALL_P_MODULE_IDS}

    # Auto-Module aus Regelwerk immer priorisiert (wenn nicht disabled)
    try:
        auto_mods = list(decision.modules or [])
    except Exception:
        auto_mods = []
    for mid in auto_mods:
        if mid in levels and mid not in disabled:
            levels[mid] = 1

    # Heuristiken
    if bool(derived.get("congestion_likely")) and "P02" not in disabled:
        levels["P02"] = 1

    if bool(derived.get("anemia")) and "P13" not in disabled:
        levels["P13"] = 1

    # CTEPH-typische Konstellation
    if g4 >= 2 or bool(ui.get("vq_defect")) or bool(ui.get("ct_embolie")) or bool(ui.get("ct_mosaic")):
        if "P10" not in disabled:
            levels["P10"] = 1
        if "P05" not in disabled:
            levels["P05"] = min(levels.get("P05", 3), 1)

    # Lungen-/ILD-typische Konstellation
    if g3 >= 2 or bool(ui.get("ild")) or bool(ui.get("ct_ild")) or bool(ui.get("ct_emphysema")):
        if "P12" not in disabled:
            levels["P12"] = 1
        if "P08" not in disabled:
            levels["P08"] = 1

    # Linksherzdominanz / HFpEF-Wahrscheinlichkeit
    pawp = _safe_float(ui.get("pawp_rest"))
    hfpef_cat = str(derived.get("hfpef_category") or "").lower()
    if g2 >= 2 or (pawp is not None and pawp > 15) or hfpef_cat in ("wahrscheinlich", "likely", "hoch", "high"):
        if "P09" not in disabled:
            levels["P09"] = 1
        if "P02" not in disabled:
            levels["P02"] = min(levels.get("P02", 3), 2)

    # RV/RA-Marker auffällig → Verlauf/Stratifizierung strukturieren
    if bool(derived.get("tapse_spap_reduced")) or bool(derived.get("s_prime_raai_low")):
        if "P14" not in disabled:
            levels["P14"] = min(levels.get("P14", 3), 2)

    # Hochrisiko → eskalationsnahe Themen hoch priorisieren
    esc4 = str(derived.get("esc_ers_4strata") or "").strip().lower()
    if esc4 in ("high", "intermediate-high"):
        for mid in ("P06", "P25"):
            if mid in levels and mid not in disabled:
                levels[mid] = 1
    elif esc4 in ("intermediate", "intermediate-low"):
        if "P25" not in disabled:
            levels["P25"] = min(levels.get("P25", 3), 2)

    # Zusätzliche Trigger (NEU: Mutation/Virologie/Immunologie/CHD)
    if bool(ui.get("mutation_pos")) and "P20" not in disabled:
        levels["P20"] = 1
    if bool(ui.get("virology_pos")) and "P18" not in disabled:
        levels["P18"] = 1
    if bool(ui.get("immunology_pos")) and "P17" not in disabled:
        levels["P17"] = 1
    if bool(ui.get("chd_pos")) and "P01" not in disabled:
        levels["P01"] = min(levels.get("P01", 3), 1)

    # Generell sinnvolle Basismodule (wenn nicht anders priorisiert)
    for mid in ("P11", "P23"):
        if mid in levels and mid not in disabled:
            levels[mid] = min(levels[mid], 2)

    # allowed + sortiert
    allowed = [mid for mid in _ALL_P_MODULE_IDS if mid not in disabled]
    allowed_sorted = sorted(
        allowed,
        key=lambda m: (levels.get(m, 3), int(m[1:]) if m[1:].isdigit() else 999),
    )

    return {
        "allowed": allowed_sorted,
        "levels": levels,
        "disabled": disabled,
        "group_scores": {1: g1, 2: g2, 3: g3, 4: g4},
        "hemo_category": hemo_cat,
        "leading_group": leading_group,
        "clear_leader": clear_leader,
    }


def _level_prefix(level: int) -> str:
    if level == 1:
        return "[I]"
    if level == 2:
        return "[II]"
    if level == 3:
        return "[III]"
    return "[—]"


def build_p_module_choices(blocks: Dict[str, "TextBlock"],
                           policy: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Erstellt Checkbox-Choices (Label, Value=ID) aus Policy."""
    if not policy:
        # Fallback: einfach P01..P25
        out: List[Tuple[str, str]] = []
        for mid in _ALL_P_MODULE_IDS:
            if mid in blocks:
                out.append((f"{mid} – {blocks[mid].title}", mid))
        return out

    levels: Dict[str, int] = policy.get("levels") or {}
    allowed: List[str] = policy.get("allowed") or []

    out: List[Tuple[str, str]] = []
    for mid in allowed:
        if mid in blocks:
            lvl = int(levels.get(mid, 3))
            label = f"{_level_prefix(lvl)} {mid} – {blocks[mid].title}"
            out.append((label, mid))
    return out


def build_disabled_p_modules_html(blocks: Dict[str, "TextBlock"],
                                 policy: Optional[Dict[str, Any]]) -> str:
    """HTML-Liste der nicht anwählbaren Module (hellgrau hinterlegt)."""
    if not policy:
        return ""
    disabled: Dict[str, str] = policy.get("disabled") or {}
    if not disabled:
        return ""

    # sort by numeric id
    mids = sorted(disabled.keys(), key=lambda m: (int(m[1:]) if m[1:].isdigit() else 999, m))

    cards: List[str] = []
    for mid in mids:
        title = blocks[mid].title if mid in blocks else ""
        reason = disabled.get(mid, "")
        cards.append(
            f"""<div class='pmod-card disabled'>
  <div class='pmod-title'>{mid} – {title}</div>
  <div class='pmod-reason'>{_escape_html(reason)}</div>
</div>"""
        )

    return (
        "<div style='margin-top:6px;'>"
        "<div style='font-weight:650; margin:8px 0 6px 0;'>Derzeit nicht anwählbar</div>"
        "<div class='pmod-disabled-grid'>"
        + "".join(cards)
        + "</div></div>"
    )


def _compare_rhk_trend(ui: Dict[str, Any], derived: Dict[str, Any]) -> Dict[str, Any]:
    """Vergleicht aktuelle RHK-Ruhe-Hämodynamik mit einem optionalen Vor-RHK.

    Liefert eine robuste Richtung (besser/stabil/schlechter/gemischt) inkl. kurzer Begründung
    und einer praxisnahen Konsequenzempfehlung. Kein Ersatz für klinische Beurteilung.
    """
    prev_date = (ui.get("prev_rhk_date") or "").strip()
    prev_is_initial = bool(ui.get("prev_is_initial"))
    prev_tx = ui.get("prev_tx_added") or []
    prev_tx_free = (ui.get("prev_tx_free") or "").strip()

    # Vorwerte
    prev_mpap = _safe_float(ui.get("prev_mpap"))
    prev_pawp = _safe_float(ui.get("prev_pawp"))
    prev_ci = _safe_float(ui.get("prev_ci"))
    prev_pvr = _safe_float(ui.get("prev_pvr"))
    prev_rap = _safe_float(ui.get("prev_rap"))

    has_prev = bool(prev_date) and any(v is not None for v in (prev_mpap, prev_pawp, prev_ci, prev_pvr, prev_rap))
    if not has_prev:
        return {"has_prev": False}

    # Aktuelle Werte (Ruhe)
    cur_mpap = _safe_float(derived.get("mpap_rest") if derived.get("mpap_rest") is not None else derived.get("mpap"))
    cur_pawp = _safe_float(derived.get("pawp_rest") if derived.get("pawp_rest") is not None else derived.get("pawp"))
    cur_ci = _safe_float(derived.get("ci_rest") if derived.get("ci_rest") is not None else derived.get("ci"))
    cur_pvr = _safe_float(derived.get("pvr_rest") if derived.get("pvr_rest") is not None else derived.get("pvr"))
    cur_rap = _safe_float(derived.get("rap_rest") if derived.get("rap_rest") is not None else derived.get("rap"))

    # Bewertungsregeln (tolerant gegenüber Messstreuung)
    # Verbesserung: relevante Abnahme/Anstieg über kleine Schwellen
    thr = {
        "mpap": 3.0,   # mmHg
        "pawp": 2.0,   # mmHg
        "pvr": 0.5,    # WU
        "ci": 0.2,     # l/min/m²
        "rap": 2.0,    # mmHg
    }

    def _cmp(name: str, prev: Optional[float], cur: Optional[float]) -> Optional[str]:
        if prev is None or cur is None:
            return None
        d = cur - prev
        if name in {"mpap", "pawp", "pvr", "rap"}:
            if d <= -thr[name]:
                return "better"
            if d >= thr[name]:
                return "worse"
            return "same"
        if name == "ci":
            if d >= thr[name]:
                return "better"
            if d <= -thr[name]:
                return "worse"
            return "same"
        return None

    comps = {
        "mPAP": (prev_mpap, cur_mpap, _cmp("mpap", prev_mpap, cur_mpap), "mmHg", 0),
        "PAWP": (prev_pawp, cur_pawp, _cmp("pawp", prev_pawp, cur_pawp), "mmHg", 0),
        "PVR": (prev_pvr, cur_pvr, _cmp("pvr", prev_pvr, cur_pvr), "WU", 1),
        "CI": (prev_ci, cur_ci, _cmp("ci", prev_ci, cur_ci), "l/min/m²", 2),
        "RAP": (prev_rap, cur_rap, _cmp("rap", prev_rap, cur_rap), "mmHg", 0),
    }

    better = sum(1 for _, (_, _, c, _, _) in comps.items() if c == "better")
    worse = sum(1 for _, (_, _, c, _, _) in comps.items() if c == "worse")

    if better >= 2 and worse == 0:
        trend = "besser"
    elif worse >= 2 and better == 0:
        trend = "schlechter"
    elif better > 0 and worse > 0:
        trend = "gemischt"
    else:
        trend = "stabil"

    # Details (Doc): mPAP 35→28 mmHg (↓)
    arrow_map = {"better": "↓", "worse": "↑", "same": "≈", None: ""}

    def _fmt_pair(prev: Optional[float], cur: Optional[float], unit: str, digits: int) -> str:
        if prev is None or cur is None:
            return ""
        return f"{_fmt(prev, digits)}→{_fmt(cur, digits)} {unit}"

    detail_bits: List[str] = []
    detail_bits_pat: List[str] = []
    table_rows: List[str] = []

    for label, (pv, cv, c, unit, digits) in comps.items():
        if pv is None or cv is None:
            continue
        arr = arrow_map.get(c, "")
        pair = _fmt_pair(pv, cv, unit, digits)
        if pair:
            detail_bits.append(f"{label} {pair} {arr}".strip())
            # Patient: weniger dicht, aber konkret
            if c == "better":
                detail_bits_pat.append(f"{label}: besser ({pair})")
            elif c == "worse":
                detail_bits_pat.append(f"{label}: höher/schlechter ({pair})")
            else:
                detail_bits_pat.append(f"{label}: ähnlich ({pair})")
            table_rows.append(f"| {label} | {_fmt(pv, digits)} | {_fmt(cv, digits)} | {arr or '≈'} |")

    tx_parts: List[str] = []
    # prev_tx kann als Liste (CheckboxGroup) kommen oder als String
    if isinstance(prev_tx, str) and prev_tx.strip():
        tx_parts.append(prev_tx.strip())
    elif isinstance(prev_tx, list) and prev_tx:
        tx_parts.extend([str(x).strip() for x in prev_tx if str(x).strip()])
    if prev_tx_free:
        tx_parts.append(prev_tx_free)

    tx_txt = "; ".join(dict.fromkeys(tx_parts))  # dedup preserve order

    ctx_txt = "Initialkatheter" if prev_is_initial else "Voruntersuchung"
    under_txt = f" unter Therapieanpassung ({tx_txt})" if tx_txt else ""

    # Sätze
    sentence_doc = f"Verlauf im Vergleich zu RHK {prev_date} ({ctx_txt}){under_txt}: insgesamt **{trend}**."
    sentence_pat = f"Im Vergleich zu Ihrer früheren Herzkatheter-Untersuchung ({prev_date}) sind die Werte insgesamt **{trend}**."

    # Konsequenz (kurz + praxisnah)
    if trend == "besser":
        rec_doc = "Verlauf spricht für hämodynamisches Ansprechen – Fortführung/Optimierung der Therapie und Verlaufskontrolle gemäß Gesamtrisiko."
        rec_pat = "Das spricht dafür, dass die Behandlung wirkt. Wir besprechen die nächsten Schritte und die weitere Kontrolle."
    elif trend == "stabil":
        rec_doc = "Im Verlauf keine klare Änderung – Therapie/Komorbiditäten nach Gesamtschau weiter optimieren und klinisch/echo‑basiert nachverfolgen."
        rec_pat = "Die Werte sind ähnlich. Entscheidend sind Beschwerden und Gesamtbild – wir schauen gemeinsam, ob Anpassungen sinnvoll sind."
    elif trend == "gemischt":
        rec_doc = "Gemischter Verlauf – einzelne Werte besser, andere unverändert/ungünstiger. Therapie und Begleitfaktoren (Volumenstatus, Lunge, linkes Herz) gezielt prüfen."
        rec_pat = "Einige Werte sind besser, andere eher unverändert. Wir prüfen gezielt, welche Faktoren das erklären und was man verbessern kann."
    else:  # schlechter
        rec_doc = "Hämodynamische Verschlechterung – zeitnahe Reevaluation (Therapieeskalation/Adhärenz/Komorbiditäten/Differenzialdiagnosen) erwägen."
        rec_pat = "Die Werte sind eher schlechter. Deshalb ist wichtig, dass wir die Behandlung zeitnah überprüfen und ggf. anpassen."

    table_md = "\n".join([
        "| Parameter | Vorher | Jetzt | Trend |",
        "|---|---:|---:|:---:|",
        *table_rows,
    ]) if table_rows else ""

    return {
        "has_prev": True,
        "prev_date": prev_date,
        "trend": trend,
        "tx_txt": tx_txt,
        "sentence_doc": sentence_doc,
        "sentence_patient": sentence_pat,
        "detail_doc": "; ".join(detail_bits),
        "detail_patient": "\n".join([f"- {x}" for x in detail_bits_pat]),
        "table_md": table_md,
        "rec_doc": rec_doc,
        "rec_patient": rec_pat,
    }




# ---------------------------------------------------------------------------
# Re-export: make `from rhk_base import *` work across split modules.
# We intentionally include leading-underscore helpers because other modules rely on them.
__all__ = [k for k in globals().keys() if not k.startswith('__')]
