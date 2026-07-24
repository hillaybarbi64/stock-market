"""Persist Flex Web Service credentials in the settings table.

Env vars (IBKR_FLEX_TOKEN / IBKR_FLEX_QUERY_ID) remain the bootstrap default.
Credentials saved from the UI are encrypted before they enter Postgres so
they survive container restarts without appearing in clear text.
"""

from datetime import UTC, datetime

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import Setting
from app.services.local_crypto import credential_cipher

log = get_logger(__name__)

FLEX_SETTINGS_KEY = "flex_credentials"
_CIPHERTEXT_PREFIX = "fernet:v1:"


async def load_flex_credentials() -> tuple[str, str]:
    """Return (token, query_id) from DB, or ("", "") if unset."""
    async with db_session() as session:
        row = (
            await session.execute(select(Setting).where(Setting.key == FLEX_SETTINGS_KEY))
        ).scalar_one_or_none()
        if row is None or not isinstance(row.value, dict):
            return "", ""

        query_id = str(row.value.get("query_id") or "").strip()
        ciphertext = str(row.value.get("token_ciphertext") or "").strip()
        if ciphertext:
            try:
                return _decrypt_token(ciphertext), query_id
            except (InvalidToken, ValueError):
                log.error("flex_credentials_decrypt_failed")
                return "", ""

        # One-time migration for installations created before encryption.
        legacy_token = str(row.value.get("token") or "").strip()
        if legacy_token:
            row.value = {
                "token_ciphertext": _encrypt_token(legacy_token),
                "query_id": query_id,
            }
            row.updated_at = datetime.now(UTC)
            await session.commit()
            log.info("flex_credentials_encrypted_at_rest")
        return legacy_token, query_id


async def save_flex_credentials(token: str, query_id: str) -> None:
    token = token.strip()
    query_id = query_id.strip()
    payload = {
        "token_ciphertext": _encrypt_token(token),
        "query_id": query_id,
    }
    async with db_session() as session:
        stmt = pg_insert(Setting).values(
            key=FLEX_SETTINGS_KEY,
            value=payload,
            updated_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Setting.key],
            set_={"value": stmt.excluded.value, "updated_at": stmt.excluded.updated_at},
        )
        await session.execute(stmt)
        await session.commit()
    log.info("flex_credentials_saved", token_set=bool(token))


def _encrypt_token(token: str) -> str:
    ciphertext = credential_cipher(get_settings()).encrypt(token.encode("utf-8")).decode("ascii")
    return f"{_CIPHERTEXT_PREFIX}{ciphertext}"


def _decrypt_token(value: str) -> str:
    if not value.startswith(_CIPHERTEXT_PREFIX):
        raise ValueError("unsupported credential ciphertext format")
    payload = value.removeprefix(_CIPHERTEXT_PREFIX).encode("ascii")
    return credential_cipher(get_settings()).decrypt(payload).decode("utf-8")


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "****"
    return f"…{token[-4:]}"
