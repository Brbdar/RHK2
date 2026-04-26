#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Declarative rule-engine primitives and evaluators.

This module is extracted from ``rhk_base.py`` to keep the base module focused
on medical calculations and text/database helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass
class Rule:
    """A single declarative rule with a boolean guard and action payload."""

    id: str
    when: str
    then: Dict[str, Any]
    priority: int = 100


@dataclass
class Decision:
    """Accumulated output of the rule engine (diagnosis, modules, recommendations)."""

    bundle: str = "K00"
    primary_dx: str = "—"
    modules: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    require_fields: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    leading_cause: Optional[str] = None
    leading_action: Optional[str] = None


@dataclass
class RuleTrace:
    """Debug trace recording which rules fired and which caused errors."""

    fired: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


class SafeExprError(Exception):
    """Raised for unsupported expressions in safe rule evaluation."""


_ALLOWED_NODES = (
    "Expression",
    "BoolOp",
    "BinOp",
    "UnaryOp",
    "Compare",
    "Name",
    "Load",
    "Constant",
    "And",
    "Or",
    "Not",
    "Eq",
    "NotEq",
    "Lt",
    "LtE",
    "Gt",
    "GtE",
    "Is",
    "IsNot",
    "In",
    "NotIn",
)


@lru_cache(maxsize=4096)
def _safe_parse_expr(expr: str):
    import ast

    e = str(expr or "").strip()
    if not e:
        return None
    tree = ast.parse(e, mode="eval")
    for node in ast.walk(tree):
        if node.__class__.__name__ not in _ALLOWED_NODES:
            raise SafeExprError(f"Node not allowed: {node.__class__.__name__}")
    return tree


_RULEBOOK_CACHE: Dict[str, Dict[str, Any]] = {}


