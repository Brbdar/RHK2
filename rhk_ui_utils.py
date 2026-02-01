#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI Rendering Engine for RHK Befundassistent.
Version: 1.9.6 (Hotfix)

Changes:
- Removed metadata headers causing SyntaxErrors.
- Restored 'from rhk_base import *' to fix app-wide NameErrors.
- Restored '_fmt_or_dash' and '_normalize_module_ids' for compatibility.
- Implemented robust DataProbe to prevent NoneType crashes.
"""

from __future__ import annotations

import os
import html as _html
import functools
import re
import math
from typing import Any, Dict, List, Optional, Union, Tuple, Callable

# --- CRITICAL: Restore Base Context ---
# Many parts of the app rely on rhk_ui_utils providing these constants.
try:
    from rhk_base import *
except ImportError:
    pass

# --- Safe Import of Viz Engine ---
try:
    from rhk_viz import (
        svg_mpap_pawp_vs_co, 
        svg_series_over_phases, 
        svg_delta_bars, 
        svg_compare_bars
    )
except ImportError:
    # Fallback mocks to prevent crash if viz module is missing/broken
    def svg_mpap_pawp_vs_co(*a, **k): return ""
    def svg_series_over_phases(*a, **k): return ""
    def svg_delta_bars(*a, **k): return ""
    def svg_compare_bars(*a, **k): return ""

# Optional YAML support
try:
    import yaml
except ImportError:
    yaml = None


# --- 1. Safety & Infrastructure Layer ---

def ui_safe_render(fallback: str = "") -> Callable:
    """Decorator: Catches any error during HTML generation to prevent UI crash."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                return fallback
        return wrapper
    return decorator


class DataProbe:
    """
    Robust accessor for deeply nested clinical data structures.
    Prevents 'AttributeError: NoneType' chains and standardizes formatting.
    """
    def __init__(self, data: Optional[Dict[str, Any]]):
        self._data = data or {}

    def get(self, *path: Union[str, int], default: Any = None) -> Any:
        """Deep safe get."""
        curr = self._data
        for key in path:
            if isinstance(curr, dict):
                curr = curr.get(key)
            elif isinstance(curr, list) and isinstance(key, int):
                try:
                    curr = curr[key]
                except IndexError:
                    return default
            else:
                return default
        return curr if curr is not None else default

    def float(self, *path: Union[str, int]) -> Optional[float]:
        """Returns float or None. No exceptions."""
        val = self.get(*path)
        if val is None or val == "":
            return None
        try:
            # Handle German decimal comma if present
            if isinstance(val, str):
                val = val.replace(",", ".")
            f = float(val)
            return f if math.isfinite(f) else None
        except (ValueError, TypeError):
            return None

    def str(self, *path: Union[str, int]) -> str:
        """Returns string (stripped) or empty string."""
        val = self.get(*path)
        return str(val).strip() if val is not None else ""

    def fmt(self, *path: Union[str, int], nd: int = 0, dash: str = "–") -> str:
        """Formats number safely."""
        val = self.float(*path)
        if val is None:
            return dash
        return f"{val:.{nd}f}"


def html_escape(s: Any) -> str:
    """Robust HTML escape."""
    if s is None: return ""
    try:
        return _html.escape(str(s), quote=True)
    except Exception:
        return ""


# --- 2. Global Helpers (Restored for Compatibility) ---

def _fmt_or_dash(v: Any, nd: int = 0) -> str:
    """Legacy helper required by rhk_ui.py."""
    try:
        if v is None or v == "": return "–"
        if isinstance(v, str): v = v.replace(",", ".")
        fv = float(v)
        return f"{fv:.{nd}f}"
    except Exception:
        return "–"

def _normalize_module_ids(ids: List[str]) -> List[str]:
    """Helper to normalize list of module IDs."""
    if not ids: return []
    return [str(x).strip() for x in ids if x]

def _gradio_major_version() -> int:
    try:
        import gradio as gr
        v = getattr(gr, "__version__", "0")
        return int(str(v).split(".")[0])
    except Exception:
        return 0


@functools.lru_cache(maxsize=16)
def load_rulebook_meta(path: str) -> Dict[str, Any]:
    """Cached metadata reader."""
    if not path or not os.path.exists(path) or yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        return doc.get("meta", {}) if isinstance(doc, dict) else {}
    except Exception:
        return {}


# --- 3. Medical Logic Layer ---

