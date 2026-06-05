#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$APP_DIR/data/logs"
LOG_FILE="$LOG_DIR/fail-artifacts-cleanup.log"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then PYTHON_BIN=python3; fi
mkdir -p "$LOG_DIR"
{
  echo "[$(date -Is)] cleanup_fail_artifacts start app=$APP_DIR art=$APP_DIR/data/logs/fail-artifacts"
  cd "$APP_DIR"
  "$PYTHON_BIN" -c 'import json; from src.utils.fail_artifacts import cleanup_fail_artifacts; print(json.dumps(cleanup_fail_artifacts(logger=None), ensure_ascii=False, sort_keys=True))'
  echo "[$(date -Is)] cleanup_fail_artifacts done"
} >> "$LOG_FILE" 2>&1
