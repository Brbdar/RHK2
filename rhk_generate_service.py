"""Runtime services for UI-triggered case/report generation."""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from rhk_base import (
    _normalize_module_ids,
    build_disabled_p_modules_html,
    build_p_module_choices,
    pmods_apply_overrides,
    pmods_get_force_optional,
)
from rhk_case import build_case, build_dashboard_html
from rhk_case_schema import CaseLike
from rhk_case_service import prepare_case_runtime_input
from rhk_logging import log_exception
from rhk_reports import (
    _extract_markdown_section_cached,
    _markdown_to_plain_cached,
    _markdown_to_word_html_cached,
    build_doctor_report,
    build_echo_doctor_report_extended,
    build_echo_patient_report,
    build_patient_report,
    build_summary_dict,
)
from rhk_ui_helpers import _build_generate_signature
from rhk_ui_utils import (
    build_compare_overview_html,
    build_docx_status_html,
    build_p_module_cards_html,
    build_sticky_summary_html,
)


@dataclass
class GeneratePmodulePayload:
    choices_lvl1: List[Tuple[str, str]]
    choices_lvl2: List[Tuple[str, str]]
    choices_lvl3: List[Tuple[str, str]]
    selected_lvl1_ids: List[str]
    selected_lvl2_ids: List[str]
    selected_lvl3_ids: List[str]
    disabled_html: str
    disabled_dd_choices: List[Tuple[str, str]]
    state: Dict[str, Any]


@dataclass
class GenerateArtifacts:
    auto_mpap: Any
    auto_ci: Any
    auto_pvr: Any
    auto_pvri: Any
    auto_tpg: Any
    auto_dpg: Any
    dashboard_html: str
    doctor_report: str
    patient_report: str
    echo_doctor_report: str
    echo_patient_report: str
    internal_report: str
    summary_json: str
    debug_json: str
    copy_doc_plain: str
    copy_pat_plain: str
    copy_rhk_plain: str
    copy_doc_html: str
    copy_pat_html: str
    copy_rhk_html: str
    case: CaseLike
    flags: Dict[str, Any]
    pmodules: GeneratePmodulePayload
    sticky_summary_html: str
    compare_overview_html: str
    rhk_plots_html: str
    import_status_html: str
    modules_cards_html: str

