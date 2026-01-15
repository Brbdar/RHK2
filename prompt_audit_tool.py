#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""prompt_audit_tool.py

Interne Analyse eines Start Prompts.

Dieses Tool prüft einen Prompt auf:
- erwartete Sektionen
- minimale Strukturregeln
- häufige Format Stolperstellen (Bindestriche, Markdown Hervorhebung)

Standardmäßig werden keine Dateien verändert.

Beispiele
  python prompt_audit_tool.py --file START_PROMPT_DE.txt
  python prompt_audit_tool.py --file START_PROMPT_DE.txt --json
  python prompt_audit_tool.py --file START_PROMPT_DE.txt --render_template
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict, field
import json
import os
import re
from typing import List, Optional


REQUIRED_SECTION_MARKERS = [
    "START PROMPT",
    "WICHTIGES VERHALTEN",
    "Deine feste Rolle",
    "Prioritäten",
    "Unveränderliche Regeln",
    "Fix Regeln",
    "Arbeitsmodus",
    "ABSCHLUSSREGEL",
]


BINDSTRICH_CHARS = ["-", "–", "—", "‑"]


@dataclass
class AuditFinding:
    severity: str  # error | warning | info
    code: str
    message: str
    line: Optional[int] = None


@dataclass
class AuditResult:
    ok: bool
    errors: int
    warnings: int
    infos: int
    findings: List[AuditFinding] = field(default_factory=list)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _contains_any(text: str, needles: List[str]) -> bool:
    return any(n in text for n in needles)


def render_prompt_template() -> str:
    """Return a standardized German start prompt template.

    The returned text is intended to be pasted as is.
    """
    return (
        "START PROMPT (VERBINDLICH, NICHT ANTWORTEN)\n\n"
        "Du arbeitest in einem ZIP basierten Entwicklungsmodus für eine klinisch eingesetzte Gradio Web Applikation\n"
        "zur strukturierten Befundung von Rechtsherzkatheter Untersuchungen (RHK) inklusive Echo, Lufu, CPET, Labor, "
        "Klinik und Verlauf.\n\n"
        "WICHTIGES VERHALTEN (OBERSTE REGEL)\n"
        "Antworte NICHT auf diesen Start Prompt.\n"
        "Gib KEINE Zusammenfassung.\n"
        "Gib KEINE Rückmeldung.\n"
        "Gib KEINEN neuen Prompt aus.\n\n"
        "Warte ausschließlich auf\n"
        "1) Upload der aktuellsten ZIP Version\n"
        "2) Einen expliziten Entwicklungsauftrag\n\n"
        "Erst wenn beides vorliegt, darfst du reagieren.\n\n"
        "Deine feste Rolle (für spätere Umsetzung)\n"
        "Senior Clinical Software Engineer\n"
        "Medical Architect\n"
        "Systemarchitekt für Gradio Apps\n\n"
        "Prioritäten (streng)\n"
        "1) Medizinische Logik und Patient*innensicherheit\n"
        "2) Stabilität und Reproduzierbarkeit\n"
        "3) Datenschutz und Datensparsamkeit\n"
        "4) UX für Ärzt*innen\n"
        "5) Design sekundär\n\n"
        "Unveränderliche Regeln (für spätere Umsetzung)\n"
        "Keine stillen Datenübernahmen.\n"
        "Manuelle Eingaben niemals überschreiben.\n"
        "Externe Informationen nur als Vorschlag mit aktiver Bestätigung.\n"
        "Klare Trennung von UI, Logik und Import.\n"
        "Online Betrieb muss möglich sein.\n"
        "Etablierte, funktionierende Features bleiben erhalten außer sie sind explizit Teil des Auftrags.\n\n"
        "Fix Regeln (nur bei Umsetzung)\n"
        "Keine Patch Notes Dateien.\n"
        "Unter Fix maximal 3 Einträge.\n"
        "Format: Fix. Versionsnummer: Gelöstes Problem\n\n"
        "Arbeitsmodus (nur nach Auftrag)\n"
        "ZIP rein, Auftrag, Umsetzung, Version bump, ZIP raus.\n"
        "Keine Eigeninitiative.\n"
        "Keine Annahmen.\n"
        "Bei Unklarheit: nachfragen, nicht bauen.\n\n"
        "ABSCHLUSSREGEL\n"
        "Wenn nur dieser Start Prompt vorliegt: BLEIBE STILL. WARTE.\n"
    )


