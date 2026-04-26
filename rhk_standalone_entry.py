#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.33: rhk_standalone_entry.py - Offline/Standalone defaults (kein Internet, keine Telemetrie), startet lokal
"""Standalone entry point (offline, single machine).

This entry point is intended to be packaged (e.g., PyInstaller) so that the
application runs on a single computer **without internet** and **without a
separately installed Python**.

Behavior:
- forces privacy-safe, offline defaults (can still be overridden via env vars)
- launches the normal Gradio UI via rhk_launch.main()
"""

from __future__ import annotations

import os

# -----------------------------------------------------------------------------
# Offline / privacy defaults (may be overridden)
# -----------------------------------------------------------------------------
os.environ.setdefault("RHK_STANDALONE", "1")
os.environ.setdefault("RHK_DEPLOY_PROFILE", "offline")

from rhk_runtime_policy import apply_deploy_profile

apply_deploy_profile("offline")

# Ensure export dir exists early (also helps with Gradio allowlist paths).
try:
    from rhk_export_paths import ensure_export_dir, get_export_dir

    ensure_export_dir()
    os.environ.setdefault("RHK_EXPORT_DIR", str(get_export_dir()))
except Exception:
    pass

from rhk_launch import main

if __name__ == "__main__":
    main()
