#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
PATTERN='(ROOM_SWITCH_TRACKER|BROWSER_RECOVERY_REQUESTED|BROWSER_RECOVERY_RESULT|BROWSER_RESTART_REQUESTED|BROWSER_RESTART_RESULT|GROUP_RECONNECT_RESULT|ZALO_STATUS_TRANSITION|LOGIN_STATE_UNKNOWN|ZALO_STATUS_CHECK_ERROR|SAVE_DOCUMENT_RESULT) '
EVENT_PREFIX_REGEX='^.*(ROOM_SWITCH_TRACKER|BROWSER_RECOVERY_REQUESTED|BROWSER_RECOVERY_RESULT|BROWSER_RESTART_REQUESTED|BROWSER_RESTART_RESULT|GROUP_RECONNECT_RESULT|ZALO_STATUS_TRANSITION|LOGIN_STATE_UNKNOWN|ZALO_STATUS_CHECK_ERROR|SAVE_DOCUMENT_RESULT) '

GROUP_FILTER=""
EVENT_FILTER=""
SINCE_FILTER=""
TAIL_LIMIT=""
FAIL_ONLY=0
LATEST_ONLY=0
SUMMARY_ONLY=0
OUTPUT_MODE="json"
INPUTS=()

usage() {
  cat <<'EOF'
Usage:
  ./scripts/event-timeline.sh [options] [logfile ...]

Options:
  --group <text>     Filter by .group or .target_group substring (case-insensitive)
  --event <name>     Filter by .event exact match
  --since <iso>      Filter by .ts >= ISO-8601 timestamp
  --tail <n>         Keep only last n matched events after filtering
  --fail-only        Show only suspicious/failure events
  --latest           Auto-pick the latest log file in LOG_DIR
  --summary          Print aggregate counts instead of raw timeline
  --json             Output JSON lines (default)
  --pretty           Output human-friendly timeline lines
  -h, --help         Show this help

Examples:
  ./scripts/event-timeline.sh logs/*.log
  ./scripts/event-timeline.sh --latest --fail-only
  ./scripts/event-timeline.sh --event room_switch_tracker --tail 20
  ./scripts/event-timeline.sh --group "RETURN ROOM LỊCH" --since 2026-03-19T04:45:00 logs/*.log
  ./scripts/event-timeline.sh --latest --pretty
  ./scripts/event-timeline.sh --latest --summary
EOF
}

if ! command -v rg >/dev/null 2>&1; then
  echo "Missing dependency: rg" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing dependency: jq" >&2
  exit 1
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --group)
      GROUP_FILTER="${2:-}"
      shift 2
      ;;
    --event)
      EVENT_FILTER="${2:-}"
      shift 2
      ;;
    --since)
      SINCE_FILTER="${2:-}"
      shift 2
      ;;
    --tail)
      TAIL_LIMIT="${2:-}"
      shift 2
      ;;
    --fail-only)
      FAIL_ONLY=1
      shift
      ;;
    --latest)
      LATEST_ONLY=1
      shift
      ;;
    --summary)
      SUMMARY_ONLY=1
      shift
      ;;
    --json)
      OUTPUT_MODE="json"
      shift
      ;;
    --pretty)
      OUTPUT_MODE="pretty"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        INPUTS+=("$1")
        shift
      done
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      INPUTS+=("$1")
      shift
      ;;
  esac
done

if [ "$LATEST_ONLY" -eq 1 ]; then
  latest_file="$(find "$LOG_DIR" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
  if [ -z "$latest_file" ]; then
    echo "No log files found for --latest under $LOG_DIR" >&2
    exit 1
  fi
  INPUTS=("$latest_file")
elif [ "${#INPUTS[@]}" -eq 0 ]; then
  shopt -s nullglob
  INPUTS=("$LOG_DIR"/*.log)
  shopt -u nullglob
fi

if [ "${#INPUTS[@]}" -eq 0 ]; then
  echo "No log files found. Pass files explicitly, use --latest, or set LOG_DIR." >&2
  exit 1
fi

JQ_FILTER='select(
  (($event == "") or (.event == $event))
  and (($since == "") or ((.ts // "") >= $since))
  and (($group == "") or (
    ((.group // "") | ascii_downcase | contains($group | ascii_downcase))
    or ((.target_group // "") | ascii_downcase | contains($group | ascii_downcase))
  ))
  and (($fail_only == "0") or (
    (.success == false)
    or (.event == "login_state_unknown")
    or (.event == "zalo_status_check_error")
    or ((.event == "group_reconnect_result") and (.success != true))
    or ((.event == "browser_recovery_result") and (.success != true))
    or ((.event == "browser_restart_result") and (.success != true))
    or ((.event == "zalo_status_transition") and ((.reason // .status_reason // "") != "ready-in-target-group"))
  ))
) | {
  ts,
  event,
  group,
  session_id,
  host,
  room_cycle,
  reason:(.reason // .status_reason // ""),
  step:(.step // ""),
  success:(.success // null),
  fail_streak:(.fail_streak // null),
  processed_count:(.processed_count // null),
  sleep_s:(.sleep_s // null),
  backlog_hot:(.backlog_hot // null),
  target_group:(.target_group // ""),
  group_title:(.group_title // ""),
  error:(.error // "")
}'

PIPE_OUTPUT="$({
  rg --no-heading -e "$PATTERN" "${INPUTS[@]}" \
    | while IFS= read -r line; do
        stripped="$(printf '%s\n' "$line" | sed -E "s/${EVENT_PREFIX_REGEX}//")"
        printf '%s\n' "$stripped"
      done \
    | jq -Rrc --arg group "$GROUP_FILTER" --arg event "$EVENT_FILTER" --arg since "$SINCE_FILTER" --arg fail_only "$FAIL_ONLY" "fromjson? | select(type == \"object\") | $JQ_FILTER"
} || true)"

if [ -n "$TAIL_LIMIT" ]; then
  PIPE_OUTPUT="$(printf '%s\n' "$PIPE_OUTPUT" | tail -n "$TAIL_LIMIT")"
fi

if [ "$SUMMARY_ONLY" -eq 1 ]; then
  if [ -z "$PIPE_OUTPUT" ]; then
    if [ "$OUTPUT_MODE" = "pretty" ]; then
      echo "No matching events."
    else
      echo '{"total":0,"by_event":[],"by_group":[],"failures":0}'
    fi
    exit 0
  fi

  SUMMARY_JSON="$(printf '%s\n' "$PIPE_OUTPUT" | jq -sc '
    {
      total: length,
      failures: map(select((.success == false) or (.event == "login_state_unknown") or (.event == "zalo_status_check_error"))) | length,
      by_event: (group_by(.event) | map({event: .[0].event, count: length}) | sort_by(-.count, .event)),
      by_group: (group_by(.group // "") | map(select((.[0].group // "") != "") | {group: .[0].group, count: length}) | sort_by(-.count, .group))
    }
  ')"

  if [ "$OUTPUT_MODE" = "pretty" ]; then
    printf '%s\n' "$SUMMARY_JSON" | jq -r '
      "total=" + (.total|tostring),
      "failures=" + (.failures|tostring),
      "by_event:",
      (.by_event[]? | "  - " + .event + ": " + (.count|tostring)),
      "by_group:",
      (.by_group[]? | "  - " + .group + ": " + (.count|tostring))
    '
  else
    printf '%s\n' "$SUMMARY_JSON"
  fi
  exit 0
fi

if [ "$OUTPUT_MODE" = "pretty" ]; then
  printf '%s\n' "$PIPE_OUTPUT" | jq -r '
    if type != "object" then empty
    else
      (.ts // "-") + " | " + (.event // "-")
      + " | group=" + (.group // "-")
      + " | reason=" + (.reason // "-")
      + " | success=" + ((.success // "null") | tostring)
      + " | step=" + (.step // "-")
      + " | fail_streak=" + ((.fail_streak // "null") | tostring)
      + " | processed=" + ((.processed_count // "null") | tostring)
      + " | sleep=" + ((.sleep_s // "null") | tostring)
      + " | error=" + (.error // "")
    end
  '
else
  printf '%s\n' "$PIPE_OUTPUT"
fi
