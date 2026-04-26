"""Input-summary helpers extracted from ``rhk_reports``.

These functions build the structured Markdown overview of raw input data
that is shown alongside the doctor and patient reports.

Public surface
--------------
- ``summarize_inputs(case, *, mode="default")`` — entry point.
- ``_summary_*`` helpers — leaf-level builders for individual sections.
- ``_build_risk_lines``, ``_extract_positive_detail_parts``,
  ``_get_ph_tx_episodes``, ``_normalize_yes_no_status`` — small helpers
  that were only used inside this block, moved with it.

Notes
-----
The K_* section keys are duplicated locally to avoid a circular import
with rhk_reports. If a key is renamed there, update it here too.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rhk_base import (
    _fmt,
    _safe_float,
    _safe_float_echo,
    fmt_int,
)
from rhk_case_schema import CaseLike
from rhk_logging import log_exception
from rhk_ph_tx import (
    format_ph_tx_episode_line,
    legacy_lists_to_episodes,
    parse_ph_tx_table_rows,
)
from rhk_report_filters import _md_kv, _md_section
from rhk_validation import parse_boolish

__all__ = [
    "summarize_inputs",
    "_build_risk_lines",
    "_extract_positive_detail_parts",
    "_get_ph_tx_episodes",
    "_normalize_yes_no_status",
    "_summary_bp_line",
    "_summary_clean_text",
    "_summary_cmr_bits",
    "_summary_cmr_lines",
    "_summary_context_lines",
    "_summary_cpet_add_metric",
    "_summary_cpet_items",
    "_summary_cpet_predicted_line",
    "_summary_cpet_rr_items",
    "_summary_cpet_section",
    "_summary_cpet_symptom_items",
    "_summary_ct_lines",
    "_summary_echo_bits",
    "_summary_echo_derived_bits",
    "_summary_echo_flag_bits",
    "_summary_echo_lines",
    "_summary_echo_ui_bits",
    "_summary_ekg_sign_items",
    "_summary_exam_lines",
    "_summary_imaging_lines",
    "_summary_infectious_genetic_lines",
    "_summary_klinik_lines",
    "_summary_labor_section",
    "_summary_lsb_lines",
    "_summary_lufu_section",
    "_summary_medication_lines",
    "_summary_anticoag_message",
    "_summary_antifibrotic_message",
    "_summary_ph_lines",
    "_summary_ph_therapy_lines",
    "_summary_positive_line",
    "_summary_symptom_lines",
    "_summary_syncope_text",
    "_summary_vq_lines",
]

# Mirror the section keys used by rhk_reports (single source of truth lives
# there; if those rename, update here).
K_UI = "ui"
K_DERIVED = "derived"
K_SCORES = "scores"
K_STATUS = "status"
K_STORY = "story"
K_CHD_POS = "chd_pos"


def _section(case: CaseLike, key: str) -> Dict[str, Any]:
    """Narrow ``case.get(key) or {}`` to ``Dict[str, Any]`` for mypy."""
    val = case.get(key)
    return val if isinstance(val, dict) else {}


def _build_risk_lines(case: CaseLike) -> List[str]:
    """Build risk stratification lines (doctor-facing) as markdown list items."""
    sc = _section(case, K_SCORES)
    der = _section(case, K_DERIVED)
    lines: List[str] = []
    if sc.get("esc_ers_4s"):
        lines.append(_md_kv("ESC/ERS 4-Strata", str(sc["esc_ers_4s"])))
    if sc.get("esc_ers_3s"):
        lines.append(_md_kv("ESC/ERS 3-Strata", str(sc["esc_ers_3s"])))
    if sc.get("reveal_lite2"):
        cat = sc.get("reveal_lite2")
        pts = sc.get("reveal_lite2_points")
        if cat == "nicht berechenbar":
            missing = sc.get("reveal_lite2_missing") or []
            miss_txt = ", ".join(missing) if missing else "Parameter unvollständig"
            lines.append(_md_kv("REVEAL Lite 2", f"nicht berechenbar (fehlend: {miss_txt})"))
        else:
            cat_de = {"low": "niedrig", "intermediate": "intermediär", "high": "hoch"}.get(str(cat), str(cat))
            pts_txt = str(pts) if pts is not None else "—"
            lines.append(_md_kv("REVEAL Lite 2", f"{pts_txt} Punkte ({cat_de})"))
    if der.get("hfpef_category"):
        lines.append(_md_kv("HFpEF (H2FPEF)", f"{der['hfpef_category']} (~{_fmt(der.get('hfpef_percent'),0)}%)"))
    return lines


def _extract_positive_detail_parts(items_value: Any, desc_value: Any) -> List[str]:
    parts: List[str] = []
    if isinstance(items_value, list):
        parts.extend(str(x).strip() for x in items_value if str(x).strip())
    elif isinstance(items_value, str) and items_value.strip():
        parts.append(items_value.strip())
    desc = str(desc_value or "").strip()
    if desc:
        parts.append(desc)
    return parts

def _get_ph_tx_episodes(ui: Dict[str, Any], derived: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Return PH therapy episodes (prefer derived, else parse UI table, else legacy lists)."""
    der = derived or {}
    if isinstance(der.get("ph_tx_episodes"), list):
        eps = [e for e in (der.get("ph_tx_episodes") or []) if isinstance(e, dict)]
        if eps:
            return eps
    rows = ui.get("ph_tx_table")
    eps = parse_ph_tx_table_rows(rows)
    if eps:
        return eps
    return legacy_lists_to_episodes(ui)


