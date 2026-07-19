#!/usr/bin/env bash
# Full bring-up: .env → Docker Desktop → free ports → build/start → wait → open UI.
# Idempotent. Safe to re-run. This is the single command that should get you to :3000.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"

echo "==> IBKR dashboard bring-up"

ensure_env_file
ensure_docker
free_app_ports

compose_up() {
  # Prefer --wait when available; fall back to plain up.
  if docker compose up -d --build --wait; then
    return 0
  fi
  echo "    compose --wait failed — retrying plain up…"
  docker compose up -d --build
}

echo "==> Building / starting db + backend + frontend"
set +e
compose_err="$(compose_up 2>&1)"
compose_rc=$?
set -e
if [[ $compose_rc -ne 0 ]]; then
  printf '%s\n' "$compose_err" >&2
  if printf '%s' "$compose_err" | grep -qiE 'address already in use|ports are not available'; then
    echo "==> Port conflict detected — cleaning again and retrying once"
    free_app_ports
    compose_up
  else
    exit "$compose_rc"
  fi
fi

echo "==> Waiting for HTTP endpoints"
wait_http "http://127.0.0.1:8000/api/system/health" "backend" 120 || true
wait_http "http://127.0.0.1:3000/" "frontend" 120 || true

echo ""
echo "==> Status"
if curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/health >/dev/null 2>&1; then
  echo "    health:     $(curl -fsS http://127.0.0.1:8000/api/system/health)"
  echo "    connection: $(curl -fsS http://127.0.0.1:8000/api/system/connection)"
else
  echo "    backend still not answering — run: docker compose logs --tail=80 backend"
fi

if command -v nc >/dev/null 2>&1; then
  if nc -z 127.0.0.1 4001 >/dev/null 2>&1; then
    echo "    IB Gateway: port 4001 is open"
  else
    echo "    IB Gateway: nothing on :4001 — open IB Gateway (Live, Read-Only API) for live data"
  fi
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  open "http://localhost:3000" 2>/dev/null || true
fi

echo ""
echo "Dashboard: http://localhost:3000"
echo "API docs:  http://localhost:8000/api/docs"
echo "Diagnose:  ./scripts/doctor.sh"
