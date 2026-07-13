#!/usr/bin/env bash
# Restore a backup created by backup.sh. Usage: ./scripts/restore.sh <db_....sql.gz>
set -euo pipefail
cd "$(dirname "$0")/.."

FILE="${1:?usage: restore.sh <backup-file.sql.gz>}"
[ -f "$FILE" ] || { echo "ERROR: file not found: $FILE"; exit 1; }

echo "This will REPLACE the current database with the backup."
read -r -p "Type 'restore' to continue: " CONFIRM
[ "$CONFIRM" = "restore" ] || { echo "Aborted."; exit 1; }

source .env
docker compose up -d db
gunzip -c "$FILE" | docker compose exec -T db psql -U "${POSTGRES_USER:-ibkr}" -d "${POSTGRES_DB:-ibkr_dashboard}"
echo "Restore complete."
