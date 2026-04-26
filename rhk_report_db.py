"""Report phrase/rule database (local, DSGVO-safe).

This DB contains *generic* phrases and rules to improve report consistency.
It must never contain patient-identifiable data.

The app can run without the DB; in that case, this module returns empty
structures.

Single source of truth for medical calculations remains the case state.
This module only helps with deterministic text selection.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ReportPhrase:
    phrase_id: str
    audience: str  # 'doctor' | 'patient'
    section: str
    tags: List[str]
    priority: int
    text: str


@dataclass(frozen=True)
class ReportRule:
    rule_id: str
    safe_expr: str
    add_tags: List[str]
    include_phrases: List[str]
    exclude_phrases: List[str]
    priority: int


_cache: Dict[str, Any] = {
    "mtime": None,
    "phrases": None,
    "rules": None,
}


def _db_path() -> str:
    """Return absolute path to the local report DB.

    Supports PyInstaller (sys._MEIPASS) and normal source checkout.
    """
    # 1) PyInstaller bundle
    try:
        meipass = getattr(sys, '_MEIPASS', None)
    except Exception:
        meipass = None
    if meipass:
        cand = os.path.join(str(meipass), 'data', 'report_texts.sqlite')
        if os.path.exists(cand):
            return cand

    # 2) Source checkout (ZIP mode)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'data', 'report_texts.sqlite')


def load_report_db() -> Tuple[Dict[Tuple[str, str], ReportPhrase], List[ReportRule]]:
    """Load phrases and rules from local SQLite DB (cached by mtime).

    Returns:
        phrases: dict keyed by (phrase_id, audience)
        rules: list ordered by priority asc
    """
    path = _db_path()
    try:
        st = os.stat(path)
    except OSError:
        return {}, []

    mtime = st.st_mtime
    if _cache.get("mtime") == mtime and _cache.get("phrases") is not None and _cache.get("rules") is not None:
        return _cache["phrases"], _cache["rules"]

    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    phrases: Dict[Tuple[str, str], ReportPhrase] = {}
    for row in cur.execute(
        "SELECT phrase_id,audience,section,tags,priority,text FROM report_phrase WHERE active=1"
    ).fetchall():
        tags: List[Any] = []
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        phrases[(row["phrase_id"], row["audience"])] = ReportPhrase(
            phrase_id=row["phrase_id"],
            audience=row["audience"],
            section=row["section"],
            tags=[str(x) for x in (tags or [])],
            priority=int(row["priority"] or 100),
            text=row["text"],
        )

    rules: List[ReportRule] = []
    for row in cur.execute(
        "SELECT rule_id,safe_expr,add_tags,include_phrases,exclude_phrases,priority FROM report_rule WHERE active=1 ORDER BY priority ASC"
    ).fetchall():
        def _j(x):
            try:
                return json.loads(x) if x else []
            except (json.JSONDecodeError, TypeError):
                return []
        rules.append(
            ReportRule(
                rule_id=row["rule_id"],
                safe_expr=row["safe_expr"],
                add_tags=[str(x) for x in _j(row["add_tags"])],
                include_phrases=[str(x) for x in _j(row["include_phrases"])],
                exclude_phrases=[str(x) for x in _j(row["exclude_phrases"])],
                priority=int(row["priority"] or 100),
            )
        )

    conn.close()
    _cache["mtime"] = mtime
    _cache["phrases"] = phrases
    _cache["rules"] = rules
    return phrases, rules


def select_phrases(
    env: Dict[str, Any],
    tags: Optional[List[str]] = None,
    audience: str = "doctor",
    section: Optional[str] = None,
    safe_eval_bool_fn=None,
) -> Tuple[List[str], List[str]]:
    """Evaluate rules against env, return (phrases, tags).

    safe_eval_bool_fn must be passed in from rhk_base to avoid circular imports.
    """
    phrases_db, rules = load_report_db()
    tags_out = set(tags or [])

    include: List[str] = []
    exclude: set[str] = set()

    if safe_eval_bool_fn is None:
        # cannot evaluate; return tag-only selection
        return [], sorted(tags_out)

    for rule in rules:
        try:
            ok = bool(safe_eval_bool_fn(rule.safe_expr, env))
        except Exception:
            ok = False
        if not ok:
            continue
        for t in rule.add_tags:
            if t:
                tags_out.add(t)
        for pid in rule.include_phrases:
            if pid:
                include.append(pid)
        for pid in rule.exclude_phrases:
            if pid:
                exclude.add(pid)

    # collect texts
    out_texts: List[Tuple[int, str]] = []
    for pid in include:
        if pid in exclude:
            continue
        phr = phrases_db.get((pid, audience))
        if not phr:
            continue
        if section and phr.section != section:
            continue
        out_texts.append((phr.priority, phr.text.strip()))

    out_texts.sort(key=lambda x: (x[0], x[1]))
    return [t for _, t in out_texts if t], sorted(tags_out)
