"""Compatibility shim (legacy import path).

Historically the project used a version-suffixed patient text database module.
From v25.0 onward, `rhk_textdb_patient.py` is the single source of truth.

Do not modify clinical content here. Edit `rhk_textdb_patient.py` instead.
"""

from rhk_textdb_patient import *  # noqa: F401,F403
