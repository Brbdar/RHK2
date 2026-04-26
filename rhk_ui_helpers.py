#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper utilities extracted from `rhk_ui.py`."""

from __future__ import annotations

import hashlib
import importlib
import json
from typing import Any, Dict, List

from rhk_logging import log_exception

_SPIRO_LOGIC: Any = None
_UI_RECOVERABLE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    TypeError,
    ValueError,
    ImportError,
    ModuleNotFoundError,
)


def _get_spiro_logic():
    """Lazy import Spiro-Logic.

    MUST be fail-safe: example loading and bulk programmatic updates can trigger
    the CPET wizard. If import fails, return a fallback implementation.
    """
    global _SPIRO_LOGIC
    if _SPIRO_LOGIC is None:
        try:
            _SPIRO_LOGIC = importlib.import_module("spiro_logic")
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception(
                "RHK_UI_SPIRO_IMPORT",
                "Spiro-Logic import failed; fallback implementation activated.",
                exc,
            )

            class _FallbackSpiroLogic:
                @staticmethod
                def build_wizard_outputs(_ui: Dict[str, Any]):
                    msg = (
                        "<div class='docx-muted'>Spiro-Logic ist in dieser Umgebung nicht "
                        "verfügbar (Import fehlgeschlagen). CPET-Wizard-Ausgabe deaktiviert.</div>"
                    )
                    return {
                        "mod0_html": msg,
                        "mod1_html": "",
                        "mod2_html": "",
                        "mod3_html": "",
                        "mod4_html": "",
                        "mod5_html": "",
                        "mod6_html": "",
                        "mod7_html": "",
                        "mod9_html": "",
                        "modfinal_html": "",
                        "overall_html": msg,
                        "report_text": "",
                        "need_chrono_followups": False,
                    }

                @staticmethod
                def build_cpet_outputs(_ui: Dict[str, Any]):
                    out = _FallbackSpiroLogic.build_wizard_outputs(_ui)
                    msg = out.get("overall_html") or ""
                    out.setdefault("live_html", msg)
                    out.setdefault("teaching_html", "")
                    return out

            _SPIRO_LOGIC = _FallbackSpiroLogic()
    return _SPIRO_LOGIC


