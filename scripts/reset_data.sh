#!/usr/bin/env bash
# Deletes ALL local data (database volume + attachments). Double confirmation.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "WARNING: this permanently deletes the local database and attachments."
echo "Backups in ~/.ibkr-dashboard/backups are NOT touched."
read -r -p "Type 'delete my data' to continue: " CONFIRM
[ "$CONFIRM" = "delete my data" ] || { echo "Aborted."; exit 1; }

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"
ensure_docker

docker compose down -v
echo "All local data volumes removed. Run ./scripts/setup.sh to start fresh."
