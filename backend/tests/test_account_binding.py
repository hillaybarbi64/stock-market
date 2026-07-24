"""Persistent single-account binding for a distributable local appliance."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.base import db_session, dispose_engine
from app.db.models import AccountSnapshot, Setting
from app.services.account_binding import (
    ACCOUNT_BINDING_KEY,
    AccountBindingConfirmationRequiredError,
    AccountBindingKeyMismatchError,
    AccountBindingMismatchError,
    account_binding_exists,
    assert_account_matches_binding,
    confirm_account_binding,
    ensure_account_binding,
)

_LEGACY_SNAPSHOT_TS = datetime(2099, 12, 31, tzinfo=UTC)


async def _clear_binding() -> None:
    async with db_session() as session:
        await session.execute(delete(Setting).where(Setting.key == ACCOUNT_BINDING_KEY))
        await session.commit()


async def _clear_legacy_flex_setting() -> None:
    async with db_session() as session:
        await session.execute(delete(Setting).where(Setting.key == "flex_credentials"))
        await session.commit()


async def _clear_legacy_snapshot() -> None:
    async with db_session() as session:
        await session.execute(
            delete(AccountSnapshot).where(AccountSnapshot.ts == _LEGACY_SNAPSHOT_TS)
        )
        await session.commit()


async def test_binding_persists_and_rejects_another_account(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "account-binding-test-key-123456")
    get_settings.cache_clear()
    await _clear_binding()
    try:
        assert not await account_binding_exists()

        # Explicit confirmation keeps this test deterministic even when another
        # integration test has left unrelated financial rows in the test DB.
        await confirm_account_binding("U1234567")

        assert await account_binding_exists()
        await assert_account_matches_binding("U1234567")
        with pytest.raises(AccountBindingMismatchError):
            await assert_account_matches_binding("U7654321")
    finally:
        await _clear_binding()
        await dispose_engine()
        get_settings.cache_clear()


async def test_rotated_key_blocks_binding_before_external_requests(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "account-binding-first-key-123456")
    get_settings.cache_clear()
    await _clear_binding()
    try:
        await confirm_account_binding("U1234567")
        monkeypatch.setenv("APP_SECRET_KEY", "account-binding-other-key-123456")
        get_settings.cache_clear()

        assert not await account_binding_exists()
        with pytest.raises(AccountBindingKeyMismatchError):
            await assert_account_matches_binding("U1234567")
    finally:
        await _clear_binding()
        await dispose_engine()
        get_settings.cache_clear()


async def test_legacy_financial_data_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "account-binding-legacy-key-123456")
    get_settings.cache_clear()
    await _clear_binding()
    await _clear_legacy_snapshot()
    try:
        async with db_session() as session:
            session.add(
                AccountSnapshot(
                    ts=_LEGACY_SNAPSHOT_TS,
                    net_liquidation=Decimal("123.4500"),
                    base_currency="USD",
                    data_quality="stale",
                )
            )
            await session.commit()

        with pytest.raises(AccountBindingConfirmationRequiredError):
            await ensure_account_binding("U1234567")

        assert not await account_binding_exists()
        await confirm_account_binding("U1234567")
        assert await account_binding_exists()
        await assert_account_matches_binding("U1234567")
    finally:
        await _clear_binding()
        await _clear_legacy_snapshot()
        await dispose_engine()
        get_settings.cache_clear()


async def test_legacy_flex_credentials_require_confirmation_before_binding(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "account-binding-flex-key-123456")
    get_settings.cache_clear()
    await _clear_binding()
    await _clear_legacy_flex_setting()
    try:
        async with db_session() as session:
            session.add(
                Setting(
                    key="flex_credentials",
                    value={
                        "token_ciphertext": "legacy-account-secret",
                        "query_id": "123",
                    },
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

        with pytest.raises(AccountBindingConfirmationRequiredError):
            await ensure_account_binding("U1234567")
        assert not await account_binding_exists()
    finally:
        await _clear_binding()
        await _clear_legacy_flex_setting()
        await dispose_engine()
        get_settings.cache_clear()
