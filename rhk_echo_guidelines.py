#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central guideline rule library for Echo cutoffs and trend logic.

Used by
- rhk_ui_echo.py: Ampel (green, yellow, red) in preview and compare tables
- rhk_reports.py: Patient and doctor narratives with meaningful trend statements

Thresholds are stored in `echo_guidelines.yaml` to keep them transparent and
versionable.

Ampel meaning
- g: within reference range
- y: borderline or mildly/moderately abnormal
- r: clearly abnormal or high risk marker

This is an orientation aid. Final interpretation depends on clinical context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml  # type: ignore[import-untyped]

_YAML_PATH = Path(__file__).with_name("echo_guidelines.yaml")
_CACHE: Dict[str, Any] | None = None
_NUMERIC_TOKEN_RE = re.compile(
    r"(?P<cmp><=|>=|<|>|≤|≥)?\s*(?P<num>[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:[eE][+-]?\d+)?)"
)


@dataclass(frozen=True)
class TrendResult:
    key: str
    prev: Any
    cur: Any
    delta: Optional[float]
    direction: str  # higher | lower | more_negative | binary
    improved: Optional[bool]
    meaningful: bool
    reason: str


@dataclass
class EchoPhProbabilityResult:
    probability: Optional[str]
    trv_present: bool
    trv_bucket: str
    sign_count: int
    category_count: int
    category_reasons: Dict[str, List[str]]


def _load_yaml() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data: Dict[str, Any] = {}
    if _YAML_PATH.exists():
        with _YAML_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    _CACHE = data
    return data


def guidelines_meta() -> Dict[str, Any]:
    return (_load_yaml().get("meta") or {})


def guidelines_sources() -> list[str]:
    meta = guidelines_meta()
    src = meta.get("sources") or []
    return [str(s) for s in src if str(s).strip()]


def rules() -> Dict[str, Any]:
    return (_load_yaml().get("rules") or {})


def rule_for(key: str) -> Dict[str, Any]:
    return rules().get(key) or {}


def label_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("label") or key)


def unit_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("unit") or "")


def note_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("note") or "")


