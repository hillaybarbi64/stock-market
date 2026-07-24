#!/usr/bin/env bash
# Full bring-up. Idempotent. Does NOT tear down a healthy stack.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"

echo "==> IBKR dashboard bring-up"

ensure_env_file
ensure_docker

stack_healthy() {
  curl -fsS --connect-timeout 1 http://127.0.0.1:8000/api/system/health >/dev/null 2>&1 \
    && curl -fsS --connect-timeout 1 http://127.0.0.1:3000/ >/dev/null 2>&1
}

print_status() {
  local gateway_port gateway_mode
  echo ""
  echo "==> Status"
  if curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/health >/dev/null 2>&1; then
    echo "    health:     $(curl -fsS http://127.0.0.1:8000/api/system/health)"
    echo "    connection: $(curl -fsS http://127.0.0.1:8000/api/system/connection)"
  else
    echo "    backend DOWN"
    docker compose ps 2>/dev/null || true
    echo "    --- backend logs ---"
    docker compose logs --tail=60 backend 2>/dev/null || true
    echo "    --- frontend logs ---"
    docker compose logs --tail=40 frontend 2>/dev/null || true
  fi
  gateway_port="$(
    awk -F= '$1 == "IBKR_GATEWAY_PORT" { print substr($0, index($0, "=") + 1); exit }' .env
  )"
  gateway_port="${gateway_port:-4001}"
  gateway_mode="Live"
  if [[ "$gateway_port" == "4002" || "$gateway_port" == "7497" ]]; then
    gateway_mode="Paper"
  fi
  if command -v nc >/dev/null 2>&1; then
    if nc -z 127.0.0.1 "$gateway_port" >/dev/null 2>&1; then
      echo "    IB Gateway: ${gateway_mode} port ${gateway_port} is open"
    else
      echo "    IB Gateway: nothing on :${gateway_port} — open IB Gateway (${gateway_mode}, Read-Only API)"
    fi
  fi
}

if stack_healthy; then
  echo "==> Stack already healthy — leaving it running"
  print_status
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "http://localhost:3000" 2>/dev/null || true
  fi
  echo ""
  echo "Dashboard: http://localhost:3000"
  exit 0
fi

# Only free ports when the stack is not already serving.
# Avoids needlessly taking a working dashboard down on every start.sh.
free_app_ports

compose_up() {
  # Avoid compose --wait here: a slow frontend healthcheck was aborting the
  # whole bring-up even when containers were fine. We poll HTTP ourselves.
  docker compose up -d --build
}

echo "==> Building / starting db + backend + frontend"
set +e
compose_err="$(compose_up 2>&1)"
compose_rc=$?
set -e
printf '%s\n' "$compose_err"
if [[ $compose_rc -ne 0 ]]; then
  if printf '%s' "$compose_err" | grep -qiE 'address already in use|ports are not available'; then
    echo "==> Port conflict — cleaning and retrying once"
    free_app_ports
    compose_up
  else
    echo "==> compose failed" >&2
    docker compose ps >&2 || true
    docker compose logs --tail=80 >&2 || true
    exit "$compose_rc"
  fi
fi

echo "==> Waiting for HTTP endpoints"
wait_http "http://127.0.0.1:8000/api/system/health" "backend" 180 || true
wait_http "http://127.0.0.1:3000/" "frontend" 180 || true

# If still down, one recovery attempt (recreate without full image rebuild).
if ! stack_healthy; then
  echo "==> Stack not healthy — recreating containers once"
  docker compose up -d --force-recreate --no-build || true
  wait_http "http://127.0.0.1:8000/api/system/health" "backend" 120 || true
  wait_http "http://127.0.0.1:3000/" "frontend" 120 || true
fi

print_status

if [[ "$(uname -s)" == "Darwin" ]]; then
  open "http://localhost:3000" 2>/dev/null || true
fi

echo ""
echo "Dashboard: http://localhost:3000"
echo "API docs:  http://localhost:8000/api/docs"
echo "Diagnose:  ./scripts/doctor.sh"

if ! stack_healthy; then
  exit 1
fi