def compute_egfr(creatinine_mg_dl: Any, age_years: Any, sex: Any) -> Tuple[Optional[float], str]:
    """
    Computes eGFR (CKD-EPI 2021) and returns (value, stage_label).
    Strict validation of inputs to avoid biological nonsense.
    """
    try:
        scr = float(str(creatinine_mg_dl).replace(",", "."))
        age = float(str(age_years).replace(",", "."))
    except (ValueError, TypeError, AttributeError):
        return None, ""

    # Biological plausibility bounds
    if scr <= 0.1 or scr > 25.0 or age <= 0 or age > 130:
        return None, ""

    # Sex normalization
    s = str(sex or "").strip().lower()
    is_female = s in {"w", "weiblich", "female", "f", "frau"}

    # Constants CKD-EPI 2021 (Race-free)
    k = 0.7 if is_female else 0.9
    a = -0.241 if is_female else -0.302
    sex_factor = 1.012 if is_female else 1.0

    ratio = scr / k
    mn = min(ratio, 1.0)
    mx = max(ratio, 1.0)

    try:
        egfr = 142.0 * (mn ** a) * (mx ** -1.200) * (0.9938 ** age) * sex_factor
        
        # Staging
        if egfr >= 90: stage = "G1"
        elif egfr >= 60: stage = "G2"
        elif egfr >= 45: stage = "G3a"
        elif egfr >= 30: stage = "G3b"
        elif egfr >= 15: stage = "G4"
        else: stage = "G5"
        
        return round(egfr, 1), stage
    except Exception:
        return None, ""


# --- 4. UI Component Builders ---

def _chip(text: str, tone: str = "", title: str = "") -> str:
    """Helper for semantic chips.

    Wenn ein Titel gesetzt ist, wird ein Hover-Tooltip gerendert (CSS-only, ohne JS).
    Dadurch bleibt der Hinweis auch dann verfuegbar, wenn Attribute wie `title`
    durch Sanitizing entfernt werden.
    """
    c = f"rhk-schip {tone}".strip()
    if title:
        safe_title = html_escape(title)
        tip_html = safe_title.replace("\n", "<br>")
        tattr = f" title='{safe_title}'"
        return (
            f"<span class='{c} rhk-has-tip'{tattr}>"
            f"{html_escape(text)}"
            f"<span class='rhk-tip'>{tip_html}</span>"
            f"</span>"
        )
    return f"<span class='{c}'>{html_escape(text)}</span>"


@ui_safe_render(fallback="<div class='rhk-error'>Summary Render Error</div>")
def build_sticky_summary_html(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]] = None) -> str:
    """Concise, always-visible live preview of key values."""
    if not case:
        status_chips = []
        if flags:
            if flags.get("dirty"):
                status_chips.append(_chip("Ungespeichert", "rhk-schip--warn"))
            elif flags.get("saved_at"):
                status_chips.append(_chip("Gespeichert", "rhk-schip--good"))
        return f"<div class='rhk-summarybar'><span class='rhk-schip'>Lade Daten...</span>{''.join(status_chips)}</div>"

    # Use DataProbe for cleaner access
    ui = DataProbe(case.get("ui"))
    der = DataProbe(case.get("derived"))
    scores = DataProbe(case.get("scores"))
    
    # 1. Hemodynamics
    cat_map = {
        "precap": "Prä-kapillär",
        "ipcph": "iPcPH",
        "cpcph": "cPcPH",
        "no_ph": "Keine PH",
        "unknown": "Unklar"
    }
    hemo_cat = der.str("hemo_category") or "unknown"
    hemo_txt = cat_map.get(hemo_cat, hemo_cat)
    
    vals = [
        _chip(f"Hämo: {hemo_txt}", "rhk-schip--info"),
        _chip(f"RAP: {der.fmt('rap_rest', nd=0)}"),
        _chip(f"mPAP: {der.fmt('mpap_rest', nd=0)}"),
        _chip(f"PAWP: {der.fmt('pawp_rest', nd=0)}"),
        _chip(f"PVR: {der.fmt('pvr_rest', nd=1)}"),
        _chip(f"CI: {der.fmt('ci_rest', nd=2)}")
    ]
    
    # 2. Risk Scores (ESC/ERS)
    esc4 = scores.str("esc_ers_4s")
    if esc4:
        tone = "rhk-schip--good" if esc4 == "low" else ("rhk-schip--bad" if esc4 == "high" else "rhk-schip--orange")
        vals.append(_chip(f"Risk: {esc4}", tone))
    
    # 3. Deltas (Comparison)
    curr_mpap = der.float("mpap_rest")
    prev_mpap = ui.float("prev_mpap")
    if curr_mpap is not None and prev_mpap is not None:
        diff = curr_mpap - prev_mpap
        arrow = "↑" if diff > 1 else ("↓" if diff < -1 else "→")
        vals.append(_chip(f"ΔmPAP {arrow}{abs(diff):.0f}", "rhk-schip--info"))
        
    # 4. Warnings
    warns = case.get("warnings") or []
    if warns:
        tip_lines = ["Warnungen:"]
        warn_list = warns if isinstance(warns, list) else [warns]
        has_error = False
        for w in warn_list[:10]:
            try:
                if isinstance(w, dict):
                    msg = str(w.get("message") or w.get("code") or "").strip()
                    sev = str(w.get("severity") or "").strip().lower()
                    if sev == "error":
                        has_error = True
                    icon = {
                        "error": "⛔",
                        "warn": "⚠️",
                        "info": "ℹ️",
                    }.get(sev, "•")
                    if msg:
                        tip_lines.append(f"{icon} {msg}")
                else:
                    tip_lines.append(f"- {w}")
            except Exception:
                continue
        if len(warn_list) > 10:
            tip_lines.append(f"(+{len(warn_list)-10} weitere)")
        tip = "\n".join(tip_lines)
        warn_cls = "rhk-schip--bad" if has_error else "rhk-schip--warn"
        vals.append(_chip(f"! {len(warn_list)}", warn_cls, tip))
        
    # 5. System Status
    if flags:
        if flags.get("dirty"):
            vals.append(_chip("Ungespeichert", "rhk-schip--warn"))
        elif flags.get("saved_at"):
            vals.append(_chip("Gespeichert", "rhk-schip--good"))
            
    return "<div class='rhk-summarybar'>" + "".join(vals) + "</div>"


