"""Local encryption-key validation and rotation detection."""

import pytest

from app.core.config import Settings
from app.services.local_crypto import (
    account_fingerprint,
    local_key_check,
    local_key_material,
)


def test_dedicated_app_key_is_stable_and_keyed():
    first = Settings(app_secret_key="first-local-secret-key-123456", _env_file=None)
    second = Settings(app_secret_key="second-local-secret-key-12345", _env_file=None)

    assert account_fingerprint("U1234567", first) == account_fingerprint("U1234567", first)
    assert account_fingerprint("U1234567", first) != account_fingerprint("U1234567", second)
    assert local_key_check(first) != local_key_check(second)


def test_placeholder_or_short_app_key_is_rejected():
    with pytest.raises(RuntimeError):
        local_key_material(Settings(app_secret_key="CHANGE_ME_APP", _env_file=None))
    with pytest.raises(RuntimeError):
        local_key_material(Settings(app_secret_key="too-short", _env_file=None))


def test_strong_legacy_database_password_remains_supported():
    settings = Settings(
        app_secret_key="",
        database_url="postgresql+asyncpg://ibkr:legacy-password-123456@localhost/db",
        _env_file=None,
    )

    assert local_key_material(settings) == "legacy-password-123456"
