#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "ERROR: .env missing — run ./scripts/setup.sh first"; exit 1; }
docker compose up -d
echo "Started. Frontend: http://localhost:3000 | API docs: http://localhost:8000/api/docs"
echo "Reminder: IB Gateway must be running & logged in for live data."
