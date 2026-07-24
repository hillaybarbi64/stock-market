#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCK_HELPER="${REPO_ROOT}/scripts/lib/data-operation-lock.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ibkr-data-lock-test.XXXXXX")"
OWNER_PID=""

cleanup_test() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  if [[ -n "$OWNER_PID" ]] && kill -0 "$OWNER_PID" 2>/dev/null; then
    kill -KILL "$OWNER_PID" 2>/dev/null
    wait "$OWNER_PID" 2>/dev/null
  fi
  rm -rf -- "$TEST_ROOT"
  exit "$status"
}
trap cleanup_test EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_until_ready() {
  local ready_file="$1"
  local attempt
  for attempt in {1..100}; do
    if [[ -f "$ready_file" ]]; then
      return 0
    fi
    if [[ -n "$OWNER_PID" ]] && ! kill -0 "$OWNER_PID" 2>/dev/null; then
      echo "ERROR: Lock owner exited before becoming ready." >&2
      return 1
    fi
    sleep 0.05
  done
  echo "ERROR: Timed out waiting for the lock owner." >&2
  return 1
}

if ! command -v flock >/dev/null 2>&1 \
  && ! command -v lockf >/dev/null 2>&1; then
  echo "ERROR: This test requires flock (Linux) or lockf (macOS)." >&2
  exit 1
fi

ACTIVE_ROOT="${TEST_ROOT}/active"
ACTIVE_READY="${TEST_ROOT}/active.ready"
HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$ACTIVE_ROOT" READY_FILE="$ACTIVE_READY" \
  /bin/bash -c '
    set -euo pipefail
    source "$HELPER_PATH"
    trap release_data_operation_lock EXIT
    trap "exit 130" INT
    trap "exit 143" TERM
    acquire_data_operation_lock "$LOCK_PARENT" active-owner
    : >"$READY_FILE"
    while :; do
      sleep 1
    done
  ' &
OWNER_PID=$!
wait_until_ready "$ACTIVE_READY"

if HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$ACTIVE_ROOT" /bin/bash -c '
  set -euo pipefail
  source "$HELPER_PATH"
  acquire_data_operation_lock "$LOCK_PARENT" active-contender
' 2>"${TEST_ROOT}/active.error"; then
  echo "ERROR: A second process acquired an active lock." >&2
  exit 1
fi
grep -q "already running" "${TEST_ROOT}/active.error"

kill -TERM "$OWNER_PID"
wait "$OWNER_PID" 2>/dev/null || true
OWNER_PID=""
HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$ACTIVE_ROOT" /bin/bash -c '
  set -euo pipefail
  source "$HELPER_PATH"
  acquire_data_operation_lock "$LOCK_PARENT" post-exit
  data_operation_lock_is_owned
  release_data_operation_lock
'
echo "ok - active lock rejects a contender and releases on normal exit"

REENTRANT_ROOT="${TEST_ROOT}/reentrant"
REENTRANT_ERROR="${TEST_ROOT}/reentrant-contender.error"
HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$REENTRANT_ROOT" \
  CONTENDER_ERROR="$REENTRANT_ERROR" /bin/bash -c '
  set -euo pipefail
  source "$HELPER_PATH"
  acquire_data_operation_lock "$LOCK_PARENT" restore
  data_operation_lock_is_owned
  source "$HELPER_PATH"
  [[ "$DATA_OPERATION_LOCK_ACQUIRED" == "1" ]]
  data_operation_lock_is_owned

  /bin/bash -c '\''
    set -euo pipefail
    source "$HELPER_PATH"
    acquire_data_operation_lock "$LOCK_PARENT" safety-backup
    data_operation_lock_is_owned
    release_data_operation_lock
  '\''

  if env \
    -u IBKR_DATA_LOCK_TOKEN \
    -u IBKR_DATA_LOCK_FILE \
    -u IBKR_DATA_LOCK_OPERATION \
    HELPER_PATH="$HELPER_PATH" \
    LOCK_PARENT="$LOCK_PARENT" \
    /bin/bash -c '\''
      set -euo pipefail
      source "$HELPER_PATH"
      acquire_data_operation_lock "$LOCK_PARENT" independent-contender
    '\'' 2>"$CONTENDER_ERROR"; then
    echo "ERROR: A nested cleanup released the parent lock." >&2
    exit 1
  fi
  grep -q "already running" "$CONTENDER_ERROR"
  data_operation_lock_is_owned
  release_data_operation_lock
'
echo "ok - inherited token is reentrant and cannot release the parent lock"

SIGKILL_ROOT="${TEST_ROOT}/sigkill"
SIGKILL_READY="${TEST_ROOT}/sigkill.ready"
HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$SIGKILL_ROOT" READY_FILE="$SIGKILL_READY" \
  /bin/bash -c '
    set -euo pipefail
    source "$HELPER_PATH"
    acquire_data_operation_lock "$LOCK_PARENT" sigkill-owner
    : >"$READY_FILE"
    exec sleep 60
  ' &
OWNER_PID=$!
wait_until_ready "$SIGKILL_READY"
kill -KILL "$OWNER_PID"
wait "$OWNER_PID" 2>/dev/null || true
OWNER_PID=""

HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$SIGKILL_ROOT" /bin/bash -c '
  set -euo pipefail
  source "$HELPER_PATH"
  acquire_data_operation_lock "$LOCK_PARENT" sigkill-recovery
  data_operation_lock_is_owned
  release_data_operation_lock
'
[[ -f "${SIGKILL_ROOT}/.data-operation.lock" ]]
echo "ok - SIGKILL releases the kernel lock immediately without stale cleanup"

SYMLINK_ROOT="${TEST_ROOT}/symlink"
mkdir -p "$SYMLINK_ROOT"
: >"${TEST_ROOT}/symlink-target"
ln -s "${TEST_ROOT}/symlink-target" "${SYMLINK_ROOT}/.data-operation.lock"
if HELPER_PATH="$LOCK_HELPER" LOCK_PARENT="$SYMLINK_ROOT" /bin/bash -c '
  set -euo pipefail
  source "$HELPER_PATH"
  acquire_data_operation_lock "$LOCK_PARENT" symlink-check
' 2>"${TEST_ROOT}/symlink.error"; then
  echo "ERROR: A symlink was accepted as the lock file." >&2
  exit 1
fi
grep -q "symlink" "${TEST_ROOT}/symlink.error"
echo "ok - symlink lock files fail closed"
