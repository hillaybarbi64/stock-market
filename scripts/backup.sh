#!/usr/bin/env bash
# Dump the database + attachments to ~/.ibkr-dashboard/backups (outside the repo,
# so backups can never end up in git). Keeps the 14 most recent backups.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/.ibkr-dashboard/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"

source .env
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-ibkr}" -d "${POSTGRES_DB:-ibkr_dashboard}" \
  | gzip > "$BACKUP_DIR/db_${STAMP}.sql.gz"

# Attachments volume (screenshots etc.)
docker compose cp backend:/app/data "$BACKUP_DIR/data_${STAMP}" 2>/dev/null || true

ls -1t "$BACKUP_DIR"/db_*.sql.gz | tail -n +15 | xargs -r rm --
echo "Backup written: $BACKUP_DIR/db_${STAMP}.sql.gz"
echo "Tip: schedule weekly via launchd/cron, e.g.:  0 20 * * 0  $PWD/scripts/backup.sh"
