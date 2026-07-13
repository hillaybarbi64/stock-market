"""Instruments, FX rates and benchmark prices."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    conid: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    sec_type: Mapped[str] = mapped_column(String(16))  # STK, OPT, FUT, CASH, ...
    currency: Mapped[str] = mapped_column(String(8))
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(64))
    # provenance: where the classification came from (flex | gateway | manual)
    classification_source: Mapped[str | None] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FxRate(Base):
    """Daily FX close rate to the account base currency. Stored so every
    historical computation is reproducible."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("rate_date", "currency", name="uq_fx_date_ccy"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    currency: Mapped[str] = mapped_column(String(8))
    rate_to_base: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    source: Mapped[str] = mapped_column(String(16))  # flex | gateway


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"
    __table_args__ = (UniqueConstraint("symbol", "price_date", name="uq_benchmark_symbol_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    price_date: Mapped[date] = mapped_column(Date, index=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    source: Mapped[str] = mapped_column(String(16), default="gateway")


class InstrumentBar(Base):
    """Daily OHLCV bar for an instrument, used for the candlestick / sparkline
    charts. Cached from IBKR historical data (a read-only request) so the UI
    renders without hammering the gateway. One row per (conid, day)."""

    __tablename__ = "instrument_bars"
    __table_args__ = (UniqueConstraint("conid", "bar_date", name="uq_bar_conid_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conid: Mapped[int] = mapped_column(index=True)
    bar_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    source: Mapped[str] = mapped_column(String(16), default="gateway")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