@ui_safe_render()
def build_compare_overview_html(case: Optional[Dict[str, Any]]) -> str:
    """Comparison table (Prev vs Current)."""
    if not case: return ""
    
    ui = DataProbe(case.get("ui"))
    der = DataProbe(case.get("derived"))
    
    # Check if we have any previous data
    prev_keys = ["prev_rap", "prev_mpap", "prev_pawp", "prev_ci", "prev_pvr"]
    if not any(ui.get(k) is not None for k in prev_keys):
        return ""

    rows = [
        ("RAP (mmHg)", "prev_rap", "rap_rest", 0, 1.0),
        ("mPAP (mmHg)", "prev_mpap", "mpap_rest", 0, 2.0),
        ("PAWP (mmHg)", "prev_pawp", "pawp_rest", 0, 2.0),
        ("CI (l/min/m²)", "prev_ci", "ci_rest", 2, 0.2),
        ("PVR (WU)", "prev_pvr", "pvr_rest", 1, 0.5),
    ]
    
    html_rows = []
    for label, k_prev, k_curr, nd, thr in rows:
        v_prev = ui.float(k_prev)
        v_curr = der.float(k_curr)
        
        cell_prev = f"{v_prev:.{nd}f}" if v_prev is not None else "–"
        cell_curr = f"{v_curr:.{nd}f}" if v_curr is not None else "–"
        
        delta_html = "<span class='cmp-delta-flat'>–</span>"
        if v_prev is not None and v_curr is not None:
            delta = v_curr - v_prev
            cls = "cmp-delta-up" if delta > thr else ("cmp-delta-down" if delta < -thr else "cmp-delta-flat")
            sym = "↑" if delta > thr else ("↓" if delta < -thr else "±")
            delta_html = f"<span class='{cls}'>{sym} {abs(delta):.{nd}f}</span>"
            
        html_rows.append(
            f"<tr><td>{html_escape(label)}</td><td>{cell_prev}</td><td>{cell_curr}</td><td>{delta_html}</td></tr>"
        )
        
    date_prev = ui.str("prev_rhk_date")
    date_curr = ui.str("rhk_date")
    
    return (
        "<div class='cmp-wrap'>"
        "<div class='cmp-head'><div class='cmp-title'>Verlauf</div></div>"
        "<table><thead><tr>"
        f"<th>Parameter</th><th>Vorher <small>{html_escape(date_prev)}</small></th>"
        f"<th>Aktuell <small>{html_escape(date_curr)}</small></th><th>Δ</th>"
        f"</tr></thead><tbody>{''.join(html_rows)}</tbody></table>"
        "</div>"
    )


