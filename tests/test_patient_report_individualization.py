#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_reports import build_patient_report


def _case_with_personal_context():
    return {
        "ui": {
            "firstname": "Max",
            "name": "Muster",
            "story": "Belastungsdyspnoe seit 6 Monaten",
            "ph_reason_rhk": "Verlaufskontrolle",
            "comorbidities": "COPD, Diabetes mellitus",
            "exertional_dyspnea": True,
            "dizziness": True,
            "syncope": "gelegentlich",
            "stairs_flights": 1,
            "six_mwd_m": 280,
            "six_mwd_date": "03/2026",
            "who_fc": "III",
        },
        "derived": {
            "mpap_rest": 34,
            "pawp_rest": 11,
            "pvr_rest": 4.8,
            "ci_rest": 2.1,
            "rap_rest": 9,
            "hemo_category": "precap",
            "risk_category": "intermediate-high",
        },
        "scores": {
            "esc_ers_4s": "intermediate-high",
            "esc_ers_4s_n": 3,
            "esc_ers_4s_missing": [],
        },
        "decision": {
            "leading_action": "die Ursache der Druckerhöhung weiter eingrenzen",
        },
        "hfpef": {},
        "env": {},
    }


def test_lay_report_uses_personal_context_for_more_individual_text():
    report = build_patient_report(_case_with_personal_context(), mode="laienbefund")

    assert "**Relevante Vorerkrankungen (laut Dokumentation):** COPD, Diabetes mellitus" in report
    assert "## Ihre Angaben zur Belastbarkeit im Alltag" in report
    assert "Im 6-Minuten-Gehtest wurden zuletzt 280 m erreicht (03/2026)." in report
    assert "Welche meiner Vorerkrankungen beeinflusst die Therapieentscheidung aktuell am stärksten?" in report
    assert "Welches realistische persönliche Belastungsziel" in report
    assert "Welche Sicherheitsregeln gelten für mich bei Schwindel/Ohnmacht im Alltag" in report
    assert "Bis wann sollte mein nächster Kontrolltermin konkret stattfinden?" in report


def test_short_report_includes_personal_context_section():
    report = build_patient_report(_case_with_personal_context(), mode="kurzfassung")

    assert "Relevante Vorerkrankungen laut Dokumentation: COPD, Diabetes mellitus" in report
    assert "## Persönliche Belastbarkeit im Alltag" in report
    assert "Im 6-Minuten-Gehtest wurden zuletzt 280 m erreicht (03/2026)." in report
