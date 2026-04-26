#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPET / Spiroergometrie tab — ground-up redesign.

Rationale
---------
The legacy layout stacked 11 nested tab items with ~80 fields and preserved
multiple legacy duplicates (``cpet_borg_dyspnea``/``cpet_borg_dyspnoe`` etc.).
The new layout follows progressive disclosure:

1.  **Header** — "CPET durchgeführt" gate + live risk chips.
2.  **Kerndaten** (always visible) — the ESC/ERS-2022 core parameters: effort,
    peak V'O2, V'E/V'CO2-slope, PETCO2, O2-pulse.
3.  **Ventilation & Muster** (collapsible) — breathing mechanics, 9-panel,
    quality/safety details.
4.  **Synthese** — live Spiro-Logic output + physician-report gate.

Field names are preserved verbatim so downstream modules (spiro_logic,
rhk_reports, rhk_case) keep working without migration. Legacy duplicate
fields stay as hidden shims for state round-trips.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from rhk_base import gr


# ---------------------------------------------------------------------------
# Header HTML (card chrome)
# ---------------------------------------------------------------------------


def _card_header_html(title: str) -> str:
    return (
        "<div class='rhk-sec-head'>"
        f"<div class='rhk-sec-title'>{title}</div>"
        "<div class='rhk-sec-progress'>"
        "<span class='rhk-sec-count'>0/0</span>"
        "<div class='rhk-sec-bar' role='progressbar' aria-valuenow='0' "
        "aria-valuemin='0' aria-valuemax='100'>"
        "<div style='width:0%'></div></div></div></div>"
    )


# ---------------------------------------------------------------------------
# Sub-builders — keep each section focused and readable
# ---------------------------------------------------------------------------


def _build_lufu_card(add: Callable[..., Any]) -> Any:
    """Lufu (pulmonary function) — compact, unchanged field set."""
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card"]):
        hdr = gr.HTML(_card_header_html("Lungenfunktion"))
        with gr.Column(elem_classes=["rhk-sec-body"]):
            with gr.Row():
                add("lufu_done", gr.Checkbox(label="Lufu durchgeführt"))
                add("lufu_obstructive", gr.Checkbox(label="Obstruktiv"))
                add("lufu_restrictive", gr.Checkbox(label="Restriktiv"))
                add("lufu_diffusion", gr.Checkbox(label="Diffusionsstörung"))
            with gr.Row():
                add("fev1_l", gr.Number(label="FEV1 (% Soll)"))
                add("fvc_l", gr.Number(label="FVC (% Soll)"))
                add("dlco_sb", gr.Number(label="DLCO SB (% Soll)"))
            with gr.Row():
                add("dlco_va", gr.Number(label="DLCO/VA (% Soll)"))
                add("residual_volume_l", gr.Number(label="RV (% Soll)"))
            add("lufu_summary", gr.Textbox(label="Lufu Kommentar (Freitext)", lines=2))

            with gr.Accordion("PVOD/PCH – Red Flags (optional)", open=False):
                with gr.Row():
                    add("pvod_dlco_disproportionate", gr.Checkbox(label="DLCO disproportional niedrig"))
                    add("pvod_rest_hypoxemia", gr.Checkbox(label="Ruhe-Hypoxämie"))
                    add("pvod_ex_desat", gr.Checkbox(label="Belastungs-Desaturation"))
                with gr.Row():
                    add("pvod_edema_on_vaso", gr.Checkbox(label="Ödem nach Vasodilatatoren"))
                add("pvod_edema_desc", gr.Textbox(label="Details (optional)", lines=2, visible=False))
    return hdr


