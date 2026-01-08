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
    markdown_to_docx_file,
    extract_markdown_section,
    load_case_json,
)  # noqa: F401
from rhk_import_docx import parse_maclab_docx, map_payload_to_ui  # noqa: F401
from rhk_ui_echo import build_echo_section, bind_echo_import, render_echo_import_views  # noqa: F401
from rhk_ui_rhk import build_rhk_tab  # noqa: F401

from rhk_ui_assets import CSS, JS_ON_LOAD, HEAD_HTML  # noqa: F401
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

                def add(name: str, comp: gr.components.Component):
                    field_components[name] = comp
                    return comp

                # ---- Tab 1: Klinik & Labor ----
                with gr.TabItem("Klinik & Labor", id=0):

                    # Card 1
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Allgemeines, Anamnese, Vorerkrankungen")
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
                            gr.Markdown("#### Bekannte PH – Details")
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

                    # Card 2
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Funktion / Symptome")
                        with gr.Row():
                            add("who_fc", gr.Dropdown(label="WHO-FC", choices=["keine Angabe", "I", "II", "III", "IV"], value="keine Angabe"))
                            add("six_mwd_m", gr.Number(label="6MWD (m)"))
                            add("six_mwd_date", gr.Textbox(label="6MWD Datum", placeholder="z.B. 01/2026"))
                            add("syncope", gr.Dropdown(label="Synkope", choices=["keine Angabe", "keine", "gelegentlich", "wiederholt"], value="keine Angabe"))
                        with gr.Row():
                            add("hemoptysis", gr.Checkbox(label="Hämoptyse"))
                            add("dizziness", gr.Checkbox(label="Schwindel"))
                            add("stairs_flights", gr.Number(label="Treppen (Etagen) bis Pause", precision=0))

                    # Card 3
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Labor")
                        with gr.Row():
                            add("hb_g_dl", gr.Number(label="Hb (g/dl)"))
                            add("leukocytes_g_l", gr.Number(label="Leukozyten (G/l)"))
                            add("platelets_g_l", gr.Number(label="Thrombozyten (G/l)"))

                        anemia_type = add("anemia_type", gr.Dropdown(
                            label="Anämie-Typ (falls Anämie vorliegt)",
                            choices=["keine Angabe", "mikrozytär", "normozytär", "makrozytär", "hämolytisch", "akute Blutung/Blutverlust", "unklar"],
                            value="keine Angabe",
                            visible=False,
                        ))

                        with gr.Row():
                            add("inr", gr.Number(label="INR"))
                            add("ptt_s", gr.Number(label="PTT (s)"))
                            add("creatinine_mg_dl", gr.Number(label="Kreatinin (mg/dl)"))

                        with gr.Row():
                            add("egfr_ml_min_1_73", gr.Number(label="eGFR (ml/min/1,73m²)", interactive=False))
                            add("crp_mg_l", gr.Number(label="CRP (mg/l)"))
                        with gr.Row():
                            add("bnp_kind", gr.Dropdown(label="BNP/NT-proBNP", choices=["BNP", "NT-proBNP"], value="NT-proBNP"))
                            add("bnp_value", gr.Number(label="Wert (pg/ml)"))
                            add("entresto", gr.Checkbox(label="Entresto/ARNI? (BNP eingeschränkt)"))
                        with gr.Row():
                            add("congestive_organopathy", gr.Radio(label="Hinweis auf congestive Organopathie?", choices=["keine Angabe", "ja", "nein"], value="keine Angabe"))

                    # Card 4
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Medikation & wichtige Zusatzangaben")

                        with gr.Row():
                            anticoag_status = add("anticoag_status", gr.Dropdown(
                                label="Antikoagulation (Blutverdünnung)?",
                                choices=["keine Angabe", "nein", "ja", "ja, aber pausiert", "unklar"],
                                value="keine Angabe",
                            ))
                            anticoag_substance = add("anticoag_substance", gr.Dropdown(
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
                            ))
                        with gr.Row():
                            anticoag_indication = add("anticoag_indication", gr.Dropdown(
                                label="Indikation (falls ja)",
                                choices=["keine Angabe", "Vorhofflimmern", "Venenthrombose/Lungenembolie", "CTEPH/CTEPD", "Mechanische Klappe", "Andere/unklar"],
                                value="keine Angabe",
                                visible=False,
                            ))
                            anticoag_since = add("anticoag_since", gr.Textbox(
                                label="seit wann (optional)",
                                placeholder="MM/JJJJ",
                                visible=False,
                            ))
                        anticoag_note = add("anticoag_note", gr.Textbox(
                            label="Antikoagulation – Bemerkung (optional)",
                            lines=2,
                            visible=False,
                        ))

                        anticoag_paused = add(
                            "anticoag_paused",
                            gr.Checkbox(label="Antikoagulation pausiert?", visible=False),
                        )

                        with gr.Row():
                            add("ltx_eval", gr.Dropdown(
                                label="LTX-Evaluation (Transplantations-Abklärung) erfolgt?",
                                choices=["keine Angabe", "ja", "nein", "unklar"],
                                value="keine Angabe",
                            ))
                            add("ltx_eval_date", gr.Textbox(label="LTX-Evaluation: Datum (optional)", placeholder="MM/JJJJ"))


                # ---- Tab 2: Bildgebung & Echo/CMR (merged) ----

                with gr.TabItem("Bildgebung & Echo/CMR", id=1):
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Thorax-Bildgebung")
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


                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### MRT / CMR (optional)")
                        with gr.Row():
                            add("cmr_done", gr.Checkbox(label="CMR durchgeführt"))
                            add("rvef", gr.Number(label="RV-EF (%)"))
                            add("rvesvi", gr.Number(label="RVESVi (ml/m²)"))

                # ---- Tab 3: Lungenfunktion ----

                with gr.TabItem("Lungenfunktion", id=2):
                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Lungenfunktion")
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

                    with gr.Group(elem_classes=["rhk-card"]):
                        gr.Markdown("### Spiroergometrie / CPET")
                        with gr.Row():
                            add("cpet_done", gr.Checkbox(label="CPET durchgeführt"))
                            add("cpet_protocol", gr.Dropdown(label="Protokoll (optional)", choices=["Rampe", "Stufenprotokoll", "Semi supine", "Laufband", "Sonstiges"], value="Rampe"))
                            add("cpet_site", gr.Textbox(label="Ort/Setup (optional)"))

                        cpet_risk_html = gr.HTML(value="<div class='docx-muted'>Keine CPET Daten erfasst.</div>")

                        with gr.Column(visible=False) as cpet_details:
                            with gr.Row():
                                add("cpet_peak_vo2_ml_kg_min", gr.Number(label="Peak VO2 (ml/min/kg)"))
                                add("cpet_peak_vo2_pct_pred", gr.Number(label="Peak VO2 (% Soll)"))
                            with gr.Row():
                                add("cpet_ve_vco2_slope", gr.Number(label="VE/VCO2 slope"))
                                add("cpet_petco2_vt1_mmhg", gr.Number(label="PETCO2 @ VT1 (mmHg)"))
                            with gr.Row():
                                add("cpet_ve_vco2_vt1", gr.Number(label="VE/VCO2 @ VT1"))
                                add("cpet_peak_o2_pulse_pct_pred", gr.Number(label="Peak O2 Puls (% Soll)"))
                            with gr.Row():
                                add("cpet_vo2_wr_slope_ml_min_w", gr.Number(label="ΔVO2/ΔWR (ml/min/W, optional)"))
                                add("cpet_vo2_vt1_ml_kg_min", gr.Number(label="VO2 @ VT1 (ml/min/kg, optional)"))
                            with gr.Row():
                                add("cpet_spo2_nadir_pct", gr.Number(label="SpO2 Nadir (%), optional"))
                                add("cpet_rer_peak", gr.Number(label="RER peak (Qualität)"))
                                add("cpet_hr_peak_bpm", gr.Number(label="HF peak (/min, optional)"))
                            with gr.Row():
                                add("cpet_o2_pulse_pattern", gr.Dropdown(label="O2 Puls Verlauf (optional)", choices=["normal", "plateau", "fallend", "unbekannt"], value="unbekannt"))
                            add("cpet_summary", gr.Textbox(label="CPET Summary (Freitext)", lines=3))

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

                # ---- Tab 5: Weitere Bereiche ----
                with gr.TabItem("Weitere Befunde", id=4):
                    gr.Markdown("### Blutgase / LTOT")
                    with gr.Row():
                        add("ltot", gr.Checkbox(label="LTOT vorhanden"))
                        ltot_flow = add("ltot_flow_l_min", gr.Number(label="LTOT (l/min)", visible=False))
                    gr.Markdown("### Infektiologie / Immunologie")
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

                    gr.Markdown("### Genetik")
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

                    gr.Markdown("### Abdomen / Leber")
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
                        gr.Markdown("### P-Module (optional)")
                        gr.Markdown("**Level I – prioritäre Empfehlungen** · Level II – sinnvoll ergänzend · Level III – optional")
                        gr.Markdown(
                            "Die P-Module werden automatisch nach Sinnhaftigkeit in **Level I–III** sortiert. "
                            "Nicht passende Module werden **hellgrau** angezeigt und sind nicht anwählbar. "
                            "Falls Sie dennoch Aspekte dokumentieren möchten, nutzen Sie den **Freitext** im Procedere."
                        )

                        with gr.Group(elem_id="pmods_lvl1"):
                            modules_lvl1_comp = add(
                                "modules_lvl1",
                                gr.CheckboxGroup(
                                    label="Level I – prioritäre Empfehlungen",
                                    choices=[],
                                    value=[],
                                    elem_id="pmods_choice_lvl1",
                                ),
                            )

                        with gr.Group(elem_id="pmods_lvl2"):
                            modules_lvl2_comp = add(
                                "modules_lvl2",
                                gr.CheckboxGroup(
                                    label="Level II – sinnvoll ergänzend",
                                    choices=[],
                                    value=[],
                                    elem_id="pmods_choice_lvl2",
                                ),
                            )

                        with gr.Group(elem_id="pmods_lvl3"):
                            modules_lvl3_comp = add(
                                "modules_lvl3",
                                gr.CheckboxGroup(
                                    label="Level III – optional",
                                    choices=base_module_choices,
                                    value=[],
                                    elem_id="pmods_choice_lvl3",
                                ),
                            )

                    add("procedere_free", gr.Textbox(label="Procedere – Freitext", lines=3, elem_id="procedere_free"))
                    gr.Markdown("Hinweis: Bereits durchgeführte Untersuchungen werden in den Modulen möglichst ausgefiltert (z.B. V/Q, CT, Echo, Lufu).")

            with gr.Column(scale=5):
                dashboard = gr.HTML(value=build_dashboard_html(None))

                # Copy/paste helpers (plain text, no formatting chaos)
                with gr.Row(elem_id="rhk_copy_row"):
                    btn_copy_doc = gr.Button("Arztbericht kopieren", variant="secondary", elem_id="btn_copy_doc")
                    btn_download_doc = gr.DownloadButton("DOCX", variant="secondary", elem_id="btn_download_doc")
                    btn_copy_pat = gr.Button("Patient*innenbrief komplett kopieren", variant="secondary", elem_id="btn_copy_pat")
                    btn_copy_rhk = gr.Button("nur RHK Abschnitt kopieren", variant="secondary", elem_id="btn_copy_rhk")
                copy_feedback = gr.Markdown("", elem_id="rhk_copy_feedback")


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
                             allergies_present, allergies_list, allergies_other_text):
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
        _bind_change(field_components["creatinine_mg_dl"], _update_egfr, inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[field_components["egfr_ml_min_1_73"]])
        _bind_change(field_components["age"], _update_egfr, inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[field_components["egfr_ml_min_1_73"]])
        _bind_change(field_components["sex"], _update_egfr, inputs=[field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[field_components["egfr_ml_min_1_73"]])

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
                _bind_change(field_components[_k], _sync_post_load_cpet, inputs=_cpet_inputs, outputs=[cpet_details, cpet_risk_html])
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
            ]
            # Update on any of these changes
            for _k in (
                "consent_done", "access_route", "inr", "ptt_s", "platelets_g_l",
                "anticoag_status", "anticoag_paused", "crp_mg_l",
                "creatinine_mg_dl", "age", "sex",
                "allergies_present", "allergies_list", "allergies_other_text",
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

        try:
            _bind_change(field_components["allergies_present"], _toggle_allergies, inputs=[field_components["allergies_present"]], outputs=[allergies_details])
            _bind_change(field_components["allergies_list"], _toggle_allergies_other, inputs=[field_components["allergies_list"]], outputs=[field_components["allergies_other_text"]])
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

            remembered_name = (case_filename_state or '').strip()
            # Normalize: ensure .json extension
            if remembered_name and not remembered_name.lower().endswith('.json'):
                remembered_name = remembered_name + '.json'

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
            case = build_case(raw, rules)

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
            # Copy/paste payloads
            # - plain text for systems that break on rich formatting
            # - HTML for Word (clipboard text/html)
            try:
                doc_copy_md = build_doctor_report_for_copy(case, blocks)

                doc_plain = markdown_to_plain(doc_copy_md)
                pat_plain = markdown_to_plain(pat)
                rhk_section = extract_markdown_section(doc, "Rechtsherzkatheter", "Beurteilung")
                rhk_plain = markdown_to_plain(rhk_section)

                doc_html = markdown_to_word_html(doc_copy_md)
                pat_html = markdown_to_word_html(pat)
                rhk_html = markdown_to_word_html(rhk_section)
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

            # --- P-Module UI: fallbasiert sortieren + nicht anwählbare Module (hellgrau) anzeigen ---
            policy = der.get("p_module_policy") or {}
            mod_choices = build_p_module_choices(blocks, policy)
            disabled_html = build_disabled_p_modules_html(blocks, policy)

            # --- Live preview layers ---
            # Status: report is now up-to-date
            flags["has_report"] = True
            flags["report_stale"] = False
            flags["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            try:
                flags["warnings"] = case.get("warnings") or []
            except Exception:
                flags["warnings"] = []

            summary_html = build_sticky_summary_html(case, flags)
            compare_html = build_compare_overview_html(case)
            cards_html = build_p_module_cards_html(blocks, case)
            # --- DOCX Import: attach raw payloads into case for transparency/QA ---
            try:
                case.setdefault("imports", {})["docx_current"] = docx_cur_state
                case.setdefault("imports", {})["docx_prev"] = docx_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
                case.setdefault("imports", {})["echo_cur"] = echo_cur_state
                case.setdefault("imports", {})["echo_prev"] = echo_prev_state
            except Exception:
                pass

            # --- Import status + plots (never raise) ---
            try:
                status_html = build_docx_status_html(docx_cur_state, docx_prev_state)
            except Exception:
                status_html = ""
            try:
                plots_html = build_rhk_plots_html(case, docx_cur_state, docx_prev_state)
            except Exception:
                plots_html = ""

            allowed_vals = {v for (_, v) in mod_choices}

            # Sichtbarkeit/Logik vereinheitlichen:
            # - "Auto"-Module aus dem Regelwerk (case.decision.modules) werden im Bericht verwendet,
            #   sollen aber auch in der UI als "vorselektiert" sichtbar sein.
            auto_mods = _normalize_module_ids((case.get("decision") or {}).get("modules") or [])
            sel_vals = _normalize_module_ids(case.get("ui", {}).get("modules") or [])

            # Auto + User-Auswahl zusammenführen (dedup, Reihenfolge: Auto zuerst)
            sel_vals = list(dict.fromkeys(auto_mods + sel_vals))

            # Nur erlaubte Module behalten
            sel_vals = [m for m in sel_vals if m in allowed_vals]

            # In den Case-State zurückschreiben, damit Save/Live-Update konsistent bleibt
            try:
                case.setdefault("ui", {})["modules"] = sel_vals
            except Exception:
                pass


            # --- P-Module UI: robust gegen Gradio-Versionen ---
            # Wir nutzen reine Label-Strings als Choices und Values.
            # Label ohne '[I]/[II]/[III]' Prefix, da Level bereits durch getrennte Gruppen abgebildet wird.
            import re
            def _clean_pmod_label(lab: Any) -> str:
                s = str(lab) if lab is not None else ""
                s = re.sub(r"^\s*\[[^\]]+\]\s*", "", s).strip()
                return s
            
            levels_map = (policy.get("levels") or {}) if isinstance(policy, dict) else {}
            id_to_label = {mid: _clean_pmod_label(lab) for (lab, mid) in mod_choices}
            id_to_level = {mid: int(levels_map.get(mid, 3)) for (_lab, mid) in mod_choices}
            
            choices_lvl1 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 1]
            choices_lvl2 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 2]
            choices_lvl3 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) not in (1, 2)]
            
            allowed_lvl1_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 1}
            allowed_lvl2_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 2}
            allowed_lvl3_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) not in (1, 2)}
            
            selected_lvl1_ids = [m for m in sel_vals if m in allowed_lvl1_ids]
            selected_lvl2_ids = [m for m in sel_vals if m in allowed_lvl2_ids]
            selected_lvl3_ids = [m for m in sel_vals if m in allowed_lvl3_ids]
            
            selected_lvl1 = [id_to_label.get(mid) for mid in selected_lvl1_ids if id_to_label.get(mid)]
            selected_lvl2 = [id_to_label.get(mid) for mid in selected_lvl2_ids if id_to_label.get(mid)]
            selected_lvl3 = [id_to_label.get(mid) for mid in selected_lvl3_ids if id_to_label.get(mid)]

            pmods_sel_state = {
                "lvl1": selected_lvl1,
                "lvl2": selected_lvl2,
                "lvl3": selected_lvl3,
            }

            
            modules_lvl1_update = gr.update(choices=choices_lvl1, value=[])
            modules_lvl2_update = gr.update(choices=choices_lvl2, value=[])
            modules_lvl3_update = gr.update(choices=choices_lvl3, value=[])
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

        def _export_doctor_docx(case_state: Any):
            """Create a formatted DOCX for the doctor report (copy layout).

            Uses ONLY the copy layout. The in-app report stays unchanged.
            """
            import os
            import tempfile
            import time

            if not isinstance(case_state, dict):
                raise gr.Error("Bitte zuerst den Befund erstellen, dann DOCX herunterladen.")

            # Build a single DOCX that contains:
            # 1) Doctor report (copy layout)
            # 2) Patient RHK report
            # 3) Patient Echo report
            # The in-app report remains unchanged.
            md_doc = build_doctor_report_for_copy(case_state, blocks)
            md_pat_rhk = build_patient_report(case_state)
            md_pat_echo = build_echo_patient_report(case_state)

            md = "\n\n".join(
                [
                    "## Arztbericht",
                    str(md_doc or "").strip(),
                    "[[PAGEBREAK]]",
                    "## Patientenbericht – Rechtsherzkatheter",
                    str(md_pat_rhk or "").strip(),
                    "[[PAGEBREAK]]",
                    "## Patientenbericht – Echokardiographie",
                    str(md_pat_echo or "").strip(),
                ]
            ).strip()

            # Deterministic, safe filename stub (avoid patient identifiers in file name by default)
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(tempfile.gettempdir(), f"rhk_arztbericht_{ts}.docx")

            markdown_to_docx_file(md, out_path)
            return out_path

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
            sticky_summary_html,
            compare_overview_html,
            rhk_plots_html,
            import_status_html,
            modules_cards_html,
        ]

        btn_generate_top.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        btn_generate_bottom.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        # DOCX export for the doctor report (copy layout)
        btn_download_doc.click(
            _export_doctor_docx,
            inputs=[state_case],
            outputs=[btn_download_doc],
        )
        # --- Live status update (debounced client ping) ---
        # Instead of attaching a .change handler to dozens of inputs (slow + triggers during bulk programmatic updates),
        # we use ONE hidden textbox that the browser updates (debounced) whenever the user edits any input.
        # Procedere/Module are handled by _update_procedere_only and therefore excluded from the client ping.
        def _on_dirty_ping(flags_state, case_state, _ping_val: str):
            flags = dict(flags_state or {})

            flags["dirty"] = True
            if bool(flags.get("has_report")):
                flags["report_stale"] = True

            # Keep warnings from last generation for visibility; do not recompute.
            try:
                if "warnings" not in flags or flags.get("warnings") is None:
                    flags["warnings"] = (case_state or {}).get("warnings") or []
                else:
                    flags["warnings"] = list(flags.get("warnings") or [])
            except Exception:
                flags["warnings"] = []

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
                    gr.update(),  # modules_cards_html
                )
            flags = dict(flags_state or {})
            try:
                ui = dict(case_state.get("ui") or {})
                ui["modules_lvl1"] = m1 or []
                ui["modules_lvl2"] = m2 or []
                ui["modules_lvl3"] = m3 or []
                ui["procedere_free"] = free_text or ""
                ui["modules"] = _normalize_module_ids(
                    (ui.get("modules_lvl1") or []) + (ui.get("modules_lvl2") or []) + (ui.get("modules_lvl3") or [])
                )
                case_state["ui"] = ui

                doc = build_doctor_report(case_state, blocks)
                pat = build_patient_report(case_state)
                echo_doc = build_echo_doctor_report_extended(case_state)
                echo_pat = build_echo_patient_report(case_state)
                internal = build_internal_report(case_state)

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
                    doc_plain = markdown_to_plain(doc)
                    pat_plain = markdown_to_plain(pat)
                    rhk_section = extract_markdown_section(doc, "Rechtsherzkatheter", "Beurteilung")
                    rhk_plain = markdown_to_plain(rhk_section)

                    doc_html = markdown_to_word_html(doc_copy_md)
                    pat_html = markdown_to_word_html(pat)
                    rhk_html = markdown_to_word_html(rhk_section)
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
                    doc,
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
            return {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}

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

        btn_example_top.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected, state_case_filename])\
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html, details_echo_html, btn_echo_apply, state_case_filename])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        btn_example_bottom.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected, state_case_filename])\
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html, details_echo_html, btn_echo_apply, state_case_filename])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])


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
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])
            btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs, queue=False)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])
        except TypeError:
            # Older Gradio builds may not support queue=...
            btn_clear_top.click(_clear_all, inputs=[], outputs=load_outputs)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])
            btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs)\
                .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])


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

        save_btn_top.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])\
            .then(_save_case, inputs=[state_case, state_flags, state_case_filename], outputs=_save_outputs)
        save_btn_bottom.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])\
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

        docx_btn_top.upload(_docx_import_current, inputs=[docx_btn_top, state_docx_cur] + input_components, outputs=input_components + [state_docx_cur])\
            .then(_reset_pmods_after_import, inputs=[], outputs=[state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        docx_btn_bottom.upload(_docx_import_current, inputs=[docx_btn_bottom, state_docx_cur] + input_components, outputs=input_components + [state_docx_cur])\
            .then(_reset_pmods_after_import, inputs=[], outputs=[state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        prev_docx_btn.upload(_docx_import_prev, inputs=[prev_docx_btn, state_docx_prev] + input_components, outputs=input_components + [state_docx_prev])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

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
                _generate,
                inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components,
                outputs=generate_outputs,
            )

        if btn_wipe_docx_prev is not None:
            btn_wipe_docx_prev.click(
                _wipe_docx_prev,
                inputs=[state_docx_prev] + input_components,
                outputs=input_components + [state_docx_prev],
            ).then(
                _generate,
                inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components,
                outputs=generate_outputs,
            )

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
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

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
            .then(_sync_post_load, inputs=[field_components["ct_done"], field_components["ct_ild"], field_components["vq_done"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"]], outputs=[ct_desc_col, acc_ild, field_components["ild_extent"], ild_tx_details, acc_vq, field_components["egfr_ml_min_1_73"], allergies_details, field_components["allergies_other_text"]])\
            .then(_sync_post_load_cpet, inputs=[field_components["cpet_done"], field_components["cpet_peak_vo2_ml_kg_min"], field_components["cpet_peak_vo2_pct_pred"], field_components["cpet_ve_vco2_slope"], field_components["cpet_petco2_vt1_mmhg"], field_components["cpet_ve_vco2_vt1"], field_components["cpet_peak_o2_pulse_pct_pred"], field_components["cpet_vo2_wr_slope_ml_min_w"], field_components["cpet_vo2_vt1_ml_kg_min"], field_components["cpet_spo2_nadir_pct"], field_components["cpet_rer_peak"], field_components["cpet_hr_peak_bpm"], field_components["cpet_o2_pulse_pattern"]], outputs=[cpet_details, cpet_risk_html])\
            .then(_update_pre_cath_both, inputs=[field_components["consent_done"], field_components["access_route"], field_components["inr"], field_components["ptt_s"], field_components["platelets_g_l"], field_components["anticoag_status"], field_components["anticoag_paused"], field_components["crp_mg_l"], field_components["creatinine_mg_dl"], field_components["age"], field_components["sex"], field_components["allergies_present"], field_components["allergies_list"], field_components["allergies_other_text"]], outputs=[pre_cath_html, pre_cath_home_html])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev, state_echo_cur, state_echo_prev, state_case_filename] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        # Copy-to-Word buttons are handled by the HEAD script (cross-browser; no Gradio _js dependency).

    # Backwards-compatible return signature expected by rhk_app_web_master.py.
    # Note: on Gradio 6+ the CSS/JS/HEAD/THEME are passed via demo._rhk_launch_kwargs.
    return demo, CSS, theme