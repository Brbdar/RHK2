import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_reports import summarize_inputs


def _base_case(ui):
    return {
        "ui": dict(ui),
        "derived": {},
        "scores": {},
        "decision": {},
        "env": {},
        "warnings": [],
    }


def test_summarize_inputs_doctor_accepts_boolish_anticoag_status():
    case = _base_case(
        {
            "anticoag_status": "true",
            "anticoag_substance": "Apixaban",
            "anticoag_indication": "Vorhofflimmern",
            "anticoag_since": "01/2025",
        }
    )
    out = summarize_inputs(case, mode="doctor")
    assert "- **Antikoagulation:** ja (Apixaban; Indikation: Vorhofflimmern; seit 01/2025)" in out


def test_summarize_inputs_patient_shows_anticoag_note_for_yes_token():
    case = _base_case(
        {
            "anticoag_status": "yes",
            "anticoag_note": "Bitte Einnahmezeiten dokumentieren.",
        }
    )
    out = summarize_inputs(case, mode="default")
    assert "- **Antikoagulation:** ja" in out
    assert "- **Antikoagulation – Bem.:** Bitte Einnahmezeiten dokumentieren." in out


def test_summarize_inputs_patient_normalizes_antifibrotic_bool():
    case = _base_case(
        {
            "antifibrotic_status": True,
            "antifibrotic_drug": "Nintedanib",
            "antifibrotic_since": "2024",
            "antifibrotic_note": "Gut vertragen.",
        }
    )
    out = summarize_inputs(case, mode="default")
    assert "- **Antifibrotische Therapie:** ja (Nintedanib; seit 2024)" in out
    assert "- **Antifibrotika – Bem.:** Gut vertragen." in out
