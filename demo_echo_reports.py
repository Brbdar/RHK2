#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal demo for Echo report output (before/after manual inspection).

Run:
  python demo_echo_reports.py

This script does NOT modify any project data. It only prints generated reports.
"""

from rhk_reports import build_echo_patient_report, build_echo_doctor_report_extended


def _case_example() -> dict:
    return {
        "ui": {
            "echo_done": True,
            "cmr_done": False,
            # RV function
            "tapse_mm": 15,
            "s_prime_cm_s": 8.8,
            "rvfac_pct": 32,
            "rv_3d_ef_pct": None,
            "rv_fwls_pct": -14,
            "tapse_spap_ratio": 0.25,
            # pressure signs
            "trv_ms": 3.6,
            "pasp_echo": 65,
            "paat_ms": 85,
            "rvot_notch": "ja",
            "septal_flattening": "D-Shape in Systole",
            # RA/IVC
            "ra_esa_cm2": 22,
            "ivc_diam_mm": 24,
            "ivc_collapse_index_pct": 30,
            "ivc_collapse": "nein",
            # Pericard
            "pericardial_effusion": "nein",
        },
        "derived": {},
    }


if __name__ == "__main__":
    case = _case_example()
    print("=" * 80)
    print("PATIENT*INNEN ECHO REPORT")
    print("=" * 80)
    print(build_echo_patient_report(case))
    print()
    print("=" * 80)
    print("ARZT ECHO REPORT")
    print("=" * 80)
    print(build_echo_doctor_report_extended(case))
