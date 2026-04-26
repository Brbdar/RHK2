#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_render_docx.py - DOCX Import Übersicht Renderer ausgelagert, 1:1 Logik, bessere Wartbarkeit
"""DOCX import overview renderers (HTML).

This module renders:
- status boxes (current/previous)
- compact structured hemodynamics tables (filtered)
- optional raw table snippets (filtered)

Important: Rendering-only. No parsing, no mutation, no medical computation besides simple threshold highlighting.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from rhk_ui_core import DataProbe, _chip, html_escape, ui_safe_render


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
        except (TypeError, ValueError):
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
                except (TypeError, ValueError):
                    return "–"

            def _fmt_float(x: Optional[float], nd: int = 1) -> str:
                if x is None:
                    return "–"
                try:
                    xx = float(x)
                    if not math.isfinite(xx):
                        return "–"
                    return f"{xx:.{nd}f}"
                except (TypeError, ValueError):
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
