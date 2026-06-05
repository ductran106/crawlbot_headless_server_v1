#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/maintenance-restart.log"

PROFILE_DIR="${PROFILE_DIR:-./chrome_user_data}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"

{
  echo "=== $(date '+%F %T') maintenance restart begin ==="

  echo "[1/3] Stopping crawler gracefully..."
  pkill -TERM -f '^python main.py$' || true
  sleep 8

  if pgrep -f '^python main.py$' >/dev/null 2>&1; then
    echo "Crawler still running after grace period; sending SIGKILL..."
    pkill -KILL -f '^python main.py$' || true
    sleep 2
  fi

  echo "[2/3] Cleaning profile cache..."
  ./scripts/cleanup-chrome-profile-cache.sh "$PROFILE_DIR" "$BACKUP_ROOT"

  echo "[3/3] Restarting crawler..."
  nohup "$PYTHON_BIN" main.py >> "$LOG_FILE" 2>&1 &
  echo "Restarted crawler with PID $!"

  echo "=== $(date '+%F %T') maintenance restart end ==="
} | tee -a "$LOG_FILE"
