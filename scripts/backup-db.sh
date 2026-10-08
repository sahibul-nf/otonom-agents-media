#!/usr/bin/env bash
# Automated backup script for Otonom Media SQLite database
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${MEDIA_ENGINE_DB:-"$ROOT_DIR/media-engine/data/media_engine.sqlite"}"
BACKUP_DIR="${BACKUP_DIR:-"$ROOT_DIR/backups"}"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
TARGET_FILE="$BACKUP_DIR/media_engine_$TIMESTAMP.sqlite"
RETENTION_DAYS=7

if [ ! -f "$DB_PATH" ]; then
  echo "[backup] SQLite database not found at: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "[backup] Running online SQLite backup from $DB_PATH to $TARGET_FILE..."
sqlite3 "$DB_PATH" ".backup '$TARGET_FILE'"

# Compress backup
gzip -f "$TARGET_FILE"
echo "[backup] Backup created: ${TARGET_FILE}.gz"

# Clean up older backups than RETENTION_DAYS
echo "[backup] Pruning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -name "media_engine_*.sqlite.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[backup] Backup process completed successfully."
