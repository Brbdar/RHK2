#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_render_modules.py - Decision-Support Karten ausgelagert, Renderer-only
"""Renderers for decision-support module cards."""

from __future__ import annotations

from typing import Any, Dict, Optional

from rhk_ui_core import DataProbe, html_escape, ui_safe_render


@ui_safe_render()
def build_p_module_cards_html(blocks: Dict[str, Any], case: Optional[Dict[str, Any]]) -> str:
    """Decision Support Cards."""
    if not case: return ""
    ui = DataProbe(case.get("ui"))
    decision = DataProbe(case.get("decision"))
    policy = DataProbe(case.get("derived")).get("p_module_policy", default={})
    
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
