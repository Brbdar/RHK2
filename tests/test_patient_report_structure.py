import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import re

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case
from rhk_echo_report_patient import (
    _echo_glossary_one_sentence,
    _rewrite_echo_line_for_lay_mode,
    build_echo_patient_report,
)
from rhk_reports import (
    _glossary_one_sentence,
    _rewrite_patient_line_for_lay_mode,
    build_patient_report,
    random_example,
)

_RULES = load_rulebook(DEFAULT_RULEBOOK_PATH)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9ÄÖÜäöüß]+(?:/[A-Za-z0-9ÄÖÜäöüß]+)?", str(text or "")))


def _extract_section(lines, header):
    try:
        idx = lines.index(header)
    except ValueError:
        return []
    out = []
    for ln in lines[idx + 1 :]:
        if ln.startswith("## ") or ln.startswith("### "):
            break
        out.append(ln)
    return out


def _sentence_count(text: str) -> int:
    s = str(text or "").strip()
    if not s:
        return 0
    parts = re.split(r"(?<=[.!?])\s+", s)
    return len([p for p in parts if p.strip()])


def test_patient_report_contains_new_lay_sections():
    ui = random_example("pah_pre", seed=20260209)
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case)

    assert "## Einordnung und Transparenz" in txt
    assert "## Anlass der Untersuchung" in txt
    assert "## Diagnosen und Einordnung" in txt
    assert "## Persönliche Risikoeinschätzung" in txt
    assert "## Therapie und Medikamente" in txt
    assert "## Ansprechpartner und Kontakt" in txt


def test_echo_patient_report_contains_new_lay_sections():
    ui = random_example("pah_pre", seed=20260210)
    ui.update(
        {
            "echo_done": True,
            "trv_ms": 3.2,
            "tapse_mm": 15.0,
            "paat_ms": 90.0,
            "pericardial_effusion": "nein",
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case)

    assert "### Einordnung und Transparenz" in txt
    assert "### Anlass der Untersuchung" in txt
    assert "### Vergleich mit Orientierungswerten" in txt
    assert "### Wie geht es weiter?" in txt
    assert "### Ansprechpartner und Kontakt" in txt


def test_patient_report_kurzfassung_mode_is_compact():
    ui = random_example("pah_pre", seed=20260211)
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="kurzfassung")

    assert "# Kurzfassung zum Rechtsherzkatheter" in txt
    assert "## Kernbotschaft" in txt
    assert "## Nächste Schritte" in txt
    assert "## Warnzeichen" in txt
    assert "## Fragen für das Arztgespräch" not in txt


def test_patient_report_mode_from_ui_field_is_honored():
    ui = random_example("pah_pre", seed=20260213)
    ui["patient_report_mode"] = "kurzfassung"
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case)

    assert "# Kurzfassung zum Rechtsherzkatheter" in txt


def test_lay_rewriter_expands_medical_terms_inline():
    # v27.4.24+: expansion format keeps the medical term primary and puts the
    # lay-language explanation in parentheses — the previous format
    # ("{explanation} ({term})") produced ungrammatical German, e.g.
    # "Bei der Test, wie gut …".
    line = "Die ESC/ERS-Risikoeinstufung hilft bei der Einordnung. Der PAWP liegt im Normbereich."
    out = _rewrite_patient_line_for_lay_mode(line)

    assert "ESC/ERS-Risikoeinstufung (Risikoeinschätzung nach europäischen Fachleitlinien)" in out
    assert "PAWP (" in out
    out_lc = out.lower()
    assert "linken herzhälfte" in out_lc or "linken herzseite" in out_lc


def test_lay_rewriter_preserves_uncertainty_and_clear_negation():
    line = "V. a. CTEPH. DD: chronische Embolie. Es wurde kein Hinweis auf Perikarderguss gesehen. Befund regelrecht."
    out = _rewrite_patient_line_for_lay_mode(line)

    assert "Es besteht ein Verdacht auf" in out
    assert "Andere mögliche Erklärung:" in out
    assert "Es gibt keinen Hinweis auf" in out
    assert "unauffällig" in out


def test_lay_rewriter_normalizes_hinweise_phrase():
    line = "Hinweise auf eine pulmonale Hypertonie sind vorhanden."
    out = _rewrite_patient_line_for_lay_mode(line)

    assert "Es gibt Hinweise auf" in out


