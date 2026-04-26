#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.49: rhk_reports.py - Fingerprint-Overhead reduziert (kein Hashing ohne Cache, Imports werden ignoriert)
# Refactor v1.48: rhk_reports.py - Modul-Transparenz vereinheitlicht (ausgewählt/deaktiviert/auto-vorgeschlagen)
# Refactor v1.43: rhk_reports.py - Patientenbericht: weniger Fachwörter (prä/post...), keine Step-Ziele, neue "Fragen fürs Arztgespräch" Sektion
# Refactor v1.42: rhk_reports.py - Patientenbericht: Glossar-Auszug (Begriffe kurz erklärt) + Diskrepanz-Block bereinigt
# Refactor v1.39: rhk_reports.py - Patientenbericht gehärtet: fehlende Kernwerte transparent, Jargon reduziert, Docstring/Types bereinigt
# Refactor v1.31: rhk_reports.py - Performance/Stability: fehlendes `re` Import ergänzt; regex-heavy Converter vorbereitet
# Refactor v1.27: rhk_reports.py - Star-Import entfernt, Base-Dependencies explizit, Datenschutz-Caching unverändert
"""RHK Befundassistent – Report Builder (split from rhk_app_web_master.py).

Enthält:
- Arztbericht, Patientenbericht, interner Bericht
- Input-Summary, JSON Export/Import

Hinweis: Inhalt ist weitgehend 1:1 aus der Master-Datei extrahiert.
"""

from __future__ import annotations

import datetime as _dt

# NOTE (DSGVO/Datensparsamkeit): Do NOT cache functions that take full report text.
# Caching would store patient data in global process memory across sessions.
import json
import os
import random
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from rhk_base import (
    _ALL_P_MODULE_IDS,
    APP_VERSION,
    SafeDict,
    TextBlock,
    _fmt,
    _normalize_module_ids,
    _safe_float,
    _safe_num,
    describe_exercise_pattern,
    fmt_float,
    fmt_int,
    pmods_apply_overrides,
    pmods_get_force_optional,
    render_block,
    safe_eval_bool,
)
from rhk_case_schema import CaseLike
from rhk_logging import log_exception
from rhk_report_cache import (
    REPORT_CACHE_MAXSIZE,  # noqa: F401  (re-exported for back-compat)
    _cache_get,
    _cache_set,
    _case_fingerprint,
)
from rhk_report_doctor import (  # noqa: F401  (re-exported for back-compat)
    _doctor_tpl_append_assessment_block,
    _doctor_tpl_append_cpet_block,
    _doctor_tpl_append_cpet_context_lines,
    _doctor_tpl_append_intro_block,
    _doctor_tpl_append_klinik_block,
    _doctor_tpl_append_module_transparency,
    _doctor_tpl_append_preprocedural_safety,
    _doctor_tpl_append_procedere_block,
    _doctor_tpl_append_risk_block,
    _doctor_tpl_append_summary_section,
    _doctor_tpl_bul,
    _doctor_tpl_bundle_paragraphs,
    _doctor_tpl_clean_bullet_text,
    _doctor_tpl_clean_item,
    _doctor_tpl_collect_hints,
    _doctor_tpl_cpet_interpretation_lines,
    _doctor_tpl_emit_module_text,
    _doctor_tpl_emit_selected_module_content,
    _doctor_tpl_extract_section,
    _doctor_tpl_fmt_bp,
    _doctor_tpl_has_cpet_data,
    _doctor_tpl_module_state,
    _doctor_tpl_par,
    _doctor_tpl_render_module_text,
    _doctor_tpl_split_items,
    _doctor_tpl_study_hints,
    _doctor_tpl_warning_hints,
)
from rhk_report_filters import (
    _filter_narrative_block,  # noqa: F401  (re-exported for back-compat)
    _format_warning_item,
    _md_kv,
    _md_section,  # noqa: F401  (re-exported for back-compat)
    _no_congestion_context,  # noqa: F401  (re-exported for back-compat)
    _sanitize_concluding,
    _sanitize_interpretation_block,
    _strip_procedere_from_text,  # noqa: F401  (re-exported for back-compat)
)
from rhk_report_markdown import (
    _extract_markdown_section_cached,  # noqa: F401
    _markdown_to_plain_cached,  # noqa: F401
    _markdown_to_word_html_cached,  # noqa: F401
    extract_markdown_section,  # noqa: F401
    markdown_to_docx_file,  # noqa: F401
    markdown_to_word_html,  # noqa: F401
)
from rhk_report_patient import (  # noqa: F401  (re-exported for back-compat)
    PATIENT_REPORT_MODE_LAY,
    PATIENT_REPORT_MODE_SHORT,
    _append_patient_bridge,
    _append_patient_diagnosis_block,
    _append_patient_followup_sections,
    _append_patient_glossary_section,
    _append_patient_intro_meta,
    _append_patient_intro_sections,
    _append_patient_measurement_sections,
    _append_patient_relevance_section,
    _build_layered_paragraph,
    _build_patient_inline_terms,
    _build_patient_report_content,
    _build_patient_report_impl,
    _build_patient_short_report,
    _collect_glossary_line_hits,
    _collect_patient_bundle_texts,
    _collect_used_glossary_terms,
    _enforce_patient_layered_constraints,
    _ensure_clarity_label,
    _find_glossary_term_idx,
    _find_header_bounds,
    _get_patient_auto_glossary,
    _get_patient_jargon_explanations,
    _glossary_one_sentence,
    _has_patient_transition_prefix,
    _inline_explanation_from_glossary_text,
    _limit_sentences,
    _load_echo_patient_textdb,
    _load_patient_textdb,
    _load_patient_variant_context,
    _lowercase_patient_chunk_start,
    _merge_patient_glossary,
    _normalize_patient_certainty_line,
    _normalize_patient_report_mode,
    _patient_arch_blocks,
    _patient_arch_text,
    _patient_bio_qual,
    _patient_bridge,
    _patient_bundle_patient_blocks,
    _patient_ci_low_severity_key,
    _patient_clean_choice,
    _patient_conversation_questions,
    _patient_cpet_lines,
    _patient_discordance_flags,
    _patient_episode_patient_bullet,
    _patient_first_nonempty,
    _patient_functional_context_lines,
    _patient_hemo_qual,
    _patient_hf_text,
    _patient_is_high_risk,
    _patient_medication_goal,
    _patient_module_level,
    _patient_module_reason,
    _patient_mpap_block_key,
    _patient_name,
    _patient_norm,
    _patient_overview_bnp_sentence,
    _patient_overview_clarity_sentence,
    _patient_overview_core_sentence,
    _patient_overview_next_step_sentence,
    _patient_overview_pattern_sentence,
    _patient_paragraph_chunk_with_transition,
    _patient_pawp_block_key,
    _patient_pvr_severity_key,
    _patient_rap_severity_key,
    _patient_relevance_from_esc4,
    _patient_relevance_line,
    _patient_rest_hemo_values,
    _patient_risk_txt,
    _patient_salutation,
    _patient_symptom_profile,
    _patient_to_bool,
    _patient_variant_or_fallback,
    _patient_warn_lines,
    _patientize_cause_text,
    _pick_echo_patient_template,
    _pick_patient_template,
    _render_echo_patient_text,
    _render_patient_text,
    _replace_patient_jargon_once,
    _resolve_patient_report_mode,
    _rewrite_patient_line_for_lay_mode,
    _rewrite_patient_lines_for_lay_mode,
    _safe_format_text_template,
    _sanitize_patient_tone,
    _split_sentences,
    _stable_patient_seed,
    _strip_expansion_sentinels,
    _tr,
    _truncate_words,
    _word_count,
    build_doctor_report_for_copy,
    build_echo_patient_report,
    build_patient_report,
)
from rhk_report_summary import (
    _extract_positive_detail_parts,  # noqa: F401  (re-exported for back-compat)
    _get_ph_tx_episodes,
    _normalize_yes_no_status,  # noqa: F401  (re-exported for back-compat)
    _summary_anticoag_message,  # noqa: F401  (re-exported for back-compat)
    _summary_antifibrotic_message,  # noqa: F401  (re-exported for back-compat)
    _summary_bp_line,  # noqa: F401  (re-exported for back-compat)
    _summary_clean_text,  # noqa: F401  (re-exported for back-compat)
    _summary_cmr_bits,  # noqa: F401  (re-exported for back-compat)
    _summary_cmr_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_context_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_add_metric,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_items,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_predicted_line,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_rr_items,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_section,  # noqa: F401  (re-exported for back-compat)
    _summary_cpet_symptom_items,  # noqa: F401  (re-exported for back-compat)
    _summary_ct_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_echo_bits,  # noqa: F401  (re-exported for back-compat)
    _summary_echo_derived_bits,  # noqa: F401  (re-exported for back-compat)
    _summary_echo_flag_bits,  # noqa: F401  (re-exported for back-compat)
    _summary_echo_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_echo_ui_bits,  # noqa: F401  (re-exported for back-compat)
    _summary_ekg_sign_items,  # noqa: F401  (re-exported for back-compat)
    _summary_exam_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_imaging_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_infectious_genetic_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_lsb_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_medication_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_ph_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_ph_therapy_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_positive_line,  # noqa: F401  (re-exported for back-compat)
    _summary_symptom_lines,  # noqa: F401  (re-exported for back-compat)
    _summary_syncope_text,  # noqa: F401  (re-exported for back-compat)
    _summary_vq_lines,  # noqa: F401  (re-exported for back-compat)
    summarize_inputs,
)

# =============================================================================
# Named constants for frequently-used dictionary keys
# =============================================================================
# Extracting these avoids silent bugs from typos in string literals.

# -- Case-level section keys --
K_UI = "ui"
K_DERIVED = "derived"
K_SCORES = "scores"
K_DECISION = "decision"
K_ENV = "env"
K_WARNINGS = "warnings"
K_MODULES = "modules"
K_HFPEF = "hfpef"
K_DEBUG = "debug"

# -- Frequently-used data keys --
K_STORY = "story"
K_CHD_POS = "chd_pos"
K_SEVERITY = "severity"
K_CANDIDATES = "candidates"
K_BUNDLE = "bundle"
K_STATUS = "status"
K_RISK_CATEGORY = "risk_category"
K_PH_ETIOLOGY = "ph_etiology"

# =============================================================================
# Report caching — extracted to rhk_report_cache for clearer privacy boundary
# =============================================================================

_REPORT_RECOVERABLE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    TypeError,
    ValueError,
    ImportError,
    ModuleNotFoundError,
)




# =============================================================================
# Exercise slope QC – user-facing text (no internal codes)
# =============================================================================

def _exercise_flag_to_text(code: str) -> str:
    code = str(code or "").strip()
    mapping = {
        "missing_values": "Belastungswerte unvollständig (mPAP/PAWP/CO in Ruhe oder Peak)",
        "dco_nonpositive": "ΔCO ≤ 0 (CO_peak ≤ CO_rest); CO-Werte prüfen",
        "co_nonpositive": "CO ≤ 0; Eingabe/Messung prüfen",
        "wedge_inconsistent_rest": "mPAP < PAWP in Ruhe; Wedge-Messung inkonsistent",
        "wedge_inconsistent_peak": "mPAP < PAWP bei Peak; Wedge-Messung inkonsistent",
        "pawp_negative": "PAWP < 0; Eingabe/Messung prüfen",
        "dco_small": "ΔCO gering; Slopes unsicher",
        "slope_inconsistent": "Algebra inkonsistent (ΔmPAP/ΔCO ≠ ΔPAWP/ΔCO + ΔTPG/ΔCO); Plausibilität prüfen",
        "low_peak_pawp_with_high_slope": "ΔPAWP/ΔCO erhöht trotz niedriger PAWP_peak; häufig Artefakt/Wedge-Unsicherheit",
        "wedge_wave_present": "Wedge-Wellen; PAWP/Slopes vorsichtig interpretieren",
        "af_present": "Vorhofflimmern; Mittelwerte/Slopes vorsichtig interpretieren",
        # CO-Methode ist im klinischen Interpretationstext nicht hilfreich; keine Ausgabe.
        "co_method_unknown": "",
        "extreme_jump_pawp": "Starker PAWP-Sprung zwischen Ruhe und Peak; Plausibilität prüfen",
        "extreme_jump_mpap": "Starker mPAP-Sprung zwischen Ruhe und Peak; Plausibilität prüfen",
    }
    return mapping.get(code, code) if code else ""


def _describe_exercise_response_2pt(d: dict) -> str:
    """User-facing interpretation for rest→peak slopes.

    Goal:
    - Keep the term "Slope".
    - Avoid opaque labels such as "gemischt".
    - Add a short, clinically interpretable rationale without changing diagnoses.

    The base labels (see ``rhk_config.EXERCISE_PATTERN_LABELS``) already carry
    a parenthetical rationale for the pv_dominant/la_dominant/normal cases
    (e.g. "pulmonalvaskulär dominierte Druckantwort (ΔmPAP/ΔCO und ΔTPG/ΔCO
    erhöht bei unauffälliger ΔPAWP/ΔCO)"). Emitting another near-identical
    rationale afterwards produces clinically awkward duplication like
    "…unauffälliger ΔPAWP/ΔCO) Dominanz der pulmonalvaskulären Komponente
    (ΔTPG/ΔCO erhöht bei unauffälliger ΔPAWP/ΔCO)." — so we skip the add
    when the label already contains a rationale.
    """
    code = (d or {}).get("exercise_pattern")
    if not code:
        return ""

    label = describe_exercise_pattern(code)
    if not label:
        return ""

    add = ""
    if code == "exercise_2pt_mixed":
        # The "kombinierte Druckantwort (…)" label is short — add a richer
        # clinical explanation since this pattern needs disambiguation.
        add = (
            " Vereinbar mit kombinierter linksatrialer und pulmonalvaskulärer Komponente. "
            "Kontextfaktoren (Volumenstatus, Shunt, High Output) und Wedge Qualität mitbeurteilen; "
            "bei klinischer Relevanz Reevaluation nach Optimierung."
        )

    out = (label + add).strip()
    if out and not out.endswith("."):
        out += "."
    return out

# PH Therapieepisoden (restart-fähig)
from rhk_ph_tx import (  # noqa: F401
    format_ph_tx_episode_line,
    legacy_lists_to_episodes,
    parse_ph_tx_table_rows,
)

# Optional: local phrase/rule DB (DSGVO-safe). App must run without it.
select_phrases: Any = None
try:
    from rhk_report_db import select_phrases
except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
    log_exception("RHK_REP_IMPORT_DB", "Optional report DB import unavailable.", exc)

# Einige Render-Helpers liegen im Case-Modul (im Flat-Master waren sie vorher "weiter oben").
from rhk_case import build_render_ctx, filter_module_text, render_p01_dynamic  # noqa: F401

# Optional study pre-screen checks. App must run without it.
try:
    from rhk_study_checks import get_study_hints
except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
    log_exception("RHK_REP_IMPORT_STUDY_HINTS", "Optional study hints import unavailable.", exc)
    def get_study_hints(case: Dict[str, Any]) -> List[str]:
        return []
# ---------------------------------------------------------------------------
# Small, conservative post-filters for narrative blocks
# ---------------------------------------------------------------------------

# _no_congestion_context and _filter_narrative_block are now defined in
# rhk_report_filters and imported via the module-level re-export below.



# =============================================================================
# Warnings / Hinweise – formatting helpers
# =============================================================================

# _format_warning_item lives in rhk_report_filters; re-exported below.

# =============================================================================
# Befund – input summary block
# =============================================================================


# _md_kv / _md_section live in rhk_report_filters; re-exported below.





# _strip_procedere_from_text / _sanitize_concluding / _sanitize_interpretation_block
# now live in rhk_report_filters; re-exported below.


def _build_relevante_vorerkrankungen_line(ui: Dict[str, Any]) -> str:
    """Build a single-line 'Relevante Vorerkrankungen' string for the Arztbericht.

    Includes ONLY items explicitly captured as relevant comorbidities in the UI:
    - Freitext 'comorbidities'
    - Virologie/Infektiologie (e.g., HIV/Hepatitis) when marked positive
    - Immunologie/Autoimmun when marked positive
    - Angeborener Herzfehler/Shunt when marked positive
    """
    items: List[str] = []
    comorb = _patient_clean_choice(ui.get("comorbidities"))
    if comorb:
        items.append(comorb)

    # CHD/Shunt
    if ui.get(K_CHD_POS) is True:
        chd_type = _patient_clean_choice(ui.get("chd_type"))
        chd_desc = _patient_clean_choice(ui.get("chd_desc"))
        txt = "Angeborener Herzfehler/Shunt"
        bits = []
        if chd_type:
            bits.append(chd_type)
        if chd_desc:
            bits.append(chd_desc)
        if bits:
            # Use colon form instead of an outer (...) wrapper — ``chd_type``
            # values like "ASD (Vorhofseptumdefekt)" already contain parens,
            # and nesting them produces clutter like
            # "Shunt (ASD (Vorhofseptumdefekt) – …)" which reads like a parser
            # bug. "Shunt: ASD (Vorhofseptumdefekt) – …" is clean and reads
            # naturally in both clinician and lay contexts.
            txt += ": " + " – ".join(bits)
        items.append(txt)

    for pos_key, items_key, desc_key, label in (
        ("virology_pos", "virology_items", "virology_desc", "Virologie/Infektiologie"),
        ("immunology_pos", "immunology_items", "immunology_desc", "Immunologie/Autoimmun"),
    ):
        if ui.get(pos_key) is not True:
            continue
        parts = _extract_positive_detail_parts(ui.get(items_key), ui.get(desc_key))
        items.append(f"{label}: " + (", ".join(parts) if parts else "positiv"))

    joined = "; ".join([x for x in items if x])
    return joined if joined else "-"





