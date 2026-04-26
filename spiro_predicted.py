"""Spiro predicted values: Wasserman, Hansen, Tanaka regressions.

Computes percent-predicted reference values for CPET parameters when
raw inputs (age, sex, height, weight) are available. Keeps the
clinical surface small and deterministic.

All functions return Optional[float] so callers can transparently handle
missing inputs without branching on sentinel values.

References
----------
- Wasserman K et al. "Principles of Exercise Testing and Interpretation",
  Lippincott Williams & Wilkins (Hansen/Wasserman cycle-ergometer equations).
- Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate
  revisited. J Am Coll Cardiol. 2001;37(1):153-156.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from rhk_validation import parse_floatish

__all__ = [
    "PredictedInputs",
    "PredictedValues",
    "compute_predicted",
    "chronotropic_index",
]


@dataclass(frozen=True)
class PredictedInputs:
    """Anthropometrics needed for predicted-value equations."""

    age: Optional[float]
    sex: Optional[str]  # "male" | "female" | None
    height_cm: Optional[float]
    weight_kg: Optional[float]

    @staticmethod
    def parse(ui: Dict[str, Any]) -> "PredictedInputs":
        age = parse_floatish(ui.get("age"), treat_zero_as_missing=True)
        height = parse_floatish(ui.get("height_cm"), treat_zero_as_missing=True)
        weight = parse_floatish(ui.get("weight_kg"), treat_zero_as_missing=True)
        raw_sex = str(ui.get("sex") or "").strip().lower()
        sex: Optional[str] = None
        if raw_sex.startswith("m") or raw_sex.startswith("männ"):
            sex = "male"
        elif raw_sex.startswith("f") or raw_sex.startswith("w"):
            sex = "female"
        return PredictedInputs(age=age, sex=sex, height_cm=height, weight_kg=weight)

    @property
    def complete(self) -> bool:
        return (
            self.age is not None
            and self.height_cm is not None
            and self.weight_kg is not None
            and self.sex in ("male", "female")
        )


@dataclass(frozen=True)
class PredictedValues:
    """Predicted reference values derived from anthropometrics."""

    vo2_peak_ml_min: Optional[float] = None          # absolute predicted V'O2peak (mL/min)
    vo2_peak_ml_kg_min: Optional[float] = None       # relative predicted V'O2peak (mL/min/kg)
    hr_max_bpm: Optional[float] = None               # predicted HR max (Tanaka)
    hr_max_classic_bpm: Optional[float] = None       # classic 220 - age
    mvv_l_min_fev1_35: Optional[float] = None        # MVV from FEV1*35
    mvv_l_min_fev1_40: Optional[float] = None        # MVV from FEV1*40
    o2_pulse_peak_ml: Optional[float] = None         # predicted peak O2 pulse (Wasserman)


def _wasserman_vo2_cycle(inp: PredictedInputs) -> Optional[float]:
    """Wasserman/Hansen cycle-ergometer V'O2peak (mL/min).

    Simplified Hansen/Wasserman equation for a Caucasian adult on a cycle
    ergometer. Normal-weight path and overweight path use the same formula
    (the clinical "ideal weight" variant is omitted — a single, auditable
    equation is preferred for deterministic output).
    """
    if not inp.complete:
        return None
    age = float(inp.age or 0)
    height_cm = float(inp.height_cm or 0)
    weight_kg = float(inp.weight_kg or 0)
    if age <= 0 or height_cm <= 0 or weight_kg <= 0:
        return None

    # Hansen/Wasserman cycle ergometer
    # Male:   VO2 = (height - age) * 20   (sedentary); active add 10%
    # Female: VO2 = (height - age) * 14
    # Weight adjustment: add (actual - ideal) * 6 for males, * 4 for females
    if inp.sex == "male":
        base = (height_cm - age) * 20.0
        ideal_weight = 0.79 * height_cm - 60.7
        adj = max(0.0, weight_kg - ideal_weight) * 6.0
    else:  # female
        base = (height_cm - age) * 14.0
        ideal_weight = 0.65 * height_cm - 42.8
        adj = max(0.0, weight_kg - ideal_weight) * 4.0
    vo2 = base + adj
    return max(0.0, vo2)


def _tanaka_hr_max(age: Optional[float]) -> Optional[float]:
    """Tanaka age-predicted HR max: 208 - 0.7*age."""
    if age is None or age <= 0:
        return None
    return 208.0 - 0.7 * float(age)


def _classic_hr_max(age: Optional[float]) -> Optional[float]:
    """Classic 220 - age formula (widely used legacy)."""
    if age is None or age <= 0:
        return None
    return 220.0 - float(age)


def _mvv_from_fev1(fev1_l: Optional[float], factor: float) -> Optional[float]:
    """MVV (L/min) estimated as FEV1 (L) * factor. Common factors: 35 or 40."""
    if fev1_l is None or fev1_l <= 0:
        return None
    return fev1_l * factor


def _o2_pulse_predicted(vo2_ml_min: Optional[float], hr_max: Optional[float]) -> Optional[float]:
    """O2 pulse predicted = V'O2peak pred / HR max pred."""
    if vo2_ml_min is None or hr_max is None or hr_max <= 0:
        return None
    return vo2_ml_min / hr_max


def compute_predicted(ui: Dict[str, Any], fev1_l: Optional[float] = None) -> PredictedValues:
    """Compute all predicted reference values we can derive from UI input.

    `ui` should contain at least age/sex/height/weight (from the clinical tab).
    `fev1_l` is an optional override if FEV1 is already parsed elsewhere.
    """
    inp = PredictedInputs.parse(ui or {})
    vo2_abs = _wasserman_vo2_cycle(inp)
    vo2_rel = None
    if vo2_abs is not None and inp.weight_kg and inp.weight_kg > 0:
        vo2_rel = vo2_abs / float(inp.weight_kg)

    hr_tanaka = _tanaka_hr_max(inp.age)
    hr_classic = _classic_hr_max(inp.age)

    # FEV1 fallback: the UI uses `fev1_l` as "% predicted", not absolute L.
    # Skip MVV estimate unless caller supplies absolute FEV1.
    mvv35 = _mvv_from_fev1(fev1_l, 35.0)
    mvv40 = _mvv_from_fev1(fev1_l, 40.0)

    o2p = _o2_pulse_predicted(vo2_abs, hr_tanaka)

    return PredictedValues(
        vo2_peak_ml_min=vo2_abs,
        vo2_peak_ml_kg_min=vo2_rel,
        hr_max_bpm=hr_tanaka,
        hr_max_classic_bpm=hr_classic,
        mvv_l_min_fev1_35=mvv35,
        mvv_l_min_fev1_40=mvv40,
        o2_pulse_peak_ml=o2p,
    )


def chronotropic_index(
    hr_rest: Optional[float],
    hr_peak: Optional[float],
    hr_max_predicted: Optional[float],
) -> Optional[float]:
    """Chronotropic index (CI) per Wilkoff / Lauer.

    CI = (HR_peak - HR_rest) / (HR_max_predicted - HR_rest)

    Reference values: ≥ 0.80 is typically considered adequate;
    < 0.80 indicates chronotropic incompetence.
    """
    if hr_rest is None or hr_peak is None or hr_max_predicted is None:
        return None
    reserve = hr_max_predicted - hr_rest
    if reserve <= 0:
        return None
    return (hr_peak - hr_rest) / reserve
