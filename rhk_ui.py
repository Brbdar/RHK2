#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

from rhk_base import *  # noqa: F401,F403

from rhk_case import build_case, build_dashboard_html  # noqa: F401
from rhk_reports import (
    build_doctor_report,
    build_doctor_report_template,
    build_doctor_report_for_copy,
    build_patient_report,
    build_echo_patient_report,
    build_echo_doctor_report_extended,
    build_internal_report,
    random_example,
    export_json,
    export_summary_json,
    build_summary_dict,
    markdown_to_plain,
    markdown_to_word_html,
    _markdown_to_plain_cached,
    _markdown_to_word_html_cached,
    _extract_markdown_section_cached,
    markdown_to_docx_file,
    extract_markdown_section,
    load_case_json,
)  # noqa: F401
from rhk_import_docx import parse_maclab_docx, map_payload_to_ui  # noqa: F401
from rhk_ui_echo import build_echo_section, bind_echo_import, render_echo_import_views  # noqa: F401
from rhk_ui_rhk import build_rhk_tab  # noqa: F401

# Deterministic CPET expert logic (Spiro-Logic wizard)
# Performance: lazy import to reduce cold-start time.
import importlib

_SPIRO_LOGIC = None

def _get_spiro_logic():
    global _SPIRO_LOGIC
    if _SPIRO_LOGIC is None:
        _SPIRO_LOGIC = importlib.import_module('spiro_logic')
    return _SPIRO_LOGIC

from rhk_ui_assets import CSS, JS_ON_LOAD, HEAD_HTML  # noqa: F401
from rhk_ui_utils import _gradio_major_version  # re-export for rhk_launch

