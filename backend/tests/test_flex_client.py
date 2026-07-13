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


async def test_happy_path_with_pending_retries():
    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if flex.SEND_PATH in str(request.url):
            return httpx.Response(200, text=SEND_OK)
        polls["n"] += 1
        return httpx.Response(200, text=PENDING if polls["n"] < 3 else STATEMENT)

    statement = await make_client(handler).fetch_statement()
    assert "<FlexQueryResponse" in statement.xml
    assert polls["n"] == 3  # two pending responses, then the statement


async def test_expired_token_raises_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEND_BAD_TOKEN)

    with pytest.raises(FlexError) as exc:
        await make_client(handler).fetch_statement()
    assert exc.value.code == "1012"


def test_missing_credentials_rejected_early():
    with pytest.raises(ValueError):
        FlexClient(token="", query_id="42")