@ui_safe_render()
def build_pre_cath_header_html(ui: Dict[str, Any] | None) -> str:
    """
    Safety Header (Ampel system) with Clinical Cross-Checks.
    """
    d = DataProbe(ui)
    chips = []
    
    # 1. Consent
    done = d.get("consent_done") is True
    chips.append(_chip("Aufklärung OK" if done else "Aufklärung fehlt", "rhk-schip--good" if done else "rhk-schip--bad"))
    
    # 2. Access
    route = d.str("access_route")
    if route:
        chips.append(_chip(f"Zugang: {route}", "rhk-schip--info"))
        
    # 3. Coagulation & Anticoagulation (Integrated Logic)
    inr = d.float("inr")
    ptt = d.float("ptt_s")
    thrombos = d.float("platelets_g_l")
    
    ac_status = d.str("anticoag_status").lower()
    ac_paused = d.get("anticoag_paused") is True
    ac_active_kw = any(k in ac_status for k in ["ja", "yes", "marcumar", "doak"]) and "nein" not in ac_status

    # Coagulation Chips
    coag_warns = []
    if inr and inr > 1.5: coag_warns.append(f"INR {inr}")
    if ptt and ptt > 40: coag_warns.append(f"PTT {ptt}")
    if thrombos and thrombos < 100: coag_warns.append(f"Thrombos {thrombos}") # G/l
    
    if coag_warns:
        chips.append(_chip("Gerinnung (!)", "rhk-schip--warn", ", ".join(coag_warns)))
    else:
        has_data = (inr is not None or ptt is not None or thrombos is not None)
        chips.append(_chip("Gerinnung OK" if has_data else "Gerinnung ?", "rhk-schip--good" if has_data else "rhk-schip--info"))

    # Anticoagulation Chips (Cross-Check)
    if not ac_active_kw:
        # User says NO anticoagulation
        if inr and inr > 1.5:
             # Logic Conflict!
             chips.append(_chip("Antikoag? (INR hoch)", "rhk-schip--bad", "INR erhöht trotz Angabe 'Keine Antikoagulation'"))
        else:
             chips.append(_chip("Antikoag: Nein", "rhk-schip--good"))
    else:
        # User says YES anticoagulation
        if ac_paused or "paus" in ac_status:
            chips.append(_chip("Antikoag: Pausiert", "rhk-schip--good"))
        else:
            chips.append(_chip("Antikoag: Aktiv (!)", "rhk-schip--bad", "Nicht pausiert!"))

    # 4. Kidney (eGFR Staging)
    crea = d.float("creatinine_mg_dl")
    egfr_val, stage = compute_egfr(d.get("creatinine_mg_dl"), d.get("age"), d.get("sex"))
    
    # Fallback to direct entry if calc failed
    if egfr_val is None:
        egfr_val = d.float("egfr_ml_min_1_73") or d.float("egfr")
        if egfr_val: stage = "(Manuell)"

    kidney_tone = "rhk-schip--info"
    label = "Niere"
    tip = ""

    if egfr_val:
        label = f"eGFR {egfr_val:.0f}"
        if stage: label += f" {stage}"
        
        if egfr_val >= 90: kidney_tone = "rhk-schip--good" # G1
        elif egfr_val >= 60: kidney_tone = "rhk-schip--good" # G2
        elif egfr_val >= 30: kidney_tone = "rhk-schip--warn" # G3
        else: kidney_tone = "rhk-schip--bad" # G4/G5
    elif crea:
        label = f"Krea {crea:.2f}"
        kidney_tone = "rhk-schip--good" if crea < 1.3 else ("rhk-schip--warn" if crea < 1.8 else "rhk-schip--bad")
        
    chips.append(_chip(label, kidney_tone, tip))
    
    # 5. Infection
    crp = d.float("crp_mg_l")
    if crp is not None:
        chips.append(_chip(f"CRP {crp:.1f}", "rhk-schip--good" if crp < 5 else ("rhk-schip--warn" if crp < 20 else "rhk-schip--bad")))

    return "<div class='rhk-summarybar'>" + "".join(chips) + "</div>"


