#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK-Tab UI (Layout only)."""

from __future__ import annotations

from typing import Any, Dict

from rhk_base import gr  # type: ignore

# Reuse the exact same renderer as the global Hämodynamik sticky header
from rhk_ui_utils import build_pre_cath_header_html


def build_rhk_tab(add) -> Dict[str, Any]:
    """Build the RHK tab UI and return key components."""

    # -------------------------------------------------------------
    # Pre-Cath Safety Header (sticky bar just under global summary)
    # -------------------------------------------------------------
    pre_cath_html = gr.HTML(
        value=build_pre_cath_header_html({}),
        elem_id="rhk_pre_cath_wrapper",
    )
    with gr.Row():
        add("consent_done", gr.Checkbox(label="Aufklärung erfolgt (RHK)"))
        add(
            "access_route",
            gr.Dropdown(
                label="Zugangsweg",
                choices=["", "V. jugularis rechts", "V. jugularis links", "unbekannt", "cave - schwierig"],
                value="",
            ),
        )

    # =============================================================
    # DOCX Import Übersicht (Quelle der Wahrheit)
    # =============================================================
    with gr.Accordion("DOCX Import Übersicht (Quelle der Wahrheit)", open=True, elem_id="docx_overview_acc"):
        import_status_html = gr.HTML(
            value="<div class='docx-muted'>Noch kein DOCX importiert.</div>",
            elem_id="import_status_html",
        )

    # Plots bewusst als eigener, separater Block
    with gr.Accordion("Plots & Verlauf", open=False, elem_id="rhk_plots_acc"):
        rhk_plots_html = gr.HTML(value="", elem_id="rhk_plots_html")

    # -------------------------------------------------------------
    # Ruhehämodynamik
    # -------------------------------------------------------------
    gr.Markdown("### Ruhehämodynamik")
    with gr.Row():
        add("spap_rest", gr.Number(label="sPAP (mmHg)"))
        add("dpap_rest", gr.Number(label="dPAP (mmHg)"))
        add("mpap_rest", gr.Number(label="mPAP (optional)"))
    with gr.Row():
        add("pawp_rest", gr.Number(label="PAWP (mmHg)"))
        add("rap_rest", gr.Number(label="RAP (mmHg)"))
    with gr.Row():
        add("co_rest", gr.Number(label="CO (l/min)"))
        add("ci_rest", gr.Number(label="CI (optional)"))
        add("pvr_rest", gr.Number(label="PVR (optional, WU)"))
        add(
            "co_method",
            gr.Dropdown(
                label="HZV Methode",
                choices=["keine Angabe", "Thermodilution", "Fick"],
                value="keine Angabe",
            ),
        )

    gr.Markdown("#### Auto-Berechnung (wird nach \u201eBefund erstellen\u201c gefüllt)")
    with gr.Row():
        auto_mpap = gr.Number(label="mPAP (berechnet)", interactive=False)
        auto_ci = gr.Number(label="CI (berechnet)", interactive=False)
        auto_pvr = gr.Number(label="PVR (berechnet)", interactive=False)
    with gr.Row():
        auto_pvri = gr.Number(label="PVRi (berechnet)", interactive=False)
        auto_tpg = gr.Number(label="TPG (berechnet)", interactive=False)
        auto_dpg = gr.Number(label="DPG (berechnet)", interactive=False)

    # -------------------------------------------------------------
    # Belastung / Volumen / Vaso / Oximetrie / Kurven
    # -------------------------------------------------------------
    gr.Markdown("### Belastungshämodynamik (optional)")
    with gr.Row():
        add(
            "exercise_protocol",
            gr.Dropdown(
                choices=["", "WHO-Rampe", "Stufenprotokoll", "Laufband", "unbekannt"],
                value="",
                label="Belastungsprotokoll",
            ),
        )
        add("exercise_peak_watts", gr.Number(label="Max. Last (W)"))
    with gr.Row():
        add("exercise_done", gr.Checkbox(label="Belastung durchgeführt"))
        add("spap_peak", gr.Number(label="sPAP Peak (mmHg)"))
        add("dpap_peak", gr.Number(label="dPAP Peak (mmHg)"))
        add("mpap_peak", gr.Number(label="mPAP Peak (optional)"))
    with gr.Row():
        add("pawp_peak", gr.Number(label="PAWP Peak (mmHg)"))
        add("co_peak", gr.Number(label="CO Peak (l/min)"))
        add("ci_peak", gr.Number(label="CI Peak (l/min/m²) (optional)"))

    gr.Markdown("### Volumenchallenge (optional)")
    with gr.Row():
        add("volume_challenge_done", gr.Checkbox(label="Volumenchallenge durchgeführt"))
        add("pawp_pre", gr.Number(label="PAWP pre (mmHg)"))
        add("pawp_post", gr.Number(label="PAWP post (mmHg)"))
    with gr.Row():
        add("mpap_pre", gr.Number(label="mPAP pre (mmHg)"))
        add("mpap_post", gr.Number(label="mPAP post (mmHg)"))

    gr.Markdown("### Vasoreaktivität (optional)")
    with gr.Row():
        add("vaso_test_done", gr.Checkbox(label="Vasoreaktivität getestet"))
        add("vaso_agent", gr.Textbox(label="Agent (z.B. iNO)", lines=1))
    add("vaso_response_desc", gr.Textbox(label="Antwort / Kommentar", lines=2))
    with gr.Row():
        add("vaso_mpap_pre", gr.Number(label="mPAP vor Test (mmHg)", precision=0))
        add("vaso_co_pre", gr.Number(label="CO vor Test (L/min)", precision=2))
        add("vaso_mpap_post", gr.Number(label="mPAP nach Test (mmHg)", precision=0))
        add("vaso_co_post", gr.Number(label="CO nach Test (L/min)", precision=2))

    gr.Markdown("### Stufenoxymetrie (optional)")
    with gr.Row():
        add("sat_svc", gr.Number(label="SVC O2-Sättigung (%)"))
        add("sat_ivc", gr.Number(label="IVC O2-Sättigung (%)"))
        add("sat_ra", gr.Number(label="RA O2-Sättigung (%)"))
    with gr.Row():
        add("sat_rv", gr.Number(label="RV O2-Sättigung (%)"))
        add("sat_pa", gr.Number(label="PA O2-Sättigung (%)"))
        add("sat_ao", gr.Number(label="Aorta O2-Sättigung (%)"))

    gr.Markdown("### Kurvenmorphologie (optional)")
    with gr.Row():
        add("wedge_v_wave", gr.Checkbox(label="Prominente V-Welle (PAWP)"))
        add("wedge_a_wave", gr.Checkbox(label="Prominente A-Welle (PAWP)"))
        add("rap_a_wave", gr.Checkbox(label="Prominente A-Welle (RAP)"))
        add("rap_v_wave", gr.Checkbox(label="Prominente V-Welle (RAP)"))
    with gr.Row():
        add("rv_pseudo_dip", gr.Checkbox(label="Pseudo-Dip (RV-Kurve)"))
        add("rv_dip_plateau", gr.Checkbox(label="Dip-Plateau (RV-Kurve)"))

    # -------------------------------------------------------------
    # Verlauf / Vergleich
    # -------------------------------------------------------------
    gr.Markdown("### Verlauf / Vergleich (Vor-RHK, optional)")

    with gr.Row():
        prev_docx_btn = gr.UploadButton(
            "Vor-RHK import (.docx)",
            file_types=[".docx"],
            variant="secondary",
            elem_id="btn_docx_prev",
        )

    with gr.Row():
        add("rhk_date", gr.Textbox(label="Aktueller RHK (z.B. 12/25)", placeholder="MM/JJ oder TT.MM.JJJJ"))
        add("prev_rhk_date", gr.Textbox(label="Vor-RHK (z.B. 03/21)"))
        add("prev_is_initial", gr.Checkbox(label="Vor-RHK war Initialkatheter"))

    with gr.Row():
        add("prev_mpap", gr.Number(label="mPAP vor (mmHg)"))
        add("prev_pawp", gr.Number(label="PAWP vor (mmHg)"))
        add("prev_rap", gr.Number(label="RAP vor (mmHg)"))

    with gr.Row():
        add("prev_ci", gr.Number(label="CI vor (l/min/m²)"))
        add("prev_pvr", gr.Number(label="PVR vor (WU)"))
        add("prev_label", gr.Textbox(label="Kommentar (optional)"))

    compare_overview_html = gr.HTML(value="", elem_id="rhk_compare_overview")

    gr.Markdown(
        "**Therapie seit Vor-RHK (optional):** Nur relevant, wenn es sich um eine Verlaufskontrolle nach Therapieanpassung handelt."
    )

    add(
        "prev_tx_added",
        gr.CheckboxGroup(
            label="Therapie neu/eskaliert",
            choices=[
                "ERA (Endothelin-Rezeptor-Antagonist)",
                "PDE5-Hemmer",
                "sGC-Stimulator (Riociguat)",
                "Prostazyklin (inhalativ/IV/SC)",
                "IP-Rezeptor-Agonist (Selexipag)",
                "Kalziumantagonist (bei Vasoreaktivität)",
                "Antikoagulation",
                "Diuretika / Entwässerung",
                "Sauerstofftherapie",
                "Sonstiges",
            ],
            value=[],
        ),
    )

    add("prev_tx_free", gr.Textbox(label="Therapie – Freitext (optional)", lines=2))

    return {
        "import_status_html": import_status_html,
        "rhk_plots_html": rhk_plots_html,
        "compare_overview_html": compare_overview_html,
        "prev_docx_btn": prev_docx_btn,
        "auto_mpap": auto_mpap,
        "auto_ci": auto_ci,
        "auto_pvr": auto_pvr,
        "auto_pvri": auto_pvri,
        "auto_tpg": auto_tpg,
        "auto_dpg": auto_dpg,
        "pre_cath_html": pre_cath_html,
    }
