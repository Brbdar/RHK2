#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.51: rhk_ui.py - Workflow-Panel erweitert (Schnellnavigation für Eingabe-/Ausgabe-Tabs)
# Refactor v1.49: rhk_ui.py - Verlaufsladen für gespeicherte JSON-Fälle (neuer Katheter-Zyklus) + Load-Bindings entdoppelt
# Refactor v1.48: rhk_ui.py - Generate-Path Cache (Signatur-basiert) für schnellere Wiederhol-Generierungen
# Refactor v1.47: rhk_ui.py - Übersicht verbessert (Workflow-Panel + klar nummerierte Eingabe-Tabs), kein klinischer Logik-Change
# Refactor v1.45: rhk_ui.py - Hotfix: pathlib.Path global import (DOCX/DOCX ZIP/PDF Export stabil), no logic change
# Refactor v1.43: rhk_ui.py - Downloads stabilisiert (Gradio 6 kompatibel): Export-Buttons -> File-Links, Export-Dir konsistent, Download-Diagnose
# Refactor v1.40: rhk_ui.py - Pre-RHK PDF Download stabilisiert (DownloadButton -> File), Cloud/Browser kompatibel
# Refactor v1.32: rhk_ui.py - Export/Downloads gefixt (DOCX/Pre-RHK PDF), Debug/Plots entkoppelt, weniger Payload -> schneller
# Refactor v1.31: rhk_ui.py - Performance: _generate() ohne Deepcopy/Double-Read, weniger Memory-Churn bei Case/UI-Merge
# Refactor v1.28: rhk_ui.py - DOCX-Import Merge-Policy extrahiert (rhk_import_merge), bool/0 Edge-Case gefixt, manuelle Korrekturen geschützt
# Refactor v1.27: rhk_ui.py - Star-Import entfernt, Section-Progress ausgelagert, Imports explizit, Fix-Header aktualisiert
# Refactor v1.26: rhk_ui.py - Bindings modularisiert (clinic/imaging/cpet/rhk), Bugfix CHD-Details Handle, UI stabiler
"""RHK Befundassistent - Gradio UI.

This module intentionally contains only:
- UI layout (Gradio Blocks)
- wiring/bindings (callbacks)

Heavy inline assets and helper functions were split into:
- rhk_ui_assets.py (CSS, JavaScript, HEAD HTML)
- rhk_ui_utils.py (helper/render functions)
"""

from __future__ import annotations

import html
import json
import os
import platform
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from rhk_base import (
    APP_TITLE,
    DEFAULT_RULEBOOK_PATH,
    RHK_HEADER_HTML,
    WHATS_NEW,
    _infer_anemia,
    _normalize_module_ids,
    _pmod_level,
    _safe_float,
    _safe_num,
    build_disabled_p_modules_html,
    build_p_module_choices,
    calc_bsa,
    load_rulebook,
    load_textdb_blocks,
    pmods_apply_overrides,
    pmods_get_force_optional,
)
from rhk_case import build_dashboard_html
from rhk_export_paths import get_export_dir
from rhk_export_service import (
    build_doctor_docx_file,
    export_doctor_docx,
    export_doctor_docx_zip,
    export_prerhk_pdf,
    save_doctor_docx_local,
)
from rhk_generate_service import generate_runtime_artifacts

# NOTE: In some Gradio 6.x versions, dynamically updating DownloadButtons with
# local filepaths can be unreliable. For clinical robustness we use explicit
# "Erstellen" buttons and expose the result via gr.File (download link).
from rhk_i18n import tr_ui
from rhk_import_docx import (
    DOCX_CURRENT_WIPE_DEFAULTS,
    DOCX_PREV_WIPE_DEFAULTS,
)
from rhk_import_service import import_current_docx, import_previous_docx
from rhk_logging import log_exception
from rhk_persistence_service import load_case_bundle, save_case_bundle
from rhk_reports import (
    _extract_markdown_section_cached,
    _markdown_to_plain_cached,
    _markdown_to_word_html_cached,
    build_doctor_report,
    build_echo_doctor_report_extended,
    build_echo_patient_report,
    build_internal_report,
    build_patient_report,
    build_summary_dict,
    example_suite_case,
)

# NOTE: gr.Dataframe triggers a pandas import in Gradio. In mixed NumPy environments
# (NumPy 2.x with wheels compiled against NumPy 1.x), importing pandas/pyarrow/numexpr
# can hard-fail. For maximal deployment robustness we always use the Textbox-based
# episode editor for PH Therapie.
from rhk_ui_assets import CSS, HEAD_HTML, JS_ON_LOAD
from rhk_ui_bindings_clinic import bind_clinic_bindings
from rhk_ui_bindings_cpet import bind_cpet_bindings
from rhk_ui_bindings_imaging import bind_imaging_bindings
from rhk_ui_bindings_rhk import bind_rhk_bindings
from rhk_ui_cpet import render_cpet_risk_html as _render_cpet_risk_html
from rhk_ui_echo import bind_echo_import, render_echo_import_views
from rhk_ui_helpers import (
    _UI_RECOVERABLE_ERRORS,
    _build_workflow_overview_html,
    _get_spiro_logic,
)
# NOTE: rhk_ui_mode (Einfach/Experte toggle) is no longer wired into the UI.
# The module is kept for its unit tests and for any programmatic callers,
# but the toggle widget and its visibility gate have been removed.
from rhk_ui_progress import bind_section_progress as _bind_section_progress_core
from rhk_ui_progress import is_filled as _is_filled
from rhk_ui_rhk import build_rhk_tab
from rhk_ui_tab_clinic import build_clinic_tab
from rhk_ui_tab_cpet import build_cpet_tab
from rhk_ui_tab_imaging import build_imaging_tab
from rhk_ui_utils import (
    build_p_module_cards_html,
    build_pre_cath_header_html,
    build_rhk_plots_html,
    build_sticky_summary_html,
    compute_egfr,
    load_rulebook_meta,
)


def _build_ui_theme() -> Optional[gr.Theme]:
    theme = None
    try:
        if hasattr(gr, "themes"):
            theme = gr.themes.Soft()
    except _UI_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_UI_THEME_INIT", "Gradio theme initialization failed; continuing without theme.", exc)
    return theme


def _gradio_major_version() -> int:
    v = str(getattr(gr, "__version__", ""))
    m = re.match(r"\s*(\d+)", v)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except _UI_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_UI_GRADIO_VERSION_PARSE", "Gradio major version parsing failed; defaulting to 0.", exc, version=v)
        return 0


