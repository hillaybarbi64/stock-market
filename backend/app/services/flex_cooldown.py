"""Durable protection against IBKR Flex account lockouts.

IBKR error 1025 is account-scoped. Restarting the backend must not erase the
cooldown and immediately call Flex again, so the latest SyncRun is the source
of truth instead of process memory.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SyncRun

FLEX_LOCKOUT_CODE = "1025"
FLEX_LOCKOUT_COOLDOWN = timedelta(hours=2)
FLEX_MIN_ATTEMPT_INTERVAL = timedelta(seconds=90)
FLEX_RUNNING_GRACE = timedelta(minutes=10)
FLEX_INTERRUPTED_HOLD = timedelta(minutes=10)
_LEGACY_1025_RE = re.compile(r"\bFlex error 1025:", flags=re.IGNORECASE)
_PUBLIC_ERROR_MESSAGES = {
    "Connect one IB Gateway account before importing Flex history",
    "Flex account does not match connected Gateway",
    "This installation is bound to a different IBKR account",
    "The local key does not match the saved account binding",
    "Flex HTTP request failed",
    "Flex network request failed",
    "Flex sync failed",
    "Flex sync interrupted during shutdown",
}
_PUBLIC_ENDPOINTS = {
    "FlexStatementService.SendRequest",
    "FlexStatementService.GetStatement",
}
_PUBLIC_TRIGGERS = {"manual", "scheduled", "flex_config_save"}


@dataclass(frozen=True)
class FlexCooldown:
    error_code: str
    until: datetime
    remaining_seconds: int


class FlexCooldownActive(RuntimeError):
    def __init__(self, cooldown: FlexCooldown) -> None:
        super().__init__(f"Flex cooldown active for {cooldown.remaining_seconds} seconds")
        self.cooldown = cooldown


@dataclass(frozen=True)
class FlexAttemptBlock:
    reason: str
    remaining_seconds: int


class FlexAttemptBlocked(RuntimeError):
    def __init__(self, block: FlexAttemptBlock) -> None:
        super().__init__(
            f"Flex attempt blocked ({block.reason}) for {block.remaining_seconds} seconds"
        )
        self.block = block


def cooldown_for_run(
    run: SyncRun | None,
    *,
    now: datetime | None = None,
) -> FlexCooldown | None:
    """Return an active cooldown when the latest Flex run hit error 1025.

    Legacy rows stored only a human-readable error string, while new rows also
    store ``error_code`` and ``cooldown_until``. Supporting both means the
    protection takes effect immediately without a data migration.
    """
    if run is None or run.kind != "flex_full" or run.status != "failed":
        return None

    errors = run.errors or {}
    if not _is_1025_failure(run):
        return None

    until = _parse_datetime(errors.get("cooldown_until"))
    if until is None:
        reference = run.finished_at or run.started_at
        if reference is None:
            return None
        until = _as_utc(reference) + FLEX_LOCKOUT_COOLDOWN

    current = _as_utc(now or datetime.now(UTC))
    remaining = (until - current).total_seconds()
    if remaining <= 0:
        return None
    return FlexCooldown(
        error_code=FLEX_LOCKOUT_CODE,
        until=until,
        remaining_seconds=ceil(remaining),
    )


def active_cooldown_from_runs(
    runs: list[SyncRun],
    *,
    now: datetime | None = None,
) -> FlexCooldown | None:
    """Evaluate terminal Flex runs ordered by newest finish time.

    A newer successful run proves recovery and ends the search. Newer unrelated
    failures are skipped, while the most recent 1025 decides the cooldown.
    """
    ordered_runs = sorted(
        runs,
        key=lambda run: _as_utc(
            run.finished_at or run.started_at or datetime.min.replace(tzinfo=UTC)
        ),
        reverse=True,
    )
    for run in ordered_runs:
        if run.kind != "flex_full":
            continue
        if run.status == "ok":
            return None
        if _is_1025_failure(run):
            return cooldown_for_run(run, now=now)
    return None


async def get_active_flex_cooldown(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> FlexCooldown | None:
    runs = (
        (
            await session.execute(
                select(SyncRun)
                .where(
                    SyncRun.kind == "flex_full",
                    SyncRun.status.in_(("failed", "ok")),
                )
                .order_by(desc(SyncRun.finished_at).nullslast(), desc(SyncRun.started_at))
            )
        )
        .scalars()
        .all()
    )
    return active_cooldown_from_runs(list(runs), now=now)


def attempt_block_for_run(
    run: SyncRun | None,
    *,
    now: datetime | None = None,
) -> FlexAttemptBlock | None:
    """Block recent/unknown in-flight Flex activity before any HTTP request."""
    if run is None or run.kind != "flex_full" or run.started_at is None:
        return None

    current = _as_utc(now or datetime.now(UTC))
    if run.status == "running":
        remaining = (_as_utc(run.started_at) + FLEX_RUNNING_GRACE - current).total_seconds()
        if remaining > 0:
            return FlexAttemptBlock(reason="running", remaining_seconds=ceil(remaining))
        return None

    reference = run.finished_at or run.started_at
    if str((run.errors or {}).get("error_code", "")) == "interrupted":
        remaining = (_as_utc(reference) + FLEX_INTERRUPTED_HOLD - current).total_seconds()
        if remaining > 0:
            return FlexAttemptBlock(reason="interrupted", remaining_seconds=ceil(remaining))
        return None
    remaining = (_as_utc(reference) + FLEX_MIN_ATTEMPT_INTERVAL - current).total_seconds()
    if remaining > 0:
        return FlexAttemptBlock(reason="recent", remaining_seconds=ceil(remaining))
    return None


async def get_flex_attempt_block(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> FlexAttemptBlock | None:
    runs = (
        (
            await session.execute(
                select(SyncRun)
                .where(SyncRun.kind == "flex_full")
                .order_by(
                    desc(func.coalesce(SyncRun.finished_at, SyncRun.started_at)),
                    desc(SyncRun.started_at),
                )
            )
        )
        .scalars()
        .all()
    )
    return active_attempt_block_from_runs(list(runs), now=now)


def active_attempt_block_from_runs(
    runs: list[SyncRun],
    *,
    now: datetime | None = None,
) -> FlexAttemptBlock | None:
    """Return the strongest active hold across terminal and in-flight rows."""
    blocks = [block for run in runs if (block := attempt_block_for_run(run, now=now)) is not None]
    return max(blocks, key=lambda block: block.remaining_seconds, default=None)


def lockout_error_details(exc: Exception, *, trigger: str, failed_at: datetime) -> dict:
    """Build secret-free SyncRun error metadata, including durable cooldown."""
    from app.ibkr.flex import FlexError

    details: dict = {
        "error_type": type(exc).__name__,
        "trigger": trigger,
    }
    if isinstance(exc, FlexError):
        details["error"] = f"Flex error {exc.code}"
        details["error_code"] = exc.code
        if exc.code == FLEX_LOCKOUT_CODE:
            details["cooldown_until"] = (_as_utc(failed_at) + FLEX_LOCKOUT_COOLDOWN).isoformat()
    elif isinstance(exc, httpx.HTTPStatusError):
        details["error"] = "Flex HTTP request failed"
        details["http_status"] = exc.response.status_code
        details["endpoint"] = exc.request.url.path.rsplit("/", maxsplit=1)[-1]
    elif isinstance(exc, httpx.HTTPError):
        details["error"] = "Flex network request failed"
    elif type(exc).__name__ == "FlexAccountMismatchError":
        details["error"] = "Flex account does not match connected Gateway"
    elif type(exc).__name__ == "AccountBindingRequiredError":
        details["error"] = "Connect one IB Gateway account before importing Flex history"
    elif type(exc).__name__ == "AccountBindingMismatchError":
        details["error"] = "This installation is bound to a different IBKR account"
    elif type(exc).__name__ == "AccountBindingKeyMismatchError":
        details["error"] = "The local key does not match the saved account binding"
    else:
        details["error"] = "Flex sync failed"
    return details


def public_error_details(errors: dict | None) -> dict | None:
    """Return only safe, bounded SyncRun metadata for API/UI responses.

    Older rows may contain an HTTP exception string with the complete Flex URL.
    The cooldown detector still reads those rows internally, but no raw legacy
    value is ever returned to a browser.
    """
    if not isinstance(errors, dict):
        return None

    public: dict = {}
    trigger = errors.get("trigger")
    if trigger in _PUBLIC_TRIGGERS:
        public["trigger"] = trigger

    parse_skipped = errors.get("parse_skipped")
    if isinstance(parse_skipped, dict):
        public["parse_skipped"] = {
            str(key): value
            for key, value in parse_skipped.items()
            if isinstance(value, int) and value >= 0
        }

    code = str(errors.get("error_code", ""))
    raw_error = str(errors.get("error", ""))
    if code.isdigit():
        public["error_code"] = code
        public["error"] = f"Flex error {code}"
    elif _LEGACY_1025_RE.search(raw_error):
        public["error_code"] = FLEX_LOCKOUT_CODE
        public["error"] = f"Flex error {FLEX_LOCKOUT_CODE}"
    elif raw_error in _PUBLIC_ERROR_MESSAGES:
        public["error"] = raw_error
    elif raw_error:
        public["error"] = "Flex sync failed"

    http_status = errors.get("http_status")
    if isinstance(http_status, int) and 100 <= http_status <= 599:
        public["http_status"] = http_status

    endpoint = errors.get("endpoint")
    if endpoint in _PUBLIC_ENDPOINTS:
        public["endpoint"] = endpoint

    cooldown_until = _parse_datetime(errors.get("cooldown_until"))
    if cooldown_until is not None:
        public["cooldown_until"] = cooldown_until.isoformat()

    return public or None


def _is_1025_failure(run: SyncRun) -> bool:
    if run.status != "failed":
        return False
    errors = run.errors or {}
    if str(errors.get("error_code", "")) == FLEX_LOCKOUT_CODE:
        return True
    return bool(_LEGACY_1025_RE.search(str(errors.get("error", ""))))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