@ui_safe_render()
def build_docx_tables_overview_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    """DOCX Table extraction (Filtered)."""
    if not docx_cur and not docx_prev: return ""

    # --- Ampel styles (inline; keeps the overview table self-contained) ---
    _SEV_BG = {
        "g": "background:rgba(34,197,94,.14);",
        "y": "background:rgba(234,179,8,.16);",
        "r": "background:rgba(239,68,68,.14);",
        "": "",
    }
    _SEV_BORDER = {
        "g": "border-left:6px solid rgba(34,197,94,.45);",
        "y": "border-left:6px solid rgba(234,179,8,.55);",
        "r": "border-left:6px solid rgba(239,68,68,.45);",
        "": "border-left:6px solid rgba(0,0,0,.04);",
    }

    def _hemo_sev(metric: str, x: Optional[float]) -> str:
        """Return g/y/r for hemodynamic guideline cutoffs.

        This is a compact orientation aid for the import overview table.
        """
        if x is None:
            return ""
        try:
            xx = float(x)
            if not math.isfinite(xx):
                return ""
        except Exception:
            return ""

        m = (metric or "").lower()

        # PH definition / severity oriented cutoffs (ESC/ERS aligned)
        if m in ("mpap",):
            # <=20 no PH (g), 21-24 borderline (y), >=25 clearly elevated (r)
            if xx <= 20:
                return "g"
            if xx < 25:
                return "y"
            return "r"

        if m in ("pawp",):
            # <=15 (g), 16-18 (y), >18 (r)
            if xx <= 15:
                return "g"
            if xx <= 18:
                return "y"
            return "r"

        if m in ("rap",):
            # Low/intermediate/high risk marker (mRAP)
            if xx < 8:
                return "g"
            if xx <= 14:
                return "y"
            return "r"

        if m in ("ci",):
            # Low/intermediate/high risk marker (CI)
            if xx >= 2.5:
                return "g"
            if xx >= 2.0:
                return "y"
            return "r"

        if m in ("pvr",):
            # Precap definition marker (PVR)
            if xx <= 2:
                return "g"
            if xx <= 5:
                return "y"
            return "r"

        return ""

    def _plaus_sev(metric: str, x: Optional[float]) -> str:
        """Plausibility ampel (broad physiologic ranges). Missing -> no color."""
        try:
            if x is None:
                return ""
            xx = float(x)
            if not math.isfinite(xx):
                return ""
        except Exception:
            return ""
        if xx <= 0:
            return "r"
        m = (metric or "").lower()

        # Cardiac output related
        if m in ("co",):
            if 3.0 <= xx <= 8.0:
                return "g"
            if 2.0 <= xx < 3.0 or 8.0 < xx <= 10.0:
                return "y"
            return "r"
        if m in ("hr", "hf"):
            if 50 <= xx <= 110:
                return "g"
            if 40 <= xx < 50 or 110 < xx <= 130:
                return "y"
            return "r"
        if m in ("sv",):
            if 50 <= xx <= 120:
                return "g"
            if 30 <= xx < 50 or 120 < xx <= 160:
                return "y"
            return "r"
        if m in ("svi",):
            if 30 <= xx <= 65:
                return "g"
            if 20 <= xx < 30 or 65 < xx <= 80:
                return "y"
            return "r"
        if m in ("bsa",):
            if 1.3 <= xx <= 2.3:
                return "g"
            if 1.1 <= xx < 1.3 or 2.3 < xx <= 2.6:
                return "y"
            return "r"

        # Resistances (WU / indexed WU): plausibility only (not guideline risk)
        if m in ("pvri",):
            if xx <= 6:
                return "g"
            if xx <= 10:
                return "y"
            return "r"
        if m in ("tpr", "tvr"):
            if 10 <= xx <= 30:
                return "g"
            if 5 <= xx < 10 or 30 < xx <= 40:
                return "y"
            return "r"
        if m in ("tpri", "tvri"):
            if 15 <= xx <= 45:
                return "g"
            if 10 <= xx < 15 or 45 < xx <= 60:
                return "y"
            return "r"

        # Stroke work (broad)
        if m in ("rvswi",):
            if 2 <= xx <= 20:
                return "g"
            if 20 < xx <= 35:
                return "y"
            return "r"
        if m in ("rvsw",):
            if 2 <= xx <= 30:
                return "g"
            if 30 < xx <= 50:
                return "y"
            return "r"
        if m in ("lvswi",):
            if 20 <= xx <= 90:
                return "g"
            if 90 < xx <= 120:
                return "y"
            return "r"
        if m in ("lvsw",):
            if 20 <= xx <= 150:
                return "g"
            if 150 < xx <= 200:
                return "y"
            return "r"

        # Flow / oxygen transport (broad)
        if m in ("vo2",):
            if 150 <= xx <= 450:
                return "g"
            if 100 <= xx < 150 or 450 < xx <= 600:
                return "y"
            return "r"
        if m in ("avo2", "avo2diff"):
            if 3 <= xx <= 7:
                return "g"
            if 7 < xx <= 10 or 2 <= xx < 3:
                return "y"
            return "r"
        if m in ("qp_qs", "qpqs"):
            if 0.8 <= xx <= 1.2:
                return "g"
            if 0.6 <= xx < 0.8 or 1.2 < xx <= 1.5:
                return "y"
            return "r"

        return ""

    def _td(text: str, sev: str = "") -> str:
        sty = (_SEV_BG.get(sev or "", "") + _SEV_BORDER.get(sev or "", "")).strip()
        if sty:
            return f"<td style='{sty};padding-left:10px'>{text}</td>"
        return f"<td>{text}</td>"

    def render_doc(payload: Optional[Dict], title: str) -> str:
        if not payload: return ""
        p = DataProbe(payload)
        phases = p.get("phases", default={})
        
        # Struct Table
        tbl = ""
        if phases:
            # Phase order (stable): Base1/Base2 + optional Zusatzphasen
            order = ["base1", "base2", "exercise", "post"]
            keys = [k for k in order if k in phases]
            if not keys: keys = list(phases.keys())
            
            label_map = {"base1": "Base 1", "base2": "Base 2", "exercise": "Ergo", "post": "Intervention"}
            cols = [label_map.get(k, k) for k in keys]
            
            rows = []
            def row(lbl, acc):
                vals = [acc(k) for k in keys]
                if any(v.get("text") != "–" for v in vals):
                    cells = "".join(_td(v.get("text", "–"), v.get("sev", "")) for v in vals)
                    rows.append(f"<tr><td>{html_escape(lbl)}</td>{cells}</tr>")
            def _fmt_int(x: Optional[float]) -> str:
                if x is None:
                    return "–"
                try:
                    return f"{float(x):.0f}" if math.isfinite(float(x)) else "–"
                except Exception:
                    return "–"

            def _fmt_float(x: Optional[float], nd: int = 1) -> str:
                if x is None:
                    return "–"
                try:
                    xx = float(x)
                    if not math.isfinite(xx):
                        return "–"
                    return f"{xx:.{nd}f}"
                except Exception:
                    return "–"

            def section(t: str) -> None:
                # visual group separator
                rows.append(
                    f"<tr><td colspan='{len(keys)+1}' style='font-weight:700;background:rgba(0,0,0,.03);padding:8px 10px'>{html_escape(t)}</td></tr>"
                )

            def sl_press(ph: str, ch: str, ks: list[str]) -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                # For cell ampel: use mean if present (fallback: sys for PAP)
                mean_for_sev = pp.float("pressures", ch, "mean")
                if ch == "pa" and mean_for_sev is None:
                    mean_for_sev = pp.float("pressures", ch, "sys")
                vs = [_fmt_int(pp.float("pressures", ch, k)) for k in ks]
                txt = "/".join(vs)
                if txt == "–/–/–":
                    txt = "–"
                sev = ""
                if ch == "ra":
                    sev = _hemo_sev("rap", mean_for_sev)
                elif ch == "pcw":
                    sev = _hemo_sev("pawp", mean_for_sev)
                elif ch == "pa":
                    sev = _hemo_sev("mpap", mean_for_sev)
                return {"text": txt, "sev": sev}

            def pair_cell(ph: str, sect: str, key_a: str, key_b: str, *, nd: int = 1, sev_metric: str = "") -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                a = pp.float(sect, key_a)
                b = pp.float(sect, key_b)
                txt = f"{_fmt_float(a, nd)} / {_fmt_float(b, nd)}"
                if txt == "– / –":
                    txt = "–"
                sev_val = a if a is not None else b
                sev = _plaus_sev(sev_metric, sev_val) if sev_metric else ""
                return {"text": txt, "sev": sev}

            def single_cell(ph: str, sect: str, key: str, *, nd: int = 1, sev_metric: str = "") -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                v = pp.float(sect, key)
                txt = _fmt_float(v, nd)
                if txt == "–":
                    return {"text": "–", "sev": ""}
                sev = _plaus_sev(sev_metric, v) if sev_metric else ""
                return {"text": txt, "sev": sev}

            def res_cell(ph: str, key: str, *, sev_metric: str = "") -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                r = pp.get("resistance", key, default=None)
                wu = dyn = None
                if isinstance(r, dict):
                    wu = r.get("wu")
                    dyn = r.get("dyn")
                txt = "–"
                if wu is not None and dyn is not None:
                    txt = f"{_fmt_float(wu, 1)} / {_fmt_int(dyn)}"
                elif wu is not None:
                    txt = f"{_fmt_float(wu, 1)}"
                elif dyn is not None:
                    txt = f"{_fmt_int(dyn)}"
                sev = ""
                if wu is not None:
                    if sev_metric == "pvr":
                        sev = _hemo_sev("pvr", wu)
                    elif sev_metric:
                        sev = _plaus_sev(sev_metric, wu)
                return {"text": txt, "sev": sev}

            def work_cell(ph: str, key: str, *, nd: int = 1, sev_metric: str = "") -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                v = pp.float("work", key)
                txt = _fmt_float(v, nd)
                sev = _plaus_sev(sev_metric, v) if (sev_metric and v is not None) else ""
                return {"text": txt if txt != "–" else "–", "sev": sev}

            def flow_cell(ph: str, key: str, *, nd: int = 1, sev_metric: str = "") -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                v = pp.float("flow", key)
                txt = _fmt_float(v, nd)
                sev = _plaus_sev(sev_metric, v) if (sev_metric and v is not None) else ""
                return {"text": txt if txt != "–" else "–", "sev": sev}

            # --- Requested compact summary (only key hemodynamics; no risk-table/Hb noise) ---
            section("Drücke")
            row("RAP (a/v/m)", lambda k: sl_press(k, "ra", ["a", "v", "mean"]))
            row("PAP (s/d/m)", lambda k: sl_press(k, "pa", ["sys", "dia", "mean"]))
            row("PAWP (a/v/m)", lambda k: sl_press(k, "pcw", ["a", "v", "mean"]))

            section("Herzzeitvolumen")
            row("CO (TD/Fick)", lambda k: pair_cell(k, "co", "td_co", "fick_co", nd=1, sev_metric="co"))
            def _ci_cell(ph: str) -> Dict[str, str]:
                pp = DataProbe(phases.get(ph))
                td_ci = pp.float("co", "td_ci")
                fk_ci = pp.float("co", "fick_ci")
                ci_for_sev = td_ci if td_ci is not None else fk_ci
                return {"text": pair_cell(ph, "co", "td_ci", "fick_ci", nd=2).get("text", "–"), "sev": _hemo_sev("ci", ci_for_sev)}
            row("CI (TD/Fick)", lambda k: _ci_cell(k))
            row("HF (TD/Fick)", lambda k: pair_cell(k, "co", "td_hr", "fick_hr", nd=0, sev_metric="hr"))
            row("SV (TD/Fick)", lambda k: pair_cell(k, "co", "td_sv_ml", "fick_sv_ml", nd=0, sev_metric="sv"))
            row("SVI (TD/Fick)", lambda k: pair_cell(k, "co", "td_svi_ml_m2", "fick_svi_ml_m2", nd=0, sev_metric="svi"))
            row("BSA (m2)", lambda k: single_cell(k, "co", "bsa_m2", nd=2, sev_metric="bsa"))

            section("Widerstände")
            row("PVR (WU)", lambda k: res_cell(k, "pvr", sev_metric="pvr"))
            row("PVRI (WU*m2)", lambda k: res_cell(k, "pvri", sev_metric="pvri"))
            row("TPR (WU)", lambda k: res_cell(k, "tpr", sev_metric="tpr"))
            row("TPRI (WU*m2)", lambda k: res_cell(k, "tpri", sev_metric="tpri"))
            row("TVR (WU)", lambda k: res_cell(k, "tvr", sev_metric="tvr"))

            section("Schlagarbeit")
            row("RVSWI (g*m/m2)", lambda k: work_cell(k, "rvswi_gm_m2", nd=1, sev_metric="rvswi"))
            row("RVSW (g*m)", lambda k: work_cell(k, "rvsw_gm", nd=1, sev_metric="rvsw"))
            row("LVSWI (g*m/m2)", lambda k: work_cell(k, "lvswi_gm_m2", nd=1, sev_metric="lvswi"))
            row("LVSW (g*m)", lambda k: work_cell(k, "lvsw_gm", nd=1, sev_metric="lvsw"))

            section("Blutfluss")
            row("VO2 (ml/min)", lambda k: flow_cell(k, "vo2_ml_min", nd=0, sev_metric="vo2"))
            row("a-VO2 (ml/dl)", lambda k: flow_cell(k, "avo2diff_ml_dl", nd=1, sev_metric="avo2"))
            row("Fick-HZV (l/min)", lambda k: flow_cell(k, "fick_co_repeat", nd=1, sev_metric="co"))
            row("Qp (l/min)", lambda k: flow_cell(k, "qp_l_min", nd=1, sev_metric="co"))
            row("Qs (l/min)", lambda k: flow_cell(k, "qs_l_min", nd=1, sev_metric="co"))
            row("Qp/Qs", lambda k: flow_cell(k, "qp_qs", nd=2, sev_metric="qp_qs"))

            if rows:

                tbl = f"<div class='docx-box'><div class='docx-title'>{title} (Strukturiert)</div><table class='rhk-tbl'><thead><tr><th>Param</th>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"

        # Raw Tables
        raw_html = []
        for t in p.get("raw_tables", "all_tables", default=[]):
            mtx = t.get("matrix", [])
            t_tit = t.get("title", "Tabelle")
            # Strict UI filter: only keep raw tables that belong to the compact hemodynamic summary.
            # Everything else (patient/meta/time, biomarkers, echo, cMRI, etc.) is intentionally hidden here.
            tit_l = str(t_tit or "").strip().lower()
            allow_terms = [
                "für berechnung", "fuer berechnung", "druckwerte", "druck",
                "herzzeitvolumen", "hzv",
                "widerstand", "resist",
                "schlagarbeit", "stroke work",
                "blutfluss", "flow",
            ]
            if not tit_l:
                continue
            if not any(a in tit_l for a in allow_terms):
                continue
            if mtx and len(mtx) > 1:
                s = str(mtx).lower()
                skip_terms = [
                    "risiko", "risk", "who-f",
                    "hb", "hämoglobin", "haemoglobin", "hemoglobin",
                    "sao2", "svo2", "sat", "sätt", "sättigung", "saturation",
                    "blutgas", "bga", "oxygen", "o2"
                ]
                if any(t in s for t in skip_terms):
                    continue
                head = "".join(f"<th>{html_escape(c)}</th>" for c in mtx[0])
                body = "".join(f"<tr>{''.join(f'<td>{html_escape(c)}</td>' for c in r)}</tr>" for r in mtx[1:10])
                raw_html.append(f"<details><summary>{html_escape(t_tit)}</summary><table class='rhk-tbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></details>")
        
        return tbl + "".join(raw_html)

    return render_doc(docx_cur, "Aktuell") + render_doc(docx_prev, "Vorher")


