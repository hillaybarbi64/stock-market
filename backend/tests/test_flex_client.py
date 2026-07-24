"""Flex client: request → poll → download flow, with retryable pending codes."""

import httpx
import pytest

from app.ibkr import flex
from app.ibkr.flex import FlexClient, FlexError

SEND_OK = """<FlexStatementResponse timestamp="13 July, 2026 03:00 PM EDT">
<Status>Success</Status><ReferenceCode>1234567890</ReferenceCode>
<Url>https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement</Url>
</FlexStatementResponse>"""

SEND_BAD_TOKEN = """<FlexStatementResponse timestamp="x">
<Status>Fail</Status><ErrorCode>1012</ErrorCode>
<ErrorMessage>Token has expired.</ErrorMessage></FlexStatementResponse>"""

PENDING = """<FlexStatementResponse timestamp="x">
<Status>Warn</Status><ErrorCode>1019</ErrorCode>
<ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>
</FlexStatementResponse>"""

STATEMENT = """<FlexQueryResponse queryName="all" type="AF">
<FlexStatements count="1"><FlexStatement accountId="U***" fromDate="2026-02-17" toDate="2026-07-13">
</FlexStatement></FlexStatements></FlexQueryResponse>"""


def make_client(handler) -> FlexClient:
    client = FlexClient(token="test-token", query_id="42", poll_interval_s=0.01)

    transport = httpx.MockTransport(handler)
    orig_fetch = client.fetch_statement

    async def fetch():
        async with httpx.AsyncClient(transport=transport) as http:
            ref = await client._send_request(http)
            return await client._poll_statement(http, ref)

    client.fetch_statement = fetch  # type: ignore[method-assign]
    assert orig_fetch is not None
    return client


async def test_happy_path_with_spaced_pending_polls(monkeypatch):
    polls = {"n": 0}
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(flex.asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        if flex.SEND_PATH in str(request.url):
            return httpx.Response(200, text=SEND_OK)
        polls["n"] += 1
        return httpx.Response(200, text=PENDING if polls["n"] < 3 else STATEMENT)

    statement = await make_client(handler).fetch_statement()
    assert "<FlexQueryResponse" in statement.xml
    assert polls["n"] == 3  # two pending responses, then the statement
    assert sleeps == [0.01, 0.01, 0.01]  # including before the first GetStatement


async def test_expired_token_raises_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEND_BAD_TOKEN)

    with pytest.raises(FlexError) as exc:
        await make_client(handler).fetch_statement()
    assert exc.value.code == "1012"


def test_missing_credentials_rejected_early():
    with pytest.raises(ValueError):
        FlexClient(token="", query_id="42")


async def test_retryable_send_response_is_single_shot():
    sends = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        sends["n"] += 1
        return httpx.Response(200, text=PENDING)

    client = FlexClient(token="test-token", query_id="42", poll_interval_s=0.01)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(FlexError) as exc:
            await client._send_request(http)

    assert exc.value.code == "1019"
    assert sends["n"] == 1


async def test_production_default_waits_ten_seconds_before_statement_poll(monkeypatch):
    sleeps: list[float] = []
    requests: list[str] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(flex.asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        body = SEND_OK if flex.SEND_PATH in request.url.path else STATEMENT
        return httpx.Response(200, text=body)

    client = FlexClient(token="test-token", query_id="42")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        reference = await client._send_request(http)
        await client._poll_statement(http, reference)

    assert len(requests) == 2
    assert requests[0].endswith(flex.SEND_PATH)
    assert requests[1].endswith(flex.GET_PATH)
    assert sleeps == [10.0]


async def test_get_statement_transport_retry_reuses_reference_without_new_send(monkeypatch):
    sends = 0
    polls = 0

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(flex.asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sends, polls
        if flex.SEND_PATH in request.url.path:
            sends += 1
            return httpx.Response(200, text=SEND_OK)
        polls += 1
        if polls == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, text=STATEMENT)

    statement = await make_client(handler).fetch_statement()

    assert "<FlexQueryResponse" in statement.xml
    assert sends == 1
    assert polls == 2


async def test_get_statement_503_retry_reuses_reference(monkeypatch):
    sends = 0
    polls = 0

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(flex.asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal sends, polls
        if flex.SEND_PATH in request.url.path:
            sends += 1
            return httpx.Response(200, text=SEND_OK)
        polls += 1
        if polls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, text=STATEMENT)

    await make_client(handler).fetch_statement()

    assert sends == 1
    assert polls == 2
