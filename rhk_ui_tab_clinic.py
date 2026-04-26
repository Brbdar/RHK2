#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_tab_clinic.py - CHD-Details Handle zurückgegeben (Bugfix), Vorbereitung auf tab-weise Bindings

"""UI submodule (tab builder).

This file contains ONLY Gradio layout for the corresponding tab.
Business logic (case building, interpretation, exports) remains in rhk_ui.py / controllers.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from rhk_base import gr
from rhk_ph_tx import PH_DRUG_CHOICES, PH_TX_STATUS_CHOICES, PH_TX_STOP_REASON_CHOICES


def build_clinic_tab(add: Callable[[str, Any], Any]) -> Dict[str, Any]:
    """Build the tab UI and return component handles needed by the main UI binder."""

    # Card 1: Allgemeines/Anamnese/Vorerkrankungen
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
        hdr_klinik_general = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Allgemeines, Anamnese, Vorerkrankungen</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
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
                _ekg_present = add("ekg_present", gr.Checkbox(label="12-Kanal-EKG vorhanden"))  # noqa: F841
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
            _allergies_present = add("allergies_present", gr.Checkbox(label="Allergien"))  # noqa: F841
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
                _ph_known = add("ph_known", gr.Checkbox(label="PH-Diagnose bekannt"))  # noqa: F841
                _ph_suspected = add("ph_suspected", gr.Checkbox(label="PH-Verdachtsdiagnose"))  # noqa: F841

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

                # ------------------------------------------------------------------
                # PH Therapie (neu): Episoden statt diffuser Mehrfach-Listen
                # - Wiederbeginn = neue Zeile
                # - Eigennamen (Opsumit, Sildenafil, Tadalafil, ...) + Sotatercept
                # - Legacy-Felder bleiben verfügbar (Accordion), werden aber nicht
                #   automatisch überschrieben.
                # ------------------------------------------------------------------

                gr.Markdown(
                    "Therapieepisoden: pro Zeile eine Episode. Wiederbeginn bitte als neue Zeile erfassen. Seit/Bis optional (MM/JJJJ).",
                )

                with gr.Row():
                    ph_tx_add_drug = gr.Dropdown(
                        label="Medikament",
                        choices=PH_DRUG_CHOICES,
                        value=None,
                    )
                    ph_tx_add_status = gr.Dropdown(
                        label="Status",
                        choices=PH_TX_STATUS_CHOICES,
                        value="aktuell",
                    )
                    ph_tx_add_since = gr.Textbox(label="seit (MM/JJJJ)", placeholder="MM/JJJJ")
                    ph_tx_add_until = gr.Textbox(label="bis (MM/JJJJ)", placeholder="MM/JJJJ")

                with gr.Row():
                    ph_tx_add_reason = gr.Dropdown(
                        label="Grund (optional)",
                        choices=PH_TX_STOP_REASON_CHOICES,
                        value="keine Angabe",
                    )
                    ph_tx_add_note = gr.Textbox(label="Kommentar (optional)", lines=1)
                    ph_tx_add_btn = gr.Button("Episode hinzufügen", variant="secondary")
                ph_tx_use_df = False
                ph_tx_table = add(
                    "ph_tx_table",
                    gr.Textbox(
                        label="PH Therapieepisoden (Tab-getrennt)",
                        lines=8,
                        placeholder="Medikament	Status	seit (MM/JJJJ)	bis (MM/JJJJ)	Grund	Kommentar",
                        value="",
                    ),
                )

                with gr.Row():
                    ph_tx_del_idx = gr.Number(label="Zeile löschen (Index, beginnt bei 1)", precision=0)
                    ph_tx_del_btn = gr.Button("Zeile löschen", variant="secondary")
                    ph_tx_from_legacy_btn = gr.Button(
                        "Legacy Therapie in Episoden übernehmen",
                        variant="secondary",
                        visible=False,
                    )

                # Legacy Felder (Alt-Fälle): bleiben erhalten, aber nicht im Hauptfluss
                with gr.Accordion("Legacy PH Therapie Felder (nur Alt-Fälle)", open=False, visible=False) as ph_tx_legacy_acc:
                    ph_med_choices = [
                        "PDE-5-Hemmer",
                        "sGC-Stimulator (Riociguat)",
                        "Endothelin-Rezeptorantagonist (ERA)",
                        "Prostazyklin-Therapie / -Analogon",
                        "IP-Rezeptoragonist (z.B. Selexipag)",
                        "Kalziumantagonist (bei Vasoreaktivität)",
                        "Diuretikum",
                        "Sauerstofftherapie",
                        "Sotatercept (BMPR2/Activin-Pfad)",
                        "Sonstiges",
                    ]
                    add("ph_current_meds", gr.Dropdown(
                        label="Aktuelle Therapie (Legacy, Mehrfachauswahl)",
                        choices=ph_med_choices,
                        multiselect=True,
                        value=[],
                    ))
                    add("ph_prev_meds", gr.Dropdown(
                        label="Frühere Therapie (Legacy, Mehrfachauswahl)",
                        choices=ph_med_choices,
                        multiselect=True,
                        value=[],
                    ))
                    add("ph_tx_status", gr.Dropdown(
                        label="Therapie-Verlauf seit letzter Kontrolle (Legacy)",
                        choices=["keine Angabe", "unverändert", "neu begonnen", "eskaliert", "deeskaliert", "abgesetzt", "pausiert"],
                        value="keine Angabe",
                    ))
                    add("ph_new_meds", gr.Dropdown(
                        label="Neu begonnen / hinzugefügt (Legacy, Mehrfachauswahl)",
                        choices=ph_med_choices,
                        multiselect=True,
                        value=[],
                    ))
                    add("ph_stopped_meds", gr.Dropdown(
                        label="Abgesetzt / pausiert (Legacy, Mehrfachauswahl)",
                        choices=ph_med_choices,
                        multiselect=True,
                        value=[],
                    ))
                    add("ph_stop_reason", gr.Dropdown(
                        label="Grund für Absetzen/Pause (Legacy, optional)",
                        choices=PH_TX_STOP_REASON_CHOICES,
                        value="keine Angabe",
                    ))
                    add("ph_stop_reason_text", gr.Textbox(label="Details (Legacy, optional)", lines=2, placeholder="z.B. Hypotonie, Kopfschmerz, Blutung …"))

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
        hdr_klinik_symptoms = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Funktion / Symptome</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
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
        hdr_klinik_labs = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Labor</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
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

            # Studien Screening (Labor, klickbasiert)
            with gr.Row():
                _tri = ["Unklar / nicht erhoben", "Nein", "Ja"]
                add("study_liver_pathologic", gr.Dropdown(label="Leberwerte pathologisch (Screening)", choices=_tri, value=_tri[0]))
                add("study_renal_pathologic", gr.Dropdown(label="Nierenfunktion klinisch relevant eingeschränkt (Screening)", choices=_tri, value=_tri[0]))

    # Card 4: Medikation & wichtige Zusatzangaben
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
        hdr_klinik_meds = gr.HTML("<div class='rhk-sec-head'><div class='rhk-sec-title'>Medikation & wichtige Zusatzangaben</div><div class='rhk-sec-progress'><span class='rhk-sec-count'>0/0</span><div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' aria-valuemin='0' aria-valuemax='100'><div style='width:0%'></div></div></div></div>")
        with gr.Column(elem_classes=["rhk-sec-body"]):
            # Antikoagulation (wichtig v.a. für CTEPH-/Embolie-Logik)
            with gr.Row():
                _anticoag_status = add(  # noqa: F841
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
                        visible=True,
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
                        visible=True,
                    ),
                )
                anticoag_since = add(
                    "anticoag_since",
                    gr.Textbox(
                        label="seit wann (optional)",
                        placeholder="MM/JJJJ",
                        visible=True,
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
            _pde5_hardship = add("pde5_hardship", gr.Checkbox(  # noqa: F841
                label="PDE-5 außerhalb Gruppe 1: Härtefall-Ausnahme dokumentiert",
                value=False,
            ))
            _pde5_hardship_desc = add("pde5_hardship_desc", gr.Textbox(  # noqa: F841
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

    return {
        "hdr_klinik_general": hdr_klinik_general,
        "hdr_klinik_symptoms": hdr_klinik_symptoms,
        "hdr_klinik_labs": hdr_klinik_labs,
        "hdr_klinik_meds": hdr_klinik_meds,
        "anemia_type": anemia_type,
        "allergies_details": allergies_details,
        "chd_details": chd_details,
        "ekg_details": ekg_details,
        "ph_known_details": ph_known_details,
        "anticoag_substance": anticoag_substance,
        "anticoag_indication": anticoag_indication,
        "anticoag_since": anticoag_since,
        "anticoag_note": anticoag_note,
        "anticoag_paused": anticoag_paused,
        "ph_tx_use_df": ph_tx_use_df,
        "ph_tx_add_drug": ph_tx_add_drug,
        "ph_tx_add_status": ph_tx_add_status,
        "ph_tx_add_since": ph_tx_add_since,
        "ph_tx_add_until": ph_tx_add_until,
        "ph_tx_add_reason": ph_tx_add_reason,
        "ph_tx_add_note": ph_tx_add_note,
        "ph_tx_add_btn": ph_tx_add_btn,
        "ph_tx_table": ph_tx_table,
        "ph_tx_del_idx": ph_tx_del_idx,
        "ph_tx_del_btn": ph_tx_del_btn,
        "ph_tx_from_legacy_btn": ph_tx_from_legacy_btn,
        "ph_tx_legacy_acc": ph_tx_legacy_acc,
    }
