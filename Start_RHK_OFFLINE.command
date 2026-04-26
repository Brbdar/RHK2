#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Offline/Privacy profile: no cloud share, local-only bind.
export RHK_DEPLOY_PROFILE="${RHK_DEPLOY_PROFILE:-offline}"
export RHK_STANDALONE="${RHK_STANDALONE:-1}"
export RHK_OFFLINE="${RHK_OFFLINE:-1}"
export RHK_PRIVACY_MODE="${RHK_PRIVACY_MODE:-1}"
export RHK_ALLOW_CDN_ASSETS="${RHK_ALLOW_CDN_ASSETS:-0}"
export RHK_ENABLE_BROWSER_IMPORT="${RHK_ENABLE_BROWSER_IMPORT:-0}"
export RHK_ENABLE_BROWSER_OCR="${RHK_ENABLE_BROWSER_OCR:-0}"
export RHK_FORCE_HOSTED_BROWSER_TOOLS="${RHK_FORCE_HOSTED_BROWSER_TOOLS:-0}"
export RHK_ALLOW_SERVER_UPLOAD="${RHK_ALLOW_SERVER_UPLOAD:-0}"
export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-127.0.0.1}"
export GRADIO_SHARE="${GRADIO_SHARE:-0}"

BOOTSTRAP_PY="${PYTHON_BOOTSTRAP:-python3}"
if ! command -v "$BOOTSTRAP_PY" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    BOOTSTRAP_PY="python"
  else
    echo "Fehler: Weder 'python3' noch 'python' wurde gefunden." >&2
    exit 1
  fi
fi

# OneDrive/iCloud kann .venv-Dateien blockieren; daher Standard-venv im Home-Verzeichnis.
VENV_DIR="${RHK_VENV_DIR:-$HOME/.rhk_befundassistent_venv}"
PYTHON_BIN="$VENV_DIR/bin/python"

echo "Starte RHK Befundassistent im OFFLINE-Modus..."
echo "Projekt: $ROOT_DIR"
echo "Profil: $RHK_DEPLOY_PROFILE | Server: ${GRADIO_SERVER_NAME}:7860"
echo "Python-Umgebung: $VENV_DIR"

# OneDrive-Placeholders ("dataless") blockieren Python offline und wirken wie "kein Start".
ESSENTIAL_FILES=(
  "rhk_app_web_master.py"
  "rhk_ui.py"
  "rhk_base.py"
  "rhk_i18n.py"
  "rhk_ui_assets.py"
  "requirements.txt"
)
RUNTIME_DIR="${RHK_RUNTIME_DIR:-$HOME/RHK-BEfunder-offline-runtime}"
RUN_ROOT="$ROOT_DIR"

SOURCE_DATALLESS=()
SOURCE_MISSING=()
for rel in "${ESSENTIAL_FILES[@]}"; do
  abs="$ROOT_DIR/$rel"
  if [ ! -f "$abs" ]; then
    SOURCE_MISSING+=("$rel")
    continue
  fi
  if ls -lO "$abs" 2>/dev/null | grep -q "dataless"; then
    SOURCE_DATALLESS+=("$rel")
  fi
done

if [ "${#SOURCE_MISSING[@]}" -gt 0 ]; then
  echo "Fehler: Pflichtdateien fehlen im Projektordner:" >&2
  for rel in "${SOURCE_MISSING[@]}"; do
    echo "  - $rel" >&2
  done
  exit 2
fi

if [ "${#SOURCE_DATALLESS[@]}" -eq 0 ]; then
  # Standard: direkt aus Projektordner starten (schnell, kein OneDrive-Risiko durch Voll-Sync).
  RUN_ROOT="$ROOT_DIR"
  # Optionaler Voll-Sync nur bei Bedarf: RHK_SYNC_RUNTIME=1
  if [ "${RHK_SYNC_RUNTIME:-0}" = "1" ]; then
    mkdir -p "$RUNTIME_DIR"
    if command -v rsync >/dev/null 2>&1; then
      if rsync -a --delete \
        --exclude=".venv/" \
        --exclude="__pycache__/" \
        --exclude=".pytest_cache/" \
        --exclude=".mypy_cache/" \
        --exclude=".ruff_cache/" \
        --exclude="run_logs/" \
        --exclude="exports/" \
        "$ROOT_DIR/" "$RUNTIME_DIR/"; then
        RUN_ROOT="$RUNTIME_DIR"
        echo "Lokale Laufkopie aktualisiert: $RUN_ROOT"
      else
        echo "Warnung: Laufkopie konnte nicht aktualisiert werden, starte direkt aus Projektordner." >&2
      fi
    else
      echo "Warnung: rsync nicht gefunden, starte direkt aus Projektordner." >&2
    fi
  fi
else
  CACHE_DATALLESS=()
  CACHE_MISSING=()
  for rel in "${ESSENTIAL_FILES[@]}"; do
    abs="$RUNTIME_DIR/$rel"
    if [ ! -f "$abs" ]; then
      CACHE_MISSING+=("$rel")
      continue
    fi
    if ls -lO "$abs" 2>/dev/null | grep -q "dataless"; then
      CACHE_DATALLESS+=("$rel")
    fi
  done

  if [ "${#CACHE_MISSING[@]}" -eq 0 ] && [ "${#CACHE_DATALLESS[@]}" -eq 0 ]; then
    RUN_ROOT="$RUNTIME_DIR"
    echo "Hinweis: OneDrive-Platzhalter erkannt, starte aus lokaler Laufkopie: $RUN_ROOT"
  else
    echo "Fehler: OneDrive-Platzhalter erkannt (dataless), und keine nutzbare lokale Laufkopie vorhanden." >&2
    echo "Bitte im Finder für den Projektordner 'Immer auf diesem Gerät behalten' aktivieren und den Starter einmal online ausführen." >&2
    echo "Betroffene Quelldateien:" >&2
    for rel in "${SOURCE_DATALLESS[@]}"; do
      echo "  - $rel" >&2
    done
    if [ "${#CACHE_MISSING[@]}" -gt 0 ] || [ "${#CACHE_DATALLESS[@]}" -gt 0 ]; then
      echo "Lokale Laufkopie unvollständig in: $RUNTIME_DIR" >&2
    fi
    exit 2
  fi
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Erzeuge lokale Python-Umgebung..."
  mkdir -p "$VENV_DIR"
  "$BOOTSTRAP_PY" -m venv "$VENV_DIR"
fi

# Defekte Umgebung automatisch neu aufsetzen.
if ! "$PYTHON_BIN" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
  echo "Warnung: Python-Umgebung ist defekt und wird neu erstellt..."
  rm -rf "$VENV_DIR"
  "$BOOTSTRAP_PY" -m venv "$VENV_DIR"
fi

if ! "$PYTHON_BIN" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('gradio') else 1)" >/dev/null 2>&1; then
  echo "Installiere Python-Abhängigkeiten aus requirements.txt..."
  "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$PYTHON_BIN" -m pip install --upgrade pip
  if ! "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"; then
    echo "Fehler: Installation fehlgeschlagen. Bitte einmal online ausführen:" >&2
    echo "  $PYTHON_BIN -m pip install -r \"$ROOT_DIR/requirements.txt\"" >&2
    exit 1
  fi
fi

exec "$PYTHON_BIN" "$RUN_ROOT/rhk_app_web_master.py"