def _build_pmodule_payload(blocks: Dict[str, Any], case: CaseLike) -> GeneratePmodulePayload:
    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    policy = der.get("p_module_policy") or {}
    force_optional = pmods_get_force_optional(ui)
    eff_policy = pmods_apply_overrides(policy, force_optional)

    mod_choices = build_p_module_choices(blocks, eff_policy)
    disabled_html = build_disabled_p_modules_html(blocks, eff_policy)

    levels_map = (eff_policy.get("levels") or {}) if isinstance(eff_policy, dict) else {}
    disabled_map = (eff_policy.get("disabled") or {}) if isinstance(eff_policy, dict) else {}

    sel_vals = _normalize_module_ids(ui.get("modules") or [])
    locked_selected = [module_id for module_id in sel_vals if (module_id in disabled_map and module_id not in force_optional)]

    def _clean_label(label: Any) -> str:
        return re.sub(r"^\s*\[[^\]]+\]\s*", "", str(label) if label is not None else "").strip()

    id_to_label: Dict[str, str] = {module_id: _clean_label(label) for (label, module_id) in mod_choices}
    for module_id in locked_selected:
        if module_id not in id_to_label:
            title = blocks[module_id].title if module_id in blocks else ""
            id_to_label[module_id] = f"{module_id} – {title}".strip(" –")

    def _get_level(module_id: str) -> int:
        try:
            return int(levels_map.get(module_id, 3) or 3)
        except (TypeError, ValueError) as exc:
            log_exception("RHK_UI_PMOD_LEVEL", "Module level parse failed; defaulting to level 3.", exc, module_id=module_id)
            return 3

    selected_lvl1_ids = [module_id for module_id in sel_vals if _get_level(module_id) == 1]
    selected_lvl2_ids = [module_id for module_id in sel_vals if _get_level(module_id) == 2]
    selected_lvl3_ids = [module_id for module_id in sel_vals if _get_level(module_id) not in (1, 2)]

    allowed_ids = [module_id for (_label, module_id) in mod_choices]

    def _choices_for_level(level: int) -> List[Tuple[str, str]]:
        choices: List[Tuple[str, str]] = []
        for module_id in allowed_ids:
            if _get_level(module_id) != level:
                continue
            choices.append((id_to_label.get(module_id, module_id), module_id))
        for module_id in locked_selected:
            if _get_level(module_id) != level:
                continue
            choice = (id_to_label.get(module_id, module_id) + " (gesperrt)", module_id)
            if choice not in choices:
                choices.append(choice)
        return choices

    def _choices_for_level3() -> List[Tuple[str, str]]:
        choices: List[Tuple[str, str]] = []
        for module_id in allowed_ids:
            if _get_level(module_id) in (1, 2):
                continue
            choices.append((id_to_label.get(module_id, module_id), module_id))
        for module_id in locked_selected:
            if _get_level(module_id) in (1, 2):
                continue
            choice = (id_to_label.get(module_id, module_id) + " (gesperrt)", module_id)
            if choice not in choices:
                choices.append(choice)
        return choices

    disabled_dd_choices: List[Tuple[str, str]] = []
    for module_id, reason in sorted(disabled_map.items(), key=lambda item: item[0]):
        if module_id in force_optional:
            continue
        title = blocks[module_id].title if module_id in blocks else ""
        label = f"{module_id} – {title}".strip(" –")
        if reason:
            label = f"{label} | {reason}"
        disabled_dd_choices.append((label, module_id))

    state = {
        "lvl1": selected_lvl1_ids,
        "lvl2": selected_lvl2_ids,
        "lvl3": selected_lvl3_ids,
        "modules": sel_vals,
        "force_optional": list(force_optional),
    }

    return GeneratePmodulePayload(
        choices_lvl1=_choices_for_level(1),
        choices_lvl2=_choices_for_level(2),
        choices_lvl3=_choices_for_level3(),
        selected_lvl1_ids=selected_lvl1_ids,
        selected_lvl2_ids=selected_lvl2_ids,
        selected_lvl3_ids=selected_lvl3_ids,
        disabled_html=disabled_html,
        disabled_dd_choices=disabled_dd_choices,
        state=state,
    )