def _build_ph_therapieverlauf_block(ui: Dict[str, Any], derived: Optional[Dict[str, Any]] = None) -> str:
    """Build 'PH-Therapieverlauf' block for Arztbericht.

    Deterministic ordering:
    - Historie (früher/abgesetzt/pausiert)
    - Aktuell
    - Geplant
    """
    eps = _get_ph_tx_episodes(ui, derived)
    if not eps:
        return ""

    def _collect(statuses: set[str]) -> List[str]:
        out: List[str] = []
        for e in eps:
            try:
                st = str(e.get(K_STATUS) or "").strip().lower()
            except _REPORT_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_REP_TX_STATUS_PARSE", "PH episode status parsing failed.", exc)
                st = ""
            if st not in statuses:
                continue
            s = format_ph_tx_episode_line(e)
            if s and s not in out:
                out.append(s)
        return out

    lines: List[str] = []
    hist = _collect({"früher", "abgesetzt", "pausiert"})
    cur = _collect({"aktuell"})
    planned = _collect({"geplant"})

    if hist:
        lines.append(_md_kv("Historie", ", ".join(hist)))
    if cur:
        lines.append(_md_kv("Aktuell", ", ".join(cur)))
    if planned:
        lines.append(_md_kv("Geplant", ", ".join(planned)))

    return "PH-Therapieverlauf:\n" + "\n".join([l for l in lines if l]) + "\n"



# =============================================================================
# Report DB phrase injection (optional)
# =============================================================================

def _report_db_text(case: CaseLike, audience: str, section: str) -> str:
    """Return deterministic DB phrases for a given report section.

    - Never contains patient-identifiable data (DB is local + generic).
    - If DB is missing/unavailable, returns empty string.
    """
    if select_phrases is None:
        return ""
    try:
        env = case.get(K_ENV) or {}
        tags0 = []
        dec = case.get(K_DECISION) or {}
        if isinstance(dec.get("tags"), list):
            tags0 = [str(x) for x in (dec.get("tags") or []) if x]
        phrases, _tags = select_phrases(
            env=env,
            tags=tags0,
            audience=str(audience),
            section=str(section),
            safe_eval_bool_fn=safe_eval_bool,
        )
        phrases = [str(p).strip() for p in (phrases or []) if str(p).strip()]
        return "\n\n".join(phrases).strip()
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_DB_PHRASES", "Report DB phrase rendering failed.", exc, audience=audience, section=section)
        return ""
# =============================================================================
# Doctor report (Markdown)
# =============================================================================



def build_doctor_report_template(case: CaseLike, blocks: Dict[str, TextBlock]) -> str:
    """Arztbericht im Klinik-Layout (Muster-basiert, kompakt, nicht redundant)."""
    from rhk_doctor_report_service import build_doctor_report_template_service

    return build_doctor_report_template_service(case, blocks)


def _build_ph_etiology_candidate_line(cand: Dict[str, Any], group_names: Dict[int, str]) -> str:
    try:
        g_raw = cand.get("group")
        g_key: Optional[int] = None
        if g_raw is not None:
            try:
                g_key = int(str(g_raw))
            except (TypeError, ValueError):
                g_key = None
        ev = cand.get("evidence") or []
        if not isinstance(ev, list):
            return ""
        ev_clean = [str(x).strip() for x in ev if str(x).strip() and not str(x).strip().lower().startswith("hinweis:")]
        if not ev_clean:
            return ""
        ev_txt = "; ".join(ev_clean[:3]) + ("; …" if len(ev_clean) > 3 else "")
        g_name = group_names.get(g_key) if g_key is not None else None
        g_title = g_key if g_key is not None else g_raw
        title = f"Gruppe {g_title}" + (f" ({g_name})" if g_name else "")
        end = "" if ev_txt.endswith((".", "!", "?", "…")) else "."
        return f"{title}: {ev_txt}{end}"
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_ETIOLOGY_EVIDENCE", "Etiology evidence rendering skipped for one candidate.", exc)
        return ""


def _build_ph_etiology_dd_block(d: Dict[str, Any]) -> str:
    """Return a compact differential etiology block for Interpretation."""
    try:
        et = (d or {}).get(K_PH_ETIOLOGY) or {}
        cands = et.get(K_CANDIDATES) or []
        if not isinstance(cands, list) or not cands:
            return ""

        labels = [str(c.get("label_doc") or "").strip() for c in cands]
        labels = [x for x in labels if x]
        if not labels:
            return ""

        clear = bool(et.get("clear_leader"))
        head = "Ätiologische Einordnung: "
        if clear:
            head += f"Am ehesten {labels[0]}."
            if len(labels) > 1:
                head += " DD: " + ", ".join(labels[1:]) + "."
        else:
            head += (
                "Hinweise auf mehrere mögliche Ursachen/Mechanismen ("
                + ", ".join(labels)
                + "); führende Zuordnung anhand der vorliegenden Angaben nicht sicher."
            )

        group_names = {1: "PAH", 2: "Linksherz", 3: "Lunge/Hypoxie", 4: "CTEPH/CTEPD"}
        ev_lines = [ln for ln in (_build_ph_etiology_candidate_line(c, group_names) for c in cands[:4]) if ln]

        if ev_lines:
            # Emit a proper Markdown list (leading blank line + "- " items) so
            # the Interpretation renders cleanly. The legacy "• " bullets were
            # literal characters — they did not produce a Markdown list and
            # collapsed into prose with dangling bullet glyphs.
            ev_block = "\n\n" + "\n".join(["- " + ln for ln in ev_lines])
            return (head + ev_block).strip()
        return head.strip()
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_ETIOLOGY_BLOCK", "Etiology differential block generation failed.", exc)
        return ""


def _hemo_non_ph_statement(pawp: float, pvr: float) -> str:
    if pawp <= 15 and pvr < 2:
        return (
            "Die hämodynamischen Parameter in Ruhe liegen im Normbereich. "
            "Es bestehen keine Kriterien für pulmonale Hypertonie."
        )
    if pawp > 15:
        return (
            "Die Kriterien für pulmonale Hypertonie sind in Ruhe nicht erfüllt. "
            "Auffällig sind erhöhte Linksherzfüllungsdrücke als Hinweis auf eine mögliche diastolische Dysfunktion/HFpEF Konstellation."
        )
    if pvr >= 2:
        return (
            "Die Kriterien für pulmonale Hypertonie sind in Ruhe nicht erfüllt. "
            "Bei erhöhter PVR ist die Konstellation im Kontext von Herzzeitvolumen und Messbedingungen zu interpretieren; "
            "eine frühe pulmonalvaskuläre Beteiligung kann nicht sicher ausgeschlossen werden."
        )
    return "Die hämodynamischen Parameter in Ruhe liegen überwiegend im Normbereich; Kriterien für pulmonale Hypertonie sind nicht erfüllt."


def _hemo_ph_statement(mpap: float, pawp: float, pvr: float, co: Optional[float], ci: Optional[float], high_flow: Any) -> str:
    if pawp <= 15 and pvr > 2:
        return "Es liegen hämodynamische Kriterien für eine präkapilläre pulmonale Hypertonie vor."
    if pawp <= 15 and pvr <= 2:
        is_high_flow = high_flow is True or (co is not None and co >= 8.0) or (ci is not None and ci >= 4.0)
        if is_high_flow:
            return (
                "Es besteht eine mPAP Erhöhung bei normalem PAWP und nicht erhöhter PVR im Kontext eines erhöhten Herzzeitvolumens. "
                "Dies spricht für eine flussdominante Druckerhöhung; Kriterien einer präkapillären PH (PVR >2 WU) sind nicht erfüllt. "
                "Hoher CO CI ersetzt nicht das PVR Kriterium."
            )
        return (
            "Es besteht eine isolierte mPAP Erhöhung bei normalem PAWP und nicht erhöhter PVR. "
            "Diese Konstellation erfüllt keine Kriterien einer präkapillären PH; Einordnung im Kontext von CO CI, Messbedingungen und klinischem Risiko."
        )
    if pawp > 15 and pvr <= 2:
        return (
            "Es liegen hämodynamische Kriterien für eine isolierte postkapilläre pulmonale Hypertonie vor, "
            "passend zu einer Linksherzerkrankung/HFpEF Konstellation."
        )
    if pawp > 15 and pvr > 2:
        return (
            "Es liegen hämodynamische Kriterien für eine kombinierte post und präkapilläre pulmonale Hypertonie vor. "
            "Dies spricht für eine postkapilläre Komponente mit zusätzlicher pulmonalvaskulärer Beteiligung."
        )
    if mpap > 20:
        return "Es bestehen Kriterien für pulmonale Hypertonie. Die weitere Einordnung erfolgt anhand von PAWP und PVR im Gesamtkontext."
    return ""


def _hemo_additional_bits(rap: Optional[float], ci: Optional[float], pac: Optional[float], pp: Optional[float]) -> List[str]:
    bits: List[str] = []
    if rap is not None and rap >= 10:
        bits.append("RAP erhöht als Hinweis auf rechtskardiale Füllungsdruckerhöhung")
    if ci is not None and ci < 2.0:
        bits.append("CI erniedrigt im Sinne einer Low output Konstellation")
    if pac is not None and pac < 2.0:
        if pp is not None and pp >= 30:
            bits.append("verminderte pulmonalarterielle Compliance mit erhöhter pulsatile RV Nachlast")
        else:
            bits.append("verminderte pulmonalarterielle Compliance als Hinweis auf erhöhte pulsatile RV Nachlast")
    return bits


def _hemo_pvod_line(d: Dict[str, Any], mpap: float, pawp: float) -> str:
    try:
        lvl = _safe_float(d.get("pvod_hint_level"))
        desc = str(d.get("pvod_hint_desc") or "").strip()
        if lvl is not None and lvl >= 2 and desc and mpap > 20 and pawp <= 15:
            return f"Zusätzlich bestehen Red Flags für PVOD/PCH (DD): {desc}."
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_PVOD_HINT", "PVOD/PCH hint rendering failed.", exc)
    return ""


def _hemo_volume_line(d: Dict[str, Any]) -> str:
    if not bool(d.get("volume_challenge_done")):
        return ""
    pawp_post = _safe_float(d.get("vol_challenge_pawp_post"))
    if pawp_post is None:
        return ""
    if pawp_post >= 18:
        return (
            "Die Volumenprovokation zeigt einen Anstieg der PAWP auf ≥18 mmHg und spricht damit für eine okkulte diastolische LV Dysfunktion/HFpEF. "
            "Hinweis: Für die hämodynamische Antwort auf Fluid challenge bei PAH sind die Daten limitiert."
        )
    return "Die Volumenprovokation zeigt keinen Anstieg der PAWP auf ≥18 mmHg und ergibt damit keinen Hinweis auf eine okkulte HFpEF Konstellation."


def _hemo_exercise_lines(d: Dict[str, Any]) -> List[str]:
    if not bool(d.get("exercise_done")):
        return []
    lines: List[str] = []
    slope_line = _doctor_beurteilung_slope_line(d)
    if slope_line:
        lines.append(slope_line)

    inter = d.get("exercise_interpretability")
    if inter == "ok" and d.get("exercise_pattern"):
        patt = _describe_exercise_response_2pt(d)
        if patt:
            lines.append("Belastungsreaktion: " + patt)
        return lines
    if inter not in ("hard_stop", "numeric_only"):
        return lines

    hard = d.get("exercise_hard_fail_flags") or []
    soft = d.get("exercise_soft_flags") or []
    reasons = _doctor_beurteilung_flag_reasons(list(hard) + list(soft))
    if not reasons:
        return lines
    if inter == "hard_stop":
        lines.append("Belastungs-Slopes nicht interpretierbar: " + "; ".join(reasons) + ".")
    else:
        lines.append("Belastungs-Slopes nur eingeschränkt interpretierbar: " + "; ".join(reasons) + ".")
    return lines


def _build_hemo_interpretation_paragraph(der: Dict[str, Any]) -> str:
    """Generate a guideline-aligned interpretation paragraph under Beurteilung."""
    d = der or {}
    mpap = _safe_float(d.get("mpap_rest"))
    pawp = _safe_float(d.get("pawp_rest"))
    pvr = _safe_float(d.get("pvr_rest"))
    if mpap is None or pawp is None or pvr is None:
        return ""

    rap = _safe_float(d.get("rap_rest"))
    ci = _safe_float(d.get("ci_rest"))
    co = _safe_float(d.get("co_rest"))
    pac = _safe_float(d.get("pac_rest_ml_per_mmhg"))
    pp = _safe_float(d.get("pp_pa_rest"))
    high_flow = d.get("high_flow")

    lines: List[str] = []
    lines.append(_hemo_non_ph_statement(pawp, pvr) if mpap <= 20 else _hemo_ph_statement(mpap, pawp, pvr, co, ci, high_flow))

    add_bits = _hemo_additional_bits(rap, ci, pac, pp)
    if add_bits:
        lines.append("Zusätzlich zeigen sich " + "; ".join(add_bits) + ".")

    pvod_line = _hemo_pvod_line(d, mpap, pawp)
    if pvod_line:
        lines.append(pvod_line)
    volume_line = _hemo_volume_line(d)
    if volume_line:
        lines.append(volume_line)
    lines.extend(_hemo_exercise_lines(d))

    return "\n".join([line.strip() for line in lines if str(line).strip()])


def _compose_rest_hemo_parenthetical(d: Dict[str, Any], ui: Dict[str, Any], existing_text: str = "") -> str:
    """Return one parenthetical with mandatory rest hemodynamics.

    The parenthetical is composed so callers can append/replace it into a
    Beurteilung sentence. Tokens already mentioned in `existing_text` are
    skipped to avoid duplication.
    """
    parts = _compose_rest_hemo_parts(d, ui, existing_text=existing_text)
    if not parts:
        return ""
    return "(" + ", ".join(parts) + ")"


def _compose_rest_hemo_parts(d: Dict[str, Any], ui: Dict[str, Any], existing_text: str = "") -> List[str]:
    """Return the list of missing rest-hemodynamic value tokens.

    Unlike `_compose_rest_hemo_parenthetical`, this returns the raw tokens so
    the caller can embed them as a prose clause (e.g. "Hämodynamik: X, Y, Z.")
    rather than as an orphaned parenthetical. Tokens already mentioned in
    `existing_text` are skipped.
    """
    mpap = d.get("mpap_rest")
    pawp = d.get("pawp_rest")
    pvr = d.get("pvr_rest")
    if mpap is None or pawp is None or pvr is None:
        return []

    existing_l = str(existing_text or "").lower()

    def _has(tok: str) -> bool:
        t = tok.lower().strip()
        if not t:
            return False
        return re.search(rf"\b{re.escape(t)}\b", existing_l) is not None

    bits: List[str] = []
    spap = ui.get("spap_rest")
    dpap = ui.get("dpap_rest")
    if (not _has("spap")) and (spap is not None) and (dpap is not None):
        bits.append(f"sPAP/dPAP {fmt_int(spap)}/{fmt_int(dpap)} mmHg")

    rap = d.get("rap_rest")
    co = d.get("co_rest")
    if co is None:
        co = d.get("co")
    ci = d.get("ci_rest")
    if ci is None:
        ci = d.get("ci")

    token_builders: List[Tuple[str, str]] = [
        ("mpap", f"mPAP {fmt_int(mpap)} mmHg"),
        ("pawp", f"PAWP {fmt_int(pawp)} mmHg"),
        ("rap", f"RAP {fmt_int(rap)} mmHg" if rap is not None else ""),
        ("co", f"CO {fmt_float(co, 2)} l/min" if co is not None else ""),
        ("ci", f"CI {fmt_float(ci, 2)} l/min/m²" if ci is not None else ""),
        ("pvr", f"PVR {fmt_float(pvr, 2)} WU"),
    ]
    for tok, text in token_builders:
        if (not _has(tok)) and text:
            bits.append(text)

    return bits


