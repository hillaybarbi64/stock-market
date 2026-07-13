"""Gateway supervisor: read-only enforcement, state machine, normalization."""

import asyncio
from decimal import Decimal

import pytest
from ib_async.objects import AccountValue

from app.core.config import Settings
from app.ibkr.gateway import GatewaySupervisor, ReadOnlyViolation, mask_account
from app.ibkr.types import (
    AccountSummaryData,
    CashBalanceData,
    ConnectionInfo,
    GatewayState,
)
from tests.fakes import FakeIB


class RecordingListener:
    def __init__(self) -> None:
        self.states: list[GatewayState] = []
        self.summaries: list[AccountSummaryData] = []
        self.balances: list[list[CashBalanceData]] = []

    async def on_connection(self, info: ConnectionInfo) -> None:
        self.states.append(info.state)

    async def on_account_summary(self, data: AccountSummaryData) -> None:
        self.summaries.append(data)

    async def on_cash_balances(self, balances) -> None:
        self.balances.append(balances)

    async def on_position(self, position) -> None: ...

    async def on_execution(self, execution) -> None: ...

    async def on_order(self, order) -> None: ...


def make_settings(**kw) -> Settings:
    return Settings(ibkr_gateway_autostart=False, _env_file=None, **kw)


def test_readonly_false_is_refused():
    listener = RecordingListener()
    with pytest.raises(ReadOnlyViolation):
        GatewaySupervisor(make_settings(ibkr_readonly=False), listener)


def test_mask_account():
    assert mask_account("U7654321") == "U***321"
    assert mask_account("U1") == "***"


async def test_refused_connection_goes_gateway_down_and_schedules_retry():
    listener = RecordingListener()
    sup = GatewaySupervisor(
        make_settings(), listener, ib_factory=lambda: FakeIB(connect_error=ConnectionRefusedError())
    )
    await sup.start()
    await asyncio.sleep(0.1)
    await sup.stop()

    assert GatewayState.CONNECTING in listener.states
    assert GatewayState.GATEWAY_DOWN in listener.states
    assert sup.info.next_retry_in_s == 5  # first backoff step, no tight loop


async def test_successful_connect_emits_connected_and_summary():
    values = [
        AccountValue("U7654321", "NetLiquidation", "3490.73", "USD", ""),
        AccountValue("U7654321", "TotalCashValue", "2551.56", "USD", ""),
        AccountValue("U7654321", "BuyingPower", "12316", "USD", ""),
        AccountValue("U7654321", "CashBalance", "-760.54", "USD", ""),
        AccountValue("U7654321", "CashBalance", "10000", "ILS", ""),
        AccountValue("U7654321", "ExchangeRate", "0.3305", "ILS", ""),
    ]
    fake = FakeIB(account_values=values)
    listener = RecordingListener()
    sup = GatewaySupervisor(make_settings(), listener, ib_factory=lambda: fake)
    await sup.start()
    await asyncio.sleep(0.1)

    assert sup.info.state == GatewayState.CONNECTED
    assert sup.info.account_id_masked == "U***321"
    assert listener.summaries, "initial account summary must be emitted on connect"
    summary = listener.summaries[-1]
    assert summary.net_liquidation == Decimal("3490.73")
    assert summary.base_currency == "USD"

    assert listener.balances, "per-currency balances must be emitted"
    ccys = {b.currency for b in listener.balances[-1]}
    assert ccys == {"USD", "ILS"}
    ils = next(b for b in listener.balances[-1] if b.currency == "ILS")
    assert ils.fx_rate_to_base == Decimal("0.3305")

    # disconnect → supervisor reports loss and schedules reconnect
    fake.disconnectedEvent.emit()
    await asyncio.sleep(0.05)
    assert GatewayState.DISCONNECTED in listener.states
    await sup.stop()


async def test_manual_reconnect_skips_backoff():
    attempts = 0

    def factory():
        nonlocal attempts
        attempts += 1
        return FakeIB(connect_error=ConnectionRefusedError())

    listener = RecordingListener()
    sup = GatewaySupervisor(make_settings(), listener, ib_factory=factory)
    await sup.start()
    await asyncio.sleep(0.05)
    first = attempts
    await sup.manual_reconnect()  # skip the 5s wait
    await asyncio.sleep(0.05)
    await sup.stop()
    assert attempts > first
