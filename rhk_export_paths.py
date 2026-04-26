#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.43: rhk_export_paths.py - Export-Dir Determinismus: Projektpfad > CWD, ENV-Override, safer for Gradio downloads
"""Export path utilities (clinic-safe, deployment-robust).

Why this exists
---------------
In clinical deployments, the current working directory may be read-only
or outside Gradio's download allowlist. Generating files into such paths
causes **silent download failures** in hosted environments.

This module provides:
- A deterministic, writable export directory selection.
- Centralized directory creation.
- Timestamped, PHI-safe filenames.

Security / privacy
------------------
- Filenames never include patient identifiers.
- No patient data is cached globally.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from rhk_runtime_policy import get_runtime_export_temp_dir, prefers_project_exports

__all__ = [
    "get_export_dir",
    "ensure_export_dir",
    "make_export_path",
]


_CACHED_EXPORT_DIR: Optional[Path] = None


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".rhk_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_export_dir() -> Path:
    """Return a writable export directory.

    Preference order (deterministic & clinic-safe):
    1) $RHK_EXPORT_DIR (if set and writable)
    2) Profile-preferred default (`./exports` for offline, runtime temp for clinic/cloud)
    3) Secondary stable fallback (project exports vs runtime temp)
    4) <current_workdir>/exports (backwards compatibility)
    """
    global _CACHED_EXPORT_DIR
    if _CACHED_EXPORT_DIR is not None:
        return _CACHED_EXPORT_DIR

    # 1) explicit override
    env_dir = os.getenv("RHK_EXPORT_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        if _is_writable_dir(p):
            _CACHED_EXPORT_DIR = p
            return p

    # 2) profile-aware defaults
    try:
        project_exports = Path(__file__).resolve().parent / "exports"
        project_exports = project_exports.resolve()
    except Exception:
        project_exports = None
    runtime_exports = get_runtime_export_temp_dir().resolve()

    cwd_exports = Path(os.getcwd()).resolve() / "exports"

    candidates = []
    if prefers_project_exports():
        candidates.extend([project_exports, cwd_exports, runtime_exports])
    else:
        candidates.extend([runtime_exports, project_exports, cwd_exports])

    for candidate in candidates:
        if candidate is None:
            continue
        if _is_writable_dir(candidate):
            _CACHED_EXPORT_DIR = candidate
            return candidate

    # Best-effort: even if not writable, we still return the runtime temp path.
    _is_writable_dir(runtime_exports)
    _CACHED_EXPORT_DIR = runtime_exports
    return runtime_exports


def ensure_export_dir() -> Path:
    """Ensure the chosen export dir exists and return it."""
    p = get_export_dir()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        # last resort: do not crash
        pass
    return p


def make_export_path(*, stem: str, suffix: str, ts: Optional[str] = None) -> str:
    """Build a PHI-safe export file path in the export dir.

    Args:
        stem: File stem, e.g. "rhk_arztbericht".
        suffix: Extension including dot, e.g. ".docx".
        ts: Optional timestamp override (YYYYMMDD_HHMMSS). If None, uses now.
    """
    d = ensure_export_dir()
    ts_s = ts or time.strftime("%Y%m%d_%H%M%S")
    safe_stem = "".join(ch for ch in str(stem) if ch.isalnum() or ch in ("_", "-"))
    if not safe_stem:
        safe_stem = "export"
    if not str(suffix).startswith("."):
        suffix = "." + str(suffix)
    return str((d / f"{safe_stem}_{ts_s}{suffix}").resolve())
