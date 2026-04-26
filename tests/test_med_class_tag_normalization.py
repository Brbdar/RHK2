#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook
from rhk_case import build_case


def _fired_rule_ids(case: Any) -> list[str]:
    fired = (case.get("debug") or {}).get("rule_trace", {}).get("fired") or []
    out: list[str] = []
    for x in fired:
        if isinstance(x, dict):
            rid = x.get("id")
            if isinstance(rid, str) and rid:
                out.append(rid)
    return out


def test_nitrate_pde5_contra_with_unicode_hyphen_tag() -> None:
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    ui = {
        "mpap_rest": 25,
        "pawp_rest": 10,
        "co_rest": 5.0,
        "rap_rest": 8,
        "on_nitrates": True,
        "ph_current_meds": ["PDE\u20115\u2011Hemmer"],
        "ph_prev_meds": [],
        "ph_new_meds": [],
    }

    case = build_case(ui, rules)
    fired_ids = _fired_rule_ids(case)

    assert "R_CONTRA_NITRATES_PDE5" in fired_ids