def _append_doctor_procedere_block(
    *,
    report: List[str],
    ui: Dict[str, Any],
    all_mods: List[str],
    modules_txts: List[str],
    skipped_mods_txts: List[str],
    auto_mods_txts: List[str],
    recs: List[str],
) -> None:
    if not (modules_txts or skipped_mods_txts or auto_mods_txts or ui.get("procedere_free") or recs):
        return

    # Heading normalization: no trailing colon. Section sub-groups use ### so the
    # hierarchy mirrors ## Beurteilung / ## Interpretation.
    #
    # Spacing rule: the outer list is joined with ``"\n".join(report)``, so every
    # block that should begin a new paragraph prepends ``"\n"`` itself. That
    # yields the blank line required by CommonMark renderers between paragraphs
    # and before/after Markdown headings — without which a ``### Heading`` glued
    # to the preceding paragraph silently loses its heading semantics.
    # Keep the section heading tight: no trailing newline. The next chunk
    # provides its own leading "\n" if blank-line spacing is needed. This avoids
    # two stacked blank lines when no primary modules are selected
    # (heading → empty → next ### subsection).
    report.append("\n## Empfehlung und Procedere")
    if all_mods:
        report.append("\n**Übernommene Module:** " + ", ".join(all_mods))
    if modules_txts:
        # Each module block already carries a "**Pxx – Title**\n\n<body>" shape;
        # joining with two newlines keeps the blank line between modules.
        report.append("\n" + "\n\n".join(modules_txts))
    if skipped_mods_txts:
        report.append("\n### In dieser Konstellation nicht anwählbar\n\n" + "\n".join(skipped_mods_txts))
    if auto_mods_txts:
        report.append(
            "\n### Weitere Regelwerk-Vorschläge (nicht automatisch übernommen)\n\n"
            + "\n".join(auto_mods_txts)
        )
    free = str(ui.get("procedere_free") or "").strip()
    if free:
        report.append("\n### Freitext\n\n" + free)
    if recs:
        report.append("\n### Zusätzliche Hinweise\n\n" + "\n".join(f"- {r}" for r in recs))


def _sanitize_recommendation_text(empfehlung: str) -> str:
    """Remove pathophysiology duplication from recommendation text."""
    try:
        empfehlung = re.sub(
            r"\s*Es\s+liegen\s+hämodynamische\s+Kriterien[^.]*\.\s*",
            " ",
            empfehlung,
            flags=re.IGNORECASE,
        )
        empfehlung = re.sub(
            r"\s*\([^)]*(mPAP|PAWP|PVR|TPG|DPG)[^)]*\)\s*",
            " ",
            empfehlung,
            flags=re.IGNORECASE,
        )
        return " ".join(str(empfehlung or "").split())
    except (TypeError, ValueError, re.error) as exc:
        log_exception("RHK_REP_RECOMMENDATION_SANITIZE", "Recommendation de-dup/sanitize failed.", exc)
        return str(empfehlung or "").strip()


