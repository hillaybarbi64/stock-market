#!/usr/bin/env bash
# Install or update the distributable GHCR build without compiling locally.
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly RELEASE_COMPOSE="${PROJECT_DIR}/docker-compose.release.yml"
readonly RELEASE_ENV_TEMPLATE="${PROJECT_DIR}/config/release.env.example"

cd "${PROJECT_DIR}"

# shellcheck source=lib/ensure-docker.sh
source "${SCRIPT_DIR}/lib/ensure-docker.sh"

random_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
    return
  fi
  LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48 || true
}

env_value() {
  local key="$1"
  awk -F= -v wanted="${key}" '$1 == wanted { print substr($0, index($0, "=") + 1); exit }' .env
}

set_env_value() {
  local key="$1"
  local value="$2"
  local env_temp=""

  umask 077
  env_temp="$(mktemp "${PROJECT_DIR}/.env.update.XXXXXX")"
  if ! awk -F= -v wanted="${key}" -v replacement="${value}" '
    BEGIN { updated = 0 }
    $1 == wanted {
      if (!updated) {
        print wanted "=" replacement
        updated = 1
      }
      next
    }
    { print }
    END {
      if (!updated) {
        print wanted "=" replacement
      }
    }
  ' .env >"${env_temp}"; then
    rm -f "${env_temp}"
    return 1
  fi
  chmod 600 "${env_temp}"
  if ! mv "${env_temp}" .env; then
    rm -f "${env_temp}"
    return 1
  fi
}

