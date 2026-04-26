#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_render_viz.py - Plot/Viz-Renderer ausgelagert, Safe Import (no hard crash)
"""Visualization renderers (SVG HTML snippets)."""

from __future__ import annotations

import functools
import json
from typing import Any, Dict, List, Optional, Tuple

from rhk_ui_core import DataProbe, ui_safe_render

# Safe import of viz engine (fail-safe: missing/broken module must not crash UI)
try:
    from rhk_viz import (
        svg_compare_bars,
        svg_delta_bars,
        svg_mpap_pawp_vs_co,
        svg_series_over_phases,
    )
except Exception:  # pragma: no cover
    def svg_mpap_pawp_vs_co(*_a: Any, **_k: Any) -> str:  # type: ignore
        return ""

    def svg_series_over_phases(*_a: Any, **_k: Any) -> str:  # type: ignore
        return ""

    def svg_delta_bars(*_a: Any, **_k: Any) -> str:  # type: ignore
        return ""

    def svg_compare_bars(*_a: Any, **_k: Any) -> str:  # type: ignore
        return ""


_PLOT_PHASE_KEYS = ("base1", "base2", "exercise", "post")
_PLOT_DERIVED_KEYS = (
    "mpap",
    "pawp",
    "co",
    "mpap_peak",
    "pawp_peak",
    "co_peak",
    "mpap_rest",
    "pvr_rest",
    "ci_rest",
    "pvr",
    "ci",
)
_PLOT_UI_KEYS = ("prev_mpap", "prev_pvr", "prev_ci")


def _phase_plot_payload(docx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(docx, dict):
        return None
    phases = DataProbe(docx).get("phases", default={})
    if not isinstance(phases, dict):
        return None
    out: Dict[str, Any] = {}
    for key in _PLOT_PHASE_KEYS:
        src = phases.get(key)
        if not isinstance(src, dict):
            continue
        p = DataProbe(src)
        out[key] = {
            "pressures": {"pa": {"mean": p.get("pressures", "pa", "mean")}},
            "co": {"td_co": p.get("co", "td_co")},
        }
    return out or None


def _plots_cache_payload(
    case: Optional[Dict[str, Any]],
    docx_cur: Optional[Dict[str, Any]],
    docx_prev: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    safe_case = case if isinstance(case, dict) else {}
    raw = safe_case.get("raw") if isinstance(safe_case.get("raw"), dict) else {}
    der = safe_case.get("derived") if isinstance(safe_case.get("derived"), dict) else {}
    ui = safe_case.get("ui") if isinstance(safe_case.get("ui"), dict) else {}
    return {
        "case": {
            "raw": {"exercise_done": raw.get("exercise_done")},
            "derived": {k: der.get(k) for k in _PLOT_DERIVED_KEYS},
            "ui": {k: ui.get(k) for k in _PLOT_UI_KEYS},
        },
        "docx_cur": {"phases": _phase_plot_payload(docx_cur)},
        "docx_prev": {"phases": _phase_plot_payload(docx_prev)},
    }


def _cache_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@functools.lru_cache(maxsize=128)
def _build_rhk_plots_html_cached(payload_json: str) -> str:
    payload = json.loads(payload_json)
    return _build_rhk_plots_html_impl(
        payload.get("case"),
        payload.get("docx_cur"),
        payload.get("docx_prev"),
    )


def _build_rhk_plots_html_impl(case: Dict[str, Any], docx_cur: Optional[Dict], docx_prev: Optional[Dict]) -> str:
    _ = docx_prev  # reserved for future comparative charting
    if not case:
        return ""
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
    deltas: List[Tuple[str, Optional[float]]] = []
    for k, l in [("mpap", "mPAP"), ("pvr", "PVR"), ("ci", "CI")]:
        c = der.float(f"{k}_rest")
        if c is None:
            c = der.float(k)
        prev_val = ui.float(f"prev_{k}")
        if c is not None and prev_val is not None:
            deltas.append((l, c - prev_val))
    if deltas:
        charts.append(svg_delta_bars(deltas, "Verlauf (Delta)", "Diff"))

    return "<div class='rhk-viz-grid'>" + "".join(f"<div class='rhk-viz-item'>{c}</div>" for c in charts) + "</div>" if charts else ""


@ui_safe_render()
def build_rhk_plots_html(case: Dict[str, Any], docx_cur: Optional[Dict], docx_prev: Optional[Dict]) -> str:
    """Viz generation."""
    payload = _plots_cache_payload(case, docx_cur, docx_prev)
    return _build_rhk_plots_html_cached(_cache_json(payload))