def _summary_clean_text(value: Any) -> str:
    txt = str(value).strip() if value is not None else ""
    if txt.lower() in {"", "-", "—", "keine angabe", "k. a."}:
        return ""
    return txt


def _normalize_yes_no_status(value: Any) -> Tuple[str, str]:
    """Normalize mixed yes/no inputs to stable German status tokens.

    Returns (display, normalized) where normalized is typically "ja"/"nein"
    and display is user-facing text.
    """
    if isinstance(value, bool):
        return ("ja", "ja") if value else ("nein", "nein")

    if isinstance(value, (int, float)):
        try:
            if bool(parse_boolish(value)):
                return "ja", "ja"
            return "nein", "nein"
        except Exception:
            pass

    status = _summary_clean_text(value)
    if not status:
        return "", ""

    tok = status.strip().lower()
    yes_tokens = {"ja", "j", "yes", "y", "true", "t", "1", "on", "aktiv"}
    no_tokens = {"nein", "no", "false", "f", "0", "off", "inaktiv"}
    if tok in yes_tokens:
        return "ja", "ja"
    if tok in no_tokens:
        return "nein", "nein"
    return status, tok


def _summary_positive_line(
    ui: Dict[str, Any],
    *,
    pos_key: str,
    items_key: str,
    desc_key: str,
    label: str,
) -> Optional[str]:
    if ui.get(pos_key) is not True:
        return None
    parts = _extract_positive_detail_parts(ui.get(items_key), ui.get(desc_key))
    details = " / ".join([p for p in parts if p]) if parts else "positiv"
    return _md_kv(label, details)


def _summary_ph_therapy_lines(ui: Dict[str, Any], der: Dict[str, Any]) -> List[str]:
    eps = _get_ph_tx_episodes(ui, der)
    if not eps:
        return []

    lines: List[str] = []
    status_map: List[Tuple[str, set[str]]] = [
        ("PH Therapie Historie", {"früher", "abgesetzt", "pausiert"}),
        ("PH Therapie aktuell", {"aktuell"}),
        ("PH Therapie geplant", {"geplant"}),
    ]
    for label, statuses in status_map:
        vals = [
            format_ph_tx_episode_line(e)
            for e in eps
            if str(e.get(K_STATUS) or "").strip().lower() in statuses
        ]
        vals = [v for v in vals if v]
        if vals:
            lines.append(_md_kv(label, ", ".join(vals)))
    return lines


def _summary_ph_lines(ui: Dict[str, Any], der: Dict[str, Any], *, is_doctor: bool) -> List[str]:
    if is_doctor:
        return []
    if ui.get("ph_known") is True:
        lines = [_md_kv("PH-Diagnose", "bekannt")]
        for key, label in (
            ("ph_known_dx", "Bekannte PH-Diagnose"),
            ("ph_first_dx", "Erstdiagnose"),
            ("ph_reason_rhk", "Aktueller Anlass"),
            ("ph_known_subtype", "Subtyp/Kontext"),
        ):
            val = _summary_clean_text(ui.get(key))
            if val:
                lines.append(_md_kv(label, val))
        lines.extend(_summary_ph_therapy_lines(ui, der))
        interventions = ui.get("ph_interventions") or []
        if isinstance(interventions, list):
            vals = [str(x).strip() for x in interventions if str(x).strip()]
            if vals:
                lines.append(_md_kv("Interventionen", ", ".join(vals)))
        return lines
    if ui.get("ph_suspected") is True:
        return [_md_kv("PH-Verdachtsdiagnose", "ja")]
    return []


def _summary_bp_line(ui: Dict[str, Any]) -> Optional[str]:
    sbp = _safe_float(ui.get("bp_sys"))
    dbp = _safe_float(ui.get("bp_dia"))
    if sbp is None and dbp is None:
        return None
    if sbp is not None and dbp is not None:
        return _md_kv("Blutdruck", f"{fmt_int(sbp)}/{fmt_int(dbp)} mmHg")
    if sbp is not None:
        return _md_kv("Blutdruck", f"{fmt_int(sbp)} mmHg")
    return _md_kv("Blutdruck", f"{fmt_int(dbp)} mmHg")


