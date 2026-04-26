import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_config import (
    EXERCISE_PATTERN_LABELS,
    FALSE_TOKENS,
    FIELD_LABELS,
    MISSING_TOKENS,
    SEV_BG,
    SEV_BORDER,
    SEV_RANK,
    TRUE_TOKENS,
    WARNING_LEVEL_LABEL,
    WARNING_LEVEL_ORDER,
)

# ---------------------------------------------------------------------------
# SEV_RANK
# ---------------------------------------------------------------------------

def test_sev_rank_has_expected_keys():
    assert "" in SEV_RANK
    assert "g" in SEV_RANK
    assert "y" in SEV_RANK
    assert "r" in SEV_RANK


def test_sev_rank_order():
    assert SEV_RANK[""] < SEV_RANK["g"] < SEV_RANK["y"] < SEV_RANK["r"]


def test_sev_rank_values_are_ints():
    for k, v in SEV_RANK.items():
        assert isinstance(v, int), f"SEV_RANK[{k!r}] is {type(v)}, expected int"


# ---------------------------------------------------------------------------
# SEV_BG / SEV_BORDER
# ---------------------------------------------------------------------------

def test_sev_bg_has_expected_keys():
    for key in ("g", "y", "r", ""):
        assert key in SEV_BG


def test_sev_border_has_expected_keys():
    for key in ("g", "y", "r", ""):
        assert key in SEV_BORDER


def test_sev_bg_values_are_strings():
    for v in SEV_BG.values():
        assert isinstance(v, str)


def test_sev_border_values_are_strings():
    for v in SEV_BORDER.values():
        assert isinstance(v, str)


# ---------------------------------------------------------------------------
# WARNING_LEVEL
# ---------------------------------------------------------------------------

def test_warning_level_order_keys():
    assert "hint" in WARNING_LEVEL_ORDER
    assert "important" in WARNING_LEVEL_ORDER
    assert "critical" in WARNING_LEVEL_ORDER


def test_warning_level_order_is_ascending():
    assert WARNING_LEVEL_ORDER["hint"] < WARNING_LEVEL_ORDER["important"] < WARNING_LEVEL_ORDER["critical"]


def test_warning_level_label_keys_match_order():
    assert set(WARNING_LEVEL_LABEL.keys()) == set(WARNING_LEVEL_ORDER.keys())


def test_warning_level_labels_non_empty():
    for k, v in WARNING_LEVEL_LABEL.items():
        assert v, f"WARNING_LEVEL_LABEL[{k!r}] is empty"


# ---------------------------------------------------------------------------
# Token sets are frozensets
# ---------------------------------------------------------------------------

def test_true_tokens_is_frozenset():
    assert isinstance(TRUE_TOKENS, frozenset)


def test_false_tokens_is_frozenset():
    assert isinstance(FALSE_TOKENS, frozenset)


def test_missing_tokens_is_frozenset():
    assert isinstance(MISSING_TOKENS, frozenset)


def test_true_tokens_not_empty():
    assert len(TRUE_TOKENS) > 0


def test_false_tokens_not_empty():
    assert len(FALSE_TOKENS) > 0


def test_missing_tokens_not_empty():
    assert len(MISSING_TOKENS) > 0


def test_true_false_tokens_no_overlap():
    # Except for empty string which is only in FALSE_TOKENS
    overlap = TRUE_TOKENS & FALSE_TOKENS
    assert overlap == frozenset() or overlap == frozenset({""}), f"Unexpected overlap: {overlap}"


def test_common_true_tokens_present():
    for t in ("1", "true", "yes", "ja"):
        assert t in TRUE_TOKENS, f"Missing true token: {t}"


def test_common_false_tokens_present():
    for t in ("0", "false", "no", "nein"):
        assert t in FALSE_TOKENS, f"Missing false token: {t}"


# ---------------------------------------------------------------------------
# FIELD_LABELS
# ---------------------------------------------------------------------------

def test_field_labels_not_empty():
    assert len(FIELD_LABELS) > 0


def test_field_labels_values_are_non_empty_strings():
    for k, v in FIELD_LABELS.items():
        assert isinstance(v, str) and v, f"FIELD_LABELS[{k!r}] is empty or not a string"


def test_field_labels_has_core_hemodynamic_keys():
    for key in ("mpap_rest", "pawp_rest", "pvr_rest", "ci_rest", "co_rest"):
        assert key in FIELD_LABELS, f"FIELD_LABELS missing {key}"


# ---------------------------------------------------------------------------
# EXERCISE_PATTERN_LABELS
# ---------------------------------------------------------------------------

def test_exercise_pattern_labels_not_empty():
    assert len(EXERCISE_PATTERN_LABELS) > 0


def test_exercise_pattern_labels_values_are_non_empty_strings():
    for k, v in EXERCISE_PATTERN_LABELS.items():
        assert isinstance(v, str) and v, f"EXERCISE_PATTERN_LABELS[{k!r}] is empty"


# ---------------------------------------------------------------------------
# No empty values in any config dict
# ---------------------------------------------------------------------------

def test_no_none_values_in_config_dicts():
    for name, d in [
        ("SEV_RANK", SEV_RANK),
        ("SEV_BG", SEV_BG),
        ("SEV_BORDER", SEV_BORDER),
        ("WARNING_LEVEL_ORDER", WARNING_LEVEL_ORDER),
        ("WARNING_LEVEL_LABEL", WARNING_LEVEL_LABEL),
        ("FIELD_LABELS", FIELD_LABELS),
        ("EXERCISE_PATTERN_LABELS", EXERCISE_PATTERN_LABELS),
    ]:
        for k, v in d.items():
            assert v is not None, f"{name}[{k!r}] is None"