def _build_cpet_core(add: Callable[..., Any]) -> None:
    """ESC/ERS-2022 core CPET parameters — always visible."""
    gr.HTML(
        "<div class='rhk-sec-intro'>Kerndaten der ESC/ERS 2022 PH-Risikostratifizierung. "
        "Fehlende Felder werden nicht als 0 interpretiert.</div>"
    )
    # Peak capacity
    with gr.Row():
        add("cpet_peak_vo2_ml_kg_min", gr.Number(
            label="V'O2peak (mL/min/kg)",
            info="Prognosemarker. Risiko-Cutoffs (ESC 2022): < 11 hoch, 11–15 intermediär, > 15 niedrig.",
        ))
        add("cpet_peak_vo2_pct_pred", gr.Number(
            label="V'O2peak (% Soll)",
            info="Prozent des Sollwerts. Erlaubt Vergleich über Alter und Geschlecht.",
        ))
        add("cpet_peak_vo2_ml_min", gr.Number(
            label="V'O2peak absolut (mL/min, optional)",
        ))

    # Effort + chronotropic
    with gr.Row():
        add("cpet_rer_peak", gr.Number(
            label="RER Peak",
            info="VCO2/VO2. RER ≥ 1.10 spricht für metabolische Ausbelastung.",
        ))
        add("cpet_hr_rest_bpm", gr.Number(
            label="HF Ruhe (bpm)",
            info="Ruhe-Herzfrequenz vor Belastung. Basis für Chronotropen Index.",
        ))
        add("cpet_hr_peak_bpm", gr.Number(
            label="HF Peak (bpm)",
            info="Maximale Herzfrequenz während CPET.",
        ))
        add("cpet_hr_pct_pred", gr.Number(
            label="HF Peak (% Soll)",
            info="Niedrig trotz hohem RER spricht für chronotrope Inkompetenz.",
        ))

    # Ventilation efficiency
    with gr.Row():
        add("cpet_ve_vco2_slope", gr.Number(
            label="V'E/V'CO2-Slope",
            info="Ventilatorische Effizienz. Erhöht (≥ 35) bei PH, Linksherzinsuffizienz, Totraum.",
        ))
        add("cpet_ve_vco2_nadir", gr.Number(
            label="V'E/V'CO2 Nadir",
            info="Minimaler V'E/V'CO2. Oft klinisch aussagekräftiger als Slope.",
        ))
        add("cpet_oues", gr.Number(
            label="OUES",
            info="Oxygen Uptake Efficiency Slope. Belastungs­unabhängiger Prognosemarker (HF).",
        ))
        add("cpet_ve_vco2_vt1", gr.Number(
            label="V'E/V'CO2 @ VT1",
            info="Ventilatorisches Äquivalent an der VT1.",
        ))
        add("cpet_petco2_vt1_mmhg", gr.Number(
            label="PETCO2 @ VT1 (mmHg)",
            info="PETCO2 an der ventilatorischen Schwelle. Niedrig spricht für Totraum/vaskuläres Muster.",
        ))

    # Circulation
    with gr.Row():
        add("cpet_peak_o2_pulse_ml", gr.Number(
            label="O2-Puls Peak (mL)",
            info="V'O2/HF. Surrogat für Schlagvolumen.",
        ))
        add("cpet_peak_o2_pulse_pct_pred", gr.Number(
            label="O2-Puls (% Soll)",
        ))
        add("cpet_o2_pulse_pattern", gr.Dropdown(
            label="O2-Puls Verlauf",
            choices=["unbekannt", "normal", "plateau", "fallend"],
            value="unbekannt",
            info="Plateau oder Abfall spricht für zirkulatorische Limitation.",
        ))

    # Peak V'O2 confirmation
    with gr.Row():
        add("cpet_vo2_peak_reached", gr.Dropdown(
            label="Peak V'O2 erreicht?",
            choices=["unklar", "ja", "nein"],
            value="unklar",
            info="Bestätigung der Ausbelastung. Bei „unklar“: Interpretation eingeschränkt.",
        ))
        add("cpet_stop_reason", gr.Dropdown(
            label="Abbruchgrund",
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
            info="Dokumentationspflicht. Zentral für Testqualität und Sicherheit.",
        ))


