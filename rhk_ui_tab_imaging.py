#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.25: rhk_ui_tab_imaging.py - Bildgebung/Echo/CMR-Tab extrahiert (View), Echo-Import-Refs konsolidiert

"""UI submodule (tab builder).

This file contains ONLY Gradio layout for the corresponding tab.
Business logic (case building, interpretation, exports) remains in rhk_ui.py / controllers.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from rhk_base import gr
from rhk_ui_echo import build_echo_section


def build_imaging_tab(add: Callable[[str, Any], Any]) -> Dict[str, Any]:
    """Build the tab UI and return component handles needed by the main UI binder."""

    # Card 1: Thorax-Bildgebung
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
        hdr_imaging = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Thorax-Bildgebung</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
        with gr.Column(elem_classes=["rhk-sec-body"]):
            with gr.Row():
                add("ct_done", gr.Checkbox(label="CT Thorax/CT-Angio durchgeführt"))
                add("vq_done", gr.Checkbox(label="V/Q durchgeführt"))
            # CT Thorax – Befundtext nur sichtbar wenn CT durchgeführt
            with gr.Column(visible=False) as ct_desc_col:
                add("ct_desc", gr.Textbox(label="CT Thorax – Kurzbefund", lines=3))

                # PVOD/PCH – CT Zeichen (optional; rein dokumentierend)
                with gr.Accordion("PVOD/PCH – CT Zeichen (optional)", open=False):
                    with gr.Row():
                        add("ct_pvod_gg", gr.Checkbox(label="Milchglasareale (zentrolobulär)", value=False))
                        add("ct_pvod_septal", gr.Checkbox(label="Septenlinien / Septenverdickung", value=False))
                        add("ct_pvod_ln", gr.Checkbox(label="Mediastinale LK-Vergrößerung", value=False))
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
                _antifib_status = add("antifibrotic_status", gr.Dropdown(  # noqa: F841
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

                # Zusätzliche CTEPH Diagnostik/Board (nur dokumentieren, keine stillen Annahmen)
                with gr.Row():
                    _vq_pa_angio_done = add(  # noqa: F841
                        "vq_pa_angio_done",
                        gr.Checkbox(label="PA Angio durchgeführt", value=False),
                    )
                    _vq_cteph_conf_done = add(  # noqa: F841
                        "vq_cteph_conf_done",
                        gr.Checkbox(label="CTEPH Konferenz erfolgt", value=False),
                    )

                # PA Angio Befund (nur sichtbar wenn aktiviert)
                _vq_pa_angio_desc = add(  # noqa: F841
                    "vq_pa_angio_desc",
                    gr.Textbox(label="PA Angio – Befund", lines=2, visible=False),
                )

                # CTEPH Konferenz Details (nur sichtbar wenn aktiviert)
                with gr.Row():
                    _vq_cteph_conf_date = add(  # noqa: F841
                        "vq_cteph_conf_date",
                        gr.Textbox(label="CTEPH Konferenz: Datum", placeholder="TT.MM.JJJJ", visible=False),
                    )
                _vq_cteph_conf_decision = add(  # noqa: F841
                    "vq_cteph_conf_decision",
                    gr.Textbox(label="CTEPH Konferenz: Beschluss", lines=3, visible=False),
                )

                # CTEPD ohne PH – strukturierte Kriterien
                # Nur sichtbar, wenn V/Q pathologisch markiert ist (keine stillen Annahmen)
                with gr.Column(visible=False) as ctepd_no_ph_col:
                    gr.HTML(
                        "<div class='docx-muted'>CTEPD ohne PH: bitte Kriterien aktiv bestätigen (keine automatische Diagnose ohne bestätigte Chronizität und morphologische Läsionen).</div>"
                    )
                    with gr.Row():
                        add(
                            "ctepd_symptoms",
                            gr.Checkbox(
                                label="Symptome oder objektive Belastungslimitierung passend (z.B. Dyspnoe, reduzierte Leistungsfähigkeit, Desaturation)",
                                value=False,
                            ),
                        )
                    with gr.Row():
                        add(
                            "ctepd_chronicity_3m_ak",
                            gr.Checkbox(
                                label="Chronizität gesichert (mindestens 3 Monate therapeutische Antikoagulation nach akuter PE)",
                                value=False,
                            ),
                        )
                    with gr.Row():
                        add(
                            "ctepd_chronic_lesions",
                            gr.Checkbox(
                                label="CTPA oder DSA: Zeichen chronischer organisierter thromboembolischer Läsionen (z.B. webs, ringförmige Stenosen, slits, pouch, tapering, chronische Okklusion)",
                                value=False,
                            ),
                        )
                    add(
                        "ctepd_lesions_desc",
                        gr.Textbox(
                            label="CTPA oder DSA: Details (optional)",
                            lines=2,
                            placeholder="kurz beschreiben (z.B. webs segmental, pouch in A. pulmonalis dextra …)",
                        ),
                    )
    # Card 2: Echokardiographie
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
        hdr_echo = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Echokardiographie</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
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
        hdr_cmr = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>MRT / CMR</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
        with gr.Column(elem_classes=["rhk-sec-body"]):
            with gr.Row():
                add("cmr_done", gr.Checkbox(label="CMR durchgeführt"))
                add("rvef", gr.Number(label="RVEF (%)"))
            with gr.Row():
                add("rvedv", gr.Number(label="RVEDV (ml)"))
                add("rvesv", gr.Number(label="RVESV (ml)"))
                # Index-Volumina sind abgeleitet (EDV/ESV + BSA) und werden daher als read-only gefuehrt.
                add("rvedvi", gr.Number(label="RVEDVi (ml/m²)", interactive=False))
                add("rvesvi", gr.Number(label="RVESVi (ml/m²)", interactive=False))

    return {
        "hdr_imaging": hdr_imaging,
        "hdr_echo": hdr_echo,
        "hdr_cmr": hdr_cmr,
        "ct_desc_col": ct_desc_col,
        "acc_ild": acc_ild,
        "ild_tx_details": ild_tx_details,
        "acc_vq": acc_vq,
        "ctepd_no_ph_col": ctepd_no_ph_col,
        "echo_ui": echo_ui,
        "import_pdf_cur": import_pdf_cur,
        "import_pdf_prev": import_pdf_prev,
        "import_preview_cur_html": import_preview_cur_html,
        "import_preview_prev_html": import_preview_prev_html,
        "compare_echo_html": compare_echo_html,
        "details_echo_html": details_echo_html,
        "state_echo_cur": state_echo_cur,
        "state_echo_prev": state_echo_prev,
        "btn_echo_apply": btn_echo_apply,
        "btn_echo_clear": btn_echo_clear,
        "btn_echo_clear_prev": btn_echo_clear_prev,
        "antifib_drug": antifib_drug,
        "antifib_since": antifib_since,
        "antifib_note": antifib_note,
    }
