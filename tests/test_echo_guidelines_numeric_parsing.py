#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_echo_guidelines import fmt_value, severity, trend


def test_severity_parses_values_with_units_and_decimal_comma():
    assert severity("trv_ms", "3,2 m/s") == "r"
    assert severity("pasp_echo", "49 mmHg") == "y"
    assert severity("pasp_echo", "50 mmHg") == "r"


def test_severity_respects_inequality_prefixes_for_threshold_direction():
    assert severity("pasp_echo", "<=34 mmHg") == "g"
    assert severity("pasp_echo", ">=50 mmHg") == "r"


def test_trend_and_formatting_work_with_embedded_units():
    tr = trend("pasp_echo", "34 mmHg", ">=50 mmHg")
    assert tr.meaningful is True
    assert tr.reason == "severity_change"
    assert tr.improved is False
    assert tr.delta is not None and tr.delta > 15
    assert fmt_value("2,81 m/s", digits=2) == "2,81"
