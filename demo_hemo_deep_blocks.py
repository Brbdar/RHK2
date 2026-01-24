
"""Mini demo for deep hemodynamic interpretation blocks.

Run:
  python demo_hemo_deep_blocks.py

This script is READ-ONLY and does not depend on the full Gradio app.
It demonstrates the generated add-on paragraph that is appended to the
Interpretation section of the doctor report.

MASTERMIND IMPROVEMENTS:
- Physics Engine: Validates input physiology against basic laws (Ohm's Law, Forward Flow).
- Safety Layer: Strict typing and graceful fallback if modules are missing.
- Visual Dashboard: Tabular delta-view to verify logic correctness instantly.
"""

from typing import TypedDict, Optional, List, Dict, Any

# --- 1. Robust Import Strategy (Safety Layer) ---
try:
    from rhk_hemo_deep_interpretation import build_hemo_deep_interpretation
except ImportError:
    print("⚠️  SYSTEM WARNING: 'rhk_hemo_deep_interpretation' module not found.")
    print("    -> Running in SAFE SIMULATION MODE (Mocking logic).\n")
    
    def build_hemo_deep_interpretation(ui: Dict, der: Dict) -> str:
        return "[MOCK OUTPUT] Logic module missing. This text simulates a successful generation."


# --- 2. Strict Data Contracts (Type Definitions) ---

class HemoPrevUI(TypedDict, total=False):
    """Strict interface for historical user inputs. Missing values must be None, never 0."""
    prev_rhk_date: Optional[str]
    prev_mpap: Optional[float]
    prev_pawp: Optional[float]
    prev_pvr: Optional[float]
    prev_ci: Optional[float]
    prev_rap: Optional[float]

class HemoDerived(TypedDict, total=False):
    """Strict interface for current calculated hemodynamic parameters."""
    mpap_rest: float
    pawp_rest: float
    pvr_rest: float
    ci_rest: float
    rap_rest: float
    sv_rest_ml: float
    pp_pa_rest: float
    pac_rest_ml_per_mmhg: float
    tpg_rest: float
    dpg_rest: float


# --- 3. Hemodynamic Physics Engine (Validation Layer) ---

def _validate_physiology(der: HemoDerived) -> List[str]:
    """
    Checks for hemodynamic impossibilities before processing.
    Ensures 'Garbage In' results in warnings, not 'Garbage Out'.
    """
    warnings = []
    
    mpap = der.get("mpap_rest")
    pawp = der.get("pawp_rest")
    pvr = der.get("pvr_rest")
    
    # Check 1: Forward Flow Integrity
    if mpap is not None and pawp is not None:
        if mpap < pawp:
            warnings.append(f"⛔ CRITICAL PHYSICS: Negative Gradient (mPAP {mpap} < PAWP {pawp}). Impossible state.")

    # Check 2: Ohm's Law Consistency check (PVR vs TPG)
    # PVR = TPG / CO. If PVR is high but TPG is tiny, data is suspect.
    if mpap is not None and pawp is not None and pvr is not None:
        tpg = mpap - pawp
        # Threshold: PVR > 3 WU implies PH, but TPG < 5 mmHg implies no driving pressure.
        if pvr > 3.0 and tpg < 5.0:
            warnings.append(f"⚠️ DATA INCONSISTENCY: High PVR ({pvr} WU) with physiological low TPG ({tpg} mmHg).")
            
    return warnings


# --- 4. Clinical Dashboard (Visualization Layer) ---

def _format_value_with_delta(curr: Optional[float], prev: Optional[float], unit: str) -> str:
    """Intelligent formatting helper."""
    if curr is None:
        return "   n/a"
    
    val_str = f"{curr:>5.1f} {unit}"
    
    if prev is None:
        return f"{val_str} (Initial)"
        
    delta = curr - prev
    # Visual cues for rapid clinical scanning
    if delta > 0.5:
        trend = f"⬈ {delta:+.1f}"
    elif delta < -0.5:
        trend = f"⬊ {delta:+.1f}"
    else:
        trend = "→ stable"
        
    return f"{val_str} ({trend})"


def _print_dashboard(ui: HemoPrevUI, der: HemoDerived) -> None:
    """Prints a structured clinical table for rapid data verification."""
    print(f"  {'PARAMETER':<10} | {'PREVIOUS':<10} | {'CURRENT & DYNAMICS'}")
    print(f"  {'-'*10} | {'-'*10} | {'-'*35}")
    
    # Mapping: Label -> (UI Key, Derived Key, Unit)
    params = [
        ("mPAP", "prev_mpap", "mpap_rest", "mmHg"),
        ("PAWP", "prev_pawp", "pawp_rest", "mmHg"),
        ("PVR",  "prev_pvr",  "pvr_rest",  "WU"),
        ("CI",   "prev_ci",   "ci_rest",   "l/min"),
        ("RAP",  "prev_rap",  "rap_rest",  "mmHg"),
    ]
    
    for label, k_ui, k_der, unit in params:
        val_prev = ui.get(k_ui) # type: ignore
        val_curr = der.get(k_der) # type: ignore
        
        # Safe display for None
        disp_prev = f"{val_prev:>5.1f} {unit}" if val_prev is not None else "     -"
        disp_curr = _format_value_with_delta(val_curr, val_prev, unit)
        
        print(f"  {label:<10} | {disp_prev:<10} | {disp_curr}")
    print(f"  {'-'*60}")