def test_lay_rewriter_tones_down_panic_words():
    line = "Der Befund wirkt gefährlich und schlimm."
    out = _rewrite_patient_line_for_lay_mode(line)

    assert "gefährlich" not in out.lower()
    assert "schlimm" not in out.lower()
    assert "ernst zu nehmen" in out.lower()


def test_echo_lay_rewriter_applies_certainty_rules():
    line = "V. a. PH. DD: Linksherzbeteiligung. Es wurde kein Hinweis auf Perikarderguss gesehen."
    out = _rewrite_echo_line_for_lay_mode(line)

    assert "Es besteht ein Verdacht auf" in out
    assert "Andere mögliche Erklärung:" in out
    assert "Es gibt keinen Hinweis auf" in out


def test_patient_report_applies_clarity_rules_to_story_text():
    # v27.4.24+: glossary expansions are now rendered as "{term} ({explanation})"
    # so that the medical term remains the primary noun (grammar-safe). The
    # previous format put the term in parens.
    ui = random_example("pah_pre", seed=20260214)
    ui["story"] = "V.a. PH. DD: ILD. Es wurde kein Hinweis auf Erguss gesehen. Befund regelrecht, aber gefährlich wirkend."
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="laienbefund")

    assert "Es besteht ein Verdacht auf" in txt
    # PH must still appear as a medical term somewhere (it may be expanded
    # inline as "PH (Pulmonale Hypertonie …)" or kept bare).
    assert "PH" in txt
    assert "Andere mögliche Erklärung:" in txt
    assert "ILD" in txt
    assert "Es gibt keinen Hinweis auf" in txt
    assert "Erguss" in txt
    assert "Befund unauffällig" in txt
    assert "gefährlich" not in txt.lower()
    assert "ernst zu nehmen" in txt.lower()


def test_patient_report_contains_explicit_overall_classification():
    ui = random_example("pah_pre", seed=20260215)
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case)

    assert "Gesamteinordnung:" in txt


def test_echo_report_contains_explicit_overall_classification():
    ui = random_example("pah_pre", seed=20260216)
    ui.update({"echo_done": True, "trv_ms": 3.2, "tapse_mm": 15.0})
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case)

    assert "Gesamteinordnung:" in txt


def test_patient_report_auto_glossary_inline_and_end_section():
    # v27.4.24+: inline expansion keeps the medical term primary, so the
    # rendering is "KM (Kontrastmittel)" not "Kontrastmittel (KM)".
    ui = random_example("pah_pre", seed=20260217)
    ui["story"] = (
        "KM i.v. gegeben, RR erhöht. LWS-Läsion mit DD: benigne vs maligne. "
        "Zusätzlich Ödem und Infiltrat beschrieben."
    )
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="laienbefund")

    assert "KM (Kontrastmittel" in txt
    assert "RR (Blutdruck" in txt
    assert "## Begriffe kurz erklärt" in txt
    assert "- **KM:**" in txt
    assert "- **RR:**" in txt
    assert "- **LWS:**" in txt
    assert "- **Ödem:**" in txt
    assert "- **Infiltrat:**" in txt


def test_patient_short_report_can_emit_glossary():
    ui = random_example("pah_pre", seed=20260218)
    ui["story"] = "KM i.v. gegeben, RR grenzwertig."
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="kurzfassung")

    assert "## Begriffe kurz erklärt" in txt
    assert "- **KM:**" in txt
    assert "- **RR:**" in txt


def test_echo_report_auto_glossary_section():
    ui = random_example("pah_pre", seed=20260219)
    ui.update(
        {
            "echo_done": True,
            "trv_ms": 3.2,
            "tapse_mm": 15.0,
            "story": "KM i.v. gegeben, RR erhöht.",
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case, mode="laienbefund")

    assert "Kontrastmittel (KM)" in txt
    assert "### Begriffe kurz erklärt" in txt
    assert "- **TAPSE:**" in txt
    assert "- **KM:**" in txt


def test_patient_layered_output_constraints():
    ui = random_example("pah_pre", seed=20260220)
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="laienbefund")
    lines = txt.splitlines()

    summary_lines = [ln.strip() for ln in _extract_section(lines, "## Kurzfazit (Schnellüberblick)") if ln.strip()]
    summary_txt = " ".join(summary_lines)
    wc = _word_count(summary_txt)
    assert 80 <= wc <= 120

    bullet_lines = [ln for ln in _extract_section(lines, "### Wichtigste Punkte") if ln.strip().startswith("- ")]
    assert bullet_lines
    for bl in bullet_lines:
        content = bl[2:].strip()
        sc = _sentence_count(content)
        assert 1 <= sc <= 2


