"""Test doubles for the IB Gateway layer.

These are TEST FIXTURES ONLY (see PROJECT_AUDIT.md §2): they simulate the
ib_async surface the supervisor touches so the connection state machine and
normalization can be tested without a live gateway. They are never imported
by production code.
"""

from ib_async.objects import AccountValue


class FakeEvent:
    def __init__(self) -> None:
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def emit(self, *args) -> None:
        for h in list(self._handlers):
            h(*args)


class FakeIB:
    """Minimal ib_async.IB stand-in. Configure behavior per test."""

    def __init__(
        self,
        connect_error: Exception | None = None,
        accounts: list[str] | None = None,
        account_values: list[AccountValue] | None = None,
    ) -> None:
        self._connect_error = connect_error
        self._accounts = accounts if accounts is not None else ["U7654321"]
        self._account_values = account_values or []
        self.connected = False

        self.accountValueEvent = FakeEvent()
        self.updatePortfolioEvent = FakeEvent()
        self.execDetailsEvent = FakeEvent()
        self.orderStatusEvent = FakeEvent()
        self.pnlEvent = FakeEvent()
        self.errorEvent = FakeEvent()
        self.disconnectedEvent = FakeEvent()

    async def connectAsync(self, host, port, clientId, readonly, timeout):
        assert readonly is True, "supervisor must always connect readonly"
        if self._connect_error is not None:
            raise self._connect_error
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def managedAccounts(self):
        return self._accounts

    def accountValues(self):
        return self._account_values

    def portfolio(self):
        return []

    def openTrades(self):
        return []

    def fills(self):
        return []

    async def reqExecutionsAsync(self, _filter):
        return []

    def pnl(self):
        return []

    def reqPnL(self, account):
        return None
