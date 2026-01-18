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
        for w in (warns[:10] if isinstance(warns, list) else []):
            try:
                tip_lines.append(f"- {w}")
            except Exception:
                continue
        if isinstance(warns, list) and len(warns) > 10:
            tip_lines.append(f"(+{len(warns)-10} weitere)")
        tip = "\n".join(tip_lines)
        vals.append(_chip(f"! {len(warns)}", "rhk-schip--warn", tip))
        
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

    def render_doc(payload: Optional[Dict], title: str) -> str:
        if not payload: return ""
        p = DataProbe(payload)
        phases = p.get("phases", default={})
        
        # Struct Table
        tbl = ""
        if phases:
            order = ["base1", "base2", "exercise", "post"]
            keys = [k for k in order if k in phases]
            if not keys: keys = list(phases.keys())
            
            label_map = {"base1": "Base 1", "base2": "Base 2", "exercise": "Ergo", "post": "Intervention"}
            cols = [label_map.get(k, k) for k in keys]
            
            rows = []
            def row(lbl, acc):
                vals = [acc(k) for k in keys]
                if any(v!="–" for v in vals):
                    rows.append(f"<tr><td>{html_escape(lbl)}</td>"+"".join(f"<td>{v}</td>" for v in vals)+"</tr>")
            
            def sl(ph, ch, ks):
                pp = DataProbe(phases.get(ph))
                vs = [f"{pp.float('pressures',ch,k) or '–':.0f}".replace("nan","–") for k in ks]
                return "/".join(vs).replace("–/–/–", "–")
            
            row("RAP (a/v/m)", lambda k: sl(k,"ra",["a","v","mean"]))
            row("PAP (s/d/m)", lambda k: sl(k,"pa",["sys","dia","mean"]))
            row("PAWP (a/v/m)", lambda k: sl(k,"pcw",["a","v","mean"]))
            row("CO (TD/Fick)", lambda k: f"{DataProbe(phases.get(k)).fmt('co','td_co')} / {DataProbe(phases.get(k)).fmt('co','fick_co')}")
            
            if rows:
                tbl = f"<div class='docx-box'><div class='docx-title'>{title} (Strukturiert)</div><table class='rhk-tbl'><thead><tr><th>Param</th>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"

        # Raw Tables
        raw_html = []
        for t in p.get("raw_tables", "all_tables", default=[]):
            mtx = t.get("matrix", [])
            t_tit = t.get("title", "Tabelle")
            if mtx and len(mtx) > 1 and not any(x in str(mtx).lower() for x in ["risiko", "risk", "who-f"]):
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
        w = "warn" if p.str("quality","status") != "ok" else ""
        return f"<div class='docx-box {w}'><div class='docx-title'>{t}</div><div class='docx-row'>{_chip(p.str('patient','exam_date'))} {_chip(p.str('quality','status'))}</div></div>"
    return "<div class='docx-status'>" + ren("Import Aktuell", docx_cur) + ren("Import Vorher", docx_prev) + "</div>" + build_docx_tables_overview_html(docx_cur, docx_prev)