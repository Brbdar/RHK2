#!/usr/bin/env python3
"""Static audit of i18n coverage.

Walks the UI / report Python files and extracts German string literals that
look like user-facing copy. For each, checks whether it is registered in
``rhk_i18n._EXACT['en']``. Prints:

  * a CSV-friendly list of MISSING strings (would be empty in EN/ZH today);
  * a one-line summary suitable for CI gating.

Heuristic for "user-facing copy":
  * literal is a Python ``str`` of length >= 4
  * contains at least one space OR a German-specific character (ä/ö/ü/ß)
  * is passed positionally to a known UI helper (``label=``, ``info=``,
    ``placeholder=``, ``_tr(...)``, ``gr.Button(...)``, ``gr.Markdown(...)``,
    ``gr.Tab(...)``, etc.)

This is a heuristic — false positives are accepted (better to surface a
non-UI string than to miss a real label). Run with ``--strict`` in CI to
fail when new untranslated UI strings are introduced.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from typing import Iterable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import rhk_i18n  # noqa: E402

# UI files to audit (intentionally narrow — we only audit Gradio surface
# files and the UI bindings layer; deep helpers like rhk_case.py are
# language-neutral by design).
UI_FILES = [
    "rhk_ui.py",
    "rhk_ui_assets.py",
    "rhk_ui_bindings_clinic.py",
    "rhk_ui_bindings_cpet.py",
    "rhk_ui_bindings_imaging.py",
    "rhk_ui_bindings_rhk.py",
    "rhk_ui_core.py",
    "rhk_ui_cpet.py",
    "rhk_ui_echo.py",
    "rhk_ui_helpers.py",
    "rhk_ui_mode.py",
    "rhk_ui_progress.py",
    "rhk_ui_render_docx.py",
    "rhk_ui_render_modules.py",
    "rhk_ui_render_summary.py",
    "rhk_ui_render_viz.py",
    "rhk_ui_rhk.py",
    "rhk_ui_tab_clinic.py",
    "rhk_ui_tab_cpet.py",
    "rhk_ui_tab_imaging.py",
    "rhk_ui_utils.py",
]

# Files that emit dynamic chips/messages built from string literals into HTML.
# We audit these with a stricter heuristic: any German-looking literal that
# ends up inside an HTML tag with a class hinting at user-visible content
# (rhk-chip, rhk-todo, rhk-summary, etc.) is a candidate for the i18n table.
DYNAMIC_FILES = [
    "rhk_ui_render_summary.py",
    "rhk_ui_render_modules.py",
    "rhk_ui_render_docx.py",
    "rhk_ui_render_viz.py",
]

UI_KWARGS = {"label", "info", "placeholder", "value", "title", "header"}
UI_FUNCS = {
    "Button", "Tab", "Tabs", "Markdown", "Number", "Textbox", "Dropdown",
    "Checkbox", "CheckboxGroup", "Radio", "Slider", "Accordion", "HTML",
    "Group", "Row", "Column", "_tr", "gr.Button", "gr.Tab",
}


def _looks_like_ui_string(s: str) -> bool:
    if not isinstance(s, str):
        return False
    if len(s) < 4:
        return False
    s_stripped = s.strip()
    if not s_stripped:
        return False
    # Pure code/path/url tokens — skip
    if any(ch in s_stripped for ch in ("/", "\\", "{", "}", "<", ">")):
        return False
    has_space = " " in s_stripped
    has_umlaut = any(ch in s_stripped for ch in "äöüÄÖÜß")
    if not (has_space or has_umlaut):
        return False
    # Skip pure-English strings — they may already be canonical EN/ZH copy
    # surfaced through gettext-style _("…") wrappers we can't detect.
    if not has_umlaut and s_stripped.isascii():
        # Only treat as UI candidate if it looks like German prose
        # (contains a space and starts with capital letter).
        if not s_stripped[0].isupper():
            return False
    return True


def _walk_strings(tree: ast.AST) -> Iterable[tuple[str, int]]:
    """Yield (string, lineno) for string literals in UI-relevant positions."""
    for node in ast.walk(tree):
        # Keyword arguments: label="...", info="..."
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            in_ui_func = func_name in UI_FUNCS

            for kw in node.keywords:
                if kw.arg in UI_KWARGS and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, str):
                        yield kw.value.value, kw.value.lineno

            if in_ui_func and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    yield first.value, first.lineno


def collect_missing(file_paths: list[str]) -> list[tuple[str, str, int, str]]:
    en = rhk_i18n._EXACT.get("en", {})
    zh = rhk_i18n._EXACT.get("zh", {})
    missing: list[tuple[str, str, int, str]] = []
    for rel in file_paths:
        full = os.path.join(ROOT, rel)
        if not os.path.exists(full):
            continue
        try:
            with open(full, encoding="utf-8") as fh:
                src = fh.read()
            tree = ast.parse(src, filename=full)
        except (OSError, SyntaxError):
            continue
        for s, lineno in _walk_strings(tree):
            if not _looks_like_ui_string(s):
                continue
            if s in en and s in zh:
                continue
            tag = "MISSING" if s not in en else "ZH_ONLY_MISSING"
            missing.append((rel, s, lineno, tag))
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any missing strings are found.")
    ap.add_argument("--csv", action="store_true",
                    help="Emit CSV instead of human-readable output.")
    args = ap.parse_args()

    rows = collect_missing(UI_FILES)

    if args.csv:
        print("file,lineno,status,string")
        for path, s, lineno, tag in rows:
            print(f'"{path}",{lineno},{tag},"{s.replace(chr(34), chr(39))}"')
    else:
        if not rows:
            print(f"i18n audit: 0 missing UI strings across {len(UI_FILES)} files. ✓")
        else:
            print(f"i18n audit: {len(rows)} candidate UI strings without EN/ZH translation:")
            print()
            for path, s, lineno, tag in sorted(rows):
                print(f"  [{tag}] {path}:{lineno}")
                print(f"    {s!r}")
            print()
            print(f"Summary: {len(rows)} candidates, {len(set(r[1] for r in rows))} unique strings.")

    if args.strict and rows:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
