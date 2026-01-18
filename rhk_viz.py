#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-Performance Clinical Visualization Engine (SVG).

Design Goals:
1. Zero Dependencies: Pure Python SVG generation (No Matplotlib/NumPy).
2. Clinical Precision: "Nice Numbers" algorithm for readable axes.
3. Web Safety: Scoped CSS, HTML escaping, and ARIA labels.
4. Performance: Buffered string building for O(n) complexity.

MASTERMIND EDITION:
- Implements Heckbert's "Nice Numbers" algorithm for tick generation.
- Supports Reference Bands (Normal ranges) in charts.
- Handles sparse/missing data robustly.
- Type-Safe closures for rendering loops.
"""

from __future__ import annotations
import math
import html
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

# --- 1. Core Utilities & Math ---

def _safe_float(x: Any) -> Optional[float]:
    """Strict conversion preventing NaN propagation in SVG paths."""
    if x is None or x == "":
        return None
    try:
        val = float(x)
        if math.isfinite(val):
            return val
    except (ValueError, TypeError):
        pass
    return None

def _nice_num(range_val: float, round_val: bool) -> float:
    """Helper for nice-scaling algorithm (Wilkinson/Heckbert)."""
    if range_val <= 0:
        return 0.0
        
    try:
        exponent = math.floor(math.log10(range_val))
    except ValueError:
        exponent = 0
        
    fraction = range_val / (10 ** exponent)
    
    if round_val:
        if fraction < 1.5: nice_fraction = 1.0
        elif fraction < 3.0: nice_fraction = 2.0
        elif fraction < 7.0: nice_fraction = 5.0
        else: nice_fraction = 10.0
    else:
        if fraction <= 1.0: nice_fraction = 1.0
        elif fraction <= 2.0: nice_fraction = 2.0
        elif fraction <= 5.0: nice_fraction = 5.0
        else: nice_fraction = 10.0
        
    return nice_fraction * (10 ** exponent)

def calculate_nice_scale(min_v: float, max_v: float, max_ticks: int = 5) -> Tuple[float, float, float]:
    """
    Calculates a 'human-readable' scale for chart axes.
    Returns (nice_min, nice_max, nice_step).
    """
    if min_v == max_v:
        if min_v == 0: return 0.0, 1.0, 0.2
        # Create artificial range around the single value
        return min_v - 0.5 * abs(min_v or 1.0), max_v + 0.5 * abs(max_v or 1.0), abs(min_v or 1.0) / 5

    range_v = _nice_num(max_v - min_v, False)
    if range_v == 0: 
        range_v = 1.0 # Fallback
        
    step = _nice_num(range_v / (max_ticks - 1), True)
    if step == 0:
        step = 1.0

    nice_min = math.floor(min_v / step) * step
    nice_max = math.ceil(max_v / step) * step
    
    # Correction if range is too tight
    if nice_max < max_v: nice_max += step
    if nice_min > min_v: nice_min -= step
    
    return nice_min, nice_max, step

# --- 2. Visualization Engine ---

@dataclass
class SvgTheme:
    """Central styling configuration."""
    # Palette: Blue, Orange, Green, Red, Neutral
    colors: List[str] = field(default_factory=lambda: [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"
    ])
    grid_color: str = "rgba(0,0,0,0.06)"
    text_main: str = "#1f2937"
    text_sub: str = "#6b7280"
    font: str = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

class SvgEngine:
    """
    Buffered SVG Builder with Scoped CSS.
    """
    def __init__(self, width: int, height: int, title: str, subtitle: str):
        self.w = width
        self.h = height
        self.title = title
        self.subtitle = subtitle
        # Unique ID for scoped CSS to prevent style collisions in the DOM
        self.uid = f"viz-{uuid.uuid4().hex[:8]}"
        self.buffer: List[str] = []
        
        # Margins
        self.ml, self.mr = 50, 16
        self.mt, self.mb = 36, 30
        self.pw = self.w - self.ml - self.mr
        self.ph = self.h - self.mt - self.mb
        
        # Scales (set later)
        self.y_range = (0.0, 1.0)

    def set_y_scale(self, min_v: float, max_v: float) -> Tuple[float, float, float]:
        """Auto-sets Y scale using Nice Numbers algorithm."""
        nice_min, nice_max, step = calculate_nice_scale(min_v, max_v)
        self.y_range = (nice_min, nice_max)
        return nice_min, nice_max, step

    def map_y(self, val: float) -> float:
        min_v, max_v = self.y_range
        span = max_v - min_v
        if span == 0: return self.mt + self.ph / 2
        return self.mt + self.ph - ((val - min_v) / span * self.ph)

    def map_x_cat(self, idx: int, count: int) -> float:
        if count <= 1: return self.ml + self.pw / 2
        return self.ml + (idx / (count - 1)) * self.pw

    def map_x_lin(self, val: float, min_v: float, max_v: float) -> float:
        span = max_v - min_v
        if span == 0: return self.ml + self.pw / 2
        return self.ml + ((val - min_v) / span * self.pw)

    def add(self, s: str) -> None:
        self.buffer.append(s)

    def draw_grid_y(self, nice_min: float, nice_max: float, step: float) -> None:
        """Draws horizontal grid lines."""
        curr = nice_min
        # Safety break to prevent infinite loops if step is 0
        if step <= 0: step = 1.0
        
        count = 0
        while curr <= nice_max + (step * 0.001) and count < 20:
            y = self.map_y(curr)
            # Line
            if self.mt <= y <= self.h - self.mb:
                self.add(f"<line x1='{self.ml}' y1='{y:.1f}' x2='{self.w - self.mr}' y2='{y:.1f}' "
                         f"stroke='{SvgTheme().grid_color}' stroke-width='1'/>")
                # Label
                label = f"{curr:.0f}" if abs(curr % 1) < 0.01 else f"{curr:.1f}"
                self.add(f"<text x='{self.ml - 8}' y='{y + 4:.1f}' font-size='11' "
                         f"fill='{SvgTheme().text_sub}' text-anchor='end'>{label}</text>")
            curr += step
            count += 1

    def render(self, legend_html: str = "") -> str:
        svg_content = "".join(self.buffer)
        
        # Scoped CSS
        css = (
            f"<style>"
            f"#{self.uid} {{ font-family: {SvgTheme().font}; border: 1px solid rgba(0,0,0,0.1); border-radius: 8px; padding: 12px; background: #fff; margin-bottom: 12px; }}"
            f"#{self.uid} .t {{ font-weight: 600; font-size: 14px; color: {SvgTheme().text_main}; margin: 0; }}"
            f"#{self.uid} .s {{ font-size: 11px; color: {SvgTheme().text_sub}; margin: 0 0 8px 0; }}"
            f"#{self.uid} .l {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; font-size: 11px; color: {SvgTheme().text_main}; }}"
            f"#{self.uid} .d {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}"
            f"</style>"
        )
        
        return (
            f"{css}"
            f"<div id='{self.uid}' role='img' aria-label='Chart: {html.escape(self.title)}'>"
            f"<div class='t'>{html.escape(self.title)}</div>"
            f"<div class='s'>{html.escape(self.subtitle)}</div>"
            f"<svg width='100%' viewBox='0 0 {self.w} {self.h}' preserveAspectRatio='xMidYMid meet' aria-hidden='true'>"
            f"{svg_content}"
            f"</svg>"
            f"<div class='l'>{legend_html}</div>"
            f"</div>"
        )


# --- 3. Public Chart Functions ---

def svg_series_over_phases(
    phases: List[str],
    series: Dict[str, List[Optional[float]]],
    title: str,
    y_label: str,
    height: int = 220,
    ref_band: Optional[Tuple[float, float]] = None
) -> str:
    """
    Multi-line chart over categorical phases (e.g., Rest -> Peak -> Recovery).
    Supports a 'Reference Band' to visualize normal ranges.
    """
    # 1. Clean Data
    clean_series = {k: [_safe_float(x) for x in v] for k, v in series.items()}
    all_vals = [x for v in clean_series.values() for x in v if x is not None]
    
    # 2. Setup Engine
    eng = SvgEngine(760, max(160, height), title, y_label)
    
    # 3. Scale Y-Axis
    min_v, max_v = (min(all_vals), max(all_vals)) if all_vals else (0.0, 1.0)
    
    # Expand scale to include reference band if present
    if ref_band:
        min_v = min(min_v, ref_band[0])
        max_v = max(max_v, ref_band[1])
        
    n_min, n_max, n_step = eng.set_y_scale(min_v, max_v)
    
    # 4. Draw Reference Band (Normal Range)
    if ref_band:
        r0, r1 = ref_band
        # Clamp visual rect to grid area
        r0_vis = max(r0, n_min)
        r1_vis = min(r1, n_max)
        
        if r1_vis > r0_vis:
            y_top = eng.map_y(r1_vis)
            y_bot = eng.map_y(r0_vis)
            eng.add(f"<rect x='{eng.ml}' y='{y_top:.1f}' width='{eng.pw}' height='{y_bot - y_top:.1f}' "
                    f"fill='rgba(46, 125, 50, 0.08)' />") # Green tint
            eng.add(f"<text x='{eng.w - eng.mr - 4}' y='{y_top + 10:.1f}' font-size='9' fill='#2e7d32' text-anchor='end'>Norm</text>")

    # 5. Draw Grid
    eng.draw_grid_y(n_min, n_max, n_step)
    
    # 6. Draw X-Axis Labels
    n_phases = len(phases)
    for i, ph in enumerate(phases):
        x = eng.map_x_cat(i, n_phases)
        eng.add(f"<text x='{x:.1f}' y='{eng.h - 8}' font-size='11' fill='{SvgTheme().text_sub}' "
                f"text-anchor='middle'>{html.escape(ph)}</text>")

    # 7. Draw Lines
    colors = SvgTheme().colors
    legend_items = []
    
    for idx, (name, vals) in enumerate(clean_series.items()):
        color = colors[idx % len(colors)]
        pts = []
        
        # Compute points
        for i, val in enumerate(vals):
            if val is not None:
                pts.append((eng.map_x_cat(i, n_phases), eng.map_y(val)))
            else:
                pts.append(None)
                
        # Path
        d_cmds = []
        current_seg = False
        for p in pts:
            if p is None:
                current_seg = False
                continue
            cmd = "L" if current_seg else "M"
            d_cmds.append(f"{cmd} {p[0]:.1f} {p[1]:.1f}")
            current_seg = True
            
        if d_cmds:
            eng.add(f"<path d='{' '.join(d_cmds)}' fill='none' stroke='{color}' stroke-width='2' stroke-linejoin='round'/>")

        # Dots
        for i, p in enumerate(pts):
            if p:
                eng.add(f"<circle cx='{p[0]:.1f}' cy='{p[1]:.1f}' r='3.5' fill='white' stroke='{color}' stroke-width='1.5'>"
                        f"<title>{html.escape(name)}: {vals[i]}</title></circle>")
                        
        legend_items.append(f"<span><span class='d' style='background:{color}'></span>{html.escape(name)}</span>")

    return eng.render("".join(legend_items))


def svg_mpap_pawp_vs_co(
    mpap_rest: Optional[float], pawp_rest: Optional[float], co_rest: Optional[float],
    mpap_peak: Optional[float], pawp_peak: Optional[float], co_peak: Optional[float],
    title: str,
) -> str:
    """
    Pressure-Flow Slope Plot (mPAP/PAWP vs CO).
    """
    # Validation
    vr_mpap, vp_mpap = _safe_float(mpap_rest), _safe_float(mpap_peak)
    vr_pawp, vp_pawp = _safe_float(pawp_rest), _safe_float(pawp_peak)
    vr_co, vp_co = _safe_float(co_rest), _safe_float(co_peak)
    
    if vr_co is None or vp_co is None:
        return "<div class='docx-muted'>(Keine ausreichenden HZV-Daten für Druck-Fluss-Plot)</div>"

    eng = SvgEngine(760, 260, title, "Druck (mmHg) vs. Fluss (l/min)")
    
    # Scales
    # X: Flow
    x_min, x_max, _ = calculate_nice_scale(min(vr_co, vp_co), max(vr_co, vp_co), max_ticks=4)
    # Y: Pressure
    p_vals = [x for x in [vr_mpap, vp_mpap, vr_pawp, vp_pawp] if x is not None]
    if not p_vals: p_vals = [0, 20]
    y_min, y_max, y_step = eng.set_y_scale(min(p_vals), max(p_vals)) 
    
    # Grids
    eng.draw_grid_y(y_min, y_max, y_step)
    
    # X Grid (Vertical)
    x_curr = x_min
    x_step = (x_max - x_min) / 4
    if x_step <= 0: x_step = 1.0
    for i in range(5):
        val = x_min + i * x_step
        x = eng.map_x_lin(val, x_min, x_max)
        eng.add(f"<line x1='{x:.1f}' y1='{eng.mt}' x2='{x:.1f}' y2='{eng.h - eng.mb}' stroke='rgba(0,0,0,0.05)'/>")
        eng.add(f"<text x='{x:.1f}' y='{eng.h - 10}' font-size='11' fill='{SvgTheme().text_sub}' text-anchor='middle'>{val:.1f}</text>")
        
    eng.add(f"<text x='{eng.w/2}' y='{eng.h - 2}' font-size='11' fill='{SvgTheme().text_main}' text-anchor='middle'>Herzzeitvolumen (l/min)</text>")

    # Draw Lines
    colors = SvgTheme().colors
    
    def draw_slope(v_rest: Optional[float], v_peak: Optional[float], name: str, col_idx: int) -> None:
        if v_rest is None or v_peak is None: return
        # Explicit type cast to satisfy linters since vr_co/vp_co validated not None above
        assert vr_co is not None and vp_co is not None
        
        x1 = eng.map_x_lin(float(vr_co), x_min, x_max)
        x2 = eng.map_x_lin(float(vp_co), x_min, x_max)
        y1 = eng.map_y(v_rest)
        y2 = eng.map_y(v_peak)
        
        col = colors[col_idx]
        eng.add(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{col}' stroke-width='2.5'/>")
        eng.add(f"<circle cx='{x1:.1f}' cy='{y1:.1f}' r='4' fill='{col}'><title>{name} Rest: {v_rest}</title></circle>")
        eng.add(f"<circle cx='{x2:.1f}' cy='{y2:.1f}' r='4' fill='{col}'><title>{name} Peak: {v_peak}</title></circle>")
        
    draw_slope(vr_mpap, vp_mpap, "mPAP", 0)
    draw_slope(vr_pawp, vp_pawp, "PAWP", 1)
    
    legend = (
        f"<span><span class='d' style='background:{colors[0]}'></span>mPAP</span>"
        f"<span><span class='d' style='background:{colors[1]}'></span>PAWP</span>"
    )
    return eng.render(legend)


def svg_delta_bars(
    items: List[Tuple[str, Optional[float]]],
    title: str,
    unit: str,
    note: Optional[str] = None
) -> str:
    """Diverging Bar Chart."""
    clean = [(k, _safe_float(v)) for k, v in items if _safe_float(v) is not None]
    if not clean: return ""
    
    vals = [v for _, v in clean] # type: ignore
    max_abs = max([abs(v) for v in vals]) if vals else 1.0
    if max_abs == 0: max_abs = 1.0
    
    h = 60 + len(clean) * 36
    eng = SvgEngine(760, h, title, unit + (f" • {note}" if note else ""))
    
    cx = eng.ml + eng.pw / 2
    scale = (eng.pw / 2 - 20) / max_abs
    
    # Zero Line
    eng.add(f"<line x1='{cx:.1f}' y1='{eng.mt}' x2='{cx:.1f}' y2='{eng.h - eng.mb}' stroke='rgba(0,0,0,0.2)' stroke-dasharray='4,2'/>")
    
    for i, (label, val) in enumerate(clean):
        y = eng.mt + i * 36 + 18
        v = float(val) # type: ignore
        w = abs(v) * scale
        
        # Color: Positive (Orange), Negative (Blue) - Clinical generic
        col = SvgTheme().colors[1] if v >= 0 else SvgTheme().colors[0]
        x_rect = cx if v >= 0 else cx - w
        
        eng.add(f"<text x='{eng.ml - 10}' y='{y + 4}' font-size='11' fill='#1f2937' text-anchor='end'>{html.escape(label)}</text>")
        eng.add(f"<rect x='{x_rect:.1f}' y='{y - 7}' width='{w:.1f}' height='14' rx='3' fill='{col}'/>")
        
        x_txt = cx + w + 6 if v >= 0 else cx - w - 6
        anchor = "start" if v >= 0 else "end"
        eng.add(f"<text x='{x_txt:.1f}' y='{y + 4}' font-size='11' fill='#4b5563' text-anchor='{anchor}'>{v:+.1f}</text>")
        
    return eng.render()


def svg_compare_bars(
    items: List[Tuple[str, Optional[float], Optional[float]]],
    title: str,
    unit: str,
    labels: Tuple[str, str] = ("Vorher", "Jetzt"),
) -> str:
    """Grouped Bar Chart."""
    clean = []
    max_v = 0.0
    for n, v1, v2 in items:
        f1, f2 = _safe_float(v1), _safe_float(v2)
        if f1 is not None and f2 is not None:
            clean.append((n, f1, f2))
            max_v = max(max_v, f1, f2)
            
    if not clean: return ""
    if max_v == 0: max_v = 1.0
    
    eng = SvgEngine(760, 60 + len(clean) * 50, title, unit)
    eng.ml = 140 # More space for labels
    eng.pw = eng.w - eng.ml - eng.mr
    
    scale = eng.pw / max_v
    c1, c2 = "#9ca3af", SvgTheme().colors[0] # Grey -> Blue
    
    for i, (name, v1, v2) in enumerate(clean):
        y = eng.mt + i * 50
        w1, w2 = v1 * scale, v2 * scale
        
        eng.add(f"<text x='{eng.ml - 12}' y='{y + 20}' font-size='11' fill='#1f2937' text-anchor='end'>{html.escape(name)}</text>")
        
        # Bar 1
        eng.add(f"<rect x='{eng.ml}' y='{y}' width='{w1:.1f}' height='10' rx='3' fill='{c1}' opacity='0.7'/>")
        eng.add(f"<text x='{eng.ml + w1 + 6:.1f}' y='{y + 9}' font-size='10' fill='#6b7280'>{v1:.1f}</text>")
        
        # Bar 2
        eng.add(f"<rect x='{eng.ml}' y='{y + 14}' width='{w2:.1f}' height='10' rx='3' fill='{c2}'/>")
        eng.add(f"<text x='{eng.ml + w2 + 6:.1f}' y='{y + 23}' font-size='10' fill='#1f2937' font-weight='600'>{v2:.1f}</text>")
        
    legend = (
        f"<span><span class='d' style='background:{c1};opacity:0.7'></span>{html.escape(labels[0])}</span>"
        f"<span><span class='d' style='background:{c2}'></span>{html.escape(labels[1])}</span>"
    )
    return eng.render(legend)