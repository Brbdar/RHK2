import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import rhk_textdb_patient as tdb_de
import rhk_textdb_patient_en as tdb_en
import rhk_textdb_patient_zh as tdb_zh
from rhk_base import load_textdb_blocks
from rhk_textdb import BUNDLES

# ---------------------------------------------------------------------------
# Doctor TextDB: blocks have required fields
# ---------------------------------------------------------------------------

def test_all_doctor_blocks_have_required_fields():
    blocks = load_textdb_blocks()
    assert len(blocks) > 0, "No blocks loaded"
    for bid, blk in blocks.items():
        assert bid, "Block has empty id"
        assert blk.title, f"Block {bid} has empty title"
        # variants dict should exist (may be empty for simple blocks)
        # template should be a non-empty string
        tmpl = getattr(blk, "template", None)
        variants = getattr(blk, "variants", None)
        assert tmpl or variants, f"Block {bid} has neither template nor variants"


def test_bundle_ids_map_to_valid_block_ids():
    blocks = load_textdb_blocks()
    for bundle_id, sections in BUNDLES.items():
        assert isinstance(sections, dict), f"Bundle {bundle_id} is not a dict"
        for section_name, block_ids in sections.items():
            assert isinstance(block_ids, list), f"Bundle {bundle_id}.{section_name} is not a list"
            for bid in block_ids:
                assert bid in blocks, f"Bundle {bundle_id} references missing block {bid}"


# ---------------------------------------------------------------------------
# Patient TextDB (DE): blocks have required fields
# ---------------------------------------------------------------------------

def test_patient_de_blocks_have_required_fields():
    blocks = tdb_de.PATIENT_BLOCKS
    assert len(blocks) > 0, "DE patient blocks empty"
    for bid, blk in blocks.items():
        assert blk.id == bid, f"Block id mismatch: key={bid}, id={blk.id}"
        assert blk.title, f"Block {bid} has empty title"
        assert len(blk.templates) > 0, f"Block {bid} has no templates"


def test_patient_de_bundles_reference_valid_blocks():
    blocks = tdb_de.PATIENT_BLOCKS
    for bundle_id, block_ids in tdb_de.PATIENT_BUNDLES.items():
        for bid in block_ids:
            assert bid in blocks, f"DE bundle {bundle_id} references missing block {bid}"


def test_patient_de_module_summary_has_expected_keys():
    summary = tdb_de.PATIENT_MODULE_SUMMARY
    # At minimum P01 through P11 should exist
    for i in range(1, 12):
        key = f"P{i:02d}"
        assert key in summary, f"DE module summary missing {key}"
        assert len(summary[key]) > 10, f"DE module summary {key} is too short"


# ---------------------------------------------------------------------------
# Patient TextDB (EN): blocks have required fields
# ---------------------------------------------------------------------------

def test_patient_en_blocks_have_required_fields():
    blocks = tdb_en.PATIENT_BLOCKS
    assert len(blocks) > 0, "EN patient blocks empty"
    for bid, blk in blocks.items():
        assert blk.id == bid
        assert blk.title, f"EN block {bid} has empty title"
        assert len(blk.templates) > 0, f"EN block {bid} has no templates"


def test_patient_en_bundles_reference_valid_blocks():
    blocks = tdb_en.PATIENT_BLOCKS
    for bundle_id, block_ids in tdb_en.PATIENT_BUNDLES.items():
        for bid in block_ids:
            assert bid in blocks, f"EN bundle {bundle_id} references missing block {bid}"


def test_patient_en_module_summary_has_expected_keys():
    summary = tdb_en.PATIENT_MODULE_SUMMARY
    for i in range(1, 12):
        key = f"P{i:02d}"
        assert key in summary, f"EN module summary missing {key}"


# ---------------------------------------------------------------------------
# Patient TextDB (ZH): blocks have required fields
# ---------------------------------------------------------------------------

def test_patient_zh_blocks_have_required_fields():
    blocks = tdb_zh.PATIENT_BLOCKS
    assert len(blocks) > 0, "ZH patient blocks empty"
    for bid, blk in blocks.items():
        assert blk.id == bid
        assert blk.title, f"ZH block {bid} has empty title"
        assert len(blk.templates) > 0, f"ZH block {bid} has no templates"


def test_patient_zh_bundles_reference_valid_blocks():
    blocks = tdb_zh.PATIENT_BLOCKS
    for bundle_id, block_ids in tdb_zh.PATIENT_BUNDLES.items():
        for bid in block_ids:
            assert bid in blocks, f"ZH bundle {bundle_id} references missing block {bid}"


# ---------------------------------------------------------------------------
# Cross-language parity
# ---------------------------------------------------------------------------

def test_de_en_zh_have_same_block_count():
    de_count = len(tdb_de.PATIENT_BLOCKS)
    en_count = len(tdb_en.PATIENT_BLOCKS)
    zh_count = len(tdb_zh.PATIENT_BLOCKS)
    assert de_count == en_count, f"DE ({de_count}) and EN ({en_count}) block counts differ"
    assert de_count == zh_count, f"DE ({de_count}) and ZH ({zh_count}) block counts differ"


def test_de_en_zh_have_same_block_ids():
    de_ids = set(tdb_de.PATIENT_BLOCKS.keys())
    en_ids = set(tdb_en.PATIENT_BLOCKS.keys())
    zh_ids = set(tdb_zh.PATIENT_BLOCKS.keys())
    assert de_ids == en_ids, f"DE/EN block id mismatch: DE-only={de_ids - en_ids}, EN-only={en_ids - de_ids}"
    assert de_ids == zh_ids, f"DE/ZH block id mismatch: DE-only={de_ids - zh_ids}, ZH-only={zh_ids - de_ids}"


def test_de_en_zh_bundles_have_same_keys():
    de_keys = set(tdb_de.PATIENT_BUNDLES.keys())
    en_keys = set(tdb_en.PATIENT_BUNDLES.keys())
    zh_keys = set(tdb_zh.PATIENT_BUNDLES.keys())
    assert de_keys == en_keys, "DE/EN bundle key mismatch"
    assert de_keys == zh_keys, "DE/ZH bundle key mismatch"


def test_de_en_zh_module_summary_have_same_keys():
    de_keys = set(tdb_de.PATIENT_MODULE_SUMMARY.keys())
    en_keys = set(tdb_en.PATIENT_MODULE_SUMMARY.keys())
    zh_keys = set(tdb_zh.PATIENT_MODULE_SUMMARY.keys())
    assert de_keys == en_keys, f"DE/EN module summary key mismatch: DE-only={de_keys - en_keys}, EN-only={en_keys - de_keys}"
    assert de_keys == zh_keys, f"DE/ZH module summary key mismatch: DE-only={de_keys - zh_keys}, ZH-only={zh_keys - de_keys}"
