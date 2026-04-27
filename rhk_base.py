#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.48: rhk_base.py - Version bump to v1.48, Parser-/Transparenz-/Performance-Release
# Refactor v1.47: rhk_base.py - Version bump to v1.47, UI-Übersicht verbessert (Workflow-Panel + nummerierte Tabs)
# Refactor v1.46: rhk_base.py - Version bump to v1.46, Render-Download-Hotfix (404)
# Refactor v1.44: rhk_base.py - Version bump to v1.44, Fix-Header (max 3) aktualisiert
# Refactor v1.37: rhk_base.py - Version bump to v1.37, Fix-Header aktualisiert (Browser-OCR defaults robust)
# Refactor v1.31: rhk_base.py - Version bump to v1.31 (Performance-Release, kein klinischer Logik-Change)
# Refactor v1.30: rhk_base.py - Version bump to v1.30, Fix-Header aktualisiert (kein klinischer Logik-Change)
# Refactor v1.27: rhk_base.py - Version bump to v1.27, Fallback-Fix-Header aktualisiert (kein klinischer Logik-Change)
# Refactor v1.25: rhk_base.py - Version bump to v1.25 (no clinical logic change)
# Refactor v1.24: rhk_base.py - Privacy (no Google Fonts), _safe_float/_safe_int gehärtet, Version bump
"""
RHK Befundassistent (Web) – v1.1

- Ultra-interaktiver Gradio-Assistenzbogen für RHK-/PH-Befunde
- Deklaratives Regelwerk (YAML) zur Guideline-nahen Klassifikation, Modulen & Empfehlungen
- Separater Patientenbericht in einfacher, erklärender Sprache (ohne Abkürzungen/Zahlen)

Hinweis: Dieses Tool ist als Assistenzsystem gedacht und ersetzt keine ärztliche Beurteilung.
"""

from __future__ import annotations

import html as _html
import math
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:  # Optional for non-UI logic/tests; UI startup still enforces version via _require_gradio_version().
    import gradio as gr
except ImportError:  # pragma: no cover
    gr = None

from rhk_logging import log_exception
from rhk_rule_engine import (
    Decision,
    Rule,
    RuleTrace,
    SafeExprError,
    apply_rule_engine,
    apply_rule_engine_trace,
    load_rulebook,
    safe_eval_bool,
)

# Re-export the public clinical thresholds so existing
# `from rhk_base import SPRIME_RAAI_CUTOFF` callers continue to work; the
# canonical definitions with citations live in rhk_thresholds.py.
from rhk_thresholds import (  # noqa: F401
    EXERCISE_MPAP_CO_SLOPE,
    EXERCISE_PAWP_CO_SLOPE,
    SPRIME_RAAI_CUTOFF,
    TAPSE_SPAP_HIGH_RISK,
    TAPSE_SPAP_LOW_RISK,
    VASO_RESPONDER_MPAP_ABS,
    VASO_RESPONDER_MPAP_DROP,
)
from rhk_validation import parse_boolish
from rhk_validation import safe_float as _safe_float
from rhk_validation import safe_float_echo as _safe_float_echo_impl

__all__ = [
    "Decision",
    "Rule",
    "RuleTrace",
    "SafeExprError",
    "apply_rule_engine",
    "apply_rule_engine_trace",
    "load_rulebook",
    "safe_eval_bool",
]


# =============================================================================
# App Meta
# =============================================================================

APP_NAME = "RHK Befundassistent"
# Versioning policy: Semantic-Versionsnummer vMAJOR.MINOR[.PATCH] — bei jeder
# Änderung PATCH erhöhen, bei klinisch relevanten Changes MINOR, bei Breaking
# Changes MAJOR. Automatisierung via `tools/bump_version.py --note "..."`.
APP_VERSION = "v1.1"
APP_TITLE = f"{APP_NAME} – {APP_VERSION}"
_FALLBACK_FIX_LOG = [
    "Fix. v1.1: P-Module-System überarbeitet (Metadata-Felder, Stub-Content-Verstärkung P03–P06, Duplikat-Disambiguierung, P32-Meta-Regel, Laienbefund-Integration P31–P52 in DE/EN/ZH).",
    "Fix. v1.1: Tello-Lab-Design-Adaption (Blau-Palette, Inter-Font, Pill-Tabs, Gradient-Headings).",
    "Fix. v1.1: Arztbericht komplett neu strukturiert (Zusammenfassung-Epikrise, saubere Headings, Procedere-Refactor).",
]


def _load_fix_header_lines() -> List[str]:
    """Load the public 'Fix' header from FIX_HEADER.md if present.

    Optional: when FIX_HEADER.md is missing (the file is a scratch helper for
    short release notes and is not always shipped), the in-code
    ``_FALLBACK_FIX_LOG`` is used. The canonical release notes live in
    ``PATCH_NOTES.md``; this UI surface only shows the most recent few lines.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(here, "FIX_HEADER.md")
        if not os.path.exists(p):
            return list(_FALLBACK_FIX_LOG)
        with open(p, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines()]
        lines = [ln for ln in lines if ln and ln.lower().startswith("fix.")]
        return lines or list(_FALLBACK_FIX_LOG)
    except OSError as exc:
        log_exception("RHK_BASE_FIX_HEADER", "Failed to load FIX_HEADER.md.", exc)
        return list(_FALLBACK_FIX_LOG)


FIX_LOG = _load_fix_header_lines()


def _render_whats_new() -> str:
    return "<br>".join((FIX_LOG or [])[:3])


WHATS_NEW = _render_whats_new()



# =============================================================================
# RHK Glass Header v2.0 (Responsive Island Design)
# =============================================================================
RHK_HEADER_HTML = f"""
<style>

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
    font-family: "Avenir Next", "SF Pro Text", "Segoe UI Variable", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Noto Sans", system-ui, -apple-system, sans-serif !important;
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
    /* Ensure predictable stacking across browsers (prevents washed-out text) */
    isolation: isolate;
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
    /* Keep the aurora behind content, never above text */
    z-index: 0;
    opacity: 0.8;
    pointer-events: none;
}}

/* Content above the aurora layer */
.rhk-left-section, .rhk-right-section, .rhk-text-content {{
    position: relative;
    z-index: 1;
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
    /* Explicit colors to avoid variable collisions with framework themes */
    color: #0f172a !important;
    white-space: nowrap;
}}

.rhk-sub-title {{
    font-size: clamp(15px, 1vw, 18px);
    font-weight: 600;
    color: rgba(15, 23, 42, 0.65) !important;
    margin-top: 2px;
}}

.rhk-meta-tag {{
    display: inline-flex;
    margin-top: 6px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b !important;
}}

/* --- Rechte Sektion (Status Badges) --- */
.rhk-right-section {{
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 16px;
    justify-content: center;
    flex-wrap: wrap;
}}

.rhk-top-actions,
.rhk-status-row {{
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    width: 100%;
    flex-wrap: wrap;
}}

.rhk-lang-switch {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.52);
    border: 1px solid rgba(255, 255, 255, 0.72);
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}}

.rhk-lang-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    color: #64748b !important;
}}

.rhk-lang-buttons {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}

.rhk-lang-btn {{
    appearance: none;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(255, 255, 255, 0.66);
    color: #0f172a;
    border-radius: 999px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.03em;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
}}

.rhk-lang-btn:hover {{
    transform: translateY(-1px);
    border-color: rgba(37, 99, 235, 0.35);
}}

.rhk-lang-btn.is-active,
.rhk-lang-btn[aria-pressed="true"] {{
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: #ffffff;
    border-color: rgba(37, 99, 235, 0.9);
    box-shadow: 0 10px 18px rgba(37, 99, 235, 0.18);
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
    .rhk-right-section {{ align-items: center; }}
    .rhk-top-actions,
    .rhk-status-row {{ justify-content: center; }}
}}
</style>

<a class="rhk-skip-link" href="#rhk_main_content">Zum Inhalt springen</a>
<div id="rhk_topbar_wrapper" role="banner">
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
            <div class="rhk-top-actions">
                <div class="rhk-lang-switch" role="group" aria-label="Sprache wechseln" title="Sprache wechseln">
                    <span class="rhk-lang-label">Sprache</span>
                    <div class="rhk-lang-buttons">
                        <button type="button" class="rhk-lang-btn" data-rhk-lang="de" aria-pressed="true">DE</button>
                        <button type="button" class="rhk-lang-btn" data-rhk-lang="en" aria-pressed="false">EN</button>
                        <button type="button" class="rhk-lang-btn" data-rhk-lang="zh" aria-pressed="false">中文</button>
                    </div>
                </div>
            </div>

            <div class="rhk-status-row" role="status" aria-label="System-Status">
                <div class="rhk-status-badge" aria-label="Gateway Status: Online">
                    <span class="rhk-badge-label">Gateway Status</span>
                    <span class="rhk-badge-value">
                        <span class="status-dot" aria-hidden="true"></span> Online
                    </span>
                </div>

                <div class="rhk-status-badge" style="background: rgba(37, 99, 235, 0.1); border-color: rgba(37, 99, 235, 0.2);" aria-label="Version: {APP_VERSION}">
                    <span class="rhk-badge-label" style="color: #3b82f6;">Version</span>
                    <span class="rhk-badge-value" style="color: #1d4ed8;">
                        {APP_VERSION}
                    </span>
                </div>
            </div>
        </div>

    </div>