def generate_runtime_artifacts(
    *,
    case_state_in: Any,
    flags_state: Any,
    pmods_state: Any,
    docx_cur_state: Any,
    docx_prev_state: Any,
    raw_ui: Dict[str, Any],
    rules: List[Any],
    blocks: Dict[str, Any],
    rulebook_meta: Dict[str, Any],
    generate_cache: Dict[str, Any],
    perf_on: bool = False,
    lang: str = "de",
) -> GenerateArtifacts:
    flags = dict(flags_state or {})
    t0 = time.perf_counter() if perf_on else 0.0
    t_raw0 = t0
    t_case0 = t0
    t_rep0 = t0
    t_ui0 = t0

    if perf_on:
        t_raw0 = time.perf_counter()
    raw, base_case = prepare_case_runtime_input(
        raw_ui=raw_ui,
        case_state_in=case_state_in,
        pmods_state=pmods_state,
        flags=flags,
    )

    fast_load = bool(flags.get("fast_load"))
    gen_sig = _build_generate_signature({"raw": raw, "fast_load": fast_load})
    cached_payload = None
    cache_hit = False
    try:
        if gen_sig and generate_cache.get("sig") == gen_sig and isinstance(generate_cache.get("payload"), dict):
            cached_payload = generate_cache.get("payload")
            cache_hit = True
    except Exception as exc:
        log_exception("RHK_UI_GENERATE_CACHE_CHECK", "Generate cache lookup failed; continuing without cache.", exc)
        cached_payload = None
        cache_hit = False

    if perf_on:
        t_case0 = time.perf_counter()
    if isinstance(cached_payload, dict):
        case_computed: Dict[str, Any] = dict(cached_payload.get("case_computed") or {})
    else:
        case_computed = dict(build_case(raw, rules))
    if not isinstance(case_computed, dict) or ("derived" not in case_computed):
        case_computed = dict(build_case(raw, rules))
        cache_hit = False

    case: Dict[str, Any] = dict(base_case) if isinstance(base_case, dict) else {}
    try:
        case.update(case_computed)
        case["ui"] = raw
    except Exception as exc:
        log_exception("RHK_UI_GENERATE_CASE_MERGE", "Case merge failed; falling back to computed case.", exc)
        case = case_computed

    if perf_on:
        t_rep0 = time.perf_counter()
    if isinstance(cached_payload, dict):
        doc = str(cached_payload.get("doc") or "")
        pat = str(cached_payload.get("pat") or "")
        echo_doc = str(cached_payload.get("echo_doc") or "")
        echo_pat = str(cached_payload.get("echo_pat") or "")
        internal = str(
            cached_payload.get("internal")
            or "*(Intern-Report wird aus Performance-Gründen erst auf Knopfdruck erzeugt.)*"
        )
        dash = str(cached_payload.get("dash") or "")
        summary_dict = dict(cached_payload.get("summary_dict") or {})
        summary_json = str(cached_payload.get("summary_json") or "{}")
        doc_plain = str(cached_payload.get("doc_plain") or "")
        pat_plain = str(cached_payload.get("pat_plain") or "")
        rhk_plain = str(cached_payload.get("rhk_plain") or "")
        doc_html = str(cached_payload.get("doc_html") or "")
        pat_html = str(cached_payload.get("pat_html") or "")
        rhk_html = str(cached_payload.get("rhk_html") or "")
        case["summary"] = summary_dict
    else:
        doc = build_doctor_report(case, blocks)
        pat = build_patient_report(case, lang=lang)
        echo_doc = build_echo_doctor_report_extended(case)
        echo_pat = build_echo_patient_report(case)
        internal = "*(Intern-Report wird aus Performance-Gründen erst auf Knopfdruck erzeugt.)*"
        dash = build_dashboard_html(case)

        try:
            summary_dict = build_summary_dict(case, rulebook_meta)
            case["summary"] = summary_dict
            summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
        except Exception as exc:
            log_exception("RHK_UI_GENERATE_SUMMARY", "Summary generation failed; emitting empty summary.", exc)
            summary_dict = {}
            summary_json = "{}"

        try:
            doc_master_md = str(doc or "")
            doc_plain = _markdown_to_plain_cached(doc_master_md)
            pat_plain = _markdown_to_plain_cached(str(pat or ""))
            rhk_section = _extract_markdown_section_cached(str(doc or ""), "Rechtsherzkatheter", "Beurteilung")
            rhk_plain = _markdown_to_plain_cached(str(rhk_section or ""))

            if fast_load:
                doc_html = ""
                pat_html = ""
                rhk_html = ""
            else:
                doc_html = _markdown_to_word_html_cached(doc_master_md)
                pat_html = _markdown_to_word_html_cached(str(pat or ""))
                rhk_html = _markdown_to_word_html_cached(str(rhk_section or ""))
        except Exception as exc:
            log_exception("RHK_UI_GENERATE_CLIPBOARD_PAYLOADS", "Clipboard payload generation failed.", exc)
            doc_plain = ""
            pat_plain = ""
            rhk_plain = ""
            doc_html = ""
            pat_html = ""
            rhk_html = ""

        try:
            generate_cache["sig"] = gen_sig
            generate_cache["payload"] = {
                "case_computed": case_computed,
                "doc": doc,
                "pat": pat,
                "echo_doc": echo_doc,
                "echo_pat": echo_pat,
                "internal": internal,
                "dash": dash,
                "summary_dict": summary_dict,
                "summary_json": summary_json,
                "doc_plain": doc_plain,
                "pat_plain": pat_plain,
                "rhk_plain": rhk_plain,
                "doc_html": doc_html,
                "pat_html": pat_html,
                "rhk_html": rhk_html,
            }
        except Exception as exc:
            log_exception("RHK_UI_GENERATE_CACHE_STORE", "Generate cache store failed; continuing without cache.", exc)

    der = case["derived"]
    ci_calc = None
    if der.get("co") is not None and der.get("bsa_m2") is not None and der.get("bsa_m2"):
        try:
            co_value = der.get("co")
            bsa_value = der.get("bsa_m2")
            ci_calc = float(co_value) / float(bsa_value)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            log_exception("RHK_UI_CI_CALC", "CI calculation failed; using None.", exc)
            ci_calc = None

    flags["has_report"] = True
    flags["report_stale"] = False
    flags["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    flags.pop("fast_load", None)
    try:
        flags["warnings"] = case.get("warnings") or []
    except Exception as exc:
        log_exception("RHK_UI_FLAGS_WARNINGS_SET", "Failed to set warnings into flags state.", exc)
        flags["warnings"] = []

    if perf_on:
        t_ui0 = time.perf_counter()
    summary_html = build_sticky_summary_html(case, flags)
    compare_html = build_compare_overview_html(case)
    cards_html = build_p_module_cards_html(blocks, case)

    try:
        status_html = build_docx_status_html(docx_cur_state, docx_prev_state)
    except Exception as exc:
        log_exception("RHK_UI_DOCX_STATUS_HTML", "Docx import status HTML rendering failed.", exc)
        status_html = ""

    plots_html = "<div class='docx-muted'>Plots werden nur auf Knopfdruck erzeugt (Performance).</div>"
    pmodules = _build_pmodule_payload(blocks, case)

    if perf_on:
        t_end = time.perf_counter()
        try:
            print(
                "[PERF] Generate "
                f"total={(t_end - t0)*1000:.1f}ms | "
                f"raw={(t_case0 - t_raw0)*1000:.1f}ms | "
                f"case={(t_rep0 - t_case0)*1000:.1f}ms | "
                f"reports={(t_ui0 - t_rep0)*1000:.1f}ms | "
                f"ui={(t_end - t_ui0)*1000:.1f}ms | "
                f"cache_hit={cache_hit}"
            )
        except Exception as exc:
            log_exception("RHK_UI_PERF_PRINT", "Performance debug print failed.", exc)

    return GenerateArtifacts(
        auto_mpap=der.get("mpap_calc"),
        auto_ci=ci_calc,
        auto_pvr=der.get("pvr_calc"),
        auto_pvri=der.get("pvri"),
        auto_tpg=der.get("tpg"),
        auto_dpg=der.get("dpg"),
        dashboard_html=dash,
        doctor_report=doc,
        patient_report=pat,
        echo_doctor_report=echo_doc,
        echo_patient_report=echo_pat,
        internal_report=internal,
        summary_json=summary_json,
        debug_json='{\n  "note": "Debug JSON wird aus Performance-Gründen erst auf Knopfdruck erzeugt."\n}',
        copy_doc_plain=doc_plain,
        copy_pat_plain=pat_plain,
        copy_rhk_plain=rhk_plain,
        copy_doc_html=doc_html,
        copy_pat_html=pat_html,
        copy_rhk_html=rhk_html,
        case=case,
        flags=flags,
        pmodules=pmodules,
        sticky_summary_html=summary_html,
        compare_overview_html=compare_html,
        rhk_plots_html=plots_html,
        import_status_html=status_html,
        modules_cards_html=cards_html,
    )
