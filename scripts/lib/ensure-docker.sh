#!/usr/bin/env bash
# Shared helper: make sure the Docker CLI exists and the daemon is ready.
# On macOS, if the daemon is down, try to launch Docker Desktop and wait.
#
# Usage (from other scripts that have already `cd`'d to the repo root):
#   # shellcheck source=lib/ensure-docker.sh
#   source "$(dirname "$0")/lib/ensure-docker.sh"
#   ensure_docker

ensure_docker() {
  local wait_s="${DOCKER_WAIT_SECONDS:-120}"
  local i

  if ! command -v docker >/dev/null 2>&1; then
    cat >&2 <<'EOF'
ERROR: Docker CLI not found.

Install Docker Desktop for Mac:
  https://www.docker.com/products/docker-desktop/
Then re-run this script.
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
    else
      cat >&2 <<'EOF'
ERROR: Docker Desktop app not found under /Applications.

Install it from https://www.docker.com/products/docker-desktop/
Open it once, wait until it says "Docker is running", then re-run.
EOF
      return 1
    fi
  else
    cat >&2 <<'EOF'
ERROR: Docker daemon is not running.

Start the Docker service, then re-run this script.
EOF
    return 1
  fi

  echo "    Waiting up to ${wait_s}s for Docker to become ready…"
  for ((i = 1; i <= wait_s; i++)); do
    if docker info >/dev/null 2>&1; then
      echo "    Docker is ready (${i}s)."
      return 0
    fi
    # Print a heartbeat every 10s so the terminal doesn't look stuck.
    if ((i % 10 == 0)); then
      echo "    …still waiting (${i}/${wait_s}s) — finish any Docker Desktop first-run prompts if shown"
    fi
    sleep 1
  done

  cat >&2 <<'EOF'
ERROR: Docker Desktop did not become ready in time.

Open Docker Desktop manually, wait until the whale icon is steady / "Docker is running",
then re-run:
  ./scripts/start.sh
EOF
  return 1
}
