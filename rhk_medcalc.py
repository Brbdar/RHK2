#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.26: rhk_medcalc.py - Ausgelagerte medizinische Hilfsberechnungen (eGFR CKD-EPI 2021), robuste Validierung
"""Medical helper calculations.

Important:
- These functions MUST be deterministic.
- They MUST NOT silently coerce missing values to 0.
- Biological plausibility checks are conservative (invalid inputs -> None).
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple


def compute_egfr(creatinine_mg_dl: Any, age_years: Any, sex: Any) -> Tuple[Optional[float], str]:
    """Compute eGFR (CKD-EPI 2021, race-free).

    Returns:
        (egfr_ml_min_1_73, stage_label)

    Validation (conservative):
    - Non-numeric inputs -> (None, "")
    - NaN/Inf -> (None, "")
    - Clearly non-biological ranges -> (None, "")

    Notes:
    - The staging labels G1..G5 follow common KDIGO-style ranges.
    - This is a *support* value for UI safety headers; it is not used to make therapy decisions.
    """
    try:
        scr = float(str(creatinine_mg_dl).replace(",", "."))
        age = float(str(age_years).replace(",", "."))
    except (TypeError, ValueError):
        return None, ""

    if not (math.isfinite(scr) and math.isfinite(age)):
        return None, ""

    # Biological plausibility bounds (conservative)
    if scr <= 0.1 or scr > 25.0 or age <= 0 or age > 130:
        return None, ""

    s = str(sex or "").strip().lower()
    is_female = s in {"w", "weiblich", "female", "f", "frau"}

    # CKD-EPI 2021 constants (race-free)
    k = 0.7 if is_female else 0.9
    a = -0.241 if is_female else -0.302
    sex_factor = 1.012 if is_female else 1.0

    ratio = scr / k
    mn = min(ratio, 1.0)
    mx = max(ratio, 1.0)

    try:
        egfr = 142.0 * (mn ** a) * (mx ** -1.200) * (0.9938 ** age) * sex_factor
        if not math.isfinite(egfr):
            return None, ""

        # Staging (KDIGO-style)
        if egfr >= 90:
            stage = "G1"
        elif egfr >= 60:
            stage = "G2"
        elif egfr >= 45:
            stage = "G3a"
        elif egfr >= 30:
            stage = "G3b"
        elif egfr >= 15:
            stage = "G4"
        else:
            stage = "G5"

        return round(egfr, 1), stage
    except Exception:
        return None, ""
