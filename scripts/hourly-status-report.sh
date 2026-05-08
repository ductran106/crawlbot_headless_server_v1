#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

RUN_LOG="$(find "$REPO_DIR/logs" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"

pid=$(python3 - <<'PY' "$REPO_DIR"
import glob, os, sys
repo=sys.argv[1]
for pid_dir in sorted(glob.glob('/proc/[0-9]*')):
    pid=os.path.basename(pid_dir)
    try:
        cwd=os.readlink(f'{pid_dir}/cwd')
        cmd=open(f'{pid_dir}/cmdline','rb').read().replace(b'\x00',b' ').decode('utf-8','ignore')
    except Exception:
        continue
    if cwd == repo and 'python main.py' in cmd:
        print(pid)
        break
PY
)
if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
  etime=$(ps -o etime= -p "$pid" | xargs)
  stat=$(ps -o stat= -p "$pid" | xargs)
  status_line="crawler_pid=$pid status=up etime=$etime stat=$stat"
else
  status_line="crawler_pid=${pid:-unknown} status=down"
fi

last_room_switch="<none>"
last_nav="<none>"
last_forensic="<none>"
if [[ -n "${RUN_LOG:-}" && -f "$RUN_LOG" ]]; then
  last_room_switch=$(grep -E 'ROOM_SWITCH_TRACKER' "$RUN_LOG" | tail -n 1 || true)
  last_nav=$(grep -E 'Navigation ok; verify_mode=' "$RUN_LOG" | tail -n 1 || true)
  last_forensic=$(grep -Ei 'tab crashed|read timed out|HTTPConnectionPool|BROWSER_FATAL|BROWSER_RECOVERY|BROWSER_RECOVERY_ESCALATION|ERR_TAB_CRASHED|ERR_DRIVER_TIMEOUT|driver_timeout_suspected|browser_disconnect|unknown_browser_fatal|invalid session id|group-opened-unverified|classify_browser_error is not defined|Traceback \(most recent call last\)' "$RUN_LOG" | tail -n 5 || true)
  [[ -z "$last_room_switch" ]] && last_room_switch="<none>"
  [[ -z "$last_nav" ]] && last_nav="<none>"
  [[ -z "$last_forensic" ]] && last_forensic="<none>"
fi

message_file="$REPO_DIR/logs/hourly-status-$(date +%Y%m%d-%H%M%S).md"
{
  echo "# Crawlbot hourly status"
  echo
  echo "- Time: $(date '+%F %T %Z')"
  echo "- Repo: $REPO_DIR"
  echo "- Log: ${RUN_LOG:-<none>}"
  echo "- $status_line"
  echo
  echo "## Last navigation ok"
  echo '```'
  printf '%s\n' "$last_nav"
  echo '```'
  echo
  echo "## Last room switch tracker"
  echo '```'
  printf '%s\n' "$last_room_switch"
  echo '```'
  echo
  echo "## Last forensic markers"
  echo '```'
  printf '%s\n' "$last_forensic"
  echo '```'
} > "$message_file"

summary_text=$(python3 - <<'PY' "$message_file"
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding='utf-8', errors='replace')
parts = []
for line in text.splitlines():
    s = line.strip()
    if not s or s.startswith('#') or s == '```':
        continue
    parts.append(s)
summary = "\n".join(parts[:14])
print(summary[:3500])
PY
)

printf '%s\n' "$summary_text"
printf '\n[attachment] %s\n' "$(basename "$message_file")"