</div>
"""

APP_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_RULEBOOK_PATH = os.environ.get("RHK_RULEBOOK", os.path.join(APP_DIR, "rhk_rules.yaml"))

# Clinical thresholds: see top-of-file re-exports from rhk_thresholds.



def _require_gradio_version(min_major: int = 5) -> None:
    """Fail fast with a human friendly error if Gradio is too old."""
    try:
        import gradio as _gr
        ver = getattr(_gr, "__version__", "0.0.0")
        major = int(str(ver).split(".")[0])
    except (ValueError, TypeError, AttributeError) as exc:
        log_exception("RHK_BASE_GRADIO_VERSION", "Failed to parse Gradio version.", exc)
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


def _as_list(v: Any) -> List[Any]:
    """Normalize *v* to a flat list, dropping None and empty strings.

    Handles None, str, list, tuple, set, and scalar values.
    """
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, tuple):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, set):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    return [v]


def _safe_num(x: Any) -> Optional[float]:
    """Parse *x* to float or return None.  Never raises."""
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _pmod_level(levels_map: Dict[str, Any], mid: str) -> int:
    """Return the integer level for module *mid* from *levels_map*, defaulting to 3."""
    try:
        return int(levels_map.get(mid, 3) or 3)
    except (TypeError, ValueError):
        return 3


def _safe_int(x: Any) -> Optional[int]:
    """Konservativer Int-Parser für UI-Inputs.

    - Fehlende Werte -> None (keine implizite 0)
    - Bool -> None
    - Strings mit Komma-Punkt -> ok
    - 0 wird als fehlend behandelt (z.B. leere gr.Number roundtrips)
    """
    v = _safe_float(x)
    if v is None:
        return None
    # NaN
    if isinstance(v, float) and (v != v):
        return None
    if abs(v) < 1e-12:
        return None
    try:
        return int(round(v))
    except (ValueError, TypeError, OverflowError) as exc:
        log_exception("RHK_BASE_SAFE_INT", "Int conversion failed.", exc)
        return None


def _safe_float_echo(x: Any) -> Optional[float]:
    """Echo-spezifische Float-Normalisierung.

    Thin backwards-compatible wrapper around
    :func:`rhk_validation.safe_float_echo` — kept so existing imports continue
    to work. Echo parameters are physiologically never ``0`` and empty import
    fields should not be treated as present.
    """
    return _safe_float_echo_impl(x)


def _escape_html(s: Any) -> str:
    """Einfache HTML-Escaping-Hilfe (für UI-HTML)."""
    try:
        return _html.escape(str(s), quote=True)
    except (ValueError, TypeError) as exc:
        log_exception("RHK_BASE_ESCAPE_HTML", "HTML escaping failed.", exc)
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

def _normalize_height_cm(height_cm: Optional[float]) -> Optional[float]:
    """Normalize height to centimeters.

    The UI label is "cm", but imported values may occasionally be provided in meters.
    - If 0.5 <= height < 3.0, interpret as meters and convert to cm.
    - Otherwise interpret as cm.

    Unphysiologic ranges are treated as missing (None).
    """
    if height_cm is None or height_cm == "":
        return None
    try:
        h = float(height_cm)
    except (ValueError, TypeError) as exc:
        log_exception("RHK_BASE_HEIGHT", "Height conversion failed.", exc)
        return None
    if h <= 0:
        return None
    # meters -> cm
    if 0.5 <= h < 3.0:
        h = h * 100.0
    # broad plausibility gate (keep stable; do not guess)
    if h < 30.0 or h > 300.0:
        return None
    return h


def _normalize_weight_kg(weight_kg: Optional[float]) -> Optional[float]:
    """Normalize weight to kg with broad plausibility."""
    if weight_kg is None or weight_kg == "":
        return None
    try:
        w = float(weight_kg)
    except (ValueError, TypeError) as exc:
        log_exception("RHK_BASE_WEIGHT", "Weight conversion failed.", exc)
        return None
    if w <= 0:
        return None
    # broad plausibility gate
    if w < 1.0 or w > 500.0:
        return None
    return w

def calc_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    h_cm = _normalize_height_cm(height_cm)
    w_kg = _normalize_weight_kg(weight_kg)
    if not h_cm or not w_kg:
        return None
    h_m = h_cm / 100.0
    if h_m <= 0:
        return None
    return w_kg / (h_m * h_m)


def calc_bsa(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    # Mosteller
    h_cm = _normalize_height_cm(height_cm)
    w_kg = _normalize_weight_kg(weight_kg)
    if not h_cm or not w_kg:
        return None
    return math.sqrt((h_cm * w_kg) / 3600.0)


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
    """Probability of heart failure with preserved EF (H2FPEF), continuous model.

    [Reddy YNV et al. Circulation 2018; 138(9):861-870]

    Formula
    -------
    y = -9.1917 + 0.0451·age + 0.1307·BMI + 0.0859·E/e'
        + 0.0520·PASP + 1.6997·AF
    P = e^y / (1 + e^y)  (logistic transform, returned as percentage)

    AF is encoded as 1/0 (yes/no). BMI is capped at 50 to avoid extrapolation
    outside the source cohort.

    Probability → category mapping
    ------------------------------
    The original Reddy 2018 paper defined three risk groups via the discrete
    point score (H2FPEF 0-9): low (0-1), intermediate (2-5), high (6-9).
    This implementation operates on the *continuous* probability instead and
    bins it as follows:

      <20 % → "unlikely"
      20–60 % → "possible"
      ≥60 %  → "likely"

    These bin edges are an internal, conservative approximation of the
    discrete score categories, NOT a direct guideline-anchored mapping. They
    are used only for narrative classification in the patient/physician
    report; the underlying continuous probability is preserved and reported
    alongside the category.
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


def _normalize_who_fc_token(who_fc: Any) -> str:
    """Normalize WHO-FC input from heterogeneous UI/import payloads."""
    if who_fc is None:
        return ""
    if isinstance(who_fc, str):
        return who_fc.strip().upper()
    if isinstance(who_fc, (list, tuple, set)):
        for item in who_fc:
            token = _normalize_who_fc_token(item)
            if token:
                return token
        return ""
    if isinstance(who_fc, dict):
        for k in ("value", "label", "name", "text"):
            if k in who_fc:
                token = _normalize_who_fc_token(who_fc.get(k))
                if token:
                    return token
        return ""
    try:
        return str(who_fc).strip().upper()
    except (ValueError, TypeError, AttributeError) as exc:
        log_exception("RHK_BASE_WHO_FC", "WHO-FC normalization failed.", exc)
        return ""


