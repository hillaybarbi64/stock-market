"""Trading history: executions, orders, cash transactions, corporate actions.

Every externally-sourced table carries IBKR's natural unique id so repeated
syncs upsert instead of duplicating (see DATA_DICTIONARY.md)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Execution(Base):
    """A single fill. Sources: gateway (live, recent days) and flex (full history)."""

    __tablename__ = "executions"

    exec_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(32), index=True)
    perm_id: Mapped[str | None] = mapped_column(String(32), index=True)
    conid: Mapped[int] = mapped_column(ForeignKey("instruments.conid"), index=True)
    side: Mapped[str] = mapped_column(String(8))  # BUY | SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trade_time_tz: Mapped[str | None] = mapped_column(String(48))  # original tz name from source
    exchange: Mapped[str | None] = mapped_column(String(32))
    order_type: Mapped[str | None] = mapped_column(String(16))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    commission_currency: Mapped[str | None] = mapped_column(String(8))
    realized_pnl_ib: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))  # as reported by IBKR (FIFO)
    currency: Mapped[str] = mapped_column(String(8))
    fx_rate_to_base: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    source: Mapped[str] = mapped_column(String(16))  # gateway | flex
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Order(Base):
    """Order state (read-only mirror; this system never creates orders)."""

    __tablename__ = "orders"

    perm_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conid: Mapped[int | None] = mapped_column(ForeignKey("instruments.conid"), index=True)
    status: Mapped[str] = mapped_column(String(24))
    side: Mapped[str | None] = mapped_column(String(8))
    order_type: Mapped[str | None] = mapped_column(String(16))
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    aux_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    tif: Mapped[str | None] = mapped_column(String(8))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    filled: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    remaining: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(16), default="gateway")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CashTransaction(Base):
    """Deposits, withdrawals, dividends, taxes, fees, interest, FX. Source: flex."""

    __tablename__ = "cash_transactions"

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(8))
    fx_rate_to_base: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    tx_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    settle_date: Mapped[date | None] = mapped_column(Date)
    conid: Mapped[int | None] = mapped_column(ForeignKey("instruments.conid"), index=True)
    description: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(16), default="flex")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    conid: Mapped[int | None] = mapped_column(ForeignKey("instruments.conid"), index=True)
    ratio: Mapped[str | None] = mapped_column(String(32))
    ex_date: Mapped[date | None] = mapped_column(Date)
    pay_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(String(512))
    raw: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(16), default="flex")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
