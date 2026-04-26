import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_bump_version_tool_dry_run_executes():
    cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "bump_version.py"),
        "--dry-run",
        "--to",
        "v27.99.0",
        "--note",
        "Testlauf",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "DRY-RUN" in out
    assert "v27.99.0" in out
