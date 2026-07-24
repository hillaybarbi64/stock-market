"""IBKR Flex Web Service client (read-only by nature).

Protocol (verified against IBKR docs 2026-07):
1. SendRequest with token + queryId → returns a ReferenceCode.
2. GetStatement with token + ReferenceCode → the XML statement, or an
   "in progress" error code while IBKR is still generating it.

We submit exactly one report-generation request, then poll conservatively.
IBKR allows at most one request/second and ten requests/minute per token, so
every retrieval attempt is separated by ten seconds. The token is a secret:
it is sent only over HTTPS and never logged.
"""

import asyncio
from dataclasses import dataclass

import httpx
from defusedxml import ElementTree as SafeET

from app.core.logging import get_logger

log = get_logger(__name__)

BASE_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet"
SEND_PATH = "/FlexStatementService.SendRequest"
GET_PATH = "/FlexStatementService.GetStatement"
USER_AGENT = "ibkr-dashboard/0.1"

# Error codes that mean "the accepted statement is not ready yet" per IBKR docs.
_POLL_RETRYABLE_CODES = {"1019", "1021", "1001"}


class FlexError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"Flex error {code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FlexStatement:
    """Raw XML payload of a generated Flex statement."""

    xml: str


class FlexClient:
    def __init__(
        self,
        token: str,
        query_id: str,
        poll_interval_s: float = 10.0,
        max_polls: int = 24,
        timeout_s: float = 60.0,
    ) -> None:
        if not token or not query_id:
            raise ValueError("Flex token and query id are required (see RUNBOOK.md §3)")
        self._token = token
        self._query_id = query_id
        self._poll_interval_s = poll_interval_s
        self._max_polls = max_polls
        self._timeout_s = timeout_s

    async def fetch_statement(self) -> FlexStatement:
        async with httpx.AsyncClient(
            timeout=self._timeout_s, headers={"User-Agent": USER_AGENT}
        ) as client:
            reference_code = await self._send_request(client)
            return await self._poll_statement(client, reference_code)

    async def _send_request(self, client: httpx.AsyncClient) -> str:
        """Submit exactly one query and return its ReferenceCode.

        A retryable failure is surfaced to the caller instead of silently
        generating more reports. This makes one manual sync equal one
        SendRequest and prevents another account-level lockout.
        """
        resp = await client.get(
            BASE_URL + SEND_PATH,
            params={"t": self._token, "q": self._query_id, "v": "3"},
        )
        resp.raise_for_status()
        root = SafeET.fromstring(resp.text)
        status = root.findtext("Status")
        if status == "Success":
            reference_code = root.findtext("ReferenceCode")
            if not reference_code:
                raise FlexError("?", "missing ReferenceCode in Flex response")
            log.info("flex_request_accepted")
            return reference_code
        code = root.findtext("ErrorCode") or "?"
        message = root.findtext("ErrorMessage") or "unrecognized Flex response"
        raise FlexError(code, message)

    async def _poll_statement(
        self, client: httpx.AsyncClient, reference_code: str
    ) -> FlexStatement:
        for attempt in range(1, self._max_polls + 1):
            # Wait before the first retrieval too: SendRequest and GetStatement
            # share the same per-token request budget.
            await asyncio.sleep(self._poll_interval_s)
            try:
                resp = await client.get(
                    BASE_URL + GET_PATH,
                    params={"t": self._token, "q": reference_code, "v": "3"},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status != 429 and status < 500:
                    raise
                log.warning(
                    "flex_statement_poll_http_retry",
                    attempt=attempt,
                    http_status=status,
                )
                if attempt == self._max_polls:
                    raise
                continue
            except httpx.TransportError:
                log.warning("flex_statement_poll_network_retry", attempt=attempt)
                if attempt == self._max_polls:
                    raise
                continue
            text = resp.text
            # A ready statement starts with <FlexQueryResponse; errors come as
            # a small <FlexStatementResponse> envelope.
            if "<FlexQueryResponse" in text[:200]:
                log.info("flex_statement_downloaded", bytes=len(text), polls=attempt)
                return FlexStatement(xml=text)
            root = SafeET.fromstring(text)
            code = root.findtext("ErrorCode") or "?"
            message = root.findtext("ErrorMessage") or "unknown Flex response"
            if code in _POLL_RETRYABLE_CODES:
                log.info("flex_statement_pending", attempt=attempt, code=code)
                continue
            raise FlexError(code, message)
        raise FlexError("timeout", f"statement not ready after {self._max_polls} polls")
