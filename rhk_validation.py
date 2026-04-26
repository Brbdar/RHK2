#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.48: rhk_validation.py - zentrale Parser (parse_boolish/parse_floatish) für konsistente Input-Logik
# Refactor v1.29: rhk_validation.py - Echo-/Import-HardLimits erweitert (unphys/0 -> None) für sichere Echo-PDF/OCR Übernahme
# Refactor v1.24: rhk_validation.py - Zentralisierte Sanitization & Plausibility-Gates, fehlende Werte ≠ 0, Type-Hints + Docstrings
"""Clinical input validation & sanitization utilities.

Dieses Projekt ist klinisch eingesetzt. Für **numerische** Eingaben gilt strikt:

- Fehlende Werte bleiben ``None`` (keine Imputation, fehlend ≠ 0).
- Unphysiologische Werte gelten als **nicht vorhanden** (für Berechnungen/Regeln).
- Manuelle Eingaben werden in der UI **nicht** überschrieben – Sanitization liefert
  stets eine Kopie.

Wichtig:
- Die in ``HARD_LIMITS`` definierten Grenzen sind *sehr breit* und dienen nur dazu,
  offensichtliche Tipp-/Einheitenfehler (z.B. falsche Einheit, Dezimalfehler) zu
  verhindern. Klinische Grenzfälle sollen **nicht** fälschlich verworfen werden.
- *Soft* Plausibilitätswarnungen bleiben Aufgabe von ``collect_plausibility_warnings()``
  (siehe ``rhk_base.py``).

Determinismus:
- Gleicher Input → gleiche Sanitization → gleicher Output.

Datenschutz:
- Keine Protokollierung von Rohwerten in diesem Modul.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from rhk_config import FALSE_TOKENS, MISSING_TOKENS, TRUE_TOKENS

# Back-compat aliases (used within this module and possibly externally).
TRUE_BOOL_TOKENS = TRUE_TOKENS
FALSE_BOOL_TOKENS = FALSE_TOKENS
NUM_MISSING_TOKENS = MISSING_TOKENS


def parse_boolish(x: Any) -> bool:
    """Parse mixed UI/import values into bool deterministically."""
    if isinstance(x, bool):
        return x
    if x is None:
        return False
    if isinstance(x, (int, float)):
        try:
            v = float(x)
        except (ValueError, TypeError):
            return False
        if not math.isfinite(v):
            return False
        return abs(v) > 1e-12
    if isinstance(x, str):
        s = x.strip().lower()
        if s in TRUE_BOOL_TOKENS:
            return True
        if s in FALSE_BOOL_TOKENS:
            return False
    return bool(x)


def parse_floatish(x: Any, *, treat_zero_as_missing: bool = False) -> Optional[float]:
    """Conservative numeric parser for UI/import values.

    - missing/invalid/bool -> None
    - supports decimal comma and unicode minus
    - optional: treat 0 as missing (for fields where 0 cannot be valid)
    """
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        try:
            v = float(x)
        except (ValueError, TypeError):
            return None
    elif isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        s = s.replace("\u2212", "-")
        s = s.lower()
        if s in NUM_MISSING_TOKENS:
            return None
        s = s.replace(",", ".")
        try:
            v = float(s)
        except (ValueError, TypeError):
            return None
    else:
        return None
    if not math.isfinite(v):
        return None
    if treat_zero_as_missing and abs(v) < 1e-12:
        return None
    return v


def safe_float(x: Any) -> Optional[float]:
    """Parse a user/UI value to float.

    - ``None``/""/NaN → ``None``
    - ``bool`` → ``None`` (Gradio checkboxes must never be coerced)
    - German decimal comma is supported.

    This is intentionally conservative. It does **not** try to guess thousands
    separators (that logic belongs to specific importers such as DOCX/PDF).
    """
    return parse_floatish(x, treat_zero_as_missing=False)


def safe_int(x: Any) -> Optional[int]:
    """Parse to int in a conservative, UI-friendly way.

    - Missing/NaN/Bool → None
    - ``0`` is treated as missing **only** by higher-level rules (see HardLimit),
      because some Gradio builds roundtrip empty number fields as 0.
    """
    v = safe_float(x)
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def safe_float_echo(x: Any) -> Optional[float]:
    """Echo-specific float normalisation.

    Echo parameters are physiologically never ``0`` — an apparent zero usually
    means the field was left empty at import time. This helper parses like
    :func:`safe_float` but additionally collapses ``0``/``0.0`` to ``None`` so
    that echo follow-up comparisons do not spuriously flag a value as present.
    """
    v = safe_float(x)
    if v is None:
        return None
    if abs(v) < 1e-12:
        return None
    return v


@dataclass(frozen=True)
class HardLimit:
    """Hard plausibility gate for numeric inputs.

    Values outside this range are treated as missing for downstream logic.
    """

    lo: float
    hi: float
    zero_is_missing: bool = False


# Broad hard limits (intentionally generous).
# These limits MUST be wide enough to not discard legitimate severe pathology.
HARD_LIMITS: dict[str, HardLimit] = {
    # Demography / vitals
    "age": HardLimit(0.0, 125.0, zero_is_missing=True),
    "height_cm": HardLimit(30.0, 300.0, zero_is_missing=True),
    "weight_kg": HardLimit(1.0, 500.0, zero_is_missing=True),
    "bp_sys": HardLimit(30.0, 300.0, zero_is_missing=True),
    "bp_dia": HardLimit(10.0, 200.0, zero_is_missing=True),
    "hr": HardLimit(10.0, 300.0, zero_is_missing=True),
    "bp_mean": HardLimit(0.0, 250.0, zero_is_missing=True),
    "spo2": HardLimit(0.0, 100.0, zero_is_missing=True),

    # Hemodynamics (rest/peak/pre/post/vaso)
    "spap_rest": HardLimit(0.0, 200.0, zero_is_missing=True),
    "dpap_rest": HardLimit(0.0, 150.0, zero_is_missing=True),
    "mpap_rest": HardLimit(0.0, 150.0, zero_is_missing=True),
    "pawp_rest": HardLimit(-5.0, 80.0, zero_is_missing=True),
    "rap_rest": HardLimit(-5.0, 40.0, zero_is_missing=True),
    "co_rest": HardLimit(0.1, 30.0, zero_is_missing=True),
    "ci_rest": HardLimit(0.1, 15.0, zero_is_missing=True),
    "pvr_rest": HardLimit(0.0, 60.0, zero_is_missing=True),

    "spap_peak": HardLimit(0.0, 220.0, zero_is_missing=True),
    "dpap_peak": HardLimit(0.0, 180.0, zero_is_missing=True),
    "mpap_peak": HardLimit(0.0, 180.0, zero_is_missing=True),
    "pawp_peak": HardLimit(-5.0, 100.0, zero_is_missing=True),
    "rap_peak": HardLimit(-5.0, 50.0, zero_is_missing=True),
    "co_peak": HardLimit(0.1, 40.0, zero_is_missing=True),
    "ci_peak": HardLimit(0.1, 20.0, zero_is_missing=True),

    "pawp_pre": HardLimit(-5.0, 80.0, zero_is_missing=True),
    "pawp_post": HardLimit(-5.0, 80.0, zero_is_missing=True),
    "mpap_pre": HardLimit(0.0, 180.0, zero_is_missing=True),
    "mpap_post": HardLimit(0.0, 180.0, zero_is_missing=True),

    "vaso_mpap_pre": HardLimit(0.0, 180.0, zero_is_missing=True),
    "vaso_mpap_post": HardLimit(0.0, 180.0, zero_is_missing=True),
    "vaso_co_pre": HardLimit(0.1, 40.0, zero_is_missing=True),
    "vaso_co_post": HardLimit(0.1, 40.0, zero_is_missing=True),

    # Step oximetry (%)
    "sat_svc": HardLimit(0.0, 100.0, zero_is_missing=True),
    "sat_ivc": HardLimit(0.0, 100.0, zero_is_missing=True),
    "sat_ra": HardLimit(0.0, 100.0, zero_is_missing=True),
    "sat_rv": HardLimit(0.0, 100.0, zero_is_missing=True),
    "sat_pa": HardLimit(0.0, 100.0, zero_is_missing=True),
    "sat_ao": HardLimit(0.0, 100.0, zero_is_missing=True),

# Echo (broad; hard-gates only for obviously impossible values / unit mistakes)
"bsa_m2": HardLimit(0.3, 5.0, zero_is_missing=True),
"lvef": HardLimit(1.0, 99.0, zero_is_missing=True),
"ee_ratio": HardLimit(0.1, 100.0, zero_is_missing=True),
"la_vmax_ml": HardLimit(1.0, 2000.0, zero_is_missing=True),
"la_esa_cm2": HardLimit(1.0, 500.0, zero_is_missing=True),
"lavi_ml_m2": HardLimit(1.0, 1000.0, zero_is_missing=True),

"tapse_mm": HardLimit(0.5, 200.0, zero_is_missing=True),
"s_prime_cm_s": HardLimit(0.1, 100.0, zero_is_missing=True),
"rvfac_pct": HardLimit(0.5, 100.0, zero_is_missing=True),
"tapse_spap_ratio": HardLimit(0.01, 10.0, zero_is_missing=True),

"rv_gls_pct": HardLimit(-100.0, 0.0, zero_is_missing=True),
"rv_fwls_pct": HardLimit(-100.0, 0.0, zero_is_missing=True),

"trv_ms": HardLimit(0.2, 10.0, zero_is_missing=True),
"pasp_echo": HardLimit(0.0, 300.0, zero_is_missing=True),
"paat_ms": HardLimit(1.0, 2000.0, zero_is_missing=True),
"rvet_ms": HardLimit(1.0, 2000.0, zero_is_missing=True),
"paat_rvet_ratio": HardLimit(0.0, 2.0, zero_is_missing=True),

"ra_esa_cm2": HardLimit(1.0, 400.0, zero_is_missing=True),
"ra_eda_cm2": HardLimit(1.0, 400.0, zero_is_missing=True),
"rv_edd_mm": HardLimit(1.0, 200.0, zero_is_missing=True),
"rv_esd_mm": HardLimit(1.0, 200.0, zero_is_missing=True),
"rv_eda_cm2": HardLimit(1.0, 500.0, zero_is_missing=True),
"rv_esa_cm2": HardLimit(1.0, 500.0, zero_is_missing=True),
"rv_wall_thickness_mm": HardLimit(0.1, 50.0, zero_is_missing=True),

"rv_3d_edv_ml": HardLimit(1.0, 4000.0, zero_is_missing=True),
"rv_3d_esv_ml": HardLimit(0.5, 4000.0, zero_is_missing=True),
"rv_3d_sv_ml": HardLimit(0.5, 4000.0, zero_is_missing=True),
"rv_3d_ef_pct": HardLimit(1.0, 99.0, zero_is_missing=True),
"rv_3d_edvi_ml_m2": HardLimit(1.0, 4000.0, zero_is_missing=True),
"rv_3d_esvi_ml_m2": HardLimit(1.0, 4000.0, zero_is_missing=True),

"ivc_exp_mm": HardLimit(0.1, 100.0, zero_is_missing=True),
"ivc_insp_mm": HardLimit(0.0, 100.0, zero_is_missing=True),
"ivc_collapse_index_pct": HardLimit(0.0, 100.0, zero_is_missing=True),

"pa_diam_mm": HardLimit(1.0, 120.0, zero_is_missing=True),
"rv_lv_ratio": HardLimit(0.1, 10.0, zero_is_missing=True),
"ivc_diam_mm": HardLimit(0.1, 100.0, zero_is_missing=True),


    # Basic labs (broad)
    "hb_g_dl": HardLimit(1.0, 25.0, zero_is_missing=True),
    "bnp_value": HardLimit(0.0, 1_000_000.0, zero_is_missing=True),
}


def sanitize_ui_numbers(ui: Mapping[str, Any]) -> dict[str, Any]:
    """Return a sanitized *copy* of a UI dict.

    - For keys in ``HARD_LIMITS``: returns float values or ``None``.
    - For all other keys: values are passed through unchanged.

    This function is intentionally shallow; it does not try to sanitize nested
    structures (episodes etc.), which have their own parsers.
    """
    out: dict[str, Any] = dict(ui or {})
    for k, lim in HARD_LIMITS.items():
        if k not in out:
            continue
        v = safe_float(out.get(k))
        if v is None:
            out[k] = None
            continue
        if lim.zero_is_missing and abs(v) < 1e-12:
            out[k] = None
            continue
        if v < lim.lo or v > lim.hi:
            out[k] = None
            continue
        out[k] = float(v)
    return out
