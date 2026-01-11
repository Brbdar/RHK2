#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snapshot Tests (Regelwerk Regression)

- Erzeugt und vergleicht Snapshots der Rule-Engine Outputs für definierte Beispiel-Fälle.
- Ziel: klinische Stabilität (keine stillen Regel-Regressionen), ohne CI-Zwang.

Usage:
  python tests/rules_snapshot.py
  python tests/rules_snapshot.py --update
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy

# Sicherstellen, dass Projekt-Root im Pfad ist (Flat-Repo)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_base import DEFAULT_RULEBOOK_PATH, load_rulebook  # noqa: E402
from rhk_case import build_case  # noqa: E402


SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "_snapshots", "rules_snapshot.json")


def _minimal_snapshot(case_out: dict) -> dict:
    """Keep the snapshot small but clinically meaningful."""
    decision = case_out.get("decision") or {}
    debug = case_out.get("debug") or {}
    trace = (debug.get("rule_trace") or {})
    fired = trace.get("fired") or []
    fired_ids = [x.get("id") for x in fired if isinstance(x, dict) and x.get("id")]

    # Shorten recommendations (avoid huge diffs due to text wrapping changes)
    recs = decision.get("recommendations") or []
    recs_short = []
    for r in recs:
        s = str(r).strip().replace("\n", " ")
        if len(s) > 240:
            s = s[:240] + "…"
        recs_short.append(s)

    return {
        "bundle": decision.get("bundle"),
        "primary_dx": decision.get("primary_dx"),
        "tags": decision.get("tags") or [],
        "modules": decision.get("modules") or [],
        "recommendations_short": recs_short,
        "fired_rule_ids": fired_ids,
        "warnings_count": case_out.get("derived", {}).get("warnings_count", None),
    }


def build_examples() -> dict:
    """Define a small set of deterministic cases."""
    examples = {}

    base_ui = {
        # minimal hemodynamics (avoid None-branches)
        "mpap_rest": 25,
        "pawp_rest": 10,
        "co_rest": 5.0,
        "rap_rest": 8,
        # PH therapy inputs
        "ph_current_meds": [],
        "ph_prev_meds": [],
        "on_nitrates": False,
    }

    # 1) Contra: Nitrate + PDE5
    ui1 = deepcopy(base_ui)
    ui1["on_nitrates"] = True
    ui1["ph_current_meds"] = ["PDE‑5‑Hemmer"]
    examples["contra_nitrates_pde5"] = ui1

    # 2) Nitrates only
    ui2 = deepcopy(base_ui)
    ui2["on_nitrates"] = True
    ui2["ph_current_meds"] = []
    examples["nitrates_only"] = ui2

    # 3) PDE5 only
    ui3 = deepcopy(base_ui)
    ui3["on_nitrates"] = False
    ui3["ph_current_meds"] = ["PDE‑5‑Hemmer"]
    examples["pde5_only"] = ui3

    return examples


def run(update: bool = False) -> int:
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    out = {}
    for name, ui in build_examples().items():
        case = build_case(ui, rules)
        out[name] = _minimal_snapshot(case)

    if update or (not os.path.exists(SNAPSHOT_PATH)):
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"[OK] Snapshot written: {SNAPSHOT_PATH}")
        return 0

    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        ref = json.load(f)

    if ref == out:
        print("[OK] Snapshot match.")
        return 0

    # Simple diff output
    print("[FAIL] Snapshot mismatch.\n")
    print("Expected:", json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True))
    print("\nGot:", json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="Overwrite snapshot intentionally.")
    args = ap.parse_args()
    return run(update=args.update)


if __name__ == "__main__":
    raise SystemExit(main())
