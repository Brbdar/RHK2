#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-RHK one-page PDF overview (A4 landscape).

Purpose
- Print immediately BEFORE right-heart catheterization.
- Show only essential information already available pre-procedure.
- No recommendations, no therapy, no RHK result interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import os
import tempfile
import uuid
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors

# PH Therapieepisoden (restart-fähig, konsistent)
from rhk_ph_tx import (
    parse_ph_tx_table_rows,
    legacy_lists_to_episodes,
)


# --- Pre-RHK PDF layout constants (compact, one-page) ---
BOX_PAD_X = 6 * mm
BOX_PAD_TOP = 12 * mm
BOX_PAD_BOTTOM = 6 * mm
BOX_GAP_Y = 3 * mm
LINE_TIGHTEN = 0.96  # slightly tighter line spacing for dense boxes


def _get(d: Any, key: str, default=None):
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def _fmt_num(val, ndigits: int = 0) -> Optional[str]:
    try:
        if val is None:
            return None
        f = float(val)
        if ndigits == 0:
            if abs(f - round(f)) < 1e-6:
                return str(int(round(f)))
            return f"{f:.1f}"
        return f"{f:.{ndigits}f}"
    except Exception:
        return None


def _fmt(val, unit: str = "", ndigits: int = 0) -> Optional[str]:
    s = _fmt_num(val, ndigits=ndigits)
    if s is None:
        return None
    return f"{s}{(' ' + unit) if unit else ''}"


def _arrow(flag: Optional[str]) -> str:
    # flag in {"up","down","warn","bad",None}
    return {"up": "↑", "down": "↓", "warn": "⚠", "bad": "⬆"}.get(flag or "", "")


def _is_truthy(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, bool):
        return bool(x)
    s = str(x).strip().lower()
    return s in {"1","true","yes","ja","y","j"}


def _pick_top(items: List[str], n: int) -> List[str]:
    out=[]
    for it in items:
        it=str(it).strip()
        if not it or it.lower() in {"keine","keine angabe","-"}:
            continue
        if it not in out:
            out.append(it)
        if len(out) >= n:
            break
    return out


def _norm_list(x: Any) -> List[str]:
    """Normalize a UI value that may be a list/tuple or comma-separated string."""
    if x is None:
        return []
    if isinstance(x, str):
        return [s.strip() for s in x.split(",") if s.strip()]
    if isinstance(x, (list, tuple)):
        return [str(s).strip() for s in x if str(s).strip()]
    s = str(x).strip()
    return [s] if s else []


def _draw_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str):
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 6*mm, y + h - 8*mm, title)


def _draw_box_small(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str):
    """Slightly smaller box title for short-height boxes (e.g. bottom strip)."""
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    # Title sits a bit higher to free vertical space for the content.
    c.drawString(x + 6*mm, y + h - 6.5*mm, title)


def _draw_kv_lines(c: canvas.Canvas, x: float, y_top: float, lines: List[Tuple[str,str]], line_h: float = 6.2*mm, max_lines: int = 10, font_size: int = 10):
    c.setFont("Helvetica", font_size)
    y = y_top
    shown=0
    for k,v in lines:
        if shown >= max_lines:
            break
        if not v:
            continue
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x, y, k)
        c.setFillColor(colors.black)
        c.drawRightString(x + 80*mm, y, v)
        y -= line_h
        shown += 1
    return y


def _chip(c: canvas.Canvas, x: float, y: float, text: str):
    # small rounded label (compact)
    pad_x = 3.0 * mm
    pad_y = 1.4 * mm
    fs = 8
    c.setFont("Helvetica", fs)
    tw = c.stringWidth(text, "Helvetica", fs)
    w = tw + 2 * pad_x
    h = 5.6 * mm
    c.setFillColor(colors.HexColor("#f0f0f0"))
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.drawString(x + pad_x, y + pad_y, text)
    return x + w + 2 * mm


def _chip_draw(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    *,
    fs: int = 8,
    h: float = 5.6 * mm,
    pad_x: float = 3.0 * mm,
    pad_y: float = 1.4 * mm,
) -> float:
    """Draw a chip with configurable font size and return the next x."""
    c.setFont("Helvetica", fs)
    tw = c.stringWidth(text, "Helvetica", fs)
    w = tw + 2 * pad_x
    c.setFillColor(colors.HexColor("#f0f0f0"))
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(x, y, w, h, 3, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.drawString(x + pad_x, y + pad_y, text)
    return x + w + 2 * mm


def _chip_width(c: canvas.Canvas, text: str, *, fs: int = 8, pad_x: float = 3.0 * mm) -> float:
    """Width of a chip in points, consistent with _chip_draw()."""
    c.setFont("Helvetica", fs)
    tw = c.stringWidth(str(text), "Helvetica", fs)
    return tw + 2 * pad_x + 2 * mm


def _metric_box(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    label: str,
    value: str,
    sub: str = "",
) -> None:
    """Draw a prominent metric inside a fixed box (safe if value is empty)."""
    pad_x = 7 * mm
    pad_top = 14 * mm
    y0 = y_top - pad_top
    y_min = y_top - h_box + 6 * mm

    # Label
    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_box + pad_x, y0, label)

    # Value (big)
    y0 -= 8.5 * mm
    if y0 < y_min:
        return
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x_box + pad_x, y0, value or "–")

    # Subline
    if sub:
        y0 -= 7.0 * mm
        if y0 < y_min:
            return
        c.setFillColor(colors.HexColor("#444444"))
        c.setFont("Helvetica", 10)
        c.drawString(x_box + pad_x, y0, sub)


def _wrap_text(c: canvas.Canvas, text: str, font_name: str, font_size: int, max_width: float) -> List[str]:
    """Greedy word-wrap using ReportLab font metrics."""
    if text is None:
        return []
    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    out: List[str] = []
    for para in s.split("\n"):
        para = para.strip()
        if not para:
            out.append("")
            continue
        words = para.split()
        line = ""
        for w in words:
            cand = (line + " " + w).strip() if line else w
            if c.stringWidth(cand, font_name, font_size) <= max_width:
                line = cand
            else:
                if line:
                    out.append(line)
                # If a single token is longer than max_width, hard-split it.
                if c.stringWidth(w, font_name, font_size) <= max_width:
                    line = w
                else:
                    buf = ""
                    for ch in w:
                        cand2 = buf + ch
                        if c.stringWidth(cand2, font_name, font_size) <= max_width:
                            buf = cand2
                        else:
                            if buf:
                                out.append(buf)
                            buf = ch
                    line = buf
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return out

def _build_text_lines_for_box(c: canvas.Canvas, raw: str, font_name: str, fs: int, avail_w: float) -> List[str]:
    raw = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.strip() if raw is not None else ""
    if not raw:
        raw = "–"
    paras = [p.rstrip() for p in raw.splitlines()]
    out: List[str] = []
    for p in paras:
        if not p.strip():
            out.append("")
            continue
        out.extend(_wrap_text(c, p.strip(), font_name, fs, avail_w))
        out.append("")
    while out and out[-1] == "":
        out.pop()
    return out


def _needed_height_text(c: canvas.Canvas, text: str, w_box: float, *, fs: int, base_fs: int, line_h: float, pad_x: float, pad_top: float, pad_bottom: float) -> float:
    avail_w = max(10 * mm, w_box - 2 * pad_x)
    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
    lines = _build_text_lines_for_box(c, text, "Helvetica", fs, avail_w)
    total = pad_top + pad_bottom
    for ln in lines:
        total += (lh * 0.6) if ln == "" else lh
    return total


def _needed_height_bullets(c: canvas.Canvas, bullets: List[str], w_box: float, *, fs: int, base_fs: int, line_h: float, pad_x: float, pad_top: float, pad_bottom: float) -> float:
    bullets_in = [str(b).strip() for b in (bullets or []) if str(b).strip()]
    if not bullets_in:
        bullets_in = ["–"]
    avail_w = max(10 * mm, w_box - 2 * pad_x)
    indent = 4.5 * mm
    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
    total = pad_top + pad_bottom
    for b in bullets_in:
        lines = _wrap_text(c, b, "Helvetica", fs, avail_w - indent) or [""]
        total += len(lines) * lh
    return total


def _needed_height_kv(c: canvas.Canvas, pairs: List[Tuple[str, str]], w_box: float, *, fs: int, base_fs: int, line_h: float, pad_x: float, pad_top: float, pad_bottom: float, key_w: float) -> float:
    pairs_in: List[Tuple[str, str]] = []
    for k, v in (pairs or []):
        k = str(k).strip()
        v = str(v).strip() if v is not None else ""
        if v:
            pairs_in.append((k, v))
    if not pairs_in:
        pairs_in = [("–", "")]
    value_w = max(10 * mm, w_box - 2 * pad_x - key_w)
    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
    total = pad_top + pad_bottom
    for _k, v in pairs_in:
        v_lines = _wrap_text(c, v, "Helvetica", fs, value_w) or [""]
        total += len(v_lines) * lh
    return total



