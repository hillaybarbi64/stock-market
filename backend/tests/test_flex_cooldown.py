"""Durable IBKR Flex 1025 cooldown behavior."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.config import Settings
from app.db.models import SyncRun
from app.ibkr.flex import FlexError
from app.services import flex_sync
from app.services.flex_cooldown import (
    FLEX_LOCKOUT_COOLDOWN,
    FLEX_MIN_ATTEMPT_INTERVAL,
    FLEX_RUNNING_GRACE,
    FlexAttemptBlock,
    FlexAttemptBlocked,
    active_attempt_block_from_runs,
    active_cooldown_from_runs,
    attempt_block_for_run,
    cooldown_for_run,
    lockout_error_details,
    public_error_details,
)
from app.services.flex_sync import (
    FlexAccountMismatchError,
    FlexSyncService,
    validate_flex_account,
)


def _failed_run(*, finished_at: datetime, errors: dict) -> SyncRun:
    return SyncRun(
        kind="flex_full",
        started_at=finished_at - timedelta(seconds=5),
        finished_at=finished_at,
        status="failed",
        errors=errors,
    )


def test_flex_autosync_is_opt_in(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_AUTOSYNC", raising=False)

    assert Settings(_env_file=None).ibkr_flex_autosync is False


def test_flex_account_must_match_live_gateway():
    validate_flex_account("U1234567", "U1234567")

    with pytest.raises(FlexAccountMismatchError):
        validate_flex_account("U1234567", "U7654321")
    with pytest.raises(FlexAccountMismatchError):
        validate_flex_account(None, "U1234567")


def test_1025_legacy_error_activates_two_hour_cooldown():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    run = _failed_run(
        finished_at=failed_at,
        errors={"error": "FlexError: Flex error 1025: too many failed attempts"},
    )

    cooldown = cooldown_for_run(run, now=failed_at + timedelta(minutes=30))

    assert cooldown is not None
    assert cooldown.until == failed_at + FLEX_LOCKOUT_COOLDOWN
    assert cooldown.remaining_seconds == 90 * 60


def test_expired_or_unrelated_failure_has_no_cooldown():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    expired = _failed_run(
        finished_at=failed_at,
        errors={"error_code": "1025", "error": "too many failed attempts"},
    )
    unrelated = _failed_run(
        finished_at=failed_at,
        errors={"error_code": "1012", "error": "token expired"},
    )

    assert cooldown_for_run(expired, now=failed_at + timedelta(hours=2)) is None
    assert cooldown_for_run(unrelated, now=failed_at + timedelta(minutes=1)) is None


def test_new_1025_failure_stores_structured_cooldown_metadata():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)

    details = lockout_error_details(
        FlexError("1025", "too many failed attempts"),
        trigger="manual",
        failed_at=failed_at,
    )

    assert details["error_code"] == "1025"
    assert details["trigger"] == "manual"
    assert details["cooldown_until"] == (failed_at + FLEX_LOCKOUT_COOLDOWN).isoformat()
    assert details["error"] == "Flex error 1025"


def test_newer_noise_does_not_hide_active_1025():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    lockout = _failed_run(
        finished_at=failed_at,
        errors={"error_code": "1025", "error": "Flex error 1025"},
    )
    unrelated = _failed_run(
        finished_at=failed_at + timedelta(minutes=1),
        errors={"error_code": "1012", "error": "Flex error 1012"},
    )
    running = SyncRun(
        kind="flex_full",
        started_at=failed_at + timedelta(minutes=2),
        status="running",
    )

    cooldown = active_cooldown_from_runs(
        [running, unrelated, lockout],
        now=failed_at + timedelta(minutes=30),
    )

    assert cooldown is not None
    assert cooldown.remaining_seconds == 90 * 60


def test_newer_success_proves_recovery_from_old_1025():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    success = SyncRun(
        kind="flex_full",
        started_at=failed_at + timedelta(minutes=10),
        finished_at=failed_at + timedelta(minutes=11),
        status="ok",
    )
    lockout = _failed_run(
        finished_at=failed_at,
        errors={"error_code": "1025", "error": "Flex error 1025"},
    )

    assert (
        active_cooldown_from_runs(
            [success, lockout],
            now=failed_at + timedelta(minutes=30),
        )
        is None
    )


def test_later_finished_1025_is_not_hidden_by_later_started_success():
    base = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    lockout = SyncRun(
        kind="flex_full",
        started_at=base,
        finished_at=base + timedelta(minutes=10),
        status="failed",
        errors={"error_code": "1025", "error": "Flex error 1025"},
    )
    success = SyncRun(
        kind="flex_full",
        started_at=base + timedelta(minutes=5),
        finished_at=base + timedelta(minutes=6),
        status="ok",
    )

    cooldown = active_cooldown_from_runs(
        [success, lockout],
        now=base + timedelta(minutes=20),
    )

    assert cooldown is not None
    assert cooldown.remaining_seconds == 110 * 60


def test_recent_terminal_attempt_and_running_row_are_blocked():
    base = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    failed = _failed_run(finished_at=base, errors={"error_code": "1019"})
    running = SyncRun(
        kind="flex_full",
        started_at=base,
        status="running",
    )

    recent_block = attempt_block_for_run(
        failed,
        now=base + timedelta(seconds=30),
    )
    running_block = attempt_block_for_run(
        running,
        now=base + timedelta(minutes=2),
    )

    assert recent_block == FlexAttemptBlock(
        reason="recent",
        remaining_seconds=int(FLEX_MIN_ATTEMPT_INTERVAL.total_seconds()) - 30,
    )
    assert running_block == FlexAttemptBlock(
        reason="running",
        remaining_seconds=int(FLEX_RUNNING_GRACE.total_seconds()) - 120,
    )


def test_later_terminal_row_does_not_hide_running_grace():
    base = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    running = SyncRun(kind="flex_full", started_at=base, status="running")
    later_failure = _failed_run(
        finished_at=base + timedelta(minutes=2),
        errors={"error_code": "1012"},
    )

    block = active_attempt_block_from_runs(
        [later_failure, running],
        now=base + timedelta(minutes=3, seconds=31),
    )

    assert block == FlexAttemptBlock(
        reason="running",
        remaining_seconds=int(FLEX_RUNNING_GRACE.total_seconds()) - 211,
    )


async def test_service_attempt_guard_runs_before_flex_http(monkeypatch):
    service = FlexSyncService(
        Settings(
            ibkr_flex_token="test-token",
            ibkr_flex_query_id="42",
            ibkr_gateway_autostart=False,
            _env_file=None,
        )
    )
    block = FlexAttemptBlock(reason="recent", remaining_seconds=60)
    inner_called = False

    @asynccontextmanager
    async def fake_db_session():
        yield object()

    async def lock_acquired(_session) -> bool:
        return True

    async def no_cooldown(_session):
        return None

    async def binding_exists():
        return True

    async def blocked(_session):
        return block

    async def release(_session, _acquired) -> None:
        return None

    async def inner(_trigger: str, *, token: str, query_id: str) -> int:
        nonlocal inner_called
        assert token == "test-token"
        assert query_id == "42"
        inner_called = True
        return 1

    monkeypatch.setattr(flex_sync, "db_session", fake_db_session)
    monkeypatch.setattr(flex_sync, "_try_acquire_flex_lock", lock_acquired)
    monkeypatch.setattr(flex_sync, "get_active_flex_cooldown", no_cooldown)
    monkeypatch.setattr(flex_sync, "account_binding_exists", binding_exists)
    monkeypatch.setattr(flex_sync, "get_flex_attempt_block", blocked)
    monkeypatch.setattr(flex_sync, "_release_flex_lock", release)
    monkeypatch.setattr(service, "_run_inner", inner)

    with pytest.raises(FlexAttemptBlocked):
        await service.run()

    assert inner_called is False
    assert service.is_running is False


def test_legacy_matching_does_not_treat_unrelated_1025_as_lockout():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    run = _failed_run(
        finished_at=failed_at,
        errors={"error": "HTTP failure while processing query 1025"},
    )

    assert cooldown_for_run(run, now=failed_at + timedelta(minutes=1)) is None


def test_http_error_metadata_never_persists_request_url_or_token():
    failed_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    request = httpx.Request(
        "GET",
        "https://example.test/FlexStatementService.SendRequest?t=SUPERSECRET&q=42",
    )
    response = httpx.Response(503, request=request)
    exc = httpx.HTTPStatusError("server error", request=request, response=response)

    details = lockout_error_details(exc, trigger="manual", failed_at=failed_at)

    assert "SUPERSECRET" not in str(details)
    assert "example.test" not in str(details)
    assert details["http_status"] == 503
    assert details["endpoint"] == "FlexStatementService.SendRequest"


def test_legacy_error_url_is_never_returned_to_browser():
    public = public_error_details(
        {
            "error": (
                "HTTPStatusError: GET "
                "https://example.test/FlexStatementService.SendRequest?t=SUPERSECRET&q=123"
            ),
            "trigger": "manual",
        }
    )

    assert public == {"trigger": "manual", "error": "Flex sync failed"}
    assert "SUPERSECRET" not in str(public)
    assert "example.test" not in str(public)
