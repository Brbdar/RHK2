"""Doctor report assembly services.

These functions keep the orchestration layer out of `rhk_reports.py` while
reusing the existing text/render helpers defined there.
"""

from __future__ import annotations

from typing import Any, Dict

from rhk_case_schema import CaseLike


def build_doctor_report_template_service(case: CaseLike, blocks: Dict[str, Any]) -> str:
    from rhk_reports import (
        _cache_get,
        _cache_set,
        _case_fingerprint,
        _doctor_tpl_append_assessment_block,
        _doctor_tpl_append_cpet_block,
        _doctor_tpl_append_intro_block,
        _doctor_tpl_append_klinik_block,
        _doctor_tpl_append_preprocedural_safety,
        _doctor_tpl_append_procedere_block,
        _doctor_tpl_append_summary_section,
        _doctor_tpl_bul,
        _doctor_tpl_collect_hints,
        _doctor_tpl_par,
        build_render_ctx,
        summarize_inputs,
    )

    fp = _case_fingerprint(case)
    cached = _cache_get("doctor_report_template", fp)
    if cached is not None:
        return cached

    ui = case.get("ui", {}) or {}
    der = case.get("derived", {}) or {}
    sc = case.get("scores", {}) or {}
    dec = case.get("decision", {}) or {}
    env = case.get("env", {}) or {}
    ctx = build_render_ctx(case)

    out: list[str] = []
    _doctor_tpl_append_intro_block(out, ui)
    _doctor_tpl_append_preprocedural_safety(out, ui)
    _doctor_tpl_append_klinik_block(out, ui)

    summary_md = summarize_inputs(case) or ""
    _doctor_tpl_append_summary_section(out, summary_md=summary_md, source_title="Labor", section_title="Labor")
    _doctor_tpl_append_summary_section(
        out,
        summary_md=summary_md,
        source_title="Bildgebung / Echo / CMR",
        section_title="Bildgebung / Echo / CMR",
        nested_prefixes=("v/q details:", "echo:", "cmr:", "mrt:"),
    )
    _doctor_tpl_append_summary_section(
        out,
        summary_md=summary_md,
        source_title="Lungenfunktion",
        section_title="Lungenfunktion",
    )

    _doctor_tpl_append_cpet_block(out, ui)
    _doctor_tpl_append_assessment_block(out, ui=ui, der=der, dec=dec, scores=sc, blocks=blocks, ctx=ctx)
    _doctor_tpl_append_procedere_block(out, ui=ui, der=der, dec=dec, env=env, ctx=ctx, blocks=blocks)

    hints = _doctor_tpl_collect_hints(case)
    if hints:
        _doctor_tpl_par(out, "Zusätzliche Hinweise:")
        for hint in list(dict.fromkeys([item for item in hints if item]))[:8]:
            _doctor_tpl_bul(out, hint, 0)

    result = "\n".join(out).rstrip()
    _cache_set("doctor_report_template", fp, result)
    return result


def build_doctor_report_service(case: CaseLike, blocks: Dict[str, Any]) -> str:
    from rhk_reports import (
        _assemble_doctor_report_markdown,
        _build_doctor_beurteilung_text,
        _build_doctor_interpretation_text,
        _build_doctor_procedere_payload,
        _build_doctor_structured_sections,
        _cache_get,
        _cache_set,
        _case_fingerprint,
        _filter_narrative_block,
        _sanitize_recommendation_text,
        build_render_ctx,
        render_block,
    )

    fp = _case_fingerprint(case)
    cached = _cache_get("doctor_report", fp)
    if cached is not None:
        return cached

    ui = case["ui"]
    der = case["derived"]
    dec = case["decision"]
    env = case["env"]

    ctx = build_render_ctx(case)
    bundle_beurteilung_id = f"{dec['bundle']}_B"
    bundle_empfehlung_id = f"{dec['bundle']}_E"

    beurteilung = render_block(blocks[bundle_beurteilung_id], ctx) if bundle_beurteilung_id in blocks else f"[Fehlender Textblock: {bundle_beurteilung_id}]"
    beurteilung = _filter_narrative_block(beurteilung, ui, der)
    beurteilung = _build_doctor_beurteilung_text(beurteilung=beurteilung, ui=ui, der=der, ctx=ctx)

    empfehlung = render_block(blocks[bundle_empfehlung_id], ctx) if bundle_empfehlung_id in blocks else f"[Fehlender Textblock: {bundle_empfehlung_id}]"
    empfehlung = _filter_narrative_block(empfehlung, ui, der)
    empfehlung = _sanitize_recommendation_text(empfehlung)

    sections = _build_doctor_structured_sections(ui, der)
    procedere_payload = _build_doctor_procedere_payload(ui=ui, der=der, dec=dec, env=env, ctx=ctx, blocks=blocks)
    interpretation_text = _build_doctor_interpretation_text(
        case=case,
        ui=ui,
        der=der,
        concluding=str(procedere_payload["concluding"] or ""),
    )

    result = _assemble_doctor_report_markdown(
        case=case,
        ui=ui,
        ctx=ctx,
        beurteilung=beurteilung,
        interpretation_text=interpretation_text,
        sections=sections,
        all_mods=procedere_payload["all_mods"],
        modules_txts=procedere_payload["modules_txts"],
        skipped_mods_txts=procedere_payload["skipped_mods_txts"],
        auto_mods_txts=procedere_payload["auto_mods_txts"],
        recs=procedere_payload["recs"],
    )
    _cache_set("doctor_report", fp, result)
    return result
