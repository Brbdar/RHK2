"""Release manifest helpers shared by build and audit tools."""

from __future__ import annotations

import fnmatch
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List

MANIFEST_FILENAME = "release_manifest.json"


@dataclass(frozen=True)
class ReleaseBundleEntry:
    source: Path
    target: str


@dataclass(frozen=True)
class ReleaseBlocker:
    relpath: str
    reason: str


def get_release_root(root: Any = None) -> Path:
    if root is None:
        return Path(__file__).resolve().parent
    return Path(root).resolve()


def get_manifest_path(root: Any = None) -> Path:
    return get_release_root(root) / MANIFEST_FILENAME


def load_release_manifest(root: Any = None) -> Dict[str, Any]:
    manifest_path = get_manifest_path(root)
    with open(manifest_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Release manifest must be a JSON object: {manifest_path}")
    return data


def _validate_relative_path(text: Any, *, field_name: str) -> str:
    value = str(text or "").strip()
    if not value:
        raise ValueError(f"Missing release manifest field: {field_name}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Release manifest field must be a safe relative path: {field_name}={value!r}")
    return value


def get_release_build_config(root: Any = None) -> Dict[str, str]:
    manifest = load_release_manifest(root)
    build = manifest.get("build")
    if not isinstance(build, dict):
        raise ValueError("Release manifest is missing the 'build' section.")
    return {
        "entry_point": _validate_relative_path(build.get("entry_point"), field_name="build.entry_point"),
        "requirements": _validate_relative_path(build.get("requirements"), field_name="build.requirements"),
        "pyinstaller_spec": _validate_relative_path(build.get("pyinstaller_spec"), field_name="build.pyinstaller_spec"),
    }


def iter_release_bundle_entries(root: Any = None) -> List[ReleaseBundleEntry]:
    release_root = get_release_root(root)
    manifest = load_release_manifest(release_root)
    raw_entries = manifest.get("bundle_files")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("Release manifest is missing bundle_files entries.")

    entries: List[ReleaseBundleEntry] = []
    for idx, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise ValueError(f"bundle_files[{idx}] must be an object.")
        source_rel = _validate_relative_path(item.get("source"), field_name=f"bundle_files[{idx}].source")
        target_rel = _validate_relative_path(item.get("target", "."), field_name=f"bundle_files[{idx}].target")
        entries.append(ReleaseBundleEntry(source=release_root / source_rel, target=target_rel))
    return entries


def get_missing_release_paths(root: Any = None) -> List[str]:
    release_root = get_release_root(root)
    build = get_release_build_config(release_root)
    missing: List[str] = []

    for label, relpath in build.items():
        if not (release_root / relpath).exists():
            missing.append(f"{label}: {relpath}")

    for entry in iter_release_bundle_entries(release_root):
        if not entry.source.exists():
            missing.append(str(entry.source.relative_to(release_root)))

    return missing


def build_pyinstaller_datas(root: Any = None) -> List[tuple[str, str]]:
    return [(str(entry.source.resolve()), entry.target) for entry in iter_release_bundle_entries(root)]


def copy_release_bundle_files(root: Any, dist_app_dir: Any) -> List[str]:
    release_root = get_release_root(root)
    destination = Path(dist_app_dir).resolve()
    copied: List[str] = []

    for entry in iter_release_bundle_entries(release_root):
        rel_source = str(entry.source.relative_to(release_root))
        if entry.source.is_dir():
            target_dir = destination / entry.target
            shutil.copytree(entry.source, target_dir, dirs_exist_ok=True)
        else:
            target_dir = destination if entry.target == "." else destination / entry.target
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry.source, target_dir / entry.source.name)
        copied.append(rel_source)

    return copied


def _iter_root_children(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(root.iterdir(), key=lambda path: path.name)


def find_release_blockers(root: Any = None) -> List[ReleaseBlocker]:
    release_root = get_release_root(root)
    manifest = load_release_manifest(release_root)
    blockers: List[ReleaseBlocker] = []
    seen: set[str] = set()

    raw_exact = manifest.get("root_blockers") or []
    if not isinstance(raw_exact, list):
        raise ValueError("Release manifest root_blockers must be a list.")
    for idx, item in enumerate(raw_exact):
        if not isinstance(item, dict):
            raise ValueError(f"root_blockers[{idx}] must be an object.")
        relpath = _validate_relative_path(item.get("path"), field_name=f"root_blockers[{idx}].path")
        reason = str(item.get("reason") or "").strip() or "Release blocker"
        if (release_root / relpath).exists() and relpath not in seen:
            blockers.append(ReleaseBlocker(relpath=relpath, reason=reason))
            seen.add(relpath)

    raw_globs = manifest.get("root_blocker_globs") or []
    if not isinstance(raw_globs, list):
        raise ValueError("Release manifest root_blocker_globs must be a list.")
    for idx, item in enumerate(raw_globs):
        if not isinstance(item, dict):
            raise ValueError(f"root_blocker_globs[{idx}] must be an object.")
        pattern = str(item.get("pattern") or "").strip()
        reason = str(item.get("reason") or "").strip() or "Release blocker"
        if not pattern:
            raise ValueError(f"Missing release blocker pattern at root_blocker_globs[{idx}]")
        for child in _iter_root_children(release_root):
            if fnmatch.fnmatch(child.name, pattern) and child.name not in seen:
                blockers.append(ReleaseBlocker(relpath=child.name, reason=reason))
                seen.add(child.name)

    return blockers


def summarize_release_readiness(root: Any = None) -> Dict[str, Any]:
    release_root = get_release_root(root)
    build = get_release_build_config(release_root)
    bundle_entries = iter_release_bundle_entries(release_root)
    blockers = find_release_blockers(release_root)
    missing = get_missing_release_paths(release_root)
    return {
        "root": str(release_root),
        "manifest_path": str(get_manifest_path(release_root)),
        "build": build,
        "bundle_files": [str(entry.source.relative_to(release_root)) for entry in bundle_entries],
        "missing_paths": missing,
        "blockers": blockers,
        "ready": (not missing) and (not blockers),
    }


def assert_release_ready(root: Any = None) -> None:
    report = summarize_release_readiness(root)
    if report["ready"]:
        return

    lines = ["Release workspace is not ready."]
    if report["missing_paths"]:
        lines.append("Missing allowlisted build inputs:")
        lines.extend(f"- {item}" for item in report["missing_paths"])
    blockers = report["blockers"]
    if blockers:
        lines.append("Root blockers:")
        lines.extend(f"- {item.relpath}: {item.reason}" for item in blockers)
    raise RuntimeError("\n".join(lines))
