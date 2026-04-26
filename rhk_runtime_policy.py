"""Explicit runtime profiles, directories, and retention policies."""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, cast

DeployProfileName = Literal["offline", "clinic", "cloud"]


@dataclass(frozen=True)
class DeployProfile:
    name: DeployProfileName
    allow_cdn_assets: bool
    enable_browser_import: bool
    enable_browser_ocr: bool
    allow_server_upload: bool
    force_hosted_browser_tools: bool
    offline_mode: bool
    privacy_mode: bool
    localhost_only: bool
    auto_open_browser: bool
    share: bool
    prefer_project_exports: bool
    log_retention_days: int
    export_retention_days: int
    temp_retention_days: int


_PROJECT_ROOT = Path(__file__).resolve().parent

_PROFILES: Dict[DeployProfileName, DeployProfile] = {
    "offline": DeployProfile(
        name="offline",
        allow_cdn_assets=False,
        enable_browser_import=False,
        enable_browser_ocr=False,
        allow_server_upload=True,
        force_hosted_browser_tools=False,
        offline_mode=True,
        privacy_mode=True,
        localhost_only=True,
        auto_open_browser=True,
        share=False,
        prefer_project_exports=True,
        log_retention_days=14,
        export_retention_days=14,
        temp_retention_days=3,
    ),
    "clinic": DeployProfile(
        name="clinic",
        allow_cdn_assets=False,
        enable_browser_import=False,
        enable_browser_ocr=False,
        allow_server_upload=True,
        force_hosted_browser_tools=False,
        offline_mode=False,
        privacy_mode=True,
        localhost_only=True,
        auto_open_browser=True,
        share=False,
        prefer_project_exports=False,
        log_retention_days=7,
        export_retention_days=3,
        temp_retention_days=2,
    ),
    "cloud": DeployProfile(
        name="cloud",
        allow_cdn_assets=True,
        enable_browser_import=True,
        enable_browser_ocr=True,
        allow_server_upload=False,
        force_hosted_browser_tools=True,
        offline_mode=False,
        privacy_mode=False,
        localhost_only=False,
        auto_open_browser=False,
        share=False,
        prefer_project_exports=False,
        log_retention_days=3,
        export_retention_days=1,
        temp_retention_days=1,
    ),
}


