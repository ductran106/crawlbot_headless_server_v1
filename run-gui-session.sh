#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[crawlbot] Missing .venv. Create it first: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "[crawlbot] Missing .env. Start from .env.example" >&2
  exit 1
fi

mkdir -p data logs chrome_user_data

AUTH_PATH="${XAUTHORITY:-}"
if [ -z "$AUTH_PATH" ]; then
  AUTH_PATH="$(ps -u farm4bot -o cmd= | grep "Xwayland :0" | sed -n "s/.*-auth \([^ ]*\).*/\1/p" | head -n1 || true)"
fi

if [ -z "$AUTH_PATH" ] || [ ! -f "$AUTH_PATH" ]; then
  echo "[crawlbot] Could not determine XAUTHORITY for farm4bot GUI session." >&2
  echo "[crawlbot] Try running from the desktop terminal, or export XAUTHORITY manually." >&2
  exit 1
fi

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="$AUTH_PATH"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"
export ENV_FILE=.env

printf '[crawlbot] GUI session env:\n'
printf '  DISPLAY=%s\n' "$DISPLAY"
printf '  XAUTHORITY=%s\n' "$XAUTHORITY"
printf '  DBUS_SESSION_BUS_ADDRESS=%s\n' "$DBUS_SESSION_BUS_ADDRESS"

exec ./.venv/bin/python main.py "$@"