def _doctor_rest_hemo_line(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    lines = [
        f"- sPAP {_fmt(ui.get('spap_rest'),0)} / dPAP {_fmt(ui.get('dpap_rest'),0)} / mPAP {_fmt(der.get('mpap'),0)} mmHg",
        f"- PAWP {_fmt(ui.get('pawp_rest'),0)} mmHg, RAP {_fmt(ui.get('rap_rest'),0)} mmHg",
        f"- CO {_fmt(der.get('co'),2)} l/min, CI {_fmt(der.get('ci'),2)} l/min/m²",
    ]
    if der.get("sv_rest_ml") is not None or der.get("svi_rest_ml_m2") is not None:
        lines.append(f"- SV {_fmt(der.get('sv_rest_ml'),0)} ml, SVI {_fmt(der.get('svi_rest_ml_m2'),0)} ml/m²")

    tail = [f"PVR {_fmt(der.get('pvr'),2)} WU"]
    for key, label, digits, unit in (
        ("pvri", "PVRi", 2, "WU·m²"),
        ("tpg", "TPG", 0, "mmHg"),
        ("dpg", "DPG", 0, "mmHg"),
        ("pp_pa_rest", "PP (PA)", 0, "mmHg"),
        ("pac_rest_ml_per_mmhg", "PAC", 0, "ml/mmHg"),
        ("rc_time_rest_s", "RC-Zeit", 2, "s"),
    ):
        val = der.get(key)
        if val is not None:
            tail.append(f"{label} {_fmt(val,digits)} {unit}".strip())
    lines.append("- " + ", ".join(tail))
    return "\n".join(lines)


def _doctor_exercise_qc_line(der: Dict[str, Any]) -> str:
    inter = der.get("exercise_interpretability")
    if inter not in ("hard_stop", "numeric_only"):
        return ""
    hard = der.get("exercise_hard_fail_flags") or []
    soft = der.get("exercise_soft_flags") or []
    reasons = [_exercise_flag_to_text(x) for x in (hard + soft) if x]
    reasons = [r for r in reasons if str(r).strip()]
    return _md_kv("QC", "; ".join(reasons) if reasons else "ok")


def _doctor_exercise_response_line(der: Dict[str, Any]) -> str:
    if der.get("exercise_interpretability") != "ok" or not der.get("exercise_pattern"):
        return ""
    return _md_kv("Belastungsreaktion", _describe_exercise_response_2pt(der).rstrip("."))


def _doctor_exercise_block(der: Dict[str, Any]) -> str:
    if not der.get("exercise_done"):
        return ""
    lines = [
        _md_kv("Belastung", "semi supine, Slope Ruhe→Peak"),
        _md_kv("dCO", f"{_fmt(der.get('dco'),1)} L/min"),
        _md_kv("ΔmPAP/ΔCO", f"{_fmt(der.get('mpap_co_slope'),2)} mmHg/(L/min)"),
        _md_kv("ΔPAWP/ΔCO", f"{_fmt(der.get('pawp_co_slope'),2)} mmHg/(L/min)"),
        _md_kv("ΔTPG/ΔCO", f"{_fmt(der.get('tpg_co_slope_2pt'),2)} mmHg/(L/min)"),
        _md_kv("ΔsPAP (Peak–Ruhe)", f"{_fmt(der.get('delta_spap'),0)} mmHg"),
        _md_kv("Peak CI", f"{_fmt(der.get('ci_peak'),2)} l/min/m²"),
    ]
    adap = der.get("adaptation_type")
    if adap:
        label = "homeometrisch" if adap == "homeometric" else "heterometrisch"
        lines.append(_md_kv("Adaptionstyp", label))

    qc_line = _doctor_exercise_qc_line(der)
    if qc_line:
        lines.append(qc_line)
    resp_line = _doctor_exercise_response_line(der)
    if resp_line:
        lines.append(resp_line)
    return "### Belastungshämodynamik\n" + "\n".join(lines)


def _doctor_volume_block(der: Dict[str, Any]) -> str:
    if not der.get("volume_challenge_done"):
        return ""
    lines: List[str] = []
    pawp_pre = der.get("vol_challenge_pawp_pre")
    pawp_post = der.get("vol_challenge_pawp_post")
    if pawp_pre is not None and pawp_post is not None:
        lines.append(_md_kv("PAWP", f"{_fmt(pawp_pre,0)} → {_fmt(pawp_post,0)} mmHg"))
        if der.get("vol_challenge_delta_pawp") is not None:
            lines.append(_md_kv("PAWP (Δ)", f"{_fmt(der.get('vol_challenge_delta_pawp'),0)} mmHg"))
    else:
        lines.append(_md_kv("PAWP", "—"))

    if der.get("vol_challenge_delta_mpap") is not None:
        lines.append(_md_kv("mPAP (Δ)", f"{_fmt(der.get('vol_challenge_delta_mpap'),0)} mmHg"))
    if pawp_post is not None:
        endp = "PAWP ≥18 mmHg (Hinweis okkulte HFpEF)" if bool(der.get("vol_challenge_pawp_ge_18")) else "PAWP <18 mmHg"
        lines.append(_md_kv("Endpunkt", endp))
    return "### Volumenchallenge\n" + "\n".join(lines)


def _doctor_vaso_block(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    if not der.get("vaso_test_done"):
        return ""
    lines = [_md_kv("Agent", str(ui.get("vaso_agent") or "—"))]
    if ui.get("vaso_response_desc"):
        lines.append(_md_kv("Antwort", str(ui.get("vaso_response_desc"))))
    return "### Vasoreaktivität\n" + "\n".join(lines)


def _doctor_stepox_block(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    sat_pairs = [("sat_svc", "SVC"), ("sat_ra", "RA"), ("sat_rv", "RV"), ("sat_pa", "PA"), ("sat_ao", "System")]
    sat_filled = sum(1 for key, _ in sat_pairs if _safe_float(ui.get(key)) is not None)
    if sat_filled < 3:
        return ""

    lines: List[str] = []
    for key, label in sat_pairs:
        val = _safe_float(ui.get(key))
        if val is not None:
            lines.append(_md_kv(label, f"{_fmt(val,0)}%"))
    lines.append(_md_kv("Interpretation", der.get("step_up_sentence") or "—"))
    return "### Stufenoxymetrie\n" + "\n".join(lines)


def _doctor_curve_block(der: Dict[str, Any]) -> str:
    defs = [
        ("v_wave", "V-Welle (PAWP)"),
        ("a_wave", "A-Welle (PAWP)"),
        ("rap_a_wave_flag", "A-Welle (RAP)"),
        ("rap_v_wave_flag", "V-Welle (RAP)"),
        ("rv_pseudo_dip_flag", "Pseudo-Dip (RV)"),
        ("rv_dip_plateau_flag", "Dip-Plateau (RV)"),
    ]
    flags = [label for key, label in defs if der.get(key)]
    if not flags:
        return ""
    return "### Kurvenmorphologie\n" + _md_kv("Befund", ", ".join(flags))


def _build_doctor_structured_sections(ui: Dict[str, Any], der: Dict[str, Any]) -> Dict[str, str]:
    """Build structured RHK sub-sections for the doctor report."""
    return {
        "rest_line": _doctor_rest_hemo_line(ui, der),
        "exercise_block": _doctor_exercise_block(der),
        "volume_block": _doctor_volume_block(der),
        "vaso_block": _doctor_vaso_block(ui, der),
        "stepox_block": _doctor_stepox_block(ui, der),
        "curve_block": _doctor_curve_block(der),
    }


def _doctor_procedere_module_state(
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
) -> Tuple[List[str], List[str], List[str], Dict[str, str]]:
    selected = _normalize_module_ids(ui.get(K_MODULES) or [])
    decision_mods = _normalize_module_ids(dec.get(K_MODULES) or [])

    policy = der.get("p_module_policy") or {}
    eff_policy = pmods_apply_overrides(policy, pmods_get_force_optional(ui))
    disabled_mods: Dict[str, str] = eff_policy.get("disabled") or {}
    allowed_order: List[str] = eff_policy.get("allowed") or list(_ALL_P_MODULE_IDS)
    order_index = {mid: idx for idx, mid in enumerate(allowed_order)}

    all_mods = sorted([m for m in selected if m not in disabled_mods], key=lambda m: order_index.get(m, 10_000))
    skipped_mods = [m for m in selected if m in disabled_mods]
    auto_mods = sorted([m for m in decision_mods if m not in selected], key=lambda m: order_index.get(m, 10_000))
    return all_mods, skipped_mods, auto_mods, disabled_mods


def _doctor_procedere_render_text(
    mid: str,
    blk: Optional[TextBlock],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> str:
    if mid == "P01":
        return str(render_p01_dynamic(env) or "").strip()
    if not blk:
        return ""
    # Respect `required_context` metadata from the TextBlock: if any declared
    # placeholder is missing or empty in the render context, fall back to the
    # raw template (without substitution) so the reader sees the module's
    # standalone prose — not an accidental `{therapy_plan_sentence}` token.
    # This matters for P03-P06 whose templates combine a baseline paragraph
    # with an injected context sentence; when the injection is empty, we want
    # the baseline to render cleanly, not with a blank line where the sentence
    # would have been.
    required = tuple(getattr(blk, "required_context", ()) or ())
    if required:
        missing = [k for k in required if not str(ctx.get(k, "")).strip()]
        if missing:
            # Remove the placeholder tokens (and their surrounding newline if
            # they sit on their own line) from the template before rendering,
            # so the remaining baseline text reads as a complete module.
            tmpl = blk.template
            for k in missing:
                tmpl = re.sub(r"\n?\{" + re.escape(k) + r"\}\n?", "\n", tmpl)
                tmpl = tmpl.replace("{" + k + "}", "")
            # Build a scratch block with the cleaned template so downstream
            # rendering still has all the other context variables.
            scratch = TextBlock(
                id=blk.id,
                title=blk.title,
                applies_to=blk.applies_to,
                template=tmpl,
                category=blk.category,
                variants=dict(blk.variants),
                notes=blk.notes,
                level_default=getattr(blk, "level_default", 3),
                clinical_group=getattr(blk, "clinical_group", "misc"),
                required_context=tuple(k for k in required if k not in missing),
            )
            return str(filter_module_text(render_block(scratch, ctx), env) or "").strip()
    return str(filter_module_text(render_block(blk, ctx), env) or "").strip()


def _doctor_procedere_module_texts(
    all_mods: List[str],
    blocks: Dict[str, TextBlock],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> List[str]:
    """Render selected modules with bold labels for inline readability.

    We use bold (``**Pxx – Title**``) rather than a Markdown heading on purpose:
    the surrounding section already owns the ``## Empfehlung und Procedere`` and
    ``### Weitere Regelwerk-Vorschläge`` headings. Promoting every individual
    module to ``###`` would clutter the table of contents and break the sibling
    relationship between "selected modules" and the subsections that list
    alternatives. Some module templates also start with their own ``###`` line
    (e.g. ``### Hyperzirkulation / flussdominante Druckerhöhung``) — we strip
    that leading heading so we never emit two headings in a row.
    """
    lines: List[str] = []
    for mid in all_mods:
        blk = blocks.get(mid)
        txt = _doctor_procedere_render_text(mid, blk, env, ctx)
        if not txt:
            continue
        title = (blk.title if blk else mid) if mid != "P01" else blocks.get(mid, TextBlock(mid, mid, "", "module")).title
        # If the template starts with a Markdown heading (### …), drop it —
        # our bold label provides the visual anchor.
        cleaned = re.sub(r"^\s{0,3}#{1,6}\s+[^\n]*\n?", "", txt, count=1).strip()
        if not cleaned:
            continue
        lines.append(f"**{mid} – {title}**\n\n{cleaned}")
    return lines


def _doctor_procedere_module_preview(
    mid: str,
    blk: Optional[TextBlock],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> str:
    """Build a short, sentence-aware preview for modules not directly adopted.

    Rationale: the preview is inlined into a bullet-list item (``- **Pxx – Title**:
    <preview>``). Raw module text may contain Markdown headings (``### …``), blank
    lines or long sentences — all of which look broken inline. We:

    - Strip internal Markdown headings (``#``/``##``/``###``/``####``) and bold/italic
      emphasis so the preview reads as prose, not as inline Markdown.
    - Pick the first 1–2 complete sentences via ``_split_sentences`` (abbreviation-
      aware — "u.a.", "z.B." etc. do not end a sentence).
    - Cap at ~50 words using ``_truncate_words`` with ``require_clean_end=True`` so
      a truncation can never cut mid-word ("…Vorwärtsleist…") or mid-abbreviation.
    """
    try:
        preview = _doctor_procedere_render_text(mid, blk, env, ctx)
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_MODULE_PREVIEW", "Module preview rendering failed.", exc, module_id=mid)
        preview = ""
    raw = str(preview or "")
    # Drop Markdown heading lines (### Foo) entirely — they are structural
    # markers in the full module text but become noise when inlined.
    raw = re.sub(r"(?m)^\s{0,3}#{1,6}\s+[^\n]*\n?", "", raw)
    # Collapse whitespace so downstream sentence splitting is predictable.
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return ""
    # First two sentences as the preview candidate; most modules have their
    # key clinical message in the first sentence.
    sents = _split_sentences(raw)
    candidate = " ".join(sents[:2]).strip() if sents else raw
    if not candidate:
        return ""
    # Soft word cap: keep previews punchy but never cut mid-word. Falls back
    # to the first complete sentence when the 50-word budget is exceeded.
    if _word_count(candidate) > 50:
        clean = _truncate_words(candidate, 50, require_clean_end=True)
        if clean:
            return clean
        # 50-word budget too tight — try the first sentence alone.
        if sents:
            first = sents[0].strip()
            if first and first[-1] not in ".!?":
                first += "."
            return first
    return candidate


def _doctor_procedere_skipped_texts(
    skipped_mods: List[str],
    blocks: Dict[str, TextBlock],
    disabled_mods: Dict[str, str],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> List[str]:
    lines: List[str] = []
    for mid in skipped_mods:
        blk = blocks.get(mid)
        title = blk.title if blk else mid
        preview = _doctor_procedere_module_preview(mid, blk, env, ctx)
        reason = str(disabled_mods.get(mid) or "").strip()
        if preview:
            lines.append(f"- **{mid} – {title}**: {preview} _Grund: {reason}_")
        else:
            lines.append(f"- **{mid} – {title}**. _Grund: {reason}_")
    return lines


def _doctor_procedere_auto_texts(
    auto_mods: List[str],
    blocks: Dict[str, TextBlock],
    disabled_mods: Dict[str, str],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> List[str]:
    """Build bullet entries for the "Weitere Regelwerk-Vorschläge" section.

    The trailing "(Vorschlag, nicht automatisch übernommen)" on every bullet is
    intentionally omitted: the section heading already states that, so repeating
    it on each line is redundant and clutters the output. Only the "(nicht
    anwählbar)" note with its reason is kept, because it conveys distinct
    information (why the module was suppressed despite matching a rule).
    """
    lines: List[str] = []
    for mid in auto_mods:
        blk = blocks.get(mid)
        title = blk.title if blk else mid
        preview = _doctor_procedere_module_preview(mid, blk, env, ctx)
        reason = str(disabled_mods.get(mid) or "").strip()
        if reason:
            if preview:
                lines.append(f"- **{mid} – {title}** (nicht anwählbar): {preview} _Grund: {reason}_")
            else:
                lines.append(f"- **{mid} – {title}** (nicht anwählbar). _Grund: {reason}_")
            continue
        if preview:
            lines.append(f"- **{mid} – {title}**: {preview}")
        else:
            lines.append(f"- **{mid} – {title}**.")
    return lines


def _doctor_procedere_format_recommendation(item: Any, ctx: Dict[str, Any]) -> str:
    try:
        return str(item).format_map(SafeDict(ctx)).strip()
    except (KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_REP_RECOMMENDATION_FORMAT", "Recommendation template formatting failed.", exc)
        return str(item).strip()


def _doctor_procedere_recommendations(
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
    ctx: Dict[str, Any],
) -> List[str]:
    recs = [_doctor_procedere_format_recommendation(r, ctx) for r in (dec.get("recommendations") or []) if str(r).strip()]
    tr_rec = str(ctx.get("comparison_recommendation_doc") or "").strip()
    if tr_rec and tr_rec not in recs:
        recs = list(recs) + [tr_rec]

    if bool(der.get("exercise_values_present")) and not bool(der.get("exercise_done")):
        recs = list(recs) + [
            "Hinweis: Belastungswerte sind im Datensatz vorhanden, die Belastungshämodynamik wurde jedoch nicht als durchgeführt markiert (Checkbox nicht gesetzt). "
            "Interpretation/Übernahme erfolgt daher nicht. Bitte ggf. Modul aktivieren oder Werte entfernen."
        ]

    age = _safe_float(ui.get("age"))
    if age is not None and age >= 70 and recs:
        recs = [r for r in recs if ("transplant" not in str(r).lower()) and ("ltx" not in str(r).lower())]
    return recs


def _doctor_procedere_concluding(dec: Dict[str, Any], der: Dict[str, Any]) -> str:
    eti = der.get(K_PH_ETIOLOGY) if isinstance(der, dict) else None
    if isinstance(eti, dict) and str(eti.get("doc_conclusion") or "").strip():
        return str(eti.get("doc_conclusion") or "").strip()
    leading_cause = dec.get("leading_cause") or "unklaren Genese"
    return f"In der Zusammenschau der Befunde gehen wir von einer führenden **{leading_cause}** aus."


# Ordered by "action strength" — the first tuple wins when a recommendation
# matches multiple groups. Referring physicians want "where do I send the
# patient next?" answered before "what else should I check?" — so board/center
# presentations rank above generic follow-up or "Kontrolle" keywords.
_EPIKRISE_NEXT_STEPS_GROUPS: Tuple[Tuple[str, ...], ...] = (
    # 1. Concrete referral / board presentation — highest yield for Einweiser.
    ("PH-Zentrum", "PH-Board", "CTEPH-", "Fibrose-Sprechstunde", "Vorstellung", "Board"),
    # 2. Therapy follow-up loops — next-best.
    ("Reevaluation", "Verlaufskontrolle", "Gerinnungsambulanz"),
    # 3. Generic "clarify" actions — last resort, usually better covered in
    # the Procedere section below.
    ("Abklärung", "Kontrolle"),
)


def _epikrise_shorten_next_step(text: str, *, action_keywords: Tuple[str, ...] = ()) -> str:
    """Condense a recommendation sentence for the epikrise bullet.

    Rules:
    - Split off the leading label ("CTEPH/CTEPD-Verdacht:", "Hinweis:", …) —
      it usually just restates what is already in the Diagnose/Ätiologie line.
    - Pick the sentence that actually *contains* the matched action keyword
      (board/presentation/abklärung). A naive "first sentence" rule breaks on
      recs like ``"Bei Lungenerkrankung/Gruppe 3 und PVR >5 WU: Hinweis auf
      schwere PH. Abklärung/Management im PH-Zentrum empfohlen; …"`` — the
      first sentence is a *finding*, the actionable content is in sentence 2.
    - If the picked sentence is too long, prefer a semicolon split that still
      contains the action keyword — clean clause boundary beats mid-word
      ellipsis every time.
    - Hard-cap at ~180 chars so the epikrise stays scannable without cutting
      off trailing qualifiers ("… im PH-Zentrum") on slightly-long recs.
    """
    rs = str(text or "").strip()
    if not rs:
        return ""
    # Drop a leading "Label: " prefix (``CTEPH/CTEPD-Verdacht: Bitte …`` →
    # ``Bitte …``) — but only if the label is short enough to plausibly be a
    # stem identifier, not a full sentence.
    lead_match = re.match(r"^[^:]{2,40}:\s+(?=[A-ZÄÖÜ])", rs)
    if lead_match:
        rs = rs[lead_match.end():]
    sents = _split_sentences(rs)
    if not sents:
        return rs
    # Find the first sentence that mentions the action keyword. If none do,
    # fall back to the first sentence (better than nothing).
    picked = sents[0]
    if action_keywords:
        for s in sents:
            if any(kw in s for kw in action_keywords):
                picked = s
                break
    # If the sentence has a natural semicolon break, keep only as many clauses
    # as we need to include the action keyword — this handles recs like
    # ``Abklärung/Management im PH-Zentrum empfohlen; Therapie primär …``
    # where the entire second clause is background detail.
    if ";" in picked:
        clauses = [c.strip() for c in picked.split(";") if c.strip()]
        if clauses:
            if action_keywords:
                acc: List[str] = []
                for c in clauses:
                    acc.append(c)
                    if any(kw in c for kw in action_keywords):
                        break
                candidate = "; ".join(acc).strip()
            else:
                candidate = clauses[0]
            # Only accept the shortened form if it still carries the action
            # keyword (or none was requested) and it is actually shorter.
            if candidate and len(candidate) < len(picked) and (
                not action_keywords or any(kw in candidate for kw in action_keywords)
            ):
                picked = candidate
    # Char cap: allow up to 180 chars for a clean sentence; beyond that we
    # truncate at the last word boundary and add an ellipsis.
    if len(picked) > 180:
        cut = picked[:170].rsplit(" ", 1)[0]
        picked = cut + "…"
    if picked and picked[-1] not in ".!?…":
        picked += "."
    return picked


def _epikrise_rank_next_steps(recs: List[str]) -> List[str]:
    """Pick *one* action-oriented recommendation for the epikrise.

    Design choice — only one item: the epikrise is a glanceable summary, not a
    checklist. A referring physician opening the letter should see exactly the
    single most important next step; every additional bullet dilutes the
    signal and pushes the detailed Procedere section further down the screen.
    The full recommendation list lives in ``## Empfehlung und Procedere →
    Zusätzliche Hinweise`` below, which is the correct home for the long tail.

    Algorithm:
    - Score each rec by the *highest-priority* keyword group it matches (group 0
      beats group 1 beats group 2; no match → drop).
    - Sort by (group_index, insertion_order) so board/presentation recs come
      first while preserving the rule engine's stable ordering within a group.
    - Emit the top-ranked item, condensed to its first actionable sentence.
    """
    scored: List[Tuple[int, int, str]] = []
    for idx, r in enumerate(recs or []):
        rs = str(r).strip()
        if not rs:
            continue
        for grp_idx, kws in enumerate(_EPIKRISE_NEXT_STEPS_GROUPS):
            if any(kw in rs for kw in kws):
                scored.append((grp_idx, idx, rs))
                break
    scored.sort(key=lambda t: (t[0], t[1]))

    for grp_idx, _, rs in scored:
        # Pass the matching group's keywords so the shortening helper can
        # pick the sentence that *contains* the action verb, not just the
        # first sentence — otherwise a leading "Hinweis auf schwere PH."
        # finding can mask the actionable "Abklärung/Management im PH-Zentrum"
        # clause that follows.
        short = _epikrise_shorten_next_step(
            rs, action_keywords=_EPIKRISE_NEXT_STEPS_GROUPS[grp_idx]
        )
        if short:
            return [short]
    return []


def _build_doctor_epikrise(
    *,
    case: CaseLike,
    ui: Dict[str, Any],
    dec: Dict[str, Any],
    der: Dict[str, Any],
    recs: List[str],
) -> str:
    """Build a short Kurzepikrise at the top of the doctor report.

    Audience: the referring physician ("Einweiser") who opens the letter and
    wants the bottom line in 10 seconds — diagnosis, etiology, the four
    hemodynamic numbers that classify the case, functional class/risk, and a
    hint at the next concrete step. All downstream sections (Anamnese, Labor,
    RHK, Beurteilung, Interpretation, Procedere) still provide the full
    reasoning; this block is a signpost, never a substitute.

    Design notes:
    - We use a dash-separated list of bold labels + values (not a Markdown
      definition list) because definition lists render inconsistently across
      Markdown processors (notably the Gradio/html preview vs. the DOCX export).
    - ``·`` (middle dot) separates tokens inside a bullet so each line stays
      readable when it wraps — unlike commas, which can blur with the comma
      decimals German clinicians use for SI units (``2,49 l/min/m²``).
    - The block is suppressed entirely if no primary diagnosis is available;
      a half-filled epikrise is worse than none because it signals missing data
      where the detailed sections below would give a correct partial picture.
    """
    primary_dx = str(dec.get("primary_dx") or "").strip() if isinstance(dec, dict) else ""
    if not primary_dx:
        return ""

    # No-PH cases: the rule engine sometimes still fills ph_etiology from
    # scaffolding data (e.g. borderline echo, mild diastolic dysfunction).
    # Showing "Ätiologie: Gruppe 2" right below "Diagnose: Kein Hinweis auf PH"
    # is confusing and factually wrong — so we detect the negation early and
    # suppress the etiology line on this path.
    dx_lower = primary_dx.lower()
    is_no_ph = any(
        token in dx_lower
        for token in ("kein hinweis auf", "kein hinweis auf eine pulmonale", "keine pulmonale hypertonie")
    )

    lines: List[str] = []

    # 1) Diagnose — the single most important line.
    lines.append(f"- **Diagnose:** {primary_dx}")

    # 2) Ätiologie — only if the etiology engine produced a conclusion AND
    # the primary diagnosis actually asserts PH. We strip a redundant
    # "Ätiologische Einordnung:" prefix so the label isn't stuttered twice.
    eti_line = ""
    if not is_no_ph:
        eti = der.get(K_PH_ETIOLOGY) if isinstance(der, dict) else None
        if isinstance(eti, dict):
            eti_line = str(eti.get("doc_conclusion") or "").strip()
    if eti_line:
        eti_line = re.sub(
            r"^(Ätiologische\s+Einordnung|Ätiologie)\s*[:–—-]\s*",
            "",
            eti_line,
            flags=re.IGNORECASE,
        ).strip()
        # First sentence only — details live in ## Interpretation.
        eti_first = _split_sentences(eti_line)
        eti_short = eti_first[0] if eti_first else eti_line
        if eti_short and eti_short[-1] not in ".!?":
            eti_short += "."
        lines.append(f"- **Ätiologie:** {eti_short}")

    # 3) Kernhämodynamik — the four numbers that classify every PH case.
    mpap = _safe_float(der.get("mpap_rest") if der.get("mpap_rest") is not None else der.get("mpap"))
    pawp = _safe_float(der.get("pawp_rest") if der.get("pawp_rest") is not None else der.get("pawp"))
    pvr = _safe_float(der.get("pvr_rest") if der.get("pvr_rest") is not None else der.get("pvr"))
    ci = _safe_float(der.get("ci_rest") if der.get("ci_rest") is not None else der.get("ci"))
    hemo: List[str] = []
    if mpap is not None:
        hemo.append(f"mPAP {_fmt(mpap, 0)} mmHg")
    if pawp is not None:
        hemo.append(f"PAWP {_fmt(pawp, 0)} mmHg")
    if pvr is not None:
        hemo.append(f"PVR {_fmt(pvr, 1)} WU")
    if ci is not None:
        hemo.append(f"CI {_fmt(ci, 2)} l/min/m²")
    if hemo:
        lines.append("- **Hämodynamik (Ruhe):** " + " · ".join(hemo))

    # 4) Funktion & Risiko — one consolidated line; order is left-to-right
    # most salient to least (FC first, risk stratifier last because its label
    # is long).
    fc = str(ui.get("who_fc") or "").strip()
    six = _safe_float(ui.get("six_mwd_m"))
    bnp = _safe_float(ui.get("nt_probnp"))
    scores = case.get(K_SCORES) or {}
    risk4 = str(scores.get("esc_ers_4s") or "").strip()
    func: List[str] = []
    if fc:
        func.append(f"WHO-FC {fc}")
    if six is not None:
        func.append(f"6MWD {_fmt(six, 0)} m")
    if bnp is not None:
        func.append(f"NT-proBNP {_fmt(bnp, 0)} pg/ml")
    if risk4:
        func.append(f"ESC/ERS 4-Strata {risk4}")
    if func:
        lines.append("- **Funktion & Risiko:** " + " · ".join(func))

    # 5) Nächste Schritte — up to two ranked, shortened action items.
    # The ranking prefers board/center presentations (highest yield for
    # referring physicians) over generic "Kontrolle"-style bullets, and the
    # shortener strips label prefixes so each bullet reads as a clean action
    # sentence rather than a rule-engine memo.
    next_steps = _epikrise_rank_next_steps(recs)
    if next_steps:
        lines.append("- **Nächste Schritte:** " + " ".join(next_steps))

    if not lines:
        return ""
    return "## Zusammenfassung\n\n" + "\n".join(lines) + "\n"


def _build_doctor_procedere_payload(
    *,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
    blocks: Dict[str, TextBlock],
) -> Dict[str, Any]:
    """Build module/procedere payload for the doctor report."""
    all_mods, skipped_mods, auto_mods, disabled_mods = _doctor_procedere_module_state(ui, der, dec)
    modules_txts = _doctor_procedere_module_texts(all_mods, blocks, env, ctx)
    skipped_mods_txts = _doctor_procedere_skipped_texts(skipped_mods, blocks, disabled_mods, env, ctx)
    auto_mods_txts = _doctor_procedere_auto_texts(auto_mods, blocks, disabled_mods, env, ctx)
    recs = _doctor_procedere_recommendations(ui, der, dec, ctx)
    concluding = _doctor_procedere_concluding(dec, der)
    return {
        "all_mods": all_mods,
        "modules_txts": modules_txts,
        "skipped_mods_txts": skipped_mods_txts,
        "auto_mods_txts": auto_mods_txts,
        "recs": recs,
        "concluding": concluding,
    }


def _doctor_beurteilung_base_extras(text: str, ctx: Dict[str, Any]) -> List[str]:
    extras: List[str] = []
    if ctx.get("systemic_sentence") and "System" not in text:
        extras.append(str(ctx["systemic_sentence"]).strip())
    if ctx.get("oxygen_sentence") and "ox" not in text.lower():
        extras.append(str(ctx["oxygen_sentence"]).strip())
    return extras


def _doctor_insert_rest_parenthetical(text: str, der: Dict[str, Any], ui: Dict[str, Any]) -> str:
    """Insert missing rest-hemodynamic values into a Beurteilung sentence.

    Strategy — the goal is to avoid clinically awkward output like
    "...Widerstandskomponente (PVR 6,9 WU). (sPAP/dPAP 70/35 mmHg, mPAP 47
    mmHg, RAP 14 mmHg, CO 3,60 l/min) CI 1,96 l/min/m²." which leaves an
    orphaned parenthetical dangling between two sentences.

    Preference order:
      1. If the existing text already has a "(mPAP ...)" parenthetical, replace
         it with the comprehensive one (legacy behavior, still correct).
      2. Else, emit a clean prose clause "Hämodynamik: X, Y, Z." after the
         first sentence — this reads as a medical report, not a feature-flag
         dump. Any isolated value-sentences like "CI 1,96 l/min/m²." that
         were emitted separately by the K-bundle template are folded into
         the clause to avoid dangling fragments.
    """
    parts = _compose_rest_hemo_parts(der, ui, existing_text=text)
    if not parts and not re.search(r"\b(CI|CO|mPAP|PAWP|PVR|RAP)\s+\d", text):
        return text
    if parts:
        rest_par = "(" + ", ".join(parts) + ")"
        if re.search(r"\(\s*mPAP[^)]*\)", text):
            return re.sub(r"\(\s*mPAP[^)]*\)", rest_par, text, count=1)

    # Fold isolated value-only sentences into the prose clause so the report
    # doesn't end with a stub like "CI 1,96 l/min/m²." standing alone. The
    # regex lookbehind keeps the preceding period intact so we don't glue the
    # previous sentence to the Hämodynamik clause.
    absorbed: List[str] = []
    cleaned = text

    def _absorb(pattern: str) -> None:
        nonlocal cleaned
        m = re.search(pattern, cleaned)
        if m:
            absorbed.append(m.group(1).strip())
            # Collapse the leading space and trailing period that belonged
            # to the standalone value-sentence, but keep the period of the
            # previous sentence (matched via lookbehind).
            cleaned = (cleaned[: m.start()] + " " + cleaned[m.end():]).strip()

    # Each pattern matches ". TOKEN value unit." standing by itself between
    # sentences. Order matters: absorb CI, CO, RAP, mPAP in this order since
    # they commonly appear as standalone tokens in K-bundle templates.
    _absorb(r"(?<=\.)\s+(CI\s+[\d,\.]+\s*l/min/m²)\.")
    _absorb(r"(?<=\.)\s+(CO\s+[\d,\.]+\s*l/min)\.")
    _absorb(r"(?<=\.)\s+(RAP\s+\d+\s*mmHg)\.")
    _absorb(r"(?<=\.)\s+(mPAP\s+\d+\s*mmHg)\.")

    all_parts = parts + absorbed
    if not all_parts:
        return text
    prose = "Hämodynamik: " + ", ".join(all_parts) + "."
    # Re-close the sentence that we cut from and inject the prose clause.
    dot_pos = cleaned.find(".")
    if dot_pos == -1:
        return (cleaned.strip() + " " + prose).strip()
    return (cleaned[: dot_pos + 1] + " " + prose + cleaned[dot_pos + 1 :]).strip()


def _doctor_beurteilung_slope_line(der: Dict[str, Any]) -> str:
    mpap_s = der.get("mpap_co_slope")
    pawp_s = der.get("pawp_co_slope")
    tpg_s = der.get("tpg_co_slope_2pt")
    dco = der.get("dco")
    if (dco is None) or (dco <= 0) or (mpap_s is None and pawp_s is None and tpg_s is None):
        return ""
    bits = [f"dCO {fmt_float(dco, 1)} L/min"]
    if mpap_s is not None:
        bits.append(f"ΔmPAP/ΔCO {fmt_float(mpap_s, 2)}")
    if pawp_s is not None:
        bits.append(f"ΔPAWP/ΔCO {fmt_float(pawp_s, 2)}")
    if tpg_s is not None:
        bits.append(f"ΔTPG/ΔCO {fmt_float(tpg_s, 2)}")
    return "Belastung (semi supine), Slope Ruhe→Peak: " + "; ".join(bits) + " mmHg/(L/min)."


def _doctor_beurteilung_flag_reasons(flags: List[Any]) -> List[str]:
    reasons = [_exercise_flag_to_text(x) for x in flags if x]
    return [r for r in reasons if str(r).strip()]


def _doctor_beurteilung_numeric_only_lines(soft_flags: List[Any]) -> List[str]:
    lines: List[str] = []
    if "low_peak_pawp_with_high_slope" in soft_flags:
        lines.append(
            "Numerisch erhöhte ΔPAWP/ΔCO bei niedrigem PAWP_peak unter semi supine; "
            "Interpretation eingeschränkt (häufig dCO-Artefakt oder Wedge-Messunsicherheit)."
        )
    if "slope_inconsistent" in soft_flags:
        lines.append("Slopes algebraisch inkonsistent; Eingabe oder Messartefakt wahrscheinlich.")
    if "dco_small" in soft_flags:
        lines.append("Slopes numerisch berechnet; Interpretation eingeschränkt wegen geringer ΔCO-Spannweite.")

    limiter = [x for x in soft_flags if x in ("wedge_wave_present", "af_present", "co_method_unknown", "extreme_jump_pawp", "extreme_jump_mpap")]
    lim_texts = _doctor_beurteilung_flag_reasons(limiter)
    if lim_texts:
        lines.append("Zusatzhinweise: " + "; ".join(lim_texts) + ".")
    return lines


def _doctor_beurteilung_ok_lines(der: Dict[str, Any], soft_flags: List[Any]) -> List[str]:
    lines: List[str] = []
    patt_desc = _describe_exercise_response_2pt(der)
    if patt_desc:
        lines.append(f"Belastungsreaktion: {patt_desc}")

    pawp_peak = der.get("pawp_peak")
    wedge_or_af = ("wedge_wave_present" in soft_flags) or ("af_present" in soft_flags)
    # Consolidate the PAWP-peak statement with the Wedge/AF caveat so we don't
    # emit two near-identical "Interpretation limitiert durch Wedge-Wellen/AF"
    # lines back-to-back. Previous wording produced:
    #   "PAWP_peak erhöht; Interpretation limitiert durch Wedge-Wellen/AF."
    #   "PAWP-Interpretation limitiert durch Wedge-Wellen/AF; Slopes nur …"
    pawp_elevated = pawp_peak is not None and float(pawp_peak) >= 25
    if pawp_elevated and wedge_or_af:
        lines.append(
            "PAWP_peak erhöht; Interpretation und Slopes limitiert durch Wedge-Wellen/AF – "
            "Befund nur im Gesamtkontext bewerten."
        )
    elif pawp_elevated:
        lines.append(
            "PAWP_peak unter semi supine deutlich erhöht; dies stützt eine linksatriale Druckkomponente."
        )
    elif wedge_or_af:
        lines.append(
            "PAWP-Interpretation limitiert durch Wedge-Wellen/AF; Slopes nur im Gesamtkontext bewerten."
        )
    return lines


def _doctor_beurteilung_exercise_extras(der: Dict[str, Any], ctx: Dict[str, Any]) -> List[str]:
    if not der or not der.get("exercise_done"):
        return []
    lines: List[str] = []
    if ctx.get("exercise_protocol_sentence"):
        lines.append(str(ctx["exercise_protocol_sentence"]).strip())

    slope_line = _doctor_beurteilung_slope_line(der)
    if slope_line:
        lines.append(slope_line)

    inter = der.get("exercise_interpretability")
    hard_flags = der.get("exercise_hard_fail_flags") or []
    soft_flags = der.get("exercise_soft_flags") or []
    if inter == "hard_stop":
        reasons = _doctor_beurteilung_flag_reasons(hard_flags)
        if reasons:
            lines.append("Belastungs-Slopes nicht interpretierbar: " + "; ".join(reasons) + ".")
    elif inter == "numeric_only":
        lines.extend(_doctor_beurteilung_numeric_only_lines(soft_flags))
    elif inter == "ok":
        lines.extend(_doctor_beurteilung_ok_lines(der, soft_flags))
    return lines


def _doctor_beurteilung_context_extras(text: str, der: Dict[str, Any], ctx: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    low = text.lower()
    if ctx.get("comparison_sentence") and not re.search(r"\bim\s+vergleich\b", low):
        lines.append(str(ctx["comparison_sentence"]).strip())
    if (not ctx.get("comparison_table_md")) and (not ctx.get("comparison_sentence")):
        if not re.search(r"\bhämodynamischer\s+vorbefund\b", low) and not re.search(r"\bvorbefund\s+zum\s+verlauf\b", low):
            lines.append("Ein hämodynamischer Vorbefund zum Verlauf liegt nicht vor.")

    did_prov = bool(der and (der.get("exercise_done") or der.get("volume_done") or der.get("vaso_done")))
    if (not did_prov) and (not re.search(r"keine\s+belastungs\s*-?\s*oder\s+provokationsmanöver", low)):
        lines.append("Keine Belastungs- oder Provokationsmanöver durchgeführt.")
    return lines


def _doctor_dedup_lines(lines: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for line in lines:
        key = str(line or "").strip()
        if not key:
            continue
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(key)
    return out


def _build_doctor_beurteilung_text(
    *,
    beurteilung: str,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    ctx: Dict[str, Any],
) -> str:
    """Inject deterministic dynamic additions into the assessment block."""
    out = str(beurteilung or "").strip()
    out = _doctor_insert_rest_parenthetical(out, der, ui)

    extras: List[str] = []
    extras.extend(_doctor_beurteilung_base_extras(out, ctx))
    extras.extend(_doctor_beurteilung_exercise_extras(der, ctx))
    extras.extend(_doctor_beurteilung_context_extras(out, der, ctx))
    dedup = _doctor_dedup_lines(extras)
    if not dedup:
        return out
    return (out.rstrip() + "\n\n" + "\n".join(dedup)).strip()


def _build_doctor_interpretation_text(
    *,
    case: CaseLike,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    concluding: str,
) -> str:
    """Build final interpretation block (without procedere overlap)."""
    interpretation = ""
    try:
        from rhk_interpretation import build_intelligent_interpretation

        interpretation = str(build_intelligent_interpretation(ui, der) or "").strip()
    except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_REP_INTERPRET", "Primary interpretation builder unavailable.", exc)
        interpretation = ""

    if not interpretation:
        interpretation = _build_hemo_interpretation_paragraph(der).strip()
        try:
            from rhk_hemo_deep_interpretation import build_hemo_deep_interpretation

            _deep = build_hemo_deep_interpretation(ui, der)
            if str(_deep or "").strip():
                interpretation = (interpretation + "\n\n" + str(_deep).strip()).strip() if interpretation else str(_deep).strip()
        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_REP_HEMO_DEEP", "Deep hemodynamic interpretation add-on failed.", exc)

    # Sanitize the prose-only parts (interpretation + db + concluding). The
    # etiology DD block contains a Markdown list which the sanitizer would
    # collapse into prose — so we run sanitize on the prose parts first and
    # append the DD block afterwards to preserve list structure.
    prose_parts: List[str] = []
    if interpretation:
        prose_parts.append(interpretation.strip())

    _db_ie = _report_db_text(case, audience="doctor", section="rhk_ie")
    if _db_ie:
        prose_parts.append(_db_ie)

    _dd = _build_ph_etiology_dd_block(der)
    if not _dd:
        _conc = _sanitize_concluding(concluding)
        if _conc:
            prose_parts.append(_conc)

    prose = "\n\n".join([p for p in prose_parts if p]).strip()
    prose = _sanitize_interpretation_block(prose)

    out_parts: List[str] = []
    if prose:
        out_parts.append(prose)
    if _dd:
        out_parts.append(_dd)

    return "\n\n".join([p for p in out_parts if p]).strip()


def _assemble_doctor_report_markdown(
    *,
    case: CaseLike,
    ui: Dict[str, Any],
    ctx: Dict[str, Any],
    beurteilung: str,
    interpretation_text: str,
    sections: Dict[str, str],
    all_mods: List[str],
    modules_txts: List[str],
    skipped_mods_txts: List[str],
    auto_mods_txts: List[str],
    recs: List[str],
) -> str:
    """Assemble final doctor report text from prepared payload."""
    header = (
        "# Rechtsherzkatheter – Befundbericht\n\n"
        f"**Datum:** {_dt.date.today().strftime('%d.%m.%Y')}\n"
        f"**Tool-Version:** {APP_VERSION}\n\n"
    )
    patient_line = ""
    if ui.get("name") or ui.get("firstname"):
        patient_line = f"**Patient:** {ui.get('firstname','')} {ui.get('name','')}".strip() + "\n\n"

    summary_block = summarize_inputs(case, mode="doctor")
    relevant_vor = _build_relevante_vorerkrankungen_line(ui)

    # Only render a "Relevante Vorerkrankungen" line when there is actual content.
    # Previously we always emitted "Relevante Vorerkrankungen: -", which looked
    # like a hastily filled-out form field — and the `-` placeholder read as
    # "we forgot to fill this in" rather than "none documented".
    _rv_txt = str(relevant_vor or "").strip()
    rv_line = ""
    if _rv_txt and _rv_txt not in {"-", "–", "—", "none", "None", "keine"}:
        rv_line = f"**Relevante Vorerkrankungen:** {_rv_txt}\n\n"

    # Epikrise ("Zusammenfassung") — a 4–5 bullet Einweiser-friendly summary
    # placed *above* the detailed sections. It anchors the reader before they
    # scroll through Anamnese, Labor, RHK, Beurteilung, Interpretation and
    # Procedere. The block is opt-in: only emitted when a primary diagnosis
    # has been established by the rule engine.
    der_sec = case.get(K_DERIVED) or {}
    dec_sec = case.get(K_DECISION) or {}
    epikrise_block = _build_doctor_epikrise(
        case=case,
        ui=ui,
        dec=dec_sec,
        der=der_sec,
        recs=recs,
    )
    epikrise_slot = "\n" + epikrise_block + "\n" if epikrise_block else ""

    report = [
        header,
        patient_line,
        rv_line,
        epikrise_slot,
        summary_block,
        "\n## Rechtsherzkatheter\n",
        "### Ruhehämodynamik\n",
        sections["rest_line"],
    ]
    for key in ("exercise_block", "volume_block", "vaso_block", "stepox_block", "curve_block"):
        block = str(sections.get(key) or "").strip()
        if block:
            report.append("\n" + block)

    if ctx.get("comparison_table_md"):
        report.append("\n### Verlauf / Vergleich (Vorher → Jetzt)\n")
        report.append(str(ctx.get("comparison_table_md") or "").strip() + "\n")

    report.append("\n## Beurteilung\n")
    report.append(beurteilung.strip() + "\n")
    # Heading normalization: drop the trailing colon so all top-level headings
    # look the same (## Beurteilung, ## Interpretation, ## Procedere).
    report.append("\n## Interpretation\n")
    report.append((interpretation_text + "\n") if interpretation_text else "")

    ph_tx_block = _build_ph_therapieverlauf_block(ui, case.get(K_DERIVED) or {})
    if ph_tx_block:
        report.append("\n" + ph_tx_block)

    _append_doctor_procedere_block(
        report=report,
        ui=ui,
        all_mods=all_mods,
        modules_txts=modules_txts,
        skipped_mods_txts=skipped_mods_txts,
        auto_mods_txts=auto_mods_txts,
        recs=recs,
    )

    # Assemble, then normalize blank lines: chunks maintain their own trailing
    # "\n\n", the outer "\n".join adds another between them, and empty slots
    # (e.g. missing `rv_line`) leave a gap — unmanaged this stacks to 4+ blank
    # lines before `## Zusammenfassung`. Collapse any run of 3+ newlines down
    # to 2 (one blank line) so sections are cleanly separated without visual
    # gaps that read like "something is missing here".
    joined = "\n".join(report).strip()
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined


def build_doctor_report(case: CaseLike, blocks: Dict[str, TextBlock]) -> str:
    """Public entrypoint kept stable for UI/export callers."""
    return _build_doctor_report_impl(case, blocks)


def _build_doctor_report_impl(case: CaseLike, blocks: Dict[str, TextBlock]) -> str:
    from rhk_doctor_report_service import build_doctor_report_service

    return build_doctor_report_service(case, blocks)
# =============================================================================
# Patient report (plain language, no abbreviations/numbers)
# =============================================================================


def _append_internal_warning_rows(lines: List[str], warns: List[Any]) -> None:
    if not warns:
        lines.append("- keine")
        return
    for w in warns[:12]:
        if isinstance(w, dict):
            try:
                sev = str(w.get(K_SEVERITY) or "warn").upper()
                msg = str(w.get("message") or "").strip()
                flds = w.get("fields") or []
                ftxt = f" (Felder: {', '.join([str(x) for x in flds])})" if flds else ""
                lines.append(f"- [{sev}] {msg}{ftxt}")
            except _REPORT_RECOVERABLE_ERRORS as exc:
                log_exception("RHK_REP_INTERNAL_WARNING_ROW", "Internal warning row formatting failed.", exc)
                lines.append(f"- {_format_warning_item(w)}")
            continue
        msg = _format_warning_item(w)
        if msg:
            lines.append(f"- {msg}")
    if len(warns) > 12:
        lines.append(f"- … weitere {len(warns) - 12} Warnungen")


def _append_internal_fired_rows(lines: List[str], fired: List[Any]) -> None:
    if not fired:
        lines.append("- keine")
        return
    for r in fired[:20]:
        try:
            rid = r.get("id")
            pr = r.get("priority")
            wh = str(r.get("when") or "")
            wh_short = (wh[:160] + "…") if len(wh) > 160 else wh
            lines.append(f"- {rid} (prio {pr}): {wh_short}")
        except _REPORT_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_REP_INTERNAL_FIRED_ROW", "Internal fired-rule row formatting failed.", exc)
            continue
    if len(fired) > 20:
        lines.append(f"- … weitere {len(fired) - 20} Regeln")


def _append_internal_error_rows(lines: List[str], errors: List[Any]) -> None:
    if not errors:
        return
    lines += ["", "#### Regel-Fehler (Auszug)"]
    for e in errors[:12]:
        try:
            rid = e.get("id")
            pr = e.get("priority")
            err = str(e.get("error") or "")
            err_short = (err[:180] + "…") if len(err) > 180 else err
            lines.append(f"- {rid} (prio {pr}): {err_short}")
        except _REPORT_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_REP_INTERNAL_ERROR_ROW", "Internal rule-error row formatting failed.", exc)
            continue
    if len(errors) > 12:
        lines.append(f"- … weitere {len(errors) - 12} Fehler")


def _append_internal_env_rows(lines: List[str], env: Dict[str, Any]) -> None:
    lines += ["", "### Env (Auszug)"]
    keys = [
        "mpap", "pawp_rest", "pvr", "ci", "tpg", "dpg",
        "hemo_category", "precap", "ipcph", "cpcph",
        "hfpef_category", "hfpef_percent",
        "congestion_likely", "step_up_present", "step_up_from_to",
        "mpap_co_slope", "pawp_co_slope", "exercise_pattern",
        "adaptation_type",
        "s_prime_raai",
        "warnings_count",
    ]
    for k in keys:
        lines.append(f"- {k}: {env.get(k)}")


def build_internal_report(case: CaseLike) -> str:
    """Build internal QA/debug report with warnings, fired rules, and env info."""
    fp = _case_fingerprint(case)
    cached = _cache_get('internal_report', fp)
    if cached is not None:
        return cached

    env = case.get(K_ENV) or {}
    dec = case.get(K_DECISION) or {}
    debug = case.get(K_DEBUG) or {}
    warns = case.get(K_WARNINGS) or debug.get(K_WARNINGS) or []
    rule_trace = debug.get("rule_trace") or {}
    fired = rule_trace.get("fired") or []
    errors = rule_trace.get("errors") or []

    lines = [
        "## Internal Debug",
        f"- Bundle: {dec.get(K_BUNDLE)}",
        f"- Primary DX: {dec.get('primary_dx')}",
        f"- Tags: {', '.join(dec.get('tags') or [])}",
        f"- Missing (Regelwerk): {', '.join(dec.get('missing_fields') or [])}",
        f"- Warnungen (Plausibilität): {len(warns)}",
        "",
        "### Plausibilitätswarnungen (Auszug)",
    ]

    _append_internal_warning_rows(lines, list(warns))

    lines += [
        "",
        "### Regelwerk – Trace",
        f"- Ausgelöste Regeln: {len(fired)}",
        f"- Regel-Fehler: {len(errors)}",
        "",
        "#### Ausgelöste Regeln (Auszug)",
    ]

    _append_internal_fired_rows(lines, list(fired))
    _append_internal_error_rows(lines, list(errors))
    _append_internal_env_rows(lines, env)
    _res = "\n".join(lines)
    _cache_set('internal_report', fp, _res)
    return _res
# =============================================================================
# Random example generation (now with lab constellations)
# =============================================================================

def random_example(scenario: Optional[str] = None, seed: Optional[int] = None) -> Dict[str, Any]:
    """
    Liefert ein zufälliges, aber in sich stimmiges Beispiel.

    Ziel:
    - Beispiele sollen möglichst viele Features abdecken (RHK Ruhe/Belastung, Volumen, Vaso, Step-up,
      Echo/CT/VQ/Lufu, Labor-Konstellationen).
    - Module werden teils bewusst vorselektiert, um die Procedere-Logik sichtbar zu machen.
    """
    rng = random if seed is None else random.Random(int(seed))


    scenarios = [
        "no_ph",            # normale Hämodynamik
        "pah_pre",          # präkapilläre PH (PAH-typisch)
        "cteph",            # CTEPH-Konstellation
        "ild_ph",           # ILD/Hypoxie
        "hfpef_ipcph",      # iPcPH (HFpEF-typisch)
        "cpcph",            # cPcPH
        "shunt_asd",        # Shunt/Step-up
    ]
    scen = scenario if (isinstance(scenario, str) and scenario in scenarios) else rng.choice(scenarios)

    ui: Dict[str, Any] = {}

    # --- Demografie ---
    if scen in ("pah_pre", "shunt_asd"):
        age = rng.choice([28, 34, 41])
        sex = rng.choice(["weiblich", "weiblich", "männlich"])
    elif scen in ("hfpef_ipcph", "cpcph"):
        age = rng.choice([62, 68, 74, 79])
        sex = rng.choice(["weiblich", "männlich"])
    else:
        age = rng.choice([45, 52, 58, 66, 72])
        sex = rng.choice(["weiblich", "männlich"])

    ui["firstname"] = rng.choice(["Anna", "Max", "Sofia", "Leon", "Mara", "Jonas"])
    ui["name"] = rng.choice(["Beispiel", "Muster", "Patient", "Testfall"])
    ui["age"] = age
    ui["sex"] = sex
    ui["height_cm"] = rng.choice([160, 168, 175, 182])
    ui["weight_kg"] = rng.choice([58, 72, 86, 98])

    ui["bp_sys"] = rng.choice([105, 115, 125, 135, 145])
    ui["bp_dia"] = rng.choice([65, 70, 75, 80, 85])
    ui["hr"] = rng.choice([55, 65, 75, 85, 95])

    ui[K_STORY] = rng.choice([
        "Belastungsdyspnoe seit Monaten, reduzierte Belastbarkeit.",
        "Zunehmende Luftnot, gelegentlich Schwindel.",
        "Kontrolle nach PH-Verdachtsdiagnose.",
        "Therapieevaluation bei bekannter PH.",
    ])

    ui["ph_known"] = scen in ("pah_pre", "cteph", "cpcph")
    ui["ph_suspected"] = not ui["ph_known"]

    # Default: CHD/Shunt-Anamnese in Beispielen explizit setzen (UI-Gating)
    ui[K_CHD_POS] = (scen == "shunt_asd")
    ui["chd_type"] = "ASD (Vorhofseptumdefekt)" if ui[K_CHD_POS] else "keine Angabe"
    ui["chd_desc"] = "" if not ui[K_CHD_POS] else "Bekannter ASD, Shuntkonstellation in der Stufenoxymetrie."

    # --- PH-Status Konsistenz + Details ---
    # In der Praxis schließen sich "PH-Diagnose bekannt" und "PH-Verdachtsdiagnose" gegenseitig aus.
    # Bei bekannter PH füllen wir deshalb zusätzliche Kontextfelder, damit die UI nicht "leer" wirkt.
    if ui.get("ph_known"):
        if scen == "pah_pre":
            ui["ph_known_dx"] = "PAH (Gruppe 1)"
            ui["ph_known_subtype"] = rng.choice([
                "SOP: Systemsklerose-assoziierte PAH",
                "idiopathische PAH",
                "portopulmonale Hypertonie",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["PDE-5-Hemmer", "Endothelin-Rezeptorantagonist (ERA)"],
                ["PDE-5-Hemmer"],
                ["sGC-Stimulator (Riociguat)", "Endothelin-Rezeptorantagonist (ERA)"],
            ])
        elif scen == "cteph":
            ui["ph_known_dx"] = "CTEPH (Gruppe 4)"
            ui["ph_known_subtype"] = rng.choice([
                "inoperable CTEPH (BPA-Evaluation)",
                "Status nach LE mit Residuen",
                "CTED/CTEPH im Verlauf",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["sGC-Stimulator (Riociguat)"],
                ["sGC-Stimulator (Riociguat)", "Diuretikum"],
            ])
            ui["ph_interventions"] = rng.choice([
                ["BPA (Ballonangioplastie, Katheter)"],
                ["PEA (Pulmonalisendarteriektomie, OP)"],
                [],
            ])
        elif scen == "cpcph":
            ui["ph_known_dx"] = "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)"
            ui["ph_known_subtype"] = rng.choice([
                "HFpEF mit postkapillärer PH",
                "cPcPH bei HFpEF (Mischkomponente wahrscheinlich)",
                "Linksherzerkrankung im Verlauf",
            ])
            ui["ph_current_meds"] = rng.choice([
                ["Diuretikum"],
                ["Diuretikum", "Sauerstofftherapie"],
            ])
        else:
            ui["ph_known_dx"] = "Sonstige/unklar (Gruppe 5)"
            ui["ph_known_subtype"] = "unklar"
            ui["ph_current_meds"] = []

        # Pflichtähnliche Felder (in Beispielen immer gefüllt)
        ui["ph_first_dx"] = rng.choice(["03/2020", "09/2021", "01/2022", "06/2023"])
        ui["ph_reason_rhk"] = rng.choice(["Verlaufskontrolle", "Therapieentscheidung", "Neusymptomatik"])
        ui["ph_prev_meds"] = ui.get("ph_prev_meds") or []
        # Bei bekannter Diagnose ist Verdacht nicht gesetzt
        ui["ph_suspected"] = False
    else:
        # Kein bekannter PH-Status: Verdacht ist möglich, Details bleiben leer
        ui["ph_known_dx"] = None
        ui["ph_known_subtype"] = ""
        ui["ph_first_dx"] = ""
        ui["ph_reason_rhk"] = None
        ui["ph_current_meds"] = ui.get("ph_current_meds") or []
        ui["ph_prev_meds"] = ui.get("ph_prev_meds") or []
        ui["ph_interventions"] = ui.get("ph_interventions") or []

    # --- Klinik/Funktion ---
    ui["who_fc"] = rng.choice(["II", "III"]) if scen != "no_ph" else rng.choice(["I", "II"])
    ui["six_mwd_m"] = rng.choice([240, 320, 420]) if scen != "no_ph" else rng.choice([420, 480, 520])

    # --- EKG (Beispiele sollen fehlende vs vorhandene Daten demonstrieren) ---
    # ekg_present: True/False/None (None = keine Angabe)
    if rng.random() < 0.75:
        ui["ekg_present"] = True
        ui["ekg_rhs_signs"] = rng.sample(
            ["P pulmonale", "Rechtsachsenabweichung", "RV-Hypertrophie", "RBBB/in kompletter RSB", "S1Q3T3"],
            k=rng.choice([0, 1, 2]),
        )
        ui["ekg_other_text"] = ""
    else:
        ui["ekg_present"] = False
        ui["ekg_rhs_signs"] = []
        ui["ekg_other_text"] = ""
    ui["stairs_flights"] = rng.choice([0, 1, 2, 3])
    ui["syncope"] = rng.choices(["keine", "gelegentlich", "wiederholt"], weights=[0.83, 0.14, 0.03], k=1)[0]
    ui["hemoptysis"] = (scen == "cteph") and (rng.random() < 0.15)
    ui["dizziness"] = rng.choice([False, True])

    # --- Labor ---
    lab_mode = rng.choice(["normal", "inflammation", "anemia", "renal"])
    ui["crp_mg_l"] = rng.choice([2, 4, 6]) if lab_mode != "inflammation" else rng.choice([25, 60])
    ui["leukocytes_g_l"] = rng.choice([6.5, 7.8, 9.1]) if lab_mode != "inflammation" else rng.choice([12.0, 15.5])
    ui["creatinine_mg_dl"] = rng.choice([0.8, 1.0, 1.2]) if lab_mode != "renal" else rng.choice([1.8, 2.2])
    ui["egfr"] = rng.choice([65, 75, 85, 95]) if lab_mode != "renal" else rng.choice([25, 30, 35, 40, 45])
    ui["platelets_g_l"] = rng.choice([190, 240, 320])
    ui["inr"] = rng.choice([1.0, 1.1, 1.2])
    ui["ptt_s"] = rng.choice([28, 31, 34])

    # Hb gezielt setzen: in ~50% fehlt Hb, um "nicht anwählbar" Logik zu testen
    if rng.random() < 0.5:
        ui["hb_g_dl"] = None
        ui["anemia_type"] = None
    else:
        if lab_mode == "anemia":
            ui["hb_g_dl"] = rng.choice([9.8, 10.6, 11.4])
            ui["anemia_type"] = rng.choice(["mikrozytär", "normozytär", "makrozytär"])
        else:
            ui["hb_g_dl"] = rng.choice([12.6, 13.8, 15.1])
            ui["anemia_type"] = None

    ui["bnp_kind"] = rng.choice(["NT-proBNP", "BNP"])
    if scen in ("no_ph",):
        ui["bnp_value"] = rng.choice([40, 80, 120])
    elif scen in ("hfpef_ipcph", "cpcph"):
        ui["bnp_value"] = rng.choice([380, 900, 1800])
    else:
        ui["bnp_value"] = rng.choice([120, 380, 1200, 2400])

    # --- Bildgebung/Echo ---
    ui["ct_done"] = True
    ui["ct_koronarkalk"] = rng.choice([False, True])

    ui["ct_ild"] = (scen == "ild_ph")
    ui["ct_emphysema"] = (scen == "ild_ph") and rng.choice([False, True])
    ui["ct_embolie"] = (scen == "cteph")
    ui["ct_mosaic"] = (scen == "cteph")

    ui["vq_done"] = (scen == "cteph") or (rng.random() < 0.4)
    ui["vq_defect"] = (scen == "cteph") and ui["vq_done"]
    ui["vq_desc"] = "Mehrsegmentale Perfusionsdefekte." if ui["vq_defect"] else ""

    ui["echo_done"] = True
    ui["lvef"] = 60 if scen not in ("cpcph",) else 55
    ui["la_enlarged"] = True if scen in ("hfpef_ipcph", "cpcph") else rng.choice([False, True])
    ui["ee_ratio"] = 16 if scen in ("hfpef_ipcph", "cpcph") else rng.choice([9, 11, 13])
    ui["pasp_echo"] = rng.choice([35, 45, 60]) if scen != "no_ph" else 28
    ui["tapse_mm"] = 22 if scen == "no_ph" else rng.choice([14, 16, 18, 20])
    ui["atrial_fib"] = True if scen in ("hfpef_ipcph", "cpcph") else False


    # --- Zusatzfelder für Modul-Gating (damit "nicht anwählbar" Regeln sichtbar werden) ---

    # Antikoagulation
    if scen == "cteph" or ui.get("atrial_fib"):
        ui["anticoag_status"] = "ja"
        ui["anticoag_substance"] = rng.choice(["DOAC (Apixaban, Rivaroxaban)", "VKA (Phenprocoumon/Warfarin)"])
        ui["anticoag_indication"] = "CTEPH/CTEPD" if scen == "cteph" else "Vorhofflimmern"
        ui["anticoag_since"] = rng.choice(["09/2023", "03/2024", "11/2024"])
        ui["anticoag_note"] = ""
    else:
        ui["anticoag_status"] = "nein"
        ui["anticoag_substance"] = None
        ui["anticoag_indication"] = "keine Angabe"
        ui["anticoag_since"] = ""
        ui["anticoag_note"] = ""

    # Immunologie Autoimmun
    if scen in ("pah_pre",) and rng.random() < 0.35:
        ui["immunology_pos"] = True
        ui["immunology_items"] = rng.sample([
            "Systemische Sklerose (Sklerodermie)",
            "SLE (Lupus erythematodes)",
            "MCTD (Mixed connective tissue disease)",
            "Sjögren-Syndrom",
        ], k=1)
        ui["immunology_desc"] = "Autoimmunerkrankung bekannt."
    else:
        ui["immunology_pos"] = False
        ui["immunology_items"] = []
        ui["immunology_desc"] = ""

    # Virologie Infektiologie
    if scen in ("pah_pre",) and rng.random() < 0.15:
        ui["virology_pos"] = True
        ui["virology_items"] = rng.sample([
            "HIV",
            "Hepatitis B",
            "Hepatitis C",
            "Schistosomiasis (parasitär)",
        ], k=1)
        ui["virology_desc"] = "Infektiologischer Risikofaktor dokumentiert."
    else:
        ui["virology_pos"] = False
        ui["virology_items"] = []
        ui["virology_desc"] = ""

    # Mutation Genetik
    if (scen == "pah_pre") and (age is not None) and (age < 45) and (rng.random() < 0.18):
        ui["mutation_pos"] = True
        ui["mutation_items"] = rng.sample([
            "BMPR2 Mutation",
            "ALK1 ACVRL1 Mutation",
            "EIF2AK4 Mutation",
        ], k=1)
        ui["mutation_desc"] = "Hinweis auf hereditäre Konstellation."
    else:
        ui["mutation_pos"] = False
        ui["mutation_items"] = []
        ui["mutation_desc"] = ""

    # Abdomensonographie
    ui["abd_sono_done"] = rng.random() < 0.55
    if ui["abd_sono_done"]:
        if rng.random() < 0.12:
            ui["abd_sono_desc"] = "Hinweis auf Leberzirrhose und portale Hypertension."
        else:
            ui["abd_sono_desc"] = rng.choice(["Unauffällig.", "Normalbefund.", "Kein Hinweis auf Leberzirrhose."])
    else:
        ui["abd_sono_desc"] = ""
    ui["s_prime_cm_s"] = rng.choice([9.0, 11.0, 13.0])
    ui["ra_esa_cm2"] = rng.choice([16.0, 20.0, 26.0])

    # --- Lufu ---
    ui["lufu_done"] = True
    ui["lufu_obstructive"] = bool(ui["ct_emphysema"])
    ui["lufu_restrictive"] = bool(ui["ct_ild"])
    ui["lufu_diffusion"] = bool(ui["ct_ild"]) or (rng.random() < 0.35)
    ui["fev1_l"] = rng.choice([1.4, 2.1, 2.8])
    ui["fvc_l"] = rng.choice([2.0, 2.8, 3.6])
    ui["dlco_sb"] = rng.choice([35, 52, 68])
    ui["lufu_summary"] = rng.choice(["", "Leichte Diffusionsstörung.", "Obstruktives Muster."])

    # In einem Teil der Fälle explizit unauffällige Lufu setzen, damit P12 klar deaktiviert werden kann
    if scen == "no_ph" or rng.random() < 0.18:
        ui["lufu_obstructive"] = False
        ui["lufu_restrictive"] = False
        ui["lufu_diffusion"] = False
        ui["lufu_summary"] = rng.choice(["Unauffällig.", "Normalbefund.", "Keine relevanten Auffälligkeiten."])

    # Langzeit-Sauerstofftherapie (für Ätiologie- und Modul-Logik)
    if scen == "ild_ph":
        ui["ltot"] = True
        ui["ltot_flow_l_min"] = rng.choice([1.0, 2.0, 3.0])
    else:
        ui["ltot"] = False
        ui["ltot_flow_l_min"] = None
    # --- Hämodynamik (Ruhe) ---
    if scen == "no_ph":
        spap, dpap, pawp, co, rap = 28, 10, 10, 5.2, 6
    elif scen == "hfpef_ipcph":
        spap, dpap, pawp, co, rap = 55, 25, 20, 4.5, 10
    elif scen == "cpcph":
        spap, dpap, pawp, co, rap = 70, 35, 22, 3.6, 14
    else:  # präkapillär
        spap, dpap, pawp, co, rap = 72, 30, 10, 4.0, 9

    ui["spap_rest"] = spap
    ui["dpap_rest"] = dpap
    ui["mpap_rest"] = None  # berechnen lassen
    ui["pawp_rest"] = pawp
    ui["rap_rest"] = rap
    ui["co_rest"] = co
    ui["ci_rest"] = None
    ui["pvr_rest"] = None

    # --- Belastung / Volumen ---
    ui["exercise_done"] = scen in ("pah_pre", "hfpef_ipcph", "cpcph") and (rng.random() < 0.75)
    if ui["exercise_done"]:
        ui["exercise_protocol"] = rng.choice(["WHO-Rampe", "Stufenprotokoll"])
        ui["exercise_peak_watts"] = rng.choice([75, 100, 125, 150, 175])
        ui["spap_peak"] = spap + rng.choice([25, 35])
        ui["dpap_peak"] = dpap + rng.choice([10, 15])
        ui["mpap_peak"] = None
        ui["pawp_peak"] = pawp + (rng.choice([3, 10, 15]) if scen in ("hfpef_ipcph", "cpcph") else rng.choice([2, 4, 6]))
        ui["co_peak"] = co + rng.choice([1.0, 1.8, 2.5])
    else:
        ui["exercise_protocol"] = ""
        ui["exercise_peak_watts"] = None
        ui["spap_peak"] = None
        ui["dpap_peak"] = None
        ui["mpap_peak"] = None
        ui["pawp_peak"] = None
        ui["co_peak"] = None

    ui["volume_challenge_done"] = (scen == "hfpef_ipcph") and (rng.random() < 0.6)
    if ui["volume_challenge_done"]:
        ui["volume_ml"] = rng.choice([500, 750])
        ui["pawp_post"] = pawp + rng.choice([5, 8, 12])
        ui["mpap_post"] = None
        ui["co_post"] = co + rng.choice([0.5, 1.0])
    else:
        ui["volume_ml"] = None
        ui["pawp_post"] = None
        ui["mpap_post"] = None
        ui["co_post"] = None

    # --- Vaso (nur PAH-Beispiel) ---
    ui["vaso_test_done"] = (scen == "pah_pre") and (rng.random() < 0.5)
    if ui["vaso_test_done"]:
        ui["vaso_substance"] = rng.choice(["NO", "Iloprost"])
        ui["vaso_mpap_pre"] = None
        ui["vaso_mpap_post"] = None
        ui["vaso_response_desc"] = rng.choice([
            "Kein signifikanter Abfall des mPAP.",
            "Vasoreaktivitätskriterium erreicht (Abfall mPAP, CO stabil).",
        ])
    else:
        ui["vaso_substance"] = ""
        ui["vaso_mpap_pre"] = None
        ui["vaso_mpap_post"] = None
        ui["vaso_response_desc"] = ""

    # --- Stufenoxymetrie/Step-up (Shunt) ---
    if scen == "shunt_asd":
        ui["sat_svc"] = 65
        ui["sat_ivc"] = None
        ui["sat_ra"] = 80
        ui["sat_rv"] = 80
        ui["sat_pa"] = 80
        ui["sat_ao"] = 96

        # Kontext: angeborener Herzfehler/Shunt
        ui[K_CHD_POS] = True
        ui["chd_type"] = "ASD (Vorhofseptumdefekt)"
        ui["chd_desc"] = "Beispiel: ASD mit Links nach Rechts Shunt."
    else:
        ui["sat_svc"] = None
        ui["sat_ivc"] = None
        ui["sat_ra"] = None
        ui["sat_rv"] = None
        ui["sat_pa"] = None
        ui["sat_ao"] = None

        ui[K_CHD_POS] = False
        ui["chd_type"] = "keine Angabe"
        ui["chd_desc"] = ""

        # Default: kein bekannter angeborener Shunt
        ui[K_CHD_POS] = ui.get(K_CHD_POS) if ui.get(K_CHD_POS) is not None else False
        ui["chd_type"] = ui.get("chd_type") or "keine Angabe"
        ui["chd_desc"] = ui.get("chd_desc") or ""

    # --- Kurvenflags ---
    ui["wedge_v_wave"] = (scen in ("hfpef_ipcph", "cpcph")) and (rng.random() < 0.5)
    ui["wedge_a_wave"] = (scen in ("hfpef_ipcph", "cpcph")) and (rng.random() < 0.35)
    ui["rap_a_wave"] = rng.random() < 0.2
    ui["rap_v_wave"] = rng.random() < 0.15
    ui["rv_pseudo_dip"] = rng.random() < 0.1
    ui["rv_dip_plateau"] = rng.random() < 0.05

    # --- Procedere/Module ---
    ui["procedere_free"] = ""
    ui[K_MODULES] = []

    # Sichtbare Demo-Auswahl: ein paar Module passend zum Beispiel
    if scen == "cteph":
        ui[K_MODULES] = ["P10"]
    elif scen == "ild_ph":
        ui[K_MODULES] = ["P12"]
    elif scen in ("hfpef_ipcph", "cpcph"):
        ui[K_MODULES] = ["P09"]
    elif scen == "shunt_asd":
        ui[K_MODULES] = ["P01"]
    elif scen == "pah_pre":
        ui[K_MODULES] = ["P14"]

    # Optional: Schwangerschaft-Modul gelegentlich vorselektieren (nur wenn weiblich und <= 50)
    if sex == "weiblich" and age <= 50 and rng.random() < 0.15:
        ui[K_MODULES] = list(dict.fromkeys(ui[K_MODULES] + ["P21"]))

    # Optional: Anämie-Modul vorselektieren, wenn Hb tatsächlich niedrig ist
    hb = _safe_float(ui.get("hb_g_dl"))
    hb_low = 13.0 if sex == "männlich" else 12.0
    if hb is not None and hb < hb_low:
        ui[K_MODULES] = list(dict.fromkeys(ui[K_MODULES] + ["P13"]))

    # In der UI existieren Level-Gruppen (modules_lvl1/2/3). Beispiele sollen diese Logik sichtbar füllen.
    # Wir legen die Vorselektion standardmäßig in Level 3 ab (robust, da Level-Policy fallabhängig variieren kann).
    ui["modules_lvl1"] = []
    ui["modules_lvl2"] = []
    ui["modules_lvl3"] = list(ui.get(K_MODULES) or [])

    # --- Vor-RHK (gelegentlich) ---
    if rng.random() < 0.35:
        ui["prev_rhk_date"] = rng.choice(["03/21", "11/22", "06/23"])
        ui["prev_label"] = rng.choice(["stabiler Verlauf", "leicht progredient", "gebessert"])
        ui["prev_mpap"] = rng.choice([18, 24, 30])
        ui["prev_pawp"] = rng.choice([7, 12, 18])
        ui["prev_ci"] = rng.choice([2.1, 2.8, 3.2])
        ui["prev_pvr"] = rng.choice([1.5, 2.6, 4.2])
    else:
        ui["prev_rhk_date"] = ""
        ui["prev_label"] = ""
        ui["prev_mpap"] = None
        ui["prev_pawp"] = None
        ui["prev_ci"] = None
        ui["prev_pvr"] = None

    return ui


# =============================================================================
# Beispielreihe (Suite)
# =============================================================================

def example_suite_case(index: Any = 0) -> Dict[str, Any]:
    """Liefert ein Beispiel aus einer festen Suite.

    Ziel: Über mehrere Beispiele hinweg sollen möglichst viele Funktionen getestet werden,
    ohne Zufall und ohne implizite Datenannahmen.

    - Wiederholtes Klicken lädt das nächste Beispiel (Index modulo Suite-Länge).
    - Jede Suite belegt andere Pfade (RHK Ruhe/Belastung, Volumen, Vaso, Step-up,
      CT/VQ/Lufu, CPET, PH Therapieepisoden inkl. Restart und Sotatercept, Legacy-Import).
    """

    try:
        idx = int(index or 0)
    except (TypeError, ValueError) as exc:
        log_exception("RHK_REP_EXAMPLE_INDEX", "Example suite index parsing failed; defaulting to 0.", exc, raw_index=index)
        idx = 0

    def _tx(lines: List[List[str]]) -> str:
        # 6 Spalten: Medikament, Status, seit, bis, Grund, Kommentar
        out_lines: List[str] = []
        for row in lines:
            row = (row or []) + [""] * (6 - len(row or []))
            out_lines.append("\t".join([str(c or "").strip() for c in row[:6]]).strip())
        return "\n".join([ln for ln in out_lines if ln])

    SUITE: List[Dict[str, Any]] = [
        {
            "id": "E01",
            "label": "PAH Restart und Sotatercept",
            "scenario": "pah_pre",
            "modules": ["P14"],
            "story": "Beispiel E01: PAH (präkapillär) mit Belastung und Vasoreaktivität. Therapieepisoden mit Restart und Sotatercept.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "ph_known_subtype": "idiopathische PAH",
                "ph_first_dx": "03/2022",
                "ph_reason_rhk": "Verlaufskontrolle",
                "co_method": "Thermodilution",
                "exercise_done": True,
                "vaso_test_done": True,
                "vaso_substance": "NO",
                "vaso_response_desc": "Vasoreaktivitätskriterium erreicht (Abfall mPAP, CO stabil).",
                "ph_tx_table": _tx([
                    ["Opsumit (Macitentan)", "aktuell", "01/2024", "", "", ""],
                    ["Sildenafil", "abgesetzt", "05/2023", "10/2023", "Unverträglichkeit/Nebenwirkung", "Kopfschmerz"],
                    ["Sildenafil", "aktuell", "11/2023", "", "", "Restart"],
                    ["Sotatercept", "geplant", "02/2026", "", "", "Therapieplanung"],
                ]),
                "ph_current_meds": [],
                "ph_prev_meds": [],
                "ph_new_meds": [],
                "ph_stopped_meds": [],
                "consent_done": True,
                "access_route": "V. jugularis rechts",
                "allergies_present": True,
                "allergies_list": ["Pflaster"],
                "cpet_done": True,
                "cpet_peak_vo2_ml_kg_min": 13.8,
                "cpet_peak_vo2_pct_pred": 56,
                "cpet_ve_vco2_slope": 42,
                "cpet_petco2_vt1_mmhg": 30,
                "cpet_spo2_nadir_pct": 90,
                "cpet_rer_peak": 1.18,
                "cpet_hr_peak_bpm": 156,
            },
        },
        {
            "id": "E02",
            "label": "HIV assoziierte PAH",
            "scenario": "pah_pre",
            "modules": ["P14"],
            "story": "Beispiel E02: Präkapilläre PH mit Risikofaktor HIV. Differenzialblock soll Gruppe 1 (HIV) ausweisen.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "ph_known_subtype": "HIV assoziierte PAH",
                "virology_pos": True,
                "virology_items": ["HIV"],
                "virology_desc": "HIV positiv.",
                "immunology_pos": False,
                "immunology_items": [],
                "immunology_desc": "",
                "vq_done": True,
                "vq_defect": False,
                "ct_embolie": False,
                "ct_mosaic": False,
                "ph_tx_table": _tx([
                    ["Opsumit (Macitentan)", "aktuell", "06/2024", "", "", ""],
                    ["Tadalafil", "aktuell", "06/2024", "", "", ""],
                ]),
                "consent_done": True,
                "access_route": "V. jugularis rechts",
                "cpet_done": True,
                "cpet_peak_vo2_ml_kg_min": 12.0,
                "cpet_peak_vo2_pct_pred": 49,
                "cpet_ve_vco2_slope": 45,
                "cpet_petco2_vt1_mmhg": 28,
                "cpet_spo2_nadir_pct": 92,
            },
        },
        {
            "id": "E03",
            "label": "CTEPH",
            "scenario": "cteph",
            "modules": ["P10"],
            "story": "Beispiel E03: CTEPH Konstellation mit V/Q Defekten und CT Mosaik. Antikoagulation aktiv. Therapie mit Adempas.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "CTEPH (Gruppe 4)",
                "ph_known_subtype": "inoperable CTEPH (BPA Evaluation)",
                "vq_done": True,
                "vq_defect": True,
                "vq_desc": "Mehrsegmentale Perfusionsdefekte.",
                "ct_embolie": True,
                "ct_mosaic": True,
                "anticoag_status": "ja",
                "anticoag_indication": "CTEPH/CTEPD",
                "anticoag_substance": "DOAC (Apixaban, Rivaroxaban)",
                "ph_tx_table": _tx([
                    ["Adempas (Riociguat)", "aktuell", "08/2024", "", "", ""],
                ]),
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E04",
            "label": "Gruppe 3 ILD Hypoxie",
            "scenario": "ild_ph",
            "modules": ["P12"],
            "story": "Beispiel E04: PH Verdacht bei ILD. LTOT aktiv, Lufu restriktiv und DLCO reduziert. Differenzialblock soll Gruppe 3 priorisieren.",
            "overrides": {
                "ph_known": False,
                "ph_suspected": True,
                "ct_done": True,
                "ct_ild": True,
                "ct_emphysema": False,
                "ltot": True,
                "ltot_flow_l_min": 2.0,
                "lufu_done": True,
                "lufu_restrictive": True,
                "lufu_diffusion": True,
                "dlco_sb": 42,
                "vq_done": False,
                "virology_pos": False,
                "immunology_pos": False,
                "consent_done": True,
                "access_route": "V. jugularis rechts",
                "cpet_done": True,
                "cpet_peak_vo2_ml_kg_min": 11.2,
                "cpet_peak_vo2_pct_pred": 45,
                "cpet_ve_vco2_slope": 38,
                "cpet_spo2_nadir_pct": 84,
                "cpet_o2_supp_l_min": 2.0,
            },
        },
        {
            "id": "E05",
            "label": "HFpEF iPcPH mit Volumen und Belastung",
            "scenario": "hfpef_ipcph",
            "modules": ["P09"],
            "story": "Beispiel E05: iPcPH HFpEF Konstellation. Volumenbelastung und Belastungshämodynamik aktiv.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)",
                "ph_known_subtype": "HFpEF mit postkapillärer PH",
                "exercise_done": True,
                "volume_challenge_done": True,
                "volume_ml": 500,
                "atrial_fib": True,
                "la_enlarged": True,
                "anticoag_status": "ja",
                "anticoag_indication": "Vorhofflimmern",
                "anticoag_substance": "DOAC (Apixaban, Rivaroxaban)",
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E06",
            "label": "HFpEF cPcPH",
            "scenario": "cpcph",
            "modules": ["P09"],
            "story": "Beispiel E06: cPcPH Muster bei Linksherzerkrankung. Erhöhte PAWP und erhöhte PVR.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)",
                "ph_known_subtype": "cPcPH bei HFpEF",
                "atrial_fib": True,
                "la_enlarged": True,
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E07",
            "label": "Shunt ASD",
            "scenario": "shunt_asd",
            "modules": ["P01"],
            "story": "Beispiel E07: Step up in der Stufenoxymetrie bei ASD. Testet Shunt Logik.",
            "overrides": {
                "chd_pos": True,
                "chd_type": "ASD (Vorhofseptumdefekt)",
                "chd_desc": "ASD V.a. bzw. bekannt.",
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E08",
            "label": "Legacy PH Therapie Import",
            "scenario": "pah_pre",
            "modules": ["P14"],
            "story": "Beispiel E08: Legacy PH Therapie Felder gefüllt (Mehrfachlisten). Testet Button: Legacy Therapie in Episoden übernehmen.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "ph_known_subtype": "Systemsklerose assoziierte PAH",
                "immunology_pos": True,
                "immunology_items": ["Systemische Sklerose (Sklerodermie)"],
                "immunology_desc": "Autoimmunerkrankung bekannt.",
                "ph_tx_table": "",
                "ph_current_meds": ["PDE-5-Hemmer", "Endothelin-Rezeptorantagonist (ERA)"],
                "ph_prev_meds": ["Prostazyklin-Therapie / -Analogon"],
                "ph_tx_status": "eskaliert",
                "ph_new_meds": ["Sotatercept (BMPR2/Activin-Pfad)"],
                "ph_stopped_meds": ["Prostazyklin-Therapie / -Analogon"],
                "ph_stop_reason": "Unverträglichkeit/Nebenwirkung",
                "ph_stop_reason_text": "Beispiel: Flush und Hypotonie.",
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E09",
            "label": "PAH Genetik plus TR plus Belastung",
            "scenario": "pah_pre",
            "modules": ["P14", "P20"],
            "story": "Beispiel E09: Präkapilläre PH mit genetischer Assoziation, TR Hinweis (V-Welle) und gemischter Belastungsreaktion. Testet: keine CO-Methoden-Floskeln, keine redundante Ätiologie-Doppelung.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "ph_known_subtype": "hereditäre/assoziierte PAH",
                # absichtlich keine CO-Methode: soll keine generische Interpretation-Zeile triggern
                "co_method": "",
                "mutation_pos": True,
                "mutation_items": ["BMPR2"],
                "mutation_desc": "Genetik angegeben.",
                "exercise_done": True,
                "la_enlarged": True,
                "echo_tr_significant": True,
                "echo_tr_grade": "mind. moderat",
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E10",
            "label": "PH Verdacht: Ruhe ok, Belastung abnorm",
            "scenario": "normal_rest_exercise",
            "modules": ["P09"],
            "story": "Beispiel E10: Keine PH in Ruhe, aber abnorme Druck-Flow-Reaktion unter Belastung. Testet Belastungsinterpretation ohne redundante Zusammenfassung.",
            "overrides": {
                "ph_known": False,
                "ph_suspected": True,
                "exercise_done": True,
                "co_method": "Thermodilution",
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E11",
            "label": "CTEPH plus Linksherz DD",
            "scenario": "cteph",
            "modules": ["P10", "P09"],
            "story": "Beispiel E11: CTEPH-Konstellation mit zusätzlichen Linksherz-Hinweisen (PAWP > 15). Testet: kompakter Ätiologie/DD-Block ohne Doppelung in der Interpretation.",
            "overrides": {
                # Hämodynamik (bewusst cPcPH-ähnlich, um G2 als DD zu triggern)
                "mpap_rest": 44,
                "pawp_rest": 18,
                "pvr_rest": 6.0,
                "ci_rest": 2.2,
                # Gruppe 4 Evidenz
                "vq_done": True,
                "vq_defect": True,
                "vq_desc": "Mehrsegmentale Perfusionsdefekte.",
                "ct_embolie": True,
                "ct_mosaic": True,
                # Gruppe 2 Evidenz
                "atrial_fib": True,
                "la_enlarged": True,
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E12",
            "label": "UI-0 als fehlend (keine falsche Klassifikation)",
            "scenario": "no_ph",
            "modules": [],
            "story": "Beispiel E12: Simuliert den UI-Edge-Case 'leere Zahlenfelder -> 0'. Erwartung: 0 wird als fehlend behandelt; keine fälschliche Normal- oder PH-Klassifikation.",
            "overrides": {
                "spap_rest": 0,
                "dpap_rest": 0,
                "mpap_rest": 0,
                "pawp_rest": 0,
                "rap_rest": 0,
                "co_rest": 0,
                "ci_rest": 0,
                "pvr_rest": 0,
                "bp_sys": 0,
                "bp_dia": 0,
                "hr": 0,
                "co_method": "",
            },
        },
        {
            "id": "E13",
            "label": "Pre-RHK PDF ASCII/Flags",
            "scenario": "cteph",
            "modules": [],
            "story": "Beispiel E13: Fokus Pre-RHK PDF: Download-Workflow, ASCII-Symbole (kopierbar) und Flags (Low output, Niere, O2, Antikoag.).",
            "overrides": {
                "consent_done": True,
                "access_route": "V. jugularis rechts",
                "co_method": "Thermodilution",
                "ci_rest": 1.8,
                "egfr": 35,
                "o2_l_min": 4,
                "anticoag_status": "ja",
                "anticoag_substance": "Apixaban",
            },
        },
        {
            "id": "E14",
            "label": "Safety Kontraindikation Interaktionen",
            "scenario": "pah_pre",
            "modules": ["P14"],
            "story": "Beispiel E14: Klinische Safety-Konstellation mit Nitraten plus PDE-5 und Riociguat sowie fehlender Härtefall-Begründung. Testet Interaktions-/Kontraindikationsnetz.",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "ph_known_subtype": "idiopathische PAH",
                "on_nitrates": True,
                "pde5_hardship": True,
                "pde5_hardship_desc": "",
                "ph_tx_table": _tx([
                    ["Sildenafil", "aktuell", "01/2025", "", "", ""],
                    ["Adempas (Riociguat)", "aktuell", "01/2025", "", "", ""],
                ]),
                "ph_current_meds": [],
                "ph_prev_meds": [],
                "ph_new_meds": [],
                "ph_stopped_meds": [],
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E15",
            "label": "Messqualität Inkonsistenzen",
            "scenario": "no_ph",
            "modules": [],
            "story": "Beispiel E15: Bewusst inkonsistente Hämodynamik (sPAP/mPAP/dPAP), CO-Einheitenfehler und unplausible Sättigungssprünge. Testet Messqualität/Konsistenzchecks.",
            "overrides": {
                "spap_rest": 24,
                "dpap_rest": 32,
                "mpap_rest": 40,
                "pawp_rest": 8,
                "rap_rest": 6,
                "co_rest": 4500,
                "ci_rest": 14.2,
                "pvr_rest": 2.4,
                "sat_svc": 60,
                "sat_ra": 62,
                "sat_rv": 89,
                "sat_pa": 65,
                "sat_ao": 95,
                "volume_challenge_done": True,
                "volume_ml": 500,
                "pawp_pre": 9,
                "pawp_post": 27,
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
        {
            "id": "E16",
            "label": "Härtefall dokumentiert plus Volumen Lücke",
            "scenario": "pah_pre",
            "modules": ["P14"],
            "story": "Beispiel E16: Härtefall korrekt dokumentiert, keine Interaktionskontraindikation, aber unvollständige Volumenchallenge-Dokumentation (PAWP pre ohne post).",
            "overrides": {
                "ph_known": True,
                "ph_known_dx": "PAH (Gruppe 1)",
                "on_nitrates": False,
                "pde5_hardship": True,
                "pde5_hardship_desc": "Off-Label-Entscheidung nach interdisziplinärer Nutzen-Risiko-Abwägung dokumentiert.",
                "ph_tx_table": _tx([
                    ["Tadalafil", "aktuell", "11/2024", "", "", "Stabile Verträglichkeit"],
                    ["Opsumit (Macitentan)", "aktuell", "11/2024", "", "", ""],
                ]),
                "volume_challenge_done": True,
                "volume_ml": 500,
                "pawp_pre": 11,
                "pawp_post": None,
                "consent_done": True,
                "access_route": "V. jugularis rechts",
            },
        },
    ]

    cfg = SUITE[idx % len(SUITE)]

    # Deterministische Basis aus random_example, dann gezielte Overrides
    ui = random_example(scenario=str(cfg.get("scenario") or ""), seed=10_000 + (idx % 10_000))

    # Sichtbarkeit/Orientierung in der UI: echter Name bleibt aus random_example,
    # damit die Dichtbarriere im Laienbericht nicht durch Szenario-Beschreibungen
    # aufgebrochen wird. Szenario-ID wird separat in ``suite_id`` exportiert
    # (Tests/QA können darüber indizieren, ohne das Name-Feld zu missbrauchen);
    # die Langform (Szenario-Erzählung) lebt in ``story``.
    ui["firstname"] = ui.get("firstname") or "Test"
    ui["name"] = ui.get("name") or f"Fall {cfg.get('id')}"
    ui["suite_id"] = str(cfg.get("id") or "")
    ui["suite_label"] = str(cfg.get("label") or "")
    ui[K_STORY] = str(cfg.get(K_STORY) or ui.get(K_STORY) or "")

    # Module
    mods = list(cfg.get(K_MODULES) or [])
    ui[K_MODULES] = mods
    ui["modules_lvl1"] = []
    ui["modules_lvl2"] = []
    ui["modules_lvl3"] = mods

    # Standard: keine impliziten Angaben
    ui.setdefault("allergies_present", False)
    ui.setdefault("allergies_list", [])
    ui.setdefault("allergies_other_text", "")
    ui.setdefault("lsb_present", False)
    ui.setdefault("lsb_reason", "")
    ui.setdefault("anticoag_paused", False)

    # Apply overrides (last write wins)
    for k, v in (cfg.get("overrides") or {}).items():
        ui[k] = v

    # Konsistenz: bekannte PH impliziert kein Verdacht
    if bool(ui.get("ph_known")):
        ui["ph_suspected"] = False

    return ui


# Length of the example suite (number of distinct scenarios in example_suite_case).
# Update this constant when SUITE entries are added/removed.
EXAMPLE_SUITE_LENGTH = 16


def example_suite_length() -> int:
    """Return the number of scenarios in the example suite.

    Callers (UI, tests) use this to pick a random index without repeating
    the SUITE literal or relying on internal details of ``example_suite_case``.
    """
    return EXAMPLE_SUITE_LENGTH





# =============================================================================
# JSON export/import helpers
# =============================================================================


def build_summary_dict(case: CaseLike, rulebook_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Structured, stable JSON summary for studies/registries/QA."""
    fp = _case_fingerprint(case)
    cached = _cache_get('summary_dict', fp)
    if cached is not None:
        return cached
    ui = case.get(K_UI) or {}
    der = case.get(K_DERIVED) or {}
    scores = case.get(K_SCORES) or {}
    dec = case.get(K_DECISION) or {}
    warns = case.get(K_WARNINGS) or []

    # Slim warnings (message + severity + code if present)
    wslim: List[Dict[str, Any]] = []
    if isinstance(warns, list):
        for w in warns:
            if not isinstance(w, dict):
                continue
            wslim.append(
                {
                    "severity": w.get(K_SEVERITY),
                    "code": w.get("code"),
                    "message": w.get("message"),
                }
            )

    rb = rulebook_meta or {}
    rb_meta = {
        "version": (rb.get("version") if isinstance(rb, dict) else None),
        "updated": (rb.get("updated") if isinstance(rb, dict) else None),
    }

    # Dates
    today = _dt.datetime.now().isoformat(timespec="seconds")

    # Core hemodynamics
    hemo = {
        "rap_rest_mmHg": _safe_num(der.get("rap_rest")),
        "spap_rest_mmHg": _safe_num(der.get("spap_rest")),
        "dpap_rest_mmHg": _safe_num(der.get("dpap_rest")),
        "mpap_rest_mmHg": _safe_num(der.get("mpap_rest")),
        "pawp_rest_mmHg": _safe_num(der.get("pawp_rest")),
        "co_rest_L_min": _safe_num(der.get("co")),
        "ci_rest_L_min_m2": _safe_num(der.get("ci")),
        "pvr_rest_WU": _safe_num(der.get("pvr_rest")),
        "pvri_rest_WU_m2": _safe_num(der.get("pvri")),
        "tpg_mmHg": _safe_num(der.get("tpg")),
        "dpg_mmHg": _safe_num(der.get("dpg")),
    }

    # Classification / risk
    classification = {
        "hemo_category": der.get("hemo_category"),
        "primary_dx": dec.get("primary_dx"),
        "bundle": dec.get(K_BUNDLE),
        "risk_category": der.get(K_RISK_CATEGORY),
        "esc_ers_4s": scores.get("esc_ers_4s"),
        "esc_ers_3s": scores.get("esc_ers_3s"),
        "reveal_lite2": scores.get("reveal_lite2"),
        "reveal_lite2_points": scores.get("reveal_lite2_points"),
    }

    # Echo snapshot (only the main fields used in patient echo report)
    echo = {
        "lvef_percent": _safe_num(ui.get("lvef")),
        "tapse_mm": _safe_num(ui.get("tapse_mm")),
        "s_prime_cm_s": _safe_num(ui.get("s_prime_cm_s")),
        "pasp_echo_mmHg": _safe_num(ui.get("pasp_echo")),
        "ra_esa_cm2": _safe_num(ui.get("ra_esa_cm2")),
        "ee_ratio": _safe_num(ui.get("ee_ratio")),
        "trv_ms": _safe_num(ui.get("trv_ms")),
    }

    labs = {
        "hb_g_dl": _safe_num(ui.get("hb_g_dl")),
        "crp_mg_l": _safe_num(ui.get("crp_mg_l")),
        "creatinine_mg_dl": _safe_num(ui.get("creatinine_mg_dl")),
        "egfr_ml_min_1_73m2": _safe_num(ui.get("egfr")),
        "bnp_kind": ui.get("bnp_kind"),
        "bnp_value_pg_ml": _safe_num(ui.get("bnp_value")),
    }

    patient = {
        "firstname": ui.get("firstname"),
        "name": ui.get("name"),
        "age_years": _safe_num(ui.get("age")),
        "sex": ui.get("sex"),
        "height_cm": _safe_num(ui.get("height_cm")),
        "weight_kg": _safe_num(ui.get("weight_kg")),
    }

    context = {
        "who_fc": ui.get("who_fc"),
        "six_mwd_m": _safe_num(ui.get("six_mwd_m")),
        "story": ui.get(K_STORY),
        "ph_known": ui.get("ph_known"),
        "ph_suspected": ui.get("ph_suspected"),
        "ph_known_dx": ui.get("ph_known_dx"),
    }

    procedere = {
        "modules_selected": ui.get(K_MODULES) or [],
        "procedere_free": ui.get("procedere_free") or "",
    }

    _res = {
        "schema": "rhk_summary_v1",
        "generated_at": today,
        "app_version": APP_VERSION,
        "rulebook": rb_meta,
        "patient": patient,
        "context": context,
        "hemodynamics": hemo,
        "classification": classification,
        "echo": echo,
        "labs": labs,
        "procedere": procedere,
        "warnings": wslim,
    }
    _cache_set('summary_dict', fp, _res)
    return _res


def _atomic_json_write(payload: Any, path: str) -> str:
    """Write JSON atomically to avoid partially written files."""
    target_path = os.path.abspath(path)
    target_dir = os.path.dirname(target_path) or "."
    os.makedirs(target_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".rhk_tmp_", suffix=".json", dir=target_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return path


def export_json(case: CaseLike, path: str) -> str:
    """Write full case dict to JSON file atomically; returns the path."""
    return _atomic_json_write(case, path)


def export_summary_json(summary: Dict[str, Any], path: str) -> str:
    """Write summary dict to JSON file atomically; returns the path."""
    return _atomic_json_write(summary, path)


def load_case_json(file_path: str) -> Dict[str, Any]:
    """Load a previously exported case JSON file and return the dict."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)



def build_echo_doctor_report_extended(case: CaseLike) -> str:
    """Arztbericht Echokardiographie – strukturiert, PH-bezogen, Rechtsherz-Fokus.

    Implementierung liegt in `rhk_echo_report_doctor.py` und wird hier nur
    gecached/wrapped, um etablierte Schnittstellen stabil zu halten.
    """
    fp = _case_fingerprint(case)
    cached = _cache_get('echo_doctor_report', fp)
    if cached is not None:
        return cached

    from rhk_echo_report_doctor import build_echo_doctor_report as _impl
    out = _impl(dict(case))

    _cache_set('echo_doctor_report', fp, out)
    return out