from rhk_ui_utils import (  # noqa: F401
    load_rulebook_meta,
    build_sticky_summary_html,
    build_compare_overview_html,
    build_docx_status_html,
    build_docx_tables_overview_html,
    build_rhk_plots_html,
    build_p_module_cards_html,
    build_pre_cath_header_html,
    compute_egfr,
)
def build_demo() -> Tuple[gr.Blocks, str, gr.Theme]:
    blocks = load_textdb_blocks()
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    rulebook_meta = load_rulebook_meta(DEFAULT_RULEBOOK_PATH)

    # Gradio versions differ; themes are available in newer builds.
    theme = None
    try:
        if hasattr(gr, "themes"):
            theme = gr.themes.Soft()
    except Exception:
        theme = None

    # Gradio 6 moved theme/css/js/head from the Blocks constructor to `.launch()`.
    # We want:
    # - zero warnings on Gradio 6+
    # - full compatibility with Gradio 5
    def _gradio_major() -> int:
        import re
        v = str(getattr(gr, "__version__", ""))
        m = re.match(r"\s*(\d+)", v)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except Exception:
            return 0

    _major = _gradio_major()

    launch_kwargs: Dict[str, Any] = {"css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
    if theme is not None:
        launch_kwargs["theme"] = theme

    if _major >= 6:
        # 6.x+: pass assets to launch() (constructor must stay clean)
        demo_ctx = gr.Blocks(title=APP_TITLE)
        setattr(demo_ctx, "_rhk_launch_kwargs", launch_kwargs)
    else:
        # 5.x: assets belong to Blocks constructor
        blocks_kwargs: Dict[str, Any] = {"title": APP_TITLE, "css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
        if theme is not None:
            blocks_kwargs["theme"] = theme
        demo_ctx = gr.Blocks(**blocks_kwargs)
        setattr(demo_ctx, "_rhk_launch_kwargs", {})

    with demo_ctx as demo:
        # Header
        gr.HTML(RHK_HEADER_HTML)
        gr.Markdown(f"<div class='whatsnew'>{WHATS_NEW}</div>")

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
# Buttons top
        with gr.Row():
            btn_example_top = gr.Button("Beispiel laden (random)", variant="secondary", elem_id="btn_example_top")
            btn_generate_top = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_top")
            btn_clear_top = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_top")
            save_btn_top = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_top")
            load_btn_top = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_top")
        docx_btn_top = gr.UploadButton("RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_top")
        # DOCX Import Übersicht wird im RHK-Tab angezeigt (Accordion, open=True).
        # Layout: left inputs, right outputs
        with gr.Row():
            with gr.Column(scale=7):
                tabs = gr.Tabs(elem_id="rhk_input_tabs")

                # Tab subtitle (client-side; helps orientation when scrolling)
                gr.HTML("", elem_id="rhk_tab_subtitle")

                field_components: Dict[str, gr.components.Component] = {}

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
                            setattr(comp, "info", info)
                        except Exception:
                            pass
                    field_components[name] = comp
                    return comp

                # ---- Tab 1: Klinik & Labor ----
                with gr.TabItem("Klinik & Labor", id=0):
                    # Card 1: Allgemeines/Anamnese/Vorerkrankungen
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_klinik_general = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Allgemeines, Anamnese, Vorerkrankungen</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("firstname", gr.Textbox(label="Vorname"))
                                add("name", gr.Textbox(label="Name"))
                            with gr.Row():
                                add("age", gr.Number(label="Alter (Jahre)"))
                                add("sex", gr.Dropdown(label="Geschlecht", choices=["keine Angabe", "weiblich", "männlich"], value="keine Angabe"))
                            with gr.Row():
                                add("height_cm", gr.Number(label="Größe (cm)"))
                                add("weight_kg", gr.Number(label="Gewicht (kg)"))
                            with gr.Row():
                                add("bp_sys", gr.Number(label="RR syst (mmHg)"))
                                add("bp_dia", gr.Number(label="RR diast (mmHg)"))
                                add("hr", gr.Number(label="Herzfrequenz (/min)"))
                            add("story", gr.Textbox(label="Story / Kurz-Anamnese", lines=3))
                            add("comorbidities", gr.Textbox(
                                label="Relevante Vorerkrankungen",
                                lines=2,
                                placeholder="z.B. KHK, COPD, Z. n. LAE, CKD …",
                            ))
                            with gr.Row():
                                ekg_present = add("ekg_present", gr.Checkbox(label="12-Kanal-EKG vorhanden"))
                                add("lsb_present", gr.Checkbox(label="LSB (Linksschenkelblock)"))
                            # LSB: Begründung nur wenn LSB aktiv
                            add(
                                "lsb_reason",
                                gr.Textbox(
                                    label="LSB: Begründung (z.B. bekannt seit…, Quelle EKG…)",
                                    lines=1,
                                    placeholder="Kurz begründen, warum LSB relevant ist (z.B. präexistent im EKG vom …).",
                                    visible=False,
                                ),
                            )
                            with gr.Column(visible=False) as ekg_details:
                                add(
                                    "ekg_rhs_signs",
                                    gr.Dropdown(
                                        label="EKG: Rechtsherzbelastungszeichen (Mehrfachauswahl)",
                                        choices=[
                                            "Rechtsachsenabweichung",
                                            "P pulmonale",
                                            "R/S in V1 > 1 (RVH)",
                                            "RBBB",
                                            "T-Negativierung rechtspräkordial",
                                            "S1Q3T3",
                                            "Sonstiges/unklar",
                                        ],
                                        multiselect=True,
                                        value=[],
                                    ),
                                )
                                add("ekg_other_text", gr.Textbox(label="EKG – Sonstiges", lines=2, visible=False))

                            # Allergien (aktiviert weitere Auswahl)
                            allergies_present = add("allergies_present", gr.Checkbox(label="Allergien"))
                            with gr.Column(visible=False) as allergies_details:
                                add(
                                    "allergies_list",
                                    gr.Dropdown(
                                        label="Welche Allergien? (Mehrfachauswahl)",
                                        choices=["Pflaster", "Heparin", "Lidocain", "sonstiges"],
                                        multiselect=True,
                                        value=[],
                                    ),
                                )
                                add("allergies_other_text", gr.Textbox(label="Allergien – Sonstiges", lines=1, visible=False))
                            with gr.Row():
                                add("chd_pos", gr.Checkbox(label="Angeborener Herzfehler/Shunt bekannt oder V. a."))
                            with gr.Column(visible=False) as chd_details:
                                add("chd_type", gr.Dropdown(label="Welche Diagnose? (optional)", choices=["keine Angabe", "ASD (Vorhofseptumdefekt)", "VSD (Ventrikelseptumdefekt)", "PDA (Ductus arteriosus persistens)", "AVSD (atrioventrikulärer Septumdefekt)", "Komplexer Herzfehler / univentrikulär", "Eisenmenger-Syndrom", "Status nach Korrektur (z.B. Shunt-Verschluss)", "Sonstiges/unklar"], value="keine Angabe"))
                                add("chd_desc", gr.Textbox(label="Details (optional)", lines=2))

                            with gr.Row():
                                ph_known = add("ph_known", gr.Checkbox(label="PH-Diagnose bekannt"))
                                ph_suspected = add("ph_suspected", gr.Checkbox(label="PH-Verdachtsdiagnose"))

                            # Bekannte PH: Details (nur sichtbar, wenn „PH-Diagnose bekannt“ aktiviert ist)
                            with gr.Column(visible=False) as ph_known_details:
                                add("ph_known_dx", gr.Dropdown(
                                    label="Bekannte PH-Diagnose (Gruppe/Typ)",
                                    choices=[
                                        "keine Angabe",
                                        "PAH (Gruppe 1)",
                                        "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)",
                                        "PH bei Lungenerkrankung / Hypoxie (Gruppe 3)",
                                        "CTEPH (Gruppe 4)",
                                        "Sonstige/unklar (Gruppe 5)",
                                    ],
                                    value="keine Angabe",
                                ))
                                add("ph_known_subtype", gr.Textbox(label="Subtyp / Kontext (optional)", lines=2, placeholder="z.B. Systemsklerose, Portopulmonal, idiopathisch …"))
                                with gr.Row():
                                    add("ph_first_dx", gr.Textbox(label="Erstdiagnose (MM/JJJJ)", placeholder="z.B. 03/2021"))
                                    add("ph_reason_rhk", gr.Dropdown(
                                        label="Grund der aktuellen Untersuchung",
                                        choices=["keine Angabe", "Verlaufskontrolle", "Therapieentscheidung", "Neusymptomatik", "vor Eingriff/OP", "Sonstiges"],
                                        value="keine Angabe",
                                    ))

                                ph_med_choices = [
                                    "PDE‑5‑Hemmer",
                                    "sGC‑Stimulator (Riociguat)",
                                    "Endothelin‑Rezeptorantagonist (ERA)",
                                    "Prostazyklin‑Therapie / -Analogon",
                                    "IP‑Rezeptoragonist (z.B. Selexipag)",
                                    "Kalziumantagonist (bei Vasoreaktivität)",
                                    "Diuretikum",
                                    "Sauerstofftherapie",
                                    "Sotatercept (BMPR2/Activin-Pfad)",
                                    "Sonstiges",
                                ]
                                add("ph_current_meds", gr.Dropdown(
                                    label="Aktuelle Therapie (Mehrfachauswahl)",
                                    choices=ph_med_choices,
                                    multiselect=True,
                                    value=[],
                                ))
                                add("ph_prev_meds", gr.Dropdown(
                                    label="Frühere Therapie (optional, Mehrfachauswahl)",
                                    choices=ph_med_choices,
                                    multiselect=True,
                                    value=[],
                                ))

                                add("ph_tx_status", gr.Dropdown(
                                    label="Therapie-Verlauf seit letzter Kontrolle",
                                    choices=["keine Angabe", "unverändert", "neu begonnen", "eskaliert", "deeskaliert", "abgesetzt", "pausiert"],
                                    value="keine Angabe",
                                ))
                                add("ph_new_meds", gr.Dropdown(
                                    label="Neu begonnen / hinzugefügt (Mehrfachauswahl)",
                                    choices=ph_med_choices,
                                    multiselect=True,
                                    value=[],
                                ))
                                add("ph_stopped_meds", gr.Dropdown(
                                    label="Abgesetzt / pausiert (Mehrfachauswahl)",
                                    choices=ph_med_choices,
                                    multiselect=True,
                                    value=[],
                                ))
                                add("ph_stop_reason", gr.Dropdown(
                                    label="Grund für Absetzen/Pause (optional)",
                                    choices=["keine Angabe", "Unverträglichkeit/Nebenwirkung", "Kontraindikation", "Ineffektivität", "Patient*innenwunsch", "Andere/unklar"],
                                    value="keine Angabe",
                                ))
                                add("ph_stop_reason_text", gr.Textbox(label="Details (optional)", lines=2, placeholder="z.B. Hypotonie, Kopfschmerz, Blutung …"))

                                add("ph_interventions", gr.Dropdown(
                                    label="Bereits durchgeführte Interventionen (optional, Mehrfachauswahl)",
                                    choices=[
                                        "PEA (Pulmonalisendarteriektomie, OP)",
                                        "BPA (Ballonangioplastie, Katheter)",
                                        "Vasoreaktivitätstest",
                                        "Intensivtherapie/Parenteraltherapie",
                                        "LTX-Evaluation (Transplantations-Abklärung)",
                                        "Sonstiges",
                                    ],
                                    multiselect=True,
                                    value=[],
                                ))

                    # Card 2: Funktion/Symptome
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_klinik_symptoms = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Funktion / Symptome</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("who_fc", gr.Dropdown(label="WHO-FC", choices=["keine Angabe", "I", "II", "III", "IV"], value="keine Angabe"))
                                add("six_mwd_m", gr.Number(label="6MWD (m)"))
                                add("six_mwd_date", gr.Textbox(label="6MWD Datum", placeholder="z.B. 01/2026"))
                                add("syncope", gr.Dropdown(label="Synkope", choices=["keine Angabe", "keine", "gelegentlich", "wiederholt"], value="keine Angabe"))
                            with gr.Row():
                                add("hemoptysis", gr.Checkbox(label="Hämoptyse"))
                                add("dizziness", gr.Checkbox(label="Schwindel"))
                                add("stairs_flights", gr.Number(label="Treppen (Etagen) bis Pause", precision=0))

                    # Card 3: Labor
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_klinik_labs = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Labor</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            # Neues Raster
                            # Reihe 1: Hb | Leuko | Thrombo
                            with gr.Row():
                                add("hb_g_dl", gr.Number(label="Hb (g/dl)"))
                                add("leukocytes_g_l", gr.Number(label="Leukozyten (G/l)"))
                                add("platelets_g_l", gr.Number(label="Thrombozyten (G/l)"))

                            # Optional: Anämie-Typ (nur sichtbar, wenn Hb grenzwertig/niedrig)
                            anemia_type = add(
                                "anemia_type",
                                gr.Dropdown(
                                    label="Anämie-Typ (falls Anämie vorliegt)",
                                    choices=[
                                        "keine Angabe",
                                        "mikrozytär",
                                        "normozytär",
                                        "makrozytär",
                                        "hämolytisch",
                                        "akute Blutung/Blutverlust",
                                        "unklar",
                                    ],
                                    value="keine Angabe",
                                    visible=False,
                                ),
                            )

                            # Reihe 2: INR | PTT | Kreatinin
                            with gr.Row():
                                add("inr", gr.Number(label="INR"))
                                add("ptt_s", gr.Number(label="PTT (s)"))
                                add("creatinine_mg_dl", gr.Number(label="Kreatinin (mg/dl)"))

                            # Reihe 3: eGFR (auto) | CRP
                            with gr.Row():
                                add("egfr_ml_min_1_73", gr.Number(label="eGFR (ml/min/1,73m²)", interactive=False))
                                add("crp_mg_l", gr.Number(label="CRP (mg/l)"))
                            with gr.Row():
                                add("bnp_kind", gr.Dropdown(label="BNP/NT-proBNP", choices=["BNP", "NT-proBNP"], value="NT-proBNP"))
                                add("bnp_value", gr.Number(label="Wert (pg/ml)"))
                                add("entresto", gr.Checkbox(label="Entresto/ARNI? (BNP eingeschränkt)"))
                            with gr.Row():
                                add("congestive_organopathy", gr.Radio(label="Hinweis auf congestive Organopathie?", choices=["keine Angabe", "ja", "nein"], value="keine Angabe"))
                    
                    # Card 4: Medikation & wichtige Zusatzangaben
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_klinik_meds = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Medikation & wichtige Zusatzangaben</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            # Antikoagulation (wichtig v.a. für CTEPH-/Embolie-Logik)
                            with gr.Row():
                                anticoag_status = add(
                                    "anticoag_status",
                                    gr.Dropdown(
                                        label="Antikoagulation (Blutverdünnung)?",
                                        choices=["keine Angabe", "nein", "ja", "ja, aber pausiert", "unklar"],
                                        value="keine Angabe",
                                    ),
                                )
                                anticoag_substance = add(
                                    "anticoag_substance",
                                    gr.Dropdown(
                                        label="Substanz / Klasse (falls ja)",
                                        choices=[
                                            "keine Angabe",
                                            "DOAC (Apixaban, Rivaroxaban, Edoxaban, Dabigatran)",
                                            "VKA (Phenprocoumon/Warfarin)",
                                            "Heparin/LMWH",
                                            "Fondaparinux",
                                            "sonstiges",
                                        ],
                                        value="keine Angabe",
                                        visible=False,
                                    ),
                                )
                            with gr.Row():
                                anticoag_indication = add(
                                    "anticoag_indication",
                                    gr.Dropdown(
                                        label="Indikation (falls ja)",
                                        # NOTE: "keine Angabe" als explizite (leere) Option – verhindert Legacy-Load-Errors
                                        choices=[
                                            "keine Angabe",
                                            "Vorhofflimmern",
                                            "Venenthrombose/Lungenembolie",
                                            "CTEPH/CTEPD",
                                            "Mechanische Klappe",
                                            "Andere/unklar",
                                        ],
                                        value="keine Angabe",
                                        visible=False,
                                    ),
                                )
                                anticoag_since = add(
                                    "anticoag_since",
                                    gr.Textbox(
                                        label="seit wann (optional)",
                                        placeholder="MM/JJJJ",
                                        visible=False,
                                    ),
                                )
                            anticoag_note = add(
                                "anticoag_note",
                                gr.Textbox(
                                    label="Antikoagulation – Bemerkung (optional)",
                                    lines=2,
                                    visible=False,
                                ),
                            )

                            # Für Pre-Cath Safety: Pausierung anzeigen (nur wenn Antikoagulation = ja)
                            anticoag_paused = add(
                                "anticoag_paused",
                                gr.Checkbox(label="Antikoagulation pausiert?", visible=False),
                            )

                            # Nitrate/NO-Donor (Sicherheitsabfrage; relevant für PDE-5 / Riociguat)
                            add("on_nitrates", gr.Checkbox(
                                label="Nitrate/NO-Donor (z.B. Nitro, Isosorbid) aktuell eingenommen",
                                value=False,
                            ))

                            # PDE-5 außerhalb Gruppe 1 nur im Härtefall (strukturierte Begründung)
                            pde5_hardship = add("pde5_hardship", gr.Checkbox(
                                label="PDE-5 außerhalb Gruppe 1: Härtefall-Ausnahme dokumentiert",
                                value=False,
                            ))
                            pde5_hardship_desc = add("pde5_hardship_desc", gr.Textbox(
                                label="Härtefall-Begründung (Pflicht, wenn aktiviert)",
                                lines=2,
                                placeholder="kurz begründen (z.B. individuelle Nutzen-Risiko-Abwägung, Off-Label-Entscheidung im Zentrum)",
                                visible=False,
                            ))
                            # Lungentransplantations-Evaluation (LTX)
                            with gr.Row():
                                add(
                                    "ltx_eval",
                                    gr.Dropdown(
                                        label="LTX-Evaluation (Transplantations-Abklärung) erfolgt?",
                                        choices=["keine Angabe", "ja", "nein", "unklar"],
                                        value="keine Angabe",
                                    ),
                                )
                                add("ltx_eval_date", gr.Textbox(label="LTX-Evaluation: Datum (optional)", placeholder="MM/JJJJ"))


                # ---- Tab 2: Bildgebung & Echo/CMR (merged) ----
                with gr.TabItem("Bildgebung & Echo/CMR", id=1):
                    # Card 1: Thorax-Bildgebung
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_imaging = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Thorax-Bildgebung</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("ct_done", gr.Checkbox(label="CT Thorax/CT-Angio durchgeführt"))
                                add("vq_done", gr.Checkbox(label="V/Q durchgeführt"))
                            # CT Thorax – Befundtext nur sichtbar wenn CT durchgeführt
                            with gr.Column(visible=False) as ct_desc_col:
                                add("ct_desc", gr.Textbox(label="CT Thorax – Kurzbefund", lines=3))
                            with gr.Row():
                                add("ct_ild", gr.Checkbox(label="ILD"))
                                add("ct_emphysema", gr.Checkbox(label="Emphysem"))
                                add("ct_embolie", gr.Checkbox(label="Embolie"))
                                add("ct_mosaic", gr.Checkbox(label="Mosaikperfusion"))
                                add("ct_koronarkalk", gr.Checkbox(label="Koronarkalk"))

                            with gr.Accordion("ILD – Details (nur bei ILD)", open=False, visible=False) as acc_ild:
                                add("ild_type", gr.Textbox(label="Welche ILD?", lines=1))
                                with gr.Row():
                                    add("ild_histology", gr.Checkbox(label="Histologisch gesichert?"))
                                    add("ild_fibrosis_clinic", gr.Checkbox(label="An Fibroseambulanz angebunden?"))
                            add("ild_extent", gr.Dropdown(label="Ausmaß der ILD", choices=["", "gering", "mittel", "ausgedehnt"], value="", visible=False))

                            # ILD – Antifibrotische Therapie (nur sichtbar, wenn ILD markiert ist)
                            with gr.Column(visible=False) as ild_tx_details:
                                gr.Markdown("#### ILD – Antifibrotische Therapie")
                                antifib_status = add("antifibrotic_status", gr.Dropdown(
                                    label="Antifibrotische Therapie vorhanden?",
                                    choices=["keine Angabe", "ja", "nein", "unklar"],
                                    value="keine Angabe",
                                ))
                                with gr.Row():
                                    antifib_drug = add("antifibrotic_drug", gr.Dropdown(
                                        label="Präparat (falls ja)",
                                        choices=["keine Angabe", "Nintedanib", "Pirfenidon", "sonstiges"],
                                        value="keine Angabe",
                                        visible=False,
                                    ))
                                    antifib_since = add("antifibrotic_since", gr.Textbox(
                                        label="seit wann (optional)",
                                        placeholder="MM/JJJJ",
                                        visible=False,
                                    ))
                                antifib_note = add("antifibrotic_note", gr.Textbox(
                                    label="Bemerkung (optional)",
                                    lines=2,
                                    visible=False,
                                ))

                            with gr.Accordion("V/Q – Details (nur bei V/Q)", open=False, visible=False) as acc_vq:
                                with gr.Row():
                                    add("vq_defect", gr.Checkbox(label="V/Q pathologisch (Perfusionsdefekte)"))
                                    add("vq_desc", gr.Textbox(label="V/Q – Kurzbeschreibung", lines=2))
                    # Card 2: Echokardiographie
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_echo = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Echokardiographie</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            echo_ui = build_echo_section(add)
                    import_pdf_cur = echo_ui["import_pdf_cur"]
                    import_pdf_prev = echo_ui["import_pdf_prev"]
                    import_preview_cur_html = echo_ui["import_preview_cur_html"]
                    import_preview_prev_html = echo_ui["import_preview_prev_html"]
                    compare_echo_html = echo_ui["compare_html"]
                    details_echo_html = echo_ui["details_html"]
                    state_echo_cur = echo_ui["state_echo_cur"]
                    state_echo_prev = echo_ui["state_echo_prev"]
                    btn_echo_apply = echo_ui["btn_apply"]
                    btn_echo_clear = echo_ui["btn_clear_cur"]
                    btn_echo_clear_prev = echo_ui["btn_clear_prev"]

                    # Card 3: MRT / CMR
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_cmr = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>MRT / CMR</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("cmr_done", gr.Checkbox(label="CMR durchgeführt"))
                                add("rvef", gr.Number(label="RV-EF (%)"))
                                add("rvesvi", gr.Number(label="RVESVi (ml/m²)"))

                # ---- Tab 3: Lungenfunktion & CPET ----
                with gr.TabItem("Lungenfunktion & CPET", id=2):
                    # Card 1: Lungenfunktion
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_lufu = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Lungenfunktion & CPET</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("lufu_done", gr.Checkbox(label="Lufu durchgeführt"))
                                add("lufu_obstructive", gr.Checkbox(label="Obstruktiv"))
                                add("lufu_restrictive", gr.Checkbox(label="Restriktiv"))
                                add("lufu_diffusion", gr.Checkbox(label="Diffusionsstörung"))
                            with gr.Row():
                                add("fev1_l", gr.Number(label="FEV1 (% Soll)"))
                                add("fvc_l", gr.Number(label="FVC (% Soll)"))
                                add("dlco_sb", gr.Number(label="DLCO SB (% Soll, optional)"))
                            with gr.Row():
                                add("dlco_va", gr.Number(label="DLCO/VA (% Soll, optional)"))
                                add("residual_volume_l", gr.Number(label="Residualvolumen RV (% Soll, optional)"))
                            add("lufu_summary", gr.Textbox(label="Lufu Summary (Freitext)", lines=3))

                    # Card 2: Spiroergometrie / CPET
                    # Dedicated class to stabilize rendering (avoid flicker/pulse) during frequent wizard updates.
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card", "rhk-cpet-card"]):
                        hdr_cpet = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Spiroergometrie / CPET</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>")
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("cpet_done", gr.Checkbox(label="CPET durchgeführt"))
                                add("cpet_protocol", gr.Dropdown(label="Protokoll (optional)", choices=["Rampe", "Stufenprotokoll", "Semi supine", "Laufband", "Sonstiges"], value="Rampe"))
                                add("cpet_site", gr.Textbox(label="Ort/Setup (optional)"))

                            cpet_risk_html = gr.HTML(value="<div class='docx-muted'>Keine CPET Daten erfasst.</div>")

                            with gr.Column(visible=False) as cpet_details:
                                gr.HTML(
                                    "<div class='docx-muted'>Spiro-Logic: interaktive CPET Befundung mit Live Erklärung und Plausibilitätschecks. Die vorhandene Risikostratifizierung bleibt unverändert.</div>"
                                )

                                # Wizard modules (deterministic, no AI)
                                with gr.Tabs():
                                    # ------------------ Modul 0 ------------------
                                    with gr.TabItem("Modul 0 Qualität"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add(
                                                        "cpet_stop_reason",
                                                        gr.Dropdown(
                                                            label="Testende/Abbruchgrund",
                                                            info="Warum wurde der Test beendet. Zentrale Info für Testqualität und Sicherheit.",
                                                            choices=[
                                                                "Erschöpfung",
                                                                "Dyspnoe",
                                                                "Beine",
                                                                "Angina/Ischämie",
                                                                "Schwindel/Präsynkope/Synkope",
                                                                "Arrhythmie",
                                                                "Hypotonie",
                                                                "Desaturation",
                                                                "Technik/Maskenproblem",
                                                                "Sonstiges",
                                                            ],
                                                            value="Erschöpfung",
                                                        ),
                                                    )
                                                add("cpet_stop_reason_text", gr.Textbox(label="Details Abbruchgrund (optional)", lines=2, info="Freitext zum Abbruchgrund, zB Symptome oder Ereignisse."))
                                                with gr.Row():
                                                    add("cpet_borg_rpe", gr.Number(label="Borg RPE (0–10, optional)", info="Borg RPE Gesamtanstrengung (0 bis 10). Unterstützt die Beurteilung der Ausbelastung."))
                                                    add("cpet_borg_dyspnea", gr.Number(label="Borg Dyspnoe (0–10, optional)", info="Borg Dyspnoe (0 bis 10). Hilft Atemnot von Beinlimitierung zu trennen."))
                                                    add("cpet_borg_leg", gr.Number(label="Borg Beine (0–10, optional)", info="Borg Beine (0 bis 10). Hinweis auf periphere Limitierung."))
                                            with gr.Column(scale=1):
                                                cpet_mod0_html = gr.HTML(value="<div class='docx-muted'>Bitte Testqualität dokumentieren.</div>")

                                    # ------------------ Modul 1 ------------------
                                    with gr.TabItem("Modul 1 Antrieb"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_rer_peak", gr.Number(label="RER Peak (Qualität)", info="RER Peak (VCO2/VO2). Ab etwa 1.10 spricht es für metabolische Ausbelastung. Pitfall: Hyperventilation kann RER erhöhen."))
                                                    add("cpet_hr_peak_bpm", gr.Number(label="HF Peak (1/min)", info="Maximale Herzfrequenz während CPET. Zusammen mit RER zur Beurteilung der chronotropen Antwort."))
                                                    add("cpet_hr_pct_pred", gr.Number(label="HF Peak (% Soll, optional)", info="Herzfrequenz in Prozent des Sollwerts. Niedrig trotz metabolischer Ausbelastung spricht für chronotrope Inkompetenz oder Medikation."))

                                                # Follow up questions appear only when clinically triggered (or if already filled)
                                                with gr.Column(visible=False) as cpet_chrono_followup:
                                                    gr.HTML("<div class='docx-muted'>Nur bei Verdacht auf chronotrope Inkompetenz. Diese Angaben werden nicht automatisch überschrieben.</div>")
                                                    with gr.Row():
                                                        add("cpet_beta_blocker", gr.Checkbox(label="Betablocker oder frequenz bremsende Medikation", info="Betablocker oder andere frequenzbremsende Medikation vorhanden. Relevant für HF Interpretation."))
                                                        add("cpet_sinus_node_disorder", gr.Checkbox(label="Sinusknotenstörung oder Schrittmacher relevant", info="Hinweis auf Sinusknotendysfunktion oder Schrittmacherabhängigkeit. Relevant für HF Antwort."))
                                                    with gr.Row():
                                                        add("cpet_hyperventilation", gr.Checkbox(label="Verdacht auf Hyperventilation oder Panik", info="Ankreuzen bei Verdacht auf Hyperventilation. Kann CO2 auswaschen und RER verfälschen."))
                                                    add("cpet_chrono_comment", gr.Textbox(label="Kommentar (optional)", lines=2))

                                            with gr.Column(scale=1):
                                                cpet_mod1_html = gr.HTML(value="<div class='docx-muted'>Bitte CPET Werte eingeben.</div>")

                                    # ------------------ Modul 2 ------------------
                                    with gr.TabItem("Modul 2 Prognose"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_peak_vo2_ml_kg_min", gr.Number(label="V'O2max/kg (mL/min/kg)", info="V'O2max/kg (mL/min/kg). Prognostisch zentral. Surrogat der Pumpfunktion nach dem Fick Prinzip."))
                                                    add("cpet_peak_vo2_pct_pred", gr.Number(label="V'O2 Peak (% Soll)", info="V'O2 Peak in Prozent des Sollwerts. Erlaubt Vergleich über Alter und Geschlecht."))
                                                    add("cpet_peak_vo2_ml_min", gr.Number(label="V'O2 Peak (mL/min, optional)"))
                                                with gr.Accordion("Schwellenwerte (optional)", open=False):
                                                    with gr.Row():
                                                        add("cpet_vo2_vt1_ml_kg_min", gr.Number(label="V'O2 VT1 (mL/min/kg, optional)"))
                                                        add("cpet_vo2_vt1_ml_min", gr.Number(label="V'O2 VT1 (mL/min, optional)"))
                                                    with gr.Row():
                                                        add("cpet_vo2_vt2_ml_min", gr.Number(label="V'O2 VT2 (mL/min, optional)"))

                                            with gr.Column(scale=1):
                                                cpet_mod2_html = gr.HTML(value="")

                                    # ------------------ Modul 3 ------------------
                                    with gr.TabItem("Modul 3 Zirkulation"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_peak_o2_pulse_pct_pred", gr.Number(label="O2Puls Peak (% Soll)"))
                                                    add("cpet_peak_o2_pulse_ml", gr.Number(label="O2Puls Peak (mL, optional)", info="O2 Puls (VO2/HF). Surrogat für Schlagvolumen. Ein Plateau unter Belastung spricht für zirkulatorische Limitierung."))
                                                with gr.Row():
                                                    add("cpet_o2_pulse_pattern", gr.Dropdown(label="O2Puls Verlauf", choices=["normal", "plateau", "fallend", "unbekannt"], value="unbekannt"))
                                                    add("cpet_o2_pulse_slope", gr.Number(label="O2Puls Slope (optional)", info="Steigung des O2 Puls unter Belastung. Niedrige Steigung kann zirkulatorische Limitation unterstützen."))
                                                with gr.Row():
                                                    add("cpet_bp_sys_peak", gr.Number(label="RR syst Peak (mmHg, optional)", info="Blutdruck systolisch am Belastungspeak. In Kombination mit O2 Puls hilfreich für Afterload Interpretation."))
                                                    add("cpet_bp_dia_peak", gr.Number(label="RR diast Peak (mmHg, optional)", info="Blutdruck diastolisch am Belastungspeak. Sehr hohe Werte können Afterload Mismatch unterstützen."))

                                            with gr.Column(scale=1):
                                                cpet_mod3_html = gr.HTML(value="")

                                    # ------------------ Modul 4 ------------------
                                    with gr.TabItem("Modul 4 Ventilation"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_ve_vco2_slope", gr.Number(label="V'E/V'CO2 Slope (VECO2s)", info="V'E/V'CO2 Slope. Ventilatorische Effizienz. Erhöht bei PH, Herzinsuffizienz und Totraumventilation."))
                                                    add("cpet_ve_vco2_vt1", gr.Number(label="EqCO2 / V'E/V'CO2 VT1", info="V'E/V'CO2 an VT1. Frühe Ineffizienz kann vaskuläres Muster unterstützen."))
                                                with gr.Row():
                                                    add("cpet_petco2_rest_mmhg", gr.Number(label="PETCO2 Ruhe (mmHg, optional)", info="PETCO2 in Ruhe. Niedrige Werte können auf Totraum oder pulmonal vaskuläre Einschränkung hinweisen."))
                                                    add("cpet_petco2_peak_mmhg", gr.Number(label="PETCO2 Peak (mmHg, optional)", info="PETCO2 am Belastungspeak. Ein Abfall unter Belastung unterstützt ein pulmonal vaskuläres Muster."))
                                                    add("cpet_petco2_vt1_mmhg", gr.Number(label="PETCO2 VT1 (mmHg, optional)", info="PETCO2 zum Zeitpunkt VT1, falls ablesbar."))
                                                with gr.Row():
                                                    add("cpet_breathing_reserve_pct", gr.Number(label="Atemreserve (% , optional)", info="Atemreserve in Prozent. Niedrig spricht für ventilatorische Limitation. Idealerweise abgesichert über V'E/MVV."))
                                                    add("cpet_spo2_nadir_pct", gr.Number(label="SpO2 Nadir (% , optional)", info="Niedrigster SpO2 Wert während CPET. Relevante Desaturation muss differenzialdiagnostisch eingeordnet werden."))
                                                with gr.Row():
                                                    add("cpet_vo2_wr_slope_ml_min_w", gr.Number(label="VO2Ws (ΔV'O2/ΔW) (mL/min/W, optional)", info="VO2 pro Watt. Erwartet etwa 8 bis 11 mL/min/W. Niedrig spricht für zirkulatorische oder periphere Limitation."))

                                            with gr.Column(scale=1):
                                                cpet_mod4_html = gr.HTML(value="")

                                    # ------------------ Modul 5 Mechanik ------------------
                                    with gr.TabItem("Modul 5 Mechanik"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                gr.HTML("<div class='docx-muted'>Optional, aber sehr hilfreich zur objektiven Beurteilung einer ventilatorischen Limitation (V'E/MVV).</div>")
                                                with gr.Row():
                                                    add("cpet_ve_peak_l_min", gr.Number(label="V'E Peak (L/min, optional)", info="Peak Ventilation V'E in L/min."))
                                                    add("cpet_mvv_l_min", gr.Number(label="MVV (L/min, optional)", info="MVV (maximale willkürliche Ventilation). Gemessen oder geschätzt. Basis für V'E/MVV."))
                                                    add(
                                                        "cpet_mvv_source",
                                                        gr.Dropdown(
                                                            label="MVV Quelle (optional)",
                                                            info="Quelle der MVV Angabe, gemessen oder geschätzt (zB FEV1 mal 35).",
                                                            choices=["gemessen", "geschätzt", "FEV1*35", "FEV1*40", "unklar"],
                                                            value="geschätzt",
                                                        ),
                                                    )
                                            with gr.Column(scale=1):
                                                cpet_mod5_html = gr.HTML(value="")

                                    # ------------------ Modul 6 Gasaustausch ------------------
                                    with gr.TabItem("Modul 6 SpO2/O2"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_spo2_rest_pct", gr.Number(label="SpO2 Ruhe (% , optional)", info="SpO2 in Ruhe. Wichtig für Ausgangsstatus."))
                                                    add("cpet_spo2_peak_pct", gr.Number(label="SpO2 Peak (% , optional)", info="SpO2 am Belastungspeak."))
                                                with gr.Row():
                                                    add("cpet_spo2_nadir_pct", gr.Number(label="SpO2 Nadir (% , optional)", info="Niedrigster SpO2 Wert während CPET. Relevante Desaturation muss differenzialdiagnostisch eingeordnet werden."))
                                                    add("cpet_o2_supp_l_min", gr.Number(label="O2 Unterstützung (L/min, optional)", info="Sauerstoffgabe während Test (Liter pro Minute). Dokumentationspflicht für Interpretation."))
                                            with gr.Column(scale=1):
                                                cpet_mod6_html = gr.HTML(value="")

                                    # ------------------ Modul 7 Sicherheit ------------------
                                    with gr.TabItem("Modul 7 Sicherheit"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                with gr.Row():
                                                    add("cpet_bp_sys_rest", gr.Number(label="RR syst Ruhe (mmHg, optional)", info="Ruhe Blutdruck systolisch vor Belastung."))
                                                    add("cpet_bp_dia_rest", gr.Number(label="RR diast Ruhe (mmHg, optional)", info="Ruhe Blutdruck diastolisch vor Belastung."))
                                                gr.HTML("<div class='docx-muted'>Bei Symptomen oder EKG Auffälligkeiten wird der Test als sicherheitslimitiert dokumentiert.</div>")
                                                with gr.Row():
                                                    add("cpet_angina", gr.Checkbox(label="Angina/Thoraxschmerz", info="Angina unter Belastung dokumentiert."))
                                                    add("cpet_dizziness", gr.Checkbox(label="Schwindel/Präsynkope", info="Schwindel oder Präsynkope unter Belastung."))
                                                    add("cpet_syncope", gr.Checkbox(label="Synkope", info="Synkope unter Belastung. Relevanter Safety Befund."))
                                                    add("cpet_palpitations", gr.Checkbox(label="Palpitationen", info="Palpitationen unter Belastung."))
                                                with gr.Row():
                                                    add("cpet_arrhythmia", gr.Checkbox(label="Arrhythmie", info="Arrhythmie unter Belastung beobachtet."))
                                                    add(
                                                        "cpet_st_changes",
                                                        gr.Dropdown(
                                                            label="ST/T Veränderungen (optional)",
                                                            info="ST T Veränderungen unter Belastung. Kurz beschreiben, falls vorhanden.",
                                                            choices=["keine", "ST Senkung", "ST Hebung", "nicht beurteilbar", "Sonstiges"],
                                                            value="keine",
                                                        ),
                                                    )
                                                add("cpet_arrhythmia_text", gr.Textbox(label="Arrhythmie Details (optional)", lines=2, info="Kurze Beschreibung Rhythmus, zB VES, SVT, AF."))
                                            with gr.Column(scale=1):
                                                cpet_mod7_html = gr.HTML(value="")

                                    # ------------------ Modul 5 ------------------
                                    with gr.TabItem("9 Felder Grafik"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                add("cpet_9panel_available", gr.Checkbox(label="9 Felder Grafik beurteilt", info="Aktivieren, wenn die 9 Felder Grafik beurteilt wurde. Dann werden Kurvenmuster strukturiert dokumentiert."))

                                                with gr.Column(visible=False) as cpet_9panel_details:
                                                    gr.HTML("<div class='docx-muted'>Kurvenmuster werden als Befundentscheidungen dokumentiert. Diese Angaben werden nicht automatisch überschrieben.</div>")
                                                    with gr.Row():
                                                        add(
                                                            "cpet_9panel_vt1_identified",
                                                            gr.Dropdown(
                                                                label="VT1 identifiziert",
                                                                info="VT1 in der 9 Felder Grafik erkennbar. VT1 entspricht der ersten ventilatorischen Schwelle.",
                                                                choices=["ja", "unklar", "nein"],
                                                                value="unklar",
                                                            ),
                                                        )
                                                        add(
                                                            "cpet_9panel_vt1_method",
                                                            gr.Dropdown(
                                                                label="VT1 Methode (optional)",
                                                                info="Methode zur Bestimmung von VT1, zB V Slope, ventilatorische Äquivalente oder PETO2.",
                                                                choices=["V Slope", "VE VO2 Knick", "PETCO2 Verlauf", "Sonstiges"],
                                                                value="V Slope",
                                                            ),
                                                        )
                                                    with gr.Row():
                                                        add(
                                                            "cpet_9panel_rcp_identified",
                                                            gr.Dropdown(
                                                                label="RCP identifiziert (optional)",
                                                                info="RCP bzw VT2 erkennbar. Marker der ventilatorischen Kompensation.",
                                                                choices=["ja", "unklar", "nein"],
                                                                value="unklar",
                                                            ),
                                                        )
                                                        add(
                                                            "cpet_9panel_eov",
                                                            gr.Checkbox(label="EOV vorhanden (oszillierende Ventilation)"),
                                                            info="Exercise oscillatory ventilation. Prognostisch ungünstiges oszillierendes Ventilationsmuster.",
                                                        )
                                                    with gr.Row():
                                                        add(
                                                            "cpet_9panel_flowvol_limit",
                                                            gr.Dropdown(
                                                                label="Flow Volume Loop Limitation",
                                                                info="Annäherung der Atemschleife an die maximale Fluss Volumen Kurve. Hinweis auf mechanische Limitation oder dynamische Hyperinflation.",
                                                                choices=["nein", "unklar", "ja"],
                                                                value="unklar",
                                                            ),
                                                        )
                                                        add(
                                                            "cpet_9panel_vo2wr_pattern",
                                                            gr.Dropdown(
                                                                label="V'O2 zu Leistung Kurvenmuster",
                                                                info="V'O2 zu Leistung Kurvenmuster. Erwartet linear. Abflachung oder Plateau spricht für zirkulatorische Begrenzung.",
                                                                choices=["linear", "unklar", "flach", "plateau"],
                                                                value="unklar",
                                                            ),
                                                        )
                                                    with gr.Row():
                                                        add(
                                                            "cpet_9panel_veeq_pattern",
                                                            gr.Dropdown(
                                                                label="Ventilatorische Äquivalente Muster",
                                                                info="Verlauf der ventilatorischen Äquivalente (V'E/V'O2, V'E/V'CO2). Physiologisch sinken sie bis VT1 und steigen danach.",
                                                                choices=["normal", "unklar", "frueh", "kein"],
                                                                value="unklar",
                                                            ),
                                                        )
                                                    add("cpet_9panel_comment", gr.Textbox(label="9 Felder Kommentar (optional)", lines=2, info="Freitext Kommentar zur 9 Felder Grafik."))

                                            with gr.Column(scale=1):
                                                cpet_mod9_html = gr.HTML(value="<div class='docx-muted'>Aktiviere 9 Felder Grafik, um Kurvenmuster zu dokumentieren.</div>")

                                    # ------------------ Modul 8 Limitation ------------------
                                    with gr.TabItem("Modul 8 Limitation"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                gr.HTML("<div class='docx-muted'>Optionaler Override: Wenn du klinisch einen anderen Limitationstyp festlegst, dokumentiere kurz die Begründung. Spiro-Logic überschreibt keine manuellen Angaben.</div>")
                                                with gr.Row():
                                                    add(
                                                        "cpet_limitation_override",
                                                        gr.Dropdown(
                                                            label="Limitationstyp Override (optional)",
                                                            choices=[
                                                                "",
                                                                "kardial/zirkulatorisch",
                                                                "pulmonal mechanisch",
                                                                "pulmonal vaskulär (PH)",
                                                                "peripher/deconditioning",
                                                                "gemischt",
                                                                "nicht beurteilbar",
                                                                "sicherheitslimitiert",
                                                            ],
                                                            value="",
                                                        ),
                                                    )
                                                add("cpet_limitation_override_text", gr.Textbox(label="Begründung Override (nur falls gesetzt)", lines=2))
                                                add("cpet_next_steps_manual", gr.Textbox(label="Zusätzliche Next Steps (ärztlich, optional)", lines=3))
                                            with gr.Column(scale=1):
                                                cpet_modfinal_html = gr.HTML(value="")

                                    # ------------------ Gesamtfazit ------------------
                                    with gr.TabItem("Gesamtfazit"):
                                        cpet_overall_html = gr.HTML(value="")
                                        cpet_spiro_report = gr.Textbox(
                                            label="Automatischer CPET Befundtext (Spiro-Logic)",
                                            lines=10,
                                            interactive=False,
                                        )
                                        cpet_spiro_status = gr.HTML(value="")
                                        with gr.Row():
                                            add("cpet_spiro_in_report", gr.Checkbox(label="Spiro-Logic Interpretation in Arztbericht aufnehmen", value=False))
                                            btn_cpet_adopt = gr.Button("Als CPET Kommentar übernehmen (nur wenn leer)")
                                        add("cpet_summary", gr.Textbox(label="CPET Kommentar (Freitext)", lines=3))

                # ---- Tab 4: RHK ----
                with gr.TabItem("RHK", id=3):
                    rhk_ui = build_rhk_tab(add)
                    import_status_html = rhk_ui["import_status_html"]
                    btn_wipe_docx_current = rhk_ui.get("btn_wipe_docx_current")
                    btn_wipe_docx_prev = rhk_ui.get("btn_wipe_docx_prev")
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
                with gr.TabItem("Weitere Befunde", id=4):
                    # Blutgase / LTOT
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_bloodgas = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Blutgase / LTOT</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>"
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
                            "<div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>"
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
                            "<div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>"
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

                    # Abdomen / Leber
                    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
                        hdr_other_abd = gr.HTML(
                            "<div class='rhk-sec-head'><div class='rhk-sec-title'>Abdomen / Leber</div>"
                            "<div class='rhk-sec-progress is-optional'><span class='rhk-sec-count'>optional</span>"
                            "<div class='rhk-sec-bar'><div style='width:0%'></div></div></div></div>"
                        )
                        with gr.Column(elem_classes=["rhk-sec-body"]):
                            with gr.Row():
                                add("abd_sono_done", gr.Checkbox(label="Abdomen-Sono durchgeführt"))
                                abd_desc = add("abd_sono_desc", gr.Textbox(label="Besondere Befunde?", lines=2, visible=False))

                # ---- Tab 6: Procedere & Module ----
                with gr.TabItem("Procedere & Module", id=5):
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

            with gr.Column(scale=5):
                dashboard = gr.HTML(value=build_dashboard_html(None))

                # Copy/paste helpers (plain text, no formatting chaos)
                with gr.Row(elem_id="rhk_copy_row"):
                    btn_copy_doc = gr.Button("Arztbericht kopieren", variant="secondary", elem_id="btn_copy_doc")
                    # Use a real download button to avoid the large gr.File placeholder area.
                    btn_download_doc = gr.DownloadButton("DOCX", variant="secondary", elem_id="btn_download_doc")
                    btn_copy_pat = gr.Button("Patient*innenbrief komplett kopieren", variant="secondary", elem_id="btn_copy_pat")
                    btn_copy_rhk = gr.Button("nur RHK Abschnitt kopieren", variant="secondary", elem_id="btn_copy_rhk")
                copy_feedback = gr.Markdown("", elem_id="rhk_copy_feedback")

                # Klinik-Workaround: serverseitiges Speichern in einen frei wählbaren Ordner.
                # In Cloud/Render ist das NICHT "lokal" auf dem User-PC, daher dort ausgeblendet.
                def _is_cloud_env() -> bool:
                    import os
                    return bool(os.environ.get("PORT")) or bool(os.environ.get("RENDER")) or bool(os.environ.get("K_SERVICE"))

                with gr.Accordion(
                    "DOCX speichern (nur lokale Installation)",
                    open=False,
                    visible=(not _is_cloud_env()),
                    elem_id="docx_save_acc",
                ):
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
                    "Hinweis: In der Online-Version ist nur der DOCX-Download verfügbar.",
                    visible=_is_cloud_env(),
                    elem_id="docx_cloud_hint",
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

                with gr.Tabs(elem_id="rhk_output_tabs"):
                    with gr.TabItem("Arztbericht"):
                        out_doc = gr.Markdown(elem_id="out_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Arztbefund (extended)"):
                        out_echo_doc = gr.Markdown(elem_id="out_echo_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Patientenbericht"):
                        out_pat = gr.Markdown(elem_id="out_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Patientenbericht"):
                        out_echo_pat = gr.Markdown(elem_id="out_echo_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Intern"):
                        out_int = gr.Markdown(elem_id="out_int", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Summary (JSON)"):
                        out_summary_json = gr.Code(language="json", elem_id="out_summary_json", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Debug"):
                        out_json = gr.Code(language="json", elem_id="out_json", elem_classes=["rhk-scrollbox"])

        # Buttons bottom (mirrored)
        with gr.Row():
            btn_example_bottom = gr.Button("Beispiel laden (random)", variant="secondary", elem_id="btn_example_bottom")
            btn_generate_bottom = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_bottom")
            btn_clear_bottom = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_bottom")
            save_btn_bottom = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_bottom")
            load_btn_bottom = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_bottom")
            docx_btn_bottom = gr.UploadButton("RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_bottom")

        file_out = gr.File(label="Download: gespeicherter Fall (.json)", visible=False)
        file_summary_out = gr.File(label="Download: Summary (.json)", visible=False)

        # Single "dirty" ping from the browser (debounced). Avoids binding change-handlers to dozens of fields.
        dirty_ping = gr.Textbox(value="", visible=False, elem_id="rhk_dirty_ping")

        state_case = gr.State(value=None)
        state_case_filename = gr.State(value="")  # remembered loaded case filename
        state_pmods_selected = gr.State(value={"lvl1": [], "lvl2": [], "lvl3": []})
        state_flags = gr.State(value={"dirty": False, "saved_at": None, "has_report": False, "report_stale": False})

        # DOCX import cache (current + previous catheter). Must exist even if user never imports.
        # Stored as full parsed payload dict (or None).
        state_docx_cur = gr.State(value=None)
        state_docx_prev = gr.State(value=None)

        # Echo PDF Import bindings (Textlayer only)
        try:
            bind_echo_import(echo_ui, field_components=field_components)
        except Exception:
            # UI must stay alive even if import bindings fail
            pass


        # --- Conditional visibility bindings ---
        def _toggle_desc_text(flag: bool):
            return gr.update(visible=bool(flag))

        def _toggle_ltot(flag: bool):
            return gr.update(visible=bool(flag))

        def _update_egfr(creatinine, age, sex):
            val = compute_egfr(creatinine, age, sex)
            if val is None:
                return gr.update(value=None)
            try:
                return gr.update(value=round(float(val)))
            except Exception:
                return gr.update(value=None)

        def _update_pre_cath(consent_done, access_route, inr, ptt_s, platelets, anticoag_status, anticoag_paused, crp, creatinine, age, sex,
                             allergies_present, allergies_list, allergies_other_text, lsb_present, lsb_reason):
            egfr_val = compute_egfr(creatinine, age, sex)
            try:
                egfr_val = float(egfr_val) if egfr_val is not None else None
            except Exception:
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
            except Exception:
                # Fallback: some Gradio versions/components do not expose .blur
                _bind_change(comp, fn, inputs=inputs, outputs=outputs)

        # ------------------------------------------------------------------
        # Section header progress (non-sticky, Apple-like)
        # ------------------------------------------------------------------

        def _is_filled(v: Any) -> bool:
            """Heuristic: count 'meaningfully filled' fields for UI progress."""
            if v is None:
                return False
            # Booleans: only count when explicitly checked (True)
            if isinstance(v, bool):
                return v
            # Numbers
            try:
                import math
                if isinstance(v, (int, float)):
                    return not math.isnan(float(v))
            except Exception:
                pass
            # Multi-select
            if isinstance(v, (list, tuple, set)):
                return len([x for x in v if str(x).strip()]) > 0
            s = str(v).strip()
            if not s:
                return False
            # Common 'empty' sentinels
            if s.lower() in ("keine angabe", "unklar", "—", "-"):
                return False
            return True

        def _render_section_header(title: str, filled: int, total: int) -> str:
            total = int(total) if total else 0
            filled = int(filled) if filled else 0
            if total <= 0:
                pct = 0
                cls = "rhk-sec-progress is-optional"
                count_txt = "optional"
            else:
                pct = max(0, min(100, int(round(100.0 * filled / max(1, total)))))
                cls = "rhk-sec-progress"
                # Anzeige nur noch mit einer Dezimalstelle (UI-Konsistenz)
                count_txt = f"{float(filled):.1f}/{float(total):.1f}".replace(".", ",")
            return (
                "<div class='rhk-sec-head'>"
                f"<div class='rhk-sec-title'>{title}</div>"
                f"<div class='{cls}' title='Ausfüllgrad (Schätzwert)'>"
                f"<span class='rhk-sec-count'>{count_txt}</span>"
                f"<div class='rhk-sec-bar'><div style='width:{pct}%'></div></div>"
                "</div></div>"
            )

        def _bind_section_progress(header_comp, title: str, comps: List[gr.components.Component], calc_fn):
            """Bind progress refresh to all comps in a section (no loading flicker)."""
            # Performance: section progress is a classic "laggy typing" source because it binds events to
            # dozens of text fields and triggers server roundtrips on every keystroke.
            # Default is OFF. Enable explicitly via env var if needed.
            if os.getenv("RHK_ENABLE_SECTION_PROGRESS", "0").strip() != "1":
                return
            if not comps:
                return

            def _cb(*vals):
                filled, total = calc_fn(*vals)
                return _render_section_header(title, filled, total)

            for c in comps:
                try:
                    cname = (c.__class__.__name__ or "").lower()
                    # Text / numeric inputs: update on blur to avoid per-keystroke requests
                    if cname in ("textbox", "number") and hasattr(c, "blur"):
                        _bind_blur(c, _cb, inputs=comps, outputs=[header_comp])
                    else:
                        _bind_change(c, _cb, inputs=comps, outputs=[header_comp])
                except Exception:
                    pass

        # One-shot sync for visibility + computed fields after programmatic UI loads
        def _sync_post_load(ct_done_v, ct_ild_v, vq_done_v, creatinine, age, sex, allergies_present_v, allergies_list_v):
            # Allergie-Details sichtbar wenn Checkbox aktiv ODER wenn bereits Einträge vorhanden sind
            al_list = allergies_list_v if isinstance(allergies_list_v, list) else ([] if allergies_list_v in (None, "") else [str(allergies_list_v)])
            show_allergies = bool(allergies_present_v) or bool(al_list)
            show_other = any(str(x).strip().lower() == "sonstiges" for x in al_list)
            return (
                gr.update(visible=bool(ct_done_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(ct_ild_v)),
                gr.update(visible=bool(vq_done_v)),
                _update_egfr(creatinine, age, sex),
                gr.update(visible=show_allergies),
                gr.update(visible=show_other),
            )

        def _render_cpet_risk_html(cpet_done_v,
                                  peak_vo2, peak_vo2_pct,
                                  vevco2_slope, petco2_vt1, vevco2_vt1,
                                  o2pulse_pct, vo2_wr_slope, vo2_vt1,
                                  spo2_nadir, rer_peak, hr_peak,
                                  o2_pulse_pattern):
            if not bool(cpet_done_v):
                return "<div class='docx-muted'>Keine CPET Daten erfasst.</div>"

            ui_tmp = {
                "cpet_done": True,
                "cpet_peak_vo2_ml_kg_min": peak_vo2,
                "cpet_peak_vo2_pct_pred": peak_vo2_pct,
                "cpet_ve_vco2_slope": vevco2_slope,
                "cpet_petco2_vt1_mmhg": petco2_vt1,
                "cpet_ve_vco2_vt1": vevco2_vt1,
                "cpet_peak_o2_pulse_pct_pred": o2pulse_pct,
                "cpet_vo2_wr_slope_ml_min_w": vo2_wr_slope,
                "cpet_vo2_vt1_ml_kg_min": vo2_vt1,
                "cpet_spo2_nadir_pct": spo2_nadir,
                "cpet_rer_peak": rer_peak,
                "cpet_hr_peak_bpm": hr_peak,
                "cpet_o2_pulse_pattern": o2_pulse_pattern,
            }

            res = calc_cpet_scores(ui_tmp)

            # chips
            chips: List[str] = []

            def _chip(label: str, value: str, level: Optional[str] = None) -> str:
                cls = "rhk-schip"
                if level == "good":
                    cls += " rhk-schip--good"
                elif level == "warn":
                    cls += " rhk-schip--warn"
                elif level == "bad":
                    cls += " rhk-schip--bad"
                else:
                    cls += " rhk-schip--info"
                return f"<span class='{cls}'><b>{label}</b>: {value}</span>"

            # Primary risk (ESC/ERS 3-strata)
            if res and res.esc_ers_3_strata:
                lev = "good" if res.esc_ers_3_strata == "low" else "warn" if res.esc_ers_3_strata == "intermediate" else "bad"
                chips.append(_chip("ESC/ERS CPET Risiko", res.esc_ers_3_strata, lev))
            else:
                chips.append(_chip("ESC/ERS CPET Risiko", "nicht berechenbar", "warn"))

            # CPET score (4 strata)
            if res and res.cpet_score_4_strata:
                lev = "good" if res.cpet_score_4_strata == "low" else "warn" if res.cpet_score_4_strata in ("intermediate-low", "intermediate-high") else "bad"
                chips.append(_chip("CPET Score", res.cpet_score_4_strata, lev))

            # Effort
            if res and res.effort_ok is not None:
                chips.append(_chip("Effort", "ausreichend" if res.effort_ok else "limitiert", "good" if res.effort_ok else "warn"))

            # Key values quick view
            if _safe_float(peak_vo2) is not None:
                chips.append(_chip("Peak VO2", f"{_safe_float(peak_vo2):.1f} ml/min/kg", "info"))
            if _safe_float(vevco2_slope) is not None:
                chips.append(_chip("VE/VCO2 slope", f"{_safe_float(vevco2_slope):.1f}", "info"))
            if _safe_float(petco2_vt1) is not None:
                chips.append(_chip("PETCO2@VT1", f"{_safe_float(petco2_vt1):.0f} mmHg", "info"))

            notes_html = ""
            if res and res.notes:
                notes = " ".join([f"• {html.escape(str(n))}" for n in res.notes])
                notes_html = f"<span class='rhk-schip rhk-schip--hint'>{notes}</span>"

            return "<div class='rhk-summarybar'>" + "".join(chips) + notes_html + "</div>"

        def _sync_post_load_cpet(cpet_done_v,
                                 peak_vo2, peak_vo2_pct,
                                 vevco2_slope, petco2_vt1, vevco2_vt1,
                                 o2pulse_pct, vo2_wr_slope, vo2_vt1,
                                 spo2_nadir, rer_peak, hr_peak,
                                 o2_pulse_pattern):
            return (
                gr.update(visible=bool(cpet_done_v)),
                _render_cpet_risk_html(cpet_done_v, peak_vo2, peak_vo2_pct, vevco2_slope, petco2_vt1, vevco2_vt1, o2pulse_pct, vo2_wr_slope, vo2_vt1, spo2_nadir, rer_peak, hr_peak, o2_pulse_pattern),
            )

        # Spiro-Logic wizard: live education + pattern recognition (deterministic)
        def _sync_post_load_cpet_wizard(
            cpet_done_v,
            stop_reason, stop_reason_text,
            borg_rpe, borg_dysp, borg_leg,
            rer_peak, hr_peak, hr_pct,
            peak_vo2, peak_vo2_pct,
            o2p_ml, o2p_pattern, o2p_slope,
            bp_sys_rest, bp_dia_rest,
            bp_sys, bp_dia,
            vevco2_slope, pet_rest, pet_peak, pet_vt1,
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
        ):
            ui_tmp = {
                "cpet_done": bool(cpet_done_v),
                "cpet_stop_reason": stop_reason,
                "cpet_stop_reason_text": stop_reason_text,
                "cpet_borg_rpe": borg_rpe,
                "cpet_borg_dyspnea": borg_dysp,
                "cpet_borg_leg": borg_leg,
                "cpet_rer_peak": rer_peak,
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
            out = _get_spiro_logic().build_wizard_outputs(ui_tmp)

            # Follow up block should remain visible if triggered OR already filled
            show_follow = bool(out.get("need_chrono_followups")) or bool(beta_blocker) or bool(sinus_node) or bool(hypervent) or bool((chrono_comment or "").strip())

            # Report text for copy use
            report_text = out.get("report_text") or ""

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
                out.get("overall_html") or "",
                report_text,
                gr.update(visible=show_follow),
            )

        def _adopt_spiro_report_to_summary(current_summary: str, spiro_report_text: str):
            current_summary = (current_summary or "").strip()
            spiro_report_text = (spiro_report_text or "").strip()
            if not spiro_report_text:
                return (current_summary, "<div class='docx-muted'>Kein Spiro-Logic Text vorhanden.</div>")
            if current_summary:
                return (current_summary, "<div class='docx-muted'>CPET Kommentar ist bereits gefüllt. Übernahme wird zum Schutz vor Überschreiben blockiert.</div>")
            return (spiro_report_text, "<div class='docx-muted'>Spiro-Logic Text als CPET Kommentar übernommen.</div>")

        _bind_change(field_components["virology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["virology_pos"]], outputs=[viro_items, viro_desc])
        _bind_change(field_components["immunology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["immunology_pos"]], outputs=[immun_items, immun_desc])
        _bind_change(field_components["mutation_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["mutation_pos"]], outputs=[mut_items, mut_desc])
        _bind_change(field_components["chd_pos"], lambda x: gr.update(visible=bool(x)), inputs=[field_components["chd_pos"]], outputs=[chd_details])
        _bind_change(field_components["abd_sono_done"], lambda x: _toggle_desc_text(x), inputs=[field_components["abd_sono_done"]], outputs=[abd_desc])
        _bind_change(field_components["ltot"], lambda x: _toggle_ltot(x), inputs=[field_components["ltot"]], outputs=[ltot_flow])

        # Thorax/ILD/VQ – intelligente Sichtbarkeit
        _bind_change(field_components["ct_done"], lambda x: gr.update(visible=bool(x)), inputs=[field_components["ct_done"]], outputs=[ct_desc_col])
        _bind_change(
            field_components["ct_ild"],
            lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x)), gr.update(visible=bool(x))),
            inputs=[field_components["ct_ild"]],
            outputs=[acc_ild, field_components["ild_extent"], ild_tx_details],
        )
        _bind_change(field_components["vq_done"], lambda x: gr.update(visible=bool(x)), inputs=[field_components["vq_done"]], outputs=[acc_vq])

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
                "cpet_peak_vo2_ml_kg_min", "cpet_peak_vo2_pct_pred",
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
        except Exception:
            pass

        # CPET Spiro-Logic Wizard: live education blocks + follow up visibility
        try:
            _cpet_wiz_inputs = [
                field_components["cpet_done"],
                field_components["cpet_stop_reason"],
                field_components["cpet_stop_reason_text"],
                field_components["cpet_borg_rpe"],
                field_components["cpet_borg_dyspnea"],
                field_components["cpet_borg_leg"],
                field_components["cpet_rer_peak"],
                field_components["cpet_hr_peak_bpm"],
                field_components["cpet_hr_pct_pred"],
                field_components["cpet_peak_vo2_ml_kg_min"],
                field_components["cpet_peak_vo2_pct_pred"],
                field_components["cpet_peak_o2_pulse_ml"],
                field_components["cpet_o2_pulse_pattern"],
                field_components["cpet_o2_pulse_slope"],
                field_components["cpet_bp_sys_rest"],
                field_components["cpet_bp_dia_rest"],
                field_components["cpet_bp_sys_peak"],
                field_components["cpet_bp_dia_peak"],
                field_components["cpet_ve_vco2_slope"],
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

            for _k in (
                "cpet_done",
                "cpet_stop_reason", "cpet_stop_reason_text",
                "cpet_borg_rpe", "cpet_borg_dyspnea", "cpet_borg_leg",
                "cpet_rer_peak", "cpet_hr_peak_bpm", "cpet_hr_pct_pred",
                "cpet_peak_vo2_ml_kg_min", "cpet_peak_vo2_pct_pred",
                "cpet_peak_o2_pulse_ml", "cpet_o2_pulse_pattern", "cpet_o2_pulse_slope",
                "cpet_bp_sys_rest", "cpet_bp_dia_rest", "cpet_bp_sys_peak", "cpet_bp_dia_peak",
                "cpet_ve_vco2_slope", "cpet_petco2_rest_mmhg", "cpet_petco2_peak_mmhg", "cpet_petco2_vt1_mmhg",
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
                    _bind_change(
                        field_components[_k],
                        _sync_post_load_cpet_wizard,
                        inputs=_cpet_wiz_inputs,
                        outputs=[cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_spiro_report, cpet_chrono_followup],
                    )
        except Exception:
            pass

        # Adopt generated Spiro-Logic text into manual CPET comment (only if empty)
        try:
            btn_cpet_adopt.click(
                _adopt_spiro_report_to_summary,
                inputs=[field_components["cpet_summary"], cpet_spiro_report],
                outputs=[field_components["cpet_summary"], cpet_spiro_status],
            )
        except Exception:
            pass

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
        except Exception:
            pass



        # Antikoagulation: Pausierung-Checkbox sinnvoll steuern
        def _toggle_anticoag_paused(status, current_val):
            s = (status or "").strip().lower()
            if s == "ja":
                # show checkbox and keep current value (do not reset on load)
                return gr.update(visible=True, value=bool(current_val))
            if "paus" in s:
                # status already implies pause -> hide checkbox, set True
                return gr.update(visible=False, value=True)
            # no/unknown -> hide, reset
            return gr.update(visible=False, value=False)

        try:
            _bind_change(
                field_components["anticoag_status"],
                _toggle_anticoag_paused,
                inputs=[field_components["anticoag_status"], field_components["anticoag_paused"]],
                outputs=[field_components["anticoag_paused"]],
            )
        except Exception:
            pass

                # Allergien: Mehrfachauswahl erst aktivieren wenn Checkbox gesetzt ist
        def _toggle_allergies(present: bool):
            return gr.update(visible=bool(present))

        def _toggle_allergies_other(sel):
            if not isinstance(sel, list):
                sel = [] if sel in (None, "") else [str(sel)]
            show_other = any(str(x).strip().lower() == "sonstiges" for x in sel)
            return gr.update(visible=bool(show_other))

        # EKG: Details nur wenn EKG vorhanden; "Sonstiges" Textfeld nur wenn gewählt
        # LSB: Begründung sichtbar nur wenn Checkbox aktiv
        def _toggle_lsb_reason(flag):
            return gr.update(visible=bool(flag))

        def _toggle_ekg(ekg_present_v):
            return gr.update(visible=bool(ekg_present_v))

        def _toggle_ekg_other(ekg_signs):
            if not isinstance(ekg_signs, list):
                ekg_signs = [] if ekg_signs in (None, "") else [str(ekg_signs)]
            show = any(str(x).strip().lower().startswith("sonst") for x in ekg_signs)
            return gr.update(visible=bool(show))

        # CPET 9 Felder Grafik: Details nur wenn aktiv
        def _toggle_cpet_9panel(flag):
            return gr.update(visible=bool(flag))

        # PDE-5 Härtefall: Begründung sichtbar nur wenn Checkbox aktiv
        def _toggle_pde5_hardship_desc(flag):
            return gr.update(visible=bool(flag))

        try:
            _bind_change(field_components["allergies_present"], _toggle_allergies, inputs=[field_components["allergies_present"]], outputs=[allergies_details])
            _bind_change(field_components["allergies_list"], _toggle_allergies_other, inputs=[field_components["allergies_list"]], outputs=[field_components["allergies_other_text"]])
            _bind_change(field_components["ekg_present"], _toggle_ekg, inputs=[field_components["ekg_present"]], outputs=[ekg_details])
            _bind_change(field_components["lsb_present"], _toggle_lsb_reason, inputs=[field_components["lsb_present"]], outputs=[field_components["lsb_reason"]])
            _bind_change(field_components["cpet_9panel_available"], _toggle_cpet_9panel, inputs=[field_components["cpet_9panel_available"]], outputs=[cpet_9panel_details])
            _bind_change(field_components["ekg_rhs_signs"], _toggle_ekg_other, inputs=[field_components["ekg_rhs_signs"]], outputs=[field_components["ekg_other_text"]])
            _bind_change(field_components["pde5_hardship"], _toggle_pde5_hardship_desc, inputs=[field_components["pde5_hardship"]], outputs=[field_components["pde5_hardship_desc"]])
        except Exception:
            pass

        # Anemia type show/hide when Hb or sex changes
        _bind_change(field_components["hb_g_dl"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        _bind_change(field_components["sex"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        # Bekannte PH: Details + Exklusivität in EINEM Callback (reduziert Re-Renders / Loading-Fades)
        def _ph_known_changed(known: bool):
            k = bool(known)
            # Details sichtbar nur bei "PH-Diagnose bekannt".
            # Wenn Diagnose bekannt: Verdachtsdiagnose automatisch aus.
            return (
                gr.update(visible=k),
                False if k else gr.update(),
            )

        def _ph_suspected_changed(suspected: bool):
            s = bool(suspected)
            # Wenn Verdacht gesetzt: Diagnose bekannt automatisch aus und Details ausblenden.
            if s:
                return (
                    False,
                    gr.update(visible=False),
                )
            return (
                gr.update(),
                gr.update(),
            )

        _bind_change(
            field_components["ph_known"],
            _ph_known_changed,
            inputs=[field_components["ph_known"]],
            outputs=[ph_known_details, field_components["ph_suspected"]],
        )
        _bind_change(
            field_components["ph_suspected"],
            _ph_suspected_changed,
            inputs=[field_components["ph_suspected"]],
            outputs=[field_components["ph_known"], ph_known_details],
        )

        # Antikoagulation: Detailfelder nur bei "ja"
        def _toggle_anticoag(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        _bind_change(field_components["anticoag_status"], _toggle_anticoag, inputs=[field_components["anticoag_status"]], outputs=[anticoag_substance, anticoag_indication, anticoag_since, anticoag_note, anticoag_paused])

        # ILD – Antifibrotika: Detailfelder nur bei "ja"

        def _toggle_antifib(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        _bind_change(field_components["antifibrotic_status"], _toggle_antifib, inputs=[field_components["antifibrotic_status"]], outputs=[antifib_drug, antifib_since, antifib_note])

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
        _sec_cmr_comps = [field_components["cmr_done"], field_components["rvef"], field_components["rvesvi"]]

        def _calc_cmr(*vals):
            cmr_done, rvef, rvesvi = vals
            if not bool(cmr_done):
                return 0, 0
            total = 2
            filled = (1 if _is_filled(rvef) else 0) + (1 if _is_filled(rvesvi) else 0)
            return filled, total

        _bind_section_progress(hdr_cmr, "MRT / CMR", _sec_cmr_comps, _calc_cmr)

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
            return {k: v for k, v in zip(input_keys, vals)}

        # Default UI snapshot (used to hard-reset patient-specific state before DOCX import).
        DEFAULT_UI: Dict[str, Any] = {}
        for k, comp in zip(input_keys, input_components):
            try:
                DEFAULT_UI[k] = getattr(comp, 'value', None)
            except Exception:
                DEFAULT_UI[k] = None
        # Dropdowns that must never be invalid (avoid 'value not in choices' crashes)
        if 'anticoag_indication' in DEFAULT_UI:
            DEFAULT_UI['anticoag_indication'] = 'keine Angabe'


        def apply_ui_to_components(ui_dict: Dict[str, Any]) -> List[Any]:
            import re
            # Backward/forward compatibility aliases
            if isinstance(ui_dict, dict):
                if "egfr_ml_min_1_73" not in ui_dict and "egfr" in ui_dict:
                    ui_dict["egfr_ml_min_1_73"] = ui_dict.get("egfr")

            def _choice_values(comp) -> List[Any]:
                """Return the *values* accepted by a choice component (supports (label,value) tuples)."""
                try:
                    ch = list(getattr(comp, "choices", []) or [])
                except Exception:
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
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", s or "").strip()

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
                except Exception:
                    pass

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
                    except Exception:
                        pass
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
                    except Exception:
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
                        out: List[Any] = []
                        for it in v:
                            mapped = _try_map_to_choice(it, choices)
                            if mapped is not None:
                                out.append(mapped)
                        return out
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
            for k in field_components.keys():
                out.append(_coerce_for_component(k, ui_dict.get(k)))
            return out
        def _generate(flags_state, pmods_state, docx_cur_state, docx_prev_state, echo_cur_state, echo_prev_state, case_filename_state, *vals):
            flags = dict(flags_state or {})

            # Optional lightweight profiling (console only). Enable with env var RHK_PERF=1.
            perf_on = os.getenv("RHK_PERF", "0").strip() == "1"
            t0 = time.perf_counter() if perf_on else 0.0
            t_raw0 = t0
            t_case0 = t0
            t_rep0 = t0
            t_ui0 = t0

            remembered_name = (case_filename_state or '').strip()
            # Normalize: ensure .json extension
            if remembered_name and not remembered_name.lower().endswith('.json'):
                remembered_name = remembered_name + '.json'

            if perf_on:
                t_raw0 = time.perf_counter()
            raw = ui_get_raw(*vals)

            # --- eGFR: compute reliably (also after programmatic imports) ---
            # The UI field is non-interactive, and Gradio does not fire `.change` callbacks
            # for programmatic updates (e.g., DOCX import). We therefore ensure that eGFR is
            # always computed for case/report generation whenever inputs are available.
            try:
                _egfr_val = compute_egfr(raw.get("creatinine_mg_dl"), raw.get("age"), raw.get("sex"))
            except Exception:
                _egfr_val = None
            if _egfr_val is not None:
                try:
                    _egfr_store = int(round(float(_egfr_val)))
                except Exception:
                    _egfr_store = _egfr_val
                raw["egfr_ml_min_1_73"] = _egfr_store
                # Backwards-compatible alias used in some report/export code paths
                raw["egfr"] = _egfr_store
            else:
                # If present from older cases/imports, propagate to legacy key for reports.
                if raw.get("egfr") in (None, "") and raw.get("egfr_ml_min_1_73") not in (None, ""):
                    raw["egfr"] = raw.get("egfr_ml_min_1_73")
            # Module kommen aus der UI als IDs (Choices liefern Value=Pxx); zusätzlich robust normalisieren.
            # Module kommen aus der UI als IDs (Choices liefern Value=Pxx).
            # Beim Laden von Beispielen/JSON-Fällen halten wir die CheckboxGroup in Stage-1 absichtlich leer,
            # um Gradio "Value not in choices"-Fehler zu vermeiden. In diesem Fall übernehmen wir die
            # gewünschte Auswahl aus pmods_state (Seed), aber nur solange noch kein Report existiert und der Fall nicht "dirty" ist.
            ui_mods = _normalize_module_ids((raw.get("modules_lvl1") or []) + (raw.get("modules_lvl2") or []) + (raw.get("modules_lvl3") or []) + (raw.get("modules") or []))
            seed_mods = _normalize_module_ids(((pmods_state or {}).get("lvl1") or []) + ((pmods_state or {}).get("lvl2") or []) + ((pmods_state or {}).get("lvl3") or []))
            if (not ui_mods) and seed_mods and (not flags.get("dirty")) and (not flags.get("has_report")):
                raw["modules"] = seed_mods
            else:
                raw["modules"] = ui_mods
            if perf_on:
                t_case0 = time.perf_counter()
            case = build_case(raw, rules)

            # Arztbericht: muss die vollständige Hämodynamik (Ruhe + Provokation), Slopes und Interpretation enthalten.
            # Das kompakte Template bleibt für DOCX-Layouts im Code, wird hier aber nicht als primärer Bericht verwendet.
            if perf_on:
                t_rep0 = time.perf_counter()
            doc = build_doctor_report(case, blocks)
            pat = build_patient_report(case)
            echo_doc = build_echo_doctor_report_extended(case)
            echo_pat = build_echo_patient_report(case)
            internal = build_internal_report(case)
            dash = build_dashboard_html(case)

            # Structured summary (stable schema) for studies/registries/QA
            try:
                summary_dict = build_summary_dict(case, rulebook_meta)
                case["summary"] = summary_dict
                summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
            except Exception:
                summary_dict = {}
                summary_json = "{}"
            fast_load = bool(flags.get("fast_load"))

            # Copy/paste payloads
            # - plain text for systems that break on rich formatting
            # - HTML for Word (clipboard text/html)
            try:
                # Single source of truth for Arztbericht:
                # UI preview, Clipboard and DOCX MUST be generated from the same master markdown.
                doc_master_md = str(doc or "")

                doc_plain = _markdown_to_plain_cached(doc_master_md)
                pat_plain = _markdown_to_plain_cached(str(pat or ''))
                rhk_section = _extract_markdown_section_cached(str(doc or ''), "Rechtsherzkatheter", "Beurteilung")
                rhk_plain = _markdown_to_plain_cached(str(rhk_section or ''))

                if fast_load:
                    # Speed: avoid expensive HTML clipboard conversion during example load
                    doc_html = ""
                    pat_html = ""
                    rhk_html = ""
                else:
                    doc_html = _markdown_to_word_html_cached(doc_master_md)
                    pat_html = _markdown_to_word_html_cached(str(pat or ''))
                    rhk_html = _markdown_to_word_html_cached(str(rhk_section or ''))
            except Exception:
                doc_plain = ""
                pat_plain = ""
                rhk_plain = ""
                doc_html = ""
                pat_html = ""
                rhk_html = ""

            # computed outputs
            der = case["derived"]
            ci_calc = None
            if der.get("co") is not None and der.get("bsa_m2") is not None and der.get("bsa_m2"):
                try:
                    ci_calc = float(der.get("co")) / float(der.get("bsa_m2"))
                except Exception:
                    ci_calc = None
            # --- P-Module Policy (fallbasiert) ---
            policy = der.get("p_module_policy") or {}

            # --- Live preview layers ---
            # Status: report is now up-to-date
            flags["has_report"] = True
            flags["report_stale"] = False
            flags["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            flags.pop("fast_load", None)
            try:
                flags["warnings"] = case.get("warnings") or []
            except Exception:
                flags["warnings"] = []

            if perf_on:
                t_ui0 = time.perf_counter()
            summary_html = build_sticky_summary_html(case, flags)
            compare_html = build_compare_overview_html(case)
            cards_html = build_p_module_cards_html(blocks, case)
            # --- DOCX Import: attach raw payloads into case for transparency/QA ---
            try:
                _imp = case.setdefault("imports", {})
                _imp["docx_current"] = docx_cur_state
                _imp["docx_prev"] = docx_prev_state
                _imp["echo_cur"] = echo_cur_state
                _imp["echo_prev"] = echo_prev_state
            except Exception:
                pass

            # --- Import status + plots (never raise) ---
            try:
                status_html = build_docx_status_html(docx_cur_state, docx_prev_state)
            except Exception:
                status_html = ""
            try:
                if fast_load:
                    plots_html = ""
                else:
                    # Performance: cache plot HTML per-case/session (patient-safe: cache lives only in state_flags).
                    def _plots_key(_case: dict, _docx: Any, _docx_prev: Any) -> str:
                        try:
                            _raw = (_case.get("raw") or {}) if isinstance(_case, dict) else {}
                            _der = (_case.get("derived") or {}) if isinstance(_case, dict) else {}
                            parts = []

                            # Key hemodynamic signals that influence plot output
                            for k in (
                                "exercise_done", "volume_challenge_done",
                                "prev_mpap", "prev_pawp", "prev_rap", "prev_ci", "prev_pvr",
                                "pawp_pre", "pawp_post", "mpap_pre", "mpap_post",
                            ):
                                parts.append(_raw.get(k))

                            for k in (
                                "mpap", "pawp", "rap", "co", "ci", "pvr",
                                "mpap_peak", "pawp_peak", "co_peak",
                                "mpap_calc", "pvr_calc", "tpg", "dpg",
                            ):
                                parts.append(_der.get(k))

                            def _phase_sig(d: Any):
                                if not isinstance(d, dict):
                                    return None
                                ph = d.get("phases") or {}
                                if not isinstance(ph, dict) or not ph:
                                    return None
                                out = []
                                for pk in sorted(ph.keys()):
                                    cur = ph.get(pk) or {}
                                    if not isinstance(cur, dict):
                                        continue

                                    def g(path):
                                        c = cur
                                        for p in path:
                                            c = c.get(p) if isinstance(c, dict) else None
                                        return c if isinstance(c, (int, float, str, bool)) else None

                                    out.extend([
                                        pk,
                                        g(("pressures", "pa", "mean")),
                                        g(("pressures", "pcw", "mean")),
                                        g(("pressures", "ra", "mean")),
                                        g(("co", "td_co")),
                                        g(("co", "fick_co")),
                                        g(("resistance", "pvr", "wu")),
                                        g(("resistance", "pvri", "wu")),
                                    ])
                                return out

                            parts.append(_phase_sig(_docx))
                            parts.append(_phase_sig(_docx_prev))

                            s = json.dumps(parts, ensure_ascii=False, sort_keys=False, default=str)
                            return hashlib.md5(s.encode("utf-8")).hexdigest()
                        except Exception:
                            return ""

                    _rc = flags.get("_render_cache") if isinstance(flags, dict) else None
                    if not isinstance(_rc, dict):
                        _rc = {}
                        flags["_render_cache"] = _rc

                    key = _plots_key(case, docx_cur_state, docx_prev_state)
                    cached_key = _rc.get("plots_key")
                    if key and cached_key == key and isinstance(_rc.get("plots_html"), str):
                        plots_html = _rc.get("plots_html") or ""
                    else:
                        plots_html = build_rhk_plots_html(case, docx_cur_state, docx_prev_state)
                        _rc["plots_key"] = key
                        _rc["plots_html"] = plots_html
            except Exception:
                plots_html = ""

            
            # --- P-Module Selection (Single Source of Truth: case['ui']['modules']) ---
            # Auto-Vorschläge (decision.modules) sind nur Vorschläge und werden NICHT automatisch übernommen.
            ui = case.get("ui") or {}
            force_optional = pmods_get_force_optional(ui)
            eff_policy = pmods_apply_overrides(policy, force_optional)

            # Choices are built from the effective policy (allowed list). Disabled modules remain visible separately.
            mod_choices = build_p_module_choices(blocks, eff_policy)
            disabled_html = build_disabled_p_modules_html(blocks, eff_policy)

            levels_map = (eff_policy.get("levels") or {}) if isinstance(eff_policy, dict) else {}
            disabled_map = (eff_policy.get("disabled") or {}) if isinstance(eff_policy, dict) else {}

            # Selected modules: ONLY from UI, keep user order stable.
            sel_vals = _normalize_module_ids(ui.get("modules") or [])

            # Ensure locked-but-selected modules stay removable: include them in choices.
            locked_selected = [m for m in sel_vals if (m in disabled_map and m not in force_optional)]

            # Label helpers
            import re as _re
            def _clean_pmod_label(lab: Any) -> str:
                s = str(lab) if lab is not None else ""
                s = _re.sub(r"^\s*\[[^\]]+\]\s*", "", s).strip()
                return s

            id_to_label: Dict[str, str] = {mid: _clean_pmod_label(lab) for (lab, mid) in mod_choices}
            # fallback labels for locked-selected
            for mid in locked_selected:
                if mid not in id_to_label:
                    try:
                        title = blocks[mid].title if mid in blocks else ""
                    except Exception:
                        title = ""
                    id_to_label[mid] = f"{mid} – {title}".strip(" –")

            def _get_level(mid: str) -> int:
                try:
                    return int(levels_map.get(mid, 3) or 3)
                except Exception:
                    return 3

            # Build per-level selected lists in stable order
            selected_lvl1_ids = [m for m in sel_vals if _get_level(m) == 1]
            selected_lvl2_ids = [m for m in sel_vals if _get_level(m) == 2]
            selected_lvl3_ids = [m for m in sel_vals if _get_level(m) not in (1, 2)]

            # Build per-level choices (label,value) from allowed + locked_selected
            allowed_ids = [mid for (_lab, mid) in mod_choices]
            def _choices_for_level(lvl: int):
                ch = []
                for mid in allowed_ids:
                    if _get_level(mid) != lvl:
                        continue
                    lab = id_to_label.get(mid, mid)
                    ch.append((lab, mid))
                # Append locked selected values for this level (so the user can unselect them)
                for mid in locked_selected:
                    if _get_level(mid) != lvl:
                        continue
                    lab = id_to_label.get(mid, mid) + " (gesperrt)"
                    if (lab, mid) not in ch:
                        ch.append((lab, mid))
                return ch

            def _choices_for_level3():
                ch = []
                for mid in allowed_ids:
                    if _get_level(mid) in (1, 2):
                        continue
                    lab = id_to_label.get(mid, mid)
                    ch.append((lab, mid))
                for mid in locked_selected:
                    if _get_level(mid) in (1, 2):
                        continue
                    lab = id_to_label.get(mid, mid) + " (gesperrt)"
                    if (lab, mid) not in ch:
                        ch.append((lab, mid))
                return ch

            choices_lvl1 = _choices_for_level(1)
            choices_lvl2 = _choices_for_level(2)
            choices_lvl3 = _choices_for_level3()

            modules_lvl1_update = gr.update(choices=choices_lvl1, value=selected_lvl1_ids)
            modules_lvl2_update = gr.update(choices=choices_lvl2, value=selected_lvl2_ids)
            modules_lvl3_update = gr.update(choices=choices_lvl3, value=selected_lvl3_ids)

            # Disabled dropdown (only those still disabled)
            disabled_dd_choices = []
            for mid, reason in sorted(disabled_map.items(), key=lambda kv: kv[0]):
                if mid in force_optional:
                    continue
                title = ""
                try:
                    title = blocks[mid].title if mid in blocks else ""
                except Exception:
                    title = ""
                lab = f"{mid} – {title}".strip(" –")
                if reason:
                    lab = f"{lab} | {reason}"
                disabled_dd_choices.append((lab, mid))
            pmods_disabled_dd_update = gr.update(choices=disabled_dd_choices, value=None)

            # State snapshot (for legacy load/save flows; UI still reads from case.ui.modules)
            pmods_sel_state = {
                "lvl1": selected_lvl1_ids,
                "lvl2": selected_lvl2_ids,
                "lvl3": selected_lvl3_ids,
                "modules": sel_vals,
                "force_optional": list(force_optional),
            }

            if perf_on:
                t_end = time.perf_counter()
                try:
                    print(
                        "[PERF] Generate "
                        f"total={(t_end - t0)*1000:.1f}ms | "
                        f"raw={(t_case0 - t_raw0)*1000:.1f}ms | "
                        f"case={(t_rep0 - t_case0)*1000:.1f}ms | "
                        f"reports={(t_ui0 - t_rep0)*1000:.1f}ms | "
                        f"ui={(t_end - t_ui0)*1000:.1f}ms"
                    )
                except Exception:
                    pass

            return (
                der.get("mpap_calc"), ci_calc, der.get("pvr_calc"), der.get("pvri"), der.get("tpg"), der.get("dpg"),
                dash, doc, pat, echo_doc, echo_pat, internal,
                summary_json,
                json.dumps(case, ensure_ascii=False, indent=2),
                doc_plain, pat_plain, rhk_plain,
                doc_html, pat_html, rhk_html,
                "",  # copy feedback reset
                case,
                flags,
                pmods_sel_state,
                docx_cur_state,
                docx_prev_state,
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                disabled_html,
                pmods_disabled_dd_update,
                summary_html,
                compare_html,
                plots_html,
                status_html,
                cards_html,
            )

        def _apply_pmods_values(sel_state: Optional[Dict[str, Any]]):
            """2nd stage: set CheckboxGroup values AFTER choices were updated (robust mapping)."""
            import re
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
            except Exception:
                return (gr.update(value=[]), gr.update(value=[]), gr.update(value=[]))

        def _generate_with_pmods_apply(*args):
            """Run _generate without mutating P-Module UI state.

            Single Source of Truth is case_state["ui"]["modules"].
            The dropdown updates are already part of _generate() outputs.
            """
            return _generate(*args)

        def _export_doctor_docx(case_state: Any):
            """Create a formatted DOCX for the doctor report.

            IMPORTANT
            - The DOCX MUST match exactly the report shown in-app and copied to clipboard.
            - A single master markdown string is used for UI, clipboard and DOCX.
            """
            import os
            import tempfile
            import time

            if not isinstance(case_state, dict):
                raise gr.Error("Bitte zuerst den Befund erstellen, dann DOCX herunterladen.")

            # Single source of truth: master doctor report markdown
            md = str(build_doctor_report(case_state, blocks) or "").strip()

            # Deterministic, safe filename stub (avoid patient identifiers in file name by default)
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(tempfile.gettempdir(), f"rhk_arztbericht_{ts}.docx")

            markdown_to_docx_file(md, out_path)
            return out_path

        def _export_doctor_docx_local(case_state: Any, out_dir: str):
            """Create the same DOCX as download, but save it to a local path.

            Motivation
            - In some clinic environments, browser downloads are blocked or Word opens downloaded files in Protected View (Mark-of-the-Web).
            - Saving to a local folder (e.g., Documents) avoids the download zone marker.
            """
            import os
            import time

            if not isinstance(case_state, dict):
                raise gr.Error("Bitte zuerst den Befund erstellen, dann DOCX speichern.")

            out_dir = str(out_dir or "").strip()
            if not out_dir:
                # sensible default
                out_dir = os.path.join(os.path.expanduser("~"), "Documents", "RHK_Befunde")

            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                raise gr.Error(f"Ordner kann nicht erstellt/genutzt werden: {out_dir} ({e})")

            md = str(build_doctor_report(case_state, blocks) or "").strip()

            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(out_dir, f"rhk_arztbericht_{ts}.docx")
            markdown_to_docx_file(md, out_path)
            return f"Gespeichert: {out_path}"

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

        btn_generate_top.click(_generate_with_pmods_apply, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)
        btn_generate_bottom.click(_generate_with_pmods_apply, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)

        # DOCX export for the doctor report (Muster-Layout)
        # Use DownloadButton to keep the UI compact.
        btn_download_doc.click(
            _export_doctor_docx,
            inputs=[state_case],
            outputs=[btn_download_doc],
        )

        # DOCX save to local path (clinic workaround)
        btn_save_docx_local.click(
            _export_doctor_docx_local,
            inputs=[state_case, docx_save_dir],
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
            except Exception:
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
        def _update_procedere_only(flags_state, case_state, m1, m2, m3, free_text):
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
                except Exception:
                    levels_map = {}

                def _lvl(mid: str) -> int:
                    try:
                        return int(levels_map.get(mid, 3) or 3)
                    except Exception:
                        return 3

                prev_all = _normalize_module_ids(ui.get("modules") or [])
                prev_lvl1 = [x for x in prev_all if _lvl(x) == 1]
                prev_lvl2 = [x for x in prev_all if _lvl(x) == 2]
                prev_lvl3 = [x for x in prev_all if _lvl(x) not in (1, 2)]

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
                ui["modules_lvl1"] = m1 or []
                ui["modules_lvl2"] = m2 or []
                ui["modules_lvl3"] = m3 or []
                ui["procedere_free"] = free_text or ""
                ui["modules"] = _normalize_module_ids(
                    (ui.get("modules_lvl1") or []) + (ui.get("modules_lvl2") or []) + (ui.get("modules_lvl3") or [])
                )
                case_state["ui"] = ui

                # Master doctor report (single source of truth)
                doc_full = build_doctor_report(case_state, blocks)
                # Optional compact template (kept for legacy/export code paths)
                doc_template = build_doctor_report_template(case_state, blocks)
                pat = build_patient_report(case_state)
                echo_doc = build_echo_doctor_report_extended(case_state)
                echo_pat = build_echo_patient_report(case_state)
                internal = build_internal_report(case_state)

                # Single source of truth for Arztbericht:
                # UI preview (out_doc), Clipboard and DOCX must match.
                doc_master_md = str(doc_full or "")

                # Structured summary + debug
                try:
                    summary_dict = build_summary_dict(case_state, rulebook_meta)
                    case_state["summary"] = summary_dict
                    summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
                except Exception:
                    summary_json = "{}"
                dbg = json.dumps(case_state, ensure_ascii=False, indent=2)
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
                except Exception:
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
                except Exception:
                    flags["warnings"] = []

                sticky = build_sticky_summary_html(case_state, flags)
                return (
                    doc_full,
                    pat,
                    echo_doc,
                    echo_pat,
                    internal,
                    summary_json,
                    dbg,
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
            except Exception:
                # Fail-safe: do not break UI on minor issues
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

        _procedere_inputs = [state_flags, state_case, modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp, field_components["procedere_free"]]
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

        modules_lvl1_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        modules_lvl2_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        modules_lvl3_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        field_components["procedere_free"].change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        # Optional: bei Enter/Submit ebenfalls
        try:
            field_components["procedere_free"].submit(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        except Exception:
            pass

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

            def _lvl(mid: str) -> int:
                try:
                    return int(levels_map.get(mid, 3) or 3)
                except Exception:
                    return 3

            allowed_ids = [mid for (_lab, mid) in mod_choices]
            sel_vals = _normalize_module_ids(ui.get("modules") or [])
            locked_selected = [m for m in sel_vals if (m in disabled_map and m not in force_optional)]

            # labels
            import re as _re
            def _clean_pmod_label(lab: Any) -> str:
                s = str(lab) if lab is not None else ""
                return _re.sub(r"^\s*\[[^\]]+\]\s*", "", s).strip()

            id_to_label = {mid: _clean_pmod_label(lab) for (lab, mid) in mod_choices}
            for mid in locked_selected:
                if mid not in id_to_label:
                    try:
                        title = blocks[mid].title if mid in blocks else ""
                    except Exception:
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

            lvl1_choices = _choices_level(lambda mid: _lvl(mid)==1)
            lvl2_choices = _choices_level(lambda mid: _lvl(mid)==2)
            lvl3_choices = _choices_level(lambda mid: _lvl(mid) not in (1,2))

            sel_lvl1 = [m for m in sel_vals if _lvl(m)==1]
            sel_lvl2 = [m for m in sel_vals if _lvl(m)==2]
            sel_lvl3 = [m for m in sel_vals if _lvl(m) not in (1,2)]

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

        def _load_example_ui():
            ui = random_example()

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
            return (*vals, pending, "")

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
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
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
            sync_out = _sync_post_load(ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list)
            cpet_out = _sync_post_load_cpet(
        cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
        cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
        cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
        consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
        crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
        lsb_present, lsb_reason,
            )

            gen_out = _generate_with_pmods_apply(
        flags, pmods_sel_state,
        docx_cur_state, docx_prev_state,
        echo_state_cur_reset, echo_state_prev_reset,
        case_filename,
        *vals,
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


        btn_example_top.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected, state_case_filename])\
            .then(
        _post_example_load_and_generate,
        inputs=[
            state_pmods_selected,
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
            field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
            field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
            field_components["lsb_present"], field_components["lsb_reason"],
        ] + input_components,
        outputs=[
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            cpet_details, cpet_risk_html,
            pre_cath_html, pre_cath_home_html,
            import_pdf_cur, import_preview_cur_html, state_echo_cur,
            import_pdf_prev, import_preview_prev_html, state_echo_prev,
            compare_echo_html, details_echo_html, btn_echo_apply,
            state_case_filename,
        ] + generate_outputs,
            )

        btn_example_bottom.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected, state_case_filename])\
            .then(
        _post_example_load_and_generate,
        inputs=[
            state_pmods_selected,
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],
            field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"],
            field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"],
            field_components["lsb_present"], field_components["lsb_reason"],
        ] + input_components,
        outputs=[
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            cpet_details, cpet_risk_html,
            pre_cath_html, pre_cath_home_html,
            import_pdf_cur, import_preview_cur_html, state_echo_cur,
            import_pdf_prev, import_preview_prev_html, state_echo_prev,
            compare_echo_html, details_echo_html, btn_echo_apply,
            state_case_filename,
        ] + generate_outputs,
            )


        # --- Clear all (Befunde leeren) ---
        # Reset inputs to safe defaults and clear all outputs/state.
        # IMPORTANT: Must return exactly len(load_outputs) values.
        load_outputs = [*input_components, *generate_outputs, import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html, details_echo_html, btn_echo_apply, state_case_filename]

        def _clear_all():
            # Inputs: build empty UI dict and let apply_ui_to_components normalize legacy/defaults.
            empty_ui = {k: None for k in input_keys}
            for lk in ("meds", "comorbidities", "modules", "modules_lvl1", "modules_lvl2", "modules_lvl3"):
                if lk in empty_ui:
                    empty_ui[lk] = []
            # Dropdowns that must never be invalid (avoid "value not in choices" crashes)
            empty_ui["anticoag_indication"] = "keine Angabe"

            vals = apply_ui_to_components(empty_ui)

            flags0 = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}

            # Reset module UI deterministically
            modules_lvl1_update = gr.update(choices=[], value=[])
            modules_lvl2_update = gr.update(choices=[], value=[])
            modules_lvl3_update = gr.update(choices=base_module_choices, value=[])

            # Outputs (mirror generate_outputs order)
            cleared_outputs = (
                None, None, None, None, None, None,  # auto_mpap..auto_dpg
                build_dashboard_html(None),           # dashboard
                "", "", "", "", "",                    # out_doc, out_pat, out_echo_doc, out_echo_pat, out_int
                "{}",                                 # out_summary_json
                "{}",                                 # out_json
                "", "", "",                           # copy_*_plain
                "", "", "",                           # copy_*_html
                "",                                   # copy_feedback
                None,                                 # state_case
                flags0,                                # state_flags
                {"lvl1": [], "lvl2": [], "lvl3": []},  # state_pmods_selected
                None,                                 # state_docx_cur
                None,                                 # state_docx_prev
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                "",                                   # modules_disabled_html
                build_sticky_summary_html(None, flags0),
                "",                                   # compare_overview_html
                "",                                   # rhk_plots_html
                "",                                   # import_status_html
                "",                                   # modules_cards_html
            )
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
                *cleared_outputs,
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
            for lk in ("meds", "comorbidities", "modules_lvl1", "modules_lvl2", "modules_lvl3", "modules"):
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

        def _save_case(case_state, flags_state, case_filename):
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

            flags = dict(flags_state or {})
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

            remembered_name = (case_filename or "").strip() or None

            def _is_cloud_env() -> bool:
                # Render/Cloud environments usually set PORT.
                return bool(os.environ.get("PORT")) or bool(os.environ.get("RENDER")) or bool(os.environ.get("K_SERVICE"))

            # Decide target directory
            target_dir = None
            # Always use download-based save (browser-managed location)
            # (Local folder pickers are intentionally disabled.)

            # Fallback: cross-platform temp directory (Windows has no /tmp)
            if not target_dir:
                try:
                    import tempfile
                    tmp_root = tempfile.gettempdir()
                    target_dir = os.path.join(tmp_root, "rhk_befunder")
                    os.makedirs(target_dir, exist_ok=True)
                except Exception:
                    target_dir = os.getcwd()

            case_path = os.path.join(target_dir, remembered_name or f"rhk_case_{ts}.json")
            summary_path = os.path.join(target_dir, (os.path.splitext(remembered_name)[0] + "_summary.json") if remembered_name else f"rhk_summary_{ts}.json")

            # Ensure summary is present
            try:
                summary_dict = case_state.get("summary")
                if not isinstance(summary_dict, dict) or not summary_dict:
                    summary_dict = build_summary_dict(case_state, rulebook_meta)
                    case_state["summary"] = summary_dict
            except Exception:
                summary_dict = {}

            try:
                export_json(case_state, case_path)
                export_summary_json(summary_dict, summary_path)
            except Exception as e:
                # Do not crash the UI; show a clear message and keep downloads hidden.
                return (
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    flags,
                    build_sticky_summary_html(case_state, flags),
                    f"❌ Speichern fehlgeschlagen: {type(e).__name__}: {e}",
                )

            flags["dirty"] = False
            flags["saved_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            try:
                flags["warnings"] = case_state.get("warnings") or []
            except Exception:
                pass

            sticky = build_sticky_summary_html(case_state, flags)
            # Provide downloads as well (user can choose location in browser download dialog).
            return (
                gr.update(visible=True, value=case_path),
                gr.update(visible=True, value=summary_path),
                flags,
                sticky,
                "✅ Gespeichert. (Bei Bedarf über die Download-Links herunterladen.)",
            )

        _save_outputs = [file_out, file_summary_out, state_flags, sticky_summary_html, copy_feedback]

        save_btn_top.click(_generate_with_pmods_apply, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_save_case, inputs=[state_case, state_flags, state_case_filename], outputs=_save_outputs)
        save_btn_bottom.click(_generate_with_pmods_apply, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_save_case, inputs=[state_case, state_flags, state_case_filename], outputs=_save_outputs)

        # --- Load case ---

        def _load_case_ui(file):
            # Returns values for:
            # - input_components
            # - state_pmods_selected (pending module selection)
            # - state_docx_cur / state_docx_prev (import caches)
            # - echo import UI (states + rendered preview/compare html)
            empty_pending = {"lvl1": [], "lvl2": [], "lvl3": []}
            if file is None:
                # Keep everything as-is; do not clobber states.
                return [c.value for c in input_components] + [empty_pending, None, None,
                                                             gr.update(value=None), "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>", {"parsed": {}, "meta": {}, "has_file": False},
                                                             gr.update(value=None), "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>", {"parsed": {}, "meta": {}, "has_file": False},
                                                             "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>",
                                                             "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>",
                                                             gr.update(interactive=False)] + [""]

            try:
                import json as _json
                with open(file.name, "r", encoding="utf-8") as f:
                    data = _json.load(f)
            except Exception:
                data = {}

            ui_dict = data.get("ui") if isinstance(data, dict) and "ui" in data else data
            if not isinstance(ui_dict, dict):
                ui_dict = {}

            # Extract desired P-module selection (legacy-friendly)
            pending = {
                "lvl1": ui_dict.get("modules_lvl1") or [],
                "lvl2": ui_dict.get("modules_lvl2") or [],
                "lvl3": ui_dict.get("modules_lvl3") or (ui_dict.get("modules") or []),
            }

            # Avoid Gradio choice-errors during stage-1 load: keep UI checkbox values empty.
            ui_dict["modules_lvl1"] = []
            ui_dict["modules_lvl2"] = []
            ui_dict["modules_lvl3"] = []

            vals = apply_ui_to_components(ui_dict)

            imports = (data.get("imports") if isinstance(data, dict) else None) or {}
            if not isinstance(imports, dict):
                imports = {}

            docx_cur = imports.get("docx_current")
            docx_prev = imports.get("docx_prev")

            echo_cur = imports.get("echo_cur") or {"parsed": {}, "meta": {}, "has_file": False}
            echo_prev = imports.get("echo_prev") or {"parsed": {}, "meta": {}, "has_file": False}

            try:
                cur_html, prev_html, cmp_html, details_html, btnu = render_echo_import_views(echo_prev, echo_cur)
            except Exception:
                cur_html = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
                prev_html = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
                cmp_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
                details_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
                btnu = gr.update(interactive=False)

            # We cannot restore uploaded file objects; keep upload widgets empty.
            loaded_name = ""
            try:
                loaded_name = os.path.basename(file.name if hasattr(file, 'name') else str(file))
            except Exception:
                loaded_name = ""

            pdf_cur_reset = gr.update(value=None)
            pdf_prev_reset = gr.update(value=None)

            return (*vals,
                    pending,
                    docx_cur, docx_prev,
                    pdf_cur_reset, cur_html, echo_cur,
                    pdf_prev_reset, prev_html, echo_prev,
                    cmp_html, details_html, btnu, loaded_name)

        


        # -------------------------
        # DOCX Import (Mac-Lab)
        # -------------------------
        DOCX_WIPE_CURRENT = {
            # rest hemo
            "spap_rest": None, "dpap_rest": None, "mpap_rest": None, "pawp_rest": None, "rap_rest": None,
            "co_rest": None, "ci_rest": None, "pvr_rest": None, "co_method": None,
            # exercise
            "exercise_done": False,
            "spap_peak": None, "dpap_peak": None, "mpap_peak": None, "pawp_peak": None,
            "co_peak": None, "ci_peak": None,
            # volume
            "volume_challenge_done": False,
            "pawp_pre": None, "pawp_post": None, "mpap_pre": None, "mpap_post": None,
            # vaso
            "vaso_test_done": False,
            "vaso_agent": "", "vaso_response_desc": "",
            "vaso_mpap_pre": None, "vaso_co_pre": None, "vaso_mpap_post": None, "vaso_co_post": None,
            # oximetry
            "sat_svc": None, "sat_ivc": None, "sat_ra": None, "sat_rv": None, "sat_pa": None, "sat_ao": None,
            # vitals
            "bp_sys": None, "bp_dia": None, "bp_mean": None, "hr": None, "spo2": None,
        }

        DOCX_WIPE_PREV = {
            "prev_rhk_date": "",
            "prev_spap": None, "prev_dpap": None, "prev_mpap": None, "prev_pawp": None, "prev_rap": None,
            "prev_co": None, "prev_ci": None, "prev_pvr": None,
        }

        FILL_FROM_PREV_IF_MISSING = ["age", "sex", "height_cm", "weight_kg", "hb_g_dl"]

        def _docx_import_current(file, prev_payload, *vals):
            """Import current DOCX without deleting manual entries.

            Policy:
            - Only fields that were previously imported and remain unchanged are eligible for overwrite/clear.
            - Empty fields are eligible for auto-fill.
            - Manual edits are preserved.
            """
            ui_dict = ui_get_raw(*vals)

            prev_payload = prev_payload if isinstance(prev_payload, dict) else {}
            prev_keys = prev_payload.get("_ui_applied_keys_current") or []
            prev_vals = prev_payload.get("_ui_applied_values_current") or {}

            payload = parse_maclab_docx(file.name if hasattr(file, "name") else str(file))
            updates = map_payload_to_ui(payload, target="current")

            # 1) Clear stale imported fields that are NOT present in the new import
            #    but only if the user has not modified them.
            for k in list(prev_keys):
                if k in updates:
                    continue
                if k in DOCX_WIPE_CURRENT:
                    if ui_dict.get(k) == prev_vals.get(k):
                        ui_dict[k] = DOCX_WIPE_CURRENT.get(k)

            # 2) Apply new updates conservatively.
            applied_vals: Dict[str, Any] = {}
            for k, v in (updates or {}).items():
                cur = ui_dict.get(k)
                prev_v = prev_vals.get(k)
                if (cur in (None, "", 0)) or (cur == prev_v):
                    ui_dict[k] = v
                    applied_vals[k] = v

            # Persist provenance (does not break status/overview renderers)
            try:
                payload["_ui_applied_keys_current"] = sorted(list(applied_vals.keys()))
                payload["_ui_applied_values_current"] = applied_vals
            except Exception:
                pass

            vals_out = apply_ui_to_components(ui_dict)
            return (*vals_out, payload)

        def _docx_import_prev(file, prev_payload, *vals):
            ui_dict = ui_get_raw(*vals)

            prev_payload = prev_payload if isinstance(prev_payload, dict) else {}
            prev_keys = prev_payload.get("_ui_applied_keys_prev") or []
            prev_vals = prev_payload.get("_ui_applied_values_prev") or {}

            payload = parse_maclab_docx(file.name if hasattr(file, "name") else str(file))
            updates_prev = map_payload_to_ui(payload, target="prev")

            # Clear stale prev-imported fields not present in new import (only if unchanged)
            for k in list(prev_keys):
                if k in updates_prev:
                    continue
                if k in DOCX_WIPE_PREV:
                    if ui_dict.get(k) == prev_vals.get(k):
                        ui_dict[k] = DOCX_WIPE_PREV.get(k)

            applied_vals_prev: Dict[str, Any] = {}
            for k, v in (updates_prev or {}).items():
                cur = ui_dict.get(k)
                prev_v = prev_vals.get(k)
                if (cur in (None, "", 0)) or (cur == prev_v):
                    ui_dict[k] = v
                    applied_vals_prev[k] = v

            # Option: aus Vor-RHK fehlende Demografie/Laborwerte ergänzen (nur wenn aktuell leer)
            updates_cur = map_payload_to_ui(payload, target="current")
            for k in FILL_FROM_PREV_IF_MISSING:
                if (ui_dict.get(k) in (None, "", 0)) and (updates_cur.get(k) is not None):
                    ui_dict[k] = updates_cur.get(k)

            # Persist provenance
            try:
                payload["_ui_applied_keys_prev"] = sorted(list(applied_vals_prev.keys()))
                payload["_ui_applied_values_prev"] = applied_vals_prev
            except Exception:
                pass

            vals_out = apply_ui_to_components(ui_dict)
            return (*vals_out, payload)


        def _reset_pmods_after_import():
            # Reset pending module selection to avoid stale templates influencing a new import.
            return {"lvl1": [], "lvl2": [], "lvl3": []}




        def _post_docx_current_import_and_generate(
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
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

            sync_out = _sync_post_load(ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list)
            cpet_out = _sync_post_load_cpet(
                cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
                cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
                consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
                crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
                lsb_present, lsb_reason,
            )

            gen_out = _generate_with_pmods_apply(
                flags, pmods_sel_state,
                docx_cur_payload, docx_prev_payload,
                echo_cur_payload, echo_prev_payload,
                case_filename,
                *vals,
            )
            return (*sync_out, *cpet_out, *pre_cath_out, *gen_out)

        def _post_docx_prev_import_and_generate(
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
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

            sync_out = _sync_post_load(ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list)
            cpet_out = _sync_post_load_cpet(
                cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
                cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
                cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            )
            pre_cath_out = _update_pre_cath_both(
                consent_done, access_route, inr, ptt_s, platelets_g_l, anticoag_status, anticoag_paused,
                crp_mg_l, creatinine_mg_dl2, age2, sex2, allergies_present2, allergies_list2, allergies_other_text,
                lsb_present, lsb_reason,
            )

            gen_out = _generate_with_pmods_apply(
                flags, pmods_sel_state,
                docx_cur_payload, docx_prev_payload,
                echo_cur_payload, echo_prev_payload,
                case_filename,
                *vals,
            )
            return (*sync_out, *cpet_out, *pre_cath_out, *gen_out)

        docx_btn_top.upload(_docx_import_current, inputs=[docx_btn_top, state_docx_cur] + input_components, outputs=input_components + [state_docx_cur])\
            .then(
                _post_docx_current_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
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
                    cpet_details, cpet_risk_html,
                    pre_cath_html, pre_cath_home_html,
                ] + generate_outputs,
            )

        docx_btn_bottom.upload(_docx_import_current, inputs=[docx_btn_bottom, state_docx_cur] + input_components, outputs=input_components + [state_docx_cur])\
            .then(
                _post_docx_current_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
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
                    cpet_details, cpet_risk_html,
                    pre_cath_html, pre_cath_home_html,
                ] + generate_outputs,
            )

        prev_docx_btn.upload(_docx_import_prev, inputs=[prev_docx_btn, state_docx_prev] + input_components, outputs=input_components + [state_docx_prev])\
            .then(
                _post_docx_prev_import_and_generate,
                inputs=[
                    field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
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


        def _post_case_load_and_generate(
            # thorax + egfr + allergies
            ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list,
            # CPET live-risk
            cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
            cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
            cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            # CPET wizard (full)
            wiz_cpet_done,
            stop_reason, stop_reason_text,
            borg_rpe, borg_dysp, borg_leg,
            wiz_rer_peak, wiz_hr_peak, wiz_hr_pct,
            wiz_peak_vo2, wiz_peak_vo2_pct,
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
            pmods_sel_state, docx_cur_payload, docx_prev_payload, echo_cur_payload, echo_prev_payload, case_filename,
            *vals,
        ):
            flags = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": [], "fast_load": False}

            sync_out = _sync_post_load(ct_done, ct_ild, vq_done, creatinine_mg_dl, age, sex, allergies_present, allergies_list)
            cpet_out = _sync_post_load_cpet(
        cpet_done, cpet_peak_vo2_ml_kg_min, cpet_peak_vo2_pct_pred, cpet_ve_vco2_slope, cpet_petco2_vt1_mmhg,
        cpet_ve_vco2_vt1, cpet_peak_o2_pulse_pct_pred, cpet_vo2_wr_slope_ml_min_w, cpet_vo2_vt1_ml_kg_min,
        cpet_spo2_nadir_pct, cpet_rer_peak, cpet_hr_peak_bpm, cpet_o2_pulse_pattern,
            )
            wiz_out = _sync_post_load_cpet_wizard(
        wiz_cpet_done,
        stop_reason, stop_reason_text,
        borg_rpe, borg_dysp, borg_leg,
        wiz_rer_peak, wiz_hr_peak, wiz_hr_pct,
        wiz_peak_vo2, wiz_peak_vo2_pct,
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

            gen_out = _generate_with_pmods_apply(
        flags, pmods_sel_state,
        docx_cur_payload, docx_prev_payload,
        echo_cur_payload, echo_prev_payload,
        case_filename,
        *vals,
            )

            return (*sync_out, *cpet_out, *wiz_out, *pre_cath_out, *gen_out)

        load_btn_top.upload(
    _load_case_ui,
    inputs=[load_btn_top],
    outputs=input_components + [
        state_pmods_selected,
        state_docx_cur, state_docx_prev,
        import_pdf_cur, import_preview_cur_html, state_echo_cur,
        import_pdf_prev, import_preview_prev_html, state_echo_prev,
        compare_echo_html, details_echo_html, btn_echo_apply,
        state_case_filename,
    ],
        )\
    .then(
        _post_case_load_and_generate,
        inputs=[
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],

            field_components["cpet_done"],
            field_components["cpet_stop_reason"], field_components["cpet_stop_reason_text"],
            field_components["cpet_borg_rpe"], field_components["cpet_borg_dyspnea"], field_components["cpet_borg_leg"],
            field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_hr_pct_pred"],
            field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"],
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
        ] + input_components,
        outputs=[
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            cpet_details, cpet_risk_html,
            cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_spiro_report, cpet_chrono_followup,
            pre_cath_html, pre_cath_home_html,
        ] + generate_outputs,
    )

        load_btn_bottom.upload(
    _load_case_ui,
    inputs=[load_btn_bottom],
    outputs=input_components + [
        state_pmods_selected,
        state_docx_cur, state_docx_prev,
        import_pdf_cur, import_preview_cur_html, state_echo_cur,
        import_pdf_prev, import_preview_prev_html, state_echo_prev,
        compare_echo_html, details_echo_html, btn_echo_apply,
        state_case_filename,
    ],
        )\
    .then(
        _post_case_load_and_generate,
        inputs=[
            field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"],
            field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"],
            field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"],
            field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"],

            field_components["cpet_done"],
            field_components["cpet_stop_reason"], field_components["cpet_stop_reason_text"],
            field_components["cpet_borg_rpe"], field_components["cpet_borg_dyspnea"], field_components["cpet_borg_leg"],
            field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_hr_pct_pred"],
            field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"],
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
        ] + input_components,
        outputs=[
            ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"],
            cpet_details, cpet_risk_html,
            cpet_mod0_html, cpet_mod1_html, cpet_mod2_html, cpet_mod3_html, cpet_mod4_html, cpet_mod5_html, cpet_mod6_html, cpet_mod7_html, cpet_mod9_html, cpet_modfinal_html, cpet_overall_html, cpet_spiro_report, cpet_chrono_followup,
            pre_cath_html, pre_cath_home_html,
        ] + generate_outputs,
    )
        # Copy-to-Word buttons are handled by the HEAD script (cross-browser; no Gradio _js dependency).

    # Backwards-compatible return signature expected by rhk_app_web_master.py.
    # Note: on Gradio 6+ the CSS/JS/HEAD/THEME are passed via demo._rhk_launch_kwargs.
    return demo, CSS, theme