def direction_for(key: str) -> str:
    r = rule_for(key)
    return str(r.get("direction") or "")


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            x = float(v)
            if x != x:
                return None
            return x
        except (TypeError, ValueError):
            return None
    if isinstance(v, str):
        s = v.strip().lower()
        if not s or s in ("—", "-", "keine angabe", "n/a"):
            return None
        if s in ("ja", "nein"):
            return None
        s = (
            s.replace("\u2212", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .replace("\xa0", " ")
        )
        m = _NUMERIC_TOKEN_RE.search(s)
        if not m:
            return None
        s = (m.group("num") or "").replace(",", ".")
        try:
            x = float(s)
            if x != x:
                return None
            cmp_op = (m.group("cmp") or "").strip()
            # Keep inequality information in a stable numeric representation.
            # Example: "<35" should rank just below 35 for threshold checks.
            if cmp_op in ("<", "<=", "≤"):
                x -= 1e-9
            elif cmp_op in (">", ">=", "≥"):
                x += 1e-9
            return x
        except Exception:
            return None
    return None


def _as_yesno(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return "ja" if v else "nein"
    if isinstance(v, (int, float)):
        return "ja" if float(v) >= 0.5 else "nein"
    s = str(v).strip().lower()
    if s in ("ja", "nein"):
        return s
    if s in ("true", "yes", "y", "wahr"):
        return "ja"
    if s in ("false", "no", "n", "falsch"):
        return "nein"
    return None


def _boolish_true(v: Any) -> bool:
    return _as_yesno(v) == "ja"


def _ivc_non_collapse(data: Mapping[str, Any]) -> Optional[bool]:
    collapse = _as_yesno(data.get("ivc_collapse"))
    if collapse == "ja":
        return False
    if collapse == "nein":
        return True

    collapse_index = _as_float(data.get("ivc_collapse_index_pct"))
    if collapse_index is None:
        return None
    return collapse_index < 50.0


def compute_echo_ph_probability(data: Mapping[str, Any]) -> EchoPhProbabilityResult:
    """ESC/ERS 2022 PH probability from TRV plus additional signs in 3 categories.

    Categories:
    - A: ventricles
    - B: pulmonary artery
    - C: RA/IVC

    High probability at TRV > 3.4 m/s. For TRV 2.9-3.4 m/s, at least two
    additional sign categories are needed for "hoch". If TRV is <= 2.8 m/s or
    not measurable, at least two categories raise probability to "intermediär".
    """
    trv = _as_float(data.get("trv_ms"))
    rv_lv_ratio = _as_float(data.get("rv_lv_ratio"))
    paat_ms = _as_float(data.get("paat_ms"))
    pa_diam_mm = _as_float(data.get("pa_diam_mm"))
    ra_esa_cm2 = _as_float(data.get("ra_esa_cm2"))
    ivc_diam_mm = _as_float(data.get("ivc_diam_mm"))
    ivc_non_collapse = _ivc_non_collapse(data)

    category_reasons: Dict[str, List[str]] = {
        "Ventrikel": [],
        "Pulmonalarterie": [],
        "RA/IVC": [],
    }

    if rv_lv_ratio is not None and rv_lv_ratio > 1.0:
        category_reasons["Ventrikel"].append("RV/LV > 1,0")
    if _boolish_true(data.get("septal_flattening")):
        category_reasons["Ventrikel"].append("Septumflattening")

    if paat_ms is not None and paat_ms < 105.0:
        category_reasons["Pulmonalarterie"].append("PAAT < 105 ms")
    if _boolish_true(data.get("rvot_notch")):
        category_reasons["Pulmonalarterie"].append("mid-systolic Notch")
    if pa_diam_mm is not None and pa_diam_mm > 25.0:
        category_reasons["Pulmonalarterie"].append("PA > 25 mm")

    if ra_esa_cm2 is not None and ra_esa_cm2 > 18.0:
        category_reasons["RA/IVC"].append("RA-Fläche > 18 cm²")
    if (
        ivc_diam_mm is not None
        and ivc_diam_mm > 21.0
        and ivc_non_collapse is True
    ):
        category_reasons["RA/IVC"].append("IVC > 21 mm ohne ausreichenden Kollaps")

    sign_count = sum(len(v) for v in category_reasons.values())
    category_count = sum(1 for v in category_reasons.values() if v)

    screening_inputs_present = bool(
        trv is not None
        or rv_lv_ratio is not None
        or paat_ms is not None
        or pa_diam_mm is not None
        or ra_esa_cm2 is not None
        or ivc_diam_mm is not None
        or data.get("septal_flattening") is not None
        or data.get("rvot_notch") is not None
        or data.get("ivc_collapse") is not None
        or data.get("ivc_collapse_index_pct") is not None
    )

    if not screening_inputs_present:
        return EchoPhProbabilityResult(
            probability=None,
            trv_present=False,
            trv_bucket="missing",
            sign_count=0,
            category_count=0,
            category_reasons=category_reasons,
        )

    probability: Optional[str]
    trv_bucket = "missing"
    if trv is not None:
        if trv > 3.4:
            trv_bucket = ">3.4"
            probability = "hoch"
        elif trv > 2.8:
            trv_bucket = "2.9-3.4"
            probability = "hoch" if category_count >= 2 else "intermediär"
        else:
            trv_bucket = "<=2.8"
            probability = "intermediär" if category_count >= 2 else "niedrig"
    else:
        probability = "intermediär" if category_count >= 2 else "niedrig"

    return EchoPhProbabilityResult(
        probability=probability,
        trv_present=trv is not None,
        trv_bucket=trv_bucket,
        sign_count=sign_count,
        category_count=category_count,
        category_reasons=category_reasons,
    )


def severity(key: str, value: Any) -> str:
    """Return g/y/r or empty if unknown.

    Binary markers:
    - pericardial_effusion: ja -> r, nein -> g
    - rvot_notch: ja -> r, nein -> g
    - ivc_collapse: ja -> g, nein -> r
    """
    if value is None:
        return ""

    d = direction_for(key)
    if d == "binary" or key in ("pericardial_effusion", "rvot_notch", "ivc_collapse"):
        yn = _as_yesno(value)
        if yn is None:
            return ""
        if key == "ivc_collapse":
            return "g" if yn == "ja" else "r"
        return "r" if yn == "ja" else "g"

    x = _as_float(value)
    if x is None:
        return ""

    r = rule_for(key)
    sev = r.get("severity") or {}

    # g/y/r checks (order matters, g then y then r)
    # Some rules use min_abs/max_abs (e.g. strain expressed as negative values). In those cases we compare |x|.
    xabs = abs(x)
    for code in ("g", "y", "r"):
        band = sev.get(code) or {}
        mn = band.get("min")
        mx = band.get("max")
        mn_abs = band.get("min_abs")
        mx_abs = band.get("max_abs")
        ok = True
        if mn is not None:
            try:
                ok = ok and x >= float(mn)
            except (TypeError, ValueError):
                ok = False
        if mx is not None:
            try:
                ok = ok and x <= float(mx)
            except (TypeError, ValueError):
                ok = False
        if mn_abs is not None:
            try:
                ok = ok and xabs >= float(mn_abs)
            except (TypeError, ValueError):
                ok = False
        if mx_abs is not None:
            try:
                ok = ok and xabs <= float(mx_abs)
            except (TypeError, ValueError):
                ok = False
        if ok and band:
            return code

    return ""


def meaningful_delta(key: str) -> Optional[float]:
    r = rule_for(key)
    md = r.get("meaningful_delta")
    try:
        return float(md) if md is not None else None
    except (TypeError, ValueError):
        return None


def trend(key: str, prev: Any, cur: Any) -> TrendResult:
    """Evaluate a parameter trend.

    Meaningful change is detected if:
    - severity category changes (g/y/r) OR
    - absolute delta exceeds meaningful_delta threshold.

    Direction defines what is considered improvement.
    """
    d = direction_for(key)

    if d == "binary" or key in ("pericardial_effusion", "rvot_notch", "ivc_collapse"):
        p_bin = _as_yesno(prev)
        c_bin = _as_yesno(cur)
        improved_bin: Optional[bool] = None
        meaningful = False
        reason = ""

        if p_bin is None or c_bin is None:
            return TrendResult(key, prev, cur, None, "binary", None, False, "insufficient")

        if key == "ivc_collapse":
            # ja is physiologic collapse, so appearance is improvement
            if p_bin != c_bin:
                meaningful = True
                improved_bin = (c_bin == "ja")
                reason = "state_change"
        else:
            if p_bin != c_bin:
                meaningful = True
                improved_bin = (c_bin == "nein")  # disappearance improves
                reason = "state_change"

        return TrendResult(key, p_bin, c_bin, None, "binary", improved_bin, meaningful, reason)

    p_num = _as_float(prev)
    c_num = _as_float(cur)
    if p_num is None or c_num is None:
        return TrendResult(key, prev, cur, None, d or "", None, False, "insufficient")

    delta = c_num - p_num

    sev_prev = severity(key, p_num)
    sev_cur = severity(key, c_num)

    improved_num: Optional[bool] = None
    if d == "lower":
        improved_num = delta < 0
    elif d == "more_negative":
        improved_num = c_num < p_num
    else:  # higher
        improved_num = delta > 0

    meaningful = False
    reason = ""

    if sev_prev and sev_cur and sev_prev != sev_cur:
        meaningful = True
        reason = "severity_change"
    else:
        md = meaningful_delta(key)
        if md is not None and abs(delta) >= md:
            meaningful = True
            reason = "delta_threshold"

    return TrendResult(key, p_num, c_num, delta, d or "", improved_num, meaningful, reason)


def fmt_delta(delta: Optional[float], digits: int = 0) -> str:
    if delta is None:
        return "—"
    if digits <= 0:
        return str(int(round(delta)))
    return f"{delta:.{digits}f}".replace(".", ",")


def fmt_value(v: Any, digits: int = 0) -> str:
    x = _as_float(v)
    if x is None:
        yn = _as_yesno(v)
        return yn if yn is not None else "—"
    if digits <= 0:
        return str(int(round(x)))
    return f"{x:.{digits}f}".replace(".", ",")


def overall_trend(prev_map: Dict[str, Any], cur_map: Dict[str, Any], keys: list[str]) -> Tuple[str, Dict[str, TrendResult]]:
    """Summarize overall trend across a list of keys.

    Returns (summary_label, per_key_results).
    summary_label is one of: verbessert, stabil, verschlechtert, nicht beurteilbar
    """
    results: Dict[str, TrendResult] = {}
    meaningful = []
    for k in keys:
        if k in prev_map and k in cur_map:
            tr = trend(k, prev_map.get(k), cur_map.get(k))
            results[k] = tr
            if tr.meaningful and tr.improved is not None:
                meaningful.append(tr.improved)

    if not meaningful:
        return "nicht beurteilbar", results

    # Majority vote
    improve_count = sum(1 for x in meaningful if x)
    worsen_count = sum(1 for x in meaningful if not x)

    if improve_count > worsen_count:
        return "verbessert", results
    if worsen_count > improve_count:
        return "verschlechtert", results
    return "stabil", results
