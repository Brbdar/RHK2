Filename: demo_echo_reports.py
Full Content:
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Demo & Benchmark Harness for Echo Reports.

Run:
  python demo_echo_reports.py

MASTERMIND EDITION:
- Physics Engine: Validates TRV vs. sPAP (Bernoulli) and TAPSE/sPAP Coupling.
- Performance Telemetry: Micro-benchmarking using Context Managers.
- Resilience: Runs in Mock-Mode if backend modules are missing.
- Strict Type Safety: Enforces clean data contracts via TypedDict.
"""

import time
import sys
from typing import TypedDict, Optional, Dict, List, Any
from dataclasses import dataclass

# --- 1. Robust Import Layer (Safety & Isolation) ---
try:
    from rhk_reports import build_echo_patient_report, build_echo_doctor_report_extended
    CORE_AVAILABLE = True
except ImportError:
    print("⚠️  SYSTEM WARNING: 'rhk_reports' module not found.")
    print("    -> Running in HEADLESS MOCK MODE.\n")
    CORE_AVAILABLE = False

    def build_echo_patient_report(case: Dict) -> str:
        return f"[MOCK PATIENT] Echo report based on {len(case.get('ui', {}))} params."

    def build_echo_doctor_report_extended(case: Dict) -> str:
        return "[MOCK DOCTOR] Findings: RV function reduced, markers of PH present..."


# --- 2. Strict Data Contracts (Type Safety) ---

class EchoUI(TypedDict, total=False):
    """
    Strict interface for Echo parameters.
    Ensures clear API contracts and prevents magic string errors.
    """
    echo_done: bool
    cmr_done: bool
    # RV Function
    tapse_mm: Optional[float]
    s_prime_cm_s: Optional[float]
    rvfac_pct: Optional[float]
    rv_3d_ef_pct: Optional[float]
    rv_fwls_pct: Optional[float]
    tapse_spap_ratio: Optional[float]
    # Pressure / PH Signs
    trv_ms: Optional[float]
    pasp_echo: Optional[float]
    paat_ms: Optional[float]
    rvot_notch: Optional[str]        # "ja" | "nein"
    septal_flattening: Optional[str]
    # Morphology / Congestion
    ra_esa_cm2: Optional[float]
    ivc_diam_mm: Optional[float]
    ivc_collapse_index_pct: Optional[float]
    ivc_collapse: Optional[str]      # "ja" (>50%) | "nein"
    rv_edd_mm: Optional[float]
    rv_wall_thickness_mm: Optional[float]
    # Flags
    pericardial_effusion: Optional[str]
    shunts: Optional[str]

@dataclass
class ClinicalScenario:
    title: str
    description: str
    ui: EchoUI


# --- 3. Physics & Logic Engine (Validation Layer) ---

def _estimate_rap_ase(ivc: Optional[float], coll_pct: Optional[float], coll_flag: Optional[str]) -> int:
    """
    Estimates RAP based on ASE Guidelines (Simplified for Validation).
    """
    if ivc is None: 
        return 8  # Neutral default
    
    # Normalize Collapse input (Use Index if available, else Flag)
    is_collapsing = False
    if coll_pct is not None:
        is_collapsing = (coll_pct > 50)
    elif coll_flag is not None:
        is_collapsing = (coll_flag == "ja")

    # ASE Logic
    if ivc <= 21:
        return 3 if is_collapsing else 8
    else: # Dilated > 21mm
        return 8 if is_collapsing else 15

def _validate_hemodynamics(ui: EchoUI) -> List[str]:
    """
    MASTERMIND CHECK:
    Verifies if input data obeys hemodynamic laws (Bernoulli) and mathematical logic.
    Prevents 'Garbage In -> Garbage Out'.
    """
    warnings = []
    
    # 1. Bernoulli Consistency Check (sPAP vs TRV)
    # sPAP = 4 * v^2 + RAP
    trv = ui.get("trv_ms")
    spap = ui.get("pasp_echo")
    
    if trv is not None and spap is not None:
        rap_est = _estimate_rap_ase(
            ui.get("ivc_diam_mm"), 
            ui.get("ivc_collapse_index_pct"), 
            ui.get("ivc_collapse")
        )
        
        spap_calc = 4 * (trv ** 2) + rap_est
        
        # Tolerance: +/- 15 mmHg (covers angle error & RAP uncertainty)
        if abs(spap - spap_calc) > 15:
            warnings.append(
                f"⛔ PHYSICS VIOLATION: sPAP ({spap}) inconsistent with TRV ({trv}m/s). "
                f"Bernoulli implies ~{int(spap_calc)} mmHg (assuming RAP ~{rap_est})."
            )

    # 2. Coupling Ratio Math Check
    tapse = ui.get("tapse_mm")
    ratio = ui.get("tapse_spap_ratio")
    
    if tapse is not None and spap is not None and spap > 0 and ratio is not None:
        calc_ratio = tapse / spap
        if abs(ratio - calc_ratio) > 0.05:
             warnings.append(
                 f"⚠️ MATH ERROR: TAPSE/sPAP Ratio ({ratio}) matches neither TAPSE nor sPAP."
             )

    return warnings


# --- 4. Performance Benchmarking (Developer Experience) ---

class BenchmarkTimer:
    """Context manager for precise micro-benchmarking."""
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end = time.perf_counter()
        self.interval_ms = (self.end - self.start) * 1000

    def report(self, label: str) -> str:
        return f"⏱️  {label:<15}: {self.interval_ms:.3f} ms"


# --- 5. Main Test Suite ---

def get_scenarios() -> List[ClinicalScenario]:
    # Case 1: Severe Decompensated PH
    case_severe = ClinicalScenario(
        title="Phenotype: Severe PH (RV Failure)",
        description="High Pressure, Low Function, Congestion (RAP High)",
        ui={
            "echo_done": True, "cmr_done": False,
            "tapse_mm": 13, "s_prime_cm_s": 8.0, "rvfac_pct": 25,
            "rv_fwls_pct": -12, "tapse_spap_ratio": 0.15,
            "trv_ms": 4.2, "pasp_echo": 85, "paat_ms": 60,
            "rvot_notch": "ja", "septal_flattening": "D-Shape in Systole",
            "ra_esa_cm2": 28, "ivc_diam_mm": 26, "ivc_collapse_index_pct": 10,
            "ivc_collapse": "nein", 
            "pericardial_effusion": "ja"
        }
    )

    # Case 2: Inconsistent Input (Physics Test)
    # TRV 4.0m/s implies Gradient 64. RAP is low. sPAP 35 is impossible.
    case_impossible = ClinicalScenario(
        title="Validation: Impossible Physics (Data Error)",
        description="TRV 4.0 m/s but sPAP 35 mmHg -> Should trigger alert.",
        ui={
            "echo_done": True, "cmr_done": False,
            "tapse_mm": 22, "s_prime_cm_s": 12.0,
            "trv_ms": 4.0, "pasp_echo": 35, # <--- ERROR
            "ivc_diam_mm": 15, "ivc_collapse_index_pct": 60, "ivc_collapse": "ja",
            "pericardial_effusion": "nein"
        }
    )

    # Case 3: Normal Findings
    case_normal = ClinicalScenario(
        title="Phenotype: Normal Findings",
        description="Healthy Control.",
        ui={
            "echo_done": True, "cmr_done": False,
            "tapse_mm": 24, "s_prime_cm_s": 14.0, "rvfac_pct": 45,
            "rv_fwls_pct": -26, "tapse_spap_ratio": 1.1,
            "trv_ms": 2.1, "pasp_echo": 22, "paat_ms": 140,
            "rvot_notch": "nein", "septal_flattening": "nein",
            "ra_esa_cm2": 12, "ivc_diam_mm": 14, "ivc_collapse_index_pct": 70,
            "ivc_collapse": "ja", 
            "pericardial_effusion": "nein"
        }
    )

    return [case_severe, case_impossible, case_normal]


def run_suite():
    print(f"🚀 Starting Echo Report Benchmark ({'LIVE' if CORE_AVAILABLE else 'MOCK'})")
    print("=" * 80 + "\n")

    for i, scenario in enumerate(get_scenarios(), 1):
        print(f"🔬 CASE {i}: {scenario.title}")
        print(f"   Context: {scenario.description}")
        print("-" * 60)

        # A) Validation Phase
        alerts = _validate_hemodynamics(scenario.ui)
        if alerts:
            print("   [🚨 PHYSICS/LOGIC ALERTS]")
            for a in alerts:
                print(f"   -> {a}")
            print("-" * 40)
        else:
            print("   [✅ DATA INTEGRITY CHECK PASSED]")

        # B) Execution Phase
        case_payload = {"ui": dict(scenario.ui), "derived": {}}
        
        try:
            with BenchmarkTimer() as t_pat:
                pat_rep = build_echo_patient_report(case_payload)
            
            with BenchmarkTimer() as t_doc:
                doc_rep = build_echo_doctor_report_extended(case_payload)

            # C) Output Summary
            print(f"\n   📄 Report Generation Telemetry:")
            print(f"      {t_pat.report('Patient Report')}")
            print(f"      {t_doc.report('Doctor Report')}")

            print(f"\n   🔎 Doctor Report Preview:")
            # Show first non-empty lines
            lines = [L for L in doc_rep.split('\n') if L.strip()]
            for line in lines[:4]:
                print(f"      > {line}")
            if len(lines) > 4: print("      > [...]")

        except Exception as e:
            print(f"   ❌ RUNTIME ERROR: {e}")

        print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    run_suite()