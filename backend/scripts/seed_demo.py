"""Seed the database with a realistic demo portfolio.

For local development / demos WITHOUT a live IB Gateway or Flex connection.
It writes the same tables the read-only API falls back to when the gateway is
down (account_snapshots, cash_balances, positions, instrument_bars,
daily_equity, cash_transactions, executions, instruments), so the whole UI —
dashboard, positions, performance, risk, trades — renders populated.

The data is synthetic and deterministic (fixed RNG seed). Run:

    uv run python scripts/seed_demo.py

Re-running is safe: it clears the seeded tables first. This does NOT touch a
real account — it only inserts demo rows into the configured database.
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.db.base import db_session, dispose_engine
from app.db.models import (
    AccountSnapshot,
    CashBalance,
    CashTransaction,
    DailyEquity,
    Execution,
    Instrument,
    InstrumentBar,
    Position,
)

NOW = datetime.now(UTC)
TODAY = date.today()


def D(x, q: int = 4) -> Decimal:
    return Decimal(str(round(float(x), q)))


def business_days(back_days: int) -> list[date]:
    """Weekday dates from `back_days` ago up to and including today."""
    out = []
    d = TODAY - timedelta(days=back_days)
    while d <= TODAY:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


HOLDINGS = [
    dict(conid=265598, symbol="AAPL", name="Apple Inc.", sector="טכנולוגיה",
         qty=320, avg=178.40, start=165, drift=0.0016, vol=0.017, basevol=4_200_000),
    dict(conid=4815747, symbol="NVDA", name="NVIDIA Corp.", sector="מוליכים למחצה",
         qty=210, avg=118.70, start=95, drift=0.0042, vol=0.030, basevol=9_100_000),
    dict(conid=272093, symbol="MSFT", name="Microsoft Corp.", sector="טכנולוגיה",
         qty=96, avg=402.10, start=388, drift=0.0011, vol=0.014, basevol=2_100_000),
    dict(conid=76792991, symbol="TSLA", name="Tesla Inc.", sector="צריכה מחזורית",
         qty=140, avg=232.50, start=260, drift=-0.0008, vol=0.032, basevol=6_800_000),
    dict(conid=4391, symbol="AMD", name="Adv. Micro Devices", sector="מוליכים למחצה",
         qty=240, avg=142.30, start=120, drift=0.0021, vol=0.028, basevol=3_400_000),
    dict(conid=208813720, symbol="GOOGL", name="Alphabet Inc. A", sector="תקשורת",
         qty=130, avg=158.90, start=150, drift=0.0013, vol=0.016, basevol=1_900_000),
    dict(conid=3691937, symbol="AMZN", name="Amazon.com Inc.", sector="צריכה מחזורית",
         qty=110, avg=176.20, start=160, drift=0.0018, vol=0.019, basevol=2_600_000),
    dict(conid=107113386, symbol="META", name="Meta Platforms", sector="תקשורת",
         qty=58, avg=498.70, start=440, drift=0.0024, vol=0.021, basevol=1_500_000),
]

CASH_USD = 18_420.55
CASH_EUR = 2_140.00
EUR_RATE = 1.0850


def gen_bars(h: dict) -> list[dict]:
    """A daily-OHLCV random walk ending near a realistic current price."""
    rnd = random.Random(h["conid"])
    days = business_days(190)
    price = float(h["start"])
    bars = []
    for d in days:
        o = price
        shock = (rnd.random() - 0.5) * 2 * h["vol"] + h["drift"]
        c = max(1.0, o * (1 + shock))
        hi = max(o, c) * (1 + rnd.random() * h["vol"] * 0.6)
        lo = min(o, c) * (1 - rnd.random() * h["vol"] * 0.6)
        vol = round(h["basevol"] * (0.6 + rnd.random() * 0.9))
        bars.append(dict(date=d, open=o, high=hi, low=lo, close=c, volume=vol))
        price = c
    return bars


async def main() -> None:
    async with db_session() as db:
        # Clear seeded tables (children before instruments).
        for model in (Execution, CashTransaction, Position, InstrumentBar,
                      DailyEquity, CashBalance, AccountSnapshot, Instrument):
            await db.execute(delete(model))
        await db.commit()

        gross = 0.0
        unreal_total = 0.0
        series: dict[int, list[dict]] = {}

        # Instruments first + flush, so the FK-referencing rows below are valid.
        for h in HOLDINGS:
            db.add(Instrument(
                conid=h["conid"], symbol=h["symbol"], name=h["name"], sec_type="STK",
                currency="USD", exchange="NASDAQ", sector=h["sector"],
                country="USA", classification_source="manual", updated_at=NOW,
            ))
        await db.flush()

        for h in HOLDINGS:
            bars = gen_bars(h)
            series[h["conid"]] = bars
            for b in bars:
                db.add(InstrumentBar(
                    conid=h["conid"], bar_date=b["date"], open=D(b["open"], 6),
                    high=D(b["high"], 6), low=D(b["low"], 6), close=D(b["close"], 6),
                    volume=D(b["volume"], 2), source="gateway", updated_at=NOW,
                ))
            last, prev = bars[-1]["close"], bars[-2]["close"]
            mv = last * h["qty"]
            unreal = (last - h["avg"]) * h["qty"]
            daily = (last - prev) * h["qty"]
            gross += mv
            unreal_total += unreal
            db.add(Position(
                conid=h["conid"], quantity=D(h["qty"], 6), avg_cost=D(h["avg"], 6),
                market_price=D(last, 6), market_value=D(mv), unrealized_pnl=D(unreal),
                daily_pnl=D(daily), currency="USD", price_quality="delayed",
                is_open=True, opened_at=NOW - timedelta(days=200), updated_at=NOW,
            ))

        nlv = gross + CASH_USD
        db.add(AccountSnapshot(
            ts=NOW, net_liquidation=D(nlv), total_cash=D(CASH_USD),
            gross_position_value=D(gross), buying_power=D(CASH_USD * 4),
            available_funds=D(CASH_USD * 2.1), excess_liquidity=D(CASH_USD * 2.4),
            init_margin=D(gross * 0.25), maint_margin=D(gross * 0.22),
            unrealized_pnl=D(unreal_total), realized_pnl=D(1284.40),
            leverage=D(gross / nlv, 4), base_currency="USD", data_quality="delayed",
        ))
        db.add(CashBalance(ts=NOW, currency="USD", cash_balance=D(CASH_USD),
                           settled_cash=D(CASH_USD), nlv_in_ccy=D(nlv), fx_rate_to_base=D(1, 10)))
        db.add(CashBalance(ts=NOW, currency="EUR", cash_balance=D(CASH_EUR),
                           settled_cash=D(CASH_EUR), nlv_in_ccy=None, fx_rate_to_base=D(EUR_RATE, 10)))

        # ── Daily equity curve (~13 months of business days) ──────────
        # Build a random walk, then scale the whole series so it ends exactly
        # on the current NLV — scaling (not a final-day jump) keeps daily
        # returns realistic on non-flow days.
        eq_days = business_days(400)
        rnd = random.Random(42)
        nav = nlv * 0.60
        deposit_day = eq_days[len(eq_days) // 3]
        withdraw_day = eq_days[int(len(eq_days) * 0.7)]
        raw: list[tuple[date, float, float, float]] = []
        for d in eq_days:
            nav *= 1 + (rnd.random() - 0.46) * 0.012
            deposits = withdrawals = 0.0
            if d == deposit_day:
                nav += 15_000
                deposits = 15_000
            if d == withdraw_day:
                nav -= 5_000
                withdrawals = 5_000
            raw.append((d, nav, deposits, withdrawals))
        scale = nlv / raw[-1][1]
        for d, nav_v, deposits, withdrawals in raw:
            n = nav_v * scale
            db.add(DailyEquity(
                equity_date=d, nav=D(n), cash=D(CASH_USD),
                stock_value=D(n - CASH_USD), deposits=D(deposits), withdrawals=D(withdrawals),
                source="flex", updated_at=NOW,
            ))

        # ── Cash transactions (feed the performance cash breakdown) ───
        first = eq_days[0]
        txns = [
            ("DEPOSIT", 45_000, first, "הפקדה ראשונית"),
            ("DEPOSIT", 15_000, deposit_day, "הפקדה"),
            ("WITHDRAWAL", -5_000, withdraw_day, "משיכה"),
            ("DIVIDEND", 512.40, first + timedelta(days=90), "דיבידנד AAPL"),
            ("DIVIDEND", 634.10, first + timedelta(days=180), "דיבידנד MSFT"),
            ("DIVIDEND", 695.83, first + timedelta(days=270), "דיבידנד רבעוני"),
            ("WITHHOLDING_TAX", -276.35, first + timedelta(days=181), "ניכוי מס במקור"),
            ("FEE", -412.90, first + timedelta(days=200), "דמי ניהול ועמלות"),
            ("BROKER_INTEREST_RECEIVED", 318.44, first + timedelta(days=250), "ריבית זכות"),
        ]
        for i, (typ, amt, d, desc) in enumerate(txns):
            db.add(CashTransaction(
                transaction_id=f"TX{i:04d}", type=typ, amount=D(amt), currency="USD",
                fx_rate_to_base=D(1, 10), tx_datetime=datetime(d.year, d.month, d.day, 12, tzinfo=UTC),
                settle_date=d, description=desc, source="flex", updated_at=NOW,
            ))

        # ── Executions (trade blotter) ───────────────────────────────
        tno = 0
        for h in HOLDINGS[:6]:
            bars = series[h["conid"]]
            for k in (0, 1):
                bar = bars[-1 - k * 20]
                side = "BUY" if k == 0 else "SELL"
                qty = round(h["qty"] / (k + 2))
                price = bar["close"]
                realized = (price - h["avg"]) * qty if side == "SELL" else None
                db.add(Execution(
                    exec_id=f"E{100000 + tno}", order_id=f"O{5000 + tno}", perm_id=f"P{9000 + tno}",
                    conid=h["conid"], side=side, quantity=D(qty, 6), price=D(price, 6),
                    trade_time=datetime(bar["date"].year, bar["date"].month, bar["date"].day,
                                        15, 10 + tno % 40, tzinfo=UTC),
                    trade_time_tz="America/New_York", exchange="NASDAQ",
                    order_type="LMT" if k == 0 else "MKT",
                    commission=D(-max(1.0, qty * 0.005), 6), commission_currency="USD",
                    realized_pnl_ib=D(realized) if realized is not None else None,
                    currency="USD", fx_rate_to_base=D(1, 10),
                    net_amount=D(qty * price * (-1 if side == "BUY" else 1)),
                    source="gateway" if k == 0 else "flex", updated_at=NOW,
                ))
                tno += 1

        await db.commit()
        print(f"seeded: {len(HOLDINGS)} instruments/positions, "
              f"{sum(len(v) for v in series.values())} bars, {len(eq_days)} equity days, "
              f"{len(txns)} cash txns, {tno} executions; NLV={nlv:,.2f}")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
