#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$REPO_DIR/logs/forensic-watch.state"
PATTERN='tab crashed|read timed out|HTTPConnectionPool|BROWSER_FATAL|BROWSER_RECOVERY|BROWSER_RECOVERY_ESCALATION|browser_fatal|browser_recovery|CRASH DIAGNOSTICS|Traceback \(most recent call last\)|selenium\.common\.exceptions\.WebDriverException|ERR_TAB_CRASHED|ERR_DRIVER_TIMEOUT|driver_timeout_suspected|browser_disconnect|unknown_browser_fatal|invalid session id|classify_browser_error is not defined'
DEDUP_WINDOW_SEC=180

mkdir -p "$REPO_DIR/logs"

LOG_FILE="$(find "$REPO_DIR/logs" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
if [[ -z "${LOG_FILE:-}" || ! -f "$LOG_FILE" ]]; then
  echo "NO_LOG"
  exit 0
fi

current_inode=$(stat -c %i "$LOG_FILE")
current_size=$(stat -c %s "$LOG_FILE")

last_inode=""
last_offset=0
last_key=""
last_ts=0
if [[ -f "$STATE_FILE" ]]; then
  source "$STATE_FILE" || true
fi

if [[ "${last_inode:-}" != "$current_inode" ]] || (( current_size < ${last_offset:-0} )); then
  last_offset=0
fi

start_byte=$(( ${last_offset:-0} + 1 ))
chunk=""
if (( current_size > 0 )) && (( start_byte <= current_size )); then
  chunk=$(tail -c +"$start_byte" "$LOG_FILE" || true)
fi

new_offset=$current_size
{
  echo "last_inode=$current_inode"
  echo "last_offset=$new_offset"
  echo "last_key=$(printf '%q' "${last_key:-}")"
  echo "last_ts=${last_ts:-0}"
} > "$STATE_FILE"

if [[ -z "$chunk" ]]; then
  echo "NO_ALERT"
  exit 0
fi

matches=$(printf '%s' "$chunk" | grep -Ein "$PATTERN" || true)
if [[ -z "$matches" ]]; then
  echo "NO_ALERT"
  exit 0
fi

match_count=$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ')
last_match=$(printf '%s\n' "$matches" | tail -n 1)
alert_key=$(printf '%s' "$last_match" | tr -s ' ' ' ' | cut -c1-300)
now=$(date +%s)
if [[ "$alert_key" == "${last_key:-}" ]] && (( now - ${last_ts:-0} < DEDUP_WINDOW_SEC )); then
  {
    echo "last_inode=$current_inode"
    echo "last_offset=$new_offset"
    echo "last_key=$(printf '%q' "$alert_key")"
    echo "last_ts=$now"
  } > "$STATE_FILE"
  echo "NO_ALERT"
  exit 0
fi

context=$(tail -n 60 "$LOG_FILE" 2>/dev/null | tail -c 2600 || true)
{
  echo "ALERT_COUNT=$match_count"
  echo "LOG_FILE=$LOG_FILE"
  echo "LAST_MATCH=$last_match"
  echo "---CONTEXT---"
  printf '%s\n' "$context"
}

{
  echo "last_inode=$current_inode"
  echo "last_offset=$new_offset"
  echo "last_key=$(printf '%q' "$alert_key")"
  echo "last_ts=$now"
} > "$STATE_FILE"
