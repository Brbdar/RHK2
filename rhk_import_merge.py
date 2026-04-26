#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.30: rhk_import_merge.py - Placeholder-aware empty detection ("keine Angabe"), keeps manual edits safe; reused by Echo auto-fill
"""Import merge policy helpers.

Dieses Modul enthält **UI-unabhängige** Hilfsfunktionen, um Import-Updates
(z.B. aus DOCX) sicher in ein bestehendes UI-Dict zu mergen.

Klinische Leitplanken (STRICT):
- Manuelle Eingaben werden nicht überschrieben.
- Fehlende Werte ≠ 0: numerische ``0`` wird als *leer* behandelt (Gradio roundtrip).
- Bool-Edge-Case: ``False`` wird **nicht** mit ``0`` verwechselt. Für Checkboxen gilt:
  - Erstimport darf eine Default-Checkbox (False) auf True setzen.
  - Nach manueller Änderung (abweichend vom zuvor importierten Wert) wird nichts überschrieben.
- Deterministisch: gleicher Input → gleicher Output.

Dieses Modul ist bewusst frei von Gradio-Imports, damit es unit-testbar bleibt.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _is_empty_for_autofill(value: Any, prev_imported_value: Any | None) -> bool:
    """Return True if a value should be considered *empty* for auto-fill.

    Rules:
    - None and empty strings are empty.
    - Numeric 0 (int/float) is empty, but **bool is excluded**.
    - Bool False is considered empty **only on first import**, i.e. when there is no
      previous imported value for this key. This allows the importer to set flags
      like `exercise_done=True` on first import, while still preserving later
      manual corrections (False) after a previous import set it True.
    """
    if value is None:
        return True

    if isinstance(value, str):
        s = value.strip().lower()
        # Common UI placeholder tokens (especially for Radio components)
        return (s == "") or (s in {"keine angabe", "n/a", "na", "-", "—"})

    if isinstance(value, bool):
        # Allow setting checkboxes on first import only.
        return (prev_imported_value is None) and (value is False)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return abs(float(value)) < 1e-12
        except (TypeError, ValueError):
            return False

    # Empty containers (rare, but safe)
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0

    return False


def apply_import_updates(
    *,
    ui: Mapping[str, Any],
    updates: Mapping[str, Any],
    prev_applied_keys: Sequence[str] | None,
    prev_applied_values: Mapping[str, Any] | None,
    wipe_defaults: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge ``updates`` into ``ui`` under strict clinical policy.

    Parameters
    ----------
    ui:
        Current UI state (flat dict).
    updates:
        New updates from importer (flat dict).
    prev_applied_keys / prev_applied_values:
        Provenance from a previous import. Used to:
        - clear stale imported values (only if unchanged)
        - allow overwrite of previously imported values (if user did not change)
    wipe_defaults:
        Default values to reset stale fields to when they disappear from the new import.

    Returns
    -------
    (ui_new, applied_values):
        ui_new is a copy with changes applied.
        applied_values contains exactly the keys that were applied in this call.
    """
    ui_new: dict[str, Any] = dict(ui or {})
    updates = dict(updates or {})
    prev_keys = list(prev_applied_keys or [])
    prev_vals = dict(prev_applied_values or {})
    wipe = dict(wipe_defaults or {})

    # 1) Clear stale imported fields that are not present in the new import,
    #    but only if the user has not modified them.
    for k in list(prev_keys):
        if k in updates:
            continue
        if k in wipe:
            if ui_new.get(k) == prev_vals.get(k):
                ui_new[k] = wipe.get(k)

    # 2) Apply new updates conservatively.
    applied: dict[str, Any] = {}
    for k, v in updates.items():
        cur = ui_new.get(k)
        prev_v = prev_vals.get(k)
        if _is_empty_for_autofill(cur, prev_v) or (cur == prev_v):
            ui_new[k] = v
            applied[k] = v

    return ui_new, applied
