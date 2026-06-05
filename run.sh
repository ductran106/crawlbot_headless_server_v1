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
. .venv/bin/activate
export ENV_FILE=.env
exec python main.py "$@"
