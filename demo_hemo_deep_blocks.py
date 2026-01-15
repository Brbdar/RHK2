"""Mini demo for deep hemodynamic interpretation blocks.

Run:
  python demo_hemo_deep_blocks.py

This script is READ-ONLY and does not depend on the full Gradio app.
It demonstrates the generated add-on paragraph that is appended to the
Interpretation section of the doctor report.
"""

from rhk_hemo_deep_interpretation import build_hemo_deep_interpretation


def _case(title: str, ui: dict, der: dict) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("-" * 90)
    txt = build_hemo_deep_interpretation(ui, der)
    print(txt or "(no deep interpretation generated)")


def main() -> None:
    # Case 1: Improvement despite PCWP up
    ui1 = {
        "prev_rhk_date": "01.07.2025",
        "prev_mpap": 46,
        "prev_pawp": 12,
        "prev_pvr": 6.1,
        "prev_ci": 2.0,
        "prev_rap": 12,
    }
    der1 = {
        "mpap_rest": 34,
        "pawp_rest": 16,
        "pvr_rest": 3.2,
        "ci_rest": 2.6,
        "rap_rest": 10,
        "sv_rest_ml": 55,
        "pp_pa_rest": 36,
        "pac_rest_ml_per_mmhg": 1.5,
        "tpg_rest": 18,
        "dpg_rest": 7,
    }

    # Case 2: Worsening, PVR up + CI down
    ui2 = {
        "prev_rhk_date": "10.03.2025",
        "prev_mpap": 32,
        "prev_pawp": 10,
        "prev_pvr": 3.0,
        "prev_ci": 2.6,
        "prev_rap": 8,
    }
    der2 = {
        "mpap_rest": 40,
        "pawp_rest": 11,
        "pvr_rest": 4.4,
        "ci_rest": 2.0,
        "rap_rest": 11,
        "sv_rest_ml": 38,
        "pp_pa_rest": 32,
        "pac_rest_ml_per_mmhg": 1.2,
        "tpg_rest": 29,
        "dpg_rest": 10,
    }

    # Case 3: Stable main parameters (should generate stable sentence; minimal secondary)
    ui3 = {
        "prev_rhk_date": "05.05.2025",
        "prev_mpap": 26,
        "prev_pawp": 14,
        "prev_pvr": 2.6,
        "prev_ci": 2.3,
        "prev_rap": 9,
    }
    der3 = {
        "mpap_rest": 27,
        "pawp_rest": 14,
        "pvr_rest": 2.7,
        "ci_rest": 2.2,
        "rap_rest": 9,
        "sv_rest_ml": 60,
        "pp_pa_rest": 24,
        "pac_rest_ml_per_mmhg": 2.6,
        "tpg_rest": 13,
        "dpg_rest": 4,
    }

    _case("Case 1: Verbesserung trotz PCWP Anstieg", ui1, der1)
    _case("Case 2: Verschlechterung mit PVR Anstieg und CI Abfall", ui2, der2)
    _case("Case 3: Weitgehend stabil", ui3, der3)


if __name__ == "__main__":
    main()
