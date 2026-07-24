#!/usr/bin/env bash
# Restore a backup created by backup.sh.
# Usage: ./scripts/restore.sh <db_....sql.gz> [data_YYYYmmdd_HHMMSS]
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"
# shellcheck source=lib/data-operation-lock.sh
source "$(dirname "$0")/lib/data-operation-lock.sh"

FILE="${1:?usage: restore.sh <backup-file.sql.gz> [attachments-directory]}"
ATTACHMENTS_DIR="${2:-}"
[ -f "$FILE" ] || { echo "ERROR: file not found: $FILE"; exit 1; }
gzip -t "$FILE" || { echo "ERROR: backup is not a valid gzip archive: $FILE"; exit 1; }
if [[ -n "$ATTACHMENTS_DIR" && ! -d "$ATTACHMENTS_DIR" ]]; then
  echo "ERROR: attachments directory not found: $ATTACHMENTS_DIR" >&2
  exit 1
fi

echo "This will stop the application and REPLACE the current database."
if [[ -n "$ATTACHMENTS_DIR" ]]; then
  echo "The current attachment volume will also be replaced."
fi
read -r -p "Type 'restore' to continue: " CONFIRM
[ "$CONFIRM" = "restore" ] || { echo "Aborted."; exit 1; }

RESTORE_TEMP="$(mktemp -d "${TMPDIR:-/tmp}/ibkr-dashboard-restore.XXXXXX")"
RESTORE_DUMP="${RESTORE_TEMP}/restore.sql.gz"
RESTORE_ATTACHMENTS=""
RESTORE_PRE_REPLACEMENT=0
RESTORE_REPLACEMENT_STARTED=0
ORIGINAL_WRITERS=()

cleanup_restore() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  rm -rf -- "${RESTORE_TEMP:-}"
  if [[ "$RESTORE_PRE_REPLACEMENT" == "1" ]] \
    && [[ "$RESTORE_REPLACEMENT_STARTED" == "0" ]] \
    && [[ ${#ORIGINAL_WRITERS[@]} -gt 0 ]]; then
    echo "Restore preflight failed; returning the original application services..."
    if ! docker compose up -d "${ORIGINAL_WRITERS[@]}"; then
      echo "WARNING: Could not restart the original services automatically." >&2
    fi
  fi
  release_data_operation_lock
  exit "$status"
}
trap cleanup_restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

BACKUP_DIR="${BACKUP_DIR:-$HOME/.ibkr-dashboard/backups}"
IBKR_DATA_OPERATION_LOCK_ROOT="${IBKR_DATA_OPERATION_LOCK_ROOT:-$HOME/.ibkr-dashboard}"
export BACKUP_DIR IBKR_DATA_OPERATION_LOCK_ROOT
acquire_data_operation_lock "$IBKR_DATA_OPERATION_LOCK_ROOT" restore

cp -- "$FILE" "$RESTORE_DUMP"
gzip -t "$RESTORE_DUMP"
if [[ -n "$ATTACHMENTS_DIR" ]]; then
  RESTORE_ATTACHMENTS="${RESTORE_TEMP}/data"
  cp -R -- "$ATTACHMENTS_DIR" "$RESTORE_ATTACHMENTS"
fi

ensure_docker

DB_USER="$(
  awk -F= '$1 == "POSTGRES_USER" { print substr($0, index($0, "=") + 1); exit }' .env
)"
DB_NAME="$(
  awk -F= '$1 == "POSTGRES_DB" { print substr($0, index($0, "=") + 1); exit }' .env
)"
DB_USER="${DB_USER:-ibkr}"
DB_NAME="${DB_NAME:-ibkr_dashboard}"
if [[ ! "$DB_USER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] \
  || [[ ! "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "ERROR: POSTGRES_USER and POSTGRES_DB must be simple PostgreSQL identifiers." >&2
  exit 1
fi

RUNNING_SERVICES="$(docker compose ps --status running --services)"
while IFS= read -r service; do
  case "$service" in
    backend | frontend) ORIGINAL_WRITERS+=("$service") ;;
  esac
done <<<"$RUNNING_SERVICES"
RESTORE_PRE_REPLACEMENT=1

echo "Stopping application writers..."
docker compose stop backend frontend
if docker compose ps --status running --services \
  | grep -Eq '^(backend|frontend)$'; then
  echo "ERROR: backend/frontend are still running; restore aborted before database replacement." >&2
  exit 1
fi
docker compose up -d db

echo "Creating a safety backup of the current state before replacement..."
"$(dirname "$0")/backup.sh"

RESTORE_REPLACEMENT_STARTED=1
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d postgres \
  -v db_name="$DB_NAME" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'db_name' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"db_name";
CREATE DATABASE :"db_name";
SQL

gunzip -c "$RESTORE_DUMP" \
  | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME"

if [[ -n "$RESTORE_ATTACHMENTS" ]]; then
  docker compose run --rm --no-deps --user 0:0 appdata-init \
    sh -c 'find /app/data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
  docker compose run --rm --no-deps --user 0:0 \
    -v "${RESTORE_ATTACHMENTS}:/restore:ro" \
    appdata-init \
    sh -c 'cp -a /restore/. /app/data/ && chown -R app:app /app/data'
fi

echo "Starting the restored application..."
if docker compose up --help 2>/dev/null | grep -q -- '--wait'; then
  docker compose up -d --wait
else
  docker compose up -d
fi
wait_http "http://127.0.0.1:8000/api/system/health" "backend" 120
wait_http "http://127.0.0.1:3000/" "frontend" 120
RESTORE_PRE_REPLACEMENT=0
echo "Restore completed successfully."
