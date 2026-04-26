#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_ui_render_summary.py - UI-Renderer: Sticky Summary, Verlauf, Pre-Cath Header (clean separation)
"""HTML renderers for high-frequency UI elements.

These renderers are used on almost every interaction; they must be fast and fail-safe.
"""

from __future__ import annotations

import datetime as _dt
import functools
import json
from typing import Any, Dict, List, Optional, Tuple

from rhk_config import WARNING_LEVEL_LABEL, WARNING_LEVEL_ORDER
from rhk_medcalc import compute_egfr
from rhk_ui_core import DataProbe, _chip, html_escape, ui_safe_render

_WARNING_LEVEL_ORDER = WARNING_LEVEL_ORDER
_WARNING_LEVEL_LABEL = WARNING_LEVEL_LABEL
_WARNING_LEVEL_ICON = {"hint": "🔵", "important": "🟡", "critical": "🔴"}
_WARNING_LEVEL_CHIP = {"hint": "rhk-schip--info", "important": "rhk-schip--warn", "critical": "rhk-schip--bad"}
_TODO_ITEM_CLASS = {"hint": "rhk-todo-item--hint", "important": "rhk-todo-item--important", "critical": "rhk-todo-item--critical"}
_CHECKLIST_CLASS = {"ok": "rhk-check-item--ok", "hint": "rhk-check-item--hint", "important": "rhk-check-item--important", "critical": "rhk-check-item--critical"}
from rhk_config import FIELD_LABELS

_FIELD_LABELS = FIELD_LABELS
_MORE_LABELS = {"critical": "kritische Punkte", "important": "wichtige Punkte", "hint": "Hinweise"}
_HEMO_CORE_FIELDS = (
    ("mpap_rest", "mPAP"),
    ("pawp_rest", "PAWP"),
    ("pvr_rest", "PVR"),
)
_ESC_MISSING_FIELD_MAP = {
    "WHO-FC": ["who_fc"],
    "6MWD": ["six_mwd_m"],
    "BNP/NT-proBNP": ["bnp_value"],
}
_PREV_HEMO_KEYS = ("prev_rap", "prev_mpap", "prev_pawp", "prev_ci", "prev_pvr")
_SUMMARY_UI_KEYS = {
    "prev_rap",
    "prev_mpap",
    "prev_pawp",
    "prev_ci",
    "prev_pvr",
    "rhk_date",
    "prev_rhk_date",
    "on_nitrates",
    "pde5_hardship",
    "pde5_hardship_desc",
    "ph_current_meds",
    "ph_new_meds",
    "creatinine_mg_dl",
    "egfr_ml_min_1_73",
    "egfr",
    "age",
    "sex",
}
_SUMMARY_DERIVED_KEYS = {
    "hemo_category",
    "rap_rest",
    "mpap_rest",
    "pawp_rest",
    "pvr_rest",
    "ci_rest",
    "ph_current_meds",
    "ph_new_meds",
    "ph_tx_episodes",
    "egfr_ml_min_1_73",
    "egfr",
}
_SUMMARY_SCORE_KEYS = {
    "esc_ers_4s",
    "esc_ers_4s_missing",
}
_SUMMARY_WARNING_KEYS = ("code", "message", "severity", "triage", "category", "suggestion", "fields")


def _warning_cache_payload(raw_warns: Any) -> Any:
    """Return a minimal warning payload with only rendering-relevant fields."""
    if not isinstance(raw_warns, list):
        return raw_warns
    out: List[Any] = []
    for item in raw_warns:
        if not isinstance(item, dict):
            out.append(item)
            continue
        slim = {k: item.get(k) for k in _SUMMARY_WARNING_KEYS if k in item}
        out.append(slim)
    return out


def _effective_raw_warnings(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]]) -> Any:
    safe_case = case if isinstance(case, dict) else {}
    safe_flags = flags if isinstance(flags, dict) else {}
    raw_warns = safe_case.get("warnings")
    flag_warns = safe_flags.get("warnings")
    if isinstance(raw_warns, list):
        # Merge runtime/flag warnings with persisted case warnings so newly
        # generated safety hints are not suppressed by older case content.
        if isinstance(flag_warns, list):
            return list(raw_warns) + list(flag_warns)
        return list(raw_warns)
    if isinstance(flag_warns, list):
        return list(flag_warns)
    return raw_warns