def _draw_bullets_wrapped(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    bullets: List[str],
    font_size: int = 10,
    line_h: float = 6.2 * mm,
    pad_x: float = BOX_PAD_X,
    pad_top: float = BOX_PAD_TOP,
    *,
    min_font_size: int = 6,
    return_overflow: bool = False,
) -> Optional[List[str]]:
    """Draw bullet list inside a fixed box area with wrapping.

    Strict: never silently omit content and never spill onto a second page.
    Strategy: reduce font size until everything fits (down to 5pt, then 3pt in extreme cases).
    """
    bullets_in = [str(b).strip() for b in (bullets or []) if str(b).strip()]
    if not bullets_in:
        bullets_in = ["–"]

    y_min = y_top - h_box + BOX_PAD_BOTTOM
    avail_w = max(10 * mm, w_box - 2 * pad_x)
    indent = 4.5 * mm

    base_fs = int(font_size)

    def _fits(fs: int) -> bool:
        lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
        y = y_top - pad_top
        for b in bullets_in:
            lines = _wrap_text(c, b, "Helvetica", fs, avail_w - indent) or [""]
            for _ln in lines:
                if y < y_min:
                    return False
                y -= lh
        return True

    fs = int(font_size)
    floor = max(5, int(min_font_size))
    while (not _fits(fs)) and fs > floor:
        fs -= 1
    while (not _fits(fs)) and fs > 3:
        fs -= 1

    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN

    c.setFont("Helvetica", fs)
    c.setFillColor(colors.black)

    y = y_top - pad_top
    for b in bullets_in:
        lines = _wrap_text(c, b, "Helvetica", fs, avail_w - indent) or [""]
        # first line with bullet
        c.drawString(x_box + pad_x, y, "•")
        c.drawString(x_box + pad_x + indent, y, lines[0])
        y -= lh
        for ln in lines[1:]:
            c.drawString(x_box + pad_x + indent, y, ln)
            y -= lh

    # keep legacy return type for callers, but always None (no overflow printing)
    return None

def _draw_text_wrapped(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    text: str,
    font_size: int = 10,
    line_h: float = 6.2 * mm,
    pad_x: float = BOX_PAD_X,
    pad_top: float = BOX_PAD_TOP,
    *,
    min_font_size: int = 6,
) -> Optional[str]:
    """Draw wrapped text inside a fixed box.

    Strict: never silently omit content and never spill onto a second page.
    Strategy: reduce font size until everything fits (down to 5pt, then 3pt in extreme cases).
    """
    raw = str(text or "").strip()
    if not raw:
        raw = "–"

    avail_w = max(10 * mm, w_box - 2 * pad_x)
    y_start = y_top - pad_top
    y_min = y_top - h_box + BOX_PAD_BOTTOM

    base_fs = int(font_size)

    def _fits(fs: int) -> bool:
        lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
        y = y_start
        lines = _build_text_lines_for_box(c, raw, "Helvetica", fs, avail_w)
        for ln in lines:
            if y < y_min:
                return False
            y -= (lh * 0.6) if ln == "" else lh
        return True

    fs = int(font_size)
    floor = max(5, int(min_font_size))
    while (not _fits(fs)) and fs > floor:
        fs -= 1
    while (not _fits(fs)) and fs > 3:
        fs -= 1

    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
    lines = _build_text_lines_for_box(c, raw, "Helvetica", fs, avail_w)

    c.setFont("Helvetica", fs)
    c.setFillColor(colors.black)

    y = y_start
    for ln in lines:
        if ln == "":
            y -= lh * 0.6
            continue
        c.drawString(x_box + pad_x, y, ln)
        y -= lh

    return None

def _draw_kv_wrapped(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    pairs: List[Tuple[str, str]],
    font_size: int = 10,
    line_h: float = 6.0 * mm,
    pad_x: float = BOX_PAD_X,
    pad_top: float = BOX_PAD_TOP,
    key_w: float = 38 * mm,
    *,
    min_font_size: int = 6,
) -> Optional[List[Tuple[str, str]]]:
    """Draw key/value lines inside a fixed box with wrapping.

    Strict: never silently omit content and never spill onto a second page.
    Strategy: reduce font size until everything fits (down to 5pt, then 3pt in extreme cases).
    """
    pairs_in: List[Tuple[str, str]] = []
    for k, v in (pairs or []):
        k = str(k).strip()
        v = str(v).strip() if v is not None else ""
        if v:
            pairs_in.append((k, v))
    if not pairs_in:
        pairs_in = [("–", "")]

    y_start = y_top - pad_top
    y_min = y_top - h_box + BOX_PAD_BOTTOM
    value_x = x_box + pad_x + key_w
    value_w = max(10 * mm, w_box - 2 * pad_x - key_w)

    base_fs = int(font_size)

    def _fits(fs: int) -> bool:
        lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN
        y = y_start
        for _k, v in pairs_in:
            v_lines = _wrap_text(c, v, "Helvetica", fs, value_w) or [""]
            for _ln in v_lines:
                if y < y_min:
                    return False
                y -= lh
        return True

    fs = int(font_size)
    floor = max(5, int(min_font_size))
    while (not _fits(fs)) and fs > floor:
        fs -= 1
    while (not _fits(fs)) and fs > 3:
        fs -= 1

    lh = line_h * (fs / max(1, base_fs)) * LINE_TIGHTEN

    c.setFont("Helvetica", fs)

    y = y_start
    for k, v in pairs_in:
        v_lines = _wrap_text(c, v, "Helvetica", fs, value_w) or [""]
        c.setFillColor(colors.HexColor("#222222"))
        c.drawString(x_box + pad_x, y, k)
        c.setFillColor(colors.black)
        c.drawString(value_x, y, v_lines[0])
        y -= lh
        for ln in v_lines[1:]:
            c.setFillColor(colors.black)
            c.drawString(value_x, y, ln)
            y -= lh

    return None

def _draw_text_wrapped_block(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    text: str,
    font_size: int = 10,
    line_h: float = 6.0 * mm,
    pad_x: float = 6 * mm,
    pad_top: float = 13 * mm,
) -> Optional[str]:
    """Backward compatible wrapper for older call sites.

    Uses _draw_text_wrapped to avoid silent truncation.
    Returns overflow text (if any).
    """
    return _draw_text_wrapped(
        c,
        x_box,
        y_top,
        w_box,
        h_box,
        text,
        font_size=font_size,
        line_h=line_h,
        pad_x=pad_x,
        pad_top=pad_top,
        min_font_size=6,
    )


