"""Local key derivation for secrets and irreversible account binding."""

import base64
import hashlib
import hmac
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from app.core.config import Settings, get_settings

_PLACEHOLDERS = {"CHANGE_ME", "CHANGE_ME_APP", "changeme", "password"}


def local_key_material(settings: Settings | None = None) -> str:
    """Return validated local key material without ever logging it.

    New installations receive a dedicated APP_SECRET_KEY. Older installations
    may keep using their strong, private PostgreSQL password so existing
    ciphertext remains decryptable during a rolling upgrade.
    """
    resolved = settings or get_settings()
    app_key = resolved.app_secret_key.strip()
    if app_key:
        if app_key in _PLACEHOLDERS or len(app_key) < 24:
            raise RuntimeError("APP_SECRET_KEY must be a non-placeholder value of 24+ characters")
        return app_key

    database_password = urlparse(resolved.database_url).password or ""
    if database_password in _PLACEHOLDERS or len(database_password) < 16:
        raise RuntimeError(
            "APP_SECRET_KEY is required when the database password is not a strong legacy key"
        )
    return database_password


def credential_cipher(settings: Settings | None = None) -> Fernet:
    key = local_key_material(settings)
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode("utf-8")).digest())
    return Fernet(derived)


def account_fingerprint(account_id: str, settings: Settings | None = None) -> str:
    """Create a keyed, irreversible identifier for one IBKR account."""
    key = local_key_material(settings).encode("utf-8")
    return hmac.new(key, account_id.encode("utf-8"), hashlib.sha256).hexdigest()


def local_key_check(settings: Settings | None = None) -> str:
    """Detect key rotation before any external broker request is attempted."""
    key = local_key_material(settings).encode("utf-8")
    return hmac.new(key, b"ibkr-dashboard-local-key-v1", hashlib.sha256).hexdigest()