def _env_flag(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def is_cloud_runtime_env() -> bool:
    return bool(
        os.environ.get("RENDER")
        or os.environ.get("RENDER_SERVICE_ID")
        or os.environ.get("K_SERVICE")
        or os.environ.get("CLOUD_RUN_JOB")
        or os.environ.get("FLY_APP_NAME")
        or os.environ.get("DYNO")
        or os.environ.get("SPACE_ID")
        or os.environ.get("HF_SPACE")
        or os.environ.get("KAGGLE_URL_BASE")
        or os.environ.get("PORT")
    )


def detect_deploy_profile_name() -> DeployProfileName:
    raw = str(os.environ.get("RHK_DEPLOY_PROFILE") or "").strip().lower()
    if raw in _PROFILES:
        return cast(DeployProfileName, raw)
    if _env_flag("RHK_STANDALONE"):
        return "offline"
    if is_cloud_runtime_env():
        return "cloud"
    return "clinic"


def get_deploy_profile(profile_name: str | None = None) -> DeployProfile:
    name = (str(profile_name or "").strip().lower() or detect_deploy_profile_name())
    if name not in _PROFILES:
        name = "clinic"
    return _PROFILES[cast(DeployProfileName, name)]


def _as_env(value: bool | int | str) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def apply_deploy_profile(profile_name: str | None = None) -> DeployProfile:
    profile = get_deploy_profile(profile_name)
    os.environ.setdefault("RHK_DEPLOY_PROFILE", profile.name)
    os.environ.setdefault("RHK_ALLOW_CDN_ASSETS", _as_env(profile.allow_cdn_assets))
    os.environ.setdefault("RHK_ENABLE_BROWSER_IMPORT", _as_env(profile.enable_browser_import))
    os.environ.setdefault("RHK_ENABLE_BROWSER_OCR", _as_env(profile.enable_browser_ocr))
    os.environ.setdefault("RHK_ALLOW_SERVER_UPLOAD", _as_env(profile.allow_server_upload))
    os.environ.setdefault("RHK_FORCE_HOSTED_BROWSER_TOOLS", _as_env(profile.force_hosted_browser_tools))
    os.environ.setdefault("RHK_OFFLINE", _as_env(profile.offline_mode))
    os.environ.setdefault("RHK_PRIVACY_MODE", _as_env(profile.privacy_mode))
    os.environ.setdefault("GRADIO_SHARE", _as_env(profile.share))
    if profile.localhost_only:
        os.environ.setdefault("GRADIO_SERVER_NAME", "127.0.0.1")
    for key in (
        "GRADIO_ANALYTICS_ENABLED",
        "GRADIO_ANALYTICS",
        "GRADIO_TELEMETRY",
        "GRADIO_TELEMETRY_ENABLED",
    ):
        os.environ.setdefault(key, "False")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    return profile


def _retention_days(env_key: str, default: int) -> int:
    raw = str(os.environ.get(env_key) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except ValueError:
        return int(default)
    return max(0, value)


def get_runtime_temp_root(profile_name: str | None = None) -> Path:
    env_dir = str(os.environ.get("RHK_RUNTIME_ROOT_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    profile = get_deploy_profile(profile_name)
    tmp_root = Path(tempfile.gettempdir()).resolve()
    return (tmp_root / f"rhk_runtime_{profile.name}").resolve()


def get_runtime_log_dir(profile_name: str | None = None) -> Path:
    env_dir = str(os.environ.get("RHK_LOG_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    profile = get_deploy_profile(profile_name)
    if profile.name == "offline":
        return (_PROJECT_ROOT / "run_logs").resolve()
    return (get_runtime_temp_root(profile.name) / "logs").resolve()


def get_runtime_case_dir(profile_name: str | None = None) -> Path:
    env_dir = str(os.environ.get("RHK_CASE_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (get_runtime_temp_root(profile_name) / "cases").resolve()


def get_runtime_export_temp_dir(profile_name: str | None = None) -> Path:
    return (get_runtime_temp_root(profile_name) / "exports").resolve()


def get_runtime_download_dir(profile_name: str | None = None) -> Path:
    return (get_runtime_temp_root(profile_name) / "downloads").resolve()


def ensure_runtime_dirs(profile_name: str | None = None) -> Dict[str, Path]:
    dirs = {
        "logs": get_runtime_log_dir(profile_name),
        "cases": get_runtime_case_dir(profile_name),
        "exports": get_runtime_export_temp_dir(profile_name),
        "downloads": get_runtime_download_dir(profile_name),
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def get_allowed_file_paths(profile_name: str | None = None) -> list[str]:
    dirs = ensure_runtime_dirs(profile_name)
    out = [str(dirs["exports"]), str(dirs["cases"]), str(dirs["downloads"])]
    try:
        from rhk_export_paths import get_export_dir

        out.append(str(get_export_dir().resolve()))
    except Exception:
        pass
    tmp_gradio_cache_dir = (Path(tempfile.gettempdir()).resolve() / "gradio").resolve()
    tmp_gradio_cache_dir.mkdir(parents=True, exist_ok=True)
    out.append(str(tmp_gradio_cache_dir))
    seen: set[str] = set()
    result: list[str] = []
    for item in out:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def prefers_project_exports(profile_name: str | None = None) -> bool:
    return get_deploy_profile(profile_name).prefer_project_exports


def get_export_retention_days(profile_name: str | None = None) -> int:
    profile = get_deploy_profile(profile_name)
    return _retention_days("RHK_EXPORT_RETENTION_DAYS", profile.export_retention_days)


def get_log_retention_days(profile_name: str | None = None) -> int:
    profile = get_deploy_profile(profile_name)
    return _retention_days("RHK_LOG_RETENTION_DAYS", profile.log_retention_days)


def get_temp_retention_days(profile_name: str | None = None) -> int:
    profile = get_deploy_profile(profile_name)
    return _retention_days("RHK_TEMP_RETENTION_DAYS", profile.temp_retention_days)


def _cleanup_dir(path: Path, *, max_age_days: int, suffixes: tuple[str, ...] = (), prefixes: tuple[str, ...] = (), allow_all: bool = False) -> int:
    if max_age_days < 0 or not path.exists():
        return 0
    cutoff = time.time() - max_age_days * 24 * 3600
    removed = 0
    for item in path.glob("*"):
        try:
            if not item.is_file():
                continue
            if item.stat().st_mtime >= cutoff:
                continue
            name = item.name
            if not allow_all:
                if prefixes and not any(name.startswith(prefix) for prefix in prefixes):
                    continue
                if suffixes and not any(name.endswith(suffix) for suffix in suffixes):
                    continue
            item.unlink(missing_ok=True)
            removed += 1
        except Exception:
            continue
    return removed


def cleanup_runtime_retention(profile_name: str | None = None) -> Dict[str, int]:
    profile = get_deploy_profile(profile_name)
    dirs = ensure_runtime_dirs(profile.name)
    removed = {
        "logs": _cleanup_dir(
            dirs["logs"],
            max_age_days=get_log_retention_days(profile.name),
            suffixes=(".log",),
            allow_all=True,
        ),
        "exports": _cleanup_dir(
            dirs["exports"],
            max_age_days=get_export_retention_days(profile.name),
            allow_all=True,
        ),
        "cases": _cleanup_dir(
            dirs["cases"],
            max_age_days=get_temp_retention_days(profile.name),
            suffixes=(".json",),
            allow_all=True,
        ),
        "downloads": _cleanup_dir(
            dirs["downloads"],
            max_age_days=get_temp_retention_days(profile.name),
            allow_all=True,
        ),
    }

    project_logs = (_PROJECT_ROOT / "run_logs").resolve()
    project_exports = (_PROJECT_ROOT / "exports").resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    legacy_temp_exports = (tmp_root / "rhk_exports").resolve()
    legacy_temp_cases = (tmp_root / "rhk_befunder").resolve()
    removed["legacy_logs"] = _cleanup_dir(project_logs, max_age_days=get_log_retention_days(profile.name), suffixes=(".log",), allow_all=True)
    removed["legacy_exports"] = _cleanup_dir(project_exports, max_age_days=get_export_retention_days(profile.name), allow_all=True)
    removed["legacy_temp_exports"] = _cleanup_dir(legacy_temp_exports, max_age_days=get_export_retention_days(profile.name), allow_all=True)
    removed["legacy_temp_cases"] = _cleanup_dir(legacy_temp_cases, max_age_days=get_temp_retention_days(profile.name), suffixes=(".json",), allow_all=True)
    removed["legacy_temp_downloads"] = _cleanup_dir(
        tmp_root,
        max_age_days=get_temp_retention_days(profile.name),
        prefixes=("rhk_dl_",),
        allow_all=False,
    )
    return removed


__all__ = [
    "DeployProfile",
    "DeployProfileName",
    "apply_deploy_profile",
    "cleanup_runtime_retention",
    "detect_deploy_profile_name",
    "ensure_runtime_dirs",
    "get_allowed_file_paths",
    "get_deploy_profile",
    "get_export_retention_days",
    "get_log_retention_days",
    "get_runtime_case_dir",
    "get_runtime_download_dir",
    "get_runtime_export_temp_dir",
    "get_runtime_log_dir",
    "get_runtime_temp_root",
    "get_temp_retention_days",
    "is_cloud_runtime_env",
    "prefers_project_exports",
]