def calc_esc_ers_4_strata(who_fc: Any,
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
    w = _normalize_who_fc_token(who_fc)
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


def calc_esc_ers_3_strata(who_fc: Any,
                          six_mwd_m: Optional[float],
                          bnp_pg_ml: Optional[float],
                          ntprobnp_pg_ml: Optional[float]) -> Optional[str]:
    """
    ESC/ERS 2022 – Drei-Strata-Risikomodell (Initialbeurteilung; Table 16, vereinfacht).
    Variablen: WHO-FC, 6MWD, BNP oder NT-proBNP.
    """
    grades: List[int] = []

    # WHO-FC
    w = _normalize_who_fc_token(who_fc)
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
    who = str(ui.get("who_fc") or "").strip()
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
    bnp_kind = str(ui.get("bnp_kind") or "").strip()
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
        syn_s = str(syn or "").strip().lower()
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

    pe = str(ui.get("pericardial_effusion") or "").strip().lower()
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

    # SVI (mL/m²) — ESC/ERS 2022 Table 16: >38 / 31–38 / <31.
    # Derived dict carries svi_rest_ml_m2 (computed in rhk_case from SV/BSA).
    svi = derived.get("svi_rest_ml_m2") if isinstance(derived, dict) else None
    if not isinstance(svi, (int, float)) or svi <= 0:
        svi = _safe_float(ui.get("svi_rest_ml_m2"))
    if isinstance(svi, (int, float)) and svi > 0:
        if svi > 38:
            grades["SVI"] = 1
        elif svi >= 31:
            grades["SVI"] = 2
        else:
            grades["SVI"] = 3
    else:
        missing.append("SVI")

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

    # CPET: Peak VO2 + VE/VCO2 slope (ESC/ERS 2022 Table 16 – PAH)
    # Peak VO2: either absolute (ml/min/kg) or %pred. We apply a conservative worst-of rule.
    peak_vo2 = _safe_float(ui.get("cpet_peak_vo2_ml_kg_min"))
    peak_vo2_pct = _safe_float(ui.get("cpet_peak_vo2_pct_pred"))
    peak_grade = None
    if isinstance(peak_vo2, (int, float)) and peak_vo2 > 0:
        if peak_vo2 > 15:
            peak_grade = 1
        elif peak_vo2 >= 11:
            peak_grade = 2
        else:
            peak_grade = 3
    if isinstance(peak_vo2_pct, (int, float)) and peak_vo2_pct > 0:
        if peak_vo2_pct > 65:
            g = 1
        elif peak_vo2_pct >= 35:
            g = 2
        else:
            g = 3
        peak_grade = g if peak_grade is None else max(peak_grade, g)
    if peak_grade is not None:
        grades["CPET Peak VO2"] = peak_grade
    else:
        missing.append("CPET Peak VO2")

    vevco2 = _safe_float(ui.get("cpet_ve_vco2_slope"))
    if isinstance(vevco2, (int, float)) and vevco2 > 0:
        if vevco2 < 36:
            grades["CPET VE/VCO2 slope"] = 1
        elif vevco2 <= 44:
            grades["CPET VE/VCO2 slope"] = 2
        else:
            grades["CPET VE/VCO2 slope"] = 3
    else:
        missing.append("CPET VE/VCO2 slope")

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

    who = str(ui.get("who_fc") or "").strip()
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

    bnp_kind = str(ui.get("bnp_kind") or "").strip()
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


# ---------------------------------------------------------------------------
# CPET (Spiroergometrie) – PH-relevante Parameter + Risikostratifizierung
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CpetScoresResult:
    esc_ers_3_strata: Optional[str]
    grades: Dict[str, int]
    mean_grade: Optional[float]
    cpet_score_4_strata: Optional[str]
    effort_ok: Optional[bool]
    notes: List[str]


def _cpet_grade_peak_vo2(peak_vo2_ml_kg_min: Optional[float], peak_vo2_pct_pred: Optional[float]) -> Optional[int]:
    """ESC/ERS 2022 PAH CPET cutoffs (3 strata) – worst-of rule across absolute + %pred."""
    g_abs: Optional[int] = None
    if isinstance(peak_vo2_ml_kg_min, (int, float)) and peak_vo2_ml_kg_min > 0:
        if peak_vo2_ml_kg_min > 15:
            g_abs = 1
        elif peak_vo2_ml_kg_min >= 11:
            g_abs = 2
        else:
            g_abs = 3
    g_pct: Optional[int] = None
    if isinstance(peak_vo2_pct_pred, (int, float)) and peak_vo2_pct_pred > 0:
        if peak_vo2_pct_pred > 65:
            g_pct = 1
        elif peak_vo2_pct_pred >= 35:
            g_pct = 2
        else:
            g_pct = 3
    if g_abs is None and g_pct is None:
        return None
    if g_abs is None:
        return g_pct
    if g_pct is None:
        return g_abs
    return max(g_abs, g_pct)


def _cpet_grade_vevco2_slope(ve_vco2_slope: Optional[float]) -> Optional[int]:
    if not isinstance(ve_vco2_slope, (int, float)) or ve_vco2_slope <= 0:
        return None
    if ve_vco2_slope < 36:
        return 1
    if ve_vco2_slope <= 44:
        return 2
    return 3


def _cpet_grade_o2_pulse_pct_pred(o2_pulse_pct_pred: Optional[float]) -> Optional[int]:
    """Baccelli 2025 CPET score component: Peak O2-pulse (%pred)."""
    if not isinstance(o2_pulse_pct_pred, (int, float)) or o2_pulse_pct_pred <= 0:
        return None
    if o2_pulse_pct_pred > 65:
        return 1
    if o2_pulse_pct_pred >= 40:
        return 2
    return 3


def _cpet_score_4_strata_from_mean(mean_grade: Optional[float]) -> Optional[str]:
    """4-strata CPET score mapping (Baccelli 2025): 1–1.49 low; 1.5–1.99 int-low; 2–2.49 int-high; 2.5–3 high."""
    if not isinstance(mean_grade, (int, float)):
        return None
    if mean_grade < 1.5:
        return "low"
    if mean_grade < 2.0:
        return "intermediate-low"
    if mean_grade < 2.5:
        return "intermediate-high"
    return "high"


def calc_cpet_scores(ui: Dict[str, Any]) -> Optional[CpetScoresResult]:
    """Compute PH-oriented CPET risk classification + modern 4-strata CPET score.

    Inputs (UI keys):
      - cpet_peak_vo2_ml_kg_min
      - cpet_peak_vo2_pct_pred
      - cpet_ve_vco2_slope
      - cpet_petco2_vt1_mmhg
      - cpet_ve_vco2_vt1
      - cpet_peak_o2_pulse_pct_pred
      - cpet_rer_peak

    Returns:
      - ESC/ERS 3-strata CPET category (low/intermediate/high) based on peak VO2 + VE/VCO2 slope
      - 4-strata CPET score (Baccelli 2025) based on peak VO2 + VE/VCO2 slope + peak O2-pulse (%pred)
      - Notes for pattern recognition (e.g., low PETCO2@VT1)
    """
    if not bool(ui.get("cpet_done")):
        return None

    peak_vo2 = _safe_float(ui.get("cpet_peak_vo2_ml_kg_min"))
    peak_vo2_pct = _safe_float(ui.get("cpet_peak_vo2_pct_pred"))
    vevco2_slope = _safe_float(ui.get("cpet_ve_vco2_slope"))
    petco2_vt1 = _safe_float(ui.get("cpet_petco2_vt1_mmhg"))
    vevco2_vt1 = _safe_float(ui.get("cpet_ve_vco2_vt1"))
    o2pulse_pct = _safe_float(ui.get("cpet_peak_o2_pulse_pct_pred"))
    rer_peak = _safe_float(ui.get("cpet_rer_peak"))

    grades: Dict[str, int] = {}
    notes: List[str] = []

    g_peak = _cpet_grade_peak_vo2(peak_vo2, peak_vo2_pct)
    if g_peak is not None:
        grades["Peak VO2"] = g_peak

    g_ve = _cpet_grade_vevco2_slope(vevco2_slope)
    if g_ve is not None:
        grades["VE/VCO2 slope"] = g_ve

    # ESC/ERS 3-strata CPET (peak VO2 + VE/VCO2 slope)
    esc_cat = None
    if g_peak is not None or g_ve is not None:
        mean = sum([g for g in [g_peak, g_ve] if g is not None]) / max(len([g for g in [g_peak, g_ve] if g is not None]), 1)
        if mean <= 1.5:
            esc_cat = "low"
        elif mean <= 2.5:
            esc_cat = "intermediate"
        else:
            esc_cat = "high"

    # Modern 4-strata CPET score (Baccelli 2025): peak VO2 + VE/VCO2 slope + peak O2-pulse (%pred)
    g_o2p = _cpet_grade_o2_pulse_pct_pred(o2pulse_pct)
    if g_o2p is not None:
        grades["Peak O2-Puls (% Soll)"] = g_o2p

    score_components = [g for g in [g_peak, g_ve, g_o2p] if g is not None]
    mean_grade: Optional[float] = None
    if score_components:
        mean_grade = sum(score_components) / len(score_components)
    score4 = _cpet_score_4_strata_from_mean(mean_grade)

    # Pattern notes (PH-typical markers; not a diagnosis):
    if isinstance(petco2_vt1, (int, float)) and petco2_vt1 > 0:
        if petco2_vt1 <= 34:
            notes.append("PETCO2@VT1 niedrig (≤34 mmHg), vereinbar mit ventilatorischer Ineffizienz/Totraum")
    if isinstance(vevco2_vt1, (int, float)) and vevco2_vt1 > 0:
        if vevco2_vt1 >= 30:
            notes.append("VE/VCO2@VT1 erhöht (≥30), vereinbar mit ventilatorischer Ineffizienz")

    # Effort marker
    effort_ok: Optional[bool] = None
    if isinstance(rer_peak, (int, float)) and rer_peak > 0:
        effort_ok = rer_peak >= 1.05
        if not effort_ok:
            notes.append("Belastungsgrad ggf. eingeschränkt (RER < 1.05) – Interpretation mit Vorsicht")

    return CpetScoresResult(
        esc_ers_3_strata=esc_cat,
        grades=grades,
        mean_grade=mean_grade,
        cpet_score_4_strata=score4,
        effort_ok=effort_ok,
        notes=notes,
    )

def classify_exercise_pattern(mpap_co_slope: Optional[float], pawp_co_slope: Optional[float]) -> Optional[str]:
    """Legacy helper (two-point Δ/ΔCO).

    Kept for backwards compatibility with older report snippets.
    Cutoffs follow ESC/ERS 2022 § 5.1.12.3 — see rhk_thresholds for citation.
    """
    if mpap_co_slope is None or pawp_co_slope is None:
        return None
    if mpap_co_slope > EXERCISE_MPAP_CO_SLOPE and pawp_co_slope <= EXERCISE_PAWP_CO_SLOPE:
        return "precap_pattern"
    if mpap_co_slope > EXERCISE_MPAP_CO_SLOPE and pawp_co_slope > EXERCISE_PAWP_CO_SLOPE:
        return "postcap_pattern"
    if mpap_co_slope <= EXERCISE_MPAP_CO_SLOPE and pawp_co_slope > EXERCISE_PAWP_CO_SLOPE:
        return "left_pressure_pattern"
    return "normal_pattern"


def analyze_exercise_slopes_2pt(
    *,
    exercise_done: bool,
    mpap_rest: Optional[float],
    pawp_rest: Optional[float],
    co_rest: Optional[float],
    mpap_peak: Optional[float],
    pawp_peak: Optional[float],
    co_peak: Optional[float],
    tpg_rest: Optional[float] = None,
    tpg_peak: Optional[float] = None,
    wedge_v_wave: bool = False,
    wedge_a_wave: bool = False,
    atrial_fib: bool = False,
    co_method: Optional[str] = None,
    age: Optional[int] = None,
    dco_min_interpret: float = 1.5,
    dco_good: float = 2.0,
    eps_algebra: float = 0.5,
) -> Dict[str, Any]:
    """Exercise (semi-supine) pressure-flow assessment using *two-point* slopes (rest→peak).

    Deterministic:
    - Slopes are calculated only as Δ/ΔCO (rest→peak), unit mmHg/(L/min).
    - Pattern classification and diagnosis-like language must be gated by QC rules.
    """
    res: Dict[str, Any] = {
        "exercise_done": bool(exercise_done),
        "dco": None,
        "d_mpap": None,
        "d_pawp": None,
        "d_tpg": None,
        "mpap_co_slope_2pt": None,
        "pawp_co_slope_2pt": None,
        "tpg_co_slope_2pt": None,
        "hard_fail_flags": [],
        "soft_flags": [],
        "interpretability": "not_applicable",  # not_applicable | hard_stop | numeric_only | ok
        "pattern_2pt": None,  # normal | pv_dominant | la_dominant | mixed | unclear
    }

    if not exercise_done:
        return res

    # --- hard-stop prerequisites ---
    required = {
        "mpap_rest": mpap_rest,
        "pawp_rest": pawp_rest,
        "co_rest": co_rest,
        "mpap_peak": mpap_peak,
        "pawp_peak": pawp_peak,
        "co_peak": co_peak,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        res["hard_fail_flags"].append("missing_values")
        res["interpretability"] = "hard_stop"
        res["missing_fields"] = missing
        return res

    # cast (safe)
    assert mpap_rest is not None and pawp_rest is not None and co_rest is not None
    assert mpap_peak is not None and pawp_peak is not None and co_peak is not None
    mp_r = float(mpap_rest)
    pw_r = float(pawp_rest)
    co_r = float(co_rest)
    mp_p = float(mpap_peak)
    pw_p = float(pawp_peak)
    co_p = float(co_peak)

    # physiologic sanity (hard)
    if co_r <= 0 or co_p <= 0:
        res["hard_fail_flags"].append("co_nonpositive")
    if pw_r < 0 or pw_p < 0:
        res["hard_fail_flags"].append("pawp_negative")
    if mp_r < pw_r:
        res["hard_fail_flags"].append("wedge_inconsistent_rest")
    if mp_p < pw_p:
        res["hard_fail_flags"].append("wedge_inconsistent_peak")

    dco = co_p - co_r
    res["dco"] = dco
    if dco <= 0:
        res["hard_fail_flags"].append("dco_nonpositive")

    if res["hard_fail_flags"]:
        res["interpretability"] = "hard_stop"
        return res

    # --- compute deltas and slopes (numeric) ---
    d_mpap = mp_p - mp_r
    d_pawp = pw_p - pw_r

    if tpg_rest is None:
        tpg_rest = mp_r - pw_r
    if tpg_peak is None:
        tpg_peak = mp_p - pw_p
    d_tpg = float(tpg_peak) - float(tpg_rest)

    res["d_mpap"] = d_mpap
    res["d_pawp"] = d_pawp
    res["d_tpg"] = d_tpg

    # slopes: only if dCO > 0 (already ensured)
    mpap_s = d_mpap / dco
    pawp_s = d_pawp / dco
    tpg_s = d_tpg / dco
    res["mpap_co_slope_2pt"] = mpap_s
    res["pawp_co_slope_2pt"] = pawp_s
    res["tpg_co_slope_2pt"] = tpg_s

    # --- soft flags / QC ---
    if 0 < dco < dco_min_interpret:
        res["soft_flags"].append("dco_small")

    if abs(mp_p - mp_r) > 30:
        res["soft_flags"].append("extreme_jump_mpap")
    if abs(pw_p - pw_r) > 20:
        res["soft_flags"].append("extreme_jump_pawp")

    wedge_wave_present = bool(wedge_v_wave or wedge_a_wave)
    if wedge_wave_present:
        res["soft_flags"].append("wedge_wave_present")
    if atrial_fib:
        res["soft_flags"].append("af_present")
    co_method_s = str(co_method or "").strip().lower()
    if not co_method_s or co_method_s == "keine angabe":
        res["soft_flags"].append("co_method_unknown")

    # algebra consistency: mPAP/CO ≈ PAWP/CO + TPG/CO
    if abs(mpap_s - (pawp_s + tpg_s)) > eps_algebra:
        res["soft_flags"].append("slope_inconsistent")

    # guardrail: high PAWP slope with low PAWP_peak (semi-supine) => usually artefact / wedge uncertainty
    if pawp_s > 2 and pw_p <= 15:
        res["soft_flags"].append("low_peak_pawp_with_high_slope")

    # interpretability gate for *pattern* (numbers can still be shown)
    if "dco_small" in res["soft_flags"]:
        res["interpretability"] = "numeric_only"
        return res
    if "slope_inconsistent" in res["soft_flags"]:
        res["interpretability"] = "numeric_only"
        return res
    if "low_peak_pawp_with_high_slope" in res["soft_flags"]:
        res["interpretability"] = "numeric_only"
        return res

    # OK for a cautious pattern label (still two-point)
    res["interpretability"] = "ok"

    # --- pattern classification (two-point, QC ok) ---
    if mpap_s <= 3 and pawp_s <= 2:
        res["pattern_2pt"] = "normal"
    elif mpap_s > 3 and pawp_s <= 2 and tpg_s > 1.2:
        res["pattern_2pt"] = "pv_dominant"
    elif pawp_s > 2 and tpg_s <= 1.2:
        res["pattern_2pt"] = "la_dominant"
    elif pawp_s > 2 and tpg_s > 1.2:
        res["pattern_2pt"] = "mixed"
    else:
        res["pattern_2pt"] = "unclear"

    return res


from rhk_config import EXERCISE_PATTERN_LABELS  # centralised; re-exported for back-compat


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
    - Atrial: RA - SVC >= ~7%
    - Ventricular: RV - RA >= ~5%
    - Pulmonary artery: PA - RV >= ~5%

    Returns the most likely location of a relevant step-up, if present.
    """
    # Normalize
    def _v(x):
        x = _safe_float(x)
        return None if x is None else float(x)

    svc = _v(sat_svc)
    # IVC saturation is often not sampled in routine cath workflows and was a frequent
    # source of confusion in the UI. We keep the function signature for backward
    # compatibility but do not use IVC for the venous reference.
    _ = _v(sat_ivc)  # kept intentionally (ignored)
    ra = _v(sat_ra)
    rv = _v(sat_rv)
    pa = _v(sat_pa)
    _ = _v(sat_ao)  # kept for validation side-effect

    # Venous reference: SVC only (datensparsam + robust).
    venous_ref = svc if svc is not None else None

    candidates: List[Tuple[str, float, str]] = []  # (from_to, delta, location)

    if venous_ref is not None and ra is not None:
        d = ra - venous_ref
        if d >= thr_atrial:
            candidates.append(("SVC → RA", d, "atrial"))

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
    """dict for str.format_map that returns an empty string for missing keys.

    The empty-string fallback is intentional for templates with conditional
    placeholders (e.g. ``{cv_stauung_phrase}`` may legitimately be empty when
    the underlying parameter is not assessable). However, missing keys are
    *also* a common source of silent typos in template strings — so every
    miss is logged so QA can spot patterns over time. Logging is best-effort
    and never raises, to keep the original behaviour fully backwards-compatible.
    """

    # Module-level set so we only log each unknown key once per process —
    # otherwise a single bad template fires on every render and floods logs.
    _seen_missing: "set[str]" = set()

    def __missing__(self, key: str) -> str:
        seen = SafeDict._seen_missing
        if key not in seen:
            seen.add(key)
            try:
                # Late import: rhk_logging may import from rhk_base, so we
                # cannot import at module top.
                from rhk_logging import log_warning
                log_warning(
                    "RHK_BASE_TEMPLATE_MISSING_KEY",
                    "Template placeholder missing in render context.",
                    key=key,
                )
            except Exception:  # noqa: BLE001 — must not break formatting
                pass
        return ""


class StrictDict(dict):
    """Variant of SafeDict that raises on missing keys.

    Use in tests / CI to surface template typos that production silently
    swallows. Production paths should keep using SafeDict because some
    placeholders are legitimately empty.
    """

    def __missing__(self, key: str) -> str:
        raise KeyError(
            f"Template placeholder {key!r} not present in render context. "
            "If this key is genuinely conditional, supply it as an empty "
            "string explicitly; do not rely on silent fallback."
        )


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
        import rhk_textdb

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

    except (ImportError, KeyError, TypeError, AttributeError) as exc:
        log_exception("RHK_BASE_TEXTDB", "Failed to load text blocks from rhk_textdb.", exc)
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
    except (KeyError, ValueError, IndexError) as e:
        log_exception("RHK_BASE_RENDER_BLOCK", f"Template error in {block.id}.", e)
        return f"[Template-Fehler in {block.id}: {e}]"


# =============================================================================
# Declarative Rule Engine
# =============================================================================

@dataclass
class WarningItem:
    code: str
    severity: str  # "info" | "warn" | "error"
    triage: str  # "hint" | "important" | "critical"
    category: str  # e.g. "measurement_quality" | "safety_interaction" | "plausibility"
    message: str
    suggestion: str = ""
    fields: List[str] = field(default_factory=list)
    values: Dict[str, Any] = field(default_factory=dict)


def collect_plausibility_warnings(ui: Dict[str, Any], derived: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sammelt Plausibilitätswarnungen für Eingaben und abgeleitete Werte.

    Prinzipien:
    - **Kein Hard-Fail**: Warnungen blockieren die Befunderstellung nicht.
    - **Konservativ**: Nur klare Ausreißer/Inkonsistenzen markieren.
    - **Backwards compatible**: Fehlende Felder führen höchstens zu 'info'-Hinweisen.

    Rückgabe:
    - Liste aus dicts (JSON-freundlich): {code, severity, message, fields, values}
    """
    items: List[WarningItem] = []

    def triage_from_severity(sev: str) -> str:
        s = str(sev or "").strip().lower()
        if s == "error":
            return "critical"
        if s == "warn":
            return "important"
        return "hint"

    def add(
        code: str,
        severity: str,
        message: str,
        fields: Optional[List[str]] = None,
        values: Optional[Dict[str, Any]] = None,
        *,
        triage: Optional[str] = None,
        category: str = "plausibility",
        suggestion: str = "",
    ) -> None:
        t = str(triage or triage_from_severity(severity)).strip().lower()
        if t not in {"hint", "important", "critical"}:
            t = triage_from_severity(severity)
        items.append(WarningItem(
            code=str(code),
            severity=str(severity),
            triage=t,
            category=str(category or "plausibility"),
            message=str(message),
            suggestion=str(suggestion or "").strip(),
            fields=list(fields or []),
            values=dict(values or {}),
        ))

    # Human-readable labels for field names used in plausibility messages
    _FIELD_LABELS: Dict[str, tuple] = {
        # (display name, unit)
        "age": ("Alter", "Jahre"),
        "height_cm": ("Körpergröße", "cm"),
        "weight_kg": ("Gewicht", "kg"),
        "bp_sys": ("RR systolisch", "mmHg"),
        "bp_dia": ("RR diastolisch", "mmHg"),
        "hr": ("Herzfrequenz", "bpm"),
        "spap_rest": ("sPAP (Ruhe)", "mmHg"),
        "dpap_rest": ("dPAP (Ruhe)", "mmHg"),
        "mpap_rest": ("mPAP (Ruhe)", "mmHg"),
        "pawp_rest": ("PAWP (Ruhe)", "mmHg"),
        "rap_rest": ("RAP (Ruhe)", "mmHg"),
        "co_rest": ("CO (Ruhe)", "l/min"),
        "ci_rest": ("CI (Ruhe)", "l/min/m²"),
        "pvr_rest": ("PVR (Ruhe)", "WU"),
        "spap_peak": ("sPAP (Belastung)", "mmHg"),
        "dpap_peak": ("dPAP (Belastung)", "mmHg"),
        "mpap_peak": ("mPAP (Belastung)", "mmHg"),
        "pawp_peak": ("PAWP (Belastung)", "mmHg"),
        "co_peak": ("CO (Belastung)", "l/min"),
        "ci_peak": ("CI (Belastung)", "l/min/m²"),
        "hb_g_dl": ("Hämoglobin", "g/dl"),
        "bnp_value": ("BNP/NT-proBNP", ""),
        "lvef": ("LVEF", "%"),
        "tapse_mm": ("TAPSE", "mm"),
    }

    def rng(
        name: str,
        val: Optional[float],
        lo: float,
        hi: float,
        severity: str = "warn",
        *,
        category: str = "measurement_quality",
        suggestion: str = "",
    ) -> None:
        if val is None:
            return
        if val < lo or val > hi:
            label, unit = _FIELD_LABELS.get(name, (name, ""))
            val_str = f"{val:g}"
            unit_str = f" {unit}" if unit else ""
            direction = "ungewöhnlich hoch" if val > hi else "ungewöhnlich niedrig"
            add(
                code=f"range_{name}",
                severity=severity,
                message=f"{label} von {val_str}{unit_str} ist {direction} (plausibler Bereich: {lo}–{hi}) — bitte Messwert prüfen.",
                fields=[name],
                values={name: val},
                category=category,
                suggestion=suggestion or f"Wert für {label} und Einheit gegen Originaldokument prüfen.",
            )

    def _med_tokens() -> List[str]:
        vals: List[str] = []
        for src in (
            derived.get("ph_current_meds"),
            derived.get("ph_new_meds"),
            ui.get("ph_current_meds"),
            ui.get("ph_new_meds"),
        ):
            vals.extend([str(x).strip().lower() for x in _as_list(src) if str(x).strip()])

        episodes = derived.get("ph_tx_episodes")
        if isinstance(episodes, list):
            for ep in episodes:
                if not isinstance(ep, dict):
                    continue
                st = str(ep.get("status") or "").strip().lower()
                if st not in {"aktuell", "geplant", "pausiert", "unklar", ""}:
                    continue
                drug = str(ep.get("drug") or "").strip().lower()
                if drug:
                    vals.append(drug)
        return vals

    # --- Demografie / Vitalparameter ---
    rng("age", _safe_float(ui.get("age")), 0, 110, severity="warn")
    rng("height_cm", _safe_float(ui.get("height_cm")), 120, 220, severity="warn")
    rng("weight_kg", _safe_float(ui.get("weight_kg")), 30, 250, severity="warn")
    rng("bp_sys", _safe_float(ui.get("bp_sys")), 70, 240, severity="warn")
    rng("bp_dia", _safe_float(ui.get("bp_dia")), 30, 150, severity="warn")
    rng("hr", _safe_float(ui.get("hr")), 30, 220, severity="warn")

    # --- RHK Ruhe Hämodynamik ---
    spap = _safe_float(ui.get("spap_rest"))
    dpap = _safe_float(ui.get("dpap_rest"))
    mpap_in = _safe_float(ui.get("mpap_rest"))
    mpap_calc = _safe_float(derived.get("mpap_calc"))
    mpap = _safe_float(derived.get("mpap_rest"))
    pawp = _safe_float(ui.get("pawp_rest"))
    rap = _safe_float(ui.get("rap_rest"))
    co = _safe_float(derived.get("co_rest"))
    ci = _safe_float(derived.get("ci_rest"))
    pvr = _safe_float(derived.get("pvr_rest"))
    bsa = _safe_float(derived.get("bsa_m2"))
    pawp_pre = _safe_float(ui.get("pawp_pre"))
    pawp_post = _safe_float(ui.get("pawp_post"))

    rng("spap_rest", spap, 5, 140, severity="warn")
    rng("dpap_rest", dpap, 0, 80, severity="warn")
    rng("mpap_rest", mpap, 0, 100, severity="warn")
    rng("pawp_rest", pawp, 0, 40, severity="warn")
    rng("rap_rest", rap, 0, 30, severity="warn")
    rng("co_rest", co, 1, 15, severity="warn")
    rng("ci_rest", ci, 1, 8, severity="warn")
    rng("pvr_rest", pvr, 0, 30, severity="warn")

    # Inkonsistenzen
    if spap is not None and dpap is not None and dpap > spap:
        add(
            code="hemo_spap_dpap_order",
            severity="error",
            message="sPAP ist kleiner als dPAP. Bitte Werte prüfen (Reihenfolge/Einheit).",
            fields=["spap_rest", "dpap_rest"],
            values={"spap_rest": spap, "dpap_rest": dpap},
            category="measurement_quality",
            suggestion="dPAP und sPAP im Originalbefund gegenprüfen (möglicher Zahlendreher/Vertauschung).",
        )

    if spap is not None and mpap is not None and mpap > spap:
        add(
            code="hemo_mpap_gt_spap",
            severity="error",
            message="mPAP ist größer als sPAP. Bitte Werte prüfen (sPAP ≥ mPAP erwartet).",
            fields=["mpap_rest", "spap_rest"],
            values={"mpap_rest": mpap, "spap_rest": spap},
            category="measurement_quality",
            suggestion="sPAP/mPAP prüfen; bei Übertragungsfehler typischerweise mPAP korrigieren.",
        )

    if mpap is not None and dpap is not None and dpap > mpap:
        add(
            code="hemo_dpap_gt_mpap",
            severity="error",
            message="dPAP ist größer als mPAP. Bitte Werte prüfen (mPAP ≥ dPAP erwartet).",
            fields=["dpap_rest", "mpap_rest"],
            values={"dpap_rest": dpap, "mpap_rest": mpap},
            category="measurement_quality",
            suggestion="dPAP/mPAP auf Zahlendreher prüfen, ggf. Mittelwert neu berechnen.",
        )

    if mpap_in is not None and mpap_calc is not None:
        try:
            diff = abs(float(mpap_in) - float(mpap_calc))
            if diff >= 7:
                add(
                    code="hemo_mpap_mismatch",
                    severity="warn",
                    message="Eingegebener mPAP weicht deutlich vom aus sPAP/dPAP berechneten mPAP ab. Bitte prüfen.",
                    fields=["mpap_rest", "spap_rest", "dpap_rest"],
                    values={"mpap_rest": mpap_in, "mpap_calc": mpap_calc},
                    category="measurement_quality",
                    suggestion="mPAP aus sPAP/dPAP gegenrechnen und Eingabe auf Vertauschung prüfen.",
                )
        except (ValueError, TypeError) as exc:
            log_exception("RHK_BASE_PLAUSIBILITY", "mPAP mismatch check failed.", exc)

    if mpap is not None and pawp is not None and pawp > mpap:
        add(
            code="hemo_pawp_gt_mpap",
            severity="warn",
            message="PAWP ist größer als mPAP. Das ist ungewöhnlich und sollte geprüft werden.",
            fields=["pawp_rest", "mpap_rest"],
            values={"pawp_rest": pawp, "mpap_rest": mpap},
            category="measurement_quality",
            suggestion="Wedge-Lage, Nullabgleich und Atemlage prüfen; Messung ggf. wiederholen.",
        )

    # PVR aus Eingabe vs. berechnet (falls beides vorhanden)
    pvr_in = _safe_float(ui.get("pvr_rest"))
    pvr_calc = _safe_float(derived.get("pvr_calc"))
    if pvr_in is not None and pvr_calc is not None:
        try:
            diff = abs(float(pvr_in) - float(pvr_calc))
            if diff >= 1.5:
                add(
                    code="hemo_pvr_mismatch",
                    severity="warn",
                    message="Eingegebene PVR weicht deutlich von der aus mPAP/PAWP/CO berechneten PVR ab. Bitte prüfen.",
                    fields=["pvr_rest", "mpap_rest", "pawp_rest", "co_rest"],
                    values={"pvr_rest": pvr_in, "pvr_calc": pvr_calc},
                    category="measurement_quality",
                    suggestion="CO-Einheit und Druckwerte prüfen; PVR erneut berechnen.",
                )
        except (ValueError, TypeError) as exc:
            log_exception("RHK_BASE_PLAUSIBILITY", "PVR mismatch check failed.", exc)

    # CO / CI / BSA-Konsistenz
    if co is not None and co >= 35:
        add(
            code="hemo_co_unit_ml_min",
            severity="error",
            message="CO ist extrem hoch. Möglicherweise wurde ml/min statt L/min eingegeben.",
            fields=["co_rest"],
            values={"co_rest": co},
            category="measurement_quality",
            suggestion="Einheit prüfen (falls ml/min: durch 1000 teilen).",
        )
    elif co is not None and co > 20:
        add(
            code="hemo_co_very_high",
            severity="warn",
            message="CO ist ungewöhnlich hoch. Einheit und Dezimaltrennzeichen prüfen.",
            fields=["co_rest"],
            values={"co_rest": co},
            category="measurement_quality",
            suggestion="CO auf ml/min-Eingabe oder Dezimalfehler prüfen.",
        )
    elif co is not None and co < 1:
        add(
            code="hemo_co_very_low",
            severity="warn",
            message="CO ist ungewöhnlich niedrig. Einheit oder Dezimaltrennzeichen prüfen.",
            fields=["co_rest"],
            values={"co_rest": co},
            category="measurement_quality",
            suggestion="CO-Eingabe und Einheit mit Rohbefund abgleichen.",
        )

    if ci is not None and ci >= 12:
        add(
            code="hemo_ci_unit_suspect",
            severity="error",
            message="CI ist extrem hoch. Einheit oder Dezimaltrennzeichen wahrscheinlich fehlerhaft.",
            fields=["ci_rest"],
            values={"ci_rest": ci},
            category="measurement_quality",
            suggestion="CI und BSA gegenrechnen, Eingabeformat prüfen.",
        )

    if co is not None and ci is not None and bsa is not None and bsa > 0:
        try:
            ci_calc = float(co) / float(bsa)
            diff_ci = abs(float(ci) - ci_calc)
            if diff_ci >= 0.7:
                add(
                    code="hemo_co_ci_bsa_mismatch",
                    severity="warn",
                    message="CO/CI sind im Verhältnis zur BSA inkonsistent.",
                    fields=["co_rest", "ci_rest", "height_cm", "weight_kg"],
                    values={"co_rest": co, "ci_rest": ci, "bsa_m2": bsa, "ci_calc": ci_calc},
                    category="measurement_quality",
                    suggestion="Körpergröße/Gewicht prüfen und CI aus CO/BSA neu plausibilisieren.",
                )
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            log_exception("RHK_BASE_PLAUSIBILITY", "CO/CI/BSA consistency check failed.", exc)

    # PAWP im Kontext / Volumenchallenge
    if (pawp_pre is None) ^ (pawp_post is None):
        add(
            code="vol_challenge_incomplete",
            severity="info",
            message="Volumenchallenge unvollständig dokumentiert (PAWP pre/post fehlt).",
            fields=["pawp_pre", "pawp_post"],
            values={"pawp_pre": pawp_pre, "pawp_post": pawp_post},
            category="measurement_quality",
            suggestion="Für die Einordnung beide Werte (pre und post) dokumentieren.",
        )

    if pawp_pre is not None and pawp_post is not None:
        d_pawp = pawp_post - pawp_pre
        if d_pawp < -3:
            add(
                code="vol_challenge_pawp_drop",
                severity="warn",
                message="PAWP fällt nach Volumenchallenge deutlich ab. Messbedingungen prüfen.",
                fields=["pawp_pre", "pawp_post"],
                values={"pawp_pre": pawp_pre, "pawp_post": pawp_post, "delta_pawp": d_pawp},
                category="measurement_quality",
                suggestion="Wedge-Position/Nullpunkt kontrollieren und Messung ggf. wiederholen.",
            )
        if d_pawp > 15:
            add(
                code="vol_challenge_pawp_large_jump",
                severity="warn",
                message="Sehr großer PAWP-Anstieg nach Volumenchallenge. Plausibilität prüfen.",
                fields=["pawp_pre", "pawp_post"],
                values={"pawp_pre": pawp_pre, "pawp_post": pawp_post, "delta_pawp": d_pawp},
                category="measurement_quality",
                suggestion="Volumenprotokoll und Messzeitpunkte prüfen.",
            )
        if pawp is not None and pawp <= 15 and pawp_post >= 18:
            add(
                code="vol_challenge_occult_lhd_pattern",
                severity="warn",
                message="PAWP in Ruhe unauffällig, nach Volumenchallenge jedoch ≥18 mmHg.",
                fields=["pawp_rest", "pawp_pre", "pawp_post"],
                values={"pawp_rest": pawp, "pawp_pre": pawp_pre, "pawp_post": pawp_post},
                category="clinical_context",
                suggestion="Okkulte linksatriale Druckkomponente/HFpEF im Befundtext explizit einordnen.",
            )

    # --- Sättigungen ---
    for k in ("sat_svc", "sat_ivc", "sat_ra", "sat_rv", "sat_pa", "sat_ao"):
        v = _safe_float(ui.get(k))
        if v is None:
            continue
        if v < 0 or v > 100:
            add(
                code=f"range_{k}",
                severity="error",
                message=f"{k} liegt außerhalb 0–100%. Bitte prüfen.",
                fields=[k],
                values={k: v},
                category="measurement_quality",
                suggestion="Sättigungswert und Probennamen prüfen.",
            )

    sat_chain = [("sat_svc", "SVC"), ("sat_ra", "RA"), ("sat_rv", "RV"), ("sat_pa", "PA")]
    sat_vals: Dict[str, float] = {}
    for sk, _ in sat_chain:
        sv = _safe_float(ui.get(sk))
        if sv is not None:
            sat_vals[sk] = sv
    step_like = False
    for i in range(len(sat_chain) - 1):
        k_from, lbl_from = sat_chain[i]
        k_to, lbl_to = sat_chain[i + 1]
        if k_from not in sat_vals or k_to not in sat_vals:
            continue
        d_sat = sat_vals[k_to] - sat_vals[k_from]
        if d_sat >= 8:
            step_like = True
        if abs(d_sat) >= 18:
            add(
                code=f"sat_extreme_jump_{k_from}_{k_to}",
                severity="warn",
                message=f"Unplausibler Sättigungssprung {lbl_from}→{lbl_to} (Δ≈{_fmt(d_sat,1)}%).",
                fields=[k_from, k_to],
                values={k_from: sat_vals[k_from], k_to: sat_vals[k_to], "delta_pct": d_sat},
                category="measurement_quality",
                suggestion="Probenzuordnung und Reihenfolge der Entnahmen prüfen.",
            )
    step_flag = bool(derived.get("step_up_present"))
    if step_like and not step_flag:
        add(
            code="sat_stepup_logic_mismatch",
            severity="info",
            message="Numerischer Step-up erkennbar, aber kein Step-up-Flag gesetzt.",
            fields=[k for k in ("sat_svc", "sat_ra", "sat_rv", "sat_pa") if _safe_float(ui.get(k)) is not None],
            values={"step_up_present": step_flag},
            category="measurement_quality",
            suggestion="Step-up-Interpretation klinisch gegenprüfen.",
        )
    elif step_flag and not step_like:
        add(
            code="sat_stepup_flag_without_jump",
            severity="info",
            message="Step-up-Flag gesetzt, aber kein klarer numerischer Sprung in den Rohwerten.",
            fields=[k for k in ("sat_svc", "sat_ra", "sat_rv", "sat_pa") if _safe_float(ui.get(k)) is not None],
            values={"step_up_present": step_flag},
            category="measurement_quality",
            suggestion="Sättigungswerte auf Vollständigkeit und Reihenfolge prüfen.",
        )

    sat_pa = _safe_float(ui.get("sat_pa"))
    sat_ao = _safe_float(ui.get("sat_ao"))
    if sat_ao is not None:
        for sat_key, sat_label in (("sat_svc", "SVC"), ("sat_ra", "RA"), ("sat_rv", "RV")):
            sat_val = _safe_float(ui.get(sat_key))
            if sat_val is None:
                continue
            if sat_val > sat_ao + 3:
                add(
                    code=f"sat_venous_gt_ao_{sat_key}",
                    severity="warn",
                    message=f"{sat_label}-Sättigung liegt über der arteriellen Sättigung. Wertezuordnung prüfen.",
                    fields=[sat_key, "sat_ao"],
                    values={sat_key: sat_val, "sat_ao": sat_ao},
                    category="measurement_quality",
                    suggestion="Probenetikett und Blutgasquelle (arteriell/venös) gegeneinander prüfen.",
                )
    if sat_pa is not None and sat_ao is not None and sat_pa > sat_ao + 5:
        add(
            code="sat_pa_gt_ao",
            severity="warn",
            message="PA-Sättigung liegt deutlich über der systemischen Sättigung. Wertezuordnung prüfen.",
            fields=["sat_pa", "sat_ao"],
            values={"sat_pa": sat_pa, "sat_ao": sat_ao},
            category="measurement_quality",
            suggestion="Probeetiketten und Blutgasquelle (arteriell vs. venös) prüfen.",
        )

    # --- Echo (nur grob) ---
    rng("lvef", _safe_float_echo(ui.get("lvef")), 10, 80, severity="warn")
    rng("tapse_mm", _safe_float_echo(ui.get("tapse_mm")), 5, 30, severity="warn")
    rng("s_prime_cm_s", _safe_float_echo(ui.get("s_prime_cm_s")), 3, 25, severity="warn")
    rng("pasp_echo", _safe_float_echo(ui.get("pasp_echo")), 10, 120, severity="warn")
    rng("trv_ms", _safe_float_echo(ui.get("trv_ms")), 1.0, 6.0, severity="warn")
    rng("ra_esa_cm2", _safe_float_echo(ui.get("ra_esa_cm2")), 5, 40, severity="warn")
    rng("ee_ratio", _safe_float_echo(ui.get("ee_ratio")), 1, 30, severity="warn")

    # Interpretations-Hinweise (konservativ)
    if _safe_float_echo(ui.get("pasp_echo")) is not None and _safe_float_echo(ui.get("trv_ms")) is None:
        add(
            code="echo_pasp_without_trv",
            severity="info",
            message="sPAP (Echo) ist angegeben, TRV jedoch nicht. Die Einordnung im Echo kann dadurch eingeschränkt sein.",
            fields=["pasp_echo", "trv_ms"],
            values={"pasp_echo": _safe_float_echo(ui.get('pasp_echo'))},
            category="clinical_context",
            suggestion="Wenn möglich TRV ergänzen oder Echoeinschränkung im Bericht explizit dokumentieren.",
        )

    # --- Interaktions- / Kontraindikations-Sicherheitsnetz ---
    meds = _med_tokens()
    has_pde5 = any(("pde-5" in m) or ("sildenafil" in m) or ("tadalafil" in m) for m in meds)
    has_sgc = any(("sgc" in m) or ("riociguat" in m) or ("adempas" in m) for m in meds)
    on_nitrates = bool(ui.get("on_nitrates"))
    hardship = bool(ui.get("pde5_hardship"))
    hardship_desc = str(ui.get("pde5_hardship_desc") or "").strip()

    if on_nitrates and (has_pde5 or has_sgc):
        add(
            code="safety_nitrate_interaction",
            severity="error",
            message="Kontraindikation: Nitrate/NO-Donor zusammen mit PDE-5-Hemmer oder Riociguat.",
            fields=["on_nitrates", "ph_tx_table", "ph_current_meds", "ph_new_meds"],
            values={"on_nitrates": on_nitrates},
            category="safety_interaction",
            suggestion="Medikation sofort prüfen; Kombination vermeiden und Sicherheitsbegründung dokumentieren.",
        )

    if has_pde5 and has_sgc:
        add(
            code="safety_pde5_sgc_combo",
            severity="error",
            message="Kontraindikation: PDE-5-Hemmer und sGC-Stimulator (Riociguat) gleichzeitig erfasst.",
            fields=["ph_tx_table", "ph_current_meds", "ph_new_meds"],
            values={},
            category="safety_interaction",
            suggestion="Therapieplan auf Doppelblockade prüfen und eindeutig korrigieren.",
        )

    if hardship and not hardship_desc:
        add(
            code="safety_hardship_missing_reason",
            severity="warn",
            message="Härtefall aktiviert, aber Begründung fehlt.",
            fields=["pde5_hardship", "pde5_hardship_desc"],
            values={"pde5_hardship": hardship},
            category="safety_interaction",
            suggestion="Off-Label/Härtefall kurz und nachvollziehbar dokumentieren.",
        )
    elif hardship and hardship_desc:
        add(
            code="safety_hardship_documented",
            severity="info",
            message="Härtefall-Dokumentation erfasst.",
            fields=["pde5_hardship", "pde5_hardship_desc"],
            values={"pde5_hardship": hardship},
            category="safety_interaction",
            suggestion="Text für Bericht/Verlauf übernehmen.",
        )

    # Serialisieren als dicts
    # --- PVOD/PCH Red Flags (subtiler Reminder; keine Diagnose) ---
    try:
        lvl = _safe_float(derived.get("pvod_hint_level"))
        desc = str(derived.get("pvod_hint_desc") or "").strip()
        if lvl is not None and lvl >= 1 and desc:
            sev = "info" if float(lvl) < 3 else "warn"
            add(
                code="pvod_redflags",
                severity=sev,
                message="PVOD/PCH Red Flags erfasst. DD beachten (Hover: Details).",
                fields=[
                    "dlco_sb",
                    "fvc_l",
                    "ct_pvod_gg",
                    "ct_pvod_septal",
                    "ct_pvod_ln",
                    "pvod_dlco_disproportionate",
                    "pvod_rest_hypoxemia",
                    "pvod_ex_desat",
                    "pvod_edema_on_vaso",
                    "eif2ak4_result",
                ],
                values={"pvod_hint_level": int(lvl), "pvod_hint_desc": desc},
                category="clinical_context",
                suggestion="PVOD/PCH differenzialdiagnostisch in Therapieentscheidung einbeziehen.",
            )
    except (ValueError, TypeError, KeyError) as exc:
        log_exception("RHK_BASE_PVOD_FLAGS", "PVOD/PCH red flag evaluation failed.", exc)

    return [asdict(i) for i in items]


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
    """Normalisiert UI-Auswahl der Zusatzmodule auf reine IDs (P01–P30).

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

_ALL_P_MODULE_IDS: List[str] = [f"P{i:02d}" for i in range(1, 53)]


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
        except (ValueError, TypeError, KeyError) as exc:
            log_exception("RHK_BASE_MODULE_POLICY", "Failed to parse candidate group.", exc)
            continue
        try:
            sc = int(c.get("score") or 0)
        except (ValueError, TypeError) as exc:
            log_exception("RHK_BASE_MODULE_POLICY", "Failed to parse candidate score.", exc)
            sc = 0
        score_by_group[g] = max(score_by_group.get(g, 0), sc)

    g1 = score_by_group.get(1, 0)
    g2 = score_by_group.get(2, 0)
    g3 = score_by_group.get(3, 0)
    g4 = score_by_group.get(4, 0)

    _b = parse_boolish

    clear_leader = _b(eti.get("clear_leader"))
    leading_group = eti.get("leading_group")

    hemo_cat = str(derived.get("hemo_category") or "unknown")

    # --------- Disable-Logik (konservativ, aber nützlich) ----------
    disabled: Dict[str, str] = {}

    # -----------------------------------------------------------------
    # Volumen-/Stauungs-Module (P02, P26) nur bei plausibler Stauung
    # -----------------------------------------------------------------
    # Ziel: Wenn im Beurteilungs-/Ätiologie-Modul explizit "keine Hinweise auf Kongestion"
    # ausgegeben werden, sollen Diurese/Trinkmengenrestriktion nicht gleichzeitig im Procedere
    # als auswählbare Standardmodule erscheinen.
    congestion_likely = _b(derived.get("congestion_likely"))
    pawp = _safe_float(ui.get("pawp_rest"))
    pv_stauung_likely = bool(pawp is not None and pawp > 15)

    if not congestion_likely and not pv_stauung_likely:
        disabled["P02"] = "Nicht passend: Keine Hinweise auf zentrale/pulmonalvenöse Stauung in den vorliegenden Angaben."
        disabled["P26"] = "Nicht passend: Keine Hinweise auf Volumenüberladung/Stauung in den vorliegenden Angaben."

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
    ct_ild = _b(ui.get("ct_ild"))
    lufu_restr = _b(ui.get("lufu_restrictive"))
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
        if not _b(ui.get("atrial_fib")) and not _b(ui.get("vq_defect")) and not _b(ui.get("ct_embolie")):
            disabled["P10"] = (
                "Kein Hinweis auf eine Antikoagulationsindikation dokumentiert, "
                "kein Vorhofflimmern und kein Emboliehinweis."
            )

    # P12 Lungenfunktionelle Abklärung Restriktion oder DLCO
    # - deaktivieren, wenn Lufu als unauffällig markiert ist
    if _b(ui.get("lufu_done")) and not _b(ui.get("lufu_obstructive")) and not _b(ui.get("lufu_restrictive")) and not _b(ui.get("lufu_diffusion")):
        disabled["P12"] = (
            "Lungenfunktion als unauffällig markiert, keine Obstruktion, keine Restriktion und keine Diffusionsstörung dokumentiert."
        )

    # P15 Belastungsdiagnostik
    # - deaktivieren, wenn bereits durchgeführt
    if _b(ui.get("exercise_done")):
        disabled["P15"] = "Belastungsdiagnostik ist bereits dokumentiert."

    # P09 Kardiologische Mitbeurteilung
    # - deaktivieren, wenn keine Hinweise auf kardiale Mitursachen dokumentiert sind
    lvef = _safe_float(ui.get("lvef"))
    if (lvef is not None and lvef >= 55.0) and (not _b(ui.get("atrial_fib"))) and (not _b(ui.get("ct_koronarkalk"))):
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
    if (not _b(ui.get("immunology_pos"))) and (leading_group != 1) and (g1 < 2):
        disabled["P17"] = "Kein Hinweis auf Autoimmunerkrankung dokumentiert und die Konstellation spricht nicht primär für PAH."

    # P18 Infektiologisches Screening
    # - deaktivieren, wenn keine Hinweise dokumentiert sind und keine PAH Konstellation vorliegt
    if (not _b(ui.get("virology_pos"))) and (leading_group != 1) and (g1 < 2):
        disabled["P18"] = "Kein Hinweis auf relevante infektiologische Auslöser dokumentiert und die Konstellation spricht nicht primär für PAH."

    # P19 Portopulmonale PH Abklärung
    # - deaktivieren, wenn Abdomensonographie ohne Hinweis auf Lebererkrankung dokumentiert ist
    if _b(ui.get("abd_sono_done")):
        abd_desc = str(ui.get("abd_sono_desc") or "").strip().lower()
        if abd_desc and any(w in abd_desc for w in ("unauffällig", "normal", "kein hinweis")):
            disabled["P19"] = "Abdomensonographie ohne Hinweis auf Leberzirrhose oder portale Hypertension dokumentiert."

    # P20 Genetik
    # - deaktivieren, wenn keine Hinweise dokumentiert sind und PAH nicht im Vordergrund steht
    if (not _b(ui.get("mutation_pos"))) and (leading_group != 1) and (g1 < 2) and (age is None or age >= 50):
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
    except (TypeError, AttributeError) as exc:
        log_exception("RHK_BASE_MODULE_POLICY", "Failed to read decision modules.", exc)
        auto_mods = []
    for mid in auto_mods:
        if mid in levels and mid not in disabled:
            levels[mid] = 1

    # Heuristiken
    if _b(derived.get("congestion_likely")) and "P02" not in disabled:
        levels["P02"] = 1
    # Trinkmengenrestriktion / Volumenmanagement (neu: P26)
    # Priorität hoch bei Stauung oder erhöhtem RAP
    if (_b(derived.get("congestion_likely")) or (rap_val is not None and rap_val >= 10.0)) and "P26" not in disabled:
        levels["P26"] = 1

    if _b(derived.get("anemia")) and "P13" not in disabled:
        levels["P13"] = 1

    # CTEPH-typische Konstellation
    if g4 >= 2 or _b(ui.get("vq_defect")) or _b(ui.get("ct_embolie")) or _b(ui.get("ct_mosaic")):
        if "P10" not in disabled:
            levels["P10"] = 1
        if "P05" not in disabled:
            levels["P05"] = min(levels.get("P05", 3), 1)

    # Lungen-/ILD-typische Konstellation
    if g3 >= 2 or _b(ui.get("ild")) or _b(ui.get("ct_ild")) or _b(ui.get("ct_emphysema")):
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
    # Kardiovaskuläre Risikofaktoren (neu: P27) – grundsätzlich sinnvoll, höher priorisieren bei Atherosklerose-Hinweisen
    if "P27" in levels and "P27" not in disabled:
        levels["P27"] = min(levels.get("P27", 3), 2)
        if _b(ui.get("ct_koronarkalk")):
            levels["P27"] = 1

    # Gewichtsreduktion (neu: P28) – priorisieren bei Adipositas
    bmi_val = _safe_float(derived.get("bmi"))
    if bmi_val is not None and "P28" in levels and "P28" not in disabled:
        if bmi_val >= 30.0:
            levels["P28"] = 1
        elif bmi_val >= 27.0:
            levels["P28"] = min(levels.get("P28", 3), 2)

    # LTOT konsequent anwenden (neu: P29)
    ltot_flag = _b(ui.get("ltot"))
    ltot_flow = _safe_float(ui.get("ltot_flow_l_min"))
    if (ltot_flag or (ltot_flow is not None and ltot_flow > 0)) and "P29" in levels and "P29" not in disabled:
        levels["P29"] = 1

    # CT-Befunde interdisziplinär besprechen (neu: P30)
    # Priorität hoch, wenn CT als durchgeführt markiert ist, aber Kurzbefund fehlt bzw. als ausstehend dokumentiert ist.
    ct_done = _b(ui.get("ct_done"))
    ct_desc = str(ui.get("ct_desc") or "").strip()
    ct_desc_l = ct_desc.lower()
    if ct_done and "P30" in levels and "P30" not in disabled:
        if (not ct_desc) or any(w in ct_desc_l for w in ("ausstehend", "pending", "noch nicht", "befund folgt")):
            levels["P30"] = 1
        else:
            levels["P30"] = min(levels.get("P30", 3), 2)

    # RV/RA-Marker auffällig → Verlauf/Stratifizierung strukturieren
    if _b(derived.get("tapse_spap_reduced")) or _b(derived.get("s_prime_raai_low")):
        if "P14" not in disabled:
            levels["P14"] = min(levels.get("P14", 3), 2)

    # Hochrisiko → eskalationsnahe Themen hoch priorisieren
    esc4 = str(derived.get("esc_ers_4s") or derived.get("esc_ers_4strata") or "").strip().lower()
    if esc4 in ("high", "intermediate-high"):
        for mid in ("P06", "P25"):
            if mid in levels and mid not in disabled:
                levels[mid] = 1
    elif esc4 in ("intermediate", "intermediate-low"):
        if "P25" not in disabled:
            levels["P25"] = min(levels.get("P25", 3), 2)

    # Zusätzliche Trigger (NEU: Mutation/Virologie/Immunologie/CHD)
    if _b(ui.get("mutation_pos")) and "P20" not in disabled:
        levels["P20"] = 1
    if _b(ui.get("virology_pos")) and "P18" not in disabled:
        levels["P18"] = 1
    if _b(ui.get("immunology_pos")) and "P17" not in disabled:
        levels["P17"] = 1
    if _b(ui.get("chd_pos")) and "P01" not in disabled:
        levels["P01"] = min(levels.get("P01", 3), 1)

    # Generell sinnvolle Basismodule (wenn nicht anders priorisiert)
    for mid in ("P11", "P23", "P27"):
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
        # Fallback: einfach P01..P30
        choices: List[Tuple[str, str]] = []
        for mid in _ALL_P_MODULE_IDS:
            if mid in blocks:
                choices.append((f"{mid} – {blocks[mid].title}", mid))
        return choices

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



# ---------------------------------------------------------------------
# P-Modules helpers (Single Source of Truth: case['ui']['modules'])
# ---------------------------------------------------------------------
def pmods_get_force_optional(ui: Optional[Dict[str, Any]]) -> set:
    """Return a normalized set of module IDs that the user explicitly made optional again."""
    ui = ui or {}
    raw = ui.get("pmods_force_optional") or []
    if isinstance(raw, str):
        raw = [raw]
    out = set()
    for x in (raw or []):
        if x is None:
            continue
        s = str(x).strip()
        if not s:
            continue
        # accept 'P01 – title' etc.
        m = re.match(r"^(P\d{2})\b", s)
        out.add(m.group(1) if m else s)
    return out

def pmods_apply_overrides(policy: Optional[Dict[str, Any]], force_optional: set) -> Dict[str, Any]:
    """Apply user overrides: disabled modules become allowed again, but are NOT auto-selected."""
    policy = dict(policy or {})
    if not force_optional:
        return policy
    levels = dict(policy.get("levels") or {})
    allowed = list(policy.get("allowed") or [])
    disabled = dict(policy.get("disabled") or {})
    # remove from disabled and add to allowed (level-preserving order)
    for mid in list(force_optional):
        if mid in disabled:
            disabled.pop(mid, None)
        if mid not in allowed:
            allowed.append(mid)
    # stable sort allowed by (level, numeric id)
    def _key(mid: str):
        try:
            lvl = int(levels.get(mid, 3) or 3)
        except (ValueError, TypeError) as exc:
            log_exception("RHK_BASE_SORT_KEY", "Failed to parse module level.", exc)
            lvl = 3
        try:
            num = int(mid[1:]) if mid and mid[1:].isdigit() else 999
        except (ValueError, TypeError, IndexError) as exc:
            log_exception("RHK_BASE_SORT_KEY", "Failed to parse module number.", exc)
            num = 999
        return (lvl, num, mid)
    allowed = sorted(dict.fromkeys(allowed), key=_key)
    policy["allowed"] = allowed
    policy["disabled"] = disabled
    return policy

def _compare_rhk_trend(ui: Dict[str, Any], derived: Dict[str, Any]) -> Dict[str, Any]:
    """Vergleicht aktuelle RHK-Ruhe-Hämodynamik mit einem optionalen Vor-RHK.

    Liefert eine robuste Richtung (besser/stabil/schlechter/gemischt) inkl. kurzer Begründung
    und einer praxisnahen Konsequenzempfehlung. Kein Ersatz für klinische Beurteilung.
    """
    def _coerce_scalar_text(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, (list, tuple, set)):
            for item in v:
                s = _coerce_scalar_text(item)
                if s:
                    return s
            return ""
        if isinstance(v, dict):
            # Common import schemas: {"value": "..."} / {"label": "..."} etc.
            for k in ("value", "label", "name", "text", "date"):
                if k in v:
                    s = _coerce_scalar_text(v.get(k))
                    if s:
                        return s
            return ""
        try:
            return str(v).strip()
        except (ValueError, TypeError, AttributeError) as exc:
            log_exception("RHK_BASE_TREND", "Scalar text coercion failed.", exc)
            return ""

    prev_date = _coerce_scalar_text(ui.get("prev_rhk_date"))
    prev_is_initial = bool(ui.get("prev_is_initial"))
    prev_tx = ui.get("prev_tx_added") or []
    prev_tx_free = _coerce_scalar_text(ui.get("prev_tx_free"))

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
    if isinstance(prev_tx, str):
        s = prev_tx.strip()
        if s:
            tx_parts.append(s)
    elif isinstance(prev_tx, (list, tuple, set)):
        for x in prev_tx:
            s = _coerce_scalar_text(x)
            if s:
                tx_parts.append(s)
    if prev_tx_free:
        tx_parts.append(prev_tx_free)

    tx_txt = "; ".join(dict.fromkeys(tx_parts))  # dedup preserve order

    ctx_txt = "Initialkatheter" if prev_is_initial else "Voruntersuchung"
    under_txt = f" unter Therapieanpassung ({tx_txt})" if tx_txt else ""

    # Sätze
    # Doc sentence: keep the short trend, but make "gemischt" etc. clinically interpretable
    # by repeating the most relevant deltas (max 3) to avoid vague wording.
    delta_bits: List[str] = []
    for label, (pv, cv, c, unit, digits) in comps.items():
        if pv is None or cv is None:
            continue
        if c in ("better", "worse"):
            arr = arrow_map.get(c, "")
            pair = _fmt_pair(pv, cv, unit, digits)
            if pair:
                delta_bits.append(f"{label} {pair} {arr}".strip())
    delta_txt = "; ".join(delta_bits[:3])
    delta_suffix = f" ({delta_txt})" if delta_txt else ""

    sentence_doc = f"Verlauf im Vergleich zu RHK {prev_date} ({ctx_txt}){under_txt}: insgesamt **{trend}**{delta_suffix}."
    sentence_pat = f"Im Vergleich zu Ihrer früheren Herzkatheter-Untersuchung ({prev_date}) sind die Werte insgesamt **{trend}**."

    # Konsequenz (kurz + praxisnah)
    if trend == "besser":
        rec_doc = "Verlauf spricht für hämodynamisches Ansprechen – Fortführung/Optimierung der Therapie und Verlaufskontrolle gemäß Gesamtrisiko."
        rec_pat = "Das spricht dafür, dass die Behandlung wirkt. Wir besprechen die nächsten Schritte und die weitere Kontrolle."
    elif trend == "stabil":
        rec_doc = "Im Verlauf keine klare Änderung – Therapie/Komorbiditäten nach Gesamtschau weiter optimieren und klinisch/echo-basiert nachverfolgen."
        rec_pat = "Die Werte sind ähnlich. Entscheidend sind Beschwerden und Gesamtbild – wir schauen gemeinsam, ob Anpassungen sinnvoll sind."
    elif trend == "gemischt":
        rec_doc = "Gemischter Verlauf – einzelne Werte besser, andere unverändert/ungünstiger. Therapie und Begleitfaktoren (Volumenstatus, Lunge, linkes Herz) gezielt prüfen."
        rec_pat = "Einige Werte sind besser, andere eher unverändert. Wir prüfen gezielt, welche Faktoren das erklären und was man verbessern kann."
    else:  # schlechter
        rec_doc = "Hämodynamische Verschlechterung – zeitnahe Reevaluation (Therapieeskalation/Adhärenz/Komorbiditäten/Differenzialdiagnosen) erwägen."
        rec_pat = "Die Werte sind eher schlechter. Deshalb ist wichtig, dass wir die Behandlung zeitnah überprüfen und ggf. anpassen."

    # ------------------------------------------------------------------
    # Verlaufstypen (feiner als besser/stabil/gemischt) – nur Zusatzinfos
    # ------------------------------------------------------------------
    def _dir(param: str) -> str:
        try:
            return str(comps.get(param, (None, None, None, None, None))[2] or '')
        except (KeyError, TypeError, IndexError) as exc:
            log_exception("RHK_BASE_TREND", "Failed to extract direction from comparison.", exc)
            return ''

    d_mpap = _dir('mPAP')
    d_pvr = _dir('PVR')
    d_ci = _dir('CI')
    d_pawp = _dir('PAWP')
    _d_rap = _dir('RAP')  # noqa: F841 – reserved for future use

    subtype_id = ''
    subtype_pat = ''
    subtype_doc = ''

    if d_mpap == 'better' and d_pvr == 'worse':
        subtype_id = 'druck_besser_pvr_schlechter'
        subtype_pat = 'Der Druck ist im Verlauf niedriger, der Widerstand in den Lungengefäßen aber höher. Das kann bedeuten, dass sich einzelne Teile verbessern, andere aber noch im Vordergrund stehen. Entscheidend ist dann, ob sich Belastbarkeit und das rechte Herz gleichzeitig stabilisieren.'
        subtype_doc = 'mPAP verbessert, PVR verschlechtert – mögliche Verschiebung der Treiber (Volumenstatus, CO-Messmethode, Gefäßwiderstand) gezielt prüfen.'
    elif d_mpap == 'same' and d_pvr == 'worse':
        subtype_id = 'pvr_schlechter_druck_aehnlich'
        subtype_pat = 'Der Widerstand in den Lungengefäßen ist höher geworden, obwohl der Druck ähnlich blieb. Das kann passieren, wenn die Durchblutung oder die Gefäßspannung sich verändert. Wichtig ist dann die Gesamtschau mit Pumpleistung und Beschwerden.'
        subtype_doc = 'PVR verschlechtert bei stabilem mPAP – CO/VO2-Konsistenz, Messstreuung und klinischen Kontext prüfen.'
    elif d_ci == 'same' and (d_mpap == 'worse' or d_pvr == 'worse'):
        subtype_id = 'ci_stabil_haemodynamik_schlechter'
        subtype_pat = 'Die Pumpleistung ist ähnlich, aber einzelne Druck oder Widerstandswerte sind ungünstiger. Dann prüfen wir, ob Faktoren wie Flüssigkeitshaushalt, Lunge oder die linke Herzseite mit hineinspielen.'
        subtype_doc = 'CI stabil, Druck oder Widerstand ungünstiger – Trigger (Volumen, Komorbiditäten, Messstreuung) differenzieren.'
    elif d_pawp == 'worse' and d_pvr in ('same','better'):
        subtype_id = 'linker_druck_hoeher'
        subtype_pat = 'Der Druck vor der linken Herzhälfte ist höher geworden. Das kann zu mehr Rückstau in die Lunge beitragen. Dann ist oft die Behandlung des linken Herzens und die Flüssigkeitsbalance besonders wichtig.'
        subtype_doc = 'PAWP ansteigend – Volumenstatus, HFpEF/Linksherz und Diurese-Strategie prüfen.'
    elif trend == 'gemischt':
        subtype_id = 'therapieeffekt_unklar'
        subtype_pat = 'Ein gemischtes Bild ist nicht ungewöhnlich. Wir schauen dann darauf, welche Werte am aussagekräftigsten sind und wie es Ihnen im Alltag geht, bevor wir daraus Konsequenzen ableiten.'
        subtype_doc = 'Gemischter Verlauf – priorisiere klinisch führende Parameter und Kontext (Symptome, Echo, Biomarker).'


    # subtype patient hint is appended to the general recommendation
    if subtype_pat:
        rec_pat = (rec_pat + ' ' + subtype_pat).strip()



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
        "subtype_id": subtype_id,
        "subtype_patient": subtype_pat,
        "subtype_doc": subtype_doc,
    }




# ---------------------------------------------------------------------------
# Re-export: make `from rhk_base import *` work across split modules.
# We intentionally include leading-underscore helpers because other modules rely on them.
__all__ = [k for k in globals().keys() if not k.startswith('__')]
