#!/usr/bin/env python3
"""Release preflight audit for manifest-driven builds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rhk_release_manifest import summarize_release_readiness


def main() -> int:
    report = summarize_release_readiness(ROOT)
    blockers = report["blockers"]
    payload = {
        "root": report["root"],
        "manifest_path": report["manifest_path"],
        "ready": report["ready"],
        "build": report["build"],
        "bundle_files": report["bundle_files"],
        "missing_paths": report["missing_paths"],
        "blockers": [{"path": item.relpath, "reason": item.reason} for item in blockers],
    }

    if "--json" in sys.argv[1:]:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Release root: {payload['root']}")
        print(f"Manifest: {payload['manifest_path']}")
        print(f"Entry point: {payload['build']['entry_point']}")
        print(f"Requirements: {payload['build']['requirements']}")
        print(f"PyInstaller spec: {payload['build']['pyinstaller_spec']}")
        print(f"Allowlisted bundle files: {len(payload['bundle_files'])}")
        for relpath in payload["bundle_files"]:
            print(f"  - {relpath}")
        if payload["missing_paths"]:
            print("Missing paths:")
            for item in payload["missing_paths"]:
                print(f"  - {item}")
        if payload["blockers"]:
            print("Root blockers:")
            for item in payload["blockers"]:
                print(f"  - {item['path']}: {item['reason']}")

    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