@ui_safe_render()
def build_rhk_plots_html(case: Dict[str, Any], docx_cur: Optional[Dict], docx_prev: Optional[Dict]) -> str:
    """Viz generation."""
    if not case: return ""
    charts = []
    
    # 1. Phases
    if docx_cur:
        p = DataProbe(docx_cur)
        ph = p.get("phases", default={})
        if ph:
            order = ["base1", "base2", "exercise", "post"]
            keys = [k for k in order if k in ph]
            if keys:
                labs = [k.capitalize() for k in keys]
                s_mpap = [DataProbe(ph[k]).float("pressures", "pa", "mean") for k in keys]
                s_co = [DataProbe(ph[k]).float("co", "td_co") for k in keys]
                
                if any(x is not None for x in s_mpap):
                    charts.append(svg_series_over_phases(labs, {"mPAP": s_mpap}, "Druckverlauf", "mmHg"))
                if any(x is not None for x in s_co):
                    charts.append(svg_series_over_phases(labs, {"HZV": s_co}, "Flussverlauf", "l/min"))

    # 2. Exercise
    der = DataProbe(case.get("derived"))
    if DataProbe(case.get("raw")).get("exercise_done"):
        charts.append(svg_mpap_pawp_vs_co(
            der.float("mpap"), der.float("pawp"), der.float("co"),
            der.float("mpap_peak"), der.float("pawp_peak"), der.float("co_peak"),
            "Belastung"
        ))

    # 3. Deltas
    ui = DataProbe(case.get("ui"))
    deltas = []
    for k, l in [("mpap", "mPAP"), ("pvr", "PVR"), ("ci", "CI")]:
        c, p = (der.float(f"{k}_rest") or der.float(k)), ui.float(f"prev_{k}")
        if c is not None and p is not None: deltas.append((l, c - p))
    if deltas:
        charts.append(svg_delta_bars(deltas, "Verlauf (Delta)", "Diff"))

    return "<div class='rhk-viz-grid'>" + "".join(f"<div class='rhk-viz-item'>{c}</div>" for c in charts) + "</div>" if charts else ""


