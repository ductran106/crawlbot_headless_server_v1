#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${1:-./chrome_user_data}"
BACKUP_ROOT="${2:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/chrome_user_data_cache_backup_$STAMP"

if [[ ! -d "$PROFILE_DIR" ]]; then
  echo "Profile dir not found: $PROFILE_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "[1/4] Auditing profile before cleanup..."
du -sh "$PROFILE_DIR" || true

SAFE_PATHS=(
  "$PROFILE_DIR/Default/Cache"
  "$PROFILE_DIR/Default/Code Cache"
  "$PROFILE_DIR/Default/GPUCache"
  "$PROFILE_DIR/Default/DawnCache"
  "$PROFILE_DIR/Default/GrShaderCache"
  "$PROFILE_DIR/Default/ShaderCache"
  "$PROFILE_DIR/Default/Service Worker/CacheStorage"
  "$PROFILE_DIR/GraphiteDawnCache"
  "$PROFILE_DIR/GrShaderCache"
  "$PROFILE_DIR/ShaderCache"
  "$PROFILE_DIR/GPUPersistentCache"
  "$PROFILE_DIR/Crashpad"
  "$PROFILE_DIR/component_crx_cache"
  "$PROFILE_DIR/extensions_crx_cache"
)

echo "[2/4] Backing up removable cache paths..."
for p in "${SAFE_PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    rel="${p#${PROFILE_DIR}/}"
    mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
    cp -a "$p" "$BACKUP_DIR/$rel"
    echo "  backed up: $rel"
  fi
done

echo "[3/4] Removing cache-only paths..."
for p in "${SAFE_PATHS[@]}"; do
  if [[ -e "$p" ]]; then
    rm -rf "$p"
    echo "  removed: ${p#${PROFILE_DIR}/}"
  fi
done

echo "[4/4] Profile after cleanup..."
du -sh "$PROFILE_DIR" || true

echo "Backup saved at: $BACKUP_DIR"