def _build_blocks_context(theme: Optional[gr.Theme]) -> gr.Blocks:
    launch_kwargs: Dict[str, Any] = {"css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
    if theme is not None:
        launch_kwargs["theme"] = theme

    if _gradio_major_version() >= 6:
        demo_ctx = gr.Blocks(title=APP_TITLE)
        demo_ctx._rhk_launch_kwargs = launch_kwargs
        return demo_ctx

    blocks_kwargs: Dict[str, Any] = {"title": APP_TITLE, "css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
    if theme is not None:
        blocks_kwargs["theme"] = theme
    demo_ctx = gr.Blocks(**blocks_kwargs)
    demo_ctx._rhk_launch_kwargs = {}
    return demo_ctx


def build_demo() -> Tuple[gr.Blocks, str, gr.Theme]:
    """Public entrypoint kept stable for launcher/hosted mode."""
    return _build_demo_impl()


def _build_demo_impl() -> Tuple[gr.Blocks, str, gr.Theme]:
    blocks = load_textdb_blocks()
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    rulebook_meta = load_rulebook_meta(DEFAULT_RULEBOOK_PATH)
    theme = _build_ui_theme()
    demo_ctx = _build_blocks_context(theme)

    with demo_ctx as demo:
        # Header
        gr.HTML(RHK_HEADER_HTML)
        # Changelog is reference material — collapse behind a <details> so it
        # does not compete with status chips and actions for attention.
        gr.HTML(
            (
                "<details class='whatsnew-details'>"
                "<summary>Was ist neu?</summary>"
                f"<div class='whatsnew'>{WHATS_NEW}</div>"
                "</details>"
            ),
            elem_id="rhk_whatsnew_wrapper",
        )

        # Pre-Cath Safety Header (Sticky) on start page
        pre_cath_home_html = gr.HTML(
            value=build_pre_cath_header_html({}),
            elem_id="rhk_pre_cath_home_wrapper",
        )

        # Sticky live preview (always visible)
        sticky_summary_html = gr.HTML(
            value=build_sticky_summary_html(None),
            elem_id="rhk_summarybar_wrapper",
        )

        gr.HTML(
            value=_build_workflow_overview_html(),
            elem_id="rhk_workflow_overview_wrapper",
        )

        gr.HTML(
            '<div class="rhk-import-hint-box">'
            '<span class="rhk-import-hint-icon" aria-hidden="true">\u2139\ufe0f</span>'
            '<span class="rhk-import-hint-label">Hinweis zum DOCX-Import</span>'
            '<span class="rhk-import-hint-text">'
            "Der Import unterstützt GE MacLab Word-Exporte (z. B. Gießener Format). "
            "Für andere Zentren oder abweichende Exportformate empfehlen wir die manuelle "
            "Eingabe der Hämodynamik-Werte im Tab \u201e4. RHK\u201c. "
            "Importierte Werte können jederzeit manuell korrigiert werden."
            "</span>"
            "</div>",
            elem_id="rhk_import_hint_top",
        )
        with gr.Row(elem_id="rhk_actions_top_primary"):
            docx_btn_top = gr.UploadButton("1. RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_top")
            btn_generate_top = gr.Button("2. Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_top")

        with gr.Row(visible=True, elem_id="rhk_actions_top_expert") as expert_actions_top:
            btn_example_top = gr.Button("Beispiel laden (Suite)", variant="secondary", elem_id="btn_example_top")
            btn_clear_top = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_top")
            save_btn_top = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_top")
            load_btn_top = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_top")
            load_followup_btn_top = gr.UploadButton(
                "Fall als Verlauf laden (.json)",
                file_types=[".json"],
                variant="secondary",
                elem_id="btn_load_followup_top",
            )
        # DOCX Import Übersicht wird im RHK-Tab angezeigt (Accordion, open=True).
        # Layout: left inputs, right outputs
        gr.HTML("<span id='rhk_main_content' tabindex='-1'></span>", visible=False)
        with gr.Row():
            with gr.Column(scale=7, elem_id="rhk_input_column"):
                # Tab subtitle (client-side; helps orientation when scrolling)
                gr.HTML("", elem_id="rhk_tab_subtitle")

                field_components: Dict[str, gr.components.Component] = {}
                _field_id_counts: Dict[str, int] = {}

                def add(name: str, comp: gr.components.Component, info: str | None = None, **_kwargs):
                    """Register a field component.

                    Some call-sites pass an ``info=...`` tooltip text.
                    Older versions of this helper didn't accept that keyword
                    which caused a hard crash at startup. We accept it here and
                    set the component's ``info`` attribute if supported.
                    """
                    if info:
                        # Gradio uses `info` as tooltip/helptext for the component.
                        try:
                            comp.info = info
                        except _UI_RECOVERABLE_ERRORS as exc:
                            log_exception("RHK_UI_FIELD_INFO", "Failed to set component info tooltip.", exc, field=name)

                    safe_name = "".join(
                        [ch if (ch.isalnum() or ch in {"_", "-"}) else "-" for ch in str(name or "").strip()]
                    ).strip("-") or "field"

                    # Add stable CSS hooks for field-level warning markers.
                    try:
                        cur_classes = getattr(comp, "elem_classes", None)
                        if isinstance(cur_classes, str):
                            classes = [cur_classes]
                        elif isinstance(cur_classes, (list, tuple, set)):
                            classes = [str(x) for x in cur_classes if str(x).strip()]
                        else:
                            classes = []
                        for cls in ("rhk-field", f"rhk-field-{safe_name}"):
                            if cls not in classes:
                                classes.append(cls)
                        comp.elem_classes = classes
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_FIELD_CLASSES", "Failed to set component CSS classes.", exc, field=name)

                    # Assign deterministic IDs (duplicates get a numeric suffix).
                    try:
                        idx = int(_field_id_counts.get(safe_name, 0)) + 1
                        _field_id_counts[safe_name] = idx
                        if not getattr(comp, "elem_id", None):
                            elem_id = f"fld_{safe_name}" if idx == 1 else f"fld_{safe_name}_{idx}"
                            comp.elem_id = elem_id
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_FIELD_ELEM_ID", "Failed to set deterministic component id.", exc, field=name)

                    field_components[name] = comp
                    return comp

                # ---- Tab 1: Klinik & Labor ----
                with gr.TabItem("1. Klinik & Labor", id=0):
                    with gr.Group(elem_classes=["rhk-screen", "rhk-screen-clinic"]):
                        clinic_ui = build_clinic_tab(add)
                    hdr_klinik_general = clinic_ui["hdr_klinik_general"]
                    hdr_klinik_symptoms = clinic_ui["hdr_klinik_symptoms"]
                    hdr_klinik_labs = clinic_ui["hdr_klinik_labs"]
                    hdr_klinik_meds = clinic_ui["hdr_klinik_meds"]
                    anemia_type = clinic_ui["anemia_type"]
                    allergies_details = clinic_ui["allergies_details"]
                    _chd_details = clinic_ui["chd_details"]  # noqa: F841
                    _ekg_details = clinic_ui["ekg_details"]  # noqa: F841
                    _ph_known_details = clinic_ui["ph_known_details"]  # noqa: F841
                    _anticoag_substance = clinic_ui["anticoag_substance"]  # noqa: F841
                    _anticoag_indication = clinic_ui["anticoag_indication"]  # noqa: F841
                    _anticoag_since = clinic_ui["anticoag_since"]  # noqa: F841
                    _anticoag_note = clinic_ui["anticoag_note"]  # noqa: F841
                    _anticoag_paused = clinic_ui["anticoag_paused"]  # noqa: F841
                    _ph_tx_use_df = clinic_ui["ph_tx_use_df"]  # noqa: F841
                    _ph_tx_add_drug = clinic_ui["ph_tx_add_drug"]  # noqa: F841
                    _ph_tx_add_status = clinic_ui["ph_tx_add_status"]  # noqa: F841
                    _ph_tx_add_since = clinic_ui["ph_tx_add_since"]  # noqa: F841
                    _ph_tx_add_until = clinic_ui["ph_tx_add_until"]  # noqa: F841
                    _ph_tx_add_reason = clinic_ui["ph_tx_add_reason"]  # noqa: F841
                    _ph_tx_add_note = clinic_ui["ph_tx_add_note"]  # noqa: F841
                    _ph_tx_add_btn = clinic_ui["ph_tx_add_btn"]  # noqa: F841
                    _ph_tx_table = clinic_ui["ph_tx_table"]  # noqa: F841
                    _ph_tx_del_idx = clinic_ui["ph_tx_del_idx"]  # noqa: F841
                    _ph_tx_del_btn = clinic_ui["ph_tx_del_btn"]  # noqa: F841
                    ph_tx_from_legacy_btn = clinic_ui["ph_tx_from_legacy_btn"]
                    ph_tx_legacy_acc = clinic_ui["ph_tx_legacy_acc"]
                # ---- Tab 2: Bildgebung & Echo/CMR (merged) ----
                with gr.TabItem("2. Bildgebung & Echo/CMR", id=1):
                    with gr.Group(elem_classes=["rhk-screen", "rhk-screen-imaging"]):
                        imaging_ui = build_imaging_tab(add)
                    hdr_imaging = imaging_ui["hdr_imaging"]
                    hdr_echo = imaging_ui["hdr_echo"]
                    hdr_cmr = imaging_ui["hdr_cmr"]
                    ct_desc_col = imaging_ui["ct_desc_col"]
                    acc_ild = imaging_ui["acc_ild"]
                    ild_tx_details = imaging_ui["ild_tx_details"]
                    acc_vq = imaging_ui["acc_vq"]
                    _ctepd_no_ph_col = imaging_ui["ctepd_no_ph_col"]  # noqa: F841
                    echo_ui = imaging_ui["echo_ui"]
                    import_pdf_cur = imaging_ui["import_pdf_cur"]
                    import_pdf_prev = imaging_ui["import_pdf_prev"]
                    import_preview_cur_html = imaging_ui["import_preview_cur_html"]
                    import_preview_prev_html = imaging_ui["import_preview_prev_html"]
                    compare_echo_html = imaging_ui["compare_echo_html"]
                    details_echo_html = imaging_ui["details_echo_html"]
                    state_echo_cur = imaging_ui["state_echo_cur"]
                    state_echo_prev = imaging_ui["state_echo_prev"]
                    btn_echo_apply = imaging_ui["btn_echo_apply"]
                    _btn_echo_clear = imaging_ui["btn_echo_clear"]  # noqa: F841
                    _btn_echo_clear_prev = imaging_ui["btn_echo_clear_prev"]  # noqa: F841
                    _antifib_drug = imaging_ui["antifib_drug"]  # noqa: F841
                    _antifib_since = imaging_ui["antifib_since"]  # noqa: F841
                    _antifib_note = imaging_ui["antifib_note"]  # noqa: F841
                # ---- Tab 3: Lungenfunktion & CPET ----
                with gr.TabItem("3. Lungenfunktion & CPET", id=2):
                    with gr.Group(elem_classes=["rhk-screen", "rhk-screen-cpet"]):
                        cpet_ui = build_cpet_tab(add)
                    hdr_lufu = cpet_ui["hdr_lufu"]
                    hdr_cpet = cpet_ui["hdr_cpet"]
                    cpet_risk_html = cpet_ui["cpet_risk_html"]
                    cpet_details = cpet_ui["cpet_details"]
                    _cpet_9panel_details = cpet_ui["cpet_9panel_details"]  # noqa: F841
                    cpet_chrono_followup = cpet_ui["cpet_chrono_followup"]
                    cpet_live_html = cpet_ui["cpet_live_html"]
                    cpet_teaching_html = cpet_ui["cpet_teaching_html"]
                    cpet_mod0_html = cpet_ui["cpet_mod0_html"]
                    cpet_mod1_html = cpet_ui["cpet_mod1_html"]
                    cpet_mod2_html = cpet_ui["cpet_mod2_html"]
                    cpet_mod3_html = cpet_ui["cpet_mod3_html"]
                    cpet_mod4_html = cpet_ui["cpet_mod4_html"]
                    cpet_mod5_html = cpet_ui["cpet_mod5_html"]
                    cpet_mod6_html = cpet_ui["cpet_mod6_html"]
                    cpet_mod7_html = cpet_ui["cpet_mod7_html"]
                    cpet_mod9_html = cpet_ui["cpet_mod9_html"]
                    cpet_modfinal_html = cpet_ui["cpet_modfinal_html"]
                    cpet_overall_html = cpet_ui["cpet_overall_html"]
                    cpet_spiro_report = cpet_ui["cpet_spiro_report"]
                    cpet_spiro_status = cpet_ui["cpet_spiro_status"]
                    btn_cpet_adopt = cpet_ui["btn_cpet_adopt"]
                # ---- Tab 4: RHK ----
                with gr.TabItem("4. RHK", id=3):
                    rhk_ui = build_rhk_tab(add)
                    import_status_html = rhk_ui["import_status_html"]
                    btn_wipe_docx_current = rhk_ui.get("btn_wipe_docx_current")
                    btn_wipe_docx_prev = rhk_ui.get("btn_wipe_docx_prev")
                    btn_update_plots = rhk_ui.get("btn_update_plots")
                    rhk_plots_html = rhk_ui["rhk_plots_html"]
                    pre_cath_html = rhk_ui["pre_cath_html"]
                    compare_overview_html = rhk_ui["compare_overview_html"]
                    prev_docx_btn = rhk_ui["prev_docx_btn"]
                    auto_mpap = rhk_ui["auto_mpap"]
                    auto_ci = rhk_ui["auto_ci"]
                    auto_pvr = rhk_ui["auto_pvr"]
                    auto_pvri = rhk_ui["auto_pvri"]
                    auto_tpg = rhk_ui["auto_tpg"]
                    auto_dpg = rhk_ui["auto_dpg"]
                    hdr_rhk_rest = rhk_ui.get("hdr_rhk_rest")
                    hdr_rhk_exercise = rhk_ui.get("hdr_rhk_exercise")
                    hdr_rhk_addons = rhk_ui.get("hdr_rhk_addons")
                    hdr_rhk_prev = rhk_ui.get("hdr_rhk_prev")

                # ---- Tab 5: Weitere Bereiche ----
                with gr.TabItem("5. Weitere Befunde", id=4):
                    # Blutgase / LTOT
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_bloodgas = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Blutgase / LTOT</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt Blutgase / LTOT' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("ltot", gr.Checkbox(label="LTOT vorhanden"))
                                ltot_flow = add("ltot_flow_l_min", gr.Number(label="LTOT (l/min)", visible=False))

                    # Infektiologie / Immunologie
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_infect = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Infektiologie / Immunologie</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt Infektiologie / Immunologie' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("virology_pos", gr.Checkbox(label="Virologie/Infektiologie positiv"))
                            with gr.Row():
                                viro_items = add("virology_items", gr.Dropdown(
                                    label="Virologie/Infektiologie – Auswahl (optional, Mehrfachauswahl)",
                                    choices=["HIV", "Hepatitis B", "Hepatitis C", "Schistosomiasis (parasitär)", "Andere/unklar"],
                                    multiselect=True,
                                    value=[],
                                    visible=False,
                                ))
                                viro_desc = add("virology_desc", gr.Textbox(label="Virologie/Infektiologie – Details", lines=2, visible=False))

                            with gr.Row():
                                add("immunology_pos", gr.Checkbox(label="Immunologie/Autoimmun positiv"))
                            with gr.Row():
                                immun_items = add("immunology_items", gr.Dropdown(
                                    label="Immunologie/Autoimmun – Auswahl (optional, Mehrfachauswahl)",
                                    choices=[
                                        "Systemische Sklerose (Sklerodermie)",
                                        "SLE (Lupus erythematodes)",
                                        "MCTD (Mixed connective tissue disease)",
                                        "Sjögren-Syndrom",
                                        "Rheumatoide Arthritis",
                                        "Myositis",
                                        "Vaskulitis",
                                        "Antiphospholipid-Syndrom",
                                        "Sarkoidose",
                                        "Andere/unklar",
                                    ],
                                    multiselect=True,
                                    value=[],
                                    visible=False,
                                ))
                                immun_desc = add("immunology_desc", gr.Textbox(label="Immunologie/Autoimmun – Details", lines=2, visible=False))

                    # Genetik
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_gen = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Genetik</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt Genetik' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("mutation_pos", gr.Checkbox(label="Mutation/Genetik relevant (PAH/PH-assoziiert)"))
                            with gr.Row():
                                mut_items = add("mutation_items", gr.Dropdown(
                                    label="Genetik – Auswahl (optional, Mehrfachauswahl)",
                                    choices=[
                                        "BMPR2",
                                        "ACVRL1 (ALK1)",
                                        "ENG",
                                        "SMAD9",
                                        "KCNK3",
                                        "TBX4",
                                        "SOX17",
                                        "ATP13A3",
                                        "GDF2 (BMP9)",
                                        "KDR",
                                        "CAV1",
                                        "EIF2AK4 (PVOD/PCH)",
                                        "Andere/unklar",
                                    ],
                                    multiselect=True,
                                    value=[],
                                    visible=False,
                                ))
                                mut_desc = add("mutation_desc", gr.Textbox(label="Genetik – Details", lines=2, visible=False))

                            # EIF2AK4 separat: Ergebnis/Datum strukturieren (PVOD/PCH)
                            gr.Markdown("#### EIF2AK4 (PVOD/PCH) – strukturiert")
                            with gr.Row():
                                add("eif2ak4_test_done", gr.Checkbox(label="EIF2AK4 Test durchgeführt", value=False))
                                add(
                                    "eif2ak4_result",
                                    gr.Dropdown(
                                        label="EIF2AK4 Ergebnis",
                                        choices=["unklar", "negativ", "positiv"],
                                        value="unklar",
                                        visible=True,
                                    ),
                                )
                                add("eif2ak4_date", gr.Textbox(label="Datum (optional)", placeholder="TT.MM.JJJJ", visible=False))
                            add("eif2ak4_note", gr.Textbox(label="Bemerkung (optional)", lines=2, visible=False))

                    # Abdomen / Leber
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_abd = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Abdomen / Leber</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt Abdomen / Leber' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("abd_sono_done", gr.Checkbox(label="Abdomen-Sono durchgeführt"))
                                abd_desc = add("abd_sono_desc", gr.Textbox(label="Besondere Befunde?", lines=2, visible=False))



                    # Studien Screening (klickbasiert)
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        _hdr_other_study = gr.HTML(  # noqa: F841
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Studien Screening</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar' role='progressbar' aria-label='Fortschritt Studien Screening' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            _tri = ["Unklar / nicht erhoben", "Nein", "Ja"]
                            with gr.Row():
                                add("study_other_trial_recent", gr.Dropdown(label="Andere klinische Studie aktuell oder innerhalb 30 Tage oder 5 HWZ", choices=_tri, value=_tri[0]))
                                add("study_blood_donation_8w", gr.Dropdown(label="Blut oder Plasmaspende >=400 mL in den letzten 8 Wochen", choices=_tri, value=_tri[0]))
                            with gr.Row():
                                add("study_nicotine_active", gr.Dropdown(label="Aktiver Nikotin oder Tabakkonsum", choices=_tri, value=_tri[0]))
                                add("study_caffeine_gt800", gr.Dropdown(label="Koffein >800 mg pro Tag", choices=_tri, value=_tri[0]))
                            with gr.Row():
                                add("study_meds_supp_4w", gr.Dropdown(label="Medikamente Supplemente oder Vitamine in den letzten 4 Wochen", choices=_tri, value=_tri[0]))
                                add("study_cannabis_4w", gr.Dropdown(label="Cannabis in den letzten 4 Wochen", choices=_tri, value=_tri[0]))
                            with gr.Row():
                                add("study_alcohol_substance_misuse_1y", gr.Dropdown(label="Alkohol oder Substanzmissbrauch im letzten Jahr", choices=_tri, value=_tri[0]))
                                add("study_alcohol_drug_test_or_unwilling_72h", gr.Dropdown(label="Positiver Alkohol oder Drogentest oder fehlende Abstinenzbereitschaft ab 72 h", choices=_tri, value=_tri[0]))
                            with gr.Row():
                                add("study_cruciferous_7d", gr.Dropdown(label="Kreuzbluetler in den letzten 7 Tagen", choices=_tri, value=_tri[0]))
                                add("study_grapefruit_14d", gr.Dropdown(label="Grapefruitsaft in den letzten 14 Tagen", choices=_tri, value=_tri[0]))
                            with gr.Row():
                                add("study_pregnancy_lactation", gr.Dropdown(label="Schwangerschaft oder Stillzeit", choices=_tri, value=_tri[0]))
                                add(
                                    "study_childbearing_potential",
                                    gr.Dropdown(
                                        label="Gebärfaehigkeit (nur Frauen)",
                                        choices=[
                                            "Unklar / nicht erhoben",
                                            "Nicht gebaerfaehig (postmenopausal oder OP)",
                                            "Gebaerfaehig",
                                        ],
                                        value="Unklar / nicht erhoben",
                                        visible=True,
                                    ),
                                )

                # ---- Tab 6: Procedere & Module ----
                with gr.TabItem("6. Procedere & Module", id=5):
                    p_ids = sorted([bid for bid, b in blocks.items() if b.kind == "module" and bid.startswith("P")])

                    # Baseline-Choices (werden nach „Generieren“ fallbasiert sortiert & gelabelt)
                    base_module_choices: List[str] = []
                    for pid in p_ids:
                        if pid in blocks:
                            base_module_choices.append(f"{pid} – {blocks[pid].title}")

                    # Visual Card Layer (Auto/Manuell/Gesperrt + Level)
                    # Wichtig: Diese Übersicht soll NICHT überladen wirken. Daher:
                    # - Karten zeigen standardmäßig nur Level I/II + ausgewählte Module.
                    # - Die eigentliche Auswahl erfolgt im Accordion "Module auswählen".
                    modules_cards_html = gr.HTML(value="", elem_id="pmods_cards")

                    # Nicht anwählbare Module inkl. medizinischer Begründung (Tooltip) – bleibt sichtbar
                    modules_disabled_html = gr.HTML(value="", elem_id="modules_disabled")

                    
                    with gr.Accordion("P-Module auswählen / bearbeiten", open=False, elem_id="pmods_accordion"):
                        gr.Markdown("### P-Module (Auswahl)")
                        gr.Markdown("**Level I – prioritäre Empfehlungen** · Level II – sinnvoll ergänzend · Level III – optional")
                        gr.Markdown(
                            "Die P-Module werden nach Sinnhaftigkeit in **Level I–III** sortiert. "
                            "Module können hier bewusst gewählt oder abgewählt werden. "
                            "Nicht empfohlene Module bleiben separat sichtbar und können bei Bedarf wieder **optional** gemacht werden."
                        )

                        # WICHTIG: Keine Checkboxen. Dropdowns sind reine View – die autoritative Quelle ist case_state['ui']['modules'].
                        with gr.Group(elem_id="pmods_lvl1"):
                            modules_lvl1_comp = add(
                                "modules_lvl1",
                                gr.Dropdown(
                                    label="Level I – gewählte Module (Klick zum Abwählen)",
                                    choices=[],
                                    value=[],
                                    multiselect=True,
                                    interactive=True,
                                    elem_id="pmods_choice_lvl1",
                                ),
                            )

                        with gr.Group(elem_id="pmods_lvl2"):
                            modules_lvl2_comp = add(
                                "modules_lvl2",
                                gr.Dropdown(
                                    label="Level II – gewählte Module (Klick zum Abwählen)",
                                    choices=[],
                                    value=[],
                                    multiselect=True,
                                    interactive=True,
                                    elem_id="pmods_choice_lvl2",
                                ),
                            )

                        with gr.Group(elem_id="pmods_lvl3"):
                            modules_lvl3_comp = add(
                                "modules_lvl3",
                                gr.Dropdown(
                                    label="Level III – gewählte Module (Klick zum Abwählen)",
                                    choices=[],
                                    value=[],
                                    multiselect=True,
                                    interactive=True,
                                    elem_id="pmods_choice_lvl3",
                                ),
                            )

                        with gr.Row():
                            pmods_disabled_dd = gr.Dropdown(
                                label="Derzeit nicht empfohlen (bewusst wieder optional machen)",
                                choices=[],
                                value=None,
                                interactive=True,
                                elem_id="pmods_disabled_dd",
                            )
                            pmods_make_optional_btn = gr.Button(
                                "Wieder optional machen",
                                variant="secondary",
                                elem_id="pmods_make_optional_btn",
                            )

                    add("procedere_free", gr.Textbox(label="Procedere – Freitext", lines=3, elem_id="procedere_free"))
                    gr.Markdown("Hinweis: Bereits durchgeführte Untersuchungen werden in den Modulen möglichst ausgefiltert (z.B. V/Q, CT, Echo, Lufu).")

            with gr.Column(scale=5, elem_id="rhk_output_column"):
                dashboard = gr.HTML(value=build_dashboard_html(None), elem_id="rhk_dashboard_wrapper")

                # Copy/paste helpers (plain text, no formatting chaos)
                with gr.Row(elem_id="rhk_copy_row"):
                    _btn_copy_doc = gr.Button("Arztbericht kopieren", variant="secondary", elem_id="btn_copy_doc")  # noqa: F841
                    # Export actions: We generate artifacts into a safe export directory and
                    # expose them via `gr.File` download links.
                    # Rationale: `gr.DownloadButton` has had regressions in some Gradio 6.x
                    # versions when dynamically updated with local file paths.
                    btn_make_docx = gr.Button("DOCX erstellen", variant="secondary", elem_id="btn_make_docx")
                    _btn_copy_pat = gr.Button("Patient*innenbrief komplett kopieren", variant="secondary", elem_id="btn_copy_pat")  # noqa: F841
                    btn_make_docx_zip = gr.Button(
                        "DOCX (ZIP) erstellen",
                        variant="secondary",
                        elem_id="btn_make_docx_zip",
                        visible=False,
                    )
                    btn_make_prerhk_pdf = gr.Button(
                        "Pre-RHK PDF erstellen",
                        variant="secondary",
                        elem_id="btn_make_prerhk_pdf",
                        visible=False,
                    )
                    btn_copy_rhk = gr.Button(
                        "nur RHK Abschnitt kopieren",
                        variant="secondary",
                        elem_id="btn_copy_rhk",
                        visible=False,
                    )
                copy_feedback = gr.Markdown("", elem_id="rhk_copy_feedback")

                # Compact download links (appear after creation)
                with gr.Row(elem_id="rhk_download_files_row"):
                    docx_file = gr.File(
                        label="DOCX",
                        show_label=False,
                        interactive=False,
                        visible=False,
                        elem_id="docx_file",
                    )
                    docx_zip_file = gr.File(
                        label="DOCX ZIP",
                        show_label=False,
                        interactive=False,
                        visible=False,
                        elem_id="docx_zip_file",
                    )
                    prerhk_pdf_file = gr.File(
                        label="Pre-RHK PDF",
                        show_label=False,
                        interactive=False,
                        visible=False,
                        elem_id="prerhk_pdf_file",
                    )

                # Pre-RHK PDF: generated on click; stored in export dir (./exports or OS temp fallback).

                # Klinik-Workaround: serverseitiges Speichern in einen frei wählbaren Ordner.
                # In Cloud/Render ist das NICHT "lokal" auf dem User-PC, daher dort ausgeblendet.
                def _is_cloud_env() -> bool:
                    """Best-effort detection whether we run in a hosted web service.

                    We must *not* use plain `PORT` as a signal because some local setups export it.
                    Render provides `RENDER_EXTERNAL_URL` / `RENDER_EXTERNAL_HOSTNAME` in web services.
                    """
                    return bool(
                        os.environ.get("K_SERVICE")
                        or os.environ.get("RENDER")
                        or os.environ.get("RENDER_EXTERNAL_URL")
                        or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
                    )

                cloud_env = _is_cloud_env()

                with gr.Accordion(
                    "DOCX speichern (nur lokale Installation)",
                    open=False,
                    visible=False,
                    elem_id="docx_save_acc",
                ) as docx_save_acc:
                    with gr.Row(elem_id="rhk_docx_save_row"):
                        docx_save_dir = gr.Textbox(
                            label="Zielordner",
                            placeholder="z.B. C:\\Users\\...\\Documents\\RHK_Befunde oder /home/.../RHK_Befunde",
                            value="",
                            elem_id="docx_save_dir",
                        )
                        btn_save_docx_local = gr.Button("DOCX dort speichern", variant="secondary", elem_id="btn_save_docx_local")
                    docx_save_feedback = gr.Markdown("", elem_id="docx_save_feedback")

                docx_cloud_hint = gr.Markdown(
                    "Hinweis: In der Online-Version sind Downloads (DOCX, DOCX ZIP, Pre RHK PDF) verfügbar. Das direkte Speichern in einen frei wählbaren Ordner ist nur in der lokalen Installation möglich.",
                    visible=False,
                    elem_id="docx_cloud_hint",
                )

                # -----------------------------------------------------------------
                # Download Diagnostics (optional)
                # -----------------------------------------------------------------
                # Motivation
                # - In some Gradio versions / reverse-proxy setups, file downloads can
                #   fail due to file access restrictions (`allowed_paths`) or blocked paths.
                # - This panel gives IT/ops immediate visibility into runtime settings
                #   WITHOUT exposing any patient data.
                def _download_diag_md() -> str:
                    try:
                        exp_dir = str(get_export_dir().resolve())
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_DOWNLOAD_DIAG_EXPORT_DIR", "Download diagnostics could not resolve export directory.", exc)
                        exp_dir = "(unbekannt)"

                    allowed_env = os.environ.get("GRADIO_ALLOWED_PATHS", "")
                    blocked_env = os.environ.get("GRADIO_BLOCKED_PATHS", "")

                    lines = [
                        "### Download-Diagnose (ohne Patientendaten)",
                        f"- Gradio: **{getattr(gr, '__version__', 'unbekannt')}**",
                        f"- Python: **{sys.version.split()[0]}**",
                        f"- OS: **{platform.system()} {platform.release()}**",
                        f"- CWD: `{os.getcwd()}`",
                        f"- Export-Ordner: `{exp_dir}`",
                    ]
                    if allowed_env.strip():
                        lines.append(f"- GRADIO_ALLOWED_PATHS (env): `{allowed_env}`")
                    if blocked_env.strip():
                        lines.append(f"- GRADIO_BLOCKED_PATHS (env): `{blocked_env}`")
                    lines += [
                        "",
                        "**Wenn Downloads nicht funktionieren:**",
                        "1) Prüfe, ob der Export-Ordner oben existiert und beschreibbar ist.",
                        "2) Prüfe `GRADIO_BLOCKED_PATHS` (kann Downloads aus `Temp/exports` blockieren).",
                        "3) Testdatei unten erzeugen und herunterladen.",
                    ]
                    return "\n".join(lines)

                with gr.Accordion(
                    "Download Diagnose (für IT / wenn Download fehlschlägt)",
                    open=False,
                    elem_id="download_diag_acc",
                    visible=False,
                ) as download_diag_acc:
                    _download_diag = gr.Markdown(_download_diag_md(), elem_id="download_diag")  # noqa: F841
                    with gr.Row(elem_id="download_diag_row"):
                        btn_test_download = gr.Button(
                            "Testdatei erstellen",
                            variant="secondary",
                            elem_id="btn_test_download",
                        )
                        test_download_file = gr.File(
                            label="Testdatei",
                            show_label=False,
                            interactive=False,
                            visible=False,
                            elem_id="test_download_file",
                        )

                    def _make_test_download() -> tuple[Any, str]:
                        """Create a tiny, PHI-free file to validate download plumbing."""
                        try:
                            from pathlib import Path

                            exp_dir = Path(get_export_dir()).resolve()
                            exp_dir.mkdir(parents=True, exist_ok=True)
                            ts = time.strftime("%Y%m%d_%H%M%S")
                            p = exp_dir / f"rhk_download_test_{ts}.txt"
                            p.write_text(
                                "RHK Download Test (no PHI)\n" + ts + "\n",
                                encoding="utf-8",
                            )
                            return gr.update(value=str(p), visible=True), f"✅ Testdatei erstellt: {p.name}"
                        except _UI_RECOVERABLE_ERRORS as e:
                            log_exception("RHK_UI_DOWNLOAD_TEST_FILE", "Failed to create download test file.", e)
                            return gr.update(value=None, visible=False), f"⚠️ Testdatei fehlgeschlagen: {type(e).__name__}: {e}"

                    btn_test_download.click(
                        _make_test_download,
                        inputs=None,
                        outputs=[test_download_file, copy_feedback],
                        queue=False,
                        trigger_mode="always_last",
                    )


                # Clipboard payloads MUST stay in DOM for robust cross-browser copy.
                # We hide them via CSS (display:none) instead of Gradio's visible=False,
                # because visible=False may not render the component at all.
                copy_doc_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_doc_plain",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_pat_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_pat_plain",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_rhk_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_rhk_plain",
                    elem_classes=["rhk-hidden-payload"],
                )

                copy_doc_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_doc_html",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_pat_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_pat_html",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_rhk_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_rhk_html",
                    elem_classes=["rhk-hidden-payload"],
                )

                with gr.Row(elem_id="rhk_patient_mode_row"):
                    add(
                        "patient_report_mode",
                        gr.Radio(
                            label="Patientenbericht-Modus",
                            choices=[
                                ("Laienbefund (verständlich, mit Erklärungen)", "laienbefund"),
                                ("Kurzfassung (kompakt)", "kurzfassung"),
                            ],
                            value="laienbefund",
                            elem_id="patient_report_mode",
                        ),
                    )

                with gr.Tabs(elem_id="rhk_output_tabs"):
                    with gr.TabItem("Arztbericht"):
                        out_doc = gr.Markdown(elem_id="out_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Arztbefund (extended)"):
                        out_echo_doc = gr.Markdown(elem_id="out_echo_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Patientenbericht"):
                        out_pat = gr.Markdown(elem_id="out_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Patientenbericht"):
                        out_echo_pat = gr.Markdown(elem_id="out_echo_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Intern", visible=False) as tab_out_internal:
                        btn_update_internal = gr.Button(
                            "Intern-Report aktualisieren",
                            variant="secondary",
                            elem_id="btn_update_internal",
                        )
                        out_int = gr.Markdown(elem_id="out_int", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Summary (JSON)", visible=False) as tab_out_summary:
                        out_summary_json = gr.Code(language="json", elem_id="out_summary_json", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Debug", visible=False) as tab_out_debug:
                        btn_update_debug_json = gr.Button(
                            "Debug JSON aktualisieren",
                            variant="secondary",
                            elem_id="btn_update_debug_json",
                        )
                        out_json = gr.Code(language="json", elem_id="out_json", elem_classes=["rhk-scrollbox"])

        # Buttons bottom (mirrored)
        gr.HTML(
            '<small class="rhk-import-hint-compact">'
            "Der DOCX-Import unterstützt GE MacLab Word-Exporte (z. B. Gießen). "
            "Für andere Zentren empfehlen wir die manuelle Eingabe der Hämodynamik-Werte."
            "</small>",
            elem_id="rhk_import_hint_bottom",
        )
        with gr.Row(elem_id="rhk_actions_bottom_primary"):
            docx_btn_bottom = gr.UploadButton("1. RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_bottom")
            btn_generate_bottom = gr.Button("2. Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_bottom")

        with gr.Row(visible=True, elem_id="rhk_actions_bottom_expert") as expert_actions_bottom:
            btn_example_bottom = gr.Button("Beispiel laden (Suite)", variant="secondary", elem_id="btn_example_bottom")
            btn_clear_bottom = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_bottom")
            save_btn_bottom = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_bottom")
            load_btn_bottom = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_bottom")
            load_followup_btn_bottom = gr.UploadButton(
                "Fall als Verlauf laden (.json)",
                file_types=[".json"],
                variant="secondary",
                elem_id="btn_load_followup_bottom",
            )

        # NOTE: Pre-RHK PDF export button is intentionally only placed in the action row
        # (next to the copy/download helpers) to avoid duplicated triggers and UX confusion.


        file_out = gr.File(label="Download: gespeicherter Fall (.json)", visible=False)
        file_summary_out = gr.File(label="Download: Summary (.json)", visible=False)

        # Single "dirty" ping from the browser (debounced). Avoids binding change-handlers to dozens of fields.
        dirty_ping = gr.Textbox(value="", visible=False, elem_id="rhk_dirty_ping")
        ui_lang = gr.Textbox(value="de", visible=False, elem_id="rhk_ui_lang")

        state_case = gr.State(value=None)
        state_case_filename = gr.State(value="")  # remembered loaded case filename
        state_pmods_selected = gr.State(value={"lvl1": [], "lvl2": [], "lvl3": []})
        state_flags = gr.State(value={"dirty": False, "saved_at": None, "has_report": False, "report_stale": False})

        # Beispielreihe: Index des zuletzt geladenen Beispiels. Initialwert ist
        # -1 (sentinel), damit der allererste Klick jedes Beispiel 0..N-1 als
        # gültigen Kandidaten zulässt.
        state_example_idx = gr.State(value=-1)

        # DOCX import cache (current + previous catheter). Must exist even if user never imports.
        # Stored as full parsed payload dict (or None).
        state_docx_cur = gr.State(value=None)
        state_docx_prev = gr.State(value=None)

        # Echo PDF Import bindings (Textlayer only)
        try:
            bind_echo_import(echo_ui, field_components=field_components)
        except _UI_RECOVERABLE_ERRORS as exc:
            # UI must stay alive even if import bindings fail
            log_exception("RHK_UI_BIND_ECHO_IMPORT", "Echo import bindings failed; UI continues without these bindings.", exc)


        # --- Conditional visibility bindings ---
        def _toggle_desc_text(flag: bool):
            return gr.update(visible=bool(flag))

        def _toggle_ltot(flag: bool):
            return gr.update(visible=bool(flag))

        def _update_egfr(creatinine, age, sex):
            # compute_egfr returns (value, stage)
            val, _stage = compute_egfr(creatinine, age, sex)
            if val is None:
                return gr.update(value=None)
            try:
                return gr.update(value=round(float(val)))
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_EGFR_ROUND", "eGFR rounding failed; clearing computed value.", exc)
                return gr.update(value=None)

        def _update_pre_cath(consent_done, access_route, inr, ptt_s, platelets, anticoag_status, anticoag_paused, crp, creatinine, age, sex,
                             allergies_present, allergies_list, allergies_other_text, lsb_present, lsb_reason):
            egfr_val, _egfr_stage = compute_egfr(creatinine, age, sex)
            try:
                egfr_val = float(egfr_val) if egfr_val is not None else None
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_EGFR_CAST", "eGFR cast to float failed; using None.", exc)
                egfr_val = None
            ui = {
                'consent_done': bool(consent_done),
                'access_route': access_route,
                'inr': inr,
                'ptt_s': ptt_s,
                'platelets_g_l': platelets,
                'anticoag_status': anticoag_status,
                'anticoag_paused': bool(anticoag_paused),
                'crp_mg_l': crp,
                'creatinine_mg_dl': creatinine,
                'egfr_ml_min_1_73': egfr_val,
                'allergies_present': bool(allergies_present),
                'allergies_list': allergies_list,
                'allergies_other_text': allergies_other_text,
                'lsb_present': bool(lsb_present),
                'lsb_reason': (lsb_reason or ''),
            }
            return build_pre_cath_header_html(ui)

        def _update_pre_cath_both(*args):
            h = _update_pre_cath(*args)
            return h, h

        def _toggle_anemia(hb_val, sex_val):
            hb = _safe_float(hb_val)
            anemia = _infer_anemia(sex_val, hb)
            return gr.update(visible=bool(anemia))

        def _bind_change(comp, fn, inputs=None, outputs=None):
            """Bind lightweight change callbacks without queue/loading flicker (best-effort across Gradio versions)."""
            try:
                # Newer Gradio: hide any progress UI (prevents "pulse"/fade on newly visible blocks)
                comp.change(
                    fn,
                    inputs=inputs,
                    outputs=outputs,
                    trigger_mode="always_last",
                    queue=False,
                    show_progress="hidden",
                    scroll_to_output=False,
                )
            except TypeError:
                try:
                    # Older Gradio: no show_progress/scroll_to_output
                    comp.change(fn, inputs=inputs, outputs=outputs, trigger_mode="always_last", queue=False)
                except TypeError:
                    comp.change(fn, inputs=inputs, outputs=outputs)

        def _bind_blur(comp, fn, inputs=None, outputs=None):
            """Bind callbacks on blur (focus loss) for text/number fields to avoid per-keystroke server roundtrips."""
            try:
                comp.blur(
                    fn,
                    inputs=inputs,
                    outputs=outputs,
                    queue=False,
                    show_progress="hidden",
                    scroll_to_output=False,
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                # Fallback: some Gradio versions/components do not expose .blur
                log_exception("RHK_UI_BIND_BLUR", "Component blur binding unavailable; falling back to change binding.", exc)
                _bind_change(comp, fn, inputs=inputs, outputs=outputs)


        # ------------------------------------------------------------------
        # Tab-wise bindings (extracted for maintainability)
        # ------------------------------------------------------------------
        try:
            bind_rhk_bindings(field_components=field_components, bind_change=_bind_change)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_RHK_TAB", "RHK tab bindings failed.", exc)
        try:
            bind_clinic_bindings(field_components=field_components, clinic_ui=clinic_ui, bind_change=_bind_change)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_CLINIC_TAB", "Clinic tab bindings failed.", exc)
        try:
            bind_imaging_bindings(field_components=field_components, imaging_ui=imaging_ui, bind_change=_bind_change)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_IMAGING_TAB", "Imaging tab bindings failed.", exc)
        try:
            bind_cpet_bindings(field_components=field_components, cpet_ui=cpet_ui, bind_change=_bind_change)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_CPET_TAB", "CPET tab bindings failed.", exc)

        # ------------------------------------------------------------------
        # Section header progress (non-sticky, Apple-like)
        # ------------------------------------------------------------------

        def _bind_section_progress(header_comp, title: str, comps: List[Any], calc_fn):
            """Bind progress refresh to all comps in a section (UI-only).

            This is a thin wrapper around :func:`rhk_ui_progress.bind_section_progress`,
            kept local to reuse the version-tolerant ``_bind_change`` / ``_bind_blur``
            helpers of this UI scope.
            """
            return _bind_section_progress_core(
                header_comp,
                title,
                comps,
                calc_fn,
                bind_change=_bind_change,
                bind_blur=_bind_blur,
            )


        # One-shot sync for visibility + computed fields after programmatic UI loads
        def _sync_post_load(
            ct_done_v, ct_ild_v, vq_done_v,
            creatinine, age, sex,
            allergies_present_v, allergies_list_v,
            pvod_edema_on_vaso_v, pvod_edema_desc_v,
            eif2ak4_test_done_v, eif2ak4_result_v, eif2ak4_date_v, eif2ak4_note_v,
        ):
            # Allergie-Details sichtbar wenn Checkbox aktiv ODER wenn bereits Einträge vorhanden sind
            al_list = allergies_list_v if isinstance(allergies_list_v, list) else ([] if allergies_list_v in (None, "") else [str(allergies_list_v)])
            show_allergies = bool(allergies_present_v) or bool(al_list)
            show_other = any(str(x).strip().lower() == "sonstiges" for x in al_list)

            # PVOD/PCH: Detailfelder sichtbar wenn aktiviert ODER wenn Inhalt vorhanden
            show_pvod_edema = bool(pvod_edema_on_vaso_v) or bool(str(pvod_edema_desc_v or "").strip())

            eif_res = str(eif2ak4_result_v or "").strip().lower()
            show_eif = bool(eif2ak4_test_done_v) or (eif_res not in ("", "unklar")) or bool(str(eif2ak4_date_v or "").strip()) or bool(str(eif2ak4_note_v or "").strip())
            return (
                gr.update(visible=bool(ct_done_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(vq_done_v)),
                _update_egfr(creatinine, age, sex),
                gr.update(visible=show_allergies),
                gr.update(visible=show_other),
                gr.update(visible=show_pvod_edema),
                gr.update(visible=show_eif),
                gr.update(visible=show_eif),
                gr.update(visible=show_eif),
            )

        def _sync_post_load_cpet(
            cpet_done_v,
            peak_vo2, peak_vo2_pct,
            vo2_peak_reached,
            vt1_method, vt1_manual_checked, vt1_time_min,
            vevco2_slope, petco2_vt1, vevco2_vt1,
            o2pulse_pct, vo2_wr_slope, vo2_vt1,
            spo2_nadir, rer_peak, hr_peak,
            o2_pulse_pattern,
        ):
            # Show the CPET card details as soon as any CPET value is entered.
            # This prevents the "no live explanation" situation when users forget to tick CPET done.
            try:
                has_any = any(
                    _is_filled(v)
                    for v in [
                        peak_vo2, peak_vo2_pct,
                        vo2_peak_reached, vt1_method, vt1_manual_checked, vt1_time_min,
                        vevco2_slope, petco2_vt1, vevco2_vt1,
                        o2pulse_pct, vo2_wr_slope, vo2_vt1,
                        spo2_nadir, rer_peak, hr_peak, o2_pulse_pattern,
                    ]
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_CPET_HAS_ANY", "CPET visibility pre-check failed; falling back to done flag.", exc)
                has_any = bool(cpet_done_v)

            show_details = bool(cpet_done_v) or bool(has_any)
            return (
                gr.update(visible=show_details),
                _render_cpet_risk_html(
                    cpet_done_v,
                    peak_vo2, peak_vo2_pct,
                    vo2_peak_reached,
                    vt1_method, vt1_manual_checked, vt1_time_min,
                    vevco2_slope, petco2_vt1, vevco2_vt1,
                    o2pulse_pct, vo2_wr_slope, vo2_vt1,
                    spo2_nadir, rer_peak, hr_peak,
                    o2_pulse_pattern,
                ),
            )

        # Spiro-Logic wizard: live education + pattern recognition (deterministic)
        # Keep a tiny cache to avoid re-running analysis when inputs did not change (UI feels "live").
        _cpet_wiz_cache = {"sig": None, "out": None}
        def _sync_post_load_cpet_wizard(
            cpet_done_v,
            stop_reason, stop_reason_text,
            borg_rpe, borg_dyspnoe, borg_legs,
            rer_peak, hr_rest, hr_peak, hr_pct,
            peak_vo2, peak_vo2_pct, vo2_peak_reached,
            vt1_method, vt1_manual_checked, vt1_time_min,
            o2p_ml, o2p_pattern, o2p_slope,
            bp_sys_rest, bp_dia_rest,
            bp_sys, bp_dia,
            vevco2_slope, vevco2_nadir, oues,
            pet_rest, pet_peak, pet_vt1,
            br_pct,
            vevco2_vt1,
            spo2_rest, spo2_peak, spo2_nadir, o2_supp,
            vo2_wr_slope,
            ve_peak, mvv, mvv_source,
            angina, dizziness, syncope, palpitations,
            arrhythmia, arrhythmia_text, st_changes,
            beta_blocker, sinus_node, hypervent,
            chrono_comment,
            limitation_override, limitation_override_text, next_steps_manual,
            nine_avail, nine_vt1, nine_vt1_method, nine_rcp,
            nine_eov, nine_flow, nine_vo2wr, nine_veeq, nine_comment,
            age=None, sex=None, height_cm=None, weight_kg=None,
        ):
            done_flag = bool(cpet_done_v)

            # If CPET is marked done but no meaningful values are present, keep UI responsive
            _core_vals = [
                stop_reason, borg_rpe, borg_dyspnoe, borg_legs, rer_peak, hr_rest, hr_peak, hr_pct,
                peak_vo2, peak_vo2_pct, vo2_peak_reached, vt1_method, vt1_manual_checked, vt1_time_min, o2p_ml, o2p_pattern, o2p_slope,
                bp_sys_rest, bp_dia_rest, bp_sys, bp_dia,
                vevco2_slope, vevco2_nadir, oues,
                pet_rest, pet_peak, pet_vt1, br_pct, vevco2_vt1,
                spo2_rest, spo2_peak, spo2_nadir, o2_supp, vo2_wr_slope,
                ve_peak, mvv, mvv_source,
                angina, dizziness, syncope, palpitations,
                arrhythmia, st_changes,
                beta_blocker, sinus_node, hypervent,
                limitation_override,
                nine_avail, nine_vt1, nine_vt1_method, nine_rcp,
                nine_eov, nine_flow, nine_vo2wr, nine_veeq,
            ]
            try:
                has_any = any(_is_filled(v) for v in _core_vals)
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_CPET_WIZ_HAS_ANY", "CPET wizard core-value check failed; forcing conservative fallback.", exc)
                has_any = True
            if not has_any:
                msg = "<div class='docx-muted'>Bitte CPET Werte eingeben.</div>"
                return (
                    msg,
                    "", "", "", "", "", "", "", "",
                    "",
                    msg,
                    msg,
                    msg,
                    "",
                    gr.update(visible=False),
                )

            ui_tmp = {
                # For the wizard logic we treat "done" as the user flag, but we allow preview even if not set.
                "cpet_done": done_flag,
                "cpet_stop_reason": stop_reason,
                "cpet_stop_reason_text": stop_reason_text,
                "cpet_borg_rpe": borg_rpe,
                "cpet_borg_dyspnoe": borg_dyspnoe,
                "cpet_borg_dyspnea": borg_dyspnoe,
                "cpet_borg_legs": borg_legs,
                "cpet_borg_leg": borg_legs,
                "cpet_rer_peak": rer_peak,
                "cpet_hr_rest_bpm": hr_rest,
                "cpet_hr_peak_bpm": hr_peak,
                "cpet_hr_pct_pred": hr_pct,
                "cpet_peak_vo2_ml_kg_min": peak_vo2,
                "cpet_peak_vo2_pct_pred": peak_vo2_pct,
                "cpet_peak_o2_pulse_ml": o2p_ml,
                "cpet_o2_pulse_pattern": o2p_pattern,
                "cpet_o2_pulse_slope": o2p_slope,
                "cpet_bp_sys_rest": bp_sys_rest,
                "cpet_bp_dia_rest": bp_dia_rest,
                "cpet_bp_sys_peak": bp_sys,
                "cpet_bp_dia_peak": bp_dia,
                "cpet_ve_vco2_slope": vevco2_slope,
                "cpet_ve_vco2_nadir": vevco2_nadir,
                "cpet_oues": oues,
                # Anthropometrics for Wasserman/Tanaka predicted values
                "age": age,
                "sex": sex,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "cpet_petco2_rest_mmhg": pet_rest,
                "cpet_petco2_peak_mmhg": pet_peak,
                "cpet_petco2_vt1_mmhg": pet_vt1,
                "cpet_breathing_reserve_pct": br_pct,
                "cpet_ve_vco2_vt1": vevco2_vt1,
                "cpet_spo2_rest_pct": spo2_rest,
                "cpet_spo2_peak_pct": spo2_peak,
                "cpet_spo2_nadir_pct": spo2_nadir,
                "cpet_o2_supp_l_min": o2_supp,
                "cpet_vo2_wr_slope_ml_min_w": vo2_wr_slope,
                "cpet_ve_peak_l_min": ve_peak,
                "cpet_mvv_l_min": mvv,
                "cpet_mvv_source": mvv_source,
                "cpet_angina": bool(angina),
                "cpet_dizziness": bool(dizziness),
                "cpet_syncope": bool(syncope),
                "cpet_palpitations": bool(palpitations),
                "cpet_arrhythmia": bool(arrhythmia),
                "cpet_arrhythmia_text": arrhythmia_text,
                "cpet_st_changes": st_changes,
                "cpet_beta_blocker": bool(beta_blocker),
                "cpet_sinus_node_disorder": bool(sinus_node),
                "cpet_hyperventilation": bool(hypervent),
                "cpet_chrono_comment": chrono_comment,
                "cpet_limitation_override": limitation_override,
                "cpet_limitation_override_text": limitation_override_text,
                "cpet_next_steps_manual": next_steps_manual,
                "cpet_9panel_available": bool(nine_avail),
                "cpet_9panel_vt1_identified": nine_vt1,
                "cpet_9panel_vt1_method": nine_vt1_method,
                "cpet_9panel_rcp_identified": nine_rcp,
                "cpet_9panel_eov": bool(nine_eov),
                "cpet_9panel_flowvol_limit": nine_flow,
                "cpet_9panel_vo2wr_pattern": nine_vo2wr,
                "cpet_9panel_veeq_pattern": nine_veeq,
                "cpet_9panel_comment": nine_comment,
            }
            try:
                # Dict literal order is stable; avoid sorting on every input event.
                sig = tuple(ui_tmp.items())
                if _cpet_wiz_cache.get("sig") == sig and isinstance(_cpet_wiz_cache.get("out"), dict):
                    out = _cpet_wiz_cache.get("out")
                else:
                    out = _get_spiro_logic().build_cpet_outputs(ui_tmp)
                    _cpet_wiz_cache["sig"] = sig
                    _cpet_wiz_cache["out"] = out
            except _UI_RECOVERABLE_ERRORS as e:
                # Fail-safe: never crash the clinical UI. Log details for admins.
                log_exception("RHK_UI_CPET_WIZ_RUN", "CPET wizard execution failed; fallback content used.", e)
                teach = (
                    "<details class='spiro-edu__details' open>"
                    "<summary class='spiro-edu__summary'>Lernmodul V'O2 (Sauerstoffaufnahme)</summary>"
                    "<div class='spiro-edu__teach'>"
                    "<div class='spiro-edu__sub'>Kernaussage</div>"
                    "<div>V'O2 ist der zentrale integrative Parameter der CPET. Er bildet das Zusammenspiel von Lunge, Kreislauf und Muskulatur ab.</div>"
                    "<div class='spiro-edu__sub'>Fick Prinzip</div>"
                    "<div>V'O2 = Herzzeitvolumen × C(a v)O2.</div>"
                    "<div class='spiro-edu__sub'>Hinweis</div>"
                    "<div>Dieses Lernmodul ist read only. Es trifft keine Aussagen zum individuellen Befund.</div>"
                    "</div></details>"
                )
                msg = teach + (
                    "<div class='docx-muted'>Spiro-Logic CPET-Wizard konnte nicht ausgeführt werden. "
                    "Ausgabe deaktiviert (Details in Konsole).</div>"
                )
                out = {
                    "mod0_html": msg,
                    "mod1_html": "",
                    "mod2_html": "",
                    "mod3_html": "",
                    "mod4_html": "",
                    "mod5_html": "",
                    "mod6_html": "",
                    "mod7_html": "",
                    "mod9_html": "",
                    "modfinal_html": "",
                    "overall_html": msg,
                    "live_html": msg,
                    "report_text": "",
                    "need_chrono_followups": False,
                }

            # Follow up block should remain visible if triggered OR already filled
            show_follow = bool(out.get("need_chrono_followups")) or bool(beta_blocker) or bool(sinus_node) or bool(hypervent) or bool(str(chrono_comment or "").strip())

            # Report text for copy use
            report_text = out.get("report_text") or ""

            # Live box should show the most helpful content immediately.
            live_html = out.get("live_html") or ""
            overall_html = out.get("overall_html") or ""
            teaching_html = out.get("teaching_html") or ""
            if not done_flag:
                note = (
                    "<div class='docx-muted'>Hinweis: CPET ist nicht als durchgeführt markiert. "
                    "Spiro-Logic läuft als Vorschau und wird nicht automatisch in den Bericht übernommen.</div>"
                )
                live_html = note + live_html
                overall_html = note + overall_html

            return (
                out.get("mod0_html") or "",
                out.get("mod1_html") or "",
                out.get("mod2_html") or "",
                out.get("mod3_html") or "",
                out.get("mod4_html") or "",
                out.get("mod5_html") or "",
                out.get("mod6_html") or "",
                out.get("mod7_html") or "",
                out.get("mod9_html") or "",
                out.get("modfinal_html") or "",
                overall_html,
                live_html,
                teaching_html,
                report_text,
                gr.update(visible=show_follow),
            )

        def _adopt_spiro_report_to_summary(current_summary: str, spiro_report_text: str):
            current_summary = str(current_summary or "").strip()
            spiro_report_text = str(spiro_report_text or "").strip()
            if not spiro_report_text:
                return (current_summary, "<div class='docx-muted'>Kein Spiro-Logic Text vorhanden.</div>")
            if current_summary:
                return (current_summary, "<div class='docx-muted'>CPET Kommentar ist bereits gefüllt. Übernahme wird zum Schutz vor Überschreiben blockiert.</div>")
            return (spiro_report_text, "<div class='docx-muted'>Spiro-Logic Text als CPET Kommentar übernommen.</div>")

        _bind_change(field_components["virology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["virology_pos"]], outputs=[viro_items, viro_desc])
        _bind_change(field_components["immunology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["immunology_pos"]], outputs=[immun_items, immun_desc])
        _bind_change(field_components["mutation_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["mutation_pos"]], outputs=[mut_items, mut_desc])

        # PVOD/PCH – Zusatzfelder strikt an Checkboxen koppeln
        _bind_change(
            field_components["pvod_edema_on_vaso"],
            lambda x: gr.update(visible=bool(x)),
            inputs=[field_components["pvod_edema_on_vaso"]],
            outputs=[field_components["pvod_edema_desc"]],
        )

        _bind_change(
            field_components["eif2ak4_test_done"],
            lambda x: (
                gr.update(visible=bool(x)),
                gr.update(visible=bool(x)),
                gr.update(visible=bool(x)),
            ),
            inputs=[field_components["eif2ak4_test_done"]],
            outputs=[field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"]],
        )
        _bind_change(field_components["abd_sono_done"], lambda x: _toggle_desc_text(x), inputs=[field_components["abd_sono_done"]], outputs=[abd_desc])
        _bind_change(field_components["ltot"], lambda x: _toggle_ltot(x), inputs=[field_components["ltot"]], outputs=[ltot_flow])

        # Thorax/ILD/VQ – intelligente Sichtbarkeit
        # CTEPD ohne PH: Kriterien nur sichtbar, wenn V/Q pathologisch markiert ist
        # V/Q Zusatzfelder: Sichtbarkeit strikt an Checkboxen koppeln
        _bind_change(
            field_components["vq_pa_angio_done"],
            lambda x: gr.update(visible=bool(x)),
            inputs=[field_components["vq_pa_angio_done"]],
            outputs=[field_components["vq_pa_angio_desc"]],
        )
        _bind_change(
            field_components["vq_cteph_conf_done"],
            lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))),
            inputs=[field_components["vq_cteph_conf_done"]],
            outputs=[field_components["vq_cteph_conf_date"], field_components["vq_cteph_conf_decision"]],
        )

        # eGFR (auto) – update on creatinine/age/sex changes
        # eGFR depends only on creatinine, age, sex (do not pass unrelated inputs).
        _bind_blur(
            field_components["creatinine_mg_dl"],
            _update_egfr,
            inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"]],
            outputs=[field_components["egfr_ml_min_1_73"]],
        )
        _bind_blur(
            field_components["age"],
            _update_egfr,
            inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"]],
            outputs=[field_components["egfr_ml_min_1_73"]],
        )
        _bind_change(
            field_components["sex"],
            _update_egfr,
            inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"]],
            outputs=[field_components["egfr_ml_min_1_73"]],
        )

        # CPET (Spiroergometrie): Sichtbarkeit + Live-Risiko
        try:
            _cpet_inputs = [
                field_components["cpet_done"],
                field_components["cpet_peak_vo2_ml_kg_min"],
                field_components["cpet_peak_vo2_pct_pred"],
                field_components["cpet_vo2_peak_reached"],
                field_components["cpet_vt1_method"],
                field_components["cpet_vt1_manual_checked"],
                field_components["cpet_vt1_time_min"],
                field_components["cpet_ve_vco2_slope"],
                field_components["cpet_petco2_vt1_mmhg"],
                field_components["cpet_ve_vco2_vt1"],
                field_components["cpet_peak_o2_pulse_pct_pred"],
                field_components["cpet_vo2_wr_slope_ml_min_w"],
                field_components["cpet_vo2_vt1_ml_kg_min"],
                field_components["cpet_spo2_nadir_pct"],
                field_components["cpet_rer_peak"],
                field_components["cpet_hr_peak_bpm"],
                field_components["cpet_o2_pulse_pattern"],
            ]
            for _k in (
                "cpet_done",
                "cpet_peak_vo2_ml_kg_min", "cpet_peak_vo2_pct_pred", "cpet_vo2_peak_reached", "cpet_vt1_method", "cpet_vt1_manual_checked", "cpet_vt1_time_min",
                "cpet_ve_vco2_slope", "cpet_petco2_vt1_mmhg", "cpet_ve_vco2_vt1",
                "cpet_peak_o2_pulse_pct_pred", "cpet_vo2_wr_slope_ml_min_w", "cpet_vo2_vt1_ml_kg_min",
                "cpet_spo2_nadir_pct", "cpet_rer_peak", "cpet_hr_peak_bpm",
                "cpet_o2_pulse_pattern",
            ):
                # Performance: avoid per-keystroke server roundtrips on numeric inputs.
                if _k in ("cpet_done", "cpet_o2_pulse_pattern"):
                    _bind_change(field_components[_k], _sync_post_load_cpet, inputs=_cpet_inputs, outputs=[cpet_details, cpet_risk_html])
                else:
                    _bind_blur(field_components[_k], _sync_post_load_cpet, inputs=_cpet_inputs, outputs=[cpet_details, cpet_risk_html])
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_CPET_SYNC", "Binding CPET live sync callbacks failed.", exc)

        # CPET Spiro-Logic Wizard: live education blocks + follow up visibility
        try:
            _cpet_wiz_inputs = [
                field_components["cpet_done"],
                field_components["cpet_stop_reason"],
                field_components["cpet_stop_reason_text"],
                field_components["cpet_borg_rpe"],
                field_components["cpet_borg_dyspnoe"],
                field_components["cpet_borg_legs"],
                field_components["cpet_rer_peak"],
                field_components["cpet_hr_rest_bpm"],
                field_components["cpet_hr_peak_bpm"],
                field_components["cpet_hr_pct_pred"],
                field_components["cpet_peak_vo2_ml_kg_min"],
                field_components["cpet_peak_vo2_pct_pred"],
                field_components["cpet_vo2_peak_reached"],
                field_components["cpet_vt1_method"],
                field_components["cpet_vt1_manual_checked"],
                field_components["cpet_vt1_time_min"],
                field_components["cpet_peak_o2_pulse_ml"],
                field_components["cpet_o2_pulse_pattern"],
                field_components["cpet_o2_pulse_slope"],
                field_components["cpet_bp_sys_rest"],
                field_components["cpet_bp_dia_rest"],
                field_components["cpet_bp_sys_peak"],
                field_components["cpet_bp_dia_peak"],
                field_components["cpet_ve_vco2_slope"],
                field_components["cpet_ve_vco2_nadir"],
                field_components["cpet_oues"],
                field_components["cpet_petco2_rest_mmhg"],
                field_components["cpet_petco2_peak_mmhg"],
                field_components["cpet_petco2_vt1_mmhg"],
                field_components["cpet_breathing_reserve_pct"],
                field_components["cpet_ve_vco2_vt1"],
                field_components["cpet_spo2_rest_pct"],
                field_components["cpet_spo2_peak_pct"],
                field_components["cpet_spo2_nadir_pct"],
                field_components["cpet_o2_supp_l_min"],
                field_components["cpet_vo2_wr_slope_ml_min_w"],
                field_components["cpet_ve_peak_l_min"],
                field_components["cpet_mvv_l_min"],
                field_components["cpet_mvv_source"],
                field_components["cpet_angina"],
                field_components["cpet_dizziness"],
                field_components["cpet_syncope"],
                field_components["cpet_palpitations"],
                field_components["cpet_arrhythmia"],
                field_components["cpet_arrhythmia_text"],
                field_components["cpet_st_changes"],
                field_components["cpet_beta_blocker"],
                field_components["cpet_sinus_node_disorder"],
                field_components["cpet_hyperventilation"],
                field_components["cpet_chrono_comment"],
                field_components["cpet_limitation_override"],
                field_components["cpet_limitation_override_text"],
                field_components["cpet_next_steps_manual"],
                field_components["cpet_9panel_available"],
                field_components["cpet_9panel_vt1_identified"],
                field_components["cpet_9panel_vt1_method"],
                field_components["cpet_9panel_rcp_identified"],
                field_components["cpet_9panel_eov"],
                field_components["cpet_9panel_flowvol_limit"],
                field_components["cpet_9panel_vo2wr_pattern"],
                field_components["cpet_9panel_veeq_pattern"],
                field_components["cpet_9panel_comment"],
            ]
            # Append anthropometrics if the clinical tab is already built (for chips).
            for _anth in ("age", "sex", "height_cm", "weight_kg"):
                if _anth in field_components:
                    _cpet_wiz_inputs.append(field_components[_anth])

            for _k in (
                "cpet_done",
                "cpet_stop_reason", "cpet_stop_reason_text",
                "cpet_borg_rpe", "cpet_borg_dyspnoe", "cpet_borg_legs",
                "cpet_rer_peak", "cpet_hr_rest_bpm", "cpet_hr_peak_bpm", "cpet_hr_pct_pred",
                "cpet_peak_vo2_ml_kg_min", "cpet_peak_vo2_pct_pred", "cpet_vo2_peak_reached", "cpet_vt1_method", "cpet_vt1_manual_checked", "cpet_vt1_time_min",
                "cpet_peak_o2_pulse_ml", "cpet_o2_pulse_pattern", "cpet_o2_pulse_slope",
                "cpet_bp_sys_rest", "cpet_bp_dia_rest", "cpet_bp_sys_peak", "cpet_bp_dia_peak",
                "cpet_ve_vco2_slope", "cpet_ve_vco2_nadir", "cpet_oues",
                "cpet_petco2_rest_mmhg", "cpet_petco2_peak_mmhg", "cpet_petco2_vt1_mmhg",
                "cpet_breathing_reserve_pct",
                "cpet_ve_vco2_vt1", "cpet_spo2_rest_pct", "cpet_spo2_peak_pct", "cpet_spo2_nadir_pct", "cpet_o2_supp_l_min",
                "cpet_vo2_wr_slope_ml_min_w",
                "cpet_ve_peak_l_min", "cpet_mvv_l_min", "cpet_mvv_source",
                "cpet_angina", "cpet_dizziness", "cpet_syncope", "cpet_palpitations",
                "cpet_arrhythmia", "cpet_arrhythmia_text", "cpet_st_changes",
                "cpet_beta_blocker", "cpet_sinus_node_disorder", "cpet_hyperventilation", "cpet_chrono_comment",
                "cpet_limitation_override", "cpet_limitation_override_text", "cpet_next_steps_manual",
                "cpet_9panel_available", "cpet_9panel_vt1_identified", "cpet_9panel_vt1_method", "cpet_9panel_rcp_identified",
                "cpet_9panel_eov", "cpet_9panel_flowvol_limit", "cpet_9panel_vo2wr_pattern", "cpet_9panel_veeq_pattern", "cpet_9panel_comment",
            ):
                if _k in field_components:
                    _comp = field_components[_k]
                    try:
                        _cname = (_comp.__class__.__name__ or "").lower()
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_COMPONENT_CLASSNAME", "Component class name lookup failed; defaulting to empty.", exc, key=_k)
                        _cname = ""

                    # Performance: for text/number inputs, update Spiro-Logic on blur (avoid per-keystroke roundtrips).
                    if _cname in ("textbox", "number") and hasattr(_comp, "blur"):
                        _bind_blur(
                            _comp,
                            _sync_post_load_cpet_wizard,
                            inputs=_cpet_wiz_inputs,
                            outputs=[cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_live_html, cpet_teaching_html, cpet_spiro_report, cpet_chrono_followup],
                        )
                    else:
                        _bind_change(
                            _comp,
                            _sync_post_load_cpet_wizard,
                            inputs=_cpet_wiz_inputs,
                            outputs=[cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_live_html, cpet_teaching_html, cpet_spiro_report, cpet_chrono_followup],
                        )
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_CPET_WIZARD", "Binding CPET wizard callbacks failed.", exc)

        # Adopt generated Spiro-Logic text into manual CPET comment (only if empty)
        try:
            btn_cpet_adopt.click(
                _adopt_spiro_report_to_summary,
                inputs=[field_components["cpet_summary"], cpet_spiro_report],
                outputs=[field_components["cpet_summary"], cpet_spiro_status],
            )
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_CPET_ADOPT", "Binding CPET adopt button failed.", exc)

        # Pre-Cath Safety Header – update on relevant field changes
        try:
            _pre_cath_inputs = [
                field_components["consent_done"],
                field_components["access_route"],
                field_components["inr"],
                field_components["ptt_s"],
                field_components["platelets_g_l"],
                field_components["anticoag_status"],
                field_components["anticoag_paused"],
                field_components["crp_mg_l"],
                field_components["creatinine_mg_dl"],
                field_components["age"],
                field_components["sex"],
                field_components["allergies_present"],
                field_components["allergies_list"],
                field_components["allergies_other_text"],
                field_components["lsb_present"],
                field_components["lsb_reason"],
            ]
            # Update on any of these changes
            for _k in (
                "consent_done", "access_route", "inr", "ptt_s", "platelets_g_l",
                "anticoag_status", "anticoag_paused", "crp_mg_l",
                "creatinine_mg_dl", "age", "sex",
                "allergies_present", "allergies_list", "allergies_other_text",
                "lsb_present", "lsb_reason",
            ):
                _bind_change(field_components[_k], _update_pre_cath_both, inputs=_pre_cath_inputs, outputs=[pre_cath_html, pre_cath_home_html])
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_PRE_CATH", "Binding pre-cath header callbacks failed.", exc)


        # Anemia type show/hide when Hb or sex changes
        _bind_change(field_components["hb_g_dl"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        _bind_change(field_components["sex"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])


        # ------------------------------------------------------------------
        # Section progress headers (UI only, no clinical logic)
        # ------------------------------------------------------------------

        # Klinik – Allgemeines
        _sec_general_comps = [
            field_components["firstname"], field_components["name"], field_components["age"], field_components["sex"],
            field_components["height_cm"], field_components["weight_kg"], field_components["bp_sys"], field_components["bp_dia"],
            field_components["hr"], field_components["story"], field_components["comorbidities"],
            field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
            field_components["chd_pos"], field_components["chd_type"], field_components["chd_desc"],
            field_components["ph_known"], field_components["ph_known_dx"], field_components["ph_first_dx"], field_components["ph_reason_rhk"],
        ]

        def _calc_general(*vals):
            (
                firstname, name, age, sex, height_cm, weight_kg, bp_sys, bp_dia, hr, story, comorb,
                allergies_present, allergies_list, allergies_other,
                chd_pos, chd_type, chd_desc,
                ph_known, ph_known_dx, ph_first_dx, ph_reason,
            ) = vals

            base = [firstname, name, age, sex, height_cm, weight_kg, bp_sys, bp_dia, hr, story, comorb]
            total = len(base)
            filled = sum(1 for v in base if _is_filled(v))

            # Allergies: only count details if allergies are present or already documented
            al_list = allergies_list if isinstance(allergies_list, list) else ([] if allergies_list in (None, "") else [str(allergies_list)])
            if bool(allergies_present) or bool(al_list) or _is_filled(allergies_other):
                total += 1
                filled += 1 if bool(al_list) or _is_filled(allergies_other) else 0

            # CHD: only count details if CHD is flagged
            if bool(chd_pos):
                total += 1
                filled += 1 if _is_filled(chd_type) or _is_filled(chd_desc) else 0

            # Known PH: count minimal context if flagged
            if bool(ph_known):
                extra = [ph_known_dx, ph_first_dx, ph_reason]
                total += len(extra)
                filled += sum(1 for v in extra if _is_filled(v))

            return filled, total

        _bind_section_progress(hdr_klinik_general, "Allgemeines, Anamnese, Vorerkrankungen", _sec_general_comps, _calc_general)

        # Klinik – Symptome
        _sec_symp_comps = [
            field_components["who_fc"], field_components["six_mwd_m"], field_components["six_mwd_date"], field_components["syncope"],
            field_components["hemoptysis"], field_components["dizziness"], field_components["stairs_flights"],
        ]

        def _calc_symptoms(*vals):
            who_fc, six_mwd, six_date, syncope, hemoptysis, dizziness, stairs = vals
            core = [who_fc, six_mwd, syncope, stairs]
            # date is optional; count if provided
            total = len(core) + 1
            filled = sum(1 for v in core if _is_filled(v)) + (1 if _is_filled(six_date) else 0)
            # symptom checkboxes are optional, but if checked they count as additional documentation
            # (do not increase total to avoid penalizing stable/asymptomatic patients)
            if bool(hemoptysis):
                filled = min(total, filled + 1)
            if bool(dizziness):
                filled = min(total, filled + 1)
            return filled, total

        _bind_section_progress(hdr_klinik_symptoms, "Funktion / Symptome", _sec_symp_comps, _calc_symptoms)

        # Klinik – Labor
        _sec_labs_comps = [
            field_components["hb_g_dl"], field_components["leukocytes_g_l"], field_components["platelets_g_l"],
            field_components["inr"], field_components["ptt_s"], field_components["creatinine_mg_dl"], field_components["crp_mg_l"],
            field_components["bnp_value"], field_components["congestive_organopathy"],
        ]

        def _calc_labs(*vals):
            total = len(vals)
            filled = sum(1 for v in vals if _is_filled(v))
            return filled, total

        _bind_section_progress(hdr_klinik_labs, "Labor", _sec_labs_comps, _calc_labs)

        # Klinik – Medikation
        _sec_meds_comps = [
            field_components["anticoag_status"], field_components["anticoag_substance"], field_components["anticoag_indication"],
            field_components["anticoag_since"], field_components["ltx_eval"], field_components["ltx_eval_date"],
        ]

        def _calc_meds(*vals):
            anticoag_status, anticoag_sub, anticoag_ind, anticoag_since, ltx_eval, ltx_date = vals
            base = [ltx_eval]
            total = len(base)
            filled = sum(1 for v in base if _is_filled(v))

            s = str(anticoag_status or "").strip().lower()
            # Only count anticoag details when anticoag is present
            if s == "ja" or "paus" in s:
                extra = [anticoag_status, anticoag_sub, anticoag_ind]
                total += len(extra)
                filled += sum(1 for v in extra if _is_filled(v))
                # since is optional; count if provided
                total += 1
                filled += 1 if _is_filled(anticoag_since) else 0
            return filled, total

        _bind_section_progress(hdr_klinik_meds, "Medikation & wichtige Zusatzangaben", _sec_meds_comps, _calc_meds)

        # Bildgebung – Thorax
        _sec_imaging_comps = [
            field_components["ct_done"], field_components["ct_desc"], field_components["ct_ild"], field_components["ild_type"],
            field_components["antifibrotic_status"], field_components["vq_done"], field_components["vq_desc"],
        ]

        def _calc_imaging(*vals):
            ct_done, ct_desc, ct_ild, ild_type, antifib_status, vq_done, vq_desc = vals
            total = 0
            filled = 0
            if bool(ct_done):
                total += 1
                filled += 1 if _is_filled(ct_desc) else 0
                if bool(ct_ild):
                    total += 1
                    filled += 1 if _is_filled(ild_type) else 0
                    total += 1
                    filled += 1 if _is_filled(antifib_status) else 0
            if bool(vq_done):
                total += 1
                filled += 1 if _is_filled(vq_desc) else 0
            return filled, total

        _bind_section_progress(hdr_imaging, "Thorax-Bildgebung", _sec_imaging_comps, _calc_imaging)

        # Echo – compact progress (key parameters)
        _sec_echo_comps = [
            field_components["lvef"], field_components["pasp_echo"], field_components["tapse_mm"],
            field_components["s_prime_cm_s"], field_components["ee_ratio"],
        ]

        def _calc_echo(*vals):
            total = len(vals)
            filled = sum(1 for v in vals if _is_filled(v))
            return filled, total

        _bind_section_progress(hdr_echo, "Echokardiographie", _sec_echo_comps, _calc_echo)

        # CMR – optional
        _sec_cmr_comps = [
            field_components["cmr_done"],
            field_components["rvef"],
            field_components["rvedv"],
            field_components["rvesv"],
            field_components["rvedvi"],
            field_components["rvesvi"],
        ]

        def _calc_cmr(*vals):
            cmr_done, rvef, rvedv, rvesv, rvedvi, rvesvi = vals
            if not bool(cmr_done):
                return 0, 0
            fields = [rvef, rvedv, rvesv, rvedvi, rvesvi]
            total = len(fields)
            filled = sum(1 for v in fields if _is_filled(v))
            return filled, total

        _bind_section_progress(hdr_cmr, "MRT / CMR", _sec_cmr_comps, _calc_cmr)

        # CMR: Index-Volumina aus EDV/ESV + BSA berechnen (abgeleitete Felder; immer konsistent halten)
        def _cmr_auto_index(cmr_done, rvedv, rvesv, height_cm, weight_kg):
            edv = _safe_num(rvedv)
            esv = _safe_num(rvesv)
            if edv is not None and edv <= 0:
                edv = None
            if esv is not None and esv <= 0:
                esv = None

            # Wenn weder CMR aktiv ist noch Volumina vorliegen: Felder leeren (kein Stale-State)
            if (not bool(cmr_done)) and (edv is None and esv is None):
                return gr.update(value=None), gr.update(value=None)

            bsa = calc_bsa(_safe_num(height_cm), _safe_num(weight_kg))
            if bsa is None or bsa <= 0 or bsa < 0.8 or bsa > 3.0:
                # Ohne valide BSA: Indizes nicht anzeigen (keine stillen Altwerte)
                return gr.update(value=None), gr.update(value=None)

            out_edvi = (edv / bsa) if edv is not None else None
            out_esvi = (esv / bsa) if esv is not None else None

            return (
                gr.update(value=(None if out_edvi is None else round(float(out_edvi), 1))),
                gr.update(value=(None if out_esvi is None else round(float(out_esvi), 1))),
            )

        try:
            # Trigger on EDV/ESV and anthropometrics (BSA).
            field_components["rvedv"].change(
                _cmr_auto_index,
                inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                queue=False,
            )
            field_components["rvesv"].change(
                _cmr_auto_index,
                inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                queue=False,
            )
            field_components["height_cm"].change(
                _cmr_auto_index,
                inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                queue=False,
            )
            field_components["weight_kg"].change(
                _cmr_auto_index,
                inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                queue=False,
            )
        except _UI_RECOVERABLE_ERRORS as exc:
            # UI must stay alive even if some Gradio builds reject queue=...
            log_exception("RHK_UI_BIND_CMR_INDEX_QUEUE", "CMR auto-index binding with queue flags failed; retrying legacy binding.", exc)
            try:
                field_components["rvedv"].change(
                    _cmr_auto_index,
                    inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                    outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                )
                field_components["rvesv"].change(
                    _cmr_auto_index,
                    inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                    outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                )
                field_components["height_cm"].change(
                    _cmr_auto_index,
                    inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                    outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                )
                field_components["weight_kg"].change(
                    _cmr_auto_index,
                    inputs=[field_components["cmr_done"], field_components["rvedv"], field_components["rvesv"], field_components["height_cm"], field_components["weight_kg"]],
                    outputs=[field_components["rvedvi"], field_components["rvesvi"]],
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_BIND_CMR_INDEX_LEGACY", "CMR auto-index legacy binding also failed.", exc)

        # Lungenfunktion
        _sec_lufu_comps = [
            field_components["lufu_done"], field_components["fev1_l"], field_components["fvc_l"],
            field_components["dlco_sb"], field_components["dlco_va"], field_components["residual_volume_l"],
            field_components["lufu_summary"],
        ]

        def _calc_lufu(*vals):
            lufu_done, fev1, fvc, dlco_sb, dlco_va, rv, summary = vals
            if not bool(lufu_done):
                return 0, 0
            core = [fev1, fvc]
            optional = [dlco_sb, dlco_va, rv, summary]
            total = len(core) + len(optional)
            filled = sum(1 for v in core + optional if _is_filled(v))
            return filled, total

        _bind_section_progress(hdr_lufu, "Lungenfunktion & CPET", _sec_lufu_comps, _calc_lufu)

        # CPET
        _sec_cpet_comps = [
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"],
            field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"],
        ]

        def _calc_cpet(*vals):
            cpet_done, peak_vo2, peak_vo2_pct, vevco2, petco2, spo2, rer = vals
            if not bool(cpet_done):
                return 0, 0
            core = [peak_vo2, peak_vo2_pct, vevco2]
            optional = [petco2, spo2, rer]
            total = len(core) + len(optional)
            filled = sum(1 for v in core + optional if _is_filled(v))
            return filled, total

        _bind_section_progress(hdr_cpet, "Spiroergometrie / CPET", _sec_cpet_comps, _calc_cpet)

        # --------------------------------------------------------------
        # RHK – Section Cards
        # --------------------------------------------------------------

        # Ruhehämodynamik (core documentation)
        _sec_rhk_rest_comps = [
            field_components["spap_rest"], field_components["dpap_rest"], field_components["pawp_rest"],
            field_components["rap_rest"], field_components["co_rest"],
            field_components["mpap_rest"], field_components["ci_rest"], field_components["pvr_rest"],
        ]

        def _calc_rhk_rest(*vals):
            spap, dpap, pawp, rap, co, mpap, ci, pvr = vals
            core = [spap, dpap, pawp, rap, co]
            total = len(core)
            filled = sum(1 for v in core if _is_filled(v))
            # optional fields can only improve perception, never penalize
            if any(_is_filled(v) for v in [mpap, ci, pvr]) and filled < total:
                filled += 1
            return filled, total

        if hdr_rhk_rest is not None:
            _bind_section_progress(hdr_rhk_rest, "Ruhehämodynamik", _sec_rhk_rest_comps, _calc_rhk_rest)

        # Belastungshämodynamik (optional)
        _sec_rhk_ex_comps = [
            field_components["exercise_done"], field_components["exercise_protocol"], field_components["exercise_peak_watts"],
            field_components["spap_peak"], field_components["dpap_peak"], field_components["pawp_peak"], field_components["co_peak"],
            field_components["mpap_peak"], field_components["ci_peak"],
        ]

        def _calc_rhk_ex(*vals):
            ex_done, proto, watts, spap, dpap, pawp, co, mpap, ci = vals
            if not bool(ex_done):
                return 0, 0
            core = [proto, watts, spap, dpap, pawp, co]
            total = len(core)
            filled = sum(1 for v in core if _is_filled(v))
            # optional
            if any(_is_filled(v) for v in [mpap, ci]) and filled < total:
                filled += 1
            return filled, total

        if hdr_rhk_exercise is not None:
            _bind_section_progress(hdr_rhk_exercise, "Belastungshämodynamik", _sec_rhk_ex_comps, _calc_rhk_ex)

        # Zusatzmodule (optional, counts only when started)
        _sec_rhk_addons_comps = [
            field_components["volume_challenge_done"], field_components["pawp_pre"], field_components["pawp_post"],
            field_components["vaso_test_done"], field_components["vaso_agent"], field_components["vaso_mpap_pre"], field_components["vaso_mpap_post"],
            field_components["sat_pa"], field_components["sat_ao"],
        ]

        def _calc_rhk_addons(*vals):
            (vc_done, pawp_pre, pawp_post, vaso_done, vaso_agent, vaso_pre, vaso_post, sat_pa, sat_ao) = vals
            total = 0
            filled = 0

            if bool(vc_done):
                total += 2
                filled += (1 if _is_filled(pawp_pre) else 0) + (1 if _is_filled(pawp_post) else 0)

            if bool(vaso_done):
                total += 2
                filled += (1 if _is_filled(vaso_pre) else 0) + (1 if _is_filled(vaso_post) else 0)
                # agent optional: do not penalize
                if _is_filled(vaso_agent) and filled < total:
                    filled += 1

            # if sats are entered, count minimal documentation
            if any(_is_filled(v) for v in [sat_pa, sat_ao]):
                total += 1
                filled += 1

            if total == 0:
                return 0, 0
            return filled, total

        if hdr_rhk_addons is not None:
            _bind_section_progress(hdr_rhk_addons, "Zusatzmodule", _sec_rhk_addons_comps, _calc_rhk_addons)

        # Verlauf / Vergleich (optional)
        _sec_rhk_prev_comps = [
            field_components["prev_rhk_date"], field_components["prev_mpap"], field_components["prev_pawp"],
            field_components["prev_ci"], field_components["prev_pvr"],
        ]

        def _calc_rhk_prev(*vals):
            prev_date, prev_mpap, prev_pawp, prev_ci, prev_pvr = vals
            if not any(_is_filled(v) for v in vals):
                return 0, 0
            total = len(vals)
            filled = sum(1 for v in vals if _is_filled(v))
            return filled, total

        if hdr_rhk_prev is not None:
            _bind_section_progress(hdr_rhk_prev, "Verlauf / Vergleich", _sec_rhk_prev_comps, _calc_rhk_prev)

        # --------------------------------------------------------------
        # Weitere Befunde – Section Cards
        # --------------------------------------------------------------

        # LTOT
        _sec_other_bloodgas = [field_components["ltot"], field_components["ltot_flow_l_min"]]

        def _calc_other_bloodgas(*vals):
            ltot, flow = vals
            if not bool(ltot):
                return 0, 0
            total = 1
            filled = 1 if _is_filled(flow) else 0
            return filled, total

        _bind_section_progress(hdr_other_bloodgas, "Blutgase / LTOT", _sec_other_bloodgas, _calc_other_bloodgas)

        # Infektiologie/Immunologie
        _sec_other_infect = [
            field_components["virology_pos"], field_components["virology_items"], field_components["virology_desc"],
            field_components["immunology_pos"], field_components["immunology_items"], field_components["immunology_desc"],
        ]

        def _calc_other_infect(*vals):
            v_pos, v_items, v_desc, i_pos, i_items, i_desc = vals
            total = 0
            filled = 0
            if bool(v_pos):
                total += 1
                if (isinstance(v_items, list) and len(v_items) > 0) or _is_filled(v_desc):
                    filled += 1
            if bool(i_pos):
                total += 1
                if (isinstance(i_items, list) and len(i_items) > 0) or _is_filled(i_desc):
                    filled += 1
            if total == 0:
                return 0, 0
            return filled, total

        _bind_section_progress(hdr_other_infect, "Infektiologie / Immunologie", _sec_other_infect, _calc_other_infect)

        # Genetik
        _sec_other_gen = [field_components["mutation_pos"], field_components["mutation_items"], field_components["mutation_desc"]]

        def _calc_other_gen(*vals):
            m_pos, m_items, m_desc = vals
            if not bool(m_pos):
                return 0, 0
            total = 1
            filled = 1 if ((isinstance(m_items, list) and len(m_items) > 0) or _is_filled(m_desc)) else 0
            return filled, total

        _bind_section_progress(hdr_other_gen, "Genetik", _sec_other_gen, _calc_other_gen)

        # Abdomen
        _sec_other_abd = [field_components["abd_sono_done"], field_components["abd_sono_desc"]]

        def _calc_other_abd(*vals):
            done, desc = vals
            if not bool(done):
                return 0, 0
            total = 1
            filled = 1 if _is_filled(desc) else 0
            return filled, total

        _bind_section_progress(hdr_other_abd, "Abdomen / Leber", _sec_other_abd, _calc_other_abd)


        # --- Helpers to map UI dict to component list ---
        input_components = [field_components[k] for k in field_components.keys()]
        input_keys = list(field_components.keys())

        def ui_get_raw(*vals):
            return {k: v for k, v in zip(input_keys, vals, strict=False)}

        # Default UI snapshot (used to hard-reset patient-specific state before DOCX import).
        DEFAULT_UI: Dict[str, Any] = {}
        for k, comp in zip(input_keys, input_components, strict=False):
            try:
                DEFAULT_UI[k] = getattr(comp, 'value', None)
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_DEFAULT_UI_VALUE", "Failed to read component default value; using None.", exc, key=k)
                DEFAULT_UI[k] = None
        # Dropdowns that must never be invalid (avoid 'value not in choices' crashes)
        if 'anticoag_indication' in DEFAULT_UI:
            DEFAULT_UI['anticoag_indication'] = 'keine Angabe'


        def apply_ui_to_components(ui_dict: Dict[str, Any]) -> List[Any]:
            # Backward/forward compatibility aliases
            if isinstance(ui_dict, dict):
                if "egfr_ml_min_1_73" not in ui_dict and "egfr" in ui_dict:
                    ui_dict["egfr_ml_min_1_73"] = ui_dict.get("egfr")
                # CPET legacy/new key aliases (Persistenz ohne Datenverlust)
                if "cpet_setup" not in ui_dict and "cpet_site" in ui_dict:
                    ui_dict["cpet_setup"] = ui_dict.get("cpet_site")
                if "cpet_site" not in ui_dict and "cpet_setup" in ui_dict:
                    ui_dict["cpet_site"] = ui_dict.get("cpet_setup")

                if "cpet_borg_dyspnoe" not in ui_dict and "cpet_borg_dyspnea" in ui_dict:
                    ui_dict["cpet_borg_dyspnoe"] = ui_dict.get("cpet_borg_dyspnea")
                if "cpet_borg_dyspnea" not in ui_dict and "cpet_borg_dyspnoe" in ui_dict:
                    ui_dict["cpet_borg_dyspnea"] = ui_dict.get("cpet_borg_dyspnoe")

                if "cpet_borg_legs" not in ui_dict and "cpet_borg_leg" in ui_dict:
                    ui_dict["cpet_borg_legs"] = ui_dict.get("cpet_borg_leg")
                if "cpet_borg_leg" not in ui_dict and "cpet_borg_legs" in ui_dict:
                    ui_dict["cpet_borg_leg"] = ui_dict.get("cpet_borg_legs")

            def _choice_values(comp) -> List[Any]:
                """Return the *values* accepted by a choice component (supports (label,value) tuples)."""
                try:
                    ch = list(getattr(comp, "choices", []) or [])
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_CHOICE_VALUES", "Failed to read component choices.", exc)
                    return []
                vals: List[Any] = []
                for c in ch:
                    if isinstance(c, (tuple, list)) and len(c) >= 1:
                        vals.append(c[1] if len(c) >= 2 else c[0])
                    else:
                        vals.append(c)
                return vals

            def _strip_level_prefix(s: str) -> str:
                # e.g. "[I] P01 – ..." -> "P01 – ..."
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", str(s or "")).strip()

            def _norm_choice_text(x: Any) -> str:
                """Normalize labels/choices for robust equality across browsers/encodings.

                - strips level prefixes ([I]/[II]/[III])
                - normalizes whitespace (incl. NBSP)
                - normalizes dash variants to ' – '
                - lowercases
                """
                s = "" if x is None else str(x)
                s = _strip_level_prefix(s)
                s = s.replace("\u00a0", " ")
                # Normalize dash variants and surrounding whitespace
                s = re.sub(r"\s*[-–—]\s*", " – ", s)
                s = re.sub(r"\s+", " ", s).strip()
                return s.lower()

            def _try_map_to_choice(v: Any, choices: List[Any]) -> Any:
                """Map legacy/variant values to one of current choices when possible."""
                if not choices:
                    return None

                # Fast path: exact match
                try:
                    if v in choices:
                        return v
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_CHOICE_MEMBERSHIP", "Choice membership check failed; trying normalized mapping.", exc)

                vs = "" if v is None else str(v).strip()
                if not vs:
                    return None

                # Build normalized lookup -> original choice
                norm_map: Dict[str, Any] = {}
                for ch in choices:
                    norm_map[_norm_choice_text(ch)] = ch

                v_norm = _norm_choice_text(vs)
                if v_norm in norm_map:
                    return norm_map[v_norm]

                # If an ID like "P01" is present, map to the choice that starts with that ID
                m = re.search(r"\b(P\d{2})\b", _strip_level_prefix(vs), flags=re.IGNORECASE)
                pid = m.group(1).upper() if m else None
                if pid:
                    for ch in choices:
                        ch_clean = _strip_level_prefix(str(ch))
                        if ch_clean.startswith(pid):
                            return ch
                    # As a fallback, map by normalized prefix match
                    pid_norm = _norm_choice_text(pid)
                    for ch in choices:
                        if _norm_choice_text(str(ch)).startswith(pid_norm):
                            return ch

                return None

            def _coerce_for_component(k: str, v: Any) -> Any:
                comp = field_components.get(k)
                cname = (comp.__class__.__name__ if comp else "").lower()

                # Defaults for cleared/missing values:
                # IMPORTANT: numbers must stay None (not 0), otherwise we create physiologically impossible zeros
                # and override auto-calculations (e.g., mPAP).
                if v is None:
                    # IMPORTANT: for multi-select dropdowns, Gradio may auto-select the first choice
                    # when receiving None. Always force an explicit empty list.
                    try:
                        if hasattr(comp, "multiselect") and bool(getattr(comp, "multiselect", False)):
                            return []
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_MULTISELECT_FLAG", "Failed to inspect multiselect flag; continuing with generic defaults.", exc)
                    if "checkboxgroup" in cname:
                        return []
                    if "checkbox" in cname and "checkboxgroup" not in cname:
                        return False
                    if "number" in cname:
                        return None
                    if "slider" in cname:
                        return 0
                    if hasattr(comp, "choices"):
                        choices = _choice_values(comp)
                        if "keine Angabe" in choices:
                            return "keine Angabe"
                        return choices[0] if choices else ""
                    return ""

                # Coerce numbers from legacy string values
                if ("number" in cname or "slider" in cname) and isinstance(v, str):
                    s = v.strip()
                    if s == "":
                        return None if "number" in cname else 0
                    try:
                        return float(s.replace(",", "."))
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_NUMBER_COERCE", "Numeric field coercion failed; using empty default.", exc, key=k, raw_value=v)
                        return None if "number" in cname else 0

                # Coerce checkbox groups to list
                if "checkboxgroup" in cname:
                    if isinstance(v, (set, tuple)):
                        v = list(v)
                    elif not isinstance(v, list):
                        v = [v] if v not in ("", None) else []
                    # If choices exist, filter/migrate values to current choices
                    if hasattr(comp, "choices"):
                        choices = _choice_values(comp)
                        out_multi: List[Any] = []
                        for it in v:
                            mapped = _try_map_to_choice(it, choices)
                            if mapped is not None:
                                out_multi.append(mapped)
                        return out_multi
                    return v

                # Coerce multi-select dropdowns to list (avoid phantom defaults)
                if hasattr(comp, "multiselect") and bool(getattr(comp, "multiselect", False)):
                    if isinstance(v, (set, tuple)):
                        v = list(v)
                    elif not isinstance(v, list):
                        v = [v] if v not in ("", None) else []
                    if hasattr(comp, "choices"):
                        choices = _choice_values(comp)
                        out: List[Any] = []
                        for it in v:
                            mapped = _try_map_to_choice(it, choices)
                            if mapped is not None:
                                out.append(mapped)
                        return out
                    return v

                # Guard any single-choice component with choices
                if hasattr(comp, "choices"):
                    choices = _choice_values(comp)
                    if choices and v not in choices:
                        mapped = _try_map_to_choice(v, choices)
                        if mapped is not None:
                            return mapped
                        # safe fallback
                        if "keine Angabe" in choices:
                            return "keine Angabe"
                        return choices[0] if choices else ""

                return v

            out: List[Any] = []
            dzl_flag_val = bool(ui_dict.get("dzl_flag"))
            for k in field_components.keys():
                coerced = _coerce_for_component(k, ui_dict.get(k))
                # DZL decision dropdown visibility must follow its checkbox also for programmatic loads
                if k == "dzl_decision":
                    out.append(gr.update(value=coerced, visible=dzl_flag_val))
                elif k == "dzl_initial_test":
                    # DZL Ersttestung visibility follows DZL checkbox on programmatic loads.
                    out.append(gr.update(value=bool(coerced), visible=dzl_flag_val))
                else:
                    out.append(coerced)
            return out
        _generate_cache: Dict[str, Any] = {"sig": None, "payload": None}

        def _generate(case_state_in, flags_state, pmods_state, docx_cur_state, docx_prev_state, echo_cur_state, echo_prev_state, case_filename_state, ui_lang_val, *vals):
            perf_on = os.getenv("RHK_PERF", "0").strip() == "1"
            raw_ui = ui_get_raw(*vals)
            _lang = str(ui_lang_val or "de").strip().lower()
            if _lang not in ("de", "en", "zh"):
                _lang = "de"
            artifacts = generate_runtime_artifacts(
                case_state_in=case_state_in,
                flags_state=flags_state,
                pmods_state=pmods_state,
                docx_cur_state=docx_cur_state,
                docx_prev_state=docx_prev_state,
                raw_ui=raw_ui,
                rules=rules,
                blocks=blocks,
                rulebook_meta=rulebook_meta,
                generate_cache=_generate_cache,
                perf_on=perf_on,
                lang=_lang,
            )

            modules_lvl1_update = gr.update(
                choices=artifacts.pmodules.choices_lvl1,
                value=artifacts.pmodules.selected_lvl1_ids,
            )
            modules_lvl2_update = gr.update(
                choices=artifacts.pmodules.choices_lvl2,
                value=artifacts.pmodules.selected_lvl2_ids,
            )
            modules_lvl3_update = gr.update(
                choices=artifacts.pmodules.choices_lvl3,
                value=artifacts.pmodules.selected_lvl3_ids,
            )
            pmods_disabled_dd_update = gr.update(
                choices=artifacts.pmodules.disabled_dd_choices,
                value=None,
            )

            return (
                artifacts.auto_mpap,
                artifacts.auto_ci,
                artifacts.auto_pvr,
                artifacts.auto_pvri,
                artifacts.auto_tpg,
                artifacts.auto_dpg,
                artifacts.dashboard_html,
                artifacts.doctor_report,
                artifacts.patient_report,
                artifacts.echo_doctor_report,
                artifacts.echo_patient_report,
                artifacts.internal_report,
                artifacts.summary_json,
                artifacts.debug_json,
                artifacts.copy_doc_plain,
                artifacts.copy_pat_plain,
                artifacts.copy_rhk_plain,
                artifacts.copy_doc_html,
                artifacts.copy_pat_html,
                artifacts.copy_rhk_html,
                "",
                artifacts.case,
                artifacts.flags,
                artifacts.pmodules.state,
                docx_cur_state,
                docx_prev_state,
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                artifacts.pmodules.disabled_html,
                pmods_disabled_dd_update,
                artifacts.sticky_summary_html,
                artifacts.compare_overview_html,
                artifacts.rhk_plots_html,
                artifacts.import_status_html,
                artifacts.modules_cards_html,
            )

        def _apply_pmods_values(sel_state: Optional[Dict[str, Any]]):
            """2nd stage: set CheckboxGroup values AFTER choices were updated (robust mapping)."""
            def _clean(s: Any) -> str:
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", str(s) if s is not None else "").strip()
            def _map_list(vals: Any, comp) -> List[str]:
                if not vals:
                    return []
                if isinstance(vals, (set, tuple)):
                    vals = list(vals)
                elif not isinstance(vals, list):
                    vals = [vals]
                choices = list(getattr(comp, "choices", []) or [])
                choice_set = set(str(c) for c in choices)
                out: List[str] = []
                for v in vals:
                    vv = _clean(v)
                    if not vv:
                        continue
                    if vv in choice_set:
                        out.append(vv)
                        continue
                    # map by ID (Pxx) to the matching choice label
                    m = re.match(r"^(P\d{2})\b", vv)
                    if m:
                        pid = m.group(1)
                        hit = None
                        for c in choices:
                            cs = _clean(c)
                            if cs.startswith(pid + " –") or cs.startswith(pid + " -"):
                                hit = cs
                                break
                        if hit and hit in choice_set:
                            out.append(hit)
                # de-dup while preserving order
                return list(dict.fromkeys(out))
            try:
                return (
                    gr.update(value=_map_list((sel_state or {}).get("lvl1"), modules_lvl1_comp)),
                    gr.update(value=_map_list((sel_state or {}).get("lvl2"), modules_lvl2_comp)),
                    gr.update(value=_map_list((sel_state or {}).get("lvl3"), modules_lvl3_comp)),
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_PMOD_STAGE2_APPLY", "Second-stage P-module value apply failed; resetting selections.", exc)
                return (gr.update(value=[]), gr.update(value=[]), gr.update(value=[]))

        def _generate_with_pmods_apply(*args):
            """Run _generate without mutating P-Module UI state.

            Single Source of Truth is case_state["ui"]["modules"].
            The dropdown updates are already part of _generate() outputs.
            """
            return _generate(*args)

        def _build_doctor_docx_file(case_state: Any, lang: str = "de") -> str:
            """Build the doctor DOCX in the export directory and return its path.

            This helper keeps a stable, human-friendly filename for the DOCX itself.
            The UI exposes the result via a `gr.File` download link (robust across Gradio 5/6).
            """
            try:
                return build_doctor_docx_file(case_state, blocks=blocks)
            except ValueError as exc:
                raise gr.Error(tr_ui(str(exc), lang)) from exc

        def _export_doctor_docx(case_state: Any, lang: str = "de"):
            """Create a formatted DOCX for the doctor report.

            IMPORTANT
            - The DOCX MUST match exactly the report shown in-app and copied to clipboard.
            - A single master markdown string is used for UI, clipboard and DOCX.
            """
            try:
                export_bundle = export_doctor_docx(case_state, blocks=blocks)
            except ValueError as exc:
                raise gr.Error(tr_ui(str(exc), lang)) from exc
            return (
                gr.update(value=str(export_bundle.file_path), visible=True),
                export_bundle.message,
            )

        def _export_doctor_docx_local(case_state: Any, out_dir: str, lang: str = "de"):
            """Create the same DOCX as download, but save it to a local path.

            Motivation
            - In some clinic environments, browser downloads are blocked or Word opens downloaded files in Protected View (Mark-of-the-Web).
            - Saving to a local folder (e.g., Documents) avoids the download zone marker.
            """
            try:
                out_path = save_doctor_docx_local(case_state, blocks=blocks, out_dir=out_dir)
            except ValueError as exc:
                raise gr.Error(tr_ui(str(exc), lang)) from exc
            except _UI_RECOVERABLE_ERRORS as e:
                log_exception("RHK_UI_DOCX_LOCAL_DIR", "Creating local DOCX export directory failed.", e, out_dir=out_dir)
                raise gr.Error(tr_ui("Ordner kann nicht erstellt/genutzt werden:", lang) + f" {out_dir} ({e})") from e
            return tr_ui("Gespeichert:", lang) + f" {out_path}"

        generate_outputs = [
            auto_mpap, auto_ci, auto_pvr, auto_pvri, auto_tpg, auto_dpg,
            dashboard,
            out_doc, out_pat, out_echo_doc, out_echo_pat, out_int,
            out_summary_json,
            out_json,
            copy_doc_plain, copy_pat_plain, copy_rhk_plain,
            copy_doc_html, copy_pat_html, copy_rhk_html,
            copy_feedback,
            state_case,
            state_flags,
            state_pmods_selected,
            state_docx_cur,
            state_docx_prev,
            modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp,
            modules_disabled_html,
            pmods_disabled_dd,
            sticky_summary_html,
            compare_overview_html,
            rhk_plots_html,
            import_status_html,
            modules_cards_html,
        ]

        btn_generate_top.click(_generate_with_pmods_apply, inputs=[state_case, state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename, ui_lang] + input_components, outputs=generate_outputs)
        btn_generate_bottom.click(_generate_with_pmods_apply, inputs=[state_case, state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename, ui_lang] + input_components, outputs=generate_outputs)

        # DOCX export for the doctor report (Muster-Layout)
        # Use DownloadButton to keep the UI compact.
        
        # Pre-RHK A4 landscape PDF (print immediately before catheterization)

        def _export_prerhk_pdf(flags_state, pmods_state, docx_cur_state, docx_prev_state, echo_cur_state, echo_prev_state, case_filename_state, *vals):
            try:
                export_bundle = export_prerhk_pdf(
                    flags_state=flags_state,
                    pmods_state=pmods_state,
                    docx_cur_state=docx_cur_state,
                    docx_prev_state=docx_prev_state,
                    echo_cur_state=echo_cur_state,
                    echo_prev_state=echo_prev_state,
                    case_filename=case_filename_state,
                    raw_ui=ui_get_raw(*vals),
                    rules=rules,
                )
                return (
                    gr.update(value=str(export_bundle.file_path), visible=True),
                    export_bundle.message,
                )
            except (ValueError, _UI_RECOVERABLE_ERRORS) as e:
                log_exception("RHK_UI_PRERHK_EXPORT", "Pre-RHK PDF generation failed.", e)
                msg = f"Fehler beim Erstellen der Pre-RHK PDF: {type(e).__name__}: {e}"
                # Keep UI responsive; show message and do not serve a file.
                return gr.update(value=None, visible=False), f"⚠️ {msg}"

        # --- Export buttons -> File links (download) ---
        btn_make_docx.click(
            _export_doctor_docx,
            inputs=[state_case, ui_lang],
            outputs=[docx_file, copy_feedback],
            queue=False,
            trigger_mode="always_last",
        )

        # DOCX (ZIP) - useful if direct .docx downloads are blocked by network policy
        def _export_doctor_docx_zip(case_state: Any, lang: str = "de"):
            try:
                export_bundle = export_doctor_docx_zip(case_state, blocks=blocks)
            except ValueError as exc:
                raise gr.Error(tr_ui(str(exc), lang)) from exc
            return (
                gr.update(value=str(export_bundle.file_path), visible=True),
                export_bundle.message,
            )

        btn_make_docx_zip.click(
            _export_doctor_docx_zip,
            inputs=[state_case, ui_lang],
            outputs=[docx_zip_file, copy_feedback],
            queue=False,
            trigger_mode="always_last",
        )

        # Pre-RHK PDF must always reflect the *latest* UI values.
        # Robust across Gradio 5/6: generate on click, expose via File link.
        btn_make_prerhk_pdf.click(
            _export_prerhk_pdf,
            inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components,
            outputs=[prerhk_pdf_file, copy_feedback],
            queue=False,
            trigger_mode="always_last",
        )

        # --- On-demand heavy tabs (performance) ---
        def _update_internal_report(case_state: Any, lang: str = "de"):
            if not isinstance(case_state, dict):
                raise gr.Error(tr_ui("Bitte zuerst den Befund erstellen, dann den Intern-Report aktualisieren.", lang))
            return build_internal_report(case_state), "✅ Intern-Report aktualisiert."

        btn_update_internal.click(
            _update_internal_report,
            inputs=[state_case, ui_lang],
            outputs=[out_int, copy_feedback],
            queue=False,
            trigger_mode="always_last",
        )

        def _update_debug_json(case_state: Any, docx_cur_state: Any, docx_prev_state: Any, echo_cur_state: Any, echo_prev_state: Any, lang: str = "de"):
            if not isinstance(case_state, dict):
                raise gr.Error(tr_ui("Bitte zuerst den Befund erstellen, dann Debug JSON aktualisieren.", lang))

            # Keep debug output deterministic; also include import payloads for QA, without mutating state_case.
            debug_case = dict(case_state)
            imports: Dict[str, Any] = {}
            if isinstance(docx_cur_state, dict) and docx_cur_state:
                imports["docx_current"] = docx_cur_state
            if isinstance(docx_prev_state, dict) and docx_prev_state:
                imports["docx_prev"] = docx_prev_state
            if isinstance(echo_cur_state, dict) and echo_cur_state:
                imports["echo_cur"] = echo_cur_state
            if isinstance(echo_prev_state, dict) and echo_prev_state:
                imports["echo_prev"] = echo_prev_state
            if imports:
                debug_case["imports"] = imports

            return json.dumps(debug_case, ensure_ascii=False, indent=2), "✅ Debug JSON aktualisiert."

        btn_update_debug_json.click(
            _update_debug_json,
            inputs=[state_case, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, ui_lang],
            outputs=[out_json, copy_feedback],
            queue=False,
            trigger_mode="always_last",
        )


        # DOCX save to local path (clinic workaround)
        btn_save_docx_local.click(
            _export_doctor_docx_local,
            inputs=[state_case, docx_save_dir, ui_lang],
            outputs=[docx_save_feedback],
        )
        # --- Live status update (debounced client ping) ---
        # Instead of attaching a .change handler to dozens of inputs (slow + triggers during bulk programmatic updates),
        # we use ONE hidden textbox that the browser updates (debounced) whenever the user edits any input.
        # Procedere/Module are handled by _update_procedere_only and therefore excluded from the client ping.
        def _on_dirty_ping(flags_state, case_state, _ping_val: str):
            flags = dict(flags_state or {})

            # Performance: this callback can fire frequently while typing (client-side debounce).
            # Keep it O(1) and avoid rebuilding large HTML unless the visible state actually changes.
            was_dirty = bool(flags.get("dirty"))
            was_stale = bool(flags.get("report_stale"))
            has_report = bool(flags.get("has_report"))

            flags["dirty"] = True
            if has_report:
                flags["report_stale"] = True

            # Keep warnings from last generation for visibility; do not recompute.
            try:
                if "warnings" not in flags or flags.get("warnings") is None:
                    flags["warnings"] = (case_state or {}).get("warnings") or []
                else:
                    flags["warnings"] = list(flags.get("warnings") or [])
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_DIRTY_WARNINGS", "Failed to preserve warnings in dirty-flag ping callback.", exc)
                flags["warnings"] = []

            # Only re-render sticky summary when transitioning to a new visible state.
            if was_dirty and ((not has_report) or was_stale):
                return flags, gr.update()

            case_for_ui = case_state if isinstance(case_state, dict) else None
            return flags, build_sticky_summary_html(case_for_ui, flags)

        try:
            dirty_ping.change(
                _on_dirty_ping,
                inputs=[state_flags, state_case, dirty_ping],
                outputs=[state_flags, sticky_summary_html],
                trigger_mode="always_last",
                queue=False,
            )
        except TypeError:
            dirty_ping.change(
                _on_dirty_ping,
                inputs=[state_flags, state_case, dirty_ping],
                outputs=[state_flags, sticky_summary_html],
            )


        # --- Live-Update: Procedere/Module sollen deterministisch im Bericht landen ---
        # Häufiger UX-Fehler: User ändert Module/Freitext nach dem Generieren und erwartet, dass der Bericht folgt.
        # Wir aktualisieren daher den Bericht direkt aus dem bestehenden Case-State, ohne alle Ableitungen neu zu rechnen.
        def _update_procedere_only(flags_state, case_state, m1, m2, m3, free_text, ui_lang_val="de"):
            if not case_state:
                # Noch kein Fall generiert – nichts zu aktualisieren.
                return (
                    gr.update(),  # out_doc
                    gr.update(),  # out_pat
                    gr.update(),  # out_echo_doc
                    gr.update(),  # out_echo_pat
                    gr.update(),  # out_int
                    gr.update(),  # out_summary_json
                    gr.update(),  # out_json
                    gr.update(),  # copy_doc_plain
                    gr.update(),  # copy_pat_plain
                    gr.update(),  # copy_rhk_plain
                    gr.update(),  # copy_doc_html
                    gr.update(),  # copy_pat_html
                    gr.update(),  # copy_rhk_html
                    gr.update(),  # copy_feedback
                    None,         # state_case
                    dict(flags_state or {}),  # state_flags
                    build_sticky_summary_html(None, dict(flags_state or {})),
                    gr.update(value=[]),  # modules_lvl1
                    gr.update(value=[]),  # modules_lvl2
                    gr.update(value=[]),  # modules_lvl3
                    gr.update(),  # modules_cards_html
                )
            flags = dict(flags_state or {})
            try:
                ui = dict(case_state.get("ui") or {})
                # --- P-Module ordering: newest selection goes to top within its level group ---
                try:
                    policy = (case_state.get("derived") or {}).get("p_module_policy") or {}
                    levels_map = policy.get("levels") or {}
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_PROCEDERE_LEVELS", "Failed to read p-module policy levels; defaulting.", exc)
                    levels_map = {}

                prev_all = _normalize_module_ids(ui.get("modules") or [])
                prev_lvl1 = [x for x in prev_all if _pmod_level(levels_map, x) == 1]
                prev_lvl2 = [x for x in prev_all if _pmod_level(levels_map, x) == 2]
                prev_lvl3 = [x for x in prev_all if _pmod_level(levels_map, x) not in (1, 2)]

                def _reorder(prev_list, new_list):
                    new_list = _normalize_module_ids(new_list or [])
                    prev_set = set(prev_list or [])
                    new_set = set(new_list or [])
                    removed = [x for x in (prev_list or []) if x not in new_set]
                    added = [x for x in new_list if x not in prev_set]
                    kept = [x for x in (prev_list or []) if x in new_set]
                    # Remove removed, then prepend newly added (latest should be on top)
                    out = [x for x in kept if x not in removed]
                    for a in reversed(added):
                        if a not in out:
                            out.insert(0, a)
                    # Ensure nothing extra sneaks in
                    out = [x for x in out if x in new_set]
                    return out

                m1 = _reorder(prev_lvl1, m1)
                m2 = _reorder(prev_lvl2, m2)
                m3 = _reorder(prev_lvl3, m3)
                prev_free = str(ui.get("procedere_free") or "")
                new_free = str(free_text or "")

                # Performance guard:
                # Gradio can trigger this callback from programmatic sync updates where the
                # effective procedere payload did not change. Skip full report regeneration then.
                if (
                    m1 == prev_lvl1
                    and m2 == prev_lvl2
                    and m3 == prev_lvl3
                    and new_free == prev_free
                ):
                    return (
                        gr.update(),  # out_doc
                        gr.update(),  # out_pat
                        gr.update(),  # out_echo_doc
                        gr.update(),  # out_echo_pat
                        gr.update(),  # out_int
                        gr.update(),  # out_summary_json
                        gr.update(),  # out_json
                        gr.update(),  # copy_doc_plain
                        gr.update(),  # copy_pat_plain
                        gr.update(),  # copy_rhk_plain
                        gr.update(),  # copy_doc_html
                        gr.update(),  # copy_pat_html
                        gr.update(),  # copy_rhk_html
                        gr.update(),  # copy_feedback
                        case_state,   # state_case
                        flags,        # state_flags
                        gr.update(),  # sticky_summary_html
                        gr.update(),  # modules_lvl1
                        gr.update(),  # modules_lvl2
                        gr.update(),  # modules_lvl3
                        gr.update(),  # modules_cards_html
                    )
                ui["modules_lvl1"] = m1 or []
                ui["modules_lvl2"] = m2 or []
                ui["modules_lvl3"] = m3 or []
                ui["procedere_free"] = new_free
                ui["modules"] = _normalize_module_ids(
                    (ui.get("modules_lvl1") or []) + (ui.get("modules_lvl2") or []) + (ui.get("modules_lvl3") or [])
                )
                case_state["ui"] = ui

                # Master doctor report (single source of truth)
                doc_full = build_doctor_report(case_state, blocks)
                _plang = str(ui_lang_val or "de").strip().lower()
                if _plang not in ("de", "en", "zh"):
                    _plang = "de"
                pat = build_patient_report(case_state, lang=_plang)
                echo_doc = build_echo_doctor_report_extended(case_state)
                echo_pat = build_echo_patient_report(case_state)
                # Performance: avoid rebuilding the heavy intern report on every
                # procedere/module keystroke. Keep current intern-tab content.
                internal = gr.update()

                # Single source of truth for Arztbericht:
                # UI preview (out_doc), Clipboard and DOCX must match.
                doc_master_md = str(doc_full or "")

                # Structured summary + debug
                try:
                    summary_dict = build_summary_dict(case_state, rulebook_meta)
                    case_state["summary"] = summary_dict
                    summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_PROCEDERE_SUMMARY", "Procedere-only summary regeneration failed.", exc)
                    summary_json = "{}"
                # Debug JSON is intentionally on-demand (button) to keep live procedere updates fast.
                dbg_note = '{\n  "note": "Debug JSON bleibt beim Live-Update unverändert. Bitte \"Debug JSON aktualisieren\" klicken."\n}'
                # Copy/paste payloads
                # - plain text for systems that break on rich formatting
                # - HTML for Word (clipboard text/html)
                try:
                    doc_plain = _markdown_to_plain_cached(doc_master_md)
                    pat_plain = _markdown_to_plain_cached(str(pat or ''))
                    rhk_section = _extract_markdown_section_cached(doc_master_md, "Rechtsherzkatheter", "Beurteilung")
                    rhk_plain = _markdown_to_plain_cached(str(rhk_section or ''))

                    doc_html = _markdown_to_word_html_cached(doc_master_md)
                    pat_html = _markdown_to_word_html_cached(str(pat or ''))
                    rhk_html = _markdown_to_word_html_cached(str(rhk_section or ''))
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_PROCEDERE_CLIPBOARD", "Procedere-only clipboard payload generation failed.", exc)
                    doc_plain = ""
                    pat_plain = ""
                    rhk_plain = ""
                    doc_html = ""
                    pat_html = ""
                    rhk_html = ""

                cards_html = build_p_module_cards_html(blocks, case_state)

                # Status: report stays current (we just updated it), but changes are unsaved
                flags["dirty"] = True
                flags["has_report"] = True
                flags["report_stale"] = False
                try:
                    flags["warnings"] = case_state.get("warnings") or []
                except _UI_RECOVERABLE_ERRORS as exc:
                    log_exception("RHK_UI_PROCEDERE_FLAGS_WARNINGS", "Failed to update warnings in procedere-only flags.", exc)
                    flags["warnings"] = []

                sticky = build_sticky_summary_html(case_state, flags)
                return (
                    doc_full,
                    pat,
                    echo_doc,
                    echo_pat,
                    internal,
                    summary_json,
                    dbg_note,
                    doc_plain,
                    pat_plain,
                    rhk_plain,
                    doc_html,
                    pat_html,
                    rhk_html,
                    "",  # copy feedback reset
                    case_state,
                    flags,
                    sticky,
                    gr.update(value=ui.get("modules_lvl1") or []),
                    gr.update(value=ui.get("modules_lvl2") or []),
                    gr.update(value=ui.get("modules_lvl3") or []),
                    cards_html,
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                # Fail-safe: do not break UI on minor issues
                log_exception("RHK_UI_PROCEDERE_UPDATE", "Procedere-only live update failed; returning no-op updates.", exc)
                sticky = build_sticky_summary_html(case_state, flags)
                return (
                    gr.update(),  # out_doc
                    gr.update(),  # out_pat
                    gr.update(),  # out_echo_doc
                    gr.update(),  # out_echo_pat
                    gr.update(),  # out_int
                    gr.update(),  # out_summary_json
                    gr.update(),  # out_json
                    gr.update(),  # copy_doc_plain
                    gr.update(),  # copy_pat_plain
                    gr.update(),  # copy_rhk_plain
                    gr.update(),  # copy_doc_html
                    gr.update(),  # copy_pat_html
                    gr.update(),  # copy_rhk_html
                    gr.update(),  # copy_feedback
                    case_state,   # state_case
                    flags,        # state_flags
                    sticky,       # sticky_summary_html
                    gr.update(),  # modules_lvl1
                    gr.update(),  # modules_lvl2
                    gr.update(),  # modules_lvl3
                    gr.update(),  # modules_cards_html
                )

        _procedere_inputs = [state_flags, state_case, modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp, field_components["procedere_free"], ui_lang]
        _procedere_outputs = [
            out_doc, out_pat, out_echo_doc, out_echo_pat, out_int,
            out_summary_json,
            out_json,
            copy_doc_plain, copy_pat_plain, copy_rhk_plain,
            copy_doc_html, copy_pat_html, copy_rhk_html,
            copy_feedback,
            state_case,
            state_flags,
            sticky_summary_html,
            modules_lvl1_comp,
            modules_lvl2_comp,
            modules_lvl3_comp,
            modules_cards_html,
        ]

        _bind_change(modules_lvl1_comp, _update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        _bind_change(modules_lvl2_comp, _update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        _bind_change(modules_lvl3_comp, _update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        _bind_change(field_components["procedere_free"], _update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        # Optional: bei Enter/Submit ebenfalls
        try:
            field_components["procedere_free"].submit(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_BIND_PROCEDERE_SUBMIT", "Binding submit event for procedere free text failed.", exc)

        # --- P-Module: "wieder optional machen" (ohne Auto-Auswahl) ---
        def _pmods_make_optional(flags_state, case_state, disabled_mid):
            flags = dict(flags_state or {})
            if not isinstance(case_state, dict) or not disabled_mid:
                return (
                    case_state,
                    flags,
                    gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), gr.update(),
                    gr.update(),
                )
            ui = dict(case_state.get("ui") or {})
            # persist override
            cur = set(_normalize_module_ids(ui.get("pmods_force_optional") or []))
            cur.add(str(disabled_mid).strip())
            ui["pmods_force_optional"] = sorted(cur)
            case_state["ui"] = ui

            # rebuild effective policy views (no recomputation of derived here)
            der = case_state.get("derived") or {}
            policy = der.get("p_module_policy") or {}
            force_optional = pmods_get_force_optional(ui)
            eff_policy = pmods_apply_overrides(policy, force_optional)

            mod_choices = build_p_module_choices(blocks, eff_policy)
            disabled_html = build_disabled_p_modules_html(blocks, eff_policy)
            cards_html = build_p_module_cards_html(blocks, case_state)

            levels_map = (eff_policy.get("levels") or {}) if isinstance(eff_policy, dict) else {}
            disabled_map = (eff_policy.get("disabled") or {}) if isinstance(eff_policy, dict) else {}

            allowed_ids = [mid for (_lab, mid) in mod_choices]
            sel_vals = _normalize_module_ids(ui.get("modules") or [])
            locked_selected = [m for m in sel_vals if (m in disabled_map and m not in force_optional)]

            # labels
            def _clean_pmod_label(lab: Any) -> str:
                s = str(lab) if lab is not None else ""
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", s).strip()

            id_to_label = {mid: _clean_pmod_label(lab) for (lab, mid) in mod_choices}
            for mid in locked_selected:
                if mid not in id_to_label:
                    try:
                        title = blocks[mid].title if mid in blocks else ""
                    except _UI_RECOVERABLE_ERRORS as exc:
                        log_exception("RHK_UI_PMOD_OPTIONAL_LABEL", "Failed to resolve module title in optional-action flow.", exc, module_id=mid)
                        title = ""
                    id_to_label[mid] = f"{mid} – {title}".strip(" –")

            def _choices_level(pred):
                ch=[]
                for mid in allowed_ids:
                    if not pred(mid):
                        continue
                    ch.append((id_to_label.get(mid, mid), mid))
                for mid in locked_selected:
                    if not pred(mid):
                        continue
                    ch.append((id_to_label.get(mid, mid) + " (gesperrt)", mid))
                return ch

            lvl1_choices = _choices_level(lambda mid: _pmod_level(levels_map, mid)==1)
            lvl2_choices = _choices_level(lambda mid: _pmod_level(levels_map, mid)==2)
            lvl3_choices = _choices_level(lambda mid: _pmod_level(levels_map, mid) not in (1,2))

            sel_lvl1 = [m for m in sel_vals if _pmod_level(levels_map, m)==1]
            sel_lvl2 = [m for m in sel_vals if _pmod_level(levels_map, m)==2]
            sel_lvl3 = [m for m in sel_vals if _pmod_level(levels_map, m) not in (1,2)]

            dd_choices=[]
            for mid, reason in sorted(disabled_map.items(), key=lambda kv: kv[0]):
                if mid in force_optional:
                    continue
                title = blocks[mid].title if mid in blocks else ""
                lab = f"{mid} – {title}".strip(" –")
                if reason:
                    lab = f"{lab} | {reason}"
                dd_choices.append((lab, mid))
            disabled_dd_update = gr.update(choices=dd_choices, value=None)

            return (
                case_state,
                flags,
                gr.update(choices=lvl1_choices, value=sel_lvl1),
                gr.update(choices=lvl2_choices, value=sel_lvl2),
                gr.update(choices=lvl3_choices, value=sel_lvl3),
                disabled_html,
                disabled_dd_update,
                cards_html,
                build_sticky_summary_html(case_state, flags),
            )

        # Outputs: update only the P-Module-related UI + keep case/flags consistent
        pmods_make_optional_btn.click(
            _pmods_make_optional,
            inputs=[state_flags, state_case, pmods_disabled_dd],
            outputs=[state_case, state_flags, modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp, modules_disabled_html, pmods_disabled_dd, modules_cards_html, sticky_summary_html],
        )

        # --- Example loader ---

        def _load_example_ui(example_idx):
            # Beispielreihe: feste Suite. Bei jedem Klick wird ein zufälliges
            # Beispiel geladen (ausgenommen das zuletzt gezeigte, damit
            # konsekutive Klicks garantiert einen Wechsel zeigen).
            try:
                from rhk_reports import example_suite_length
                suite_len = max(1, int(example_suite_length()))
            except (ImportError, TypeError, ValueError):
                suite_len = 16
            # -1 (Sentinel, s. state init) = "noch kein Beispiel geladen".
            try:
                last_idx_raw = int(example_idx) if example_idx is not None else -1
            except (TypeError, ValueError):
                last_idx_raw = -1
            exclude = last_idx_raw % suite_len if last_idx_raw >= 0 else None
            if suite_len <= 1:
                new_idx = 0
            else:
                candidates = [i for i in range(suite_len) if i != exclude]
                new_idx = random.choice(candidates) if candidates else 0
            ui = example_suite_case(new_idx)

            # --- P-Module preselection (robust & leak-free) ---
            # Important: On example load we must NOT set CheckboxGroup values to non-existing choices.
            # Otherwise Gradio can throw "Value ... is not in list of choices" BEFORE we get to update choices.
            # Strategy:
            #   1) Extract desired selection into state_pmods_selected (IDs or labels are OK).
            #   2) Force UI checkbox values to [] for the first stage.
            #   3) _generate() will merge pmods_state into raw['modules'] and compute valid choices.
            #   4) _apply_pmods_values() sets the checkbox values after choices are updated.
            pending = {
                "lvl1": ui.get("modules_lvl1") or [],
                "lvl2": ui.get("modules_lvl2") or [],
                "lvl3": ui.get("modules_lvl3") or (ui.get("modules") or []),
            }

            # Ensure previous example selections do not leak into the UI stage
            ui["modules_lvl1"] = []
            ui["modules_lvl2"] = []
            ui["modules_lvl3"] = []

            vals = apply_ui_to_components(ui)
            # Merke den zuletzt gezeigten Index, damit der nächste Klick ihn
            # verlässlich überspringen kann.
            return (*vals, pending, "", new_idx)

        def _reset_flags_after_load():
            # New loaded example/file should be treated as clean until user edits.
            return {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [], "fast_load": True}

        def _reset_docx_states():
            return None, None


        
        def _reset_echo_import_states():
            echo_pdf_cur_reset = gr.update(value=None)
            echo_preview_cur_reset = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
            echo_state_cur_reset = {"parsed": None, "meta": None}

            echo_pdf_prev_reset = gr.update(value=None)
            echo_preview_prev_reset = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
            echo_state_prev_reset = {"parsed": None, "meta": None}

            echo_compare_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            echo_details_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            btn_apply_reset = gr.update(interactive=False)


            return (
                echo_pdf_cur_reset,
                echo_preview_cur_reset,
                echo_state_cur_reset,
                echo_pdf_prev_reset,
                echo_preview_prev_reset,
                echo_state_prev_reset,
                echo_compare_reset,
                echo_details_reset,
                btn_apply_reset,
                "",
            )


        def _post_example_load_and_generate(
            pmods_sel_state,
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
            pvod_edema_on_vaso, pvod_edema_desc,
            eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_vo2_peak_reached, cpet_vt1_method, cpet_vt1_manual_checked, cpet_vt1_time_min, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
            cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
            cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
            crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
            lsb_present, lsb_reason,
            *vals,
        ):
            # Reset flags + imports (example load should start clean)
            flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [], "fast_load": True}

            # Reset DOCX states
            docx_cur_state = None
            docx_prev_state = None

            # Reset Echo import states
            echo_pdf_cur_reset = gr.update(value=None)
            echo_preview_cur_reset = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
            echo_state_cur_reset = {"parsed": None, "meta": None}

            echo_pdf_prev_reset = gr.update(value=None)
            echo_preview_prev_reset = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
            echo_state_prev_reset = {"parsed": None, "meta": None}

            echo_compare_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            echo_details_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            btn_apply_reset = gr.update(interactive=False)

            case_filename = ""

            # Derived UI blocks
            sync_out = _sync_post_load(
                ct_done, ct_ild, vq_done,
                creatinine_mg_dl, age, sex,
                allergies_present, allergies_list,
                pvod_edema_on_vaso, pvod_edema_desc,
                eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            )
            cpet_out = _sync_post_load_cpet(
                cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred,
                cpet_vo2_peak_reached, cpet_vt1_method, cpet_vt1_manual_checked, cpet_vt1_time_min,
                cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg, cpet_ve_vco2_vt1,
                cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm,
                cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
        consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
        crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
        lsb_present, lsb_reason,
            )

            try:
                gen_out = _generate_with_pmods_apply(
        {}, flags, pmods_sel_state,
        docx_cur_state, docx_prev_state,
        echo_state_cur_reset, echo_state_prev_reset,
        case_filename,
        "de",
        *vals,
                )
            except _UI_RECOVERABLE_ERRORS as e:
                # Fail-safe: Example loading must never crash the app.
                log_exception("RHK_UI_EXAMPLE_GENERATE", "Example load post-processing generation failed.", e)
                # Keep inputs as loaded; clear generated outputs and surface a warning.
                warn = f"Beispiel laden: Generierung fehlgeschlagen: {type(e).__name__}: {e}"
                flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [warn], "fast_load": True}

                modules_lvl1_update = gr.update(choices=[], value=[])
                modules_lvl2_update = gr.update(choices=[], value=[])
                modules_lvl3_update = gr.update(choices=base_module_choices, value=[])
                pmods_disabled_dd_update = gr.update(choices=[], value=None)

                gen_out = (
                    None, None, None, None, None, None,
                    build_dashboard_html(None),
                    "", "", "", "", "",
                    "{}",
                    "{}",
                    "", "", "",
                    "", "", "",
                    "",
                    None,
                    flags,
                    {"lvl1": [], "lvl2": [], "lvl3": []},
                    None,
                    None,
                    modules_lvl1_update,
                    modules_lvl2_update,
                    modules_lvl3_update,
                    "",
                    pmods_disabled_dd_update,
                    build_sticky_summary_html(None, flags),
                    "",
                    "",
                    "",
                    "",
                )

            return (
        *sync_out,
        *cpet_out,
        *pre_cath_out,
        echo_pdf_cur_reset, echo_preview_cur_reset, echo_state_cur_reset,
        echo_pdf_prev_reset, echo_preview_prev_reset, echo_state_prev_reset,
        echo_compare_reset, echo_details_reset, btn_apply_reset,
        case_filename,
        *gen_out,
            )


        _example_then_inputs = [
            state_pmods_selected,
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["pvod_edema_on_vaso"], field_components["pvod_edema_desc"],
            field_components["eif2ak4_test_done"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_vo2_peak_reached"], field_components["cpet_vt1_method"], field_components["cpet_vt1_manual_checked"], field_components["cpet_vt1_time_min"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
            field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
            field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
            field_components["lsb_present"], field_components["lsb_reason"],
        ] + input_components

        _example_then_outputs = [
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            field_components["pvod_edema_desc"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
            cpet_details, cpet_risk_html,
            pre_cath_html, pre_cath_home_html,
            import_pdf_cur, import_preview_cur_html, state_echo_cur,
            import_pdf_prev, import_preview_prev_html, state_echo_prev,
            compare_echo_html, details_echo_html, btn_echo_apply,
            state_case_filename,
        ] + generate_outputs

        try:
            btn_example_top.click(
                _load_example_ui,
                inputs=[state_example_idx],
                outputs=input_components + [state_pmods_selected, state_case_filename, state_example_idx],
                queue=False,
                trigger_mode="always_last",
            ).then(
                _post_example_load_and_generate,
                inputs=_example_then_inputs,
                outputs=_example_then_outputs,
                queue=False,
                trigger_mode="always_last",
            )

            btn_example_bottom.click(
                _load_example_ui,
                inputs=[state_example_idx],
                outputs=input_components + [state_pmods_selected, state_case_filename, state_example_idx],
                queue=False,
                trigger_mode="always_last",
            ).then(
                _post_example_load_and_generate,
                inputs=_example_then_inputs,
                outputs=_example_then_outputs,
                queue=False,
                trigger_mode="always_last",
            )
        except TypeError:
            # Older Gradio builds may not support queue/trigger_mode on chained example events.
            btn_example_top.click(
                _load_example_ui,
                inputs=[state_example_idx],
                outputs=input_components + [state_pmods_selected, state_case_filename, state_example_idx],
            ).then(
                _post_example_load_and_generate,
                inputs=_example_then_inputs,
                outputs=_example_then_outputs,
            )

            btn_example_bottom.click(
                _load_example_ui,
                inputs=[state_example_idx],
                outputs=input_components + [state_pmods_selected, state_case_filename, state_example_idx],
            ).then(
                _post_example_load_and_generate,
                inputs=_example_then_inputs,
                outputs=_example_then_outputs,
            )


        # --- Clear all (Befunde leeren) ---
        # Reset inputs to safe defaults and clear all outputs/state.
        # IMPORTANT: Must return exactly len(load_outputs) values.
        load_outputs = [*input_components, *generate_outputs, import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html, details_echo_html, btn_echo_apply, state_case_filename]

        def _clear_all():

            # Inputs: start from DEFAULT_UI (component-native defaults) and clear patient-specific content.
            # This avoids "value not in choices" and type mismatches (e.g., CheckboxGroup expects list).
            empty_ui = dict(DEFAULT_UI)
            for k in input_keys:
                # Keep structural defaults from DEFAULT_UI, but clear user-entered content.
                if k not in empty_ui:
                    empty_ui[k] = None

            # Explicit empties for list-like fields
            for lk in ("meds", "comorbidities", "modules", "modules_lvl1", "modules_lvl2", "modules_lvl3", "ph_tx_table"):
                if lk in empty_ui:
                    empty_ui[lk] = []

            # Common text fields: reset to empty string for a clean UI
            for tk in ("firstname", "name", "story", "notes", "diagnosis_text", "therapy_text"):
                if tk in empty_ui:
                    empty_ui[tk] = ""

            # Dropdowns that must never be invalid (avoid "value not in choices" crashes)
            if "anticoag_indication" in empty_ui:
                empty_ui["anticoag_indication"] = "keine Angabe"

            vals = apply_ui_to_components(empty_ui)

            flags0 = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}

            # Reset module UI deterministically
            modules_lvl1_update = gr.update(choices=[], value=[])
            modules_lvl2_update = gr.update(choices=[], value=[])
            modules_lvl3_update = gr.update(choices=base_module_choices, value=[])
            pmods_disabled_dd_update = gr.update(choices=[], value=None)

            # Outputs: MUST mirror generate_outputs order exactly
            cleared_generate_outputs = (
                None, None, None, None, None, None,           # auto_mpap..auto_dpg
                build_dashboard_html(None),                    # dashboard
                "", "", "", "", "",                            # out_doc, out_pat, out_echo_doc, out_echo_pat, out_int
                "{}",                                          # out_summary_json
                "{}",                                          # out_json
                "", "", "",                                    # copy_*_plain
                "", "", "",                                    # copy_*_html
                "",                                            # copy_feedback
                None,                                          # state_case
                flags0,                                        # state_flags
                {"lvl1": [], "lvl2": [], "lvl3": []},          # state_pmods_selected
                None,                                          # state_docx_cur
                None,                                          # state_docx_prev
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                "",                                            # modules_disabled_html
                pmods_disabled_dd_update,                      # pmods_disabled_dd
                build_sticky_summary_html(None, flags0),       # sticky_summary_html
                "",                                            # compare_overview_html
                "",                                            # rhk_plots_html
                "",                                            # import_status_html
                "",                                            # modules_cards_html
            )

            # Echo import widgets/state
            echo_pdf_cur_reset = gr.update(value=None)
            echo_preview_cur_reset = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
            echo_state_cur_reset = {"parsed": None, "meta": None}

            echo_pdf_prev_reset = gr.update(value=None)
            echo_preview_prev_reset = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
            echo_state_prev_reset = {"parsed": None, "meta": None}

            echo_compare_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            echo_details_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
            btn_apply_reset = gr.update(interactive=False)

            return (
                *vals,
                *cleared_generate_outputs,
                echo_pdf_cur_reset,
                echo_preview_cur_reset,
                echo_state_cur_reset,
                echo_pdf_prev_reset,
                echo_preview_prev_reset,
                echo_state_prev_reset,
                echo_compare_reset,
                echo_details_reset,
                btn_apply_reset,
                "",  # state_case_filename
            )


        try:
            btn_clear_top.click(_clear_all, inputs=[], outputs=load_outputs, queue=False)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"], field_components["lsb_present"], field_components["lsb_reason"]], outputs=[pre_cath_html, pre_cath_home_html])
            btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs, queue=False)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"], field_components["lsb_present"], field_components["lsb_reason"]], outputs=[pre_cath_html, pre_cath_home_html])
        except TypeError:
            # Older Gradio builds may not support queue=...
            btn_clear_top.click(_clear_all, inputs=[], outputs=load_outputs)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"], field_components["lsb_present"], field_components["lsb_reason"]], outputs=[pre_cath_html, pre_cath_home_html])
            btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"], field_components["lsb_present"], field_components["lsb_reason"]], outputs=[pre_cath_html, pre_cath_home_html])


        # --- Clear / reset ---
        def _clear():
            # Reset all inputs + outputs deterministically
            empty_ui = {k: None for k in input_keys}
            # Explicit empties for list-like fields
            for lk in ("meds", "comorbidities", "modules_lvl1", "modules_lvl2", "modules_lvl3", "modules", "ph_tx_table"):
                if lk in empty_ui:
                    empty_ui[lk] = []
            vals = apply_ui_to_components(empty_ui)

            # Reset module UI: show all modules initially in Level III
            modules_lvl1_update = gr.update(choices=[], value=[])
            modules_lvl2_update = gr.update(choices=[], value=[])
            modules_lvl3_update = gr.update(choices=base_module_choices, value=[])

            dash = build_dashboard_html(None)
            flags0 = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}
            return (
                *vals,
                None, None, None, None, None, None,   # auto_* (6)
                dash,
                "", "", "", "", "",              # doc, patient, echo doc, echo patient, internal
                "{}",                                # out_summary_json
                "{}",                                # out_json
                "", "", "",                         # copy payloads
                "",                                  # copy feedback
                None,                                 # state_case
                flags0,                               # state_flags
                {"lvl1": [], "lvl2": [], "lvl3": []},   # state_pmods_selected
                modules_lvl1_update, modules_lvl2_update, modules_lvl3_update,
                "",                                  # disabled html
                build_sticky_summary_html(None, flags0),  # sticky summary
                "",                                  # compare overview
                "",                                  # module cards
            )

        def _save_case(
            case_state: Any,
            flags_state: Any,
            case_filename: Any,
            docx_cur_state: Any,
            docx_prev_state: Any,
            echo_cur_state: Any,
            echo_prev_state: Any,
        ):
            # Save should never throw a Gradio "Error" banner.
            # Local/Desktop: ask user for a folder (native dialog) and save there.
            # Web/Cloud: provide downloadable files via gr.File components.

            if not case_state:
                # Hide both downloads
                return (
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    dict(flags_state or {}),
                    build_sticky_summary_html(None, dict(flags_state or {})),
                    "",
                )
            try:
                save_bundle = save_case_bundle(
                    case_state,
                    flags_state,
                    case_filename,
                    docx_cur_state,
                    docx_prev_state,
                    echo_cur_state,
                    echo_prev_state,
                    rulebook_meta=rulebook_meta,
                )
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_SAVE_EXPORT", "Case export failed.", exc)
                # Do not crash the UI; show a clear message and keep downloads hidden.
                return (
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    dict(flags_state or {}),
                    build_sticky_summary_html(case_state, dict(flags_state or {})),
                    f"❌ Speichern fehlgeschlagen: {type(exc).__name__}: {exc}",
                )

            if isinstance(case_state, dict):
                case_state["summary"] = save_bundle.summary_dict

            sticky = build_sticky_summary_html(case_state, save_bundle.updated_flags)
            # Provide downloads as well (user can choose location in browser download dialog).
            return (
                gr.update(visible=True, value=save_bundle.case_path),
                gr.update(visible=True, value=save_bundle.summary_path),
                save_bundle.updated_flags,
                sticky,
                "✅ Gespeichert. (Bei Bedarf über die Download-Links herunterladen.)",
            )

        _save_outputs = [file_out, file_summary_out, state_flags, sticky_summary_html, copy_feedback]

        save_btn_top.click(
            _generate_with_pmods_apply,
            inputs=[state_case, state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename, ui_lang] + input_components,
            outputs=generate_outputs,
        ).then(
            _save_case,
            inputs=[state_case, state_flags, state_case_filename, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev],
            outputs=_save_outputs,
        )
        save_btn_bottom.click(
            _generate_with_pmods_apply,
            inputs=[state_case, state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename, ui_lang] + input_components,
            outputs=generate_outputs,
        ).then(
            _save_case,
            inputs=[state_case, state_flags, state_case_filename, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev],
            outputs=_save_outputs,
        )

        # --- Load case ---

        def _load_case_ui(file, as_followup: bool = False):
            # Returns values for:
            # - input_components
            # - state_pmods_selected (pending module selection)
            # - state_docx_cur / state_docx_prev (import caches)
            # - echo import UI (states + rendered preview/compare html)
            empty_pending: Dict[str, List[Any]] = {"lvl1": [], "lvl2": [], "lvl3": []}
            followup_mode = bool(as_followup)
            if file is None:
                # Keep everything as-is; do not clobber states.
                return [c.value for c in input_components] + [empty_pending, None, None,
                                                             gr.update(value=None), "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>", {"parsed": {}, "meta": {}, "has_file": False},
                                                             gr.update(value=None), "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>", {"parsed": {}, "meta": {}, "has_file": False},
                                                             "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>",
                                                             "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>",
                                                             gr.update(interactive=False)] + ["", {}]

            try:
                loaded_bundle = load_case_bundle(file.name, as_followup=followup_mode)
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_LOAD_JSON", "Loading case JSON failed; using empty payload.", exc, file_name=getattr(file, "name", str(file)))
                loaded_bundle = None

            if loaded_bundle is None:
                ui_dict = {}
                pending = empty_pending
                docx_cur = None
                docx_prev = None
                echo_cur = {"parsed": {}, "meta": {}, "has_file": False}
                echo_prev = {"parsed": {}, "meta": {}, "has_file": False}
                loaded_name = ""
                baseline_payload: Dict[str, Any] = {"ui": {}}
            else:
                ui_dict = loaded_bundle.ui_dict
                pending = loaded_bundle.pending_modules
                docx_cur = loaded_bundle.docx_cur
                docx_prev = loaded_bundle.docx_prev
                echo_cur = loaded_bundle.echo_cur
                echo_prev = loaded_bundle.echo_prev
                loaded_name = loaded_bundle.loaded_name
                baseline_payload = loaded_bundle.baseline_payload
            vals = apply_ui_to_components(ui_dict)

            try:
                cur_html, prev_html, cmp_html, details_html, btnu = render_echo_import_views(echo_prev, echo_cur)
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_UI_ECHO_IMPORT_VIEWS", "Echo import view rendering failed; using fallback placeholders.", exc)
                cur_html = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
                prev_html = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
                cmp_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
                details_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
                btnu = gr.update(interactive=False)

            # We cannot restore uploaded file objects; keep upload widgets empty.
            pdf_cur_reset = gr.update(value=None)
            pdf_prev_reset = gr.update(value=None)

            return (*vals,
                    pending,
                    docx_cur, docx_prev,
                    pdf_cur_reset, cur_html, echo_cur,
                    pdf_prev_reset, prev_html, echo_prev,
                    cmp_html, details_html, btnu, loaded_name, baseline_payload)

        


        # -------------------------
        # DOCX Import (Mac-Lab)
        # -------------------------
        DOCX_WIPE_CURRENT = dict(DOCX_CURRENT_WIPE_DEFAULTS)

        DOCX_WIPE_PREV = dict(DOCX_PREV_WIPE_DEFAULTS)

        def _docx_import_current(file, prev_payload, prev_docx_payload, *vals):
            """Import current DOCX without deleting manual entries.

            Policy:
            - Only fields that were previously imported and remain unchanged are eligible for overwrite/clear.
            - Empty fields are eligible for auto-fill.
            - Manual edits are preserved.
            """
            file_path = file.name if hasattr(file, "name") else str(file)
            import_bundle = import_current_docx(
                file_path,
                ui_dict=ui_get_raw(*vals),
                prev_payload=prev_payload,
                prev_docx_payload=prev_docx_payload,
                wipe_defaults=DOCX_WIPE_CURRENT,
            )
            vals_out = apply_ui_to_components(import_bundle.ui_dict)
            return (*vals_out, import_bundle.payload, import_bundle.status_html)

        def _docx_import_prev(file, prev_payload, cur_docx_payload, *vals):
            file_path = file.name if hasattr(file, "name") else str(file)
            import_bundle = import_previous_docx(
                file_path,
                ui_dict=ui_get_raw(*vals),
                prev_payload=prev_payload,
                current_docx_payload=cur_docx_payload,
                wipe_defaults=DOCX_WIPE_PREV,
            )
            vals_out = apply_ui_to_components(import_bundle.ui_dict)
            return (*vals_out, import_bundle.payload, import_bundle.status_html)


        def _reset_pmods_after_import():
            # Reset pending module selection to avoid stale templates influencing a new import.
            return {"lvl1": [], "lvl2": [], "lvl3": []}




        def _post_docx_current_import_and_generate(
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
            pvod_edema_on_vaso, pvod_edema_desc,
            eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
            cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
            cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
            crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
            lsb_present, lsb_reason,
            docx_cur_payload, docx_prev_payload,
            echo_cur_payload, echo_prev_payload,
            case_filename,
            *vals,
        ):
            pmods_sel_state = {"lvl1": [], "lvl2": [], "lvl3": []}
            flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [], "fast_load": False}

            sync_out = _sync_post_load(
                ct_done, ct_ild, vq_done,
                creatinine_mg_dl, age, sex,
                allergies_present, allergies_list,
                pvod_edema_on_vaso, pvod_edema_desc,
                eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            )
            cpet_out = _sync_post_load_cpet(
                # Legacy DOCX import does not provide the newer Step-1 / VT1 wizard fields.
                # Policy: missing != 0 -> pass None (do not impute).
                cpet_done,
                cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred,
                None,  # cpet_vo2_peak_reached
                None, None, None,  # cpet_vt1_method, cpet_vt1_manual_checked, cpet_vt1_time_min
                cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg, cpet_ve_vco2_vt1,
                cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm,
                cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
                consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
                crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
                lsb_present, lsb_reason,
            )

            gen_out = _generate_with_pmods_apply(
                {}, flags, pmods_sel_state,
                docx_cur_payload, docx_prev_payload,
                echo_cur_payload, echo_prev_payload,
                case_filename,
                "de",
                *vals,
            )
            return (*sync_out, *cpet_out, *pre_cath_out, *gen_out)

        def _post_docx_prev_import_and_generate(
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
            pvod_edema_on_vaso, pvod_edema_desc,
            eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
            cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
            cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
            crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
            lsb_present, lsb_reason,
            pmods_sel_state,
            docx_cur_payload, docx_prev_payload,
            echo_cur_payload, echo_prev_payload,
            case_filename,
            *vals,
        ):
            flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [], "fast_load": False}

            sync_out = _sync_post_load(
                ct_done, ct_ild, vq_done,
                creatinine_mg_dl, age, sex,
                allergies_present, allergies_list,
                pvod_edema_on_vaso, pvod_edema_desc,
                eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            )
            cpet_out = _sync_post_load_cpet(
                # Legacy DOCX import does not provide the newer Step-1 / VT1 wizard fields.
                # Policy: missing != 0 -> pass None (do not impute).
                cpet_done,
                cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred,
                None,  # cpet_vo2_peak_reached
                None, None, None,  # cpet_vt1_method, cpet_vt1_manual_checked, cpet_vt1_time_min
                cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg, cpet_ve_vco2_vt1,
                cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm,
                cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
                consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
                crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
                lsb_present, lsb_reason,
            )

            gen_out = _generate_with_pmods_apply(
                {}, flags, pmods_sel_state,
                docx_cur_payload, docx_prev_payload,
                echo_cur_payload, echo_prev_payload,
                case_filename,
                "de",
                *vals,
            )
            return (*sync_out, *cpet_out, *pre_cath_out, *gen_out)

        # Update DOCX overview immediately on import (no dependency on report generation).
        docx_btn_top.upload(
            _docx_import_current,
            inputs=[docx_btn_top, state_docx_cur, state_docx_prev] + input_components,
            outputs=input_components + [state_docx_cur, import_status_html],
        )\
            .then(
                _post_docx_current_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
                    field_components["pvod_edema_on_vaso"], field_components["pvod_edema_desc"],
                    field_components["eif2ak4_test_done"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
                    field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
                    field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
                    field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
                    field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
                    field_components["lsb_present"], field_components["lsb_reason"],
                    state_docx_cur, state_docx_prev,
                    state_echo_cur, state_echo_prev,
                    state_case_filename,
                ] + input_components,
                outputs=[
                    ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
                    field_components["pvod_edema_desc"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    cpet_details, cpet_risk_html,
                    pre_cath_html, pre_cath_home_html,
                ] + generate_outputs,
            )

        docx_btn_bottom.upload(
            _docx_import_current,
            inputs=[docx_btn_bottom, state_docx_cur, state_docx_prev] + input_components,
            outputs=input_components + [state_docx_cur, import_status_html],
        )\
            .then(
                _post_docx_current_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
                    field_components["pvod_edema_on_vaso"], field_components["pvod_edema_desc"],
                    field_components["eif2ak4_test_done"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
                    field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
                    field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
                    field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
                    field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
                    field_components["lsb_present"], field_components["lsb_reason"],
                    state_docx_cur, state_docx_prev,
                    state_echo_cur, state_echo_prev,
                    state_case_filename,
                ] + input_components,
                outputs=[
                    ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
                    field_components["pvod_edema_desc"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    cpet_details, cpet_risk_html,
                    pre_cath_html, pre_cath_home_html,
                ] + generate_outputs,
            )

        prev_docx_btn.upload(
            _docx_import_prev,
            inputs=[prev_docx_btn, state_docx_prev, state_docx_cur] + input_components,
            outputs=input_components + [state_docx_prev, import_status_html],
        )\
            .then(
                _post_docx_prev_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
                    field_components["pvod_edema_on_vaso"], field_components["pvod_edema_desc"],
                    field_components["eif2ak4_test_done"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
                    field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
                    field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
                    field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
                    field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
                    field_components["lsb_present"], field_components["lsb_reason"],
                    state_pmods_selected,
                    state_docx_cur, state_docx_prev,
                    state_echo_cur, state_echo_prev,
                    state_case_filename,
                ] + input_components,
                outputs=[
                    ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
                    field_components["pvod_edema_desc"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
                    cpet_details, cpet_risk_html,
                    pre_cath_html, pre_cath_home_html,
                ] + generate_outputs,
            )

        # -------------------------
        # DOCX Import entfernen (Undo)
        # -------------------------
        def _wipe_docx_current(prev_payload, *vals):
            ui_dict = ui_get_raw(*vals)
            prev_payload = prev_payload if isinstance(prev_payload, dict) else {}
            prev_keys = prev_payload.get("_ui_applied_keys_current") or []
            prev_vals = prev_payload.get("_ui_applied_values_current") or {}
            for k in prev_keys:
                if k in DOCX_WIPE_CURRENT and ui_dict.get(k) == prev_vals.get(k):
                    ui_dict[k] = DOCX_WIPE_CURRENT.get(k)
            return (*apply_ui_to_components(ui_dict), None)

        def _wipe_docx_prev(prev_payload, *vals):
            ui_dict = ui_get_raw(*vals)
            prev_payload = prev_payload if isinstance(prev_payload, dict) else {}
            prev_keys = prev_payload.get("_ui_applied_keys_prev") or []
            prev_vals = prev_payload.get("_ui_applied_values_prev") or {}
            for k in prev_keys:
                if k in DOCX_WIPE_PREV and ui_dict.get(k) == prev_vals.get(k):
                    ui_dict[k] = DOCX_WIPE_PREV.get(k)
            return (*apply_ui_to_components(ui_dict), None)

        if btn_wipe_docx_current is not None:
            btn_wipe_docx_current.click(
                _wipe_docx_current,
                inputs=[state_docx_cur] + input_components,
                outputs=input_components + [state_docx_cur],
            ).then(
                _generate_with_pmods_apply,
                inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components,
                outputs=generate_outputs,
            )

        if btn_wipe_docx_prev is not None:
            btn_wipe_docx_prev.click(
                _wipe_docx_prev,
                inputs=[state_docx_prev] + input_components,
                outputs=input_components + [state_docx_prev],
            ).then(
                _generate_with_pmods_apply,
                inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components,
                outputs=generate_outputs,
            )

        # -------------------------
        # Plots on-demand (Performance)
        # -------------------------
        if btn_update_plots is not None:

            def _update_plots_on_demand(case_state, docx_cur_state, docx_prev_state, lang="de"):
                if not isinstance(case_state, dict) or not case_state:
                    raise gr.Error(tr_ui("Bitte zuerst den Befund erstellen, dann Plots aktualisieren.", lang))
                try:
                    html_out = build_rhk_plots_html(case_state, docx_cur_state, docx_prev_state) or ""
                except _UI_RECOVERABLE_ERRORS as e:
                    log_exception("RHK_UI_PLOTS_RENDER", "On-demand plot rendering failed.", e)
                    html_out = (
                        "<div class='docx-muted'>❌ Plots konnten nicht erzeugt werden: "
                        + html.escape(f"{type(e).__name__}: {e}")
                        + "</div>"
                    )
                return html_out, "✅ Plots aktualisiert."

            btn_update_plots.click(
                _update_plots_on_demand,
                inputs=[state_case, state_docx_cur, state_docx_prev, ui_lang],
                outputs=[rhk_plots_html, copy_feedback],
                queue=False,
                trigger_mode="always_last",
            )

        # (No second binding here – keep exactly one on-demand path.)


        def _post_case_load_and_generate(
            # thorax + egfr + allergies
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
            pvod_edema_on_vaso, pvod_edema_desc,
            eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            # CPET live-risk
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
            cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
            cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            # CPET wizard (full)
            wiz_cpet_done,
            stop_reason, stop_reason_text,
            borg_rpe, borg_dyspnoe, borg_legs,
            wiz_rer_peak, wiz_hr_peak, wiz_hr_pct,
            wiz_peak_vo2, wiz_peak_vo2_pct, wiz_vo2_peak_reached,
            wiz_vt1_method, wiz_vt1_manual_checked, wiz_vt1_time_min,
            o2p_ml, o2p_pattern, o2p_slope,
            bp_sys_rest, bp_dia_rest,
            bp_sys_peak, bp_dia_peak,
            wiz_vevco2_slope, pet_rest, pet_peak, pet_vt1,
            br_pct,
            vevco2_vt1,
            spo2_rest, spo2_peak, spo2_nadir, o2_supp,
            vo2_wr_slope,
            ve_peak, mvv, mvv_source,
            angina, dizziness, syncope, palpitations,
            arrhythmia, arrhythmia_text, st_changes,
            beta_blocker, sinus_node, hypervent,
            chrono_comment,
            limitation_override, limitation_override_text, next_steps_manual,
            nine_avail, nine_vt1, nine_vt1_method, nine_rcp,
            nine_eov, nine_flow, nine_vo2wr, nine_veeq, nine_comment,
            # pre-cath
            consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
            crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
            lsb_present, lsb_reason,
            # states for generate
            case_state_loaded, pmods_sel_state, docx_cur_payload, docx_prev_payload, echo_cur_payload, echo_prev_payload, case_filename,
            *vals,
        ):
            # IMPORTANT (Stabilitaet/Kompatibilitaet)
            # Beim Laden alter JSON-Faelle kann die nachgelagerte Report-/HTML-Generierung
            # (inkl. JSON-Dumps, Clipboard-HTML, Plots) sehr langsam werden oder haengen.
            # Policy: Nach dem Laden KEINE automatische Generierung. Stattdessen wird der
            # Fall nur in die UI uebernommen und der Nutzer klickt gezielt "Befund erstellen".
            flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": True, "warnings": []}

            sync_out = _sync_post_load(
                ct_done, ct_ild, vq_done,
                creatinine_mg_dl, age, sex,
                allergies_present, allergies_list,
                pvod_edema_on_vaso, pvod_edema_desc,
                eif2ak4_test_done, eif2ak4_result, eif2ak4_date, eif2ak4_note,
            )
            cpet_out = _sync_post_load_cpet(
                # NOTE: Case-load path must be compatible with older saved JSON that
                # does not include the newer CPET Step-1 / VT1 wizard fields.
                # Policy: missing != 0 -> pass None (do not impute).
                cpet_done,
                cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred,
                None,  # cpet_vo2_peak_reached
                None, None, None,  # cpet_vt1_method, cpet_vt1_manual_checked, cpet_vt1_time_min
                cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg, cpet_ve_vco2_vt1,
                cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm,
                cpet_o2_pulse_pattern,
            )
            wiz_out = _sync_post_load_cpet_wizard(
        wiz_cpet_done,
        stop_reason, stop_reason_text,
        borg_rpe, borg_dyspnoe, borg_legs,
        wiz_rer_peak, wiz_hr_peak, wiz_hr_pct,
        wiz_peak_vo2, wiz_peak_vo2_pct, wiz_vo2_peak_reached,
        wiz_vt1_method, wiz_vt1_manual_checked, wiz_vt1_time_min,
        o2p_ml, o2p_pattern, o2p_slope,
        bp_sys_rest, bp_dia_rest,
        bp_sys_peak, bp_dia_peak,
        wiz_vevco2_slope, pet_rest, pet_peak, pet_vt1,
        br_pct,
        vevco2_vt1,
        spo2_rest, spo2_peak, spo2_nadir, o2_supp,
        vo2_wr_slope,
        ve_peak, mvv, mvv_source,
        angina, dizziness, syncope, palpitations,
        arrhythmia, arrhythmia_text, st_changes,
        beta_blocker, sinus_node, hypervent,
        chrono_comment,
        limitation_override, limitation_override_text, next_steps_manual,
        nine_avail, nine_vt1, nine_vt1_method, nine_rcp,
        nine_eov, nine_flow, nine_vo2wr, nine_veeq, nine_comment,
            )
            pre_cath_out = _update_pre_cath_both(
        consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
        crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
        lsb_present, lsb_reason,
            )

            # Minimal outputs: keep imports/states, but do not build reports automatically.
            # NOTE: generate_outputs order must be mirrored exactly.
            modules_lvl1_update = gr.update()
            modules_lvl2_update = gr.update()
            modules_lvl3_update = gr.update()
            pmods_disabled_dd_update = gr.update()
            _meta = (case_state_loaded.get("meta") if isinstance(case_state_loaded, dict) else {}) or {}
            _is_followup_load = str(_meta.get("load_mode") or "").strip().lower() == "followup"
            load_feedback = (
                "⚠️ Verlauf geladen: Vor-RHK übernommen, aktueller Katheter geleert. Bitte neuen Befund erstellen."
                if _is_followup_load
                else "⚠️ Fall geladen. Bitte Befund erstellen."
            )
            cleared_generate_outputs = (
                None, None, None, None, None, None,           # auto_mpap..auto_dpg
                build_dashboard_html(None),                    # dashboard
                "", "", "", "", "",                           # out_doc, out_pat, out_echo_doc, out_echo_pat, out_int
                "{}",                                          # out_summary_json
                "{}",                                          # out_json
                "", "", "",                                    # copy_*_plain
                "", "", "",                                    # copy_*_html
                load_feedback,                                  # copy_feedback
                case_state_loaded,                              # state_case
                flags,                                         # state_flags
                (pmods_sel_state or {"lvl1": [], "lvl2": [], "lvl3": []}),  # state_pmods_selected
                docx_cur_payload,                              # state_docx_cur
                docx_prev_payload,                             # state_docx_prev
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                "",                                            # modules_disabled_html
                pmods_disabled_dd_update,                      # pmods_disabled_dd
                build_sticky_summary_html(None, flags),        # sticky_summary_html
                "",                                            # compare_overview_html
                "",                                            # rhk_plots_html
                "",                                            # import_status_html
                "",                                            # modules_cards_html
            )

            return (*sync_out, *cpet_out, *wiz_out, *pre_cath_out, *cleared_generate_outputs)

        def _load_case_ui_default(file):
            return _load_case_ui(file, as_followup=False)

        def _load_case_ui_followup(file):
            return _load_case_ui(file, as_followup=True)

        _load_case_outputs = input_components + [
            state_pmods_selected,
            state_docx_cur, state_docx_prev,
            import_pdf_cur, import_preview_cur_html, state_echo_cur,
            import_pdf_prev, import_preview_prev_html, state_echo_prev,
            compare_echo_html, details_echo_html, btn_echo_apply,
            state_case_filename,
            state_case,
        ]

        _post_case_load_inputs = [
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["pvod_edema_on_vaso"], field_components["pvod_edema_desc"],
            field_components["eif2ak4_test_done"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],

            field_components["cpet_done"],
            field_components["cpet_stop_reason"], field_components["cpet_stop_reason_text"],
            field_components["cpet_borg_rpe"], field_components["cpet_borg_dyspnoe"], field_components["cpet_borg_legs"],
            field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_hr_pct_pred"],
            field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_vo2_peak_reached"], field_components["cpet_vt1_method"], field_components["cpet_vt1_manual_checked"], field_components["cpet_vt1_time_min"],
            field_components["cpet_peak_o2_pulse_ml"], field_components["cpet_o2_pulse_pattern"], field_components["cpet_o2_pulse_slope"],
            field_components["cpet_bp_sys_rest"], field_components["cpet_bp_dia_rest"],
            field_components["cpet_bp_sys_peak"], field_components["cpet_bp_dia_peak"],
            field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_rest_mmhg"], field_components["cpet_petco2_peak_mmhg"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_breathing_reserve_pct"],
            field_components["cpet_ve_vco2_vt1"],
            field_components["cpet_spo2_rest_pct"], field_components["cpet_spo2_peak_pct"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_o2_supp_l_min"],
            field_components["cpet_vo2_wr_slope_ml_min_w"],
            field_components["cpet_ve_peak_l_min"], field_components["cpet_mvv_l_min"], field_components["cpet_mvv_source"],
            field_components["cpet_angina"], field_components["cpet_dizziness"], field_components["cpet_syncope"], field_components["cpet_palpitations"],
            field_components["cpet_arrhythmia"], field_components["cpet_arrhythmia_text"], field_components["cpet_st_changes"],
            field_components["cpet_beta_blocker"], field_components["cpet_sinus_node_disorder"], field_components["cpet_hyperventilation"],
            field_components["cpet_chrono_comment"],
            field_components["cpet_limitation_override"], field_components["cpet_limitation_override_text"], field_components["cpet_next_steps_manual"],
            field_components["cpet_9panel_available"], field_components["cpet_9panel_vt1_identified"], field_components["cpet_9panel_vt1_method"], field_components["cpet_9panel_rcp_identified"],
            field_components["cpet_9panel_eov"], field_components["cpet_9panel_flowvol_limit"], field_components["cpet_9panel_vo2wr_pattern"], field_components["cpet_9panel_veeq_pattern"], field_components["cpet_9panel_comment"],

            field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
            field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
            field_components["lsb_present"], field_components["lsb_reason"],

            state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename,
        ] + input_components

        _post_case_load_outputs = [
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            field_components["pvod_edema_desc"], field_components["eif2ak4_result"], field_components["eif2ak4_date"], field_components["eif2ak4_note"],
            cpet_details, cpet_risk_html,
            cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_live_html, cpet_teaching_html, cpet_spiro_report, cpet_chrono_followup,
            pre_cath_html, pre_cath_home_html,
        ] + generate_outputs

        def _bind_case_loader(upload_comp: Any, *, followup: bool = False) -> None:
            loader = _load_case_ui_followup if followup else _load_case_ui_default
            upload_comp.upload(
                loader,
                inputs=[upload_comp],
                outputs=_load_case_outputs,
            ).then(
                _post_case_load_and_generate,
                inputs=_post_case_load_inputs,
                outputs=_post_case_load_outputs,
            )

        _bind_case_loader(load_btn_top, followup=False)
        _bind_case_loader(load_btn_bottom, followup=False)
        _bind_case_loader(load_followup_btn_top, followup=True)
        _bind_case_loader(load_followup_btn_bottom, followup=True)
        # Copy-to-Word buttons are handled by the HEAD script (cross-browser; no Gradio _js dependency).

        # --- Startseite/Footer: Tool-Disclaimer (dezent, aber dauerhaft sichtbar) ---
        # Hinweis: bewusst NICHT in PDFs. Gilt nur für das Tool selbst.
        gr.HTML(
            """
            <div id='rhk_tool_disclaimer'>
              <div class='rhk-disclaimer-inner'>
                <div class='rhk-disclaimer-title'>Hinweis (Forschungs- und Testbetrieb)</div>
                <div class='rhk-disclaimer-text'>
                  Dieses Tool befindet sich im Forschungs- und Testbetrieb und dient ausschließlich wissenschaftlichen, explorativen und evaluativen Zwecken.
                  Die Anwendung ist nicht als Medizinprodukt im Sinne der MDR zertifiziert und nicht zur alleinigen Unterstützung klinischer Entscheidungen vorgesehen.
                  Es besteht kein Anspruch auf Vollständigkeit, Richtigkeit oder Aktualität der dargestellten Inhalte.
                  Die Verantwortung für medizinische Entscheidungen verbleibt vollständig bei der behandelnden Ärztin bzw. dem behandelnden Arzt.
                </div>
                <div class='rhk-disclaimer-title' style='margin-top:0.6em;'>Datenschutz, Anonymität und rechtlicher Rahmen</div>
                <div class='rhk-disclaimer-text'>
                  Die Nutzung erfolgt ausschließlich zu Forschungs-, Lehr- und Evaluationszwecken im Rahmen des akademischen Auftrags des PH-Zentrums Universitätsklinikum Gießen. Die Verarbeitung personenbezogener Gesundheitsdaten ist nur unter strikter Beachtung der DSGVO (insb. Art. 9 Abs. 2 lit. j DSGVO i. V. m. § 27 BDSG), des HDSIG sowie einschlägiger landesrechtlicher und berufsrechtlicher Vorschriften zulässig. Vor jeder Eingabe von Patientendaten ist eine vollständige Anonymisierung oder Pseudonymisierung sicherzustellen; identifizierende Merkmale (Name, Geburtsdatum, Adresse, Versicherten- und Fallnummer, Aufnahme-IDs) dürfen nicht eingegeben werden. Re-identifikationsfähige Kombinationen sind zu vermeiden. Die Datenverarbeitung darf nur auf Grundlage einer wirksamen Einwilligung der betroffenen Person, eines Ethikvotums oder einer anderen tragfähigen Rechtsgrundlage erfolgen. Eine Übermittlung an Dritte oder eine Nutzung zu kommerziellen Zwecken ist untersagt. Die Nutzenden sind verantwortlich für die rechtskonforme Datenerhebung, -verarbeitung und -speicherung an ihrem Arbeitsplatz (Zugriffsschutz, Verschlüsselung, Speicherorte, Löschfristen) sowie für die Einhaltung der ärztlichen Schweigepflicht (§ 203 StGB). Eine Haftung der Entwicklerinnen und Entwickler sowie des PH-Zentrums Universitätsklinikum Gießen für Schäden aus unsachgemäßer Nutzung, fehlender Anonymisierung oder Verstößen gegen datenschutzrechtliche Vorgaben ist ausgeschlossen, soweit gesetzlich zulässig. Mit der Nutzung des Tools bestätigen Sie, diese Hinweise gelesen und verstanden zu haben sowie sie einzuhalten.
                </div>
              </div>
            </div>
            """,
            elem_id="rhk_tool_disclaimer_wrapper",
        )

    # Backwards-compatible return signature expected by rhk_app_web_master.py.
    # Note: on Gradio 6+ the CSS/JS/HEAD/THEME are passed via demo._rhk_launch_kwargs.
    return demo, CSS, theme