create_local_env() {
  if [[ -f .env ]]; then
    local existing_password existing_app_key
    existing_password="$(env_value POSTGRES_PASSWORD)"
    existing_app_key="$(env_value APP_SECRET_KEY)"
    if [[ -z "${existing_password}" || "${existing_password}" == "CHANGE_ME" || ${#existing_password} -lt 16 ]]; then
      echo "ERROR: Existing .env needs a non-placeholder POSTGRES_PASSWORD of 16+ characters." >&2
      return 1
    fi
    if [[ "${existing_app_key}" == "CHANGE_ME_APP" ]] \
      || [[ -n "${existing_app_key}" && ${#existing_app_key} -lt 24 ]]; then
      echo "ERROR: Existing APP_SECRET_KEY must be empty (legacy) or 24+ non-placeholder characters." >&2
      return 1
    fi
    set_env_value DASHBOARD_INSTALL_MODE release
    echo "==> Preserved the existing local .env and enabled release mode"
    return
  fi

  local gateway_port="4001"
  local gateway_choice=""
  local generated_password=""
  local generated_app_key=""
  local env_temp=""

  if [[ -t 0 ]]; then
    echo ""
    echo "Which read-only IBKR account mode will this computer use?"
    echo "  1) Live account  (Gateway port 4001)"
    echo "  2) Paper account (Gateway port 4002)"
    read -r -p "Choose 1 or 2 [1]: " gateway_choice
    case "${gateway_choice:-1}" in
      1) gateway_port="4001" ;;
      2) gateway_port="4002" ;;
      *)
        echo "ERROR: Expected 1 or 2." >&2
        return 1
        ;;
    esac
  fi

  generated_password="$(random_password)"
  generated_app_key="$(random_password)"
  if [[ ${#generated_password} -lt 24 ]]; then
    echo "ERROR: Could not generate a strong database password." >&2
    return 1
  fi
  if [[ ${#generated_app_key} -lt 24 ]]; then
    echo "ERROR: Could not generate a local encryption key." >&2
    return 1
  fi

  umask 077
  env_temp="$(mktemp "${TMPDIR:-/tmp}/ibkr-dashboard-env.XXXXXX")"
  trap 'rm -f "${env_temp:-}"' EXIT
  sed \
    -e "s/^POSTGRES_PASSWORD=CHANGE_ME$/POSTGRES_PASSWORD=${generated_password}/" \
    -e "s/^APP_SECRET_KEY=CHANGE_ME_APP$/APP_SECRET_KEY=${generated_app_key}/" \
    -e "s/^IBKR_GATEWAY_PORT=4001$/IBKR_GATEWAY_PORT=${gateway_port}/" \
    "${RELEASE_ENV_TEMPLATE}" >"${env_temp}"
  mv "${env_temp}" .env
  chmod 600 .env
  trap - EXIT

  echo "==> Created private local configuration (.env, mode 600)"
  echo "    Flex autosync remains disabled; no IBKR password is stored here."
}

pin_release_image_tag() {
  local image_tag=""
  image_tag="$(env_value DASHBOARD_IMAGE_TAG)"
  image_tag="${image_tag:-0.1.0}"
  if [[ ! "${image_tag}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$ ]]; then
    cat >&2 <<EOF
ERROR: DASHBOARD_IMAGE_TAG must be a full immutable version such as 0.1.0
or 0.2.0-rc.1. Mutable aliases and build candidates are refused.
Current value: ${image_tag}
EOF
    return 1
  fi
  set_env_value DASHBOARD_IMAGE_TAG "${image_tag}"
}

backup_existing_install() {
  local volume_id=""
  local attempt
  local db_user=""
  local db_name=""
  volume_id="$(
    docker volume ls \
      --filter label=com.docker.compose.project=ibkr-dashboard \
      --filter label=com.docker.compose.volume=pgdata \
      --quiet \
      | head -n 1
  )"
  if [[ -z "${volume_id}" ]]; then
    return 0
  fi

  echo "==> Existing database detected; creating a pre-upgrade backup"
  docker compose -f "${RELEASE_COMPOSE}" up -d db
  db_user="$(env_value POSTGRES_USER)"
  db_name="$(env_value POSTGRES_DB)"
  db_user="${db_user:-ibkr}"
  db_name="${db_name:-ibkr_dashboard}"
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if docker compose -f "${RELEASE_COMPOSE}" exec -T db \
      pg_isready -U "${db_user}" -d "${db_name}" \
      >/dev/null 2>&1; then
      COMPOSE_FILE="${RELEASE_COMPOSE}" "${SCRIPT_DIR}/backup.sh"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: Existing database did not become ready; update aborted before migrations." >&2
  return 1
}

wait_for_dashboard() {
  local attempt
  for ((attempt = 1; attempt <= 120; attempt++)); do
    if curl -fsS --connect-timeout 1 \
      http://127.0.0.1:3000 >/dev/null 2>&1; then
      echo "==> Dashboard is ready"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: Dashboard did not become ready." >&2
  echo "Inspect local logs with:" >&2
  echo "  docker compose -f docker-compose.release.yml logs --tail=100" >&2
  return 1
}

echo "==> Checking Docker"
ensure_docker
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose v2 is required." >&2
  exit 1
fi

create_local_env
pin_release_image_tag

echo "==> Validating release configuration"
docker compose -f "${RELEASE_COMPOSE}" config --quiet

backup_existing_install

echo "==> Pulling release images from GitHub Container Registry"
if ! docker compose -f "${RELEASE_COMPOSE}" pull; then
  cat >&2 <<'EOF'
ERROR: Could not pull the release images.

If the GHCR packages are private, authenticate first:
  docker login ghcr.io

For a public handoff, the repository owner must mark both GHCR packages public.
EOF
  exit 1
fi

echo "==> Starting the local read-only stack"
if docker compose up --help 2>/dev/null | grep -q -- '--wait'; then
  docker compose -f "${RELEASE_COMPOSE}" up -d --wait
else
  docker compose -f "${RELEASE_COMPOSE}" up -d
fi

wait_for_dashboard

cat <<'EOF'

Installation complete: http://localhost:3000

Next:
  1. Open the official IB Gateway and sign in there (the dashboard never sees
     or stores the IBKR username, password, or 2FA code).
  2. In Gateway API settings, enable Read-Only API and use the selected socket
     port.
  3. Open http://localhost:3000/connect and follow the account wizard.
  4. Add the Flex token and Query ID there only when historical data is needed.
     The token is encrypted locally and automatic Flex sync stays off.

Re-run ./scripts/install-release.sh later to pull and install an update.
EOF

case "$(uname -s)" in
  Darwin) open http://localhost:3000 >/dev/null 2>&1 || true ;;
  Linux)
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open http://localhost:3000 >/dev/null 2>&1 || true
    fi
    ;;
esac
