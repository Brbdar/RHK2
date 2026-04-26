#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_utils.py - Modularisierung (Core/Renderer), Star-Imports entfernt, API-kompatible Re-Exports
"""Backwards-compatible UI utilities facade.

Why this file still exists:
- Older parts of the app import helpers from ``rhk_ui_utils``.
- In v1.26 we split the former monolith into focused modules:
  - rhk_ui_core.py (DataProbe, html helpers, safe render decorator)
  - rhk_medcalc.py (medical helper calculations: eGFR)
  - rhk_ui_render_*.py (HTML renderer modules)

This facade keeps the public imports stable while making the codebase maintainable.
"""

from __future__ import annotations

# Medical calculations used by UI
from rhk_medcalc import compute_egfr

# Core helpers
from rhk_ui_core import (
    DataProbe,
    _chip,
    _fmt_or_dash,
    _gradio_major_version,
    _normalize_module_ids,
    html_escape,
    load_rulebook_meta,
    ui_safe_render,
)
from rhk_ui_render_docx import (
    build_docx_status_html,
    build_docx_tables_overview_html,
)
from rhk_ui_render_modules import build_p_module_cards_html

# Renderers
from rhk_ui_render_summary import (
    build_compare_overview_html,
    build_pre_cath_header_html,
    build_sticky_summary_html,
)
from rhk_ui_render_viz import build_rhk_plots_html

__all__ = [
    # Core
    "DataProbe",
    "ui_safe_render",
    "html_escape",
    "_chip",
    "_fmt_or_dash",
    "_normalize_module_ids",
    "_gradio_major_version",
    "load_rulebook_meta",
    # Medical
    "compute_egfr",
    # Renderers
    "build_sticky_summary_html",
    "build_compare_overview_html",
    "build_pre_cath_header_html",
    "build_docx_tables_overview_html",
    "build_docx_status_html",
    "build_rhk_plots_html",
    "build_p_module_cards_html",
]