def _build_cpet_advanced(add: Callable[..., Any]) -> Dict[str, Any]:
    """Collapsible advanced parameters — quality, ventilation detail, safety, 9-panel."""
    refs: Dict[str, Any] = {}

    # ── Qualität & Effort ────────────────────────────────────────────
    with gr.Accordion("Qualität & Ausbelastung", open=False):
        with gr.Row():
            add("cpet_borg_rpe", gr.Number(label="Borg RPE (0–10)"))
            add("cpet_borg_dyspnoe", gr.Number(label="Borg Dyspnoe (0–10)"))
            add("cpet_borg_legs", gr.Number(label="Borg Beine (0–10)"))
        add("cpet_stop_reason_text", gr.Textbox(
            label="Details Abbruchgrund (optional)", lines=2,
        ))
        with gr.Row():
            add("cpet_beta_blocker", gr.Checkbox(label="Betablocker / frequenzbremsend"))
            add("cpet_sinus_node_disorder", gr.Checkbox(label="Sinusknotenstörung / Schrittmacher"))
            add("cpet_hyperventilation", gr.Checkbox(label="Hyperventilation / Panik"))
        add("cpet_chrono_comment", gr.Textbox(label="Chronotropie-Kommentar (optional)", lines=2))

    # ── Schwellen (VT1/VT2) ───────────────────────────────────────────
    with gr.Accordion("Schwellen (VT1 / VT2)", open=False):
        with gr.Row():
            add("cpet_vo2_vt1_ml_kg_min", gr.Number(label="V'O2 @ VT1 (mL/min/kg)"))
            add("cpet_vo2_vt1_ml_min", gr.Number(label="V'O2 @ VT1 (mL/min)"))
            add("cpet_vo2_vt2_ml_min", gr.Number(label="V'O2 @ VT2 (mL/min)"))
        with gr.Row():
            add("cpet_vt1_method", gr.Dropdown(
                label="VT1-Methode",
                choices=["Automatik", "V-Slope", "VE/VO2-Min", "PETO2-Min", "Kombiniert", "Sonstiges"],
                value="Automatik",
            ))
            add("cpet_vt1_manual_checked", gr.Dropdown(
                label="VT1 manuell geprüft",
                choices=["unklar", "ja", "nein"], value="unklar",
            ))
            add("cpet_vt1_time_min", gr.Number(label="VT1 Zeitpunkt (min)"))

    # ── Ventilation & Mechanik ────────────────────────────────────────
    with gr.Accordion("Ventilation & Mechanik", open=False):
        with gr.Row():
            add("cpet_petco2_rest_mmhg", gr.Number(label="PETCO2 Ruhe (mmHg)"))
            add("cpet_petco2_peak_mmhg", gr.Number(label="PETCO2 Peak (mmHg)"))
            add("cpet_breathing_reserve_pct", gr.Number(
                label="Atemreserve (%)",
                info="< 15 % spricht für ventilatorische Limitation.",
            ))
        with gr.Row():
            add("cpet_ve_peak_l_min", gr.Number(label="V'E Peak (L/min)"))
            add("cpet_mvv_l_min", gr.Number(label="MVV (L/min)"))
            add("cpet_mvv_source", gr.Dropdown(
                label="MVV-Quelle",
                choices=["gemessen", "geschätzt", "FEV1*35", "FEV1*40", "unklar"],
                value="geschätzt",
            ))
        with gr.Row():
            add("cpet_vo2_wr_slope_ml_min_w", gr.Number(
                label="ΔV'O2/ΔW (mL/min/W)",
                info="Erwartet 8–11. Niedrig spricht für zirkulatorische/periphere Limitation.",
            ))
            add("cpet_o2_pulse_slope", gr.Number(label="O2-Puls Slope (optional)"))

    # ── Oxygenierung & Blutdruck ──────────────────────────────────────
    with gr.Accordion("Oxygenierung & Blutdruck", open=False):
        with gr.Row():
            add("cpet_spo2_rest_pct", gr.Number(label="SpO2 Ruhe (%)"))
            add("cpet_spo2_peak_pct", gr.Number(label="SpO2 Peak (%)"))
            add("cpet_spo2_nadir_pct", gr.Number(
                label="SpO2 Nadir (%)",
                info="Niedrigster Wert. Abfall ≥ 4 % oder < 88 % gilt als pathologisch.",
            ))
            add("cpet_o2_supp_l_min", gr.Number(label="O2-Gabe (L/min)"))
        with gr.Row():
            add("cpet_bp_sys_rest", gr.Number(label="RR syst. Ruhe (mmHg)"))
            add("cpet_bp_dia_rest", gr.Number(label="RR diast. Ruhe (mmHg)"))
            add("cpet_bp_sys_peak", gr.Number(label="RR syst. Peak (mmHg)"))
            add("cpet_bp_dia_peak", gr.Number(label="RR diast. Peak (mmHg)"))

    # ── Sicherheit ────────────────────────────────────────────────────
    with gr.Accordion("Sicherheit & Safety Events", open=False):
        with gr.Row():
            add("cpet_angina", gr.Checkbox(label="Angina / Thoraxschmerz"))
            add("cpet_dizziness", gr.Checkbox(label="Schwindel / Präsynkope"))
            add("cpet_syncope", gr.Checkbox(label="Synkope"))
            add("cpet_palpitations", gr.Checkbox(label="Palpitationen"))
        with gr.Row():
            add("cpet_arrhythmia", gr.Checkbox(label="Arrhythmie"))
            add("cpet_st_changes", gr.Dropdown(
                label="ST/T-Veränderungen",
                choices=["keine", "ST Senkung", "ST Hebung", "nicht beurteilbar", "Sonstiges"],
                value="keine",
            ))
        add("cpet_arrhythmia_text", gr.Textbox(
            label="Arrhythmie-Details (optional)", lines=2,
        ))

    # ── 9-Felder-Grafik ───────────────────────────────────────────────
    with gr.Accordion("9-Felder-Grafik (Muster)", open=False):
        add("cpet_9panel_available", gr.Checkbox(label="9-Felder-Grafik beurteilt"))
        with gr.Column(visible=False) as refs_panel:
            refs["cpet_9panel_details"] = refs_panel
            gr.HTML(
                "<div class='docx-muted'>Nur Muster dokumentieren, die sicher gesehen wurden. "
                "Unklar bleibt unklar. VT1 und RCP sind Ankerpunkte. EOV und Flow-Volume-Limitation "
                "sind Warnzeichen.</div>"
            )
            with gr.Row():
                add("cpet_9panel_vt1_identified", gr.Dropdown(
                    label="VT1 identifiziert",
                    choices=["ja", "unklar", "nein"], value="unklar",
                ))
                add("cpet_9panel_vt1_method", gr.Dropdown(
                    label="VT1-Methode",
                    choices=["V Slope", "VE VO2 Knick", "PETCO2 Verlauf", "Sonstiges"],
                    value="V Slope",
                ))
                add("cpet_9panel_rcp_identified", gr.Dropdown(
                    label="RCP identifiziert",
                    choices=["ja", "unklar", "nein"], value="unklar",
                ))
            with gr.Row():
                add("cpet_9panel_eov", gr.Checkbox(label="EOV (oszillierende Ventilation)"))
                add("cpet_9panel_flowvol_limit", gr.Dropdown(
                    label="Flow-Volume-Limitation",
                    choices=["nein", "unklar", "ja"], value="unklar",
                ))
            with gr.Row():
                add("cpet_9panel_vo2wr_pattern", gr.Dropdown(
                    label="V'O2 zu Leistung",
                    choices=["linear", "unklar", "flach", "plateau"], value="unklar",
                ))
                add("cpet_9panel_veeq_pattern", gr.Dropdown(
                    label="Ventilatorische Äquivalente",
                    choices=["normal", "unklar", "frueh", "kein"], value="unklar",
                ))
            add("cpet_9panel_comment", gr.Textbox(
                label="9-Felder-Kommentar (optional)", lines=2,
            ))

    # ── Override & Next Steps ────────────────────────────────────────
    with gr.Accordion("Manuelle Anpassungen (Override / Next Steps)", open=False):
        gr.HTML(
            "<div class='docx-muted'>Optionale ärztliche Korrektur. "
            "Spiro-Logic überschreibt keine manuellen Angaben.</div>"
        )
        with gr.Row():
            add("cpet_limitation_override", gr.Dropdown(
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
            ))
        add("cpet_limitation_override_text", gr.Textbox(
            label="Begründung Override", lines=2,
        ))
        add("cpet_next_steps_manual", gr.Textbox(
            label="Zusätzliche Next Steps (ärztlich)", lines=2,
        ))

    return refs