def _coerce_modules_list(value: Any) -> List[Any]:
    """Coerce module-like UI values into a list."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        parsed = None
        try:
            parsed = json.loads(s)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception("RHK_UI_MODULES_PARSE_JSON", "Failed to parse module list as JSON; trying literal parser.", exc)
            parsed = None
        if parsed is None:
            try:
                import ast

                parsed = ast.literal_eval(s)
            except _UI_RECOVERABLE_ERRORS as exc:
                log_exception(
                    "RHK_UI_MODULES_PARSE_LITERAL",
                    "Failed to parse module list as Python literal; using string fallback.",
                    exc,
                )
                parsed = None
        if isinstance(parsed, (list, tuple, set)):
            return list(parsed)
        if isinstance(parsed, str):
            s = parsed.strip()
            if not s:
                return []
        if "," in s or ";" in s:
            import re

            return [p.strip() for p in re.split(r"[;,]", s) if p and p.strip()]
        return [s]
    return [value]


def _build_generate_signature(raw: Dict[str, Any]) -> str:
    """Stable fingerprint for UI input state (used by generate-path cache)."""
    try:
        payload = json.dumps(raw or {}, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()
    except _UI_RECOVERABLE_ERRORS as exc:
        log_exception(
            "RHK_UI_SIG_PRIMARY",
            "Primary generate signature serialization failed; using fallback serialization.",
            exc,
        )
        try:
            payload = json.dumps(raw or {}, sort_keys=True, ensure_ascii=False, default=str)
        except _UI_RECOVERABLE_ERRORS as exc:
            log_exception(
                "RHK_UI_SIG_FALLBACK",
                "Fallback generate signature serialization failed; using string coercion.",
                exc,
            )
            payload = str(raw or "")
        return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _build_workflow_overview_html() -> str:
    """Compact orientation panel shown above input tabs.

    Default state is COLLAPSED — the explanatory text is not primary content and
    would otherwise dominate the above-the-fold view. Users can expand via the
    toggle button; the preference is persisted in localStorage.
    """
    return (
        "<div id='rhk_workflow_overview' class='is-collapsed' data-rhk-collapsed='1'>"
        "<div class='rhk-wf-title-row'>"
        "<div class='rhk-wf-title'>Arbeitsablauf (Schnell-Übersicht)</div>"
        "<button type='button' id='rhk_workflow_toggle' class='rhk-wf-toggle' aria-expanded='false' aria-controls='rhk_workflow_overview_body'>Einblenden</button>"
        "</div>"
        "<div id='rhk_workflow_overview_body' class='rhk-wf-body' aria-hidden='true'>"
        "<div class='rhk-wf-grid'>"
        "<div class='rhk-wf-col'>"
        "<div class='rhk-wf-head'>Eingabe in Reihenfolge</div>"
        "<ol class='rhk-wf-steps'>"
        "<li><span class='rhk-wf-step-label'>Klinik &amp; Labor</span><span class='rhk-wf-step-text'>Anamnese, Basisdaten, Labor, Medikation</span></li>"
        "<li><span class='rhk-wf-step-label'>Bildgebung &amp; Echo/CMR</span><span class='rhk-wf-step-text'>CT, V/Q, Echo, CMR</span></li>"
        "<li><span class='rhk-wf-step-label'>Lungenfunktion &amp; CPET</span><span class='rhk-wf-step-text'>Lufu, CPET inkl. Spiro-Logik</span></li>"
        "<li><span class='rhk-wf-step-label'>RHK</span><span class='rhk-wf-step-text'>Ruhe, Belastung, Volumen, Vasoreaktivität</span></li>"
        "<li><span class='rhk-wf-step-label'>Weitere Befunde</span><span class='rhk-wf-step-text'>6MWD, NYHA, Zusatzbefunde</span></li>"
        "<li><span class='rhk-wf-step-label'>Procedere &amp; Module</span><span class='rhk-wf-step-text'>Module auswählen, Freitext ergänzen</span></li>"
        "</ol>"
        "<div class='rhk-wf-quick'>"
        "<div class='rhk-wf-quick-head'>Schnellnavigation Eingabe</div>"
        "<div id='rhk_quick_nav' class='rhk-qnav'>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='0' data-rhk-input-tab='1. Klinik & Labor'>1 Klinik</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='1' data-rhk-input-tab='2. Bildgebung & Echo/CMR'>2 Bildgebung</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='2' data-rhk-input-tab='3. Lungenfunktion & CPET'>3 Lufu/CPET</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='3' data-rhk-input-tab='4. RHK'>4 RHK</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='4' data-rhk-input-tab='5. Weitere Befunde'>5 Weitere</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='input' data-rhk-nav-index='5' data-rhk-input-tab='6. Procedere & Module'>6 Procedere</button>"
        "</div>"
        "</div>"
        "</div>"
        "<div class='rhk-wf-col'>"
        "<div class='rhk-wf-head'>Ausgabe / Kontrolle</div>"
        "<ol class='rhk-wf-steps rhk-wf-steps--output'>"
        "<li><span class='rhk-wf-line'>Befund erstellen/aktualisieren starten</span></li>"
        "<li><span class='rhk-wf-line'>Arzt- und Patientenbericht prüfen</span></li>"
        "<li><span class='rhk-wf-line'>Intern/Debug bei Bedarf aktualisieren</span></li>"
        "<li><span class='rhk-wf-line'>Export: DOCX, JSON oder Summary</span></li>"
        "</ol>"
        "<div class='rhk-wf-quick'>"
        "<div class='rhk-wf-quick-head'>Schnellnavigation Ausgabe</div>"
        "<div id='rhk_output_nav' class='rhk-qnav'>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='output' data-rhk-output-tab='Arztbericht'>Arztbericht</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='output' data-rhk-output-tab='Echo Arztbefund (extended)'>Echo Arzt</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='output' data-rhk-output-tab='Patientenbericht'>Patientenbericht</button>"
        "<button type='button' class='rhk-qnav-btn' data-rhk-nav-scope='output' data-rhk-output-tab='Echo Patientenbericht'>Echo Patient</button>"
        "</div>"
        "</div>"
        "<div class='rhk-wf-tip'>Tipp: Die Sticky-Leiste oben zeigt jederzeit den aktuellen Fallstatus.</div>"
        "</div>"
        "</div>"
        "</div>"
        "</div>"
    )


__all__ = [
    "_UI_RECOVERABLE_ERRORS",
    "_build_generate_signature",
    "_build_workflow_overview_html",
    "_coerce_modules_list",
    "_get_spiro_logic",
]
