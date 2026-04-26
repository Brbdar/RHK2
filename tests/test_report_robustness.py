import os
import random
import sys

# Ensure project root in path (flat repo)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import TextBlock
from rhk_reports import (
    _render_echo_patient_text,
    _render_patient_text,
    _safe_format_text_template,
    build_doctor_report_template,
)


def test_safe_format_template_survives_malformed_placeholders():
    out = _safe_format_text_template("Hallo {name} {", {"name": "Max"})
    assert isinstance(out, str)
    assert "Hallo" in out


def test_patient_text_render_is_robust_for_invalid_templates():
    blocks = {
        "PX_TEST": {
            "template": "Hinweis {ungeschlossen",
        }
    }
    txt = _render_patient_text("PX_TEST", blocks, {"foo": "bar"}, random.Random(1))
    assert isinstance(txt, str)
    assert "Hinweis" in txt


def test_echo_patient_text_render_is_robust_for_invalid_templates():
    blocks = {
        "ECHO_TEST": {
            "template": "Echo {ungeschlossen",
        }
    }
    txt = _render_echo_patient_text("ECHO_TEST", blocks, {"foo": "bar"}, random.Random(1))
    assert isinstance(txt, str)
    assert "Echo" in txt


def test_doctor_report_template_no_nameerror_on_ph_flags():
    case = {
        "ui": {
            "story": "Belastungsdyspnoe",
            "ph_known": True,
            "ph_known_dx": "PAH",
        },
        "derived": {
            "p_module_policy": {"allowed": [], "disabled": {}, "levels": {}},
        },
        "scores": {},
        "decision": {"bundle": "K00"},
        "env": {},
        "warnings": [],
    }
    blocks = {
        "K00_B": TextBlock(id="K00_B", title="K00 Befund", template="Kein Hinweis.", kind="bundle"),
        "K00_E": TextBlock(id="K00_E", title="K00 Empfehlung", template="Kontrolle.", kind="bundle"),
        "P01": TextBlock(id="P01", title="P01", template="Basisdiagnostik.", kind="module"),
    }

    out = build_doctor_report_template(case, blocks)
    assert isinstance(out, str)
    assert len(out.strip()) > 0
