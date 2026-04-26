#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
AUDIT_RELEASE=0

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --audit-release)
      AUDIT_RELEASE=1
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 [--dry-run] [--audit-release]" >&2
      exit 2
      ;;
  esac
done

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] $*"
  else
    eval "$@"
  fi
}

echo "Cleanup root: $ROOT_DIR"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Mode: DRY-RUN"
fi

run_cmd "find \"$ROOT_DIR\" -type d -name '__pycache__' -prune -exec rm -rf {} +"
run_cmd "find \"$ROOT_DIR\" -type f -name '*.pyc' -delete"
run_cmd "find \"$ROOT_DIR\" -type f -name '*.pyo' -delete"
run_cmd "rm -rf \"$ROOT_DIR/.pytest_cache\" \"$ROOT_DIR/.mypy_cache\" \"$ROOT_DIR/.ruff_cache\""
run_cmd "find \"$ROOT_DIR/run_logs\" -type f -name '*.log' -delete 2>/dev/null || true"
run_cmd "find \"$ROOT_DIR\" -maxdepth 1 -type f -name '*.log' -delete"

echo "Cleanup finished."

if [[ "$AUDIT_RELEASE" -eq 1 ]]; then
  echo "Running release audit..."
  python3 "$ROOT_DIR/tools/release_audit.py"
fi
