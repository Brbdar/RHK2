"""Versioned migration helpers for persisted case payloads.

The active runtime schema can evolve without forcing the UI/runtime layers
to carry legacy branching everywhere. Save/load is the only supported edge
for schema migration.
"""

from __future__ import annotations

import copy
import datetime as _dt
from typing import Any, Dict

CURRENT_CASE_SCHEMA_VERSION = 1


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def migrate_case_payload(payload: Any) -> Dict[str, Any]:
    """Return a migrated case payload in the current persisted schema.

    Current migration policy is intentionally conservative:
    - non-dict payloads become an empty dict
    - legacy ui-only payloads remain valid and are wrapped only by metadata
    - `_meta.schema_version` is stamped to the current version
    """
    data = _as_dict(payload)
    meta = _as_dict(data.get("_meta"))

    # No content migrations are required yet. Keep this as the single seam.
    meta["schema_version"] = CURRENT_CASE_SCHEMA_VERSION
    data["_meta"] = meta
    return data


def stamp_case_payload(payload: Any) -> Dict[str, Any]:
    """Copy a runtime payload and attach persisted schema metadata."""
    data = copy.deepcopy(_as_dict(payload))
    meta = _as_dict(data.get("_meta"))
    meta["schema_version"] = CURRENT_CASE_SCHEMA_VERSION
    meta["saved_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    data["_meta"] = meta
    return data
