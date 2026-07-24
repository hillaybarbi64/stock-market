#!/usr/bin/env bash
# Shared helper: make sure the Docker CLI exists and the daemon is ready.
# On macOS, if the daemon is down, launch Docker Desktop and wait.
#
# Usage (from other scripts that have already `cd`'d to the repo root):
#   # shellcheck source=lib/ensure-docker.sh
#   source "$(dirname "$0")/lib/ensure-docker.sh"
#   ensure_docker

ensure_docker_cli() {
  local candidate
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi
  for candidate in \
    "$HOME/Applications/Docker.app/Contents/Resources/bin/docker" \
    "/Applications/Docker.app/Contents/Resources/bin/docker"; do
    if [[ -x "$candidate" ]]; then
      export PATH="$(dirname "$candidate"):$PATH"
      export DOCKER_CLI_PLUGIN_EXTRA_DIRS="$(dirname "$(dirname "$candidate")")/cli-plugins"
      return 0
    fi
  done
  return 1
}

select_compose_configuration() {
  local install_mode=""

  if [[ -n "${COMPOSE_FILE:-}" ]]; then
    return 0
  fi
  if [[ ! -f .env ]]; then
    return 0
  fi

  install_mode="$(
    awk -F= '$1 == "DASHBOARD_INSTALL_MODE" {
      print substr($0, index($0, "=") + 1)
      exit
    }' .env
  )"
  install_mode="${install_mode%$'\r'}"

  case "${install_mode}" in
    release)
      export COMPOSE_FILE="$PWD/docker-compose.release.yml"
      ;;
    development)
      ;;
    "")
      # Compatibility with release installations created before the explicit marker.
      if grep -q '^GHCR_OWNER=' .env; then
        export COMPOSE_FILE="$PWD/docker-compose.release.yml"
      fi
      ;;
    *)
      echo "ERROR: DASHBOARD_INSTALL_MODE must be 'development' or 'release'." >&2
      return 1
      ;;
  esac
  return 0
}

ensure_docker() {
  local wait_s="${DOCKER_WAIT_SECONDS:-180}"
  local i

  if ! select_compose_configuration; then
    return 1
  fi

  if ! ensure_docker_cli; then
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
      open "$HOME/Applications/Docker.app" 2>/dev/null \
        || open "/Applications/Docker.app" 2>/dev/null \
        || open -a Docker 2>/dev/null \
        || true
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
  local pass app_key
  pass="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)"
  app_key="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48 || true)"
  sed \
    -e "s/CHANGE_ME_APP/${app_key}/g" \
    -e "s/CHANGE_ME/${pass}/g" \
    .env.example > .env
  chmod 600 .env
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

# True if something is listening on 127.0.0.1:$1 (or *:$1).
port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return $?
  fi
  return 1
}

# Release ports owned by this Compose project and refuse to kill unrelated apps.
free_app_ports() {
  local ports="3000 8000 5432"
  if [[ "${COMPOSE_FILE:-}" == *"docker-compose.release.yml"* ]]; then
    ports="3000 8000"
  fi
  echo "==> Checking ports for this stack (${ports// /, })"
  docker compose down --remove-orphans >/dev/null 2>&1 || true

  local port
  local busy=0
  for port in $ports; do
    if port_in_use "$port"; then
      echo "    ERROR: :$port is used by a process outside this Compose stack" >&2
      if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed 's/^/      /' >&2 || true
      fi
      busy=1
    else
      echo "    :$port free"
    fi
  done
  if [[ $busy -ne 0 ]]; then
    echo "Stop or reconfigure the listed process, then run the command again." >&2
  fi
  return "$busy"
}
