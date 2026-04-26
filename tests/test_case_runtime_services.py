import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_case_migrations import CURRENT_CASE_SCHEMA_VERSION, migrate_case_payload, stamp_case_payload
from rhk_case_service import prepare_case_runtime_input


def test_prepare_case_runtime_input_seeds_modules_and_egfr_for_clean_case():
    raw, base_case = prepare_case_runtime_input(
        raw_ui={
            "creatinine_mg_dl": 1.0,
            "age": 50,
            "sex": "männlich",
            "modules_lvl1": [],
            "modules_lvl2": [],
            "modules_lvl3": [],
            "modules": [],
        },
        case_state_in={"ui": {"firstname": "Max"}},
        pmods_state={"lvl1": ["P01"], "lvl2": ["P11"], "lvl3": []},
        flags={"dirty": False, "has_report": False},
    )

    assert base_case["ui"]["firstname"] == "Max"
    assert raw["firstname"] == "Max"
    assert raw["modules"] == ["P01", "P11"]
    assert raw["egfr"] == raw["egfr_ml_min_1_73"]
    assert isinstance(raw["egfr"], int)


def test_prepare_case_runtime_input_prefers_explicit_module_selection():
    raw, _base_case = prepare_case_runtime_input(
        raw_ui={
            "modules_lvl1": ["P03"],
            "modules_lvl2": [],
            "modules_lvl3": ["P21"],
            "modules": ["P99"],
        },
        case_state_in=None,
        pmods_state={"lvl1": ["P01"], "lvl2": ["P11"], "lvl3": []},
        flags={"dirty": True, "has_report": True},
    )

    assert raw["modules"] == ["P03", "P21", "P99"]


def test_case_payload_migration_and_stamp_attach_schema_metadata():
    migrated = migrate_case_payload({"ui": {"age": 42}})
    stamped = stamp_case_payload({"ui": {"age": 42}})

    assert migrated["_meta"]["schema_version"] == CURRENT_CASE_SCHEMA_VERSION
    assert stamped["_meta"]["schema_version"] == CURRENT_CASE_SCHEMA_VERSION
    assert "saved_at" in stamped["_meta"]
    assert stamped["ui"]["age"] == 42
