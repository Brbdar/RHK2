#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import math

# Note: no external plotting dependencies. We output compact SVG snippets.

def _num(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None

def _esc(s: Any) -> str:
    t = "" if s is None else str(s)
    return (t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&#39;"))

def _minmax(vals: List[Optional[float]]) -> Tuple[float, float]:
    vv = [v for v in vals if isinstance(v, (int,float)) and math.isfinite(v)]
    if not vv:
        return (0.0, 1.0)
    mn = min(vv)
    mx = max(vv)
    if mn == mx:
        return (mn - 1.0, mx + 1.0)
    pad = 0.08 * (mx - mn)
    return (mn - pad, mx + pad)

def svg_series_over_phases(
    phases: List[str],
    series: Dict[str, List[Optional[float]]],
    title: str,
    y_label: str,
    height: int = 220,
) -> str:
    """Line chart where x is categorical phases."""
    w = 760
    h = max(160, int(height))
    pad_l, pad_r, pad_t, pad_b = 52, 16, 34, 34
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    all_vals: List[Optional[float]] = []
    for svals in series.values():
        all_vals.extend(svals)
    y0, y1 = _minmax(all_vals)

    def ypix(v: float) -> float:
        return pad_t + (y1 - v) / (y1 - y0) * plot_h if (y1 - y0) != 0 else pad_t + plot_h/2

    def xpix(i: int) -> float:
        if len(phases) <= 1:
            return pad_l + plot_w/2
        return pad_l + i/(len(phases)-1) * plot_w

    # colors via CSS variables (modern, but not overloaded)
    css = """
<style>
.rhk-viz-card{border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;background:#fff}
.rhk-viz-title{font-weight:700;margin:0 0 6px 0}
.rhk-viz-sub{color:rgba(0,0,0,.65);font-size:12px;margin:0 0 10px 0}
.rhk-viz-legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:12px;color:rgba(0,0,0,.75)}
.rhk-viz-dot{display:inline-block;width:10px;height:10px;border-radius:99px;margin-right:6px;vertical-align:-1px}
</style>
"""
    svg_parts = []
    # grid
    ticks = 4
    for t in range(ticks+1):
        y = pad_t + t/ticks*plot_h
        val = y1 - t/ticks*(y1-y0)
        svg_parts.append(f"<line x1='{pad_l}' y1='{y:.2f}' x2='{w-pad_r}' y2='{y:.2f}' stroke='rgba(0,0,0,.06)'/>")
        svg_parts.append(f"<text x='{pad_l-8}' y='{y+4:.2f}' font-size='11' fill='rgba(0,0,0,.55)' text-anchor='end'>{val:.1f}</text>")

    # axes labels
    for i, ph in enumerate(phases):
        x = xpix(i)
        svg_parts.append(f"<text x='{x:.2f}' y='{h-12}' font-size='11' fill='rgba(0,0,0,.60)' text-anchor='middle'>{_esc(ph)}</text>")

    # draw series
    palette = [
        "var(--rhk-c1, #1f77b4)",
        "var(--rhk-c2, #ff7f0e)",
        "var(--rhk-c3, #2ca02c)",
        "var(--rhk-c4, #d62728)",
        "var(--rhk-c5, #9467bd)",
    ]
    legend_html = []
    for si, (name, vals) in enumerate(series.items()):
        col = palette[si % len(palette)]
        pts = []
        for i, v in enumerate(vals):
            if v is None:
                pts.append(None)
                continue
            pts.append((xpix(i), ypix(float(v))))
        # path with gaps
        d = ""
        started = False
        for p in pts:
            if p is None:
                started = False
                continue
            x, y = p
            if not started:
                d += f"M {x:.2f} {y:.2f} "
                started = True
            else:
                d += f"L {x:.2f} {y:.2f} "
        if d.strip():
            svg_parts.append(f"<path d='{d.strip()}' fill='none' stroke='{col}' stroke-width='2.2'/>")
        # points
        for i,p in enumerate(pts):
            if p is None:
                continue
            x,y = p
            lab = phases[i]
            val = vals[i]
            svg_parts.append(
                f"<circle cx='{x:.2f}' cy='{y:.2f}' r='3.8' fill='{col}'>"
                f"<title>{_esc(name)} {lab}: {val}</title></circle>"
            )
        legend_html.append(f"<span><span class='rhk-viz-dot' style='background:{col}'></span>{_esc(name)}</span>")

    svg = (
        f"{css}"
        f"<div class='rhk-viz-card'>"
        f"<p class='rhk-viz-title'>{_esc(title)}</p>"
        f"<p class='rhk-viz-sub'>{_esc(y_label)}</p>"
        f"<svg width='100%' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet'>"
        + "".join(svg_parts) +
        f"<text x='{pad_l}' y='{16}' font-size='12' fill='rgba(0,0,0,.65)'>{_esc(y_label)}</text>"
        f"</svg>"
        f"<div class='rhk-viz-legend'>" + "".join(legend_html) + "</div>"
        f"</div>"
    )
    return svg


def svg_mpap_pawp_vs_co(
    mpap_rest: Optional[float],
    pawp_rest: Optional[float],
    co_rest: Optional[float],
    mpap_peak: Optional[float],
    pawp_peak: Optional[float],
    co_peak: Optional[float],
    title: str,
) -> str:
    """Two line segments: mPAP vs CO and PAWP vs CO (rest -> peak)."""
    # require rest and peak co to show trend
    if co_rest is None or co_peak is None:
        return ""
    xs = [co_rest, co_peak]
    ys = []
    for v in (mpap_rest, mpap_peak, pawp_rest, pawp_peak):
        if v is not None:
            ys.append(float(v))
    y0, y1 = _minmax(ys)
    x0, x1 = _minmax([float(co_rest), float(co_peak)])

    w, h = 760, 250
    pad_l, pad_r, pad_t, pad_b = 54, 16, 34, 34
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    def xpix(v: float) -> float:
        return pad_l + (v - x0) / (x1 - x0) * plot_w if (x1-x0)!=0 else pad_l + plot_w/2
    def ypix(v: float) -> float:
        return pad_t + (y1 - v) / (y1 - y0) * plot_h if (y1-y0)!=0 else pad_t + plot_h/2

    css = """
<style>
.rhk-viz-card{border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;background:#fff}
.rhk-viz-title{font-weight:700;margin:0 0 6px 0}
.rhk-viz-sub{color:rgba(0,0,0,.65);font-size:12px;margin:0 0 10px 0}
.rhk-viz-legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:12px;color:rgba(0,0,0,.75)}
.rhk-viz-dot{display:inline-block;width:10px;height:10px;border-radius:99px;margin-right:6px;vertical-align:-1px}
</style>
"""
    svg_parts = []
    # grid y
    ticks = 4
    for t in range(ticks+1):
        y = pad_t + t/ticks*plot_h
        val = y1 - t/ticks*(y1-y0)
        svg_parts.append(f"<line x1='{pad_l}' y1='{y:.2f}' x2='{w-pad_r}' y2='{y:.2f}' stroke='rgba(0,0,0,.06)'/>")
        svg_parts.append(f"<text x='{pad_l-8}' y='{y+4:.2f}' font-size='11' fill='rgba(0,0,0,.55)' text-anchor='end'>{val:.1f}</text>")
    # grid x + labels
    for t in range(ticks+1):
        x = pad_l + t/ticks*plot_w
        val = x0 + t/ticks*(x1-x0)
        svg_parts.append(f"<line x1='{x:.2f}' y1='{pad_t}' x2='{x:.2f}' y2='{h-pad_b}' stroke='rgba(0,0,0,.05)'/>")
        svg_parts.append(f"<text x='{x:.2f}' y='{h-12}' font-size='11' fill='rgba(0,0,0,.60)' text-anchor='middle'>{val:.1f}</text>")

    # series
    palette = {
        "mPAP": "var(--rhk-c1, #1f77b4)",
        "PAWP": "var(--rhk-c2, #ff7f0e)",
    }
    def draw(name: str, y_rest: Optional[float], y_peak: Optional[float]):
        if y_rest is None or y_peak is None:
            return
        col = palette[name]
        xA, yA = xpix(float(co_rest)), ypix(float(y_rest))
        xB, yB = xpix(float(co_peak)), ypix(float(y_peak))
        svg_parts.append(f"<path d='M {xA:.2f} {yA:.2f} L {xB:.2f} {yB:.2f}' fill='none' stroke='{col}' stroke-width='2.2'/>")
        svg_parts.append(f"<circle cx='{xA:.2f}' cy='{yA:.2f}' r='4.2' fill='{col}'><title>{name} Rest: {y_rest}</title></circle>")
        svg_parts.append(f"<circle cx='{xB:.2f}' cy='{yB:.2f}' r='4.2' fill='{col}'><title>{name} Peak: {y_peak}</title></circle>")

    draw("mPAP", mpap_rest, mpap_peak)
    draw("PAWP", pawp_rest, pawp_peak)

    legend = (
        f"<span><span class='rhk-viz-dot' style='background:{palette['mPAP']}'></span>mPAP</span>"
        f"<span><span class='rhk-viz-dot' style='background:{palette['PAWP']}'></span>PAWP</span>"
    )
    svg = (
        f"{css}"
        f"<div class='rhk-viz-card'>"
        f"<p class='rhk-viz-title'>{_esc(title)}</p>"
        f"<p class='rhk-viz-sub'>Druck gegen HZV (Rest und Peak)</p>"
        f"<svg width='100%' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet'>"
        + "".join(svg_parts) +
        f"<text x='{pad_l}' y='{16}' font-size='12' fill='rgba(0,0,0,.65)'>HZV (l/min) und Druck (mmHg)</text>"
        f"</svg>"
        f"<div class='rhk-viz-legend'>{legend}</div>"
        f"</div>"
    )
    return svg


def svg_delta_bars(
    items: List[Tuple[str, Optional[float]]],
    title: str,
    unit: str,
    note: str | None = None,
) -> str:
    """Simple horizontal bar chart for deltas (positive right, negative left)."""
    vals = [v for _n, v in items if v is not None and math.isfinite(float(v))]
    if not vals:
        return ""
    mx = max(abs(float(v)) for v in vals) or 1.0
    w, h = 760, 260
    pad_l, pad_r, pad_t, pad_b = 160, 16, 34, 22
    row_h = 34
    plot_w = w - pad_l - pad_r
    center = pad_l + plot_w/2

    css = """
<style>
.rhk-viz-card{border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;background:#fff}
.rhk-viz-title{font-weight:700;margin:0 0 6px 0}
.rhk-viz-sub{color:rgba(0,0,0,.65);font-size:12px;margin:0 0 10px 0}
</style>
"""
    svg_parts = []
    # center line
    svg_parts.append(f"<line x1='{center:.2f}' y1='{pad_t}' x2='{center:.2f}' y2='{h-pad_b}' stroke='rgba(0,0,0,.18)'/>")

    for i, (name, v) in enumerate(items):
        y = pad_t + i*row_h + 10
        svg_parts.append(f"<text x='{pad_l-10}' y='{y+10:.2f}' font-size='12' fill='rgba(0,0,0,.75)' text-anchor='end'>{_esc(name)}</text>")
        if v is None:
            svg_parts.append(f"<text x='{center+6:.2f}' y='{y+10:.2f}' font-size='12' fill='rgba(0,0,0,.45)'>–</text>")
            continue
        vv = float(v)
        bar_len = abs(vv)/mx * (plot_w/2 - 10)
        x = center if vv >= 0 else center - bar_len
        col = "var(--rhk-c2, #ff7f0e)" if vv >= 0 else "var(--rhk-c1, #1f77b4)"
        svg_parts.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{bar_len:.2f}' height='14' rx='6' fill='{col}'/>")
        svg_parts.append(f"<text x='{center + (bar_len + 8 if vv>=0 else -(bar_len+8)):.2f}' y='{y+12:.2f}' font-size='12' fill='rgba(0,0,0,.70)' text-anchor={'start' if vv>=0 else 'end'}>{vv:+.2f}</text>")

    note_html = ""
    if note:
        note_html = f"<p class='rhk-viz-sub'>{_esc(note)}</p>"

    svg = (
        f"{css}"
        f"<div class='rhk-viz-card'>"
        f"<p class='rhk-viz-title'>{_esc(title)}</p>"
        f"<p class='rhk-viz-sub'>{_esc(unit)}</p>"
        f"{note_html}"
        f"<svg width='100%' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet'>"
        + "".join(svg_parts) +
        f"</svg>"
        f"</div>"
    )
    return svg


def svg_compare_bars(
    items: List[Tuple[str, Optional[float], Optional[float]]],
    title: str,
    unit: str,
    labels: Tuple[str, str] = ("Vorher", "Jetzt"),
) -> str:
    """Two horizontal bars per row: previous vs current (absolute values)."""
    vv = []
    cleaned = []
    for name, a, b in items:
        if a is None or b is None:
            continue
        try:
            fa = float(a)
            fb = float(b)
            if not (math.isfinite(fa) and math.isfinite(fb)):
                continue
            cleaned.append((name, fa, fb))
            vv.extend([fa, fb])
        except Exception:
            continue
    if not cleaned:
        return ""
    mx = max(vv) if vv else 1.0
    if mx <= 0:
        mx = 1.0

    w = 760
    pad_l, pad_r, pad_t, pad_b = 160, 16, 34, 26
    row_h = 44
    h = pad_t + pad_b + row_h * len(cleaned)
    plot_w = w - pad_l - pad_r
    bar_h = 10
    gap = 6

    col_prev = "var(--rhk-c1, #1f77b4)"
    col_cur = "var(--rhk-c2, #ff7f0e)"

    css = """
<style>
.rhk-viz-card{border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;background:#fff}
.rhk-viz-title{font-weight:700;margin:0 0 6px 0}
.rhk-viz-sub{color:rgba(0,0,0,.65);font-size:12px;margin:0 0 10px 0}
.rhk-viz-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:12px;color:rgba(0,0,0,.75)}
.rhk-viz-dot{display:inline-block;width:10px;height:10px;border-radius:99px;margin-right:6px;vertical-align:-1px}
</style>
"""

    svg_parts = []
    # x axis baseline
    svg_parts.append(f"<line x1='{pad_l}' y1='{pad_t-4}' x2='{w-pad_r}' y2='{pad_t-4}' stroke='rgba(0,0,0,.06)'/>")

    for i, (name, a, b) in enumerate(cleaned):
        y0 = pad_t + i * row_h
        svg_parts.append(
            f"<text x='{pad_l-10}' y='{y0+18}' font-size='12' fill='rgba(0,0,0,.75)' text-anchor='end'>{_esc(name)}</text>"
        )

        wa = (a / mx) * plot_w
        wb = (b / mx) * plot_w

        y_prev = y0 + 8
        y_cur = y_prev + bar_h + gap
        svg_parts.append(f"<rect x='{pad_l}' y='{y_prev:.2f}' width='{wa:.2f}' height='{bar_h}' rx='6' fill='{col_prev}'/>")
        svg_parts.append(f"<rect x='{pad_l}' y='{y_cur:.2f}' width='{wb:.2f}' height='{bar_h}' rx='6' fill='{col_cur}'/>")

        svg_parts.append(
            f"<text x='{pad_l + wa + 8:.2f}' y='{y_prev + bar_h:.2f}' font-size='12' fill='rgba(0,0,0,.70)' text-anchor='start'>{a:.2f}</text>"
        )
        svg_parts.append(
            f"<text x='{pad_l + wb + 8:.2f}' y='{y_cur + bar_h:.2f}' font-size='12' fill='rgba(0,0,0,.70)' text-anchor='start'>{b:.2f}</text>"
        )

    legend = (
        f"<span><span class='rhk-viz-dot' style='background:{col_prev}'></span>{_esc(labels[0])}</span>"
        f"<span><span class='rhk-viz-dot' style='background:{col_cur}'></span>{_esc(labels[1])}</span>"
    )

    svg = (
        f"{css}"
        f"<div class='rhk-viz-card'>"
        f"<p class='rhk-viz-title'>{_esc(title)}</p>"
        f"<p class='rhk-viz-sub'>{_esc(unit)}</p>"
        f"<svg width='100%' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet'>"
        + "".join(svg_parts) +
        f"</svg>"
        f"<div class='rhk-viz-legend'>{legend}</div>"
        f"</div>"
    )
    return svg
