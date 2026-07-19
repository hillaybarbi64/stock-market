#!/usr/bin/env bash
# One-time (and safe-to-rerun) setup: prerequisites, .env, build, migrations.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"

echo "==> Checking prerequisites"
ensure_docker

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example (with a random DB password)"
  # `|| true` avoids a spurious SIGPIPE failure under `set -o pipefail`:
  # `head -c 24` closes the pipe early, which is expected and harmless here.
  PASS="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)"
  sed "s/CHANGE_ME/${PASS}/g" .env.example > .env
  echo "    Created .env — now edit it and fill IBKR_FLEX_TOKEN + IBKR_FLEX_QUERY_ID (see docs/RUNBOOK.md §3)"
else
  echo "==> .env already exists — leaving it untouched"
fi

echo "==> Building containers"
docker compose build

echo "==> Starting database and applying migrations"
docker compose up -d db
docker compose run --rm backend uv run alembic upgrade head

echo ""
echo "Setup complete. Next steps:"
echo "  1. Make sure IB Gateway is running and logged in (Read-Only API enabled, port 4001)."
echo "  2. ./scripts/start.sh"
echo "  3. Open http://localhost:3000"
echo "  4. If something looks wrong: ./scripts/doctor.sh"