def safe_eval_bool(expr: str, env: Dict[str, Any]) -> bool:
    """Evaluate a boolean expression string safely against *env*.

    Only a restricted AST subset is allowed (comparisons, boolean ops, names,
    constants). Returns ``False`` for empty or invalid expressions.
    """
    import ast

    e = str(expr or "").strip()
    if not e:
        return False

    tree = _safe_parse_expr(e)
    if tree is None:
        return False

    class _Eval(ast.NodeVisitor):
        def visit_Expression(self, node):
            return self.visit(node.body)

        def visit_Name(self, node):
            return env.get(node.id)

        def visit_Constant(self, node):
            return node.value

        def visit_BoolOp(self, node):
            if isinstance(node.op, ast.And):
                return all(self.visit(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(self.visit(v) for v in node.values)
            raise SafeExprError("Unsupported BoolOp")

        def visit_UnaryOp(self, node):
            if isinstance(node.op, ast.Not):
                return not bool(self.visit(node.operand))
            raise SafeExprError("Unsupported UnaryOp")

        def visit_Compare(self, node):
            left = self.visit(node.left)
            for op, comp in zip(node.ops, node.comparators, strict=False):
                right = self.visit(comp)
                ok = None
                try:
                    if isinstance(op, ast.Eq):
                        ok = left == right
                    elif isinstance(op, ast.NotEq):
                        ok = left != right
                    elif isinstance(op, ast.Lt):
                        ok = left is not None and right is not None and left < right
                    elif isinstance(op, ast.LtE):
                        ok = left is not None and right is not None and left <= right
                    elif isinstance(op, ast.Gt):
                        ok = left is not None and right is not None and left > right
                    elif isinstance(op, ast.GtE):
                        ok = left is not None and right is not None and left >= right
                    elif isinstance(op, ast.Is):
                        ok = left is right
                    elif isinstance(op, ast.IsNot):
                        ok = left is not right
                    elif isinstance(op, ast.In):
                        ok = (left in right) if right is not None else False
                    elif isinstance(op, ast.NotIn):
                        ok = (left not in right) if right is not None else False
                    else:
                        raise SafeExprError("Unsupported Compare op")
                except Exception:
                    ok = False
                if not ok:
                    return False
                left = right
            return True

    return bool(_Eval().visit(tree))


def load_rulebook(path: str) -> List[Rule]:
    """Load and cache a YAML rulebook, returning a priority-sorted list of Rules."""
    if yaml is None:
        raise RuntimeError("PyYAML is not installed. Please add pyyaml to requirements.")
    if not os.path.exists(path):
        return []

    try:
        mtime = os.path.getmtime(path) if os.path.exists(path) else None
    except Exception:
        mtime = None

    cached = _RULEBOOK_CACHE.get(path) if path else None
    try:
        if cached and cached.get("mtime") == mtime and isinstance(cached.get("rules"), tuple):
            return list(cached["rules"])
    except Exception:
        pass

    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}

    rules: List[Rule] = []
    for r in doc.get("rules", []):
        rules.append(
            Rule(
                id=str(r.get("id")),
                when=str(r.get("when")),
                then=dict(r.get("then") or {}),
                priority=int(r.get("priority", 100)),
            )
        )

    rules.sort(key=lambda rr: rr.priority)

    try:
        _RULEBOOK_CACHE[path] = {
            "mtime": mtime,
            "rules": tuple(rules),
            "meta": (doc.get("meta") or {}) if isinstance(doc, dict) else {},
        }
    except Exception:
        pass

    return rules


def apply_rule_engine_trace(env: Dict[str, Any], rules: List[Rule]) -> Tuple[Decision, RuleTrace]:
    """Run all *rules* against *env* and return the Decision plus a debug trace."""
    d = Decision(bundle="K00", primary_dx="Kein Hinweis auf PH")
    trace = RuleTrace()

    for rule in rules:
        matched = False
        try:
            matched = safe_eval_bool(rule.when, env)
        except Exception as exc:
            trace.errors.append(
                {
                    "id": rule.id,
                    "priority": rule.priority,
                    "when": rule.when,
                    "error": str(exc),
                }
            )
            continue

        if not matched:
            continue

        trace.fired.append(
            {
                "id": rule.id,
                "priority": rule.priority,
                "when": rule.when,
                "then": rule.then,
            }
        )

        then = rule.then or {}
        if "set_bundle" in then:
            d.bundle = str(then["set_bundle"])
        if "set_primary_dx" in then:
            d.primary_dx = str(then["set_primary_dx"])
        if "set_leading_cause" in then:
            d.leading_cause = str(then["set_leading_cause"])
        if "set_leading_action" in then:
            d.leading_action = str(then["set_leading_action"])

        if "add_modules" in then:
            for mod in then.get("add_modules") or []:
                if mod not in d.modules:
                    d.modules.append(mod)
        if "add_recommendations" in then:
            for rec in then.get("add_recommendations") or []:
                if rec and rec not in d.recommendations:
                    d.recommendations.append(str(rec))

        if "require_fields" in then:
            for fld in then.get("require_fields") or []:
                if fld not in d.require_fields:
                    d.require_fields.append(str(fld))

        if "remove_tags" in then:
            for tag in then.get("remove_tags") or []:
                if not tag:
                    continue
                tag_s = str(tag)
                while tag_s in d.tags:
                    d.tags.remove(tag_s)

        if "add_tags" in then:
            for tag in then.get("add_tags") or []:
                if tag and tag not in d.tags:
                    d.tags.append(str(tag))

    return d, trace


def apply_rule_engine(env: Dict[str, Any], rules: List[Rule]) -> Decision:
    """Convenience wrapper: run rules and return only the Decision."""
    decision, _trace = apply_rule_engine_trace(env, rules)
    return decision


__all__ = [
    "Decision",
    "Rule",
    "RuleTrace",
    "SafeExprError",
    "apply_rule_engine",
    "apply_rule_engine_trace",
    "load_rulebook",
    "safe_eval_bool",
]