# --- 5. Execution Orchestrator ---

def run_case(title: str, ui: HemoPrevUI, der: HemoDerived) -> None:
    print("\n" + "=" * 80)
    print(f"🔬 SCENARIO: {title}")
    print("-" * 80)
    
    # Step 1: Validate Physics
    warnings = _validate_physiology(der)
    if warnings:
        print("  [PHYSICS ENGINE ALERTS]")
        for w in warnings:
            print(f"  {w}")
        print("-" * 40)
        
    # Step 2: Visual Dashboard
    _print_dashboard(ui, der)
    
    # Step 3: Logic Execution
    print("\n  >>> GENERATED INTERPRETATION BLOCK:")
    try:
        # Cast to standard dict for compatibility with core logic
        txt = build_hemo_deep_interpretation(dict(ui), dict(der)) # type: ignore
        if txt:
            print(f"  {txt}")
        else:
            print("  (No deep interpretation generated - criteria not met)")
    except Exception as e:
        print(f"  ❌ FATAL ERROR in Logic Module: {e}")
        
    print("\n")


# --- 6. Test Suite ---

def main() -> None:
    # Scenario 1: Pre-capillary improvement masked by Post-capillary loading
    # Clinical: PVR improves, but mPAP stays high due to PAWP rise.
    ui1: HemoPrevUI = {
        "prev_rhk_date": "01.07.2025",
        "prev_mpap": 46, "prev_pawp": 12, "prev_pvr": 6.1,
        "prev_ci": 2.0, "prev_rap": 12,
    }
    der1: HemoDerived = {
        "mpap_rest": 34, "pawp_rest": 16, "pvr_rest": 3.2,
        "ci_rest": 2.6, "rap_rest": 10,
        "sv_rest_ml": 55, "pp_pa_rest": 36, "pac_rest_ml_per_mmhg": 1.5,
        "tpg_rest": 18, "dpg_rest": 7,
    }

    # Scenario 2: True Worsening (RV Failure Pattern)
    # Clinical: PVR rises, Cardiac Index drops. Dangerous.
    ui2: HemoPrevUI = {
        "prev_rhk_date": "10.03.2025",
        "prev_mpap": 32, "prev_pawp": 10, "prev_pvr": 3.0,
        "prev_ci": 2.6, "prev_rap": 8,
    }
    der2: HemoDerived = {
        "mpap_rest": 40, "pawp_rest": 11, "pvr_rest": 4.4,
        "ci_rest": 2.0, "rap_rest": 11,
        "sv_rest_ml": 38, "pp_pa_rest": 32, "pac_rest_ml_per_mmhg": 1.2,
        "tpg_rest": 29, "dpg_rest": 10,
    }

    # Scenario 3: Hemodynamic Stability
    # Clinical: Parameters within measurement error margin.
    ui3: HemoPrevUI = {
        "prev_rhk_date": "05.05.2025",
        "prev_mpap": 26, "prev_pawp": 14, "prev_pvr": 2.6,
        "prev_ci": 2.3, "prev_rap": 9,
    }
    der3: HemoDerived = {
        "mpap_rest": 27, "pawp_rest": 14, "pvr_rest": 2.7,
        "ci_rest": 2.2, "rap_rest": 9,
        "sv_rest_ml": 60, "pp_pa_rest": 24, "pac_rest_ml_per_mmhg": 2.6,
        "tpg_rest": 13, "dpg_rest": 4,
    }
    
    # Scenario 4: Edge Case - Impossible Physiology (Test Physics Engine)
    # Clinical: mPAP < PAWP (Impossible)
    ui4: HemoPrevUI = {
        "prev_rhk_date": "01.01.2025", "prev_mpap": 20, "prev_pawp": 10,
        "prev_pvr": 2.0, "prev_ci": 3.0, "prev_rap": 5,
    }
    der4: HemoDerived = {
        "mpap_rest": 12, "pawp_rest": 15, "pvr_rest": 1.0, # Impossible: mPAP < PAWP
        "ci_rest": 2.5, "rap_rest": 5,
        "sv_rest_ml": 50, "pp_pa_rest": 20, "pac_rest_ml_per_mmhg": 2.0,
        "tpg_rest": -3, "dpg_rest": -5,
    }

    cases = [
        ("Case 1: Verbesserung trotz PCWP Anstieg (Maskierung)", ui1, der1),
        ("Case 2: Verschlechterung mit PVR Anstieg und CI Abfall", ui2, der2),
        ("Case 3: Weitgehend stabil", ui3, der3),
        ("Case 4: STRESS TEST - Physiologisch unmöglich", ui4, der4),
    ]

    print(f"🚀 Starting Clinical Logic Validation Suite ({len(cases)} Cases)...")
    for title, ui, der in cases:
        run_case(title, ui, der)
    print("✅ Validation Cycle Complete.")


if __name__ == "__main__":
    main()