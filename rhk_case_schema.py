#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Typed case schema shared across modules."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

CaseSection = Dict[str, Any]
WarningList = List[Dict[str, Any]]


class CaseSchema(TypedDict, total=False):
    """Persisted/rendered case payload used by reports, UI state and exports."""

    ui: CaseSection
    derived: CaseSection
    scores: CaseSection
    decision: CaseSection
    hfpef: CaseSection
    env: CaseSection
    warnings: WarningList
    debug: CaseSection


class BuiltCaseSchema(TypedDict):
    """Fully built case payload returned by `build_case`."""

    ui: CaseSection
    derived: CaseSection
    scores: CaseSection
    decision: CaseSection
    hfpef: CaseSection
    env: CaseSection
    warnings: WarningList
    debug: CaseSection

CaseLike = CaseSchema | Dict[str, Any]


__all__ = [
    "BuiltCaseSchema",
    "CaseLike",
    "CaseSchema",
    "CaseSection",
    "WarningList",
]