def _draw_prev_rhk_base_compact(
    c: canvas.Canvas,
    x_box: float,
    y_top: float,
    w_box: float,
    h_box: float,
    *,
    prev_rhk_date: str,
    prev_is_initial: Any,
    prev_mpap: Any,
    prev_pawp: Any,
    prev_rap: Any,
    prev_spap: Any,
    prev_dpap: Any,
    prev_co: Any,
    prev_ci: Any,
    prev_pvr: Any,
    prev_label: str,
) -> None:
    """Compact, highly readable Vor-RHK baseline block.

    Ziel: unmittelbar vor dem RHK schnell scannbar, ohne stilles Kürzen.
    Formatierung als Mini-Grid (Drucke + Fluss/Resistenz) statt Fließtext.
    """
    # Bottom strip boxes are much shorter than the main 3-column boxes.
    # Therefore we use a tighter internal padding to keep baseline values readable.
    pad_x = BOX_PAD_X
    # Padding needs to clear the box title (drawn inside the border).
    pad_top = 10 * mm
    pad_bottom = 3 * mm

    y = y_top - pad_top
    y_min = y_top - h_box + pad_bottom

    avail_w = max(10 * mm, w_box - 2 * pad_x)
    xL = x_box + pad_x

    # Build baseline items (keep order, omit empty) grouped for readability.
    # Left: date + pressures. Right: status + flow/resistance.
    left: List[Tuple[str, str]] = []
    right: List[Tuple[str, str]] = []

    if str(prev_rhk_date or "").strip():
        left.append(("Vor-RHK", str(prev_rhk_date).strip()))
    if _is_truthy(prev_is_initial):
        right.append(("Initial", "ja"))

    # Pressures
    if _fmt_num(prev_spap) is not None or _fmt_num(prev_dpap) is not None:
        sp = _fmt_num(prev_spap)
        dp = _fmt_num(prev_dpap)
        if sp is not None and dp is not None:
            left.append(("PAP", f"{sp}/{dp} mmHg"))
        elif sp is not None:
            left.append(("sPAP", f"{sp} mmHg"))
        elif dp is not None:
            left.append(("dPAP", f"{dp} mmHg"))
    if _fmt_num(prev_mpap) is not None:
        left.append(("mPAP", f"{_fmt_num(prev_mpap)} mmHg"))
    if _fmt_num(prev_pawp) is not None:
        left.append(("PAWP", f"{_fmt_num(prev_pawp)} mmHg"))
    if _fmt_num(prev_rap) is not None:
        left.append(("RAP", f"{_fmt_num(prev_rap)} mmHg"))

    # Flow / resistance
    if _fmt_num(prev_co) is not None:
        right.append(("CO", f"{_fmt_num(prev_co)} L/min"))
    if _fmt_num(prev_ci) is not None:
        right.append(("CI", f"{_fmt_num(prev_ci)} L/min/m²"))
    if _fmt_num(prev_pvr) is not None:
        right.append(("PVR", f"{_fmt_num(prev_pvr)} WU"))

    label = str(prev_label or "").strip()

    # If the strip is very short (e.g. no handwrite box), use one compact line.
    if h_box <= (22 * mm):
        parts: List[str] = []
        for k, v in (left + right):
            if v:
                parts.append(f"{k} {v}")
        line = " · ".join(parts) if parts else "–"
        if label:
            line = line + "\n" + f"Kommentar: {label}"
        _draw_text_wrapped(
            c,
            x_box,
            y_top,
            w_box,
            h_box,
            line,
            font_size=8,
            line_h=4.2 * mm,
            pad_x=pad_x,
            pad_top=pad_top,
            min_font_size=5,
        )
        return

    # --- Mini-grid for taller strip (readability first) ---
    # Header line: date + initial flag
    fs_head = 9
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", fs_head)
    head_left = f"Vor-RHK: {str(prev_rhk_date).strip()}" if str(prev_rhk_date or "").strip() else "Vor-RHK: –"
    c.drawString(xL, y, head_left)
    if _is_truthy(prev_is_initial):
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#222222"))
        c.drawRightString(x_box + w_box - pad_x, y, "Initial: ja")

    # Grid rows
    y -= 6.0 * mm

    def _cell(xc: float, yc: float, label_txt: str, value_txt: str) -> None:
        c.setFillColor(colors.HexColor("#444444"))
        c.setFont("Helvetica", 6)
        c.drawString(xc, yc, label_txt)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(xc, yc - 3.8 * mm, value_txt)

    # Values (keep placeholders explicit)
    spap_s = _fmt(prev_spap, unit="mmHg", ndigits=0) or None
    dpap_s = _fmt(prev_dpap, unit="mmHg", ndigits=0) or None
    pap_sd_s = (f"{spap_s.split()[0]}/{dpap_s.split()[0]} mmHg" if (spap_s and dpap_s) else (spap_s or dpap_s))

    mpap_s = _fmt(prev_mpap, unit="mmHg", ndigits=0) or "–"
    pawp_s = _fmt(prev_pawp, unit="mmHg", ndigits=0) or "–"
    rap_s = _fmt(prev_rap, unit="mmHg", ndigits=0) or "–"
    co_s = _fmt(prev_co, unit="L/min", ndigits=1) or "–"
    ci_s = _fmt(prev_ci, unit="L/min/m²", ndigits=1) or "–"
    pvr_s = _fmt(prev_pvr, unit="WU", ndigits=1) or "–"

    cell_w = avail_w / 3.0
    # Row 1: pressures
    if (y - 6.0 * mm) >= (y_min + 6.0 * mm):
        _cell(xL + 0*cell_w, y, "PAP", pap_sd_s or "–")
        _cell(xL + 1*cell_w, y, "mPAP", mpap_s)
        _cell(xL + 2*cell_w, y, "PAWP", pawp_s)
        y -= 10.5 * mm

    # Row 2: RAP + CO + CI
    if (y - 6.0 * mm) >= (y_min + 4.0 * mm):
        _cell(xL + 0*cell_w, y, "RAP", rap_s)
        _cell(xL + 1*cell_w, y, "CO", co_s)
        _cell(xL + 2*cell_w, y, "CI", ci_s)
        y -= 10.5 * mm

    # Row 3: PVR (if space)
    if (y - 6.0 * mm) >= (y_min + 4.0 * mm):
        _cell(xL + 0*cell_w, y, "PVR", pvr_s)
        y -= 10.0 * mm

    # --- Comment (wrap into remaining space, no silent truncation) ---
    if label and (y - y_min) > (3.0 * mm):
        _draw_text_wrapped(
            c,
            x_box,
            y,
            w_box,
            max(4.0 * mm, y - y_min),
            f"Kommentar: {label}",
            font_size=8,
            line_h=4.2 * mm,
            pad_x=pad_x,
            pad_top=0,
            min_font_size=5,
        )