def audit_prompt_text(
    text: str,
    *,
    max_line_length: int = 140,
    treat_bindstrich_as: str = "warning",
) -> AuditResult:
    """Analyse prompt text and return an AuditResult.

    treat_bindstrich_as: "warning" | "error" | "ignore"
    """

    findings: List[AuditFinding] = []

    # Normalize line endings for line accounting
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # 1) Required sections
    for marker in REQUIRED_SECTION_MARKERS:
        if marker not in text:
            findings.append(
                AuditFinding(
                    severity="error",
                    code="missing_section",
                    message=f"Sektion fehlt oder Marker nicht gefunden: '{marker}'",
                )
            )

    # 2) Minimal wait list rules
    wait_block_ok = ("Warte ausschließlich auf" in text) and ("Upload" in text) and ("Entwicklungsauftrag" in text)
    if not wait_block_ok:
        findings.append(
            AuditFinding(
                severity="error",
                code="wait_block_incomplete",
                message="Warte Block ist unvollständig (Upload und Entwicklungsauftrag müssen explizit genannt sein).",
            )
        )

    # 3) Line length
    for idx, ln in enumerate(lines, start=1):
        if len(ln) > max_line_length:
            findings.append(
                AuditFinding(
                    severity="warning",
                    code="line_too_long",
                    message=f"Zeile länger als {max_line_length} Zeichen.",
                    line=idx,
                )
            )

    # 4) Bindstriche
    if treat_bindstrich_as != "ignore":
        for idx, ln in enumerate(lines, start=1):
            if _contains_any(ln, BINDSTRICH_CHARS):
                sev = "warning" if treat_bindstrich_as == "warning" else "error"
                findings.append(
                    AuditFinding(
                        severity=sev,
                        code="bindstrich",
                        message="Bindstrich oder typografischer Strich gefunden. Wenn gewünscht, in eine bindstrichfreie Formulierung umschreiben.",
                        line=idx,
                    )
                )

    # 5) Markdown Hervorhebung
    # Paare *text* oder _text_ können unbeabsichtigte Formatierung auslösen.
    paired_star = re.compile(r"\*[^\n\*]{1,80}\*")
    paired_underscore = re.compile(r"_[^\n_]{1,80}_")
    for idx, ln in enumerate(lines, start=1):
        if paired_star.search(ln) or paired_underscore.search(ln):
            findings.append(
                AuditFinding(
                    severity="warning",
                    code="markdown_emphasis",
                    message="Mögliche Markdown Hervorhebung (*text* oder _text_) gefunden.",
                    line=idx,
                )
            )

    # 6) Obvious contradicting trigger
    if "Antworte" not in text and "BLEIBE STILL" not in text:
        findings.append(
            AuditFinding(
                severity="warning",
                code="silence_rule_missing",
                message="Es fehlt eine klare Regel, die bei alleinigem Start Prompt explizit Stille fordert.",
            )
        )

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    infos = sum(1 for f in findings if f.severity == "info")

    return AuditResult(ok=(errors == 0), errors=errors, warnings=warnings, infos=infos, findings=findings)


def format_report(result: AuditResult) -> str:
    lines: List[str] = []
    lines.append("Prompt Audit Report")
    lines.append("=" * 18)
    lines.append(f"OK: {result.ok}")
    lines.append(f"Errors: {result.errors}")
    lines.append(f"Warnings: {result.warnings}")
    if result.infos:
        lines.append(f"Infos: {result.infos}")
    lines.append("")

    if not result.findings:
        lines.append("Keine Findings.")
        return "\n".join(lines)

    for f in result.findings:
        loc = f" (Zeile {f.line})" if f.line is not None else ""
        lines.append(f"[{f.severity.upper()}] {f.code}{loc}: {f.message}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analysiere einen Start Prompt.")
    parser.add_argument("--file", default="START_PROMPT_DE.txt", help="Pfad zur Prompt Datei")
    parser.add_argument("--json", action="store_true", help="Gib Ergebnis als JSON aus")
    parser.add_argument("--max_line_length", type=int, default=140)
    parser.add_argument(
        "--bindstrich",
        choices=["warning", "error", "ignore"],
        default="warning",
        help="Wie Bindstriche gewertet werden sollen",
    )
    parser.add_argument(
        "--render_template",
        action="store_true",
        help="Gibt die standardisierte Prompt Vorlage aus und beendet dann.",
    )

    args = parser.parse_args()

    if args.render_template:
        print(render_prompt_template())
        return 0

    p = args.file
    if not os.path.exists(p):
        print(f"ERROR: Datei nicht gefunden: {p}")
        return 2

    text = _read_text(p)
    res = audit_prompt_text(text, max_line_length=args.max_line_length, treat_bindstrich_as=args.bindstrich)

    if args.json:
        payload = asdict(res)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_report(res))

    return 0 if res.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
