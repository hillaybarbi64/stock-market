#!/usr/bin/env bash
# Shared helper: make sure the Docker CLI exists and the daemon is ready.
# On macOS, if the daemon is down, launch Docker Desktop and wait.
#
# Usage (from other scripts that have already `cd`'d to the repo root):
#   # shellcheck source=lib/ensure-docker.sh
#   source "$(dirname "$0")/lib/ensure-docker.sh"
#   ensure_docker

ensure_docker() {
  local wait_s="${DOCKER_WAIT_SECONDS:-180}"
  local i

  if ! command -v docker >/dev/null 2>&1; then
    cat >&2 <<'EOF'
ERROR: Docker CLI not found.

Install Docker Desktop for Mac:
  https://www.docker.com/products/docker-desktop/
Then re-run ./scripts/start.sh
EOF
    return 1
  fi

  if docker info >/dev/null 2>&1; then
    return 0
  fi

  echo "==> Docker daemon is not running"

  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ -d "/Applications/Docker.app" ]] || [[ -d "$HOME/Applications/Docker.app" ]]; then
      echo "    Launching Docker Desktop…"
      open -a Docker 2>/dev/null || true
      # Also nudge via open URL scheme used by newer Desktop builds.
      open "docker://" 2>/dev/null || true
    else
      cat >&2 <<'EOF'
ERROR: Docker Desktop app not found under /Applications.

Install it from https://www.docker.com/products/docker-desktop/
Open it once until it says "Docker is running", then re-run ./scripts/start.sh
EOF
      return 1
    fi
  else
    cat >&2 <<'EOF'
ERROR: Docker daemon is not running. Start the Docker service, then re-run ./scripts/start.sh
EOF
    return 1
  fi

  echo "    Waiting up to ${wait_s}s for Docker to become ready…"
  for ((i = 1; i <= wait_s; i++)); do
    if docker info >/dev/null 2>&1; then
      echo "    Docker is ready (${i}s)."
      return 0
    fi
    if ((i % 10 == 0)); then
      echo "    …still waiting (${i}/${wait_s}s) — approve any Docker Desktop prompt if one appeared"
    fi
    sleep 1
  done

  cat >&2 <<'EOF'
ERROR: Docker Desktop did not become ready in time.

Open Docker Desktop, wait until it says "Docker is running", then re-run:
  ./scripts/start.sh
EOF
  return 1
}

ensure_env_file() {
  if [[ -f .env ]]; then
    return 0
  fi
  echo "==> Creating .env from .env.example (random DB password)"
  local pass
  pass="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)"
  sed "s/CHANGE_ME/${pass}/g" .env.example > .env
  echo "    Created .env — fill IBKR_FLEX_TOKEN + IBKR_FLEX_QUERY_ID when you want history sync"
}

wait_http() {
  local url="$1"
  local label="$2"
  local wait_s="${3:-90}"
  local i
  for ((i = 1; i <= wait_s; i++)); do
    if curl -fsS --connect-timeout 1 "$url" >/dev/null 2>&1; then
      echo "    ${label} ready (${i}s)"
      return 0
    fi
    sleep 1
  done
  echo "    WARNING: ${label} not ready after ${wait_s}s — check: docker compose logs" >&2
  return 1
}
