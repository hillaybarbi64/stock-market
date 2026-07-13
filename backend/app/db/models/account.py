"""Account-level state: snapshots, balances, daily equity, current positions."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountSnapshot(Base):
    """Intraday snapshot of account summary values, in base currency.
    Source: IB Gateway (live)."""

    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    net_liquidation: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    total_cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    gross_position_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    buying_power: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    available_funds: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    excess_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    init_margin: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    maint_margin: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    leverage: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    base_currency: Mapped[str] = mapped_column(String(8))
    data_quality: Mapped[str] = mapped_column(String(16), default="realtime")  # realtime|delayed|stale


class CashBalance(Base):
    """Per-currency cash balance at snapshot time. Source: IB Gateway."""

    __tablename__ = "cash_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(8))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    settled_cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    nlv_in_ccy: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    fx_rate_to_base: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))


class DailyEquity(Base):
    """One row per trading day — the backbone of all return calculations.
    Source: Flex EquitySummaryInBase; deposits/withdrawals aggregated from
    cash transactions; twr_daily computed by the system."""

    __tablename__ = "daily_equity"

    equity_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    stock_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    dividend_accruals: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    interest_accruals: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    deposits: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    withdrawals: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    twr_daily: Mapped[Decimal | None] = mapped_column(Numeric(14, 10))
    source: Mapped[str] = mapped_column(String(16), default="flex")
    source_line_hash: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Position(Base):
    """Current open positions. Continuously updated from IB Gateway."""

    __tablename__ = "positions"

    conid: Mapped[int] = mapped_column(
        ForeignKey("instruments.conid"), primary_key=True, autoincrement=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    daily_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(8))
    price_quality: Mapped[str] = mapped_column(String(16), default="unknown")  # realtime|delayed|frozen|unknown
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
