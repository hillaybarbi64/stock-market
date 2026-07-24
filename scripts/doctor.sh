#!/usr/bin/env bash
# Quick health check for the local Mac setup (Docker, ports, IB Gateway, app).
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=lib/ensure-docker.sh
source "$(dirname "$0")/lib/ensure-docker.sh"
ensure_docker_cli || true

ok()   { printf '  ✅ %s\n' "$*"; }
warn() { printf '  ⚠️  %s\n' "$*"; }
bad()  { printf '  ❌ %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "==> Environment"
echo "    host: $(uname -s) $(uname -m) · $(hostname)"
if [[ -f .env ]]; then ok ".env present"; else bad ".env missing — run ./scripts/setup.sh"; fi

echo ""
echo "==> Docker"
if have docker; then
  ok "docker CLI: $(docker --version 2>/dev/null | head -1)"
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is running"
  else
    bad "Docker daemon is NOT running"
    if [[ "$(uname -s)" == "Darwin" ]]; then
      echo "       Fix: open Docker Desktop (or re-run ./scripts/start.sh — it will try to launch it)"
    fi
  fi
else
  bad "docker CLI not installed — https://www.docker.com/products/docker-desktop/"
fi

echo ""
echo "==> App ports (the database is intentionally not exposed in release mode)"
for port in 3000 8000; do
  if have lsof && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    ok "port $port is listening"
  elif have nc && nc -z 127.0.0.1 "$port" >/dev/null 2>&1; then
    ok "port $port accepts connections"
  else
    warn "port $port is closed"
  fi
done

gateway_port="$(
  awk -F= '$1 == "IBKR_GATEWAY_PORT" { print substr($0, index($0, "=") + 1); exit }' .env 2>/dev/null
)"
gateway_port="${gateway_port:-4001}"
gateway_mode="Live"
if [[ "$gateway_port" == "4002" || "$gateway_port" == "7497" ]]; then
  gateway_mode="Paper"
fi
echo ""
echo "==> IB Gateway (${gateway_mode} read-only API on ${gateway_port})"
if have nc && nc -z 127.0.0.1 "$gateway_port" >/dev/null 2>&1; then
  ok "something is listening on 127.0.0.1:${gateway_port}"
else
  bad "nothing on 127.0.0.1:${gateway_port} — open IB Gateway, login ${gateway_mode}, enable Read-Only API"
fi

echo ""
echo "==> App endpoints"
if curl -fsS --connect-timeout 2 http://127.0.0.1:3000/ >/dev/null 2>&1; then
  ok "frontend http://localhost:3000"
else
  warn "frontend not reachable on :3000"
fi

if curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/health >/dev/null 2>&1; then
  health="$(curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/health)"
  ok "backend health: $health"
  if curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/connection >/dev/null 2>&1; then
    conn="$(curl -fsS --connect-timeout 2 http://127.0.0.1:8000/api/system/connection)"
    echo "       connection: $conn"
  fi
else
  warn "backend not reachable on :8000"
fi

echo ""
echo "Done. If Docker was down: open Docker Desktop, then ./scripts/start.sh"
echo "If Gateway is down: login in IB Gateway (Read-Only API, port ${gateway_port})."