def test_echo_layered_output_constraints():
    ui = random_example("pah_pre", seed=20260221)
    ui.update({"echo_done": True, "trv_ms": 3.2, "tapse_mm": 15.0})
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case, mode="laienbefund")
    lines = txt.splitlines()

    summary_lines = [ln.strip() for ln in _extract_section(lines, "### Kurzfazit (Schnellüberblick)") if ln.strip()]
    summary_txt = " ".join(summary_lines)
    wc = _word_count(summary_txt)
    assert 80 <= wc <= 120

    bullet_lines = [ln for ln in _extract_section(lines, "### Wichtigste Punkte") if ln.strip().startswith("- ")]
    assert bullet_lines
    for bl in bullet_lines:
        content = bl[2:].strip()
        sc = _sentence_count(content)
        assert 1 <= sc <= 2


def test_patient_report_contains_relevance_section_and_sidefinding_label():
    ui = random_example("pah_pre", seed=20260224)
    ui["bnp_kind"] = "BNP"
    ui["bnp_value"] = 50
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="laienbefund")

    assert "### Relevanz: Hauptbefunde und Nebenbefunde" in txt
    assert "Relevanz im Bericht:" in txt
    assert "Nebenbefund; keine akute Maßnahme wird erwähnt." in txt


def test_patient_relevance_section_can_emit_neutral_urgency_fallback():
    ui = random_example("pah_pre", seed=20260225)
    ui.update(
        {
            "mpap_rest": 18,
            "bnp_value": None,
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_patient_report(case, mode="laienbefund")

    assert "### Relevanz: Hauptbefunde und Nebenbefunde" in txt
    assert "Im Bericht steht keine Dringlichkeit." in txt


def test_echo_report_contains_relevance_section():
    ui = random_example("pah_pre", seed=20260226)
    ui.update(
        {
            "echo_done": True,
            "trv_ms": 3.2,
            "tapse_mm": 15.0,
            "paat_ms": 90.0,
            "pericardial_effusion": "nein",
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case, mode="laienbefund")

    assert "### Relevanz: Hauptbefunde und Nebenbefunde" in txt
    assert "Relevanz im Bericht:" in txt


def test_echo_relevance_section_can_emit_neutral_urgency_fallback():
    ui = random_example("pah_pre", seed=20260227)
    ui.update(
        {
            "echo_done": True,
            "cmr_done": False,
            "trv_ms": None,
            "pasp_echo": None,
            "paat_ms": None,
            "tapse_mm": None,
            "rvfac_pct": None,
            "s_prime_cm_s": None,
            "ivc_diam_mm": None,
            "ivc_collapse_index_pct": None,
            "ivc_collapse": None,
            "pericardial_effusion": None,
            "rvot_notch": None,
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case, mode="laienbefund")

    assert "### Relevanz: Hauptbefunde und Nebenbefunde" in txt
    assert "Im Bericht steht keine Dringlichkeit." in txt


def test_glossary_entries_are_reduced_to_one_sentence():
    p = _glossary_one_sentence("Erster Satz. Zweiter Satz.")
    e = _echo_glossary_one_sentence("Erster Satz. Zweiter Satz.")

    assert p == "Erster Satz."
    assert e == "Erster Satz."


def test_echo_patient_report_kurzfassung_mode_is_available():
    ui = random_example("pah_pre", seed=20260212)
    ui.update(
        {
            "echo_done": True,
            "trv_ms": 3.1,
            "tapse_mm": 16.0,
        }
    )
    case = build_case(dict(ui), _RULES)
    txt = build_echo_patient_report(case, mode="kurzfassung")

    assert "## Echo Kurzfassung (Patient*innen)" in txt
    assert "### Kernaussagen" in txt
    assert "### Nächste Schritte" in txt
