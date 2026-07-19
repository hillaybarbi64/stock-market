#!/usr/bin/env bash
# One-time (and safe-to-rerun) setup. Prefer ./scripts/start.sh day-to-day —
# start.sh now creates .env, builds, and waits for health on its own.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"

echo "==> Checking prerequisites"
ensure_docker
ensure_env_file

echo "==> Building containers"
docker compose build

echo "==> Starting database and applying migrations"
docker compose up -d db --wait 2>/dev/null || docker compose up -d db
docker compose run --rm backend uv run alembic upgrade head

echo ""
echo "Setup complete. Starting the full stack…"
exec "$(dirname "$0")/start.sh"
