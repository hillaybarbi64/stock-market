"""FIFO trade-cycle builder: partial exits, scaling, zero-cross flips, shorts."""

from datetime import UTC, datetime
from decimal import Decimal

from app.db.models import Execution
from app.services.trade_cycles import build_cycles

D = Decimal
_T = 0


def ex(side: str, qty: str, price: str, realized: str | None = None, fee: str = "1") -> Execution:
    global _T
    _T += 1
    return Execution(
        exec_id=f"e{_T}",
        conid=1,
        side=side,
        quantity=D(qty),
        price=D(price),
        trade_time=datetime(2026, 1, 1, 10, _T, tzinfo=UTC),
        commission=D(fee) * -1,
        realized_pnl_ib=D(realized) if realized else None,
        currency="USD",
        source="flex",
        updated_at=datetime.now(UTC),
    )


def test_simple_round_trip():
    cycles = build_cycles([ex("BUY", "10", "100"), ex("SELL", "10", "110", realized="99")])
    assert len(cycles) == 1
    c = cycles[0]
    assert c.direction == "LONG"
    assert c.close_time is not None
    assert c.realized_pnl == D("100")  # (110-100)*10, before fees
    assert c.realized_pnl_ib == D("99")  # IBKR's after-fee figure kept separately
    assert c.fees_total == D("2")
    assert c.max_quantity == D("10")


def test_partial_exit_keeps_cycle_open():
    cycles = build_cycles([ex("BUY", "10", "100"), ex("SELL", "4", "110")])
    assert len(cycles) == 1
    c = cycles[0]
    assert c.close_time is None
    assert c.realized_pnl == D("40")


def test_scale_in_fifo_matching():
    cycles = build_cycles([ex("BUY", "10", "100"), ex("BUY", "10", "120"), ex("SELL", "15", "130")])
    c = cycles[0]
    # FIFO: 10 @100 + 5 @120 → (30*10)+(10*5) = 350
    assert c.realized_pnl == D("350")
    assert c.max_quantity == D("20")
    assert c.close_time is None


def test_zero_cross_splits_into_two_cycles():
    cycles = build_cycles([ex("BUY", "5", "100"), ex("SELL", "8", "110")])
    assert len(cycles) == 2
    long_cycle, short_cycle = cycles
    assert long_cycle.direction == "LONG"
    assert long_cycle.close_time is not None
    assert long_cycle.realized_pnl == D("50")
    assert short_cycle.direction == "SHORT"
    assert short_cycle.close_time is None
    assert short_cycle.max_quantity == D("3")


def test_short_cycle_pnl():
    cycles = build_cycles([ex("SELL", "10", "100"), ex("BUY", "10", "90")])
    c = cycles[0]
    assert c.direction == "SHORT"
    assert c.realized_pnl == D("100")  # sold high, covered low
    assert c.close_time is not None


def test_multiple_sequential_cycles():
    cycles = build_cycles(
        [
            ex("BUY", "10", "100"),
            ex("SELL", "10", "105"),
            ex("BUY", "5", "102"),
            ex("SELL", "5", "101"),
        ]
    )
    assert len(cycles) == 2
    assert cycles[0].realized_pnl == D("50")
    assert cycles[1].realized_pnl == D("-5")


def test_same_second_cycles_have_distinct_stable_opening_execution_ids():
    shared_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    executions = [
        Execution(
            exec_id=exec_id,
            conid=1,
            side=side,
            quantity=D("1"),
            price=D(price),
            trade_time=shared_time,
            commission=D("-1"),
            currency="USD",
            source="flex",
            updated_at=shared_time,
        )
        for exec_id, side, price in (
            ("e-same-1", "BUY", "100"),
            ("e-same-2", "SELL", "101"),
            ("e-same-3", "BUY", "102"),
            ("e-same-4", "SELL", "103"),
        )
    ]

    cycles = build_cycles(executions)

    assert len(cycles) == 2
    assert [cycle.open_time for cycle in cycles] == [shared_time, shared_time]
    assert [cycle.open_exec_id for cycle in cycles] == ["e-same-1", "e-same-3"]
