"""Doctor-report template helpers extracted from ``rhk_reports``.

The ``_doctor_tpl_*`` family builds the section-by-section doctor report
(the "Klinik-Layout" template). It is the largest cohesive sub-block of
the original 9 000-LoC rhk_reports.py.

Public surface
--------------
- All ``_doctor_tpl_*`` helpers — referenced internally and re-exported via
  rhk_reports for back-compat.

The K_* section keys are duplicated locally to keep the dependency graph
acyclic. If a key is renamed in rhk_reports, update it here too.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from rhk_base import (
    _ALL_P_MODULE_IDS,
    TextBlock,
    _fmt,
    _normalize_module_ids,
    _safe_float,
    fmt_int,
    pmods_apply_overrides,
    pmods_get_force_optional,
    render_block,
)
from rhk_case import filter_module_text, render_p01_dynamic
from rhk_case_schema import CaseLike
from rhk_logging import log_exception
from rhk_report_filters import _filter_narrative_block, _format_warning_item
from rhk_report_markdown import markdown_to_plain
from rhk_report_summary import _summary_clean_text, _summary_syncope_text

__all__ = [
    "_doctor_tpl_append_assessment_block",
    "_doctor_tpl_append_cpet_block",
    "_doctor_tpl_append_cpet_context_lines",
    "_doctor_tpl_append_intro_block",
    "_doctor_tpl_append_klinik_block",
    "_doctor_tpl_append_module_transparency",
    "_doctor_tpl_append_preprocedural_safety",
    "_doctor_tpl_append_procedere_block",
    "_doctor_tpl_append_risk_block",
    "_doctor_tpl_append_summary_section",
    "_doctor_tpl_bul",
    "_doctor_tpl_bundle_paragraphs",
    "_doctor_tpl_clean_bullet_text",
    "_doctor_tpl_clean_item",
    "_doctor_tpl_collect_hints",
    "_doctor_tpl_cpet_interpretation_lines",
    "_doctor_tpl_emit_module_text",
    "_doctor_tpl_emit_selected_module_content",
    "_doctor_tpl_extract_section",
    "_doctor_tpl_fmt_bp",
    "_doctor_tpl_has_cpet_data",
    "_doctor_tpl_module_state",
    "_doctor_tpl_par",
    "_doctor_tpl_render_module_text",
    "_doctor_tpl_split_items",
    "_doctor_tpl_study_hints",
    "_doctor_tpl_warning_hints",
]

# Mirror the section keys used by rhk_reports.
K_UI = "ui"
K_DERIVED = "derived"
K_BUNDLE = "bundle"
K_MODULES = "modules"
K_STORY = "story"
K_WARNINGS = "warnings"

_REPORT_RECOVERABLE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    TypeError,
    ValueError,
    ImportError,
    ModuleNotFoundError,
)


def _doctor_tpl_par(out: List[str], line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    out.append(text)
    out.append("")


def _doctor_tpl_bul(out: List[str], line: str, lvl: int = 0) -> None:
    text = str(line or "").strip()
    if not text:
        return
    indent = "  " * max(0, int(lvl))
    out.append(f"{indent}- {text}")


def _doctor_tpl_clean_item(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*[-•]\s+", "", text)
    return text.strip()


def _doctor_tpl_split_items(value: Any) -> List[str]:
    raw = str(value or "").strip()
    if not raw or raw in {"-", "—"}:
        return []
    if "\n" in raw:
        return [v for v in (_doctor_tpl_clean_item(x) for x in raw.splitlines()) if v]
    if ";" in raw:
        return [v for v in (_doctor_tpl_clean_item(x) for x in raw.split(";")) if v]
    one = _doctor_tpl_clean_item(raw)
    return [one] if one else []


def _doctor_tpl_fmt_bp(ui: Dict[str, Any], sys_key: str, dia_key: str) -> Optional[str]:
    sbp = _safe_float(ui.get(sys_key))
    dbp = _safe_float(ui.get(dia_key))
    if sbp is None and dbp is None:
        return None
    if sbp is not None and dbp is not None:
        return f"{fmt_int(sbp)}/{fmt_int(dbp)} mmHg"
    if sbp is not None:
        return f"{fmt_int(sbp)} mmHg"
    return f"{fmt_int(dbp)} mmHg"


def _doctor_tpl_extract_section(md: str, title: str) -> List[str]:
    if not md:
        return []
    start = f"### {title}"
    if start not in md:
        return []
    chunk = md.split(start, 1)[1]
    if "\n### " in chunk:
        chunk = chunk.split("\n### ", 1)[0]

    lines: List[str] = []
    for raw in chunk.splitlines():
        line = str(raw or "").strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        lines.append(line)
    return lines


def _doctor_tpl_append_intro_block(out: List[str], ui: Dict[str, Any]) -> None:
    _doctor_tpl_par(out, "**Allgemeines, Klinik, Bildgebung und Funktion:**")
    story = _summary_clean_text(ui.get(K_STORY))
    _doctor_tpl_par(out, f"Kurz-Anamnese: {story if story else '-'}")

    comorb_items = _doctor_tpl_split_items(ui.get("comorbidities"))
    if len(comorb_items) >= 2:
        _doctor_tpl_par(out, "Relevante Vorerkrankungen: -")
        for item in comorb_items:
            _doctor_tpl_bul(out, item, 0)
        out.append("")
    elif len(comorb_items) == 1:
        _doctor_tpl_par(out, f"Relevante Vorerkrankungen: {comorb_items[0]}")
    else:
        _doctor_tpl_par(out, "Relevante Vorerkrankungen: -")


def _doctor_tpl_append_preprocedural_safety(out: List[str], ui: Dict[str, Any]) -> None:
    access_route = _summary_clean_text(ui.get("access_route"))
    if access_route:
        _doctor_tpl_par(out, f"Zugang (geplant): {access_route}")

    consent_done = ui.get("consent_done")
    if consent_done is True:
        _doctor_tpl_par(out, "Aufklärung/Einwilligung: erfolgt")
    elif consent_done is False:
        _doctor_tpl_par(out, "Aufklärung/Einwilligung: nicht dokumentiert")

    anticoag_paused = ui.get("anticoag_paused")
    if anticoag_paused is True:
        _doctor_tpl_par(out, "Antikoagulation: pausiert (bitte Periprozedur-Plan prüfen)")
    elif anticoag_paused is False:
        _doctor_tpl_par(out, "Antikoagulation: nicht pausiert (bitte Periprozedur-Plan prüfen)")

    allergies_present = ui.get("allergies_present")
    allergies = ui.get("allergies_list") or []
    allergy_other = _summary_clean_text(ui.get("allergies_other_text"))
    if allergies_present is True:
        allergy_items: List[str] = []
        if isinstance(allergies, list):
            allergy_items.extend(str(x).strip() for x in allergies if str(x).strip())
        if allergy_other:
            allergy_items.append(allergy_other)
        text = ", ".join(allergy_items) if allergy_items else "ja (nicht spezifiziert)"
        _doctor_tpl_par(out, f"Allergien: {text}")
    elif allergies_present is False:
        _doctor_tpl_par(out, "Allergien: verneint")


def _doctor_tpl_append_klinik_block(out: List[str], ui: Dict[str, Any]) -> None:
    _doctor_tpl_par(out, "Klinik")
    bp = _doctor_tpl_fmt_bp(ui, "bp_sys", "bp_dia")
    if bp:
        _doctor_tpl_bul(out, f"Blutdruck: {bp}")
    hr = _safe_float(ui.get("hr"))
    if hr is not None:
        _doctor_tpl_bul(out, f"Herzfrequenz: {fmt_int(hr)}/min")
    if ui.get("dizziness") is True:
        _doctor_tpl_bul(out, "Schwindel: ja")
    syncope_txt = _summary_syncope_text(ui)
    if syncope_txt:
        _doctor_tpl_bul(out, f"Synkope: {syncope_txt}")
    if ui.get("exertional_dyspnea") is True:
        _doctor_tpl_bul(out, "Belastungsdyspnoe: ja")
    who_fc = _summary_clean_text(ui.get("who_fc"))
    if who_fc:
        _doctor_tpl_bul(out, f"WHO-FC: {who_fc}")
    six = _safe_float(ui.get("six_mwd_m"))
    if six is not None:
        six_dt = _summary_clean_text(ui.get("six_mwd_date"))
        text = f"6MWD: {_fmt(six,0)} m (Datum: {six_dt})" if six_dt else f"6MWD: {_fmt(six,0)} m"
        _doctor_tpl_bul(out, text)
    out.append("")


def _doctor_tpl_append_summary_section(
    out: List[str],
    *,
    summary_md: str,
    source_title: str,
    section_title: str,
    nested_prefixes: Tuple[str, ...] = (),
) -> None:
    lines = _doctor_tpl_extract_section(summary_md, source_title)
    if not lines:
        return
    _doctor_tpl_par(out, f"{section_title}:")
    nested = tuple(str(x).lower() for x in nested_prefixes)
    for line in lines:
        lvl = 1 if nested and str(line).lower().startswith(nested) else 0
        _doctor_tpl_bul(out, line, lvl)
    out.append("")


def _doctor_tpl_has_cpet_data(ui: Dict[str, Any]) -> bool:
    keys = [
        "cpet_peak_vo2_ml_kg_min",
        "cpet_ve_vco2_slope",
        "cpet_petco2_rest_mmhg",
        "cpet_hr_peak_bpm",
        "cpet_rer_peak",
    ]
    return any(_safe_float(ui.get(k)) is not None for k in keys) or bool(_summary_clean_text(ui.get("cpet_summary")))


def _doctor_tpl_append_cpet_context_lines(out: List[str], ui: Dict[str, Any]) -> None:
    for key, label in (
        ("cpet_protocol", "Protokoll"),
        ("cpet_site", "Ort/Setup"),
        ("cpet_chrono_comment", "Chronotrope Limitierung"),
    ):
        val = _summary_clean_text(ui.get(key))
        if val:
            _doctor_tpl_bul(out, f"{label}: {val}", 0)


def _doctor_tpl_cpet_interpretation_lines(ui: Dict[str, Any]) -> List[str]:
    try:
        import spiro_logic as _spiro
        res = _spiro.analyze(dict(ui))
    except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_REP_CPET_SPIRO", "Spiro-Logic interpretation unavailable.", exc)
        res = None

    lines: List[str] = []
    if res and (res.headline or res.clinical_summary):
        if res.headline:
            lines.append(str(res.headline))
        if res.clinical_summary:
            lines.append(str(res.clinical_summary))
        return lines

    vo2 = _safe_float(ui.get("cpet_peak_vo2_ml_kg_min"))
    if vo2 is not None:
        lines.append(f"V'O2max/kg: {_fmt(vo2,1)} mL/min/kg")
    vevco2 = _safe_float(ui.get("cpet_ve_vco2_slope"))
    if vevco2 is not None:
        lines.append(f"V'E/V'CO2 Slope: {_fmt(vevco2,1)}")
    return lines


def _doctor_tpl_append_cpet_block(out: List[str], ui: Dict[str, Any]) -> None:
    if not _doctor_tpl_has_cpet_data(ui):
        return
    _doctor_tpl_par(out, "Spiroergometrie / CPET:")
    _doctor_tpl_append_cpet_context_lines(out, ui)
    for line in _doctor_tpl_cpet_interpretation_lines(ui):
        _doctor_tpl_bul(out, line, 0)

    cpet_note = _summary_clean_text(ui.get("cpet_summary"))
    if cpet_note:
        _doctor_tpl_bul(out, f"Kommentar: {cpet_note}", 0)
    out.append("")


def _doctor_tpl_bundle_paragraphs(
    *,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
    blocks: Dict[str, TextBlock],
    ctx: Dict[str, Any],
) -> Tuple[str, str]:
    bundle = str(dec.get(K_BUNDLE) or "").strip()
    b_id = f"{bundle}_B" if bundle else ""
    e_id = f"{bundle}_E" if bundle else ""
    beur = render_block(blocks[b_id], ctx) if b_id and b_id in blocks else ""
    empf = render_block(blocks[e_id], ctx) if e_id and e_id in blocks else ""
    beur_txt = _filter_narrative_block(markdown_to_plain(beur).strip(), ui, der)
    empf_txt = _filter_narrative_block(markdown_to_plain(empf).strip(), ui, der)
    return beur_txt, empf_txt


def _doctor_tpl_append_risk_block(out: List[str], scores: Dict[str, Any]) -> None:
    if not (
        scores.get("esc_ers_4s")
        or scores.get("esc_ers_3s")
        or scores.get("reveal_lite2")
        or scores.get("reveal_lite2_points")
    ):
        return

    if scores.get("esc_ers_4s"):
        _doctor_tpl_bul(out, f"ESC/ERS 4-Strata: {scores.get('esc_ers_4s')}", 0)
    if scores.get("esc_ers_3s"):
        _doctor_tpl_bul(out, f"ESC/ERS 3-Strata: {scores.get('esc_ers_3s')}", 0)

    cat = scores.get("reveal_lite2")
    if cat is not None:
        pts = scores.get("reveal_lite2_points")
        if str(cat) == "nicht berechenbar":
            missing = scores.get("reveal_lite2_missing") or []
            miss_txt = ", ".join(missing) if missing else "Parameter unvollständig"
            _doctor_tpl_bul(out, f"REVEAL Lite 2: nicht berechenbar (fehlend: {miss_txt})", 0)
        else:
            cat_de = {"low": "niedrig", "intermediate": "intermediär", "high": "hoch"}.get(str(cat), str(cat))
            pts_txt = str(pts) if pts is not None else "—"
            _doctor_tpl_bul(out, f"REVEAL Lite 2: {pts_txt} Punkte ({cat_de})", 0)
    out.append("")


def _doctor_tpl_append_assessment_block(
    out: List[str],
    *,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
    scores: Dict[str, Any],
    blocks: Dict[str, TextBlock],
    ctx: Dict[str, Any],
) -> None:
    _doctor_tpl_par(out, "Beurteilung und Empfehlung:")
    beur_txt, empf_txt = _doctor_tpl_bundle_paragraphs(ui=ui, der=der, dec=dec, blocks=blocks, ctx=ctx)
    if beur_txt:
        _doctor_tpl_par(out, beur_txt)
    if empf_txt:
        _doctor_tpl_par(out, empf_txt)
    else:
        leading_cause = dec.get("leading_cause") or "unklaren Genese"
        _doctor_tpl_par(
            out,
            "In der Zusammenschau der Befunde ergeben sich Hinweise auf mehrere mögliche "
            f"Ursachen/Mechanismen ({leading_cause}). Eine eindeutige führende Zuordnung ist "
            "anhand der vorliegenden Angaben nicht sicher.",
        )
    _doctor_tpl_append_risk_block(out, scores)


def _doctor_tpl_clean_bullet_text(line: str) -> str:
    txt = str(line or "").strip()
    while txt.startswith("•") or txt.startswith("-") or txt.startswith("–"):
        txt = txt[1:].lstrip()
    return txt


def _doctor_tpl_render_module_text(
    *,
    module_id: str,
    block: Optional[TextBlock],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
) -> str:
    if module_id == "P01":
        return str(render_p01_dynamic(env) or "").strip()
    if not block:
        return ""
    rendered = render_block(block, ctx)
    return str(filter_module_text(rendered, env) or "").strip()


def _doctor_tpl_emit_module_text(out: List[str], text: str) -> bool:
    lines = [_doctor_tpl_clean_bullet_text(ln) for ln in str(text or "").splitlines() if str(ln).strip()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return False
    _doctor_tpl_bul(out, lines[0], 0)
    for sub in lines[1:]:
        _doctor_tpl_bul(out, sub, 1)
    return True


def _doctor_tpl_module_state(
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
) -> Tuple[List[str], List[str], Dict[str, str], List[str], List[str], List[str]]:
    selected_mods = _normalize_module_ids(ui.get(K_MODULES) or [])
    decision_mods = _normalize_module_ids(dec.get(K_MODULES) or [])
    policy = der.get("p_module_policy") or {}
    eff_policy = pmods_apply_overrides(policy, pmods_get_force_optional(ui))
    disabled_mods: Dict[str, str] = eff_policy.get("disabled") or {}
    allowed_order: List[str] = eff_policy.get("allowed") or list(_ALL_P_MODULE_IDS)

    active_selected_mods = [m for m in selected_mods if m not in disabled_mods]
    skipped_selected_mods = [m for m in selected_mods if m in disabled_mods]
    auto_mods = [m for m in decision_mods if m not in selected_mods]
    return selected_mods, allowed_order, disabled_mods, active_selected_mods, skipped_selected_mods, auto_mods


def _doctor_tpl_emit_selected_module_content(
    out: List[str],
    *,
    selected: List[str],
    allowed: List[str],
    disabled: Dict[str, str],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
    blocks: Dict[str, TextBlock],
) -> bool:
    emitted = False
    for module_id in allowed:
        if module_id not in selected or module_id in disabled:
            continue
        txt = _doctor_tpl_render_module_text(
            module_id=module_id,
            block=blocks.get(module_id),
            env=env,
            ctx=ctx,
        )
        if _doctor_tpl_emit_module_text(out, txt):
            emitted = True
    return emitted


def _doctor_tpl_append_module_transparency(
    out: List[str],
    *,
    active: List[str],
    skipped: List[str],
    auto: List[str],
    disabled: Dict[str, str],
) -> None:
    if active:
        _doctor_tpl_bul(out, "Ausgewählt übernommen: " + ", ".join(active), 0)
    if skipped:
        for module_id in skipped:
            reason = _summary_clean_text(disabled.get(module_id))
            if reason:
                _doctor_tpl_bul(out, f"Ausgewählt, aber nicht anwählbar: {module_id} ({reason})", 0)
            else:
                _doctor_tpl_bul(out, f"Ausgewählt, aber nicht anwählbar: {module_id}", 0)
    if auto:
        _doctor_tpl_bul(out, "Regelwerk-Vorschläge (nicht automatisch übernommen): " + ", ".join(auto), 0)


def _doctor_tpl_append_procedere_block(
    out: List[str],
    *,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    dec: Dict[str, Any],
    env: Dict[str, Any],
    ctx: Dict[str, Any],
    blocks: Dict[str, TextBlock],
) -> None:
    _doctor_tpl_par(out, "Procedere:")
    selected, allowed, disabled, active, skipped, auto = _doctor_tpl_module_state(ui, der, dec)
    emitted_any = _doctor_tpl_emit_selected_module_content(
        out,
        selected=selected,
        allowed=allowed,
        disabled=disabled,
        env=env,
        ctx=ctx,
        blocks=blocks,
    )

    free = _summary_clean_text(ui.get("procedere_free"))
    if free:
        _doctor_tpl_bul(out, free, 0)
        emitted_any = True

    if not emitted_any:
        _doctor_tpl_bul(
            out,
            "Kein spezifisches Procedere ausgewählt oder ableitbar (Module nicht gewählt oder Daten fehlen).",
            0,
        )
    _doctor_tpl_append_module_transparency(out, active=active, skipped=skipped, auto=auto, disabled=disabled)
    out.append("")


def _doctor_tpl_warning_hints(case: CaseLike) -> List[str]:
    hints: List[str] = []
    warnings = case.get(K_WARNINGS) or []
    if not isinstance(warnings, list):
        return hints
    for item in warnings:
        text = _format_warning_item(item)
        if not text:
            continue
        low = text.lower()
        if "fehl" in low or "unvoll" in low:
            continue
        hints.append(text)
    return hints


def _doctor_tpl_study_hints(case: CaseLike) -> List[str]:
    try:
        from rhk_study_checks import get_study_hints
        hints = get_study_hints(dict(case))
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_STUDY_HINTS", "Study hint rendering failed.", exc)
        return []
    if not isinstance(hints, list):
        return []
    return [str(h).strip() for h in hints if str(h).strip()]


def _doctor_tpl_collect_hints(case: CaseLike) -> List[str]:
    ui = case.get(K_UI) or {}
    der = case.get(K_DERIVED) or {}
    hints: List[str] = []

    try:
        if bool(ui.get("dzl_flag")):
            decision = _summary_clean_text(ui.get("dzl_decision")) or "Noch nicht gefragt"
            hints.append(f"DZL: {decision}.")
    except _REPORT_RECOVERABLE_ERRORS as exc:
        log_exception("RHK_REP_DZL_HINT", "DZL hint construction failed.", exc)

    bmi = _safe_float(der.get("bmi"))
    if bmi is not None and bmi >= 30:
        hints.append(
            "Adipositas kann Dyspnoe und Leistungsfähigkeit beeinflussen; "
            "Belastbarkeit im Kontext (Training, Lagerung, Atemmuster) interpretieren."
        )

    hints.extend(_doctor_tpl_warning_hints(case))
    hints.extend(_doctor_tpl_study_hints(case))
    return hints
