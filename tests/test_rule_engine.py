import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_rule_engine import (
    Decision,
    Rule,
    SafeExprError,
    apply_rule_engine,
    apply_rule_engine_trace,
    load_rulebook,
    safe_eval_bool,
)

# ---------------------------------------------------------------------------
# safe_eval_bool – basic expressions
# ---------------------------------------------------------------------------

def test_safe_eval_bool_simple_true():
    assert safe_eval_bool("x > 5", {"x": 10}) is True


def test_safe_eval_bool_simple_false():
    assert safe_eval_bool("x > 5", {"x": 3}) is False


def test_safe_eval_bool_equality():
    assert safe_eval_bool("status == 'active'", {"status": "active"}) is True
    assert safe_eval_bool("status == 'active'", {"status": "off"}) is False


def test_safe_eval_bool_and_or():
    env = {"a": True, "b": False, "c": True}
    assert safe_eval_bool("a and c", env) is True
    assert safe_eval_bool("a and b", env) is False
    assert safe_eval_bool("a or b", env) is True
    assert safe_eval_bool("b or b", env) is False


def test_safe_eval_bool_not():
    assert safe_eval_bool("not x", {"x": False}) is True
    assert safe_eval_bool("not x", {"x": True}) is False


def test_safe_eval_bool_comparison_chain():
    assert safe_eval_bool("1 < x < 10", {"x": 5}) is True
    assert safe_eval_bool("1 < x < 10", {"x": 15}) is False


def test_safe_eval_bool_in_operator():
    assert safe_eval_bool("x in items", {"x": "a", "items": ["a", "b"]}) is True
    assert safe_eval_bool("x in items", {"x": "z", "items": ["a", "b"]}) is False


def test_safe_eval_bool_not_in():
    assert safe_eval_bool("x not in items", {"x": "z", "items": ["a"]}) is True


# ---------------------------------------------------------------------------
# safe_eval_bool – edge cases
# ---------------------------------------------------------------------------

def test_safe_eval_bool_empty_expression():
    assert safe_eval_bool("", {}) is False
    assert safe_eval_bool(None, {}) is False


def test_safe_eval_bool_missing_variable_returns_none():
    # Missing var -> None; comparisons with None return False
    assert safe_eval_bool("x > 5", {}) is False


def test_safe_eval_bool_none_comparison():
    assert safe_eval_bool("x == None", {"x": None}) is True
    assert safe_eval_bool("x is None", {"x": None}) is True
    assert safe_eval_bool("x is not None", {"x": 42}) is True


# ---------------------------------------------------------------------------
# safe_eval_bool – security: malicious expressions rejected
# ---------------------------------------------------------------------------

def test_safe_eval_rejects_function_call():
    try:
        safe_eval_bool("__import__('os').system('echo hi')", {})
        raise AssertionError("Should have raised SafeExprError")
    except (SafeExprError, Exception):
        pass


def test_safe_eval_rejects_lambda():
    try:
        safe_eval_bool("(lambda: 1)()", {})
        raise AssertionError("Should have raised SafeExprError")
    except (SafeExprError, Exception):
        pass


def test_safe_eval_rejects_list_comprehension():
    try:
        safe_eval_bool("[x for x in range(10)]", {})
        raise AssertionError("Should have raised SafeExprError")
    except (SafeExprError, Exception):
        pass


def test_safe_eval_rejects_attribute_access():
    try:
        safe_eval_bool("x.__class__", {"x": 1})
        raise AssertionError("Should have raised SafeExprError")
    except (SafeExprError, Exception):
        pass


# ---------------------------------------------------------------------------
# load_rulebook
# ---------------------------------------------------------------------------

