#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cp .env.3room.recommended .env
echo "Switched to 3-room profile: .env <- .env.3room.recommended"
echo "GROUP_NAMES=$(grep '^GROUP_NAMES=' .env | cut -d= -f2-)"
