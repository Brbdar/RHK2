import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_release_manifest import (
    build_pyinstaller_datas,
    copy_release_bundle_files,
    find_release_blockers,
    get_missing_release_paths,
    get_release_build_config,
)


def test_release_manifest_declares_existing_build_inputs_and_bundle_files():
    root_path = Path(ROOT)
    build = get_release_build_config(root_path)

    assert (root_path / build["entry_point"]).exists()
    assert (root_path / build["requirements"]).exists()
    assert (root_path / build["pyinstaller_spec"]).exists()

    datas = build_pyinstaller_datas(root_path)
    assert datas
    for source, target in datas:
        assert Path(source).exists()
        assert target


def test_release_blockers_are_detected_from_manifest(tmp_path):
    manifest = {
        "build": {
            "entry_point": "entry.py",
            "requirements": "requirements.txt",
            "pyinstaller_spec": "standalone/app.spec",
        },
        "bundle_files": [{"source": "config.txt", "target": "."}],
        "root_blockers": [{"path": "run_logs", "reason": "logs"}],
        "root_blocker_globs": [{"pattern": "*.zip", "reason": "archives"}],
    }
    (tmp_path / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "entry.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "config.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "standalone").mkdir()
    (tmp_path / "standalone" / "app.spec").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "run_logs").mkdir()
    (tmp_path / "debug.zip").write_text("artifact\n", encoding="utf-8")

    blockers = find_release_blockers(tmp_path)

    assert {item.relpath for item in blockers} == {"debug.zip", "run_logs"}
    assert get_missing_release_paths(tmp_path) == []


def test_release_bundle_copy_uses_manifest_targets(tmp_path):
    manifest = {
        "build": {
            "entry_point": "entry.py",
            "requirements": "requirements.txt",
            "pyinstaller_spec": "standalone/app.spec",
        },
        "bundle_files": [
            {"source": "config.txt", "target": "."},
            {"source": "assets", "target": "assets"},
        ],
        "root_blockers": [],
        "root_blocker_globs": [],
    }
    (tmp_path / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "entry.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "standalone").mkdir()
    (tmp_path / "standalone" / "app.spec").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "config.txt").write_text("cfg\n", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.txt").write_text("logo\n", encoding="utf-8")
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    copied = copy_release_bundle_files(tmp_path, dist_dir)

    assert copied == ["config.txt", "assets"]
    assert (dist_dir / "config.txt").read_text(encoding="utf-8") == "cfg\n"
    assert (dist_dir / "assets" / "logo.txt").read_text(encoding="utf-8") == "logo\n"
