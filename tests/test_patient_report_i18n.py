import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case
from rhk_reports import build_patient_report, random_example


def _build_standard_case():
    """Build a standard case from a realistic PAH scenario."""
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    ui = random_example(scenario="pah_pre", seed=42)
    case = build_case(dict(ui), rules)
    return case


# ---------------------------------------------------------------------------
# Generate reports in all three languages
# ---------------------------------------------------------------------------

_CASE = None
_REPORTS = {}


def _get_case():
    global _CASE
    if _CASE is None:
        _CASE = _build_standard_case()
    return _CASE


def _get_report(lang):
    global _REPORTS
    if lang not in _REPORTS:
        _REPORTS[lang] = build_patient_report(_get_case(), lang=lang)
    return _REPORTS[lang]


# ---------------------------------------------------------------------------
# DE report tests
# ---------------------------------------------------------------------------

def test_de_report_contains_patientenbericht():
    report = _get_report("de")
    assert "Patientenbericht" in report or "patientenbericht" in report.lower()


def test_de_report_minimum_length():
    report = _get_report("de")
    assert len(report) > 500, f"DE report too short: {len(report)} chars"


def test_de_report_has_section_headers():
    report = _get_report("de")
    # Check for at least some expected section-like content
    lower = report.lower()
    markers = ["ergebnis", "zusammenfass", "messung", "untersuchung", "empfehl", "nächst"]
    hits = sum(1 for m in markers if m in lower)
    assert hits >= 2, f"DE report missing expected section content (hits={hits})"


# ---------------------------------------------------------------------------
# EN report tests
# ---------------------------------------------------------------------------

def test_en_report_minimum_length():
    report = _get_report("en")
    assert len(report) > 500, f"EN report too short: {len(report)} chars"


def test_en_report_no_common_german_words():
    report = _get_report("en")
    lines = report.strip().splitlines()
    german_words = {"Befund", "Ergebnis", "Untersuchung", "Empfehlung", "Zusammenfassung",
                    "Messwerte", "Behandlung", "Blutdruck", "Herzkathet", "Lungenhochdruck"}
    german_line_count = 0
    for line in lines:
        if any(gw in line for gw in german_words):
            german_line_count += 1
    # Allow at most 10% of lines to contain German words (some proper nouns may match)
    threshold = max(2, len(lines) // 10)
    assert german_line_count <= threshold, (
        f"EN report has {german_line_count}/{len(lines)} lines with common German words"
    )


def test_en_report_has_section_headers():
    report = _get_report("en")
    lower = report.lower()
    markers = ["result", "summar", "measur", "examinat", "recommend", "next"]
    hits = sum(1 for m in markers if m in lower)
    assert hits >= 2, f"EN report missing expected section content (hits={hits})"


# ---------------------------------------------------------------------------
# ZH report tests
# ---------------------------------------------------------------------------

def test_zh_report_minimum_length():
    report = _get_report("zh")
    assert len(report) > 500, f"ZH report too short: {len(report)} chars"


def test_zh_report_contains_chinese_characters():
    report = _get_report("zh")
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", report)
    assert len(chinese_chars) > 50, (
        f"ZH report has too few Chinese characters: {len(chinese_chars)}"
    )


def test_zh_report_has_section_headers():
    report = _get_report("zh")
    # Check for common Chinese section markers
    markers = ["结果", "检查", "建议", "总结", "测量", "下一步", "报告"]
    hits = sum(1 for m in markers if m in report)
    assert hits >= 2, f"ZH report missing expected section content (hits={hits})"


# ---------------------------------------------------------------------------
# Cross-language comparison
# ---------------------------------------------------------------------------

def test_all_three_reports_are_different():
    de = _get_report("de")
    en = _get_report("en")
    zh = _get_report("zh")
    assert de != en, "DE and EN reports are identical"
    assert de != zh, "DE and ZH reports are identical"
    assert en != zh, "EN and ZH reports are identical"
