#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[crawlbot-headless] Missing .venv" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "[crawlbot-headless] Missing .env" >&2
  exit 1
fi

mkdir -p data logs chrome_user_data

export ENV_FILE=.env
export HEADLESS=true
export CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT:-9222}"

exec .venv/bin/python main.py "$@"
