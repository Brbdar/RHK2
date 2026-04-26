from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_i18n import build_ui_i18n_payload, dump_ui_i18n_payload


def test_ui_i18n_payload_exposes_expected_languages() -> None:
    payload = build_ui_i18n_payload()
    assert payload["defaultLanguage"] == "de"
    assert sorted(payload["languages"]) == ["de", "en", "zh"]


def test_ui_i18n_payload_contains_core_translations() -> None:
    payload = build_ui_i18n_payload()
    assert payload["exact"]["en"]["RHK Befundassistent"] == "RHC Report Assistant"
    assert payload["exact"]["zh"]["Arztbericht"] == "医生报告"
    assert payload["exact"]["zh"]["Summary (JSON)"] == "摘要（JSON）"


def test_ui_i18n_payload_dump_is_valid_json() -> None:
    payload = json.loads(dump_ui_i18n_payload())
    assert payload["messages"]["en"]["language_switch_label"] == "Change language"

