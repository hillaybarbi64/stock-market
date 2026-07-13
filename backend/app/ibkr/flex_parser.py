"""Parser for IBKR Activity Flex Query XML → normalized records.

Tolerant by design: Flex omits attributes that are empty, sections the query
doesn't include are simply absent, and IBKR occasionally adds attributes.
Every accessor is defensive; missing data becomes None, never a crash.
Parsed with defusedxml (untrusted-XML safe).
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as SafeET

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class FlexInstrument:
    conid: int
    symbol: str
    sec_type: str
    currency: str
    name: str | None = None
    exchange: str | None = None


@dataclass(frozen=True)
class FlexTrade:
    exec_id: str
    instrument: FlexInstrument
    side: str
    quantity: Decimal
    price: Decimal
    trade_time: datetime
    order_id: str | None
    exchange: str | None
    order_type: str | None
    commission: Decimal | None
    commission_currency: str | None
    realized_pnl: Decimal | None
    fx_rate_to_base: Decimal | None
    net_amount: Decimal | None


@dataclass(frozen=True)
class FlexCashTransaction:
    transaction_id: str
    type: str
    amount: Decimal
    currency: str
    tx_datetime: datetime
    settle_date: date | None
    fx_rate_to_base: Decimal | None
    conid: int | None
    description: str | None
    instrument: FlexInstrument | None = None


@dataclass(frozen=True)
class FlexEquitySummary:
    report_date: date
    total: Decimal
    cash: Decimal | None
    stock: Decimal | None
    dividend_accruals: Decimal | None
    interest_accruals: Decimal | None


@dataclass(frozen=True)
class FlexOpenPosition:
    report_date: date
    instrument: FlexInstrument
    quantity: Decimal
    mark_price: Decimal | None
    cost_basis_price: Decimal | None


@dataclass(frozen=True)
class FlexCorporateAction:
    action_id: str
    type: str | None
    conid: int | None
    ex_date: date | None
    pay_date: date | None
    description: str | None
    instrument: FlexInstrument | None = None


@dataclass(frozen=True)
class FlexFxRate:
    report_date: date
    currency: str
    rate_to_base: Decimal


@dataclass
class FlexReport:
    account_id: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    when_generated: datetime | None = None
    trades: list[FlexTrade] = field(default_factory=list)
    cash_transactions: list[FlexCashTransaction] = field(default_factory=list)
    equity_summaries: list[FlexEquitySummary] = field(default_factory=list)
    open_positions: list[FlexOpenPosition] = field(default_factory=list)
    corporate_actions: list[FlexCorporateAction] = field(default_factory=list)
    fx_rates: list[FlexFxRate] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)  # element → count we could not parse


# ── attribute helpers ─────────────────────────────────────


def _dec(el, name: str) -> Decimal | None:
    raw = el.get(name)
    if raw in (None, ""):
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _int(el, name: str) -> int | None:
    raw = el.get(name)
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _str(el, name: str) -> str | None:
    raw = el.get(name)
    return raw if raw else None


def _date(el, name: str) -> date | None:
    raw = el.get(name)
    if not raw:
        return None
    raw = raw.replace("-", "")[:8]
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None


def _datetime(el, name: str) -> datetime | None:
    """Flex dateTime: 'yyyy-MM-dd;HH:mm:ss' (separator configurable) or 'yyyyMMdd;HHmmss'.
    Times are in the statement timezone (exchange-local per IBKR docs); we store
    them as-received and treat them as UTC-naive → tagged UTC with the original
    string kept upstream when it matters."""
    raw = el.get(name)
    if not raw:
        return None
    raw = raw.replace("-", "").replace(":", "").replace(",", ";").replace(" ", ";")
    try:
        if ";" in raw:
            d, t = raw.split(";", 1)
            return datetime.strptime(d + t[:6], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        return datetime.strptime(raw[:8], "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _instrument(el) -> FlexInstrument | None:
    conid = _int(el, "conid")
    if conid is None:
        return None
    return FlexInstrument(
        conid=conid,
        symbol=_str(el, "symbol") or str(conid),
        sec_type=_str(el, "assetCategory") or "STK",
        currency=_str(el, "currency") or "USD",
        name=_str(el, "description"),
        exchange=_str(el, "listingExchange") or _str(el, "exchange"),
    )


# ── main parse ────────────────────────────────────────────


def parse_flex_report(xml: str) -> FlexReport:
    root = SafeET.fromstring(xml)
    report = FlexReport()

    stmt = root.find(".//FlexStatement")
    if stmt is not None:
        report.account_id = _str(stmt, "accountId")
        report.from_date = _date(stmt, "fromDate")
        report.to_date = _date(stmt, "toDate")
        report.when_generated = _datetime(stmt, "whenGenerated")

    for el in root.iter("Trade"):
        parsed = _parse_trade(el)
        if parsed:
            report.trades.append(parsed)
        else:
            report.skipped["Trade"] = report.skipped.get("Trade", 0) + 1

    for el in root.iter("CashTransaction"):
        parsed = _parse_cash(el)
        if parsed:
            report.cash_transactions.append(parsed)
        else:
            report.skipped["CashTransaction"] = report.skipped.get("CashTransaction", 0) + 1

    for tag in ("EquitySummaryByReportDateInBase", "EquitySummaryInBase"):
        for el in root.iter(tag):
            parsed = _parse_equity(el)
            if parsed:
                report.equity_summaries.append(parsed)

    for el in root.iter("OpenPosition"):
        parsed = _parse_open_position(el)
        if parsed:
            report.open_positions.append(parsed)

    for el in root.iter("CorporateAction"):
        parsed = _parse_corporate_action(el)
        if parsed:
            report.corporate_actions.append(parsed)

    for el in root.iter("ConversionRate"):
        rd, ccy, rate = _date(el, "reportDate"), _str(el, "fromCurrency"), _dec(el, "rate")
        if rd and ccy and rate is not None:
            report.fx_rates.append(FlexFxRate(report_date=rd, currency=ccy, rate_to_base=rate))

    if report.skipped:
        log.warning("flex_parse_skipped", skipped=report.skipped)
    return report


def _parse_trade(el) -> FlexTrade | None:
    inst = _instrument(el)
    exec_id = _str(el, "ibExecID") or _str(el, "tradeID")
    quantity = _dec(el, "quantity")
    price = _dec(el, "tradePrice")
    when = _datetime(el, "dateTime") or _datetime(el, "tradeDate")
    side = _str(el, "buySell")
    if not (inst and exec_id and quantity is not None and price is not None and when and side):
        return None
    return FlexTrade(
        exec_id=exec_id,
        instrument=inst,
        side="BUY" if side.upper().startswith("B") else "SELL",
        quantity=abs(quantity),
        price=price,
        trade_time=when,
        order_id=_str(el, "ibOrderID"),
        exchange=_str(el, "exchange"),
        order_type=_str(el, "orderType"),
        commission=_dec(el, "ibCommission"),
        commission_currency=_str(el, "ibCommissionCurrency"),
        realized_pnl=_dec(el, "fifoPnlRealized"),
        fx_rate_to_base=_dec(el, "fxRateToBase"),
        net_amount=_dec(el, "netCash") or _dec(el, "tradeMoney"),
    )


_CASH_TYPE_MAP = {
    "Deposits/Withdrawals": None,  # resolved by sign → DEPOSIT / WITHDRAWAL
    "Dividends": "DIVIDEND",
    "Payment In Lieu Of Dividends": "PAYMENT_IN_LIEU",
    "Withholding Tax": "WITHHOLDING_TAX",
    "Broker Interest Paid": "BROKER_INTEREST_PAID",
    "Broker Interest Received": "BROKER_INTEREST_RECEIVED",
    "Broker Fees": "FEE",
    "Other Fees": "FEE",
    "Commission Adjustments": "COMMISSION_ADJ",
}


def _parse_cash(el) -> FlexCashTransaction | None:
    tx_id = _str(el, "transactionID")
    amount = _dec(el, "amount")
    when = _datetime(el, "dateTime") or _datetime(el, "reportDate")
    raw_type = _str(el, "type")
    currency = _str(el, "currency")
    if not (tx_id and amount is not None and when and raw_type and currency):
        return None
    mapped = _CASH_TYPE_MAP.get(raw_type)
    if raw_type == "Deposits/Withdrawals":
        mapped = "DEPOSIT" if amount > 0 else "WITHDRAWAL"
    tx_type = mapped or f"OTHER:{raw_type}"
    return FlexCashTransaction(
        transaction_id=tx_id,
        type=tx_type,
        amount=amount,
        currency=currency,
        tx_datetime=when,
        settle_date=_date(el, "settleDate"),
        fx_rate_to_base=_dec(el, "fxRateToBase"),
        conid=_int(el, "conid"),
        description=_str(el, "description"),
        instrument=_instrument(el),
    )


def _parse_equity(el) -> FlexEquitySummary | None:
    report_date = _date(el, "reportDate")
    total = _dec(el, "total")
    if not (report_date and total is not None):
        return None
    return FlexEquitySummary(
        report_date=report_date,
        total=total,
        cash=_dec(el, "cash"),
        stock=_dec(el, "stock"),
        dividend_accruals=_dec(el, "dividendAccruals"),
        interest_accruals=_dec(el, "interestAccruals"),
    )


def _parse_open_position(el) -> FlexOpenPosition | None:
    inst = _instrument(el)
    report_date = _date(el, "reportDate")
    quantity = _dec(el, "position")
    if not (inst and report_date and quantity is not None):
        return None
    return FlexOpenPosition(
        report_date=report_date,
        instrument=inst,
        quantity=quantity,
        mark_price=_dec(el, "markPrice"),
        cost_basis_price=_dec(el, "costBasisPrice"),
    )


def _parse_corporate_action(el) -> FlexCorporateAction | None:
    action_id = _str(el, "actionID") or _str(el, "transactionID")
    if not action_id:
        return None
    return FlexCorporateAction(
        action_id=action_id,
        type=_str(el, "type"),
        conid=_int(el, "conid"),
        ex_date=_date(el, "exDate") or _date(el, "reportDate"),
        pay_date=_date(el, "payDate"),
        description=_str(el, "actionDescription") or _str(el, "description"),
        instrument=_instrument(el),
    )
