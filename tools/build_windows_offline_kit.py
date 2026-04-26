#!/usr/bin/env python3
"""Create a portable Windows offline kit with embedded Python."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rhk_release_manifest import copy_release_bundle_files, get_release_build_config

try:
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
except Exception:  # pragma: no cover - packaging ships with pip, but keep a fallback.
    Requirement = None
    default_environment = None

DEFAULT_PYTHON_VERSION = "3.11.9"
DEFAULT_PLATFORM = "win_amd64"
DEFAULT_OUTPUT_DIR = ROOT / "OFFLINE" / "dist" / "RHK_OFFLINE_WIN64"
DEFAULT_CACHE_DIR = ROOT / "OFFLINE" / ".cache" / "windows_offline_kit"
RUNTIME_ROOT_FILES = (
    "spiro_logic.py",
    "sitecustomize.py",
    "requirements.txt",
    "release_manifest.json",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a portable Windows offline distribution in a subfolder.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Target directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help=f"Download cache directory (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help=f"Embedded Python version (default: {DEFAULT_PYTHON_VERSION})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete an existing output directory before building.",
    )
    return parser.parse_args()


def _log(message: str) -> None:
    print(f"[build_windows_offline_kit] {message}", flush=True)


def _ensure_clean_output_dir(output_dir: Path, *, force: bool) -> None:
    if output_dir.exists():
        if not force:
            raise RuntimeError(
                f"Output directory already exists: {output_dir}. Use --force to rebuild it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _copy_runtime_sources(output_dir: Path) -> list[str]:
    copied: list[str] = []

    for source in sorted(ROOT.glob("rhk_*.py")):
        shutil.copy2(source, output_dir / source.name)
        copied.append(source.name)

    for name in RUNTIME_ROOT_FILES:
        source = ROOT / name
        if not source.exists():
            raise RuntimeError(f"Missing runtime file: {source}")
        shutil.copy2(source, output_dir / source.name)
        copied.append(source.name)

    copied.extend(copy_release_bundle_files(ROOT, output_dir))

    template_dir = ROOT / "OFFLINE" / "template"
    for source in sorted(template_dir.iterdir()):
        if source.name == ".DS_Store":
            continue
        if source.is_dir():
            shutil.copytree(source, output_dir / source.name, dirs_exist_ok=True)
        else:
            shutil.copy2(source, output_dir / source.name)
        copied.append(f"OFFLINE/template/{source.name}")

    return copied


def _download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Download: {url}")
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


def _python_archive_path(cache_dir: Path, python_version: str) -> Path:
    return cache_dir / f"python-{python_version}-embed-amd64.zip"


def _download_embedded_python(cache_dir: Path, python_version: str) -> Path:
    archive_path = _python_archive_path(cache_dir, python_version)
    if archive_path.exists():
        _log(f"Reuse embedded Python archive: {archive_path}")
        return archive_path
    url = (
        f"https://www.python.org/ftp/python/{python_version}/"
        f"python-{python_version}-embed-amd64.zip"
    )
    return _download_file(url, archive_path)


def _extract_embedded_python(archive_path: Path, output_dir: Path) -> Path:
    python_dir = output_dir / "python"
    python_dir.mkdir(parents=True, exist_ok=True)
    _log(f"Extract embedded Python -> {python_dir}")
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(python_dir)
    return python_dir


def _patch_python_path_file(python_dir: Path) -> Path:
    candidates = list(python_dir.glob("python*._pth")) or list(python_dir.glob("python*.pth"))
    if not candidates:
        raise RuntimeError(f"No ._pth/.pth file found in {python_dir}")

    path_file = candidates[0]
    existing = [line.strip() for line in path_file.read_text(encoding="ascii").splitlines() if line.strip()]
    zip_candidates = sorted(path.name for path in python_dir.glob("python*.zip"))
    desired = [*zip_candidates, ".", "Lib", "Lib\\site-packages", "..", "import site"]
    seen: set[str] = set()
    merged: list[str] = []
    for item in existing + desired:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    path_file.write_text("\n".join(merged) + "\n", encoding="ascii")
    return path_file


def _default_target_environment(python_version: str) -> dict[str, str]:
    env: dict[str, str]
    if default_environment is not None:
        env = dict(default_environment())
    else:  # pragma: no cover
        env = {}

    env.update(
        {
            "implementation_name": "cpython",
            "implementation_version": python_version,
            "os_name": "nt",
            "platform_machine": "AMD64",
            "platform_python_implementation": "CPython",
            "platform_release": "11",
            "platform_system": "Windows",
            "platform_version": "10.0.22631",
            "python_full_version": f"{python_version}.0" if python_version.count(".") == 1 else python_version,
            "python_version": ".".join(python_version.split(".")[:2]),
            "sys_platform": "win32",
        }
    )
    return env


def _fallback_requirement_matches(marker_text: str, *, python_version: str) -> bool:
    marker = marker_text.strip().replace('"', "'")
    if not marker:
        return True
    py = ".".join(python_version.split(".")[:2])
    if "python_version" not in marker:
        return True
    if "< '3.13'" in marker or "<= '3.12'" in marker:
        return py < "3.13"
    if ">= '3.13'" in marker:
        return py >= "3.13"
    return True


def _resolve_requirement_specs(requirements_path: Path, python_version: str) -> list[str]:
    specs: list[str] = []
    target_env = _default_target_environment(python_version)

    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if Requirement is None:  # pragma: no cover
            if ";" in line:
                requirement_text, marker_text = line.split(";", 1)
                if not _fallback_requirement_matches(marker_text, python_version=python_version):
                    continue
                line = requirement_text.strip()
            specs.append(line)
            continue

        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate(target_env):
            continue

        spec = requirement.name
        if requirement.extras:
            spec += "[" + ",".join(sorted(requirement.extras)) + "]"
        spec += str(requirement.specifier)
        if requirement.url:
            spec += f" @ {requirement.url}"
        specs.append(spec)

    if not specs:
        raise RuntimeError(f"No matching requirements resolved from: {requirements_path}")
    return specs


def _download_wheelhouse(
    requirements_path: Path,
    wheelhouse_dir: Path,
    *,
    python_version: str,
) -> tuple[list[str], list[str]]:
    if wheelhouse_dir.exists():
        shutil.rmtree(wheelhouse_dir)
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)

    specs = _resolve_requirement_specs(requirements_path, python_version)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(wheelhouse_dir),
        "--only-binary=:all:",
        "--platform",
        DEFAULT_PLATFORM,
        "--python-version",
        ".".join(python_version.split(".")[:2]),
        "--implementation",
        "cp",
        *specs,
    ]
    _log(f"Download wheelhouse -> {wheelhouse_dir}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    wheel_files = sorted(path.name for path in wheelhouse_dir.glob("*.whl"))
    if not wheel_files:
        raise RuntimeError(f"No wheel files downloaded into {wheelhouse_dir}")
    return specs, wheel_files


def _safe_target(base_dir: Path, parts: Iterable[str]) -> Path:
    target = base_dir.joinpath(*parts)
    resolved_base = base_dir.resolve()
    resolved_target = target.resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError as exc:  # pragma: no cover
        raise RuntimeError(f"Unsafe zip member target: {target}") from exc
    return target


def _install_single_wheel(wheel_path: Path, python_dir: Path) -> None:
    site_packages = python_dir / "Lib" / "site-packages"
    scripts_dir = python_dir / "Scripts"
    include_dir = python_dir / "Include"
    site_packages.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    include_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(wheel_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue

            posix_path = PurePosixPath(member.filename)
            parts = posix_path.parts
            if not parts:
                continue

            target_root = site_packages
            target_parts = parts
            if parts[0].endswith(".data") and len(parts) >= 3:
                category = parts[1]
                target_parts = parts[2:]
                if category in {"purelib", "platlib"}:
                    target_root = site_packages
                elif category == "scripts":
                    target_root = scripts_dir
                elif category == "headers":
                    target_root = include_dir
                elif category == "data":
                    target_root = python_dir
                else:
                    target_root = site_packages
                    target_parts = parts

            target = _safe_target(target_root, target_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _install_wheels(wheelhouse_dir: Path, python_dir: Path) -> None:
    wheel_files = sorted(wheelhouse_dir.glob("*.whl"))
    if not wheel_files:
        raise RuntimeError(f"No wheels found in {wheelhouse_dir}")
    for wheel_path in wheel_files:
        _log(f"Install wheel: {wheel_path.name}")
        _install_single_wheel(wheel_path, python_dir)


def _write_build_manifest(
    output_dir: Path,
    *,
    copied_files: list[str],
    python_version: str,
    python_archive: Path,
    requirement_specs: list[str],
    wheel_files: list[str],
) -> None:
    payload: dict[str, Any] = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_point": get_release_build_config(ROOT)["entry_point"],
        "output_dir": str(output_dir),
        "python_version": python_version,
        "python_archive": str(python_archive),
        "platform": DEFAULT_PLATFORM,
        "requirements": requirement_specs,
        "wheel_files": wheel_files,
        "copied_files": copied_files,
    }
    (output_dir / "BUILD_INFO.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_runtime_marker(output_dir: Path, wheel_files: list[str]) -> None:
    marker = {
        "installed_at_utc": datetime.now(timezone.utc).isoformat(),
        "wheel_files": wheel_files,
    }
    marker_path = output_dir / "python" / "Lib" / "site-packages" / "rhk_offline_runtime.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _create_runtime_directories(output_dir: Path) -> None:
    for name in ("exports", "runtime", "run_logs", "temp"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)


def build_windows_offline_kit(
    *,
    output_dir: Path,
    cache_dir: Path,
    python_version: str,
    force: bool,
) -> Path:
    output_dir = output_dir.resolve()
    cache_dir = cache_dir.resolve()

    _ensure_clean_output_dir(output_dir, force=force)
    copied_files = _copy_runtime_sources(output_dir)
    python_archive = _download_embedded_python(cache_dir, python_version)
    python_dir = _extract_embedded_python(python_archive, output_dir)
    _patch_python_path_file(python_dir)

    with tempfile.TemporaryDirectory(prefix="rhk_win_wheels_", dir=str(cache_dir.parent)) as tmp_dir_text:
        wheelhouse_dir = Path(tmp_dir_text)
        requirements_path = ROOT / "requirements.txt"
        requirement_specs, wheel_files = _download_wheelhouse(
            requirements_path,
            wheelhouse_dir,
            python_version=python_version,
        )
        _install_wheels(wheelhouse_dir, python_dir)
        _write_build_manifest(
            output_dir,
            copied_files=copied_files,
            python_version=python_version,
            python_archive=python_archive,
            requirement_specs=requirement_specs,
            wheel_files=wheel_files,
        )
        _write_runtime_marker(output_dir, wheel_files)

    _create_runtime_directories(output_dir)
    return output_dir


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir).expanduser()
    cache_dir = Path(args.cache_dir).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        dist_dir = build_windows_offline_kit(
            output_dir=output_dir,
            cache_dir=cache_dir,
            python_version=args.python_version,
            force=bool(args.force),
        )
    except Exception as exc:
        _log(f"ERROR: {exc}")
        return 1

    _log(f"Ready: {dist_dir}")
    _log(f"Windows launch script: {dist_dir / 'Start_RHK.bat'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
