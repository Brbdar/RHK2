from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _guard_installed(flag: str) -> bool:
    env = dict(os.environ)
    env["RHK_ENABLE_RUNTIME_GUARD"] = flag
    script = (
        "import importlib.util, pathlib, sys; "
        "path = pathlib.Path('sitecustomize.py').resolve(); "
        "spec = importlib.util.spec_from_file_location('rhk_sitecustomize', path); "
        "mod = importlib.util.module_from_spec(spec); "
        "assert spec is not None and spec.loader is not None; "
        "spec.loader.exec_module(mod); "
        "print(any(type(x).__name__ == '_RuntimeGuard' for x in sys.meta_path))"
    )
    cmd = [
        sys.executable,
        "-c",
        script,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env, check=True)
    return proc.stdout.strip().splitlines()[-1].strip().lower() == "true"


def test_runtime_guard_enabled_by_default() -> None:
    assert _guard_installed("1") is True


def test_runtime_guard_can_be_disabled() -> None:
    assert _guard_installed("0") is False
