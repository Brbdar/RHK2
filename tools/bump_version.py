#!/usr/bin/env python3
"""Bump app version and keep version headers in sync.

Usage
  python3 tools/bump_version.py --note "Kurzbeschreibung"
  python3 tools/bump_version.py --to v27.4.24 --note "Kurzbeschreibung"
  python3 tools/bump_version.py --to v27.4.24 --note "Kurzbeschreibung" --dry-run
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "rhk_base.py"
ENTRY_FILE = ROOT / "rhk_app_web_master.py"
FIX_HEADER_FILE = ROOT / "FIX_HEADER.md"
I18N_FILE = ROOT / "rhk_i18n.py"
README_FILE = ROOT / "README.md"
PATCH_NOTES_FILE = ROOT / "PATCH_NOTES.md"
VERSION_RE = r"v\d+\.\d+(?:\.\d+)?"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str, dry_run: bool) -> None:
    if not dry_run:
        path.write_text(text, encoding="utf-8")


def _current_version(base_text: str) -> str:
    m = re.search(rf'APP_VERSION\s*=\s*"({VERSION_RE})"', base_text)
    if not m:
        raise RuntimeError("APP_VERSION in rhk_base.py nicht gefunden.")
    return m.group(1)


def _parse_version(ver: str) -> tuple[int, int, int | None]:
    m = re.fullmatch(r"v(\d+)\.(\d+)(?:\.(\d+))?", ver)
    if not m:
        raise RuntimeError(f"Ungueltiges Versionsformat: {ver}")
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3)) if m.group(3) is not None else None
    return major, minor, patch


def _inc_version(ver: str) -> str:
    major, minor, patch = _parse_version(ver)
    if patch is None:
        return f"v{major}.{minor + 1}"
    return f"v{major}.{minor}.{patch + 1}"


def _update_base(text: str, new_ver: str, note: str) -> Tuple[str, bool]:
    out = text
    out, n1 = re.subn(rf'APP_VERSION\s*=\s*"{VERSION_RE}"', f'APP_VERSION = "{new_ver}"', out, count=1)
    out, n2 = re.subn(rf"(RHK Befundassistent \(Web\)\s+–\s+){VERSION_RE}", rf"\g<1>{new_ver}", out, count=1)
    def _replace_fix_header(match: re.Match[str]) -> str:
        return f'{match.group(1)}Fix. {new_ver}: {note.strip()}{match.group(2)}'
    out, n3 = re.subn(
        r'(_FALLBACK_FIX_LOG\s*=\s*\[\s*\n\s*")[^"]+(")',
        _replace_fix_header,
        out,
        count=1,
    )
    return out, bool(n1 or n2 or n3)


def _update_entry(text: str, new_ver: str) -> Tuple[str, bool]:
    out = text
    out, n1 = re.subn(rf"(RHK Befundassistent\s+–\s+){VERSION_RE}", rf"\g<1>{new_ver}", out, count=1)
    out, n2 = re.subn(rf"(Warum\s+){VERSION_RE}(\?)", rf"\g<1>{new_ver}\g<2>", out, count=1)
    return out, bool(n1 or n2)


def _update_fix_header(text: str, new_ver: str, note: str, keep: int) -> Tuple[str, bool]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    new_line = f"Fix. {new_ver}: {note.strip()}"
    filtered = [ln for ln in lines if not ln.startswith(f"Fix. {new_ver}:")]
    new_lines = [new_line] + filtered
    if keep > 0:
        new_lines = new_lines[:keep]
    out = "\n".join(new_lines) + "\n"
    return out, (out != text)


def _update_i18n(text: str, cur_ver: str, new_ver: str) -> Tuple[str, bool]:
    """Replace the previous version everywhere it's referenced as a literal
    substring in i18n keys/values (e.g. "RHK Befundassistent – v1.1" becomes
    "RHK Befundassistent – v1.2"). Uses plain string replace rather than a
    regex so we only touch occurrences of the *current* version — other
    version numbers that appear in translated content stay untouched."""
    if cur_ver == new_ver:
        return text, False
    out = text.replace(cur_ver, new_ver)
    return out, (out != text)


def _update_readme(text: str, cur_ver: str, new_ver: str) -> Tuple[str, bool]:
    """README references the current version in the title and 'Aktueller Stand'
    heading. We replace the raw version string; other historical version
    references in the README (e.g. in a changelog section) must be hand-edited."""
    if cur_ver == new_ver:
        return text, False
    out = text.replace(cur_ver, new_ver)
    return out, (out != text)


def _update_patch_notes(text: str, new_ver: str, note: str) -> Tuple[str, bool]:
    """Prepend a new version section to PATCH_NOTES.md. If a section for the
    same version already exists, we leave it alone — the user is expected to
    edit the existing section manually rather than creating duplicates."""
    header = f"## {new_ver}"
    if header in text:
        return text, False
    new_section = f"{header}\n\n- {note.strip()}\n\n"
    return new_section + text, True


def main() -> None:
    ap = argparse.ArgumentParser(description="Version bump helper")
    ap.add_argument("--to", help="Zielversion, z.B. v27.4.24")
    ap.add_argument("--note", required=True, help="Fix-Header Kurztext")
    ap.add_argument("--keep", type=int, default=3, help="Anzahl Fix-Header-Zeilen")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base_text = _read(BASE_FILE)
    cur_ver = _current_version(base_text)
    new_ver = args.to.strip() if args.to else _inc_version(cur_ver)

    if not re.fullmatch(VERSION_RE, new_ver):
        raise RuntimeError(f"Ungueltige Zielversion: {new_ver}")

    base_new, base_changed = _update_base(base_text, new_ver, args.note)
    entry_text = _read(ENTRY_FILE)
    entry_new, entry_changed = _update_entry(entry_text, new_ver)
    fix_text = _read(FIX_HEADER_FILE)
    fix_new, fix_changed = _update_fix_header(fix_text, new_ver, args.note, args.keep)
    i18n_new, i18n_changed = (_read(I18N_FILE), False)
    if I18N_FILE.exists():
        i18n_new, i18n_changed = _update_i18n(_read(I18N_FILE), cur_ver, new_ver)
    readme_new, readme_changed = ("", False)
    if README_FILE.exists():
        readme_new, readme_changed = _update_readme(_read(README_FILE), cur_ver, new_ver)
    patch_new, patch_changed = ("", False)
    if PATCH_NOTES_FILE.exists():
        patch_new, patch_changed = _update_patch_notes(_read(PATCH_NOTES_FILE), new_ver, args.note)

    _write(BASE_FILE, base_new, args.dry_run)
    _write(ENTRY_FILE, entry_new, args.dry_run)
    _write(FIX_HEADER_FILE, fix_new, args.dry_run)
    if i18n_changed:
        _write(I18N_FILE, i18n_new, args.dry_run)
    if readme_changed:
        _write(README_FILE, readme_new, args.dry_run)
    if patch_changed:
        _write(PATCH_NOTES_FILE, patch_new, args.dry_run)

    mode = "DRY-RUN" if args.dry_run else "UPDATED"
    print(f"[{mode}] {cur_ver} -> {new_ver}")
    print(f"[{mode}] rhk_base.py: {'changed' if base_changed else 'unchanged'}")
    print(f"[{mode}] rhk_app_web_master.py: {'changed' if entry_changed else 'unchanged'}")
    print(f"[{mode}] FIX_HEADER.md: {'changed' if fix_changed else 'unchanged'}")
    print(f"[{mode}] rhk_i18n.py: {'changed' if i18n_changed else 'unchanged'}")
    print(f"[{mode}] README.md: {'changed' if readme_changed else 'unchanged'}")
    print(f"[{mode}] PATCH_NOTES.md: {'changed' if patch_changed else 'unchanged'}")


if __name__ == "__main__":
    main()
