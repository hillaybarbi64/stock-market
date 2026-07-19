"""Persist Flex Web Service credentials in the settings table.

Env vars (IBKR_FLEX_TOKEN / IBKR_FLEX_QUERY_ID) remain the bootstrap default.
Credentials saved from the UI live in Postgres so they survive container
restarts without editing .env on disk.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import Setting

log = get_logger(__name__)

FLEX_SETTINGS_KEY = "flex_credentials"


async def load_flex_credentials() -> tuple[str, str]:
    """Return (token, query_id) from DB, or ("", "") if unset."""
    async with db_session() as session:
        row = (
            await session.execute(select(Setting).where(Setting.key == FLEX_SETTINGS_KEY))
        ).scalar_one_or_none()
    if row is None or not isinstance(row.value, dict):
        return "", ""
    token = str(row.value.get("token") or "").strip()
    query_id = str(row.value.get("query_id") or "").strip()
    return token, query_id


async def save_flex_credentials(token: str, query_id: str) -> None:
    token = token.strip()
    query_id = query_id.strip()
    payload = {"token": token, "query_id": query_id}
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
    log.info("flex_credentials_saved", query_id=query_id, token_set=bool(token))


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "****"
    return f"…{token[-4:]}"