# ---------------------------------------------------------------------------
# Main tab builder
# ---------------------------------------------------------------------------


def build_cpet_tab(add: Callable[..., Any]) -> Dict[str, Any]:
    """Build the Lufu+CPET tab and return component handles needed by the UI binder."""

    # ── Card 1: Lufu ────────────────────────────────────────────────
    hdr_lufu = _build_lufu_card(add)

    # ── Card 2: CPET ────────────────────────────────────────────────
    with gr.Group(elem_classes=["rhk-card", "rhk-section-card", "rhk-cpet-card"]):
        hdr_cpet = gr.HTML(_card_header_html("Spiroergometrie / CPET"))
        with gr.Column(elem_classes=["rhk-sec-body"]):
            # CPET gate + meta
            with gr.Row():
                add("cpet_done", gr.Checkbox(label="CPET durchgeführt"))
                add("cpet_protocol", gr.Dropdown(
                    label="Protokoll",
                    choices=["Rampe", "Stufenprotokoll", "Semi supine", "Laufband", "Sonstiges"],
                    value="Rampe",
                ))
                add("cpet_setup", gr.Textbox(label="Ort / Setup (optional)"))

            # Risk chips (ESC/ERS 3-strata + CPET Score 4-strata)
            cpet_risk_html = gr.HTML(
                value="<div class='docx-muted'>Keine CPET-Daten erfasst.</div>"
            )

            # CPET details — visible whenever the Spiro-Logic has anything to say.
            # Note: visibility binding preserved from legacy code.
            with gr.Column(visible=False) as cpet_details:
                # Live headline from Spiro-Logic (always prominent, single source of truth)
                cpet_live_html = gr.HTML(
                    value="<div class='docx-muted'>Live-Erklärung erscheint nach Eingabe von CPET-Werten.</div>"
                )

                # Core values — always visible
                with gr.Group(elem_classes=["rhk-subcard"]):
                    gr.HTML("<div class='rhk-subcard-title'>Kerndaten</div>")
                    _build_cpet_core(add)

                # Advanced — collapsible groups
                with gr.Group(elem_classes=["rhk-subcard"]):
                    gr.HTML("<div class='rhk-subcard-title'>Erweiterte Parameter</div>")
                    panel_refs = _build_cpet_advanced(add)

                # Chronotropic follow-up (legacy visibility group, still needed by bindings)
                cpet_chrono_followup = gr.Column(visible=False)

                # Teaching (Lernmodus) — collapsed by default
                with gr.Accordion("Lernmodus CPET", open=False):
                    cpet_teaching_html = gr.HTML(
                        value="<div class='docx-muted'>Lernmodule erscheinen nach Eingabe oder beim Laden.</div>"
                    )

                # Structured Spiro-Logic output — all modules rendered in one pane
                with gr.Group(elem_classes=["rhk-subcard"]):
                    gr.HTML("<div class='rhk-subcard-title'>Spiro-Logic Befundung</div>")
                    cpet_overall_html = gr.HTML(value="")
                    cpet_modfinal_html = gr.HTML(value="")

                # Module detail (kept as hidden inputs for backwards compatibility;
                # rendered into the overall HTML by spiro_logic.build_cpet_outputs)
                cpet_mod0_html = gr.HTML(value="", visible=False)
                cpet_mod1_html = gr.HTML(value="", visible=False)
                cpet_mod2_html = gr.HTML(value="", visible=False)
                cpet_mod3_html = gr.HTML(value="", visible=False)
                cpet_mod4_html = gr.HTML(value="", visible=False)
                cpet_mod5_html = gr.HTML(value="", visible=False)
                cpet_mod6_html = gr.HTML(value="", visible=False)
                cpet_mod7_html = gr.HTML(value="", visible=False)
                cpet_mod9_html = gr.HTML(value="", visible=False)

                # Report gate
                with gr.Group(elem_classes=["rhk-subcard"]):
                    gr.HTML("<div class='rhk-subcard-title'>Synthese & Bericht</div>")
                    cpet_spiro_report = gr.Textbox(
                        label="Automatischer CPET-Befundtext (Spiro-Logic)",
                        lines=8,
                        interactive=False,
                    )
                    cpet_spiro_status = gr.HTML(value="")
                    with gr.Row():
                        add("cpet_spiro_in_report", gr.Checkbox(
                            label="Spiro-Logic Interpretation in Arztbericht aufnehmen",
                            value=False,
                        ))
                        btn_cpet_adopt = gr.Button("Als CPET-Kommentar übernehmen")
                    add("cpet_summary", gr.Textbox(
                        label="CPET-Kommentar (Freitext)", lines=3,
                    ))

    # Hidden shims for downstream modules that still read legacy field names.
    # Keeping them here avoids a migration pass through rhk_ui.py, rhk_case.py
    # and the reports builder.
    add("cpet_site", gr.Textbox(label="", visible=False))
    add("cpet_borg_dyspnea", gr.Number(label="", visible=False))
    add("cpet_borg_leg", gr.Number(label="", visible=False))

    return {
        "hdr_lufu": hdr_lufu,
        "hdr_cpet": hdr_cpet,
        "cpet_risk_html": cpet_risk_html,
        "cpet_details": cpet_details,
        "cpet_9panel_details": panel_refs["cpet_9panel_details"],
        "cpet_chrono_followup": cpet_chrono_followup,
        "cpet_live_html": cpet_live_html,
        "cpet_teaching_html": cpet_teaching_html,
        "cpet_mod0_html": cpet_mod0_html,
        "cpet_mod1_html": cpet_mod1_html,
        "cpet_mod2_html": cpet_mod2_html,
        "cpet_mod3_html": cpet_mod3_html,
        "cpet_mod4_html": cpet_mod4_html,
        "cpet_mod5_html": cpet_mod5_html,
        "cpet_mod6_html": cpet_mod6_html,
        "cpet_mod7_html": cpet_mod7_html,
        "cpet_mod9_html": cpet_mod9_html,
        "cpet_modfinal_html": cpet_modfinal_html,
        "cpet_overall_html": cpet_overall_html,
        "cpet_spiro_report": cpet_spiro_report,
        "cpet_spiro_status": cpet_spiro_status,
        "btn_cpet_adopt": btn_cpet_adopt,
    }