def _summary_cache_payload(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact, stable cache payload for sticky summary rendering."""
    safe_case = case if isinstance(case, dict) else None
    safe_flags = flags if isinstance(flags, dict) else {}
    effective_warns = _warning_cache_payload(_effective_raw_warnings(case, flags))
    case_payload = None
    if safe_case is not None:
        ui_src = safe_case.get("ui")
        der_src = safe_case.get("derived")
        scores_src = safe_case.get("scores")
        case_payload = {
            "ui": {k: ui_src.get(k) for k in _SUMMARY_UI_KEYS} if isinstance(ui_src, dict) else None,
            "derived": {k: der_src.get(k) for k in _SUMMARY_DERIVED_KEYS} if isinstance(der_src, dict) else None,
            "scores": {k: scores_src.get(k) for k in _SUMMARY_SCORE_KEYS} if isinstance(scores_src, dict) else None,
            "warnings": effective_warns,
        }
    return {
        "case": case_payload,
        "flags": {
            "report_stale": safe_flags.get("report_stale"),
            "generated_at": safe_flags.get("generated_at"),
            "dirty": safe_flags.get("dirty"),
            "saved_at": safe_flags.get("saved_at"),
            # Effective warnings are stored in case.warnings for cache stability.
            "warnings": None,
        },
    }


@functools.lru_cache(maxsize=128)
def _build_sticky_summary_html_cached(payload_json: str) -> str:
    payload = json.loads(payload_json)
    return _build_sticky_summary_html_impl(payload.get("case"), payload.get("flags"))


def _format_ts_short(ts: Any) -> Tuple[str, str]:
    s = str(ts or "").strip()
    if not s:
        return "", ""
    try:
        dt = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return "", s
    return dt.strftime("%H:%M"), dt.strftime("%d.%m.%Y %H:%M")


def _parse_date_any(value: Any) -> Optional[_dt.datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d.%m.%Y", "%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _has_prev_hemo_values(ui: DataProbe) -> bool:
    """Return True only when at least one previous hemo value is numerically present."""
    return any(ui.float(key) is not None for key in _PREV_HEMO_KEYS)


def _warning_level(item: Dict[str, Any]) -> str:
    triage = str(item.get("triage") or "").strip().lower()
    if triage in _WARNING_LEVEL_ORDER:
        return triage
    sev = str(item.get("severity") or "").strip().lower()
    if sev == "error":
        return "critical"
    if sev == "warn":
        return "important"
    return "hint"


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, tuple):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, set):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    return [v]


_BOOL_TRUE_STRINGS = {"1", "true", "t", "yes", "y", "ja", "j", "on", "aktiv", "active"}
_BOOL_FALSE_STRINGS = {"0", "false", "f", "no", "n", "nein", "off", "inaktiv", "inactive"}


def _as_bool_flag(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v) != 0.0
    if isinstance(v, str):
        token = v.strip().lower()
        if not token:
            return False
        if token in _BOOL_TRUE_STRINGS:
            return True
        if token in _BOOL_FALSE_STRINGS:
            return False
    return bool(v)


def _med_tokens(case: Dict[str, Any]) -> List[str]:
    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    vals: List[str] = []
    for src in (
        der.get("ph_current_meds"),
        der.get("ph_new_meds"),
        ui.get("ph_current_meds"),
        ui.get("ph_new_meds"),
    ):
        vals.extend([str(x).strip().lower() for x in _as_list(src) if str(x).strip()])
    episodes = der.get("ph_tx_episodes")
    if isinstance(episodes, list):
        for ep in episodes:
            if not isinstance(ep, dict):
                continue
            st = str(ep.get("status") or "").strip().lower()
            if st in {"abgesetzt", "früher"}:
                continue
            drug = str(ep.get("drug") or "").strip().lower()
            if drug:
                vals.append(drug)
    return vals


def _field_label(name: str) -> str:
    key = str(name or "").strip()
    if not key:
        return ""
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key]
    return key.replace("_", " ")


def _missing_hemo_fields_detail(der: DataProbe) -> List[Tuple[str, str]]:
    missing = []
    for key, label in _HEMO_CORE_FIELDS:
        if der.float(key) is None:
            missing.append((key, label))
    return missing


def _missing_hemo_fields(der: DataProbe) -> List[str]:
    return [label for _, label in _missing_hemo_fields_detail(der)]


def _hemo_trend_chip(ui: DataProbe, der: DataProbe) -> Optional[Tuple[str, str, str]]:
    """Return a compact trend chip (label, tone, tooltip) from prev vs current hemodynamics."""
    metrics = [
        ("mPAP", ui.float("prev_mpap"), der.float("mpap_rest"), 2.0, -1.0),
        ("PVR", ui.float("prev_pvr"), der.float("pvr_rest"), 0.5, -1.0),
        ("CI", ui.float("prev_ci"), der.float("ci_rest"), 0.2, +1.0),
    ]
    improved: List[str] = []
    worsened: List[str] = []
    stable: List[str] = []

    for label, prev_val, curr_val, threshold, beneficial_sign in metrics:
        if prev_val is None or curr_val is None:
            continue
        delta = curr_val - prev_val
        if abs(delta) < threshold:
            stable.append(label)
            continue
        signed = delta * beneficial_sign
        if signed > 0:
            improved.append(label)
        else:
            worsened.append(label)

    compared = len(improved) + len(worsened) + len(stable)
    if compared == 0:
        return None

    details: List[str] = []
    if improved:
        details.append(f"besser: {', '.join(improved)}")
    if worsened:
        details.append(f"schlechter: {', '.join(worsened)}")
    if stable:
        details.append(f"stabil: {', '.join(stable)}")
    tooltip = " | ".join(details)

    if worsened and not improved:
        return ("Verlauf: schlechter", "rhk-schip--bad", tooltip)
    if improved and not worsened:
        return ("Verlauf: besser", "rhk-schip--good", tooltip)
    if improved and worsened:
        return ("Verlauf: gemischt", "rhk-schip--orange", tooltip)
    return ("Verlauf: stabil", "rhk-schip--info", tooltip)


def _normalize_warning_items(raw_warns: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_warns, list):
        return out
    for idx, w in enumerate(raw_warns):
        if isinstance(w, dict):
            msg = str(w.get("message") or "").strip()
            if not msg:
                msg = str(w.get("code") or "").strip()
            if not msg:
                continue
            fields = [str(f).strip() for f in _as_list(w.get("fields")) if str(f).strip()]
            item = {
                "id": str(w.get("code") or f"w_{idx}"),
                "message": msg,
                "severity": str(w.get("severity") or "").strip().lower(),
                "triage": _warning_level(w),
                "category": str(w.get("category") or "").strip().lower(),
                "suggestion": str(w.get("suggestion") or "").strip(),
                "fields": fields,
            }
            out.append(item)
        else:
            msg = str(w).strip()
            if msg:
                out.append({
                    "id": f"w_{idx}",
                    "message": msg,
                    "severity": "warn",
                    "triage": "important",
                    "category": "plausibility",
                    "suggestion": "",
                    "fields": [],
                })
    return out


def _warning_dedupe_key(item: Dict[str, Any]) -> Tuple[str, str, str]:
    wid = str(item.get("id") or "").strip().lower()
    msg = str(item.get("message") or "").strip().lower()
    cat = str(item.get("category") or "").strip().lower()
    if wid and not wid.startswith("w_"):
        return ("id", wid, cat)
    return ("msg", cat, msg)


def _dedupe_warning_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str, str]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        key = _warning_dedupe_key(item)
        if key not in merged:
            item["triage"] = _warning_level(item)
            item["fields"] = [str(f).strip() for f in _as_list(item.get("fields")) if str(f).strip()]
            merged[key] = item
            order.append(key)
            continue
        cur = merged[key]
        cur_lvl = _warning_level(cur)
        new_lvl = _warning_level(item)
        if _WARNING_LEVEL_ORDER.get(new_lvl, 0) > _WARNING_LEVEL_ORDER.get(cur_lvl, 0):
            cur["triage"] = new_lvl
            cur["severity"] = str(item.get("severity") or cur.get("severity") or "").strip().lower()
        for f in _as_list(item.get("fields")):
            fs = str(f).strip()
            if fs and fs not in cur.get("fields", []):
                cur.setdefault("fields", []).append(fs)
        if not str(cur.get("suggestion") or "").strip():
            cur["suggestion"] = str(item.get("suggestion") or "").strip()
    return [merged[k] for k in order]


def _render_warning_item_html(item: Dict[str, Any]) -> str:
    triage = str(item.get("triage") or "hint")
    row_cls = _TODO_ITEM_CLASS.get(triage, _TODO_ITEM_CLASS["hint"])
    msg = html_escape(item.get("message") or "")
    meta_bits: List[str] = []
    fields = [x for x in _as_list(item.get("fields")) if str(x).strip()]
    if fields:
        shown = ", ".join([_field_label(str(f)) for f in fields[:3]])
        if len(fields) > 3:
            shown += f" (+{len(fields)-3})"
        meta_bits.append(f"Feld: {html_escape(shown)}")
    sug = str(item.get("suggestion") or "").strip()
    if sug:
        meta_bits.append(f"Vorschlag: {html_escape(sug)}")
    meta = ""
    if meta_bits:
        meta = f"<div class='rhk-todo-meta'>{' | '.join(meta_bits)}</div>"
    return f"<li class='{row_cls}'><div class='rhk-todo-item-title'>{msg}</div>{meta}</li>"


def _render_more_item_html(count: int, triage: str) -> str:
    if count <= 0:
        return ""
    row_cls = _TODO_ITEM_CLASS.get(triage, _TODO_ITEM_CLASS["hint"])
    label = _MORE_LABELS.get(triage, "Hinweise")
    msg = html_escape(f"Weitere {count} {label}")
    return f"<li class='{row_cls}'><div class='rhk-todo-item-title'>{msg}</div></li>"


def _build_interaction_checklist(case: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    ui = case.get("ui") or {}
    meds = _med_tokens(case)
    has_pde5 = any(("pde-5" in m) or ("sildenafil" in m) or ("tadalafil" in m) for m in meds)
    has_sgc = any(("sgc" in m) or ("riociguat" in m) or ("adempas" in m) for m in meds)
    on_nitrates = _as_bool_flag(ui.get("on_nitrates"))
    hardship = _as_bool_flag(ui.get("pde5_hardship"))
    hardship_desc = str(ui.get("pde5_hardship_desc") or "").strip()

    checks: List[Tuple[str, str, str]] = []
    if on_nitrates and (has_pde5 or has_sgc):
        checks.append(("critical", "Nitrate/NO-Donor + PDE-5/sGC", "Kontraindikation: Medikation sofort prüfen."))
    else:
        checks.append(("ok", "Nitrate/NO-Donor + PDE-5/sGC", "Keine harte Kontraindikation erkannt."))

    if has_pde5 and has_sgc:
        checks.append(("critical", "PDE-5 + Riociguat", "Kontraindikation: Kombination nicht gleichzeitig führen."))
    elif has_pde5 or has_sgc:
        checks.append(("ok", "PDE-5/Riociguat Doppelcheck", "Nur ein vasodilatierender Pfad aktiv erfasst."))
    else:
        checks.append(("hint", "PDE-5/Riociguat Doppelcheck", "Keine aktive PDE-5/sGC-Therapie dokumentiert."))

    if hardship and not hardship_desc:
        checks.append(("important", "Off-Label/Härtefall", "Härtefall aktiv, Begründung fehlt."))
    elif hardship and hardship_desc:
        checks.append(("ok", "Off-Label/Härtefall", "Begründung dokumentiert."))
    else:
        checks.append(("hint", "Off-Label/Härtefall", "Nicht aktiviert."))

    return checks


def _prioritized_todo_counts(
    case: Dict[str, Any],
    warns: List[Dict[str, Any]],
    extras: Optional[List[Dict[str, Any]]] = None,
    *,
    warns_are_deduped: bool = False,
) -> Tuple[int, int]:
    all_warns = list(warns)
    if extras:
        all_warns.extend([ex for ex in extras if isinstance(ex, dict)])
    if not warns_are_deduped:
        all_warns = _dedupe_warning_items(all_warns)

    critical_count = 0
    important_count = 0
    for w in all_warns:
        lvl = _warning_level(w)
        cat = str(w.get("category") or "").strip().lower()
        if cat == "measurement_quality" and lvl not in {"critical", "important"}:
            continue
        if lvl == "critical":
            critical_count += 1
        elif lvl == "important":
            important_count += 1

    for state, _label, _detail in _build_interaction_checklist(case):
        if state == "critical":
            critical_count += 1
        elif state == "important":
            important_count += 1

    return critical_count, important_count


def _render_todo_card(
    case: Dict[str, Any],
    warns: List[Dict[str, Any]],
    extras: Optional[List[Dict[str, Any]]] = None,
    *,
    warns_are_deduped: bool = False,
) -> str:
    all_warns = list(warns)
    if extras:
        all_warns.extend([ex for ex in extras if isinstance(ex, dict)])
    if not warns_are_deduped:
        all_warns = _dedupe_warning_items(all_warns)
    by_level: Dict[str, List[Dict[str, Any]]] = {"critical": [], "important": [], "hint": []}
    quality_items: List[Dict[str, Any]] = []
    for w in all_warns:
        lvl = _warning_level(w)
        cat = str(w.get("category") or "").strip().lower()
        if cat == "measurement_quality":
            # Prioritize clinically relevant measurement quality issues directly in
            # the triage columns. Keep only low-priority quality hints in the
            # dedicated consistency section to reduce noise.
            if lvl in {"critical", "important"}:
                by_level.setdefault(lvl, []).append(w)
            else:
                quality_items.append(w)
            continue
        by_level.setdefault(lvl, []).append(w)

    def _sort_key(x: Dict[str, Any]) -> Tuple[int, str]:
        return (-_WARNING_LEVEL_ORDER.get(_warning_level(x), 0), str(x.get("id") or ""))

    quality_items = sorted(quality_items, key=_sort_key)
    quality_html = "<div class='rhk-todo-empty'>Keine zusätzlichen Hinweise aus den aktiven Konsistenzchecks.</div>"
    if quality_items:
        shown = quality_items[:4]
        more_count = len(quality_items) - len(shown)
        quality_html = "<ul class='rhk-todo-list'>" + "".join([_render_warning_item_html(w) for w in shown])
        if more_count > 0:
            quality_html += _render_more_item_html(more_count, "hint")
        quality_html += "</ul>"

    level_cols: List[str] = []
    for lvl in ("critical", "important", "hint"):
        group = sorted(by_level.get(lvl) or [], key=_sort_key)
        icon = _WARNING_LEVEL_ICON[lvl]
        label = _WARNING_LEVEL_LABEL[lvl]
        if group:
            shown = group[:3]
            more_count = len(group) - len(shown)
            body = "<ul class='rhk-todo-list'>" + "".join([_render_warning_item_html(w) for w in shown])
            if more_count > 0:
                body += _render_more_item_html(more_count, lvl)
            body += "</ul>"
        else:
            body = "<div class='rhk-todo-empty'>keine</div>"
        level_cols.append(
            "<div class='rhk-todo-col'>"
            f"<div class='rhk-todo-col-head'>{icon} {label} ({len(group)})</div>"
            f"{body}"
            "</div>"
        )

    checks = _build_interaction_checklist(case)
    check_lines = []
    for state, label, detail in checks:
        ccls = _CHECKLIST_CLASS.get(state, _CHECKLIST_CLASS["hint"])
        check_lines.append(
            "<li class='rhk-check-item {cls}'>"
            "<span class='rhk-check-title'>{lab}</span>"
            "<span class='rhk-check-detail'>{det}</span>"
            "</li>".format(
                cls=html_escape(ccls),
                lab=html_escape(label),
                det=html_escape(detail),
            )
        )

    return (
        "<div class='rhk-safety-todo'>"
        "<div class='rhk-todo-head'>Klinische Sicherheit / To-Do</div>"
        "<div class='rhk-todo-grid'>"
        + "".join(level_cols)
        + "</div>"
        "<div class='rhk-todo-subhead'>Messqualität / Konsistenz (zusätzliche Hinweise)</div>"
        + quality_html
        + "<div class='rhk-todo-subhead'>Interaktions-Checkliste</div>"
        + "<ul class='rhk-check-list'>"
        + "".join(check_lines)
        + "</ul>"
        + "</div>"
    )


def _marker_payload(
    warns: List[Dict[str, Any]],
    extras: Optional[List[Dict[str, Any]]] = None,
    *,
    warns_are_deduped: bool = False,
) -> Dict[str, Dict[str, str]]:
    if not warns_are_deduped:
        warns = _dedupe_warning_items(warns)
    agg: Dict[str, Dict[str, Any]] = {}

    def _add_marker(fields: Any, level: str, message: str) -> None:
        lvl = str(level or "hint").strip().lower() or "hint"
        msg = str(message or "").strip()
        for f in _as_list(fields):
            key = str(f or "").strip()
            if not key:
                continue
            entry = agg.get(key)
            if not entry:
                entry = {"level": lvl, "messages": []}
                agg[key] = entry
            if _WARNING_LEVEL_ORDER.get(lvl, 0) > _WARNING_LEVEL_ORDER.get(entry.get("level", "hint"), 0):
                entry["level"] = lvl
            if msg and msg not in entry["messages"]:
                entry["messages"].append(msg)

    for w in warns:
        _add_marker(w.get("fields"), _warning_level(w), str(w.get("message") or ""))

    if extras:
        for ex in extras:
            _add_marker(ex.get("fields"), ex.get("level") or "hint", str(ex.get("message") or ""))

    payload: Dict[str, Dict[str, str]] = {}
    for key, entry in agg.items():
        lvl = entry.get("level", "hint")
        msgs = [str(x) for x in entry.get("messages") or [] if str(x).strip()]
        if msgs:
            shown = " • ".join(msgs[:3])
            if len(msgs) > 3:
                shown += f" (+{len(msgs)-3})"
            title = f"{_WARNING_LEVEL_ICON.get(lvl, '•')} {_WARNING_LEVEL_LABEL.get(lvl, 'Hinweis')}: {shown}"
        else:
            title = f"{_WARNING_LEVEL_ICON.get(lvl, '•')} {_WARNING_LEVEL_LABEL.get(lvl, 'Hinweis')}"
        payload[key] = {"level": lvl, "title": title}

    return payload


@ui_safe_render(fallback="<div class='rhk-error'>Summary Render Error</div>")
def build_sticky_summary_html(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]] = None) -> str:
    payload = _summary_cache_payload(case, flags)
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    except Exception:
        return _build_sticky_summary_html_impl(case, flags)
    return _build_sticky_summary_html_cached(payload_json)


def _build_sticky_summary_html_impl(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]] = None) -> str:
    """Concise, always-visible live preview of key values."""
    if not case:
        status_chips = []
        if flags:
            if flags.get("dirty"):
                status_chips.append(_chip("Ungespeichert", "rhk-schip--warn"))
            elif flags.get("saved_at"):
                disp, full = _format_ts_short(flags.get("saved_at"))
                label = "Gespeichert" if not disp else f"Gespeichert {disp}"
                status_chips.append(_chip(label, "rhk-schip--good", f"Stand: {full}" if full else ""))
        if not status_chips:
            # Hide completely when there is no case and no save-state to show.
            return ""
        return (
            "<div class='rhk-summarybar' role='status' aria-label='Hämodynamik-Zusammenfassung'>"
            f"{''.join(status_chips)}"
            "</div>"
        )

    ui = DataProbe(case.get("ui"))
    der = DataProbe(case.get("derived"))
    scores = DataProbe(case.get("scores"))

    cat_map = {
        "precap": "Prä-kapillär",
        "ipcph": "iPcPH",
        "cpcph": "cPcPH",
        "no_ph": "Keine PH",
        "ph_unclassified": "PH unklassifiziert",
        "high_flow_or_borderline": "High-Flow/nicht-präkapillär",
        "unknown": "Unklar",
    }
    hemo_cat = der.str("hemo_category") or "unknown"
    hemo_txt = cat_map.get(hemo_cat, hemo_cat)

    vals = [
        _chip(f"Hämo: {hemo_txt}", "rhk-schip--info"),
        _chip(f"RAP: {der.fmt('rap_rest', nd=0)}"),
        _chip(f"mPAP: {der.fmt('mpap_rest', nd=0)}"),
        _chip(f"PAWP: {der.fmt('pawp_rest', nd=0)}"),
        _chip(f"PVR: {der.fmt('pvr_rest', nd=1)}"),
        _chip(f"CI: {der.fmt('ci_rest', nd=2)}"),
    ]

    missing_hemo_detail = _missing_hemo_fields_detail(der)
    missing_hemo = [label for _, label in missing_hemo_detail]
    if missing_hemo and hemo_cat in {"unknown", "ph_unclassified"}:
        vals.append(
            _chip(
                "Hämo unvollständig",
                "rhk-schip--warn",
                f"Fehlt: {', '.join(missing_hemo)}",
            )
        )

    # Risk Scores (ESC/ERS)
    esc4 = scores.str("esc_ers_4s")
    esc_missing: List[str] = []
    if esc4:
        tone = "rhk-schip--good" if esc4 == "low" else ("rhk-schip--bad" if esc4 == "high" else "rhk-schip--orange")
        vals.append(_chip(f"Risk: {esc4}", tone))
    else:
        esc_missing = [str(x).strip() for x in _as_list(scores.get("esc_ers_4s_missing")) if str(x).strip()]
        if esc_missing:
            vals.append(_chip("ESC/ERS unvollständig", "rhk-schip--warn", f"Fehlt: {', '.join(esc_missing)}"))

    # Deltas (Comparison)
    curr_mpap = der.float("mpap_rest")
    prev_mpap = ui.float("prev_mpap")
    if curr_mpap is not None and prev_mpap is not None:
        diff = curr_mpap - prev_mpap
        arrow = "↑" if diff > 1 else ("↓" if diff < -1 else "→")
        vals.append(_chip(f"ΔmPAP {arrow}{abs(diff):.0f}", "rhk-schip--info"))
    trend_chip = _hemo_trend_chip(ui, der)
    if trend_chip:
        vals.append(_chip(trend_chip[0], trend_chip[1], trend_chip[2]))

    hemo_present = any(
        der.float(key) is not None
        for key in ("rap_rest", "mpap_rest", "pawp_rest", "pvr_rest", "ci_rest")
    )
    date_curr = ui.str("rhk_date")
    if hemo_present and not date_curr:
        vals.append(_chip("RHK-Datum fehlt", "rhk-schip--warn", "Datum der aktuellen RHK ergänzen."))

    prev_present = _has_prev_hemo_values(ui)
    date_prev = ui.str("prev_rhk_date")
    if prev_present and not date_prev:
        vals.append(_chip("Vorwerte ohne Datum", "rhk-schip--warn", "Datum der Voruntersuchung ergänzen."))

    # Kidney function snapshot (relevant for contrast/medication planning)
    renal_crea = ui.float("creatinine_mg_dl")
    renal_age = ui.get("age")
    renal_sex = ui.get("sex")
    has_age = ui.float("age") is not None
    has_sex = bool(ui.str("sex"))
    egfr_val: Optional[float] = None
    egfr_stage = ""
    if has_age and has_sex:
        egfr_val, egfr_stage = compute_egfr(renal_crea, renal_age, renal_sex)
    if egfr_val is None:
        egfr_val = ui.float("egfr_ml_min_1_73") or ui.float("egfr") or der.float("egfr_ml_min_1_73") or der.float("egfr")
        if egfr_val is not None:
            egfr_stage = "(Manuell)"

    renal_low_msg = ""
    renal_low_level = ""
    renal_missing_context = False
    if egfr_val is not None:
        if egfr_val >= 60:
            renal_tone = "rhk-schip--good"
        elif egfr_val >= 45:
            renal_tone = "rhk-schip--warn"
        else:
            renal_tone = "rhk-schip--bad"
        renal_label = f"eGFR {egfr_val:.0f}"
        if egfr_stage:
            renal_label += f" {egfr_stage}"
        vals.append(_chip(renal_label, renal_tone))
        if egfr_val < 45:
            renal_low_level = "critical" if egfr_val < 30 else "important"
            renal_low_msg = f"Nierenfunktion eingeschränkt (eGFR {egfr_val:.0f})"
    elif renal_crea is not None:
        missing_parts: List[str] = []
        if not has_age:
            missing_parts.append("Alter")
        if not has_sex:
            missing_parts.append("Geschlecht")
        if missing_parts:
            renal_missing_context = True
            vals.append(
                _chip(
                    "eGFR nicht berechenbar",
                    "rhk-schip--warn",
                    f"Für Berechnung fehlt: {', '.join(missing_parts)}",
                )
            )

    raw_warns = _effective_raw_warnings(case, flags)
    warns = _normalize_warning_items(raw_warns if isinstance(raw_warns, list) else [])
    warns = _dedupe_warning_items(warns)

    if warns:
        counts = {"critical": 0, "important": 0, "hint": 0}
        for w in warns:
            counts[_warning_level(w)] += 1

        if counts["critical"] > 0:
            vals.append(_chip(f"🔴 Kritisch {counts['critical']}", _WARNING_LEVEL_CHIP["critical"]))
        if counts["important"] > 0:
            vals.append(_chip(f"🟡 Wichtig {counts['important']}", _WARNING_LEVEL_CHIP["important"]))
        if counts["hint"] > 0:
            vals.append(_chip(f"🔵 Hinweis {counts['hint']}", _WARNING_LEVEL_CHIP["hint"]))

    # System Status
    if flags:
        if flags.get("report_stale"):
            vals.append(_chip("Report veraltet", "rhk-schip--warn"))
        gen_disp, gen_full = _format_ts_short(flags.get("generated_at"))
        if gen_disp:
            vals.append(_chip(f"Report {gen_disp}", "rhk-schip--info", f"Erzeugt: {gen_full}" if gen_full else ""))
        if flags.get("dirty"):
            vals.append(_chip("Ungespeichert", "rhk-schip--warn"))
        elif flags.get("saved_at"):
            disp, full = _format_ts_short(flags.get("saved_at"))
            label = "Gespeichert" if not disp else f"Gespeichert {disp}"
            vals.append(_chip(label, "rhk-schip--good", f"Stand: {full}" if full else ""))

    marker_extras: List[Dict[str, Any]] = []
    if missing_hemo and hemo_cat in {"unknown", "ph_unclassified"}:
        missing_keys = [key for key, _ in missing_hemo_detail]
        if missing_keys:
            marker_extras.append(
                {
                    "level": "important",
                    "message": f"Hämodynamik fehlt: {', '.join(missing_hemo)}",
                    "fields": missing_keys,
                }
            )

    if esc_missing:
        for label in esc_missing:
            keys = _ESC_MISSING_FIELD_MAP.get(label, [])
            if keys:
                marker_extras.append(
                    {
                        "level": "important",
                        "message": f"ESC/ERS fehlt: {label}",
                        "fields": keys,
                    }
                )

    if hemo_present and not date_curr:
        marker_extras.append(
            {
                "level": "important",
                "message": "RHK-Datum fehlt: aktuelles Untersuchungsdatum",
                "fields": ["rhk_date"],
            }
        )

    if prev_present and not date_prev:
        marker_extras.append(
            {
                "level": "important",
                "message": "Vorwerte ohne Datum: Voruntersuchung",
                "fields": ["prev_rhk_date"],
            }
        )

    if renal_low_msg:
        marker_extras.append(
            {
                "level": renal_low_level or "important",
                "message": f"{renal_low_msg} - Kontrastmittel/Medikation prüfen",
                "fields": ["egfr_ml_min_1_73", "creatinine_mg_dl"],
            }
        )

    if renal_missing_context:
        marker_extras.append(
            {
                "level": "important",
                "message": "eGFR nicht berechenbar: Alter/Geschlecht ergänzen",
                "fields": ["age", "sex", "creatinine_mg_dl"],
            }
        )

    todo_extras: List[Dict[str, Any]] = []
    if missing_hemo and hemo_cat in {"unknown", "ph_unclassified"}:
        missing_keys = [key for key, _ in missing_hemo_detail]
        todo_extras.append(
            {
                "id": "missing_hemo_core",
                "message": f"Hämodynamik unvollständig: {', '.join(missing_hemo)}",
                "triage": "important",
                "category": "data_completeness",
                "suggestion": "mPAP/PAWP/PVR ergänzen",
                "fields": missing_keys,
            }
        )

    if esc_missing:
        esc_keys: List[str] = []
        for label in esc_missing:
            esc_keys.extend(_ESC_MISSING_FIELD_MAP.get(label, []))
        todo_extras.append(
            {
                "id": "missing_esc_ers",
                "message": f"ESC/ERS unvollständig: {', '.join(esc_missing)}",
                "triage": "important",
                "category": "data_completeness",
                "suggestion": "WHO-FC/6MWD/BNP ergänzen",
                "fields": esc_keys,
            }
        )

    if hemo_present and not date_curr:
        todo_extras.append(
            {
                "id": "missing_rhk_date",
                "message": "RHK-Datum fehlt: aktuelles Untersuchungsdatum",
                "triage": "important",
                "category": "data_completeness",
                "suggestion": "RHK-Datum ergänzen",
                "fields": ["rhk_date"],
            }
        )

    if prev_present and not date_prev:
        todo_extras.append(
            {
                "id": "missing_prev_rhk_date",
                "message": "Vorwerte ohne Datum: Voruntersuchung",
                "triage": "important",
                "category": "data_completeness",
                "suggestion": "Datum der Voruntersuchung ergänzen",
                "fields": ["prev_rhk_date"],
            }
        )

    if renal_low_msg:
        todo_extras.append(
            {
                "id": "renal_function_reduced",
                "message": f"{renal_low_msg}: Kontrastmittel-/Therapieplanung prüfen",
                "triage": renal_low_level or "important",
                "category": "safety_renal",
                "suggestion": "Nieren-schonende Strategie dokumentieren",
                "fields": ["egfr_ml_min_1_73", "creatinine_mg_dl"],
            }
        )

    if renal_missing_context:
        todo_extras.append(
            {
                "id": "renal_egfr_not_computable",
                "message": "eGFR nicht berechenbar: Alter/Geschlecht fehlen",
                "triage": "important",
                "category": "data_completeness",
                "suggestion": "Alter und Geschlecht ergänzen",
                "fields": ["age", "sex", "creatinine_mg_dl"],
            }
        )

    prioritized_critical, prioritized_important = _prioritized_todo_counts(
        case,
        warns,
        todo_extras,
        warns_are_deduped=True,
    )
    prioritized_total = prioritized_critical + prioritized_important
    if prioritized_total > 0:
        level_cls = "rhk-schip--bad" if prioritized_critical > 0 else "rhk-schip--warn"
        vals.append(
            _chip(
                f"Offen: {prioritized_total} priorisiert",
                level_cls,
                f"Kritisch: {prioritized_critical}, Wichtig: {prioritized_important}",
            )
        )

    todo_html = _render_todo_card(case, warns, todo_extras, warns_are_deduped=True)
    marker_payload = _marker_payload(warns, marker_extras, warns_are_deduped=True)
    marker_json = html_escape(json.dumps(marker_payload, ensure_ascii=False))

    return (
        "<div class='rhk-summary-stack'>"
        "<div class='rhk-summarybar' role='status' aria-label='Hämodynamik-Zusammenfassung'>"
        + "".join(vals)
        + "</div>"
        + todo_html
        + f"<div class='rhk-field-marker-payload' data-markers=\"{marker_json}\" aria-hidden='true'></div>"
        + "</div>"
    )


@ui_safe_render()
def build_compare_overview_html(case: Optional[Dict[str, Any]]) -> str:
    """Comparison table (Prev vs Current)."""
    if not case:
        return ""

    ui = DataProbe(case.get("ui"))
    der = DataProbe(case.get("derived"))

    if not _has_prev_hemo_values(ui):
        return ""

    rows = [
        ("RAP (mmHg)", "prev_rap", "rap_rest", 0, 1.0),
        ("mPAP (mmHg)", "prev_mpap", "mpap_rest", 0, 2.0),
        ("PAWP (mmHg)", "prev_pawp", "pawp_rest", 0, 2.0),
        ("CI (l/min/m²)", "prev_ci", "ci_rest", 2, 0.2),
        ("PVR (WU)", "prev_pvr", "pvr_rest", 1, 0.5),
    ]

    html_rows = []
    for label, k_prev, k_curr, nd, thr in rows:
        v_prev = ui.float(k_prev)
        v_curr = der.float(k_curr)

        cell_prev = f"{v_prev:.{nd}f}" if v_prev is not None else "–"
        cell_curr = f"{v_curr:.{nd}f}" if v_curr is not None else "–"

        delta_html = "<span class='cmp-delta-flat'>–</span>"
        if v_prev is not None and v_curr is not None:
            delta = v_curr - v_prev
            cls = "cmp-delta-up" if delta > thr else ("cmp-delta-down" if delta < -thr else "cmp-delta-flat")
            sym = "↑" if delta > thr else ("↓" if delta < -thr else "±")
            html_rows.append(
                f"<tr><td>{html_escape(label)}</td><td>{cell_prev}</td><td>{cell_curr}</td><td><span class='{cls}'>{sym} {abs(delta):.{nd}f}</span></td></tr>"
            )
        else:
            html_rows.append(
                f"<tr><td>{html_escape(label)}</td><td>{cell_prev}</td><td>{cell_curr}</td><td>{delta_html}</td></tr>"
            )

    date_prev = ui.str("prev_rhk_date")
    date_curr = ui.str("rhk_date")
    gap_html = ""
    dt_prev = _parse_date_any(date_prev)
    dt_curr = _parse_date_any(date_curr)
    if dt_prev and dt_curr:
        delta_days = (dt_curr.date() - dt_prev.date()).days
        if delta_days >= 0:
            gap_html = f"<div class='cmp-note'>Abstand: {delta_days} Tage</div>"
        else:
            gap_html = f"<div class='cmp-note'>Achtung: Vorher liegt nach Aktuell ({abs(delta_days)} Tage)</div>"

    return (
        "<div class='cmp-wrap'>"
        "<div class='cmp-head'><div class='cmp-title'>Verlauf</div>" + gap_html + "</div>"
        "<table><thead><tr>"
        f"<th>Parameter</th><th>Vorher <small>{html_escape(date_prev)}</small></th>"
        f"<th>Aktuell <small>{html_escape(date_curr)}</small></th><th>Δ</th>"
        f"</tr></thead><tbody>{''.join(html_rows)}</tbody></table>"
        "</div>"
    )


@ui_safe_render()
def build_pre_cath_header_html(ui: Dict[str, Any] | None) -> str:
    """Safety Header (Ampel system) with clinical cross-checks.

    Returns an empty string when no case has been loaded yet — showing
    red/amber warnings ("Aufklärung fehlt", "Gerinnung ?") on a blank page
    trains users to ignore status chips. The bar becomes visible as soon as
    any of the relevant fields carries data.
    """
    d = DataProbe(ui)

    # Empty-state detection: no consent flag AND no lab values AND no access
    # route AND no anticoag status means the user has not entered anything
    # yet. In that case, suppress the bar entirely.
    has_any_signal = (
        d.get("consent_done") is True
        or d.get("consent_done") is False
        or d.str("access_route")
        or d.float("inr") is not None
        or d.float("ptt_s") is not None
        or d.float("platelets_g_l") is not None
        or d.str("anticoag_status")
        or d.get("anticoag_paused") is True
        or d.float("creatinine_mg_dl") is not None
        or d.float("egfr_ml_min_1_73") is not None
        or d.float("egfr") is not None
        or d.float("crp_mg_l") is not None
        or d.get("age") is not None
    )
    if not has_any_signal:
        return ""

    chips = []

    # Consent
    done = d.get("consent_done") is True
    chips.append(_chip("Aufklärung OK" if done else "Aufklärung fehlt", "rhk-schip--good" if done else "rhk-schip--bad"))

    # Access
    route = d.str("access_route")
    if route:
        chips.append(_chip(f"Zugang: {route}", "rhk-schip--info"))

    # Coagulation & anticoagulation cross-check
    inr = d.float("inr")
    ptt = d.float("ptt_s")
    thrombos = d.float("platelets_g_l")

    ac_status = d.str("anticoag_status").lower()
    ac_paused = d.get("anticoag_paused") is True
    ac_active_kw = any(k in ac_status for k in ["ja", "yes", "marcumar", "doak"]) and "nein" not in ac_status

    coag_warns = []
    if inr and inr > 1.5:
        coag_warns.append(f"INR {inr}")
    if ptt and ptt > 40:
        coag_warns.append(f"PTT {ptt}")
    if thrombos and thrombos < 100:
        coag_warns.append(f"Thrombos {thrombos}")

    if coag_warns:
        chips.append(_chip("Gerinnung (!)", "rhk-schip--warn", ", ".join(coag_warns)))
    else:
        has_data = (inr is not None or ptt is not None or thrombos is not None)
        chips.append(_chip("Gerinnung OK" if has_data else "Gerinnung ?", "rhk-schip--good" if has_data else "rhk-schip--info"))

    if not ac_active_kw:
        if inr and inr > 1.5:
            chips.append(_chip("Antikoag? (INR hoch)", "rhk-schip--bad", "INR erhöht trotz Angabe 'Keine Antikoagulation'"))

        else:
            chips.append(_chip("Antikoag: Nein", "rhk-schip--good"))
    else:
        if ac_paused or "paus" in ac_status:
            chips.append(_chip("Antikoag: Pausiert", "rhk-schip--good"))
        else:
            chips.append(_chip("Antikoag: Aktiv (!)", "rhk-schip--bad", "Nicht pausiert!"))

    # Kidney (eGFR staging)
    crea = d.float("creatinine_mg_dl")
    egfr_val, stage = compute_egfr(d.get("creatinine_mg_dl"), d.get("age"), d.get("sex"))

    # Fallback to direct entry if calc failed
    if egfr_val is None:
        egfr_val = d.float("egfr_ml_min_1_73") or d.float("egfr")
        if egfr_val:
            stage = "(Manuell)"

    kidney_tone = "rhk-schip--info"
    label = "Niere"
    tip = ""

    if egfr_val:
        label = f"eGFR {egfr_val:.0f}"
        if stage:
            label += f" {stage}"

        if egfr_val >= 60:
            kidney_tone = "rhk-schip--good"
        elif egfr_val >= 30:
            kidney_tone = "rhk-schip--warn"
        else:
            kidney_tone = "rhk-schip--bad"
    elif crea:
        label = f"Krea {crea:.2f}"
        kidney_tone = "rhk-schip--good" if crea < 1.3 else ("rhk-schip--warn" if crea < 1.8 else "rhk-schip--bad")

    chips.append(_chip(label, kidney_tone, tip))

    # Infection marker
    crp = d.float("crp_mg_l")
    if crp is not None:
        chips.append(_chip(f"CRP {crp:.1f}", "rhk-schip--good" if crp < 5 else ("rhk-schip--warn" if crp < 20 else "rhk-schip--bad")))

    return "<div class='rhk-summarybar' role='status' aria-label='Hämodynamik-Zusammenfassung'>" + "".join(chips) + "</div>"
