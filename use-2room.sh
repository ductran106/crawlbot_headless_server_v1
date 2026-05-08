#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cp .env.2room.recommended .env
echo "Switched to 2-room profile: .env <- .env.2room.recommended"
echo "GROUP_NAMES=$(grep '^GROUP_NAMES=' .env | cut -d= -f2-)"
