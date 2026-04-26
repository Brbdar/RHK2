import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook, load_textdb_blocks
from rhk_case import build_case
from rhk_reports import build_doctor_report, build_doctor_report_template, random_example


def test_reports_show_selected_disabled_and_auto_module_transparency():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    blocks = load_textdb_blocks()
    ui = random_example(scenario="ild_ph", seed=42)
    case = build_case(dict(ui), rules)

    doc_template = build_doctor_report_template(case, blocks)
    doc_full = build_doctor_report(case, blocks)

    # Full doctor report (Markdown) uses cleaner labels and proper ### headings
    # for the transparency sub-sections. The template report still emits flat
    # bulleted paragraphs and keeps the legacy wording.
    assert "Übernommene Module:" in doc_full
    assert "### In dieser Konstellation nicht anwählbar" in doc_full
    assert "### Weitere Regelwerk-Vorschläge (nicht automatisch übernommen)" in doc_full

    assert "Ausgewählt übernommen:" in doc_template
    assert "Ausgewählt, aber nicht anwählbar:" in doc_template
    assert "Regelwerk-Vorschläge (nicht automatisch übernommen):" in doc_template
