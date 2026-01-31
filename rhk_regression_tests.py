#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression Test Suite (Rulebook)

Dependency light assertions for core RHK rule logic.

Run:
    python rhk_regression_tests.py
"""

from __future__ import annotations

from typing import Any, Dict, List

from rhk_base import DEFAULT_RULEBOOK_PATH, apply_rule_engine_trace, load_rulebook


def _mk_env(**kw: Any) -> Dict[str, Any]:
    """Create a minimal env for the rule engine.

    Important:
    - Explicitly set booleans used in comparisons (e.g. `step_up_present != True`) to avoid
      unintended matches due to missing keys.
    """
    env: Dict[str, Any] = {
        "mpap": None,
        "pawp_rest": None,
        "pvr": None,
        "step_up_present": False,
        "liver_hint": False,
        "poph_candidate": False,
        "high_flow": False,
        # sometimes used elsewhere
        "vq_defect": False,
        "ct_embolie": False,
        "ct_mosaic": False,
        "ct_ild": False,
        "ct_emphysema": False,
        "lufu_restrictive": False,
        "lufu_obstructive": False,
        "lufu_diffusion": False,
        "leading_group": None,
        "risk_category": None,
    }
    env.update(kw)
    return env


def _run_case(
    case_id: str,
    env: Dict[str, Any],
    expect_dx_contains: str,
    expect_tags: List[str],
    expect_modules: List[str],
) -> None:
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    d, trace = apply_rule_engine_trace(env, rules)

    if expect_dx_contains.lower() not in (d.primary_dx or '').lower():
        raise AssertionError(
            f"{case_id}: primary_dx mismatch. Got='{d.primary_dx}' Expected contains='{expect_dx_contains}'. "
            f"Fired={[x.get('id') for x in trace.fired]}"
        )

    for t in expect_tags:
        if t not in (d.tags or []):
            raise AssertionError(f"{case_id}: missing tag '{t}'. Got tags={d.tags}")

    for m in expect_modules:
        if m not in (d.modules or []):
            raise AssertionError(f"{case_id}: missing module '{m}'. Got modules={d.modules}")


def main() -> None:
    # 01 Unclassified High Flow (Safety Net)
    _run_case(
        "01",
        _mk_env(mpap=25, pawp_rest=10, pvr=1.5, step_up_present=False, liver_hint=False),
        expect_dx_contains="Unclassified PH (Flussdominante Druckerhöhung)",
        expect_tags=["PVR ≤ 2 WU", "High Output State"],
        expect_modules=["P32"],
    )

    # 02 Liver Profil A
    _run_case(
        "02",
        _mk_env(mpap=25, pawp_rest=10, pvr=1.5, step_up_present=False, liver_hint=True),
        expect_dx_contains="Unclassified PH (Flussdominante Druckerhöhung)",
        expect_tags=["Leber Profil A (Hyperdynam)", "PVR ≤ 2 WU"],
        expect_modules=["P32"],
    )

    # 03 Liver Profil B (postcap should remain, plus tag + P32)
    _run_case(
        "03",
        _mk_env(mpap=35, pawp_rest=20, pvr=1.5, step_up_present=False, liver_hint=True),
        expect_dx_contains="Postkapilläre PH",
        expect_tags=["Leber Profil B (Volumenbelastung)"],
        expect_modules=["P32"],
    )

    # 04 PoPH Candidate (manifest)
    _run_case(
        "04",
        _mk_env(mpap=35, pawp_rest=12, pvr=4.5, step_up_present=False, liver_hint=True, poph_candidate=True),
        expect_dx_contains="PoPH DD",
        expect_tags=["PoPH DD"],
        expect_modules=["P19", "P32"],
    )

    # 05 PoPH Borderline Risk
    _run_case(
        "05",
        _mk_env(mpap=25, pawp_rest=12, pvr=2.5, step_up_present=False, liver_hint=True, poph_candidate=True),
        expect_dx_contains="PoPH DD",
        expect_tags=["PoPH Risiko PVR 2-3"],
        expect_modules=["P19", "P32"],
    )

    # 06 Shunt Pure (primary dx must stay shunt; no forced P32)
    _run_case(
        "06",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=False, high_flow=False),
        expect_dx_contains="Shunt",
        expect_tags=["Shuntverdacht"],
        expect_modules=[],
    )

    # 07 Shunt + Liver Hint (enrichment + profile tag)
    _run_case(
        "07",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=True, high_flow=False),
        expect_dx_contains="Shunt",
        expect_tags=["Leber Profil A (Hyperdynam)"],
        expect_modules=["P32"],
    )

    # 08 Shunt + High Flow (enrichment)
    _run_case(
        "08",
        _mk_env(mpap=30, pawp_rest=10, pvr=1.5, step_up_present=True, liver_hint=False, high_flow=True),
        expect_dx_contains="Shunt",
        expect_tags=["Shuntverdacht"],
        expect_modules=["P32"],
    )

    # 09 Precap PH (standard, no liver, no P32)
    _run_case(
        "09",
        _mk_env(mpap=35, pawp_rest=10, pvr=4.0, step_up_present=False, liver_hint=False),
        expect_dx_contains="Präkapilläre PH",
        expect_tags=["präkapillär"],
        expect_modules=[],
    )

    # 10 CpcPH (standard)
    _run_case(
        "10",
        _mk_env(mpap=45, pawp_rest=22, pvr=4.0, step_up_present=False, liver_hint=False),
        expect_dx_contains="CpcPH",
        expect_tags=["CpcPH"],
        expect_modules=[],
    )

    print("OK: Regression suite passed (10 cases).")


if __name__ == "__main__":
    main()