def _summary_syncope_text(ui: Dict[str, Any]) -> str:
    syn = ui.get("syncope")
    if isinstance(syn, bool):
        return "ja" if syn else ""
    txt = _summary_clean_text(syn)
    if txt.lower() in {"nein", "keine"}:
        return ""
    return txt


def _summary_ekg_sign_items(ui: Dict[str, Any]) -> List[str]:
    if ui.get("ekg_present") is not True:
        return []
    signs = ui.get("ekg_rhs_signs") or []
    items: List[str] = []
    if isinstance(signs, list):
        items.extend(
            str(x).strip()
            for x in signs
            if str(x).strip() and str(x).strip().lower() != "sonstiges/unklar"
        )
    other = _summary_clean_text(ui.get("ekg_other_text"))
    if other:
        items.append(other)
    return items


def _summary_lsb_lines(ui: Dict[str, Any]) -> List[str]:
    if ui.get("lsb_present") is not True:
        return []
    lines = [_md_kv("LSB", "ja")]
    reason = _summary_clean_text(ui.get("lsb_reason"))
    if reason:
        lines.append(_md_kv("LSB Begründung", reason))
    return lines


def _summary_exam_lines(ui: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    bp_line = _summary_bp_line(ui)
    if bp_line:
        lines.append(bp_line)

    hr = _safe_float(ui.get("hr"))
    if hr is not None:
        lines.append(_md_kv("Herzfrequenz", f"{fmt_int(hr)}/min"))

    ekg_items = _summary_ekg_sign_items(ui)
    if ekg_items:
        lines.append(_md_kv("EKG Rechtsherzbelastungszeichen", ", ".join(ekg_items)))
    lines.extend(_summary_lsb_lines(ui))

    if ui.get("on_nitrates") is True:
        lines.append(_md_kv("Nitrate/NO-Donor", "ja"))

    if ui.get("pde5_hardship") is True:
        desc = _summary_clean_text(ui.get("pde5_hardship_desc"))
        lines.append(_md_kv("PDE-5 Härtefall", desc if desc else "ja"))
    return lines


def _summary_symptom_lines(ui: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if ui.get("exertional_dyspnea") is True:
        lines.append(_md_kv("Belastungsdyspnoe", "ja"))

    syncope_txt = _summary_syncope_text(ui)
    if syncope_txt:
        lines.append(_md_kv("Synkope", syncope_txt))

    if ui.get("hemoptysis") is True:
        lines.append(_md_kv("Hämoptyse", "ja"))
    if ui.get("dizziness") is True:
        lines.append(_md_kv("Schwindel", "ja"))

    stairs = ui.get("stairs_flights")
    if stairs not in (None, "", 0):
        lines.append(_md_kv("Treppenstufen/Etagen (Alltag)", str(stairs)))

    who_fc = _summary_clean_text(ui.get("who_fc"))
    if who_fc:
        lines.append(_md_kv("WHO-FC", who_fc))

    six = _safe_float(ui.get("six_mwd_m"))
    if six is not None:
        six_dt = _summary_clean_text(ui.get("six_mwd_date"))
        if six_dt:
            lines.append(_md_kv("6MWD", f"{_fmt(six,0)} m (Datum: {six_dt})"))
        else:
            lines.append(_md_kv("6MWD", f"{_fmt(six,0)} m"))
    return lines


def _summary_anticoag_message(ui: Dict[str, Any], *, is_doctor: bool) -> Tuple[str, str]:
    status_display, status_norm = _normalize_yes_no_status(ui.get("anticoag_status"))
    if not status_display:
        return "", ""
    if is_doctor and status_norm != "ja":
        return "", status_norm

    msg = status_display
    if status_norm == "ja":
        bits: List[str] = []
        sub = _summary_clean_text(ui.get("anticoag_substance"))
        ind = _summary_clean_text(ui.get("anticoag_indication"))
        since = _summary_clean_text(ui.get("anticoag_since"))
        if sub:
            bits.append(sub)
        if ind:
            bits.append(f"Indikation: {ind}")
        if since:
            bits.append(f"seit {since}")
        if bits:
            msg += " (" + "; ".join(bits) + ")"
    return msg, status_norm


def _summary_antifibrotic_message(ui: Dict[str, Any]) -> Tuple[str, str]:
    status_display, status_norm = _normalize_yes_no_status(ui.get("antifibrotic_status"))
    if not status_display:
        return "", ""
    msg = status_display
    if status_norm == "ja":
        bits: List[str] = []
        drug = _summary_clean_text(ui.get("antifibrotic_drug"))
        since = _summary_clean_text(ui.get("antifibrotic_since"))
        if drug:
            bits.append(drug)
        if since:
            bits.append(f"seit {since}")
        if bits:
            msg += " (" + "; ".join(bits) + ")"
    return msg, status_norm


def _summary_medication_lines(ui: Dict[str, Any], *, is_doctor: bool) -> List[str]:
    lines: List[str] = []

    anticoag_msg, anticoag_status = _summary_anticoag_message(ui, is_doctor=is_doctor)
    if anticoag_msg:
        lines.append(_md_kv("Antikoagulation", anticoag_msg))
    anticoag_note = _summary_clean_text(ui.get("anticoag_note"))
    if anticoag_note and anticoag_status.lower() in {"ja", "nein"} and (not is_doctor):
        lines.append(_md_kv("Antikoagulation – Bem.", anticoag_note))

    antif_msg, antif_status = _summary_antifibrotic_message(ui)
    if antif_msg:
        lines.append(_md_kv("Antifibrotische Therapie", antif_msg))
    antif_note = _summary_clean_text(ui.get("antifibrotic_note"))
    if antif_note and antif_status.lower() in {"ja", "nein"}:
        lines.append(_md_kv("Antifibrotika – Bem.", antif_note))

    ltx = _summary_clean_text(ui.get("ltx_eval"))
    if ltx:
        ltx_dt = _summary_clean_text(ui.get("ltx_eval_date"))
        if ltx_dt:
            lines.append(_md_kv("LTX-Evaluation", f"{ltx} (Datum: {ltx_dt})"))
        else:
            lines.append(_md_kv("LTX-Evaluation", ltx))
    return lines


def _summary_context_lines(ui: Dict[str, Any], *, is_doctor: bool) -> List[str]:
    lines: List[str] = []
    story = _summary_clean_text(ui.get(K_STORY))
    if story:
        lines.append(_md_kv("Kurz-Anamnese", story))

    comorb = _summary_clean_text(ui.get("comorbidities"))
    if comorb and (not is_doctor):
        lines.append(_md_kv("Relevante Vorerkrankungen", comorb))

    if (not is_doctor) and ui.get(K_CHD_POS) is True:
        chd_type = _summary_clean_text(ui.get("chd_type"))
        chd_desc = _summary_clean_text(ui.get("chd_desc"))
        txt = "ja"
        if chd_type:
            txt += f" ({chd_type})"
        if chd_desc:
            txt += f" – {chd_desc}"
        lines.append(_md_kv("Angeborener Herzfehler/Shunt", txt))
    return lines


def _summary_infectious_genetic_lines(ui: Dict[str, Any], *, is_doctor: bool) -> List[str]:
    lines: List[str] = []
    defs = [
        ("virology_pos", "virology_items", "virology_desc", "Virologie/Infektiologie", not is_doctor),
        ("immunology_pos", "immunology_items", "immunology_desc", "Immunologie/Autoimmun", not is_doctor),
        ("mutation_pos", "mutation_items", "mutation_desc", "Genetik/Mutation", True),
    ]
    for pos_key, items_key, desc_key, label, allowed in defs:
        if not allowed:
            continue
        line = _summary_positive_line(
            ui,
            pos_key=pos_key,
            items_key=items_key,
            desc_key=desc_key,
            label=label,
        )
        if line:
            lines.append(line)
    return lines


def _summary_klinik_lines(case: CaseLike, *, is_doctor: bool) -> List[str]:
    ui = _section(case, K_UI)
    der = _section(case, K_DERIVED)
    lines: List[str] = []
    lines.extend(_summary_context_lines(ui, is_doctor=is_doctor))
    lines.extend(_summary_infectious_genetic_lines(ui, is_doctor=is_doctor))
    lines.extend(_summary_ph_lines(ui, der, is_doctor=is_doctor))
    lines.extend(_summary_exam_lines(ui))
    lines.extend(_summary_symptom_lines(ui))
    lines.extend(_summary_medication_lines(ui, is_doctor=is_doctor))

    if not lines:
        lines.append("Keine klinischen Angaben erfasst.")
    if is_doctor:
        risk_lines = _build_risk_lines(case)
        if risk_lines:
            lines.append("- **Risikostratifizierung:**")
            lines.extend(risk_lines)
    return lines


def _summary_labor_section(ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    lab_items: List[str] = []

    hb = _safe_float(ui.get("hb_g_dl"))
    if hb is not None:
        suffix = " (Anämie)" if der.get("anemia") else ""
        lab_items.append(f"Hb: {_fmt(hb,1)} g/dl{suffix}")

    for key, label, digits, unit in (
        ("crp_mg_l", "CRP", 1, "mg/l"),
        ("creatinine_mg_dl", "Kreatinin", 2, "mg/dl"),
        ("egfr", "eGFR", 0, "ml/min/1,73m²"),
        ("inr", "INR", 2, ""),
        ("ptt_s", "PTT", 0, "s"),
        ("platelets_g_l", "Thrombozyten", 0, "G/l"),
        ("leukocytes_g_l", "Leukozyten", 1, "G/l"),
    ):
        val = _safe_float(ui.get(key))
        if val is None:
            continue
        if digits == 0 and label == "eGFR":
            lab_items.append(f"{label}: {fmt_int(val)} {unit}".strip())
        else:
            lab_items.append(f"{label}: {_fmt(val,digits)} {unit}".strip())

    tail: List[str] = []
    bnp_kind = ui.get("bnp_kind")
    bnp_val = _safe_float(ui.get("bnp_value"))
    if bnp_val is not None:
        extra = ""
        if (
            ui.get("entresto") is True
            and isinstance(bnp_kind, str)
            and "BNP" in bnp_kind.upper()
            and "NT" not in bnp_kind.upper()
        ):
            extra = " (Hinweis: unter ARNI ist NT-proBNP für den Verlauf meist besser verwertbar)"
        tail.append(f"**{str(bnp_kind or 'BNP/NT-proBNP')}:** {_fmt(bnp_val,0)} pg/ml{extra}")

    cong_org = _summary_clean_text(ui.get("congestive_organopathy")).lower()
    if cong_org.startswith("ja"):
        tail.append("Hinweis auf congestive Organopathie: ja")
    elif cong_org.startswith("nein"):
        tail.append("Hinweis auf congestive Organopathie: nein")

    flow = "; ".join(lab_items) if lab_items else "Keine Laborwerte erfasst."
    section = "### Labor\n" + flow
    if tail:
        section += "\n\n" + "\n".join(tail)
    return section


def _summary_echo_ui_bits(ui: Dict[str, Any]) -> List[str]:
    bits: List[str] = []
    numeric_defs = [
        ("lvef", "LVEF", 0, "%"),
        ("ee_ratio", "E/e'", 1, ""),
        ("pasp_echo", "sPAP", 0, "mmHg"),
        ("tapse_mm", "TAPSE", 0, "mm"),
        ("s_prime_cm_s", "S'", 1, "cm/s"),
        ("ra_esa_cm2", "RA ESA", 0, "cm²"),
        ("ivc_diam_mm", "IVC", 0, "mm"),
    ]
    for key, label, digits, unit in numeric_defs:
        val = _safe_float_echo(ui.get(key))
        if val is None:
            continue
        unit_txt = f" {unit}" if unit else ""
        bits.append(f"{label} {_fmt(val,digits)}{unit_txt}")

    if ui.get("la_enlarged"):
        bits.append("LA erweitert")
    ivcc = _summary_clean_text(ui.get("ivc_collapse"))
    if ivcc:
        bits.append(f"IVC Kollaps: {ivcc}")
    return bits


def _summary_echo_derived_bits(der: Dict[str, Any]) -> List[str]:
    bits: List[str] = []
    for key, label, digits in (
        ("tapse_spap", "TAPSE/sPAP", 2),
        ("raai", "RAAI", 1),
        ("s_prime_raai", "S'/RAAI", 2),
    ):
        val = der.get(key)
        if val is None:
            continue
        suffix = " cm²/m²" if key == "raai" else ""
        bits.append(f"{label} {_fmt(val,digits)}{suffix}")
    return bits


def _summary_echo_bits(ui: Dict[str, Any], der: Dict[str, Any]) -> List[str]:
    return _summary_echo_ui_bits(ui) + _summary_echo_derived_bits(der)


def _summary_echo_flag_bits(der: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    if der.get("s_prime_raai_low") is True:
        flags.append("S'/RAAI erniedrigt (<0,81)")
    if der.get("tapse_spap_reduced") is True:
        lbl = "TAPSE/sPAP vermindert"
        if der.get("tapse_spap_risk") == "hoch":
            lbl += " (hochgradig)"
        elif der.get("tapse_spap_risk") == "intermediär":
            lbl += " (mäßig)"
        flags.append(lbl)
    return flags


def _summary_cmr_bits(case: CaseLike, ui: Dict[str, Any]) -> List[str]:
    bits: List[str] = []
    rvef = _safe_float(ui.get("rvef"))
    if rvef is not None:
        bits.append(f"RVEF {_fmt(rvef,0)}%")

    rvedv = _safe_float(ui.get("rvedv"))
    rvesv = _safe_float(ui.get("rvesv"))
    rvedvi = _safe_float(ui.get("rvedvi"))
    rvesvi = _safe_float(ui.get("rvesvi"))
    if rvedv is not None and rvedv <= 0:
        rvedv = None
    if rvesv is not None and rvesv <= 0:
        rvesv = None

    bsa = _safe_float((_section(case, K_DERIVED)).get("bsa_m2"))
    if rvedvi is None and rvedv is not None and bsa is not None and bsa > 0:
        rvedvi = rvedv / bsa
    if rvesvi is None and rvesv is not None and bsa is not None and bsa > 0:
        rvesvi = rvesv / bsa

    if rvedv is not None:
        bits.append(f"RVEDV {_fmt(rvedv,0)} ml")
    if rvesv is not None:
        bits.append(f"RVESV {_fmt(rvesv,0)} ml")
    if rvedvi is not None:
        bits.append(f"RVEDVi {_fmt(rvedvi,0)} ml/m²")
    if rvesvi is not None:
        bits.append(f"RVESVi {_fmt(rvesvi,0)} ml/m²")
    return bits


def _summary_ct_lines(ui: Dict[str, Any]) -> List[str]:
    if not ui.get("ct_done"):
        return [_md_kv("CT Thorax/Angio", "nicht angegeben")]

    findings = [
        lab
        for key, lab in (
            ("ct_ild", "ILD"),
            ("ct_emphysema", "Emphysem"),
            ("ct_embolie", "Embolie"),
            ("ct_mosaic", "Mosaikperfusion"),
            ("ct_koronarkalk", "Koronarkalk"),
        )
        if ui.get(key)
    ]
    ct_text = ", ".join(findings) if findings else "durchgeführt (keine pathologischen Befunde angegeben)"
    lines = [_md_kv("CT Thorax/Angio", ct_text)]
    ct_desc = _summary_clean_text(ui.get("ct_desc"))
    if ct_desc:
        lines.append(_md_kv("CT Thorax Kurzbefund", ct_desc))
    return lines


def _summary_vq_lines(ui: Dict[str, Any]) -> List[str]:
    if not ui.get("vq_done"):
        return []
    lines = [_md_kv("V/Q", "pathologisch" if ui.get("vq_defect") else "unauffällig/keine Defekte angegeben")]
    vq_desc = _summary_clean_text(ui.get("vq_desc"))
    if vq_desc:
        lines.append(_md_kv("V/Q Details", vq_desc))

    if ui.get("vq_pa_angio_done"):
        pa_desc = _summary_clean_text(ui.get("vq_pa_angio_desc"))
        lines.append(_md_kv("PA Angio", pa_desc if pa_desc else "durchgeführt"))
    if not ui.get("vq_cteph_conf_done"):
        return lines

    dt = _summary_clean_text(ui.get("vq_cteph_conf_date"))
    lines.append(_md_kv("CTEPH Konferenz", "erfolgt" + (f" ({dt})" if dt else "")))
    decision = _summary_clean_text(ui.get("vq_cteph_conf_decision"))
    if decision:
        lines.append(_md_kv("CTEPH Konferenz Beschluss", decision))
    return lines


def _summary_echo_lines(ui: Dict[str, Any], der: Dict[str, Any]) -> List[str]:
    has_echo_data = ui.get("echo_done") or any(
        ui.get(k) not in (None, "", False) for k in ("lvef", "la_enlarged", "ee_ratio", "pasp_echo")
    )
    if not has_echo_data:
        return []
    echo_bits = _summary_echo_bits(ui, der)
    lines = [_md_kv("Echo", ", ".join(echo_bits) if echo_bits else "durchgeführt (keine Details angegeben)")]
    echo_flags = _summary_echo_flag_bits(der)
    if echo_flags:
        lines.append(_md_kv("Echo Zusatz", "; ".join(echo_flags)))
    return lines


def _summary_cmr_lines(case: CaseLike, ui: Dict[str, Any]) -> List[str]:
    has_cmr_data = ui.get("cmr_done") or any(
        ui.get(k) not in (None, "", False) for k in ("rvef", "rvedv", "rvesv", "rvedvi", "rvesvi")
    )
    if not has_cmr_data:
        return []
    bits = _summary_cmr_bits(case, ui)
    return [_md_kv("CMR", ", ".join(bits) if bits else "durchgeführt (keine Details angegeben)")]


def _summary_imaging_lines(case: CaseLike) -> List[str]:
    ui = _section(case, K_UI)
    der = _section(case, K_DERIVED)
    lines: List[str] = []
    lines.extend(_summary_ct_lines(ui))
    lines.extend(_summary_vq_lines(ui))
    lines.extend(_summary_echo_lines(ui, der))
    lines.extend(_summary_cmr_lines(case, ui))

    if not lines:
        return ["Keine Bildgebung oder Echo oder CMR Angaben erfasst."]
    return lines


def _summary_lufu_section(ui: Dict[str, Any]) -> str:
    if not ui.get("lufu_done"):
        return "### Lungenfunktion\nKeine Lungenfunktion erfasst."

    phen = [txt for key, txt in (
        ("lufu_obstructive", "obstruktiv"),
        ("lufu_restrictive", "restriktiv"),
        ("lufu_diffusion", "Diffusionsstörung"),
    ) if ui.get(key)]

    items: List[str] = []
    if phen:
        items.append("Phänotyp: " + ", ".join(phen))

    for key, label in (
        ("fev1_l", "FEV1"),
        ("fvc_l", "FVC"),
        ("dlco_sb", "DLCO"),
        ("dlco_va", "DLCO/VA"),
        ("residual_volume_l", "Residualvolumen (RV)"),
    ):
        val = _safe_float(ui.get(key))
        if val is not None:
            items.append(f"{label}: {_fmt(val,0)} %")

    flow = "; ".join(items) if items else "Lungenfunktion durchgeführt (Details nicht angegeben)."
    section = "### Lungenfunktion\n" + flow
    comment = _summary_clean_text(ui.get("lufu_summary"))
    if comment:
        section += "\n\n**Kommentar:** " + comment
    return section


def _summary_cpet_add_metric(
    items: List[str],
    ui: Dict[str, Any],
    *,
    key: str,
    label: str,
    digits: int,
    unit: str = "",
    min_value: Optional[float] = None,
) -> None:
    val = _safe_float(ui.get(key))
    if val is None:
        return
    if min_value is not None and val <= min_value:
        return
    unit_txt = f" {unit}" if unit else ""
    items.append(f"{label}: {_fmt(val, digits)}{unit_txt}")


def _summary_cpet_rr_items(ui: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    rr_peak_sys = _safe_float(ui.get("cpet_bp_sys_peak"))
    rr_peak_dia = _safe_float(ui.get("cpet_bp_dia_peak"))
    if rr_peak_sys is not None and rr_peak_dia is not None:
        items.append(f"RR Peak: {_fmt(rr_peak_sys,0)}/{_fmt(rr_peak_dia,0)} mmHg")

    rr_rest_sys = _safe_float(ui.get("cpet_bp_sys_rest"))
    rr_rest_dia = _safe_float(ui.get("cpet_bp_dia_rest"))
    if rr_rest_sys is not None and rr_rest_dia is not None:
        items.append(f"RR Ruhe: {_fmt(rr_rest_sys,0)}/{_fmt(rr_rest_dia,0)} mmHg")
    return items


def _summary_cpet_symptom_items(ui: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    if bool(ui.get("cpet_angina")):
        items.append("Symptom: Angina")
    if bool(ui.get("cpet_dizziness")):
        items.append("Symptom: Schwindel/Präsynkope")
    if bool(ui.get("cpet_syncope")):
        items.append("Symptom: Synkope")
    if bool(ui.get("cpet_arrhythmia")):
        arr_txt = _summary_clean_text(ui.get("cpet_arrhythmia_text"))
        items.append("Arrhythmie" + (f" ({arr_txt})" if arr_txt else ""))
    return items


def _summary_cpet_items(ui: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    metric_defs = [
        ("cpet_peak_vo2_ml_kg_min", "V'O2max/kg", 1, "mL/min/kg", None),
        ("cpet_peak_vo2_ml_min", "V'O2 Peak", 0, "mL/min", None),
        ("cpet_peak_vo2_pct_pred", "V'O2 Peak", 0, "% Soll", None),
        ("cpet_ve_vco2_slope", "V'E/V'CO2 Slope (VECO2s)", 1, "", None),
        ("cpet_petco2_vt1_mmhg", "PETCO2 VT1", 0, "mmHg", None),
        ("cpet_ve_vco2_vt1", "VE/VCO2@VT1", 1, "", None),
        ("cpet_peak_o2_pulse_pct_pred", "Peak O2-Puls", 0, "% Soll", None),
        ("cpet_vo2_wr_slope_ml_min_w", "VO2Ws (ΔV'O2/ΔW)", 2, "mL/min/W", None),
        ("cpet_vo2_vt1_ml_kg_min", "V'O2 VT1", 1, "mL/min/kg", None),
        ("cpet_vo2_vt1_ml_min", "V'O2 VT1", 0, "mL/min", None),
        ("cpet_vo2_vt2_ml_min", "V'O2 VT2", 0, "mL/min", None),
        ("cpet_spo2_nadir_pct", "SpO2 Nadir", 0, "%", None),
        ("cpet_spo2_rest_pct", "SpO2 Ruhe", 0, "%", None),
        ("cpet_spo2_peak_pct", "SpO2 Peak", 0, "%", None),
        ("cpet_o2_supp_l_min", "O2 während CPET", 1, "L/min", 0),
        ("cpet_rer_peak", "RER Peak", 2, "", None),
        ("cpet_hr_peak_bpm", "HF Peak", 0, "1/min", None),
        ("cpet_hr_pct_pred", "HF Peak", 0, "% Soll", None),
        ("cpet_peak_o2_pulse_ml", "O2Puls Peak", 1, "mL", None),
        ("cpet_o2_pulse_slope", "O2Puls Slope", 2, "", None),
        ("cpet_petco2_rest_mmhg", "PETCO2 Ruhe", 0, "mmHg", None),
        ("cpet_petco2_peak_mmhg", "PETCO2 Peak", 0, "mmHg", None),
        ("cpet_breathing_reserve_pct", "Atemreserve", 0, "%", None),
    ]
    for key, label, digits, unit, min_value in metric_defs:
        _summary_cpet_add_metric(
            items,
            ui,
            key=key,
            label=label,
            digits=digits,
            unit=unit,
            min_value=min_value,
        )

    pattern = _summary_clean_text(ui.get("cpet_o2_pulse_pattern"))
    if pattern:
        items.append(f"O2Puls Verlauf: {pattern}")
    items.extend(_summary_cpet_rr_items(ui))
    items.extend(_summary_cpet_symptom_items(ui))
    st_changes = _summary_clean_text(ui.get("cpet_st_changes"))
    if st_changes and st_changes.lower() not in {"keine", "none"}:
        items.append(f"ST/T: {st_changes}")
    stop_reason = _summary_clean_text(ui.get("cpet_stop_reason"))
    if stop_reason:
        items.append(f"Abbruchgrund: {stop_reason}")
    return items


def _summary_cpet_predicted_line(res: Any) -> str:
    """Format the Wasserman/Tanaka predicted-value summary line.

    Returns an empty string if no predicted data is available on the Spiro
    result (older cases, missing anthropometrics, etc.).
    """
    if res is None:
        return ""
    predicted = getattr(res, "predicted", None)
    ci = getattr(res, "chronotropic_index", None)
    if predicted is None and ci is None:
        return ""
    parts: List[str] = []
    if predicted is not None:
        vo2_rel = getattr(predicted, "vo2_peak_ml_kg_min", None)
        if vo2_rel is not None:
            parts.append(f"V'O2peak Soll {vo2_rel:.1f} mL/min/kg")
        hr_max = getattr(predicted, "hr_max_bpm", None)
        if hr_max is not None:
            parts.append(f"HF max Soll {hr_max:.0f} bpm (Tanaka)")
        o2p = getattr(predicted, "o2_pulse_peak_ml", None)
        if o2p is not None:
            parts.append(f"O2-Puls Soll {o2p:.1f} mL")
    if ci is not None:
        ci_label = "adäquat" if ci >= 0.80 else "reduziert"
        parts.append(f"Chronotroper Index {ci:.2f} ({ci_label})")
    if not parts:
        return ""
    return "**Sollwerte:** " + "; ".join(parts) + "."


def _summary_cpet_section(ui: Dict[str, Any]) -> str:
    if not ui.get("cpet_done"):
        return ""

    items = _summary_cpet_items(ui)
    flow = "; ".join(items) if items else "CPET durchgeführt (Details nicht angegeben)."
    section = "### Spiroergometrie / CPET\n" + flow

    comment = _summary_clean_text(ui.get("cpet_summary"))
    if comment:
        section += "\n\n**Kommentar:** " + comment

    # Always surface a short clinical CPET interpretation (headline + summary)
    # so the doctor report does not read as a raw value dump. The full
    # ``report_text`` block stays gated behind ``cpet_spiro_in_report`` to avoid
    # doubling the CPET block when the user explicitly requests the long form.
    try:
        import spiro_logic as _spiro
        res = _spiro.analyze(dict(ui))
    except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_REP_CPET_SPIRO_SUMMARY", "Spiro-Logic short interpretation unavailable.", exc)
        res = None

    if res:
        predicted_line = _summary_cpet_predicted_line(res)
        if predicted_line:
            section += "\n\n" + predicted_line

        short_bits: List[str] = []
        headline = str(getattr(res, "headline", "") or "").strip()
        clinical = str(getattr(res, "clinical_summary", "") or "").strip()
        if headline:
            short_bits.append(f"**Interpretation:** {headline}")
        if clinical and clinical != headline:
            short_bits.append(clinical)
        if short_bits:
            section += "\n\n" + "\n".join(short_bits)

        if bool(ui.get("cpet_spiro_in_report")):
            report_text = str(getattr(res, "report_text", "") or "").strip()
            if report_text and report_text not in section:
                section += "\n\n**Spiro-Logic Interpretation:**\n" + report_text
    return section


def summarize_inputs(case: CaseLike, *, mode: str = "default") -> str:
    """Creates a compact, structured overview of the raw input data (Markdown)."""
    ui = _section(case, K_UI)
    der = _section(case, K_DERIVED)
    is_doctor = (mode == "doctor")

    # Always emit real Markdown headings for the doctor report so the hierarchy is
    # consistent (### everywhere). The legacy colon-suffixed pseudo-headings
    # ("Klinik:", "Bildgebung / Echo / CMR:") were inconsistent with the already
    # ###-style Labor / Lungenfunktion / CPET sections below and broke heading
    # navigation in DOCX exports and in Markdown viewers.
    parts: List[str] = [
        _md_section("Anamnese und Klinik", _summary_klinik_lines(case, is_doctor=is_doctor), add_colon=False),
        _summary_labor_section(ui, der),
        _md_section("Bildgebung, Echo und CMR", _summary_imaging_lines(case), add_colon=False),
        _summary_lufu_section(ui),
    ]

    cpet_section = _summary_cpet_section(ui)
    if cpet_section:
        parts.append(cpet_section)

    return "\n\n".join([p for p in parts if p]).strip()

