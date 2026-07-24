"""Bind one local appliance database to exactly one IBKR account."""

import hmac
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import db_session
from app.db.models import (
    AccountSnapshot,
    AlertEvent,
    AlertRule,
    Attachment,
    AuditLog,
    CashBalance,
    CashTransaction,
    CorporateAction,
    CycleExecution,
    DailyEquity,
    EntityTag,
    Execution,
    FxRate,
    Insight,
    JournalEntry,
    JournalTemplate,
    Order,
    Position,
    Setting,
    SyncRun,
    Tag,
    TradeCycle,
)
from app.services.local_crypto import account_fingerprint, local_key_check

ACCOUNT_BINDING_KEY = "ibkr_account_binding"
_BINDING_VERSION = 1


class AccountBindingRequiredError(RuntimeError):
    """No verified Gateway account has bound this installation yet."""


class AccountBindingMismatchError(RuntimeError):
    """The requested account is different from the installation binding."""


class AccountBindingKeyMismatchError(RuntimeError):
    """The local encryption key does not match the persisted binding."""


class AccountBindingConfirmationRequiredError(RuntimeError):
    """Legacy financial rows exist and require explicit account confirmation."""


async def ensure_account_binding(account_id: str) -> None:
    """Auto-bind an empty installation, or verify an existing binding."""
    if not account_id:
        raise AccountBindingRequiredError("A non-empty IBKR account is required")

    async with db_session() as session:
        row = await _load_binding_row(session)
        if row is not None:
            await assert_account_matches_binding(account_id, session=session)
            return
        if await _financial_data_exists(session):
            raise AccountBindingConfirmationRequiredError(
                "Existing financial data requires explicit account confirmation"
            )
        await _insert_binding(account_id, session)
        await assert_account_matches_binding(account_id, session=session)


async def confirm_account_binding(account_id: str) -> None:
    """Explicitly bind a legacy non-empty database to the displayed account."""
    if not account_id:
        raise AccountBindingRequiredError("A non-empty IBKR account is required")
    async with db_session() as session:
        row = await _load_binding_row(session)
        if row is None:
            await _insert_binding(account_id, session)
        await assert_account_matches_binding(account_id, session=session)


async def account_binding_exists(session: AsyncSession | None = None) -> bool:
    value = await _load_binding_value(session)
    return _valid_fingerprint(value) is not None


async def assert_account_matches_binding(
    account_id: str | None,
    *,
    session: AsyncSession | None = None,
) -> None:
    if not account_id:
        raise AccountBindingRequiredError("The IBKR account could not be verified")
    value = await _load_binding_value(session)
    if not isinstance(value, dict) or value.get("version") != _BINDING_VERSION:
        raise AccountBindingRequiredError(
            "Connect one IB Gateway account before importing Flex history"
        )
    stored = value.get("fingerprint")
    stored_key_check = value.get("key_check")
    if not isinstance(stored, str) or len(stored) != 64:
        raise AccountBindingRequiredError("The saved IBKR account binding is invalid")
    if not isinstance(stored_key_check, str) or not hmac.compare_digest(
        stored_key_check, local_key_check()
    ):
        raise AccountBindingKeyMismatchError(
            "APP_SECRET_KEY does not match the saved account binding"
        )
    candidate = account_fingerprint(account_id)
    if not hmac.compare_digest(stored, candidate):
        raise AccountBindingMismatchError(
            "This installation is already bound to a different IBKR account"
        )


async def _load_binding_value(session: AsyncSession | None) -> dict | None:
    if session is not None:
        row = await _load_binding_row(session)
        return row.value if row is not None and isinstance(row.value, dict) else None

    async with db_session() as owned_session:
        return await _load_binding_value(owned_session)


async def _load_binding_row(session: AsyncSession) -> Setting | None:
    return (
        await session.execute(select(Setting).where(Setting.key == ACCOUNT_BINDING_KEY))
    ).scalar_one_or_none()


async def _insert_binding(account_id: str, session: AsyncSession) -> None:
    payload = {
        "version": _BINDING_VERSION,
        "fingerprint": account_fingerprint(account_id),
        "key_check": local_key_check(),
    }
    stmt = pg_insert(Setting).values(
        key=ACCOUNT_BINDING_KEY,
        value=payload,
        updated_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[Setting.key])
    await session.execute(stmt)
    await session.commit()


async def _financial_data_exists(session: AsyncSession) -> bool:
    probes = (
        select(AccountSnapshot.id).limit(1),
        select(CashBalance.id).limit(1),
        select(Execution.exec_id).limit(1),
        select(Order.perm_id).limit(1),
        select(CashTransaction.transaction_id).limit(1),
        select(CorporateAction.action_id).limit(1),
        select(DailyEquity.equity_date).limit(1),
        select(Position.conid).limit(1),
        select(FxRate.id).limit(1),
        select(TradeCycle.id).limit(1),
        select(CycleExecution.id).limit(1),
        select(JournalEntry.id).limit(1),
        select(Attachment.id).limit(1),
        select(Insight.id).limit(1),
        select(AlertRule.id).limit(1),
        select(AlertEvent.id).limit(1),
        select(SyncRun.id).limit(1),
        select(AuditLog.id).limit(1),
        select(EntityTag.id).limit(1),
        select(Tag.id).limit(1),
        select(JournalTemplate.id).where(JournalTemplate.is_builtin.is_(False)).limit(1),
        select(Setting.key).where(Setting.key != ACCOUNT_BINDING_KEY).limit(1),
    )
    for query in probes:
        if (await session.execute(query)).scalar_one_or_none() is not None:
            return True
    return False


def _valid_fingerprint(value: dict | None) -> str | None:
    if not isinstance(value, dict) or value.get("version") != _BINDING_VERSION:
        return None
    fingerprint = value.get("fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        return None
    key_check = value.get("key_check")
    if not isinstance(key_check, str) or not hmac.compare_digest(key_check, local_key_check()):
        return None
    return fingerprint
