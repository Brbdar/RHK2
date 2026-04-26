#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_echo_report_patient import _echo_build_layered_paragraph
from rhk_reports import _build_layered_paragraph
from rhk_textdb_patient import PATIENT_BLOCKS, PATIENT_GLOSSARY


def test_duplicate_patient_blocks_are_merged_into_more_variants():
    block = PATIENT_BLOCKS["PX_DISCORDANCE_HIGH_MPAP_LOW_BNP"]
    # Block wird im TextDB-Modul zweimal ergänzt; beide Varianten sollen erhalten bleiben.
    assert len(block.templates) >= 4


def test_layered_paragraph_keeps_noun_initial_chunks_standalone():
    """Chunks that start with a capitalized determiner (Die/Der/Das/…) must
    NOT be prefixed with "Außerdem/Zusätzlich" because that would trigger
    ungrammatical V2 violations like "Außerdem die Werte sprechen…"."""
    out = _build_layered_paragraph(
        [
            "Die Messwerte zeigen eine relevante Druckerhöhung.",
            "Die Beschwerden im Alltag bleiben dabei ein zentraler Bezugspunkt.",
            "Die weitere Planung orientiert sich am Verlauf.",
        ],
        min_words=0,
        max_words=80,
    )

    assert "Außerdem die" not in out
    assert "Zusätzlich die" not in out
    # All three chunks should still appear in the output, just separated as
    # independent sentences.
    for frag in ("Messwerte zeigen", "Beschwerden im Alltag", "weitere Planung"):
        assert frag in out


def test_layered_paragraph_uses_transitions_for_verb_initial_chunks():
    """When chunks start with a finite verb, connectors are safe and welcome."""
    out = _build_layered_paragraph(
        [
            "Wir empfehlen eine Kontrolle innerhalb von drei Monaten.",
            "ergänzen wir gezielt die medikamentöse Therapie.",
            "planen wir den nächsten Kontrolltermin.",
        ],
        min_words=0,
        max_words=80,
    )

    assert "Außerdem" in out
    assert "Zusätzlich" in out


def test_echo_layered_paragraph_keeps_noun_initial_chunks_standalone():
    out = _echo_build_layered_paragraph(
        [
            "Die Messwerte sprechen für eine Druckbelastung.",
            "Die rechte Herzkammer zeigt dabei eine eingeschränkte Reserve.",
            "Die weitere Planung orientiert sich am klinischen Verlauf.",
        ],
        min_words=0,
        max_words=80,
    )

    assert "Außerdem die" not in out
    assert "Zusätzlich die" not in out
    for frag in ("Messwerte sprechen", "rechte Herzkammer", "weitere Planung"):
        assert frag in out


def test_patient_glossary_contains_extended_core_terms():
    for term in ("CTEPH", "präkapillär", "postkapillär", "6MWD", "WHO-FC"):
        assert term in PATIENT_GLOSSARY
