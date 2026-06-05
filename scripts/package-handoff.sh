#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTDIR="${1:-$ROOT/dist}"
STAMP="$(date +%Y%m%d-%H%M%S)"
NAME="crawlbot_portable_scheduler_lab-handoff-${STAMP}.zip"
OUT="$OUTDIR/$NAME"

mkdir -p "$OUTDIR"
cd "$(dirname "$ROOT")"

zip -r "$OUT" "$(basename "$ROOT")" \
  -x '*/.git/*' \
     '*/.venv/*' \
     '*/chrome_user_data/*' \
     '*/logs/*' \
     '*/logs_*/*' \
     '*/runs/*' \
     '*/backups/*' \
     '*/data/*' \
     '*/__pycache__/*' \
     '*/.pytest_cache/*' \
     '*/dist/*'

echo "$OUT"
