#!/usr/bin/env bash
set -euo pipefail

# Refactor v1.33: BUILD_LINUX.sh - one-command PyInstaller build (supports offline wheelhouse)

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -n "${VENV_DIR:-}" ]; then
  CLEAN_VENV=0
else
  VENV_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rhk_build_venv.XXXXXX")"
  CLEAN_VENV=1
fi

cleanup() {
  if [ "$CLEAN_VENV" -eq 1 ] && [ -n "${VENV_DIR:-}" ] && [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
  fi
}

trap cleanup EXIT

"$PYTHON_BIN" tools/release_audit.py

"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

WHEELHOUSE="standalone/wheelhouse"
if [ -d "$WHEELHOUSE" ] && [ "$(ls -A "$WHEELHOUSE" 2>/dev/null)" ]; then
  python -m pip install --no-index --find-links "$WHEELHOUSE" -r requirements.txt
  python -m pip install --no-index --find-links "$WHEELHOUSE" pyinstaller
else
  python -m pip install -r requirements.txt
  python -m pip install pyinstaller
fi

pyinstaller --noconfirm --clean standalone/RHK_Befundassistent.spec

echo "OK: dist/RHK_Befundassistent"
