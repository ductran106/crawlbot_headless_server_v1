#!/usr/bin/env bash
set -euo pipefail

HEARTBEAT_FILE="/tmp/crawlbot_heartbeat"
PROJECT_DIR="/home/farm4bot/work/crawlbot_portable_scheduler_headless_server_v1"

cd "$PROJECT_DIR"
mkdir -p /tmp

(
  while true; do
    date +%s > "$HEARTBEAT_FILE"
    sleep 30
  done
) &
HB_PID=$!

cleanup() {
  kill "$HB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /bin/bash "$PROJECT_DIR/run-headless-server.sh"
