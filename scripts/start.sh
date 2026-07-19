#!/usr/bin/env bash
# Daily start: ensure Docker is up (auto-launch Desktop on macOS), then compose up.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"

[ -f .env ] || { echo "ERROR: .env missing — run ./scripts/setup.sh first"; exit 1; }

ensure_docker

echo "==> Starting db + backend + frontend"
docker compose up -d

echo ""
echo "Started."
echo "  Frontend:  http://localhost:3000"
echo "  API docs:  http://localhost:8000/api/docs"
echo "  Diagnose:  ./scripts/doctor.sh"
echo ""
echo "Reminder: IB Gateway must be running & logged in (Read-Only API, port 4001) for live data."