@ui_safe_render()
def build_p_module_cards_html(blocks: Dict[str, Any], case: Optional[Dict[str, Any]]) -> str:
    """Decision Support Cards."""
    if not case: return ""
    ui = DataProbe(case.get("ui"))
    decision = DataProbe(case.get("decision"))
    policy = DataProbe(case.get("derived")).get("p_module_policy", {})
    
    allowed = set(policy.get("allowed", []))
    levels = policy.get("levels", {})
    sel = set(ui.get("modules") or [])
    auto = set(decision.get("modules") or [])
    
    cards = []
    for pid in sorted(blocks.keys()):
        if allowed and pid not in allowed: continue
        lvl = int(levels.get(pid, 3))
        
        # Hide Level 3 unless selected/suggested
        if lvl > 2 and pid not in sel and pid not in auto: continue
        
        b = blocks[pid]
        tit = getattr(b, "title", pid)
        sub = getattr(b, "subtitle", "")
        
        cls = "pmod-card"
        badges = [f"<span class='pmod-chip pmod-chip--lvl{lvl}'>Lvl {lvl}</span>"]
        if pid in sel:
            cls += " selected"
            badges.append("<span class='pmod-chip pmod-chip--manual'>Gewählt</span>")
        elif pid in auto:
            badges.append("<span class='pmod-chip pmod-chip--auto'>Vorschlag</span>")
            
        cards.append(f"<div class='{cls}'><div class='pmod-title'>{html_escape(tit)}</div><div class='pmod-sub'>{html_escape(sub)}</div><div class='pmod-meta'>{''.join(badges)}</div></div>")
        
    return "<div class='pmod-grid'>" + "".join(cards) + "</div>"

@ui_safe_render()
def build_docx_status_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    def ren(t, d):
        if not d: return ""
        p = DataProbe(d)
        st = (p.str("quality", "status") or "").strip().lower()
        # Import quality uses Ampel labels (green/yellow/red). Older payloads might use 'ok'.
        cls = ""
        if st in ("green", "ok"):
            cls = "good"
        elif st in ("yellow", "warn"):
            cls = "yellow"
        elif st in ("red", "bad"):
            cls = "bad"
        # Default: neutral box
        chip_tone = ""
        if st in ("green", "ok"):
            chip_tone = "rhk-schip--good"
        elif st in ("yellow", "warn"):
            chip_tone = "rhk-schip--warn"
        elif st in ("red", "bad"):
            chip_tone = "rhk-schip--bad"
        return (
            f"<div class='docx-box {cls}'>"
            f"<div class='docx-title'>{t}</div>"
            f"<div class='docx-row'>{_chip(p.str('patient','exam_date'))} {_chip(st or '–', chip_tone)}</div>"
            f"</div>"
        )
    return "<div class='docx-status'>" + ren("Import Aktuell", docx_cur) + ren("Import Vorher", docx_prev) + "</div>" + build_docx_tables_overview_html(docx_cur, docx_prev)
