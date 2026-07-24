"""Flex credentials persistence + service hot-reload."""

from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.core.config import Settings, get_settings
from app.db.base import db_session, dispose_engine
from app.db.models import Setting
from app.services.flex_credentials import (
    FLEX_SETTINGS_KEY,
    _decrypt_token,
    _encrypt_token,
    load_flex_credentials,
    mask_token,
    save_flex_credentials,
)
from app.services.flex_sync import FlexSyncService


def test_mask_token():
    assert mask_token("") == ""
    assert mask_token("abcd") == "****"
    assert mask_token("abcdefghij") == "…ghij"


def test_set_credentials_hot_reload():
    svc = FlexSyncService(Settings(ibkr_flex_token="", ibkr_flex_query_id="", _env_file=None))
    assert not svc.is_configured
    svc.set_credentials("tok-123456", "99999")
    assert svc.is_configured
    assert svc.token == "tok-123456"
    assert svc.query_id == "99999"


def test_flex_token_ciphertext_never_contains_plaintext(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-only-local-encryption-key")
    get_settings.cache_clear()
    try:
        encrypted = _encrypt_token("tok-SUPERSECRET-123")
        assert encrypted.startswith("fernet:v1:")
        assert "SUPERSECRET" not in encrypted
        assert _decrypt_token(encrypted) == "tok-SUPERSECRET-123"
    finally:
        get_settings.cache_clear()


async def _clear_flex_credentials() -> None:
    async with db_session() as session:
        await session.execute(delete(Setting).where(Setting.key == FLEX_SETTINGS_KEY))
        await session.commit()


async def test_saved_credentials_are_ciphertext_only_and_roundtrip(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "credential-db-test-key-1234567")
    get_settings.cache_clear()
    await _clear_flex_credentials()
    try:
        await save_flex_credentials("tok-DB-SUPERSECRET", "99123")
        async with db_session() as session:
            row = (
                await session.execute(select(Setting).where(Setting.key == FLEX_SETTINGS_KEY))
            ).scalar_one()
            serialized = str(row.value)
        assert "DB-SUPERSECRET" not in serialized
        assert "token" not in row.value
        assert await load_flex_credentials() == ("tok-DB-SUPERSECRET", "99123")
    finally:
        await _clear_flex_credentials()
        await dispose_engine()
        get_settings.cache_clear()


async def test_legacy_plaintext_is_migrated_before_return(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "credential-legacy-test-key-12345")
    get_settings.cache_clear()
    await _clear_flex_credentials()
    try:
        async with db_session() as session:
            session.add(
                Setting(
                    key=FLEX_SETTINGS_KEY,
                    value={"token": "legacy-SUPERSECRET", "query_id": "77"},
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()

        assert await load_flex_credentials() == ("legacy-SUPERSECRET", "77")
        async with db_session() as session:
            row = (
                await session.execute(select(Setting).where(Setting.key == FLEX_SETTINGS_KEY))
            ).scalar_one()
        assert "token" not in row.value
        assert "SUPERSECRET" not in str(row.value)
        assert str(row.value["token_ciphertext"]).startswith("fernet:v1:")
    finally:
        await _clear_flex_credentials()
        await dispose_engine()
        get_settings.cache_clear()
