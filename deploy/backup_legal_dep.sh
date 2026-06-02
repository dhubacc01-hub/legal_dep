#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/legal-dep}"
DATA_DIR="${DATA_DIR:-$APP_DIR/data}"
DB_PATH="${DB_PATH:-$DATA_DIR/legal_dep_fixed.db}"
GENERATED_DIR="${GENERATED_DIR:-$DATA_DIR/generated}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
TMP_DIR="${TMP_DIR:-/tmp/legal-dep-backup}"
REMOTE_NAME="${REMOTE_NAME:-gdrive}"
REMOTE_DIR="${REMOTE_DIR:-legal-dep-backups}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-7}"
KEEP_REMOTE_DAYS="${KEEP_REMOTE_DAYS:-90}"
INCLUDE_GENERATED="${INCLUDE_GENERATED:-0}"

timestamp="$(date +%F-%H%M%S)"
archive_name="legal-dep-${timestamp}.tar.gz"
sqlite_copy_path="$TMP_DIR/legal_dep_fixed.db"
archive_path="$BACKUP_DIR/$archive_name"

mkdir -p "$BACKUP_DIR" "$TMP_DIR"
rm -f "$sqlite_copy_path"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 is required for consistent backups." >&2
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone is required to upload backups to Google Drive." >&2
  exit 1
fi

sqlite3 "$DB_PATH" ".backup '$sqlite_copy_path'"

tar_args=(
  -czf
  "$archive_path"
  -C "$TMP_DIR"
  "$(basename "$sqlite_copy_path")"
)

if [[ "$INCLUDE_GENERATED" == "1" ]] && [[ -d "$GENERATED_DIR" ]]; then
  tar_args+=(-C "$DATA_DIR" "$(basename "$GENERATED_DIR")")
fi

tar "${tar_args[@]}"
rm -f "$sqlite_copy_path"

rclone copy "$archive_path" "${REMOTE_NAME}:${REMOTE_DIR}/"

find "$BACKUP_DIR" -type f -name 'legal-dep-*.tar.gz' -mtime +"$KEEP_LOCAL_DAYS" -delete
rclone delete --min-age "${KEEP_REMOTE_DAYS}d" "${REMOTE_NAME}:${REMOTE_DIR}/"
rclone rmdirs "${REMOTE_NAME}:${REMOTE_DIR}/" --leave-root

echo "Backup created: $archive_path"
