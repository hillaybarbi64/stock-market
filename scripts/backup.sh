#!/usr/bin/env bash
# Dump the database + attachments to ~/.ibkr-dashboard/backups (outside the repo,
# so backups can never end up in git). Keeps the 14 most recent backups.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"
# shellcheck source=lib/data-operation-lock.sh
source "$(dirname "$0")/lib/data-operation-lock.sh"
ensure_docker

BACKUP_DIR="${BACKUP_DIR:-$HOME/.ibkr-dashboard/backups}"
IBKR_DATA_OPERATION_LOCK_ROOT="${IBKR_DATA_OPERATION_LOCK_ROOT:-$HOME/.ibkr-dashboard}"
export IBKR_DATA_OPERATION_LOCK_ROOT
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TEMP_DUMP=""
TEMP_ATTACHMENTS=""
FINAL_DUMP=""
FINAL_ATTACHMENTS=""
BACKUP_COMMITTED=0

cleanup_backup() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  rm -f "${TEMP_DUMP:-}"
  rm -rf -- "${TEMP_ATTACHMENTS:-}"
  if [[ "$BACKUP_COMMITTED" == "0" ]] \
    && [[ -n "$FINAL_ATTACHMENTS" ]] \
    && [[ -d "$FINAL_ATTACHMENTS" ]] \
    && [[ ! -f "$FINAL_DUMP" ]]; then
    rm -rf -- "$FINAL_ATTACHMENTS"
  fi
  release_data_operation_lock
  exit "$status"
}
trap cleanup_backup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
acquire_data_operation_lock "$IBKR_DATA_OPERATION_LOCK_ROOT" backup

STAMP=""
for _stamp_attempt in 1 2 3 4 5; do
  stamp_candidate="$(date +%Y%m%d_%H%M%S)"
  if [[ ! -e "$BACKUP_DIR/db_${stamp_candidate}.sql.gz" ]] \
    && [[ ! -e "$BACKUP_DIR/data_${stamp_candidate}" ]]; then
    STAMP="$stamp_candidate"
    break
  fi
  sleep 1
done
if [[ -z "$STAMP" ]]; then
  echo "ERROR: Could not allocate a unique backup timestamp." >&2
  exit 1
fi
FINAL_DUMP="$BACKUP_DIR/db_${STAMP}.sql.gz"
TEMP_DUMP="$BACKUP_DIR/.db_${STAMP}.sql.gz.tmp"
FINAL_ATTACHMENTS="$BACKUP_DIR/data_${STAMP}"
TEMP_ATTACHMENTS="$BACKUP_DIR/.data_${STAMP}.tmp"

DB_USER="$(
  awk -F= '$1 == "POSTGRES_USER" { print substr($0, index($0, "=") + 1); exit }' .env
)"
DB_NAME="$(
  awk -F= '$1 == "POSTGRES_DB" { print substr($0, index($0, "=") + 1); exit }' .env
)"
DB_USER="${DB_USER:-ibkr}"
DB_NAME="${DB_NAME:-ibkr_dashboard}"
docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" \
  | gzip > "$TEMP_DUMP"
gzip -t "$TEMP_DUMP"
chmod 600 "$TEMP_DUMP"

# Snapshot the named volume directly so a stopped/missing backend container
# cannot make a restore safety backup silently omit attachments.
APPDATA_VOLUME="$(
  docker volume ls \
    --filter label=com.docker.compose.project=ibkr-dashboard \
    --filter label=com.docker.compose.volume=appdata \
    --quiet \
    | head -n 1
)"
mkdir "$TEMP_ATTACHMENTS"
if [[ -n "$APPDATA_VOLUME" ]]; then
  BACKUP_HOST_UID="$(id -u)"
  BACKUP_HOST_GID="$(id -g)"
  if ! docker run --rm --network none --user 0:0 \
    -e BACKUP_HOST_UID="$BACKUP_HOST_UID" \
    -e BACKUP_HOST_GID="$BACKUP_HOST_GID" \
    -e BACKUP_STAMP="$STAMP" \
    -v "${APPDATA_VOLUME}:/source:ro" \
    -v "${BACKUP_DIR}:/backup" \
    postgres:16-alpine \
    sh -c '
      trap "chown -R ${BACKUP_HOST_UID}:${BACKUP_HOST_GID} /backup/.data_${BACKUP_STAMP}.tmp 2>/dev/null || true" EXIT
      cp -a /source/. "/backup/.data_${BACKUP_STAMP}.tmp/" &&
      chown -R "${BACKUP_HOST_UID}:${BACKUP_HOST_GID}" "/backup/.data_${BACKUP_STAMP}.tmp"
    '; then
    echo "ERROR: Backup aborted because attachments could not be copied." >&2
    exit 1
  fi
fi

# Promote attachments first and the DB dump last. The dump's presence is the
# completion marker used by rotation and restore discovery.
mv "$TEMP_ATTACHMENTS" "$FINAL_ATTACHMENTS"
mv "$TEMP_DUMP" "$FINAL_DUMP"
BACKUP_COMMITTED=1

ls -1t "$BACKUP_DIR"/db_*.sql.gz | tail -n +15 | while IFS= read -r old_backup; do
  old_name="$(basename "$old_backup")"
  old_stamp="${old_name#db_}"
  old_stamp="${old_stamp%.sql.gz}"
  rm -- "$old_backup"
  if [[ "$old_stamp" =~ ^[0-9]{8}_[0-9]{6}$ ]]; then
    rm -rf -- "$BACKUP_DIR/data_${old_stamp}"
  fi
done
echo "Backup written: $FINAL_DUMP"
if [[ -d "$FINAL_ATTACHMENTS" ]]; then
  echo "Attachments written: $FINAL_ATTACHMENTS"
fi
echo "Tip: schedule weekly via launchd/cron, e.g.:  0 20 * * 0  $PWD/scripts/backup.sh"
