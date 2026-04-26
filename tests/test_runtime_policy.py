import os
import sys
import time
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import rhk_export_paths
import rhk_runtime_policy


def _touch_old_file(path: Path, *, age_days: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    old_ts = time.time() - (age_days * 24 * 3600) - 60
    os.utime(path, (old_ts, old_ts))


def test_clinic_profile_prefers_runtime_temp_exports(monkeypatch, tmp_path):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("RHK_DEPLOY_PROFILE", "clinic")
    monkeypatch.setenv("RHK_RUNTIME_ROOT_DIR", str(runtime_root))
    for key in (
        "GRADIO_SERVER_NAME",
        "RHK_ALLOW_CDN_ASSETS",
        "RHK_CASE_DIR",
        "RHK_EXPORT_DIR",
        "RHK_LOG_DIR",
    ):
        monkeypatch.delenv(key, raising=False)

    rhk_export_paths._CACHED_EXPORT_DIR = None
    profile = rhk_runtime_policy.apply_deploy_profile("clinic")
    export_dir = rhk_export_paths.get_export_dir()

    assert profile.name == "clinic"
    assert export_dir == (runtime_root / "exports").resolve()
    assert os.environ["GRADIO_SERVER_NAME"] == "127.0.0.1"
    assert os.environ["RHK_ALLOW_CDN_ASSETS"] == "0"


def test_cloud_profile_disables_server_upload_by_default(monkeypatch):
    for key in (
        "GRADIO_SERVER_NAME",
        "RHK_ALLOW_SERVER_UPLOAD",
        "RHK_ENABLE_BROWSER_IMPORT",
        "RHK_ENABLE_BROWSER_OCR",
        "RHK_FORCE_HOSTED_BROWSER_TOOLS",
    ):
        monkeypatch.delenv(key, raising=False)

    profile = rhk_runtime_policy.apply_deploy_profile("cloud")

    assert profile.name == "cloud"
    assert os.environ["RHK_ALLOW_SERVER_UPLOAD"] == "0"
    assert os.environ["RHK_ENABLE_BROWSER_IMPORT"] == "1"
    assert os.environ["RHK_ENABLE_BROWSER_OCR"] == "1"
    assert os.environ["RHK_FORCE_HOSTED_BROWSER_TOOLS"] == "1"
    assert "GRADIO_SERVER_NAME" not in os.environ


def test_cleanup_runtime_retention_removes_old_runtime_and_legacy_files(monkeypatch, tmp_path):
    runtime_root = tmp_path / "runtime"
    temp_root = tmp_path / "tmp"
    project_root = tmp_path / "project"
    monkeypatch.setenv("RHK_DEPLOY_PROFILE", "clinic")
    monkeypatch.setenv("RHK_RUNTIME_ROOT_DIR", str(runtime_root))
    monkeypatch.setattr(rhk_runtime_policy, "_PROJECT_ROOT", project_root)
    monkeypatch.setattr(rhk_runtime_policy.tempfile, "gettempdir", lambda: str(temp_root))

    runtime_log = rhk_runtime_policy.get_runtime_log_dir("clinic") / "app.log"
    runtime_export = rhk_runtime_policy.get_runtime_export_temp_dir("clinic") / "old.pdf"
    runtime_case = rhk_runtime_policy.get_runtime_case_dir("clinic") / "case.json"
    runtime_download = rhk_runtime_policy.get_runtime_download_dir("clinic") / "dl.bin"
    legacy_log = project_root / "run_logs" / "legacy.log"
    legacy_export = project_root / "exports" / "legacy.pdf"
    legacy_temp_export = temp_root / "rhk_exports" / "legacy.pdf"
    legacy_temp_case = temp_root / "rhk_befunder" / "legacy.json"
    legacy_download = temp_root / "rhk_dl_old.pdf"

    for path in (
        runtime_log,
        runtime_export,
        runtime_case,
        runtime_download,
        legacy_log,
        legacy_export,
        legacy_temp_export,
        legacy_temp_case,
        legacy_download,
    ):
        _touch_old_file(path, age_days=10)

    removed = rhk_runtime_policy.cleanup_runtime_retention("clinic")

    assert removed["logs"] == 1
    assert removed["exports"] == 1
    assert removed["cases"] == 1
    assert removed["downloads"] == 1
    assert removed["legacy_logs"] == 1
    assert removed["legacy_exports"] == 1
    assert removed["legacy_temp_exports"] == 1
    assert removed["legacy_temp_cases"] == 1
    assert removed["legacy_temp_downloads"] == 1

    for path in (
        runtime_log,
        runtime_export,
        runtime_case,
        runtime_download,
        legacy_log,
        legacy_export,
        legacy_temp_export,
        legacy_temp_case,
        legacy_download,
    ):
        assert not path.exists()
