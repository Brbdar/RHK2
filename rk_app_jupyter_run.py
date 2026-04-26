# rk_app_jupyter_run.py
# Startet rhk_app_web_master.py so, dass Exceptions/Tracebacks in Jupyter sichtbar werden.
# Nutzung:
#   %cd <projektordner>
#   %run rk_app_jupyter_run.py

from __future__ import annotations

import os
import runpy
import sys
import threading
import traceback
from pathlib import Path


def _install_global_exception_hooks() -> None:
    def excepthook(exc_type, exc, tb):
        print("\n" + "=" * 80)
        print("UNCAUGHT EXCEPTION (main)")
        traceback.print_exception(exc_type, exc, tb)
        print("=" * 80 + "\n")

    sys.excepthook = excepthook

    if hasattr(threading, "excepthook"):
        def thread_excepthook(args):
            print("\n" + "=" * 80)
            print(f"UNCAUGHT EXCEPTION (thread: {args.thread.name})")
            traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
            print("=" * 80 + "\n")
        threading.excepthook = thread_excepthook


def _ensure_project_on_syspath(project_root: Path) -> None:
    root = str(project_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def main() -> int:
    project_root = Path.cwd()
    target = project_root / "rhk_app_web_master.py"

    if not target.exists():
        print("FEHLER: rhk_app_web_master.py nicht im aktuellen Ordner gefunden.")
        print(f"CWD: {project_root}")
        print("Vorhandene .py Dateien:")
        for p in sorted(project_root.glob("*.py")):
            print(" -", p.name)
        return 2

    os.environ.setdefault("GRADIO_DEBUG", "1")
    os.environ.setdefault("RHK_DEBUG", "1")

    _install_global_exception_hooks()
    _ensure_project_on_syspath(project_root)

    print("Starte rhk_app_web_master.py mit Jupyter-Tracebacks …")
    print(f"CWD: {project_root}")
    print("-" * 80)

    try:
        runpy.run_path(str(target), run_name="__main__")
        return 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
        print(f"\nSystemExit({code})")
        return code
    except Exception:
        print("\n" + "=" * 80)
        print("FATAL ERROR while running rhk_app_web_master.py")
        traceback.print_exc()
        print("=" * 80 + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