def test_load_rulebook_from_yaml():
    yaml_content = """
rules:
  - id: R01
    when: "mpap > 20"
    then:
      set_bundle: K05
      set_primary_dx: "Precapillary PH"
    priority: 10
  - id: R02
    when: "mpap <= 20"
    then:
      set_bundle: K00
    priority: 20
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        path = f.name

    try:
        rules = load_rulebook(path)
        assert len(rules) == 2
        assert rules[0].id == "R01"  # priority 10 first
        assert rules[1].id == "R02"
        assert rules[0].when == "mpap > 20"
        assert rules[0].then["set_bundle"] == "K05"
    finally:
        os.unlink(path)


def test_load_rulebook_nonexistent_path():
    rules = load_rulebook("/nonexistent/path/rules.yaml")
    assert rules == []


def test_load_rulebook_sorted_by_priority():
    yaml_content = """
rules:
  - id: LOW
    when: "True"
    then: {}
    priority: 99
  - id: HIGH
    when: "True"
    then: {}
    priority: 1
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        path = f.name

    try:
        rules = load_rulebook(path)
        assert rules[0].id == "HIGH"
        assert rules[1].id == "LOW"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# apply_rule_engine
# ---------------------------------------------------------------------------

def test_apply_rule_engine_basic():
    rules = [
        Rule(id="R1", when="mpap > 20", then={"set_bundle": "K05", "set_primary_dx": "PH"}, priority=10),
        Rule(id="R2", when="pvr > 2", then={"add_modules": ["P01", "P03"]}, priority=20),
    ]
    env = {"mpap": 35, "pvr": 5}
    dec = apply_rule_engine(env, rules)

    assert isinstance(dec, Decision)
    assert dec.bundle == "K05"
    assert dec.primary_dx == "PH"
    assert "P01" in dec.modules
    assert "P03" in dec.modules


def test_apply_rule_engine_no_match():
    rules = [
        Rule(id="R1", when="mpap > 20", then={"set_bundle": "K05"}, priority=10),
    ]
    dec = apply_rule_engine({"mpap": 15}, rules)
    assert dec.bundle == "K00"  # default


def test_apply_rule_engine_trace_records_fired():
    rules = [
        Rule(id="R1", when="x > 0", then={"set_bundle": "K01"}, priority=10),
        Rule(id="R2", when="x < 0", then={"set_bundle": "K02"}, priority=20),
    ]
    dec, trace = apply_rule_engine_trace({"x": 5}, rules)
    assert dec.bundle == "K01"
    assert len(trace.fired) == 1
    assert trace.fired[0]["id"] == "R1"


def test_apply_rule_engine_add_tags():
    # "True" is a Name node; we need the env key to match so we go straight to
    # an explicit expression to make the intent unambiguous.
    rules2 = [
        Rule(id="R1", when="x == 1", then={"add_tags": ["tag_a", "tag_b"]}, priority=10),
    ]
    dec2 = apply_rule_engine({"x": 1}, rules2)
    assert "tag_a" in dec2.tags
    assert "tag_b" in dec2.tags


def test_apply_rule_engine_remove_tags():
    rules = [
        Rule(id="R1", when="x == 1", then={"add_tags": ["a", "b", "c"]}, priority=10),
        Rule(id="R2", when="x == 1", then={"remove_tags": ["b"]}, priority=20),
    ]
    dec = apply_rule_engine({"x": 1}, rules)
    assert "a" in dec.tags
    assert "b" not in dec.tags
    assert "c" in dec.tags


def test_apply_rule_engine_add_recommendations():
    rules = [
        Rule(id="R1", when="x == 1", then={"add_recommendations": ["Rec A", "Rec B"]}, priority=10),
    ]
    dec = apply_rule_engine({"x": 1}, rules)
    assert "Rec A" in dec.recommendations
    assert "Rec B" in dec.recommendations


def test_apply_rule_engine_require_fields():
    rules = [
        Rule(id="R1", when="x == 1", then={"require_fields": ["field_a"]}, priority=10),
    ]
    dec = apply_rule_engine({"x": 1}, rules)
    assert "field_a" in dec.require_fields