def generate_prerhk_pdf(case_state: Dict[str, Any]) -> str:
    """Create the Pre-RHK overview PDF and return a file path."""
    if not isinstance(case_state, dict):
        raise ValueError("case_state must be a dict")

    ui = _get(case_state, "ui", {}) or {}
    der = _get(case_state, "derived", {}) or {}

    # --- Header essentials (datensparsam) ---
    # Prefer IDs over names; fall back to case filename.
    case_name = str(_get(case_state, "case_filename", "") or _get(case_state, "filename", "") or "").strip()
    pid = str(ui.get("patient_id") or ui.get("pat_id") or ui.get("register_nr") or ui.get("register") or "").strip()
    fid = str(ui.get("fall_id") or ui.get("case_id") or "").strip()
    id_line = " ".join([p for p in [pid and f"ID: {pid}", fid and f"Fall: {fid}"] if p]) or (case_name and f"Fall: {case_name}") or "Fall: (ohne ID)"

    age = ui.get("age") or ui.get("alter") or ui.get("patient_age")
    sex = ui.get("sex") or ui.get("geschlecht") or ui.get("patient_sex")
    demo_line = " ".join([p for p in [age and f"{_fmt_num(age)} J", sex and str(sex)] if p]).strip()

    # DZL approval block (shown only if explicitly selected in UI)
    dzl_flag = ui.get("dzl_flag")
    dzl_decision = ui.get("dzl_decision")
    dzl_initial_test = ui.get("dzl_initial_test")
    dzl_tag = ""
    if _is_truthy(dzl_flag):
        dzl_tag = "DZL" + (f": {dzl_decision}" if str(dzl_decision or "").strip() else "")

    indication = str(ui.get("rhk_indication") or ui.get("indication") or ui.get("anlass") or ui.get("fragestellung") or "RHK – Pre Check").strip()

    # Free-text clinical story (short anamnesis) – often most relevant directly before cath.
    story_text = (ui.get("story") or ui.get("kurz_anamnese") or ui.get("short_history") or "").strip()

    # Free-text comorbidities / relevant pre-existing conditions (as entered in UI).
    comorb_text = (
        ui.get("comorbidities")
        or ui.get("relevante_vorerkrankungen")
        or ui.get("vordiagnosen_text")
        or ""
    )
    comorb_text = str(comorb_text or "").strip()

    # Pre-cath essentials
    consent_done = ui.get("consent_done")
    access_route = (ui.get("access_route") or ui.get("zugangsweg") or "").strip()
    anticoag_status = ui.get("anticoag_status")
    anticoag_substance = ui.get("anticoag_substance")
    anticoag_paused = ui.get("anticoag_paused")
    allergies_present = ui.get("allergies_present")
    allergies_list = ui.get("allergies_list") or []
    allergies_other_text = (ui.get("allergies_other_text") or "").strip()

    # PH Therapie (Episoden, restart-fähig; keine stille Übernahme)
    ph_tx_status = ui.get("ph_tx_status")
    ph_tx_episodes: List[Dict[str, str]] = []
    try:
        ph_tx_episodes = parse_ph_tx_table_rows(ui.get("ph_tx_table"))
    except Exception:
        ph_tx_episodes = []
    if (not ph_tx_episodes) and isinstance(der.get("ph_tx_episodes"), list):
        ph_tx_episodes = [
            e for e in (der.get("ph_tx_episodes") or [])
            if isinstance(e, dict) and str(e.get("drug") or "").strip() and str(e.get("status") or "").strip()
        ]
    if not ph_tx_episodes:
        ph_tx_episodes = legacy_lists_to_episodes(ui)

    # Optional: if present, show the last used access (e.g., which jugularis was used before)
    access_last = (ui.get("access_route_last") or ui.get("last_access_route") or ui.get("last_jugularis") or "").strip()

    # Optional: Vor-RHK baseline (if Vor-RHK import / values are present)
    prev_rhk_date = (ui.get("prev_rhk_date") or "").strip()
    prev_is_initial = ui.get("prev_is_initial")
    prev_mpap = ui.get("prev_mpap")
    prev_pawp = ui.get("prev_pawp")
    prev_rap = ui.get("prev_rap")
    prev_spap = ui.get("prev_spap")
    prev_dpap = ui.get("prev_dpap")
    prev_co = ui.get("prev_co")
    prev_ci = ui.get("prev_ci")
    prev_pvr = ui.get("prev_pvr")
    prev_label = (ui.get("prev_label") or "").strip()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # --- Clinic essentials (max 6 bullets) ---
    clinic_lines: List[str] = []

    who_fc = ui.get("who_fc") or ui.get("nyha") or ui.get("nyha_class") or ui.get("who_functional_class")
    if who_fc:
        clinic_lines.append(f"WHO FC: {who_fc}")
    syncope = ui.get("syncope") or ui.get("syncope_present")
    if syncope is not None and str(syncope).strip() != "":
        clinic_lines.append(f"Synkope: {'ja' if _is_truthy(syncope) else 'nein'}")
    edema = ui.get("edema") or ui.get("edema_present") or ui.get("oedema")
    if edema is not None and str(edema).strip() != "":
        clinic_lines.append(f"Ödeme: {'ja' if _is_truthy(edema) else 'nein'}")
    o2 = ui.get("o2_need") or ui.get("o2_l_min") or ui.get("o2_ltot") or ui.get("oxygen_l_min")
    if o2 is not None and str(o2).strip() != "":
        clinic_lines.append(f"O₂: {o2}")
    # comorbidities (try list-like fields)
    com_list = ui.get("comorbidities") or ui.get("preexisting") or ui.get("vordiagnosen") or ui.get("comorbidities_list") or []
    if isinstance(com_list, str):
        com_list = [s.strip() for s in com_list.split(",") if s.strip()]
    if isinstance(com_list, (list, tuple)):
        top = _pick_top([str(x) for x in com_list], 3)
        if top:
            clinic_lines.append("Vorerkr.: " + "; ".join(top))
    # avoid generic meds here; PH medication is shown in its own block

    clinic_lines = clinic_lines[:6]

    # --- Vorbereitung / unmittelbar vor RHK ---
    prep_pairs: List[Tuple[str, str]] = []
    prep_pairs.append(("Aufklärung", "ja" if _is_truthy(consent_done) else "nein"))
    if access_route:
        prep_pairs.append(("Zugang (geplant)", access_route))
    if access_last:
        prep_pairs.append(("Zugang zuletzt", access_last))
    if anticoag_status and str(anticoag_status).strip() and str(anticoag_status).lower() not in {"keine angabe","-"}:
        s = str(anticoag_status)
        if anticoag_substance and str(anticoag_substance).strip() and str(anticoag_substance).lower() not in {"keine angabe","-"}:
            s = f"{s} – {anticoag_substance}"
        if _is_truthy(anticoag_paused):
            s = f"{s} (pausiert)"
        prep_pairs.append(("Antikoag.", s))
    if _is_truthy(allergies_present):
        # Add "sonstiges" free text if present.
        al = allergies_list
        if isinstance(al, str):
            al = [s.strip() for s in al.split(",") if s.strip()]
        if isinstance(al, (list, tuple)):
            top = _pick_top([str(x) for x in al], 4)
            s = ", ".join(top) if top else "ja"
        else:
            s = "ja"
        if allergies_other_text:
            s = (s + "; " if s and s != "ja" else "") + allergies_other_text
        prep_pairs.append(("Allergien", s))

    prep_pairs = [(k, v) for k, v in prep_pairs if v]
    # --- PH Therapie (falls vorhanden) ---
    ph_pairs: List[Tuple[str, str]] = []

    def _clean(x: Any) -> str:
        s = "" if x is None else str(x).strip()
        return "" if (not s or s.lower() in {"keine angabe", "-"}) else s

    def _ep_str(e: Dict[str, str], mode: str) -> str:
        drug = _clean(e.get("drug"))
        if not drug:
            return ""
        since = _clean(e.get("since"))
        until = _clean(e.get("until"))
        reason = _clean(e.get("reason"))
        note = _clean(e.get("note"))

        bits: List[str] = []
        if mode == "aktuell":
            if since:
                bits.append(f"seit {since}")
        elif mode == "geplant":
            if since:
                bits.append(f"ab {since}")
        elif mode in {"pausiert", "abgesetzt"}:
            if until:
                bits.append(f"bis {until}")
            elif since:
                bits.append(f"seit {since}")
        else:
            if since and until:
                bits.append(f"{since} bis {until}")
            elif since:
                bits.append(f"seit {since}")
            elif until:
                bits.append(f"bis {until}")

        # Gründe/Notizen nur, wenn angegeben (kurz halten)
        if reason:
            bits.append(reason)
        if note:
            bits.append(note)

        tail = "; ".join([b for b in bits if b])
        return f"{drug} ({tail})" if tail else drug

    def _group_to_str(eps: List[Dict[str, str]], wanted: set, mode: str, max_n: int = 4) -> str:
        items: List[str] = []
        for e in eps or []:
            if not isinstance(e, dict):
                continue
            st = _clean(e.get("status")).lower()
            if st in wanted:
                s = _ep_str(e, mode=mode)
                if s:
                    items.append(s)
        return "; ".join(_pick_top(items, max_n))

    cur_s = _group_to_str(ph_tx_episodes, {"aktuell"}, mode="aktuell")
    plan_s = _group_to_str(ph_tx_episodes, {"geplant"}, mode="geplant")
    stop_s = _group_to_str(ph_tx_episodes, {"pausiert", "abgesetzt"}, mode="abgesetzt")
    prev_s = _group_to_str(ph_tx_episodes, {"früher"}, mode="früher", max_n=3)
    unkl_s = _group_to_str(ph_tx_episodes, {"unklar"}, mode="unklar", max_n=2)

    if cur_s:
        ph_pairs.append(("Aktuell", cur_s))
    if ph_tx_status and _clean(ph_tx_status):
        ph_pairs.append(("Verlauf", _clean(ph_tx_status)))
    if plan_s:
        ph_pairs.append(("Geplant", plan_s))
    if stop_s:
        ph_pairs.append(("Pausiert/abg.", stop_s))
    if prev_s:
        ph_pairs.append(("Früher", prev_s))
    if unkl_s:
        ph_pairs.append(("Unklar", unkl_s))

    # Convert pairs into bullet-friendly lines for the PH therapy box.
    # NOTE: This must exist even if empty (avoid NameError during PDF render).
    ph_lines: List[str] = [f"{k}: {v}" for k, v in ph_pairs if v]

    # --- Echo essentials (RH / PH) ---
    # Use only fields already present in UI and used elsewhere.
    def _echo_num(x: Any) -> Optional[float]:
        """Echo: fehlende Werte können als 0/0.0 ankommen -> als None behandeln."""
        try:
            if x is None or x == "":
                return None
            if isinstance(x, bool):
                return None
            f = float(x)
            if f != f:  # NaN
                return None
            if abs(f) < 1e-12:
                return None
            return f
        except Exception:
            return None

    def _echo_line(label: str, val: Any, unit: str = "", nd: int = 0):
        s = _fmt(val, unit=unit, ndigits=nd)
        return (label, s or "")

    echo_pairs: List[Tuple[str,str]] = []
    # RV function
    tapse = _echo_num(ui.get("tapse_mm"))
    sprime = _echo_num(ui.get("s_prime_cm_s"))
    rvfac = _echo_num(ui.get("rvfac_pct"))
    rvef3d = _echo_num(ui.get("rv_3d_ef_pct"))
    echo_pairs.append(_echo_line("TAPSE", tapse, "mm", 0))
    echo_pairs.append(_echo_line("S′", sprime, "cm/s", 1))
    if rvef3d is not None and str(rvef3d).strip() != "":
        echo_pairs.append(_echo_line("3D RVEF", rvef3d, "%", 0))
    else:
        echo_pairs.append(_echo_line("RV FAC", rvfac, "%", 0))

    # PH signs
    trv = _echo_num(ui.get("trv_ms"))
    pasp = _echo_num(ui.get("pasp_echo"))
    paat = _echo_num(ui.get("paat_ms"))
    sept = ui.get("septal_flattening")
    notch = ui.get("rvot_notch")
    if trv is not None and str(trv).strip() != "":
        echo_pairs.append(_echo_line("TR Vmax", trv, "m/s", 1))
    # sPAP (Echo) is rendered separately as a prominent metric box.
    if paat is not None and str(paat).strip() != "":
        echo_pairs.append(_echo_line("PAAT", paat, "ms", 0))
    if sept is not None and str(sept).strip() != "":
        echo_pairs.append(("Septum", str(sept)))
    if notch is not None and str(notch).strip() != "":
        echo_pairs.append(("RVOT notch", str(notch)))

    # congestion / RA IVC
    ra_esa = _echo_num(ui.get("ra_esa_cm2"))
    ivc_d = _echo_num(ui.get("ivc_diam_mm"))
    ivc_ci = ui.get("ivc_collapse_index_pct")
    rap_est = ui.get("rap_estimate") or ui.get("rap_est") or ui.get("rap_echo")
    if ra_esa is not None and str(ra_esa).strip() != "":
        echo_pairs.append(_echo_line("RA ESA", ra_esa, "cm²", 0))
    if ivc_d is not None and str(ivc_d).strip() != "":
        echo_pairs.append(_echo_line("IVC", ivc_d, "mm", 0))
    if ivc_ci is not None and str(ivc_ci).strip() != "":
        echo_pairs.append(_echo_line("IVC Kollaps", ivc_ci, "%", 0))
    if rap_est is not None and str(rap_est).strip() != "":
        echo_pairs.append(("RAP Schätzung", str(rap_est)))

    peri = ui.get("pericardial_effusion")
    if peri is not None and str(peri).strip() != "":
        echo_pairs.append(("Perikarderguss", "ja" if _is_truthy(peri) else "nein"))

    # remove empty
    echo_pairs = [(k,v) for k,v in echo_pairs if v]

    # limit to keep non-overloaded
    echo_pairs = echo_pairs[:10]

    # --- Lab & risk essentials ---
    lab_pairs: List[Tuple[str,str]] = []

    ntprobnp = ui.get("ntprobnp") or ui.get("nt_pro_bnp") or ui.get("ntprobnp_pg_ml") or der.get("ntprobnp") if isinstance(der, dict) else None
    hb = ui.get("hb") or ui.get("hemoglobin") or ui.get("hb_g_dl")
    crea = ui.get("creatinine_mg_dl")
    egfr = ui.get("egfr") or ui.get("egfr_ml_min_1_73")
    trop = ui.get("troponin") or ui.get("hs_troponin")
    inr = ui.get("inr")
    plt = ui.get("platelets_g_l")

    if ntprobnp is not None and str(ntprobnp).strip() != "":
        lab_pairs.append(_echo_line("NT-proBNP", ntprobnp, "", 0))
    if hb is not None and str(hb).strip() != "":
        lab_pairs.append(_echo_line("Hb", hb, "", 1))
    if egfr is not None and str(egfr).strip() != "":
        lab_pairs.append(_echo_line("eGFR", egfr, "", 0))
    elif crea is not None and str(crea).strip() != "":
        lab_pairs.append(_echo_line("Krea", crea, "mg/dL", 2))
    if trop is not None and str(trop).strip() != "":
        lab_pairs.append(_echo_line("Troponin", trop, "", 0))
    if inr is not None and str(inr).strip() != "":
        lab_pairs.append(_echo_line("INR", inr, "", 2))
    if plt is not None and str(plt).strip() != "":
        lab_pairs.append(_echo_line("Thrombos", plt, "G/L", 0))

    # Keep Antikoag/Allergien also as structured items (used in pre-procedure block + flags)
    if anticoag_status and str(anticoag_status).strip().lower() not in {"keine angabe","-"}:
        s = str(anticoag_status)
        if anticoag_substance and str(anticoag_substance).strip().lower() not in {"keine angabe","-"}:
            s = f"{s} – {anticoag_substance}"
        if _is_truthy(anticoag_paused):
            s = f"{s} (pausiert)"
        lab_pairs.append(("Antikoag.", s))

    if _is_truthy(allergies_present):
        if isinstance(allergies_list, str):
            allergies_list = [s.strip() for s in allergies_list.split(",") if s.strip()]
        if isinstance(allergies_list, (list, tuple)):
            s = ", ".join(_pick_top([str(x) for x in allergies_list], 3)) or "ja"
        else:
            s = "ja"
        if allergies_other_text:
            s = (s + "; " if s and s != "ja" else "") + allergies_other_text
        lab_pairs.append(("Allergien", s))

    lab_pairs = [(k,v) for k,v in lab_pairs if v][:10]

    # --- Flags (only if clearly relevant) ---
    flags: List[str] = []
    # Low forward output suspicion: CI or SVI low if present in UI/derived
    ci = ui.get("ci_rest") or ui.get("ci") or (der.get("ci_rest") if isinstance(der, dict) else None)
    svi = ui.get("svi_rest_ml_m2") or (der.get("svi_rest_ml_m2") if isinstance(der, dict) else None)
    try:
        if ci is not None and float(ci) < 2.0:
            flags.append("⚠ Low output")
    except Exception:
        pass
    try:
        if (svi is not None) and float(svi) < 31:
            if "⚠ Low output" not in flags:
                flags.append("⚠ Low output")
    except Exception:
        pass
    # Renal function
    try:
        if egfr is not None and float(egfr) < 45:
            flags.append("⚠ Niere")
    except Exception:
        pass
    # O2 need high
    try:
        if o2 is not None and float(str(o2).replace(",",".")) >= 4:
            flags.append("⚠ O₂")
    except Exception:
        pass
    # RV function flag if TAPSE very low
    try:
        if tapse is not None and float(tapse) < 14:
            flags.append("⚠ RV Funktion")
    except Exception:
        pass
    # anticoag active
    if anticoag_status and str(anticoag_status).strip() and str(anticoag_status).lower() not in {"nein","no","false","0","keine angabe","-"}:
        flags.append("⚠ Antikoag.")

    flags = flags[:4]

    # --- Header chips (directly pre-procedure relevant) ---
    header_chips: List[str] = []
    if consent_done is not None and str(consent_done).strip() != "":
        header_chips.append(f"Aufklärung: {'ja' if _is_truthy(consent_done) else 'nein'}")
    if access_route:
        header_chips.append(f"Zugang: {access_route}")
    if access_last:
        header_chips.append(f"zuletzt: {access_last}")
    if dzl_tag:
        header_chips.append(dzl_tag)
    if _is_truthy(dzl_initial_test):
        header_chips.append("Ersttestung")
    if _is_truthy(allergies_present):
        header_chips.append("Allergien")
    if anticoag_status and str(anticoag_status).strip() and str(anticoag_status).lower() not in {"keine angabe","-"}:
        header_chips.append("Antikoag.")
    header_chips = header_chips[:5]

    # --- Bottom strip (optional): Vor-RHK baseline + hand-written step oximetry (DZL Ersttestung) ---
    def _has_val(x: Any) -> bool:
        return x is not None and str(x).strip() != ""

    has_prev_base = bool(prev_rhk_date) or any(
        _has_val(v) for v in (prev_spap, prev_dpap, prev_mpap, prev_pawp, prev_rap, prev_co, prev_ci, prev_pvr)
    ) or bool(prev_label)

    need_handwrite_ox = _is_truthy(dzl_flag) and _is_truthy(dzl_initial_test)
    need_bottom_strip = has_prev_base or need_handwrite_ox

    # --- Create PDF ---
    # IMPORTANT (online compatibility):
    # Create the file in a dedicated export folder under the current working directory.
    # Some deployment environments restrict serving arbitrary temp paths.
    out_dir = os.path.join(os.getcwd(), "exports")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        # Fallback: OS temp dir (should still work locally)
        out_dir = os.path.join(tempfile.gettempdir(), "rhk_exports")
        os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, f"prerhk_{uuid.uuid4().hex}.pdf")

    w, h = landscape(A4)
    c = canvas.Canvas(out_path, pagesize=(w, h))
    # Page margins (compact)
    mx = 10 * mm
    my = 8 * mm

    # Header band (compact but must safely fit 2 rows of chips without clipping)
    header_h = 26 * mm

    def _draw_header(title: str) -> None:
        c.setFillColor(colors.HexColor("#f5f5f5"))
        c.rect(mx, h - my - header_h, w - 2*mx, header_h, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 14)
        y_title = h - my - 7*mm
        c.drawString(mx + 6*mm, y_title, title)

        c.setFont("Helvetica", 10)
        left_line_parts = [id_line]
        if demo_line:
            left_line_parts.append(demo_line)
        # Keep clear spacing to the chips row (avoid visual overlap / clipping).
        y_id = h - my - 14.5 * mm
        c.drawString(mx + 6*mm, y_id, " · ".join([p for p in left_line_parts if p]))

        # chips line(s) (pre-procedure essentials)
        # Render inside the header band and allow wrapping into 2 rows without clipping.
        if header_chips:
            x0 = mx + 6*mm
            max_x = w - mx - 6*mm

            def _rows_needed(fs: int) -> int:
                rows = 1
                x_run = x0
                for t in header_chips:
                    w_chip = _chip_width(c, t, fs=fs)
                    if (x_run + w_chip) > max_x:
                        rows += 1
                        x_run = x0
                    x_run += w_chip + 2*mm
                return rows

            fs_chip = 8
            h_chip = 5.6 * mm
            pad_y = 1.4 * mm
            if _rows_needed(8) > 2:
                fs_chip = 7
                h_chip = 5.0 * mm
                pad_y = 1.2 * mm

            row_gap = 1.2 * mm
            # Place chips clearly below the ID line, safely within the header band.
            y_chip = y_id - (h_chip + 1.6 * mm)
            y_min_chip = (h - my - header_h) + 2.0 * mm

            x = x0
            for txt in header_chips:
                w_chip = _chip_width(c, txt, fs=fs_chip)
                if (x + w_chip) > max_x:
                    x = x0
                    y_chip -= (h_chip + row_gap)
                if y_chip < y_min_chip:
                    break
                x = _chip_draw(c, x, y_chip, str(txt), fs=fs_chip, h=h_chip, pad_y=pad_y)

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(w/2, h - my - 10.5*mm, indication)

        c.setFont("Helvetica", 10)
        c.drawRightString(w - mx - 6*mm, y_id, now)

    _draw_header("Pre-RHK Kurzübersicht")

    # Body layout
    body_top = h - my - header_h - 4.5 * mm

    # Bottom flags bar is always present; an additional optional strip may be reserved above it.
    bar_h = 10 * mm
    strip_gap_above_bar = 2 * mm
    strip_gap_to_cols = 2 * mm

    col_gap = 5 * mm
    col_w = (w - 2*mx - 2*col_gap) / 3.0

    # Adaptive bottom strip height:
    # - Must be one-page.
    # - For DZL Ersttestung, the handwrite oximetry box must fully show PA/RV/RA/SVC lines.
    # - If many fields are empty, we reclaim vertical space for the strip.
    strip_bottom = None
    strip_top = None
    strip_h = 0.0

    def _compute_body_bottom(strip_h_val: float) -> Tuple[float, Optional[float], Optional[float]]:
        if strip_h_val > 0:
            bb = my + bar_h + strip_gap_above_bar + strip_h_val + strip_gap_to_cols
            sb = my + bar_h + strip_gap_above_bar
            st = sb + strip_h_val
            return bb, sb, st
        # Historical default: 18mm from bottom (12mm bar + 6mm margin)
        return my + 18*mm, None, None

    # Candidate strip heights (largest first) – we pick the largest that still allows all columns to fit.
    if need_bottom_strip:
        if need_handwrite_ox:
            # Guarantee room for 4 handwriting lines (PA/RV/RA/SVC) and allow using
            # otherwise unused vertical space for a bigger writing area.
            min_strip = 38 * mm
            pref_strip = 50 * mm
            candidates = [70, 68, 66, 64, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 42, 40, 38]
        else:
            min_strip = 20 * mm
            pref_strip = 24 * mm
            candidates = [30, 28, 26, 24, 22, 20]

        # Clamp by physical page constraints.
        candidates = [c*mm for c in candidates if (c*mm) >= min_strip]

        chosen = min_strip
        for cand in candidates:
            body_bottom, sb, st = _compute_body_bottom(cand)
            col_h_try = body_top - body_bottom
            if col_h_try < 70 * mm:
                continue

            # Quick feasibility checks for the three columns.
            # Column 2 uses fixed boxes; ensure Echo Essentials can still fit at min font.
            def _col2_ok(col_h_local: float) -> bool:
                gap_local = BOX_GAP_Y
                # sPAP box needs a minimum height for label + big value.
                spap_val = ui.get("pasp_echo") or ui.get("spap_echo") or ui.get("rvsp_echo")
                has_spap = (spap_val is not None and str(spap_val).strip() != "")
                spap_min = 34*mm if has_spap else 28*mm
                spap_h_local = min(max(spap_min, 32*mm), 44*mm)
                echo_h_local = col_h_local - spap_h_local - gap_local
                if echo_h_local < 28*mm:
                    # If echo would be too small, shrink sPAP box first.
                    spap_h_local = max(26*mm, spap_h_local - (28*mm - echo_h_local))
                    echo_h_local = col_h_local - spap_h_local - gap_local
                if echo_h_local < 24*mm:
                    return False
                # Check Echo Essentials content at minimum font size.
                need_echo = _needed_height_kv(
                    c,
                    echo_pairs,
                    col_w,
                    fs=6,
                    base_fs=9,
                    line_h=5.2*mm,
                    pad_x=BOX_PAD_X,
                    pad_top=BOX_PAD_TOP,
                    pad_bottom=BOX_PAD_BOTTOM,
                    key_w=34*mm,
                )
                return need_echo <= echo_h_local

            # Column 1 plan – use dynamic min-heights (empty boxes compress).
            def _col1_ok(col_h_local: float) -> bool:
                gap_local = BOX_GAP_Y

                # Build the preparation bullets locally so feasibility checks do not
                # depend on later layout code paths.
                prep_pairs_local: List[Tuple[str, str]] = []
                if consent_done is not None and str(consent_done).strip() != "":
                    prep_pairs_local.append(("Aufklärung", "ja" if _is_truthy(consent_done) else "nein"))
                if access_route:
                    prep_pairs_local.append(("Zugang", access_route))
                if access_last:
                    prep_pairs_local.append(("zuletzt", access_last))
                if anticoag_status and str(anticoag_status).strip() and str(anticoag_status).lower() not in {"keine angabe", "-"}:
                    s_ant = str(anticoag_status)
                    if anticoag_substance and str(anticoag_substance).strip() and str(anticoag_substance).lower() not in {"keine angabe", "-"}:
                        s_ant = f"{s_ant} – {anticoag_substance}"
                    if _is_truthy(anticoag_paused):
                        s_ant = f"{s_ant} (pausiert)"
                    prep_pairs_local.append(("Antikoag.", s_ant))
                if _is_truthy(allergies_present):
                    s_al = ", ".join(_pick_top(_norm_list(allergies_list), 3)) or "ja"
                    if allergies_other_text:
                        s_al = (s_al + "; " if s_al and s_al != "ja" else "") + allergies_other_text
                    prep_pairs_local.append(("Allergien", s_al))

                prep_bullets_local = [f"{k}: {v}" for k, v in prep_pairs_local if v]
                prep_bullets_local.extend(clinic_lines)

                def _is_empty_text(t: str) -> bool:
                    s = str(t or "").strip()
                    return (not s) or (s == "–") or (s == "-")

                story_empty = _is_empty_text(story_text)
                com_empty = _is_empty_text(comorb_text)
                prep_count = len([b for b in prep_bullets_local if str(b).strip() and str(b).strip() != "–"])

                base_local = {
                    "story_fs": 10,
                    "comorb_fs": 9,
                    "prep_fs": 9,
                    "story_lh": 5.4 * mm,
                    "comorb_lh": 5.2 * mm,
                    "prep_lh": 5.2 * mm,
                }

                for sc in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70):
                    story_fs = max(6, int(round(base_local["story_fs"] * sc)))
                    com_fs = max(6, int(round(base_local["comorb_fs"] * sc)))
                    prep_fs = max(6, int(round(base_local["prep_fs"] * sc)))

                    story_need = _needed_height_text(c, story_text, col_w, fs=story_fs, base_fs=base_local["story_fs"], line_h=base_local["story_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
                    com_need = _needed_height_text(c, comorb_text, col_w, fs=com_fs, base_fs=base_local["comorb_fs"], line_h=base_local["comorb_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
                    prep_need = _needed_height_bullets(c, prep_bullets_local, col_w, fs=prep_fs, base_fs=base_local["prep_fs"], line_h=base_local["prep_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)

                    story_min = 16*mm if story_empty else 22*mm
                    com_min = 14*mm if com_empty else 20*mm
                    prep_min = 20*mm if prep_count <= 3 else 26*mm

                    story_h = max(story_min, story_need)
                    com_h = max(com_min, com_need)
                    prep_h = max(prep_min, prep_need)

                    total = story_h + com_h + prep_h + 2*gap_local
                    if total <= col_h_local:
                        return True
                return False

            # Column 3 feasibility.
            def _col3_ok(col_h_local: float) -> bool:
                gap_local = BOX_GAP_Y
                ph_empty = not bool([ln for ln in (ph_lines or []) if str(ln).strip() and str(ln).strip() != "–"])
                lab_count = len(lab_pairs)

                base_local = {"ph_fs": 9, "lab_fs": 9, "ph_lh": 5.2*mm, "lab_lh": 5.2*mm, "lab_key_w": 34*mm}
                for sc in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70):
                    ph_fs = max(6, int(round(base_local["ph_fs"] * sc)))
                    lab_fs = max(6, int(round(base_local["lab_fs"] * sc)))
                    ph_need = _needed_height_bullets(c, (ph_lines or ["–"]), col_w, fs=ph_fs, base_fs=base_local["ph_fs"], line_h=base_local["ph_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
                    lab_need = _needed_height_kv(c, lab_pairs, col_w, fs=lab_fs, base_fs=base_local["lab_fs"], line_h=base_local["lab_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM, key_w=base_local["lab_key_w"])
                    ph_min = 18*mm if ph_empty else 30*mm
                    lab_min = 20*mm if lab_count <= 3 else 26*mm
                    ph_h = max(ph_min, ph_need)
                    lab_h = max(lab_min, lab_need)
                    if (ph_h + lab_h + gap_local) <= col_h_local:
                        return True
                return False

            if _col2_ok(col_h_try) and _col1_ok(col_h_try) and _col3_ok(col_h_try):
                chosen = cand
                break

        strip_h = float(chosen)
        body_bottom, strip_bottom, strip_top = _compute_body_bottom(strip_h)
    else:
        body_bottom, strip_bottom, strip_top = _compute_body_bottom(0.0)

    col_h = body_top - body_bottom

    # Column boxes
    x1 = mx
    x2 = mx + col_w + col_gap
    x3 = mx + 2*(col_w + col_gap)

    y0 = body_bottom
    # --- Column 1: Story + Vorerkrankungen + Klinik/Vorbereitung ---
    # Adaptive box heights (use full column height, avoid second pages).
    gap = BOX_GAP_Y

    # Compose preparation bullets once (used for sizing + rendering)
    prep_pairs_c1: List[Tuple[str, str]] = []
    if consent_done is not None and str(consent_done).strip() != "":
        prep_pairs_c1.append(("Aufklärung", "ja" if _is_truthy(consent_done) else "nein"))
    if access_route:
        prep_pairs_c1.append(("Zugang", access_route))
    if access_last:
        prep_pairs_c1.append(("zuletzt", access_last))
    if anticoag_status and str(anticoag_status).strip() and str(anticoag_status).lower() not in {"keine angabe", "-"}:
        s_ant = str(anticoag_status)
        if anticoag_substance and str(anticoag_substance).strip() and str(anticoag_substance).lower() not in {"keine angabe", "-"}:
            s_ant = f"{s_ant} – {anticoag_substance}"
        if _is_truthy(anticoag_paused):
            s_ant = f"{s_ant} (pausiert)"
        prep_pairs_c1.append(("Antikoag.", s_ant))
    if _is_truthy(allergies_present):
        s_al = ", ".join(_pick_top(_norm_list(allergies_list), 3)) or "ja"
        if allergies_other_text:
            s_al = (s_al + "; " if s_al and s_al != "ja" else "") + allergies_other_text
        prep_pairs_c1.append(("Allergien", s_al))

    prep_bullets = [f"{k}: {v}" for k, v in prep_pairs_c1 if v]
    prep_bullets.extend(clinic_lines)

    # Choose a compact scaling so ALL content fits in one page.
    # We try to keep fonts as large as possible; box heights adapt to the real content.
    base = {
        "story_fs": 10,
        "comorb_fs": 9,
        "prep_fs": 9,
        "story_lh": 5.4 * mm,
        "comorb_lh": 5.2 * mm,
        "prep_lh": 5.2 * mm,
    }



    def _is_empty_text(t: str) -> bool:
        s = str(t or '').strip()
        return (not s) or (s == '–') or (s == '-')

    story_empty = _is_empty_text(story_text)
    com_empty = _is_empty_text(comorb_text)
    prep_count = len([b for b in prep_bullets if str(b).strip() and str(b).strip() not in {'–','-'}])
    def _col1_plan(scale: float):
        story_fs = max(6, int(round(base["story_fs"] * scale)))
        com_fs = max(6, int(round(base["comorb_fs"] * scale)))
        prep_fs = max(6, int(round(base["prep_fs"] * scale)))

        story_need = _needed_height_text(c, story_text, col_w, fs=story_fs, base_fs=base["story_fs"], line_h=base["story_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
        com_need = _needed_height_text(c, comorb_text, col_w, fs=com_fs, base_fs=base["comorb_fs"], line_h=base["comorb_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
        prep_need = _needed_height_bullets(c, prep_bullets, col_w, fs=prep_fs, base_fs=base["prep_fs"], line_h=base["prep_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
        # Minimum visual heights (empty boxes may be compressed)
        story_min = 16 * mm if story_empty else 22 * mm
        com_min = 14 * mm if com_empty else 20 * mm
        prep_min = 20 * mm if prep_count <= 3 else 26 * mm

        story_h = max(story_min, story_need)
        com_h = max(com_min, com_need)
        prep_h = max(prep_min, prep_need)

        total = story_h + com_h + prep_h + 2 * gap
        return {
            "ok": total <= col_h,
            "total": total,
            "story_h": story_h,
            "com_h": com_h,
            "prep_h": prep_h,
            "story_fs": story_fs,
            "com_fs": com_fs,
            "prep_fs": prep_fs,
        }

    plan = None
    for sc in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70):
        pcol = _col1_plan(sc)
        if pcol["ok"]:
            plan = pcol
            break
    if plan is None:
        plan = _col1_plan(0.70)

    # Distribute remaining space to content boxes (empty boxes stay compact)
    used = plan["story_h"] + plan["com_h"] + plan["prep_h"] + 2 * gap
    extra = max(0.0, col_h - used)
    w_story = 0.0 if story_empty else 0.55
    w_com = 0.0 if com_empty else 0.20
    w_prep = 0.45
    ws = w_story + w_com + w_prep
    if ws <= 0:
        ws = 1.0
        w_prep = 1.0
    plan["story_h"] += extra * (w_story / ws)
    plan["com_h"] += extra * (w_com / ws)
    # The remainder goes to preparation box
    plan["prep_h"] = col_h - plan["story_h"] - plan["com_h"] - 2 * gap

    # Render column 1
    y_top_col = y0 + col_h

    # Story
    story_h = plan["story_h"]
    y_story_bot = y_top_col - story_h
    _draw_box(c, x1, y_story_bot, col_w, story_h, "Story / Kurz-Anamnese")
    _draw_text_wrapped(
        c,
        x1,
        y_top_col,
        col_w,
        story_h,
        story_text,
        font_size=plan["story_fs"],
        line_h=base["story_lh"],
        pad_top=BOX_PAD_TOP,
        min_font_size=6,
    )

    # Relevante Vorerkrankungen
    com_h = plan["com_h"]
    y_com_top = y_story_bot - gap
    y_com_bot = y_com_top - com_h
    _draw_box(c, x1, y_com_bot, col_w, com_h, "Relevante Vorerkrankungen")
    _draw_text_wrapped(
        c,
        x1,
        y_com_top,
        col_w,
        com_h,
        comorb_text,
        font_size=plan["com_fs"],
        line_h=base["comorb_lh"],
        pad_top=BOX_PAD_TOP,
        min_font_size=6,
    )

    # Klinik & Vorbereitung
    prep_h = plan["prep_h"]
    y_prep_top = y_com_bot - gap
    y_prep_bot = y_prep_top - prep_h
    _draw_box(c, x1, y_prep_bot, col_w, prep_h, "Klinik & Vorbereitung")
    _draw_bullets_wrapped(
        c,
        x1,
        y_prep_top,
        col_w,
        prep_h,
        prep_bullets,
        font_size=plan["prep_fs"],
        line_h=base["prep_lh"],
        pad_top=BOX_PAD_TOP,
        min_font_size=6,
        return_overflow=False,
    )
    # --- Column 2: Echo with prominent sPAP ---

    gap_c2 = BOX_GAP_Y

    spap_echo_val = ui.get("pasp_echo") or ui.get("spap_echo") or ui.get("rvsp_echo")
    has_spap = (spap_echo_val is not None and str(spap_echo_val).strip() != "")

    # Minimum heights (empty boxes may be compact, content boxes get room).
    spap_min = 34*mm if has_spap else 28*mm

    def _is_placeholder(val: Any) -> bool:
        s = str(val or '').strip().lower()
        return (not s) or (s in {'–', '-', 'keine angabe', 'n/a', 'na'})

    echo_meaningful = [(k, v) for (k, v) in echo_pairs if not _is_placeholder(v)]
    echo_empty = (len(echo_meaningful) == 0)

    # Target Echo Essentials height based on actual content.
    if echo_empty:
        echo_min = 16*mm
        echo_need = 16*mm
    else:
        echo_min = 22*mm if len(echo_pairs) <= 3 else 26*mm
        echo_need = _needed_height_kv(
            c,
            echo_pairs,
            col_w,
            fs=9,
            base_fs=9,
            line_h=5.2*mm,
            pad_x=BOX_PAD_X,
            pad_top=BOX_PAD_TOP,
            pad_bottom=BOX_PAD_BOTTOM,
            key_w=34*mm,
        )

    echo_h = max(echo_min, echo_need)
    # Give the remaining space to sPAP (prominent, especially when Echo is empty).
    spap_h = col_h - echo_h - gap_c2
    spap_h = max(spap_min, spap_h)
    # Keep a sane upper bound so the metric box stays visually balanced.
    spap_h = min(spap_h, 58*mm)
    echo_h = col_h - spap_h - gap_c2

    y_top_col2 = y0 + col_h

    # sPAP metric box
    y_spap_bot = y_top_col2 - spap_h
    _draw_box(c, x2, y_spap_bot, col_w, spap_h, "Echo: sPAP")
    spap_echo = ui.get("pasp_echo") or ui.get("spap_echo") or ui.get("rvsp_echo")
    spap_str = _fmt_num(spap_echo) if spap_echo is not None and str(spap_echo).strip() != "" else ""
    trv = ui.get("trv_ms")
    trv_str = _fmt(trv, unit="m/s", ndigits=1) if trv is not None and str(trv).strip() != "" else ""
    sub = f"TR Vmax {trv_str}" if trv_str else ""
    _metric_box(
        c,
        x2,
        y_top_col2,
        col_w,
        spap_h,
        "sPAP/RVSP (mmHg)",
        (spap_str or "–"),
        sub=sub,
    )

    # Echo essentials
    y_echo_top = y_spap_bot - gap_c2
    y_echo_bot = y_echo_top - echo_h
    _draw_box(c, x2, y_echo_bot, col_w, echo_h, "Echo Essentials")
    if echo_empty:
        _draw_text_wrapped(
            c,
            x2,
            y_echo_top,
            col_w,
            echo_h,
            "–",
            font_size=10,
            line_h=5.2*mm,
            pad_top=BOX_PAD_TOP,
            min_font_size=7,
        )
    else:
        _draw_kv_wrapped(
            c,
            x2,
            y_echo_top,
            col_w,
            echo_h,
            echo_pairs,
            font_size=9,
            line_h=5.2*mm,
            pad_top=BOX_PAD_TOP,
            key_w=34*mm,
            min_font_size=6,
        )

    # --- Column 3: PH Medikation + Labor/Risiko ---
    # Adaptive split so medication text does not force a continuation page.
    gap_c3 = BOX_GAP_Y

    base3 = {
        "ph_fs": 9,
        "lab_fs": 9,
        "ph_lh": 5.2 * mm,
        "lab_lh": 5.2 * mm,
        "lab_key_w": 34 * mm,
    }

    ph_empty = not bool([ln for ln in (ph_lines or []) if str(ln).strip() and str(ln).strip() not in {"–","-"}])
    lab_count = len(lab_pairs)

    def _col3_plan(scale: float):
        ph_fs = max(6, int(round(base3["ph_fs"] * scale)))
        lab_fs = max(6, int(round(base3["lab_fs"] * scale)))

        ph_need = _needed_height_bullets(c, ph_lines or ["–"], col_w, fs=ph_fs, base_fs=base3["ph_fs"], line_h=base3["ph_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM)
        lab_need = _needed_height_kv(c, lab_pairs, col_w, fs=lab_fs, base_fs=base3["lab_fs"], line_h=base3["lab_lh"], pad_x=BOX_PAD_X, pad_top=BOX_PAD_TOP, pad_bottom=BOX_PAD_BOTTOM, key_w=base3["lab_key_w"])

        # Empty boxes are kept compact; non-empty blocks get more room.
        ph_min = (18 * mm) if ph_empty else (30 * mm)
        lab_min = (20 * mm) if (lab_count <= 3) else (26 * mm)
        ph_h = max(ph_min, ph_need)
        lab_h = max(lab_min, lab_need)
        total = ph_h + lab_h + gap_c3
        return {
            "ok": total <= col_h,
            "ph_h": ph_h,
            "lab_h": lab_h,
            "ph_fs": ph_fs,
            "lab_fs": lab_fs,
            "total": total,
        }

    plan3 = None
    for sc in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70):
        pc3 = _col3_plan(sc)
        if pc3["ok"]:
            plan3 = pc3
            break
    if plan3 is None:
        plan3 = _col3_plan(0.70)

    used3 = plan3["ph_h"] + plan3["lab_h"] + gap_c3
    extra3 = max(0.0, col_h - used3)
    # If medication is empty, prefer giving space to lab/risk.
    w_med = 0.65 if not ph_empty else 0.25
    plan3["ph_h"] += extra3 * w_med
    plan3["lab_h"] = col_h - plan3["ph_h"] - gap_c3

    # Render
    y_top_col3 = y0 + col_h
    ph_h = plan3["ph_h"]
    lab_h = plan3["lab_h"]

    y_ph_bot = y_top_col3 - ph_h
    _draw_box(c, x3, y_ph_bot, col_w, ph_h, "PH Medikation")
    _draw_bullets_wrapped(
        c,
        x3,
        y_top_col3,
        col_w,
        ph_h,
        ph_lines or ["–"],
        font_size=plan3["ph_fs"],
        line_h=base3["ph_lh"],
        pad_top=BOX_PAD_TOP,
        min_font_size=6,
        return_overflow=False,
    )

    y_lab_top = y_ph_bot - gap_c3
    y_lab_bot = y_lab_top - lab_h
    _draw_box(c, x3, y_lab_bot, col_w, lab_h, "Labor & Risiko")
    _draw_kv_wrapped(
        c,
        x3,
        y_lab_top,
        col_w,
        lab_h,
        lab_pairs,
        font_size=plan3["lab_fs"],
        line_h=base3["lab_lh"],
        key_w=base3["lab_key_w"],
        pad_top=BOX_PAD_TOP,
        min_font_size=6,
    )

    # --- Optional bottom strip above flags bar ---

    if need_bottom_strip and strip_bottom is not None:
        total_w = w - 2*mx
        y_strip = float(strip_bottom)
        h_strip = float(strip_h)
        gap_strip = 6*mm

        # Layout: optional Vor-RHK baseline block on the left, optional hand-written step oximetry on the right.
        hand_w = 76*mm if need_handwrite_ox else 0.0
        x_hand = (mx + total_w - hand_w) if need_handwrite_ox else None

        # Vor-RHK baseline (if present)
        if has_prev_base:
            x_prev = mx
            w_prev = total_w - (hand_w + gap_strip) if need_handwrite_ox else total_w
            _draw_box_small(c, x_prev, y_strip, w_prev, h_strip, "Vor-RHK Base")

            _draw_prev_rhk_base_compact(
                c,
                x_prev,
                y_strip + h_strip,
                w_prev,
                h_strip,
                prev_rhk_date=prev_rhk_date,
                prev_is_initial=prev_is_initial,
                prev_mpap=prev_mpap,
                prev_pawp=prev_pawp,
                prev_rap=prev_rap,
                prev_spap=prev_spap,
                prev_dpap=prev_dpap,
                prev_co=prev_co,
                prev_ci=prev_ci,
                prev_pvr=prev_pvr,
                prev_label=prev_label,
            )

        # Hand-written step oximetry (only for DZL Ersttestung)
        if need_handwrite_ox and x_hand is not None:
            _draw_box_small(c, float(x_hand), y_strip, float(hand_w), h_strip, "Stufenoxymetrie (handschriftlich)")
            # Reihenfolge strikt nach Vorgabe.
            labels = ["PA", "RV", "RA", "SVC"]

            c.setFont("Helvetica", 8)
            c.setStrokeColor(colors.HexColor("#888888"))
            c.setFillColor(colors.HexColor("#222222"))

            pad_x = 8*mm
            top_offset = 15*mm
            bottom_offset = 9*mm
            y_start = y_strip + h_strip - top_offset
            y_min = y_strip + bottom_offset
            if len(labels) > 1:
                avail = max(0.0, y_start - y_min)
                step = avail / (len(labels) - 1) if avail > 0 else 0.0
                # Clamp for handwriting readability.
                step = max(4.4*mm, min(7.0*mm, step))
            else:
                step = 6.0*mm

            line_x0 = float(x_hand) + pad_x + 18*mm
            line_x1 = float(x_hand) + float(hand_w) - pad_x

            y = y_start
            for i, lab in enumerate(labels):
                if y < y_min - 0.2*mm:
                    break
                c.drawString(float(x_hand) + pad_x, y, f"{lab}:")
                c.line(line_x0, y - 1.2*mm, line_x1, y - 1.2*mm)
                y -= step
    # Flags bar
    c.setFillColor(colors.HexColor("#ffffff"))
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(mx, my, w - 2*mx, bar_h, 6, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(mx + 6*mm, my + 4*mm, "Flags vor RHK:")
    x = mx + 32*mm
    for f in flags:
        x = _chip(c, x, my + 3*mm, f)

    # Finalize (single page)
    c.save()
    return out_path
