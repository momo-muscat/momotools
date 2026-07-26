#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$HOME/momo/backup"
OLD_DIR="$BACKUP_DIR/old"
BACKUP_FILE="$BACKUP_DIR/momotools.sql.gz"
RETENTION_DAYS=90

mkdir -p "$OLD_DIR"

# 既存バックアップ（前回分）を日付付きでoldへ退避
if [ -f "$BACKUP_FILE" ]; then
    PREV_DATE="$(date -r "$BACKUP_FILE" +%Y%m%d)"
    mv "$BACKUP_FILE" "$OLD_DIR/momotools_${PREV_DATE}.sql.gz"
fi

# 新規バックアップ作成（ネイティブPostgreSQLへTCP接続、.envの認証情報を利用）
cd "$PROJECT_DIR"
set -a
source "$PROJECT_DIR/.env"
set +a
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"

# 3ヶ月(90日)以上前のバックアップを削除
find "$OLD_DIR" -name "momotools_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
