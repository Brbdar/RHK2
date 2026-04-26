"""Structured CPET teaching content, i18n-ready.

Previously this was embedded as large inline HTML in `spiro_logic.py`. It is
now a data structure so that:

1. Translations live in one place (DE/EN/ZH keys → `rhk_i18n.tr_ui`).
2. Clinical content can be audited independently of rendering logic.
3. Individual modules can be reused without rebuilding the whole HTML blob.

Rendering helpers produce compact HTML using the same CSS classes the UI
already ships with (`spiro-edu*`).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

# ``Translator`` is a simple callable ``tr(key: str) -> str``; if the
# key is missing, returning ``key`` unchanged keeps the module usable in
# tests without the i18n module loaded.
Translator = Callable[[str], str]


def _noop(text: str) -> str:
    return text


@dataclass(frozen=True)
class TeachingSection:
    """A single didactic block: headline + ordered key/value paragraphs."""

    title: str
    paragraphs: Sequence["TeachingParagraph"]
    open_by_default: bool = False


@dataclass(frozen=True)
class TeachingParagraph:
    """A paragraph inside a teaching section.

    ``kind`` is ``"text"`` for a plain paragraph or ``"list"`` for a
    bullet list. For ``list`` the ``body`` field becomes a list of items.
    """

    subtitle: Optional[str]
    body: object  # str for text, list[str] for list
    kind: str = "text"


# ---------------------------------------------------------------------------
# Content (German source of truth — English/Chinese resolved via tr())
# ---------------------------------------------------------------------------


def _vo2_section() -> TeachingSection:
    return TeachingSection(
        title="Lernmodul V'O2 (Sauerstoffaufnahme)",
        open_by_default=True,
        paragraphs=[
            TeachingParagraph(
                subtitle="Kernaussage",
                body="V'O2 ist der zentrale integrative Parameter der CPET. "
                "Er bildet das Zusammenspiel von Lunge, Kreislauf und Muskulatur ab.",
            ),
            TeachingParagraph(
                subtitle="Fick Prinzip",
                body="V'O2 = Herzzeitvolumen × C(a-v)O2.",
            ),
            TeachingParagraph(
                subtitle=None,
                kind="list",
                body=[
                    "Herzzeitvolumen steigt durch Herzfrequenzanstieg und Schlagvolumenanstieg.",
                    "C(a-v)O2 steigt durch gesteigerte periphere Sauerstoffextraktion in der arbeitenden Muskulatur.",
                ],
            ),
            TeachingParagraph(
                subtitle="Kinetik und Effizienz (Fahrradergometer)",
                body="Unter standardisierten Bedingungen steigt V'O2 mit der Leistung meist annähernd linear. "
                "Als grobe Orientierung werden etwa 10 ml pro Minute und Watt angegeben. "
                "Abweichungen können durch Effizienz, Protokoll, Trainingszustand oder frühes Abbrechen entstehen.",
            ),
            TeachingParagraph(
                subtitle="Normierung",
                body="V'O2 kann absolut (L/min) oder relativ (mL/min/kg) angegeben werden. "
                "Bei Adipositas kann die kg-Normierung die Einordnung verzerren. "
                "Ergänzend sind Prozent vom Sollwert oder andere Referenzen hilfreich.",
            ),
        ],
    )


def _o2pulse_section() -> TeachingSection:
    return TeachingSection(
        title="Lernmodul O2-Puls (V'O2/HF)",
        paragraphs=[
            TeachingParagraph(
                subtitle="Definition",
                body="O2-Puls = V'O2 / Herzfrequenz. Er entspricht der "
                "aufgenommenen Sauerstoffmenge pro Herzschlag.",
            ),
            TeachingParagraph(
                subtitle="Physiologischer Bezug",
                body="O2-Puls ist näherungsweise das Produkt aus Schlagvolumen und C(a-v)O2. "
                "Er korreliert häufig mit dem Schlagvolumen, ist jedoch ohne direkte Messung "
                "der arteriovenösen Differenz nicht exakt quantifizierbar.",
            ),
            TeachingParagraph(
                subtitle="Typische Muster",
                kind="list",
                body=[
                    "Bei Gesunden sollte der O2-Puls unter Belastung kontinuierlich ansteigen.",
                    "Frühe Plateaubildung oder ein Abfall kann auf eine fehlende Schlagvolumenreserve "
                    "oder begrenzte periphere Extraktion hinweisen.",
                ],
            ),
            TeachingParagraph(
                subtitle="Einflussgrößen",
                body="Anämie oder arterielle Hypoxämie können den O2-Puls deutlich vermindern, "
                "da die Sauerstofftransportkapazität reduziert ist.",
            ),
        ],
    )


def _thresholds_section() -> TeachingSection:
    return TeachingSection(
        title="Lernmodul AT, VAT und VCP",
        paragraphs=[
            TeachingParagraph(
                subtitle="AT und VAT",
                body="Die anaerobe Schwelle (AT) beschreibt den Übergang zu relevantem "
                "anaerobem Stoffwechsel. Die ventilatorische Schwelle (VAT/VT1) ist die "
                "indirekte Bestimmung über den Atemgasverlauf.",
            ),
            TeachingParagraph(
                subtitle="V-Slope Methode",
                body="Im aeroben Bereich besteht zwischen V'O2 und V'CO2 ein annähernd linearer Zusammenhang. "
                "Mit zunehmender Säurepufferung steigt V'CO2 überproportional. Der Knickpunkt wird "
                "zur VT1-Bestimmung genutzt.",
            ),
            TeachingParagraph(
                subtitle="VCP/VT2",
                body="Oberhalb eines weiteren Punktes (VCP/RCP) steigt die Ventilation im Verhältnis "
                "zu V'CO2 überproportional an, weil der Atemantrieb zusätzlich durch die Säurelast stimuliert wird.",
            ),
            TeachingParagraph(
                subtitle="Klinischer Nutzen",
                body="Die AT ist weniger motivationsabhängig als die maximale Leistung und eignet "
                "sich zur Beurteilung der Dauerleistungsfähigkeit. Sehr niedrige AT-Werte "
                "weisen auf frühe Limitierung des Sauerstofftransportes hin.",
            ),
        ],
    )


def _ph_pattern_section() -> TeachingSection:
    return TeachingSection(
        title="Lernmodul pulmonal-vaskuläres Muster (PH)",
        paragraphs=[
            TeachingParagraph(
                subtitle="Signatur",
                kind="list",
                body=[
                    "V'E/V'CO2-Slope erhöht (≥ 35).",
                    "PETCO2 in Ruhe/VT1 niedrig (< 30 mmHg) oder fallend unter Belastung.",
                    "O2-Puls flach oder mit früher Plateaubildung.",
                    "Oft vorzeitiger VT1, reduzierter V'O2-Watt-Anstieg.",
                    "EOV prognostisch ungünstig.",
                ],
            ),
            TeachingParagraph(
                subtitle="Plausibilität",
                body="Das Muster setzt eine freie Ventilationsmechanik voraus. "
                "Bei Atemreserve < 15 % oder Flow-Volume-Limitation ist zuerst die "
                "mechanische Komponente einzuordnen, danach das vaskuläre Muster erneut bewerten.",
            ),
        ],
    )


_TEACHING_SECTIONS = (
    _vo2_section(),
    _o2pulse_section(),
    _thresholds_section(),
    _ph_pattern_section(),
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html.escape(s or "")


def _render_paragraph(p: TeachingParagraph, tr: Translator) -> str:
    chunks: List[str] = []
    if p.subtitle:
        chunks.append(f"<div class='spiro-edu__sub'>{_esc(tr(p.subtitle))}</div>")
    if p.kind == "list":
        items = [str(it) for it in (p.body or [])]
        lis = "".join(f"<li>{_esc(tr(it))}</li>" for it in items if it)
        chunks.append(f"<ul>{lis}</ul>")
    else:
        chunks.append(f"<div>{_esc(tr(str(p.body)))}</div>")
    return "".join(chunks)


def _render_section(s: TeachingSection, tr: Translator) -> str:
    open_attr = " open" if s.open_by_default else ""
    body = "".join(_render_paragraph(p, tr) for p in s.paragraphs)
    return (
        f"<details class='spiro-edu__details'{open_attr}>"
        f"<summary class='spiro-edu__summary'>{_esc(tr(s.title))}</summary>"
        f"<div class='spiro-edu__teach'>{body}</div>"
        "</details>"
    )


def render_teaching_html(tr: Optional[Translator] = None) -> str:
    """Render the full teaching stack as HTML for the CPET tab.

    Pass ``tr=tr_ui`` from ``rhk_i18n`` to get localized content in EN/ZH;
    without ``tr`` the German source strings are returned unchanged.
    """
    trans = tr if callable(tr) else _noop
    return "".join(_render_section(s, trans) for s in _TEACHING_SECTIONS)


def render_section_html(index: int, tr: Optional[Translator] = None) -> str:
    """Render a single section by index (0=VO2, 1=O2-pulse, 2=AT/VCP, 3=PH)."""
    if index < 0 or index >= len(_TEACHING_SECTIONS):
        return ""
    trans = tr if callable(tr) else _noop
    return _render_section(_TEACHING_SECTIONS[index], trans)


# ---------------------------------------------------------------------------
# Short per-module teaching hints (used inline by spiro_logic.py)
# ---------------------------------------------------------------------------

MODULE_HINTS = {
    "m0_quality": "Ausbelastung wird über RER, Borg und Abbruchgrund beurteilt. "
    "Submaximale Tests sind interpretierbar, aber nur mit klarer Begründung. "
    "Sicherheitsabbruch ist ein valider Endpunkt.",
    "m1_drive": "Chronotrope Inkompetenz ist wahrscheinlich, wenn bei RER ≥ 1.10 "
    "weniger als 85 % der Soll-HF erreicht werden. Sie limitiert das Herzzeitvolumen "
    "und kann Symptome erklären.",
    "m2_capacity": "Bei PH ist V'O2peak < 11 mL/min/kg ein Hochrisiko-Kriterium. "
    "Werte immer im Kontext von Effort und Abbruchgrund bewerten.",
    "m3_circulation": "Ein O2-Puls-Plateau spricht für eine Schlagvolumen-Limitierung. "
    "Ein gleichzeitiger hoher diastolischer RR stützt eine Nachlast-Problematik.",
    "m4_ventilation": "Ein hoher V'E/V'CO2-Slope zusammen mit niedrigem oder fallendem "
    "PETCO2 bei freier Mechanik ist typisch für ein pulmonal-vaskuläres Muster.",
    "m5_mechanics": "Atemreserve < 15 % oder V'E/MVV ≥ 0.85 spricht für mechanische "
    "Limitation. Visuelle Flow-Volume-Limitierung verstärkt den Befund.",
    "m6_gas": "Desaturation < 88 % oder Abfall ≥ 4 % gilt als pathologisch. "
    "O2-Gabe verändert die Aussage und muss dokumentiert sein.",
    "m7_safety": "Hypotonie, Ischämiezeichen oder relevante Arrhythmien sind "
    "Abbruchkriterien. Diese Befunde sind unabhängig von V'O2 prognostisch und "
    "therapieentscheidend.",
    "m9_panel": "Die 9-Felder-Grafik dient als visuelle Plausibilisierung. "
    "Schwellen (VT1, RCP) sind Ankerpunkte. EOV ist ein ungünstiger Prognosemarker.",
}


def module_hint(key: str, tr: Optional[Translator] = None) -> str:
    """Return the localized one-line teaching string for a module key."""
    trans = tr if callable(tr) else _noop
    return trans(MODULE_HINTS.get(key, ""))
