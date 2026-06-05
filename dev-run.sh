#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "[crawlbot-dev] Missing .venv. Create it first: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi
if [ ! -f .env.dev ]; then
  echo "[crawlbot-dev] Missing .env.dev. Start from .env.dev.example" >&2
  exit 1
fi
mkdir -p dev-data dev-logs dev-chrome-profile
. .venv/bin/activate
export ENV_FILE=.env.dev
exec python main.py "$@"
