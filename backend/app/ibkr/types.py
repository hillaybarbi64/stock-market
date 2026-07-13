"""Normalized IBKR data shapes.

Everything downstream (persistence, websocket, API) works with these types,
never with raw ib_async objects — so the integration surface stays testable
and swappable."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class GatewayState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    GATEWAY_DOWN = "gateway_down"  # TCP refused — IB Gateway process not reachable
    AUTH_REQUIRED = "auth_required"  # gateway up but session not authenticated


class PriceQuality(StrEnum):
    REALTIME = "realtime"
    DELAYED = "delayed"
    FROZEN = "frozen"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AccountSummaryData:
    """Account-level values in base currency. Source: gateway."""

    ts: datetime
    base_currency: str
    net_liquidation: Decimal | None = None
    total_cash: Decimal | None = None
    gross_position_value: Decimal | None = None
    buying_power: Decimal | None = None
    available_funds: Decimal | None = None
    excess_liquidity: Decimal | None = None
    init_margin: Decimal | None = None
    maint_margin: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    daily_pnl: Decimal | None = None
    leverage: Decimal | None = None


@dataclass(frozen=True)
class CashBalanceData:
    ts: datetime
    currency: str
    cash_balance: Decimal
    settled_cash: Decimal | None = None
    nlv_in_ccy: Decimal | None = None
    fx_rate_to_base: Decimal | None = None


@dataclass(frozen=True)
class InstrumentData:
    conid: int
    symbol: str
    sec_type: str
    currency: str
    name: str | None = None
    exchange: str | None = None


@dataclass(frozen=True)
class PositionData:
    ts: datetime
    instrument: InstrumentData
    quantity: Decimal
    avg_cost: Decimal | None = None
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    daily_pnl: Decimal | None = None
    price_quality: PriceQuality = PriceQuality.UNKNOWN


@dataclass(frozen=True)
class ExecutionData:
    exec_id: str
    instrument: InstrumentData
    side: str  # BUY | SELL
    quantity: Decimal
    price: Decimal
    trade_time: datetime
    order_id: str | None = None
    perm_id: str | None = None
    exchange: str | None = None
    commission: Decimal | None = None
    commission_currency: str | None = None
    realized_pnl_ib: Decimal | None = None


@dataclass(frozen=True)
class OrderData:
    perm_id: str
    status: str
    instrument: InstrumentData | None = None
    side: str | None = None
    order_type: str | None = None
    limit_price: Decimal | None = None
    aux_price: Decimal | None = None
    tif: str | None = None
    quantity: Decimal | None = None
    filled: Decimal | None = None
    remaining: Decimal | None = None


@dataclass
class ConnectionInfo:
    state: GatewayState = GatewayState.DISCONNECTED
    readonly: bool = True
    account_id_masked: str | None = None
    connected_since: datetime | None = None
    last_update: datetime | None = None
    last_error: str | None = None
    reconnect_attempts: int = 0
    next_retry_in_s: float | None = None
    market_data_type: str | None = None  # realtime | delayed | unknown
    detail: dict = field(default_factory=dict)
