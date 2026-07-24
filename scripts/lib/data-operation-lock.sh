#!/usr/bin/env bash
# Kernel-backed exclusive lock shared by backup.sh and restore.sh.
#
# macOS provides lockf(1); Linux/WSL normally provides flock(1). Both attach
# the lock to an inherited file descriptor, so the kernel releases it after a
# normal exit, SIGKILL, host crash, or power loss. The lock file intentionally
# remains on disk: its existence is not the lock.

DATA_OPERATION_LOCK_ACQUIRED="${DATA_OPERATION_LOCK_ACQUIRED:-0}"
DATA_OPERATION_LOCK_FILE="${DATA_OPERATION_LOCK_FILE:-}"

data_operation_lock_is_owned() {
  [[ -n "${IBKR_DATA_LOCK_TOKEN:-}" ]] \
    && [[ -n "${IBKR_DATA_LOCK_FILE:-}" ]] \
    && [[ "${DATA_OPERATION_LOCK_FILE:-}" == "$IBKR_DATA_LOCK_FILE" ]]
}

_close_data_operation_lock_fd() {
  exec 9>&-
}

acquire_data_operation_lock() {
  local lock_parent="$1"
  local operation="$2"
  local lock_error=""

  mkdir -p "$lock_parent"
  chmod 700 "$lock_parent"
  DATA_OPERATION_LOCK_FILE="${lock_parent}/.data-operation.lock"

  # restore.sh owns the descriptor while its backup.sh child inherits it.
  # The child must not open a new descriptor or release the parent's lock.
  if [[ -n "${IBKR_DATA_LOCK_TOKEN:-}" ]]; then
    if data_operation_lock_is_owned; then
      return 0
    fi
    echo "ERROR: A nested data operation tried to use a different lock path." >&2
    return 1
  fi

  if [[ -L "$DATA_OPERATION_LOCK_FILE" ]]; then
    echo "ERROR: Refusing to use a symlink as the backup/restore lock." >&2
    return 1
  fi

  umask 077
  if ! exec 9>>"$DATA_OPERATION_LOCK_FILE"; then
    echo "ERROR: Could not open the backup/restore lock file." >&2
    return 1
  fi
  chmod 600 "$DATA_OPERATION_LOCK_FILE"

  if command -v flock >/dev/null 2>&1; then
    if ! flock -n 9; then
      lock_error="busy"
    fi
  elif command -v lockf >/dev/null 2>&1; then
    if ! lockf -s -t 0 9; then
      lock_error="busy"
    fi
  else
    lock_error="unsupported"
  fi

  if [[ -n "$lock_error" ]]; then
    _close_data_operation_lock_fd
    if [[ "$lock_error" == "unsupported" ]]; then
      echo "ERROR: backup/restore requires flock (Linux) or lockf (macOS)." >&2
    else
      echo "ERROR: A backup/restore operation is already running." >&2
    fi
    return 1
  fi

  IBKR_DATA_LOCK_TOKEN="$$-$(date +%s)-${RANDOM:-0}"
  IBKR_DATA_LOCK_FILE="$DATA_OPERATION_LOCK_FILE"
  IBKR_DATA_LOCK_OPERATION="$operation"
  export IBKR_DATA_LOCK_TOKEN IBKR_DATA_LOCK_FILE IBKR_DATA_LOCK_OPERATION
  DATA_OPERATION_LOCK_ACQUIRED=1
}

release_data_operation_lock() {
  if [[ "$DATA_OPERATION_LOCK_ACQUIRED" != "1" ]] \
    || ! data_operation_lock_is_owned; then
    return 0
  fi

  _close_data_operation_lock_fd
  DATA_OPERATION_LOCK_ACQUIRED=0
  unset IBKR_DATA_LOCK_TOKEN IBKR_DATA_LOCK_FILE IBKR_DATA_LOCK_OPERATION
}
