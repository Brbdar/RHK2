"""UI mode helpers for simplified vs expert workflows.

This module is intentionally Gradio-free so the visibility policy stays
unit-testable without importing the full UI stack.
"""

from __future__ import annotations

from typing import Any, Dict

UI_MODE_SIMPLE = "Einfach"
UI_MODE_EXPERT = "Experte"


def normalize_ui_mode(mode: Any) -> str:
    text = str(mode or "").strip().lower()
    if text == UI_MODE_EXPERT.lower():
        return UI_MODE_EXPERT
    return UI_MODE_SIMPLE


def build_ui_mode_help_html(mode: Any) -> str:
    normalized = normalize_ui_mode(mode)
    if normalized == UI_MODE_EXPERT:
        return (
            "<div class='rhk-card rhk-mode-card' style='padding:12px 14px;margin:8px 0 12px 0'>"
            "<span class='rhk-mode-label'>Expertenmodus</span>"
            "<span class='rhk-mode-text'>Alle Import-, Verlauf-, JSON-, Debug- und Legacy-Werkzeuge sind sichtbar. "
            "Geeignet für Sonderfälle, Migrationen, IT-Support und tiefe Qualitätskontrolle.</span>"
            "</div>"
        )
    return (
        "<div class='rhk-card rhk-mode-card' style='padding:12px 14px;margin:8px 0 12px 0'>"
        "<span class='rhk-mode-label'>Einfacher Modus</span>"
        "<span class='rhk-mode-text'>Fokussierter Hauptfluss — 1. Import → 2. Pflichtfelder prüfen → 3. Review → 4. Export. "
        "Legacy-, Admin- und Debug-Werkzeuge bleiben ausgeblendet.</span>"
        "</div>"
    )


def ui_mode_config(mode: Any, *, is_cloud_env: bool) -> Dict[str, Any]:
    normalized = normalize_ui_mode(mode)
    expert = normalized == UI_MODE_EXPERT
    return {
        "mode": normalized,
        "expert": expert,
        "help_html": build_ui_mode_help_html(normalized),
        "show_expert_actions": expert,
        "show_expert_export_buttons": expert,
        "show_docx_local_save": expert and (not is_cloud_env),
        "show_docx_cloud_hint": expert and is_cloud_env,
        "show_download_diag": expert,
        "show_internal_tabs": expert,
        "show_legacy_ph_tools": expert,
    }
