"""IBKR Flex Web Service client (read-only by nature).

Protocol (verified against IBKR docs 2026-07):
1. SendRequest with token + queryId → returns a ReferenceCode.
2. GetStatement with token + ReferenceCode → the XML statement, or an
   "in progress" error code while IBKR is still generating it.

We poll with bounded, spaced retries (the service allows ~1 req/s and
statement generation can take a while for big accounts). The token is a
secret: it is sent only over HTTPS and never logged (the logging layer also
masks it defensively).
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

# Error codes that mean "not ready yet, try again" per IBKR docs
_RETRYABLE_CODES = {"1019", "1021", "1001"}


class FlexError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"Flex error {code}: {message}")
        self.code = code


@dataclass(frozen=True)
class FlexStatement:
    """Raw XML payload of a generated Flex statement."""

    xml: str


class FlexClient:
    def __init__(
        self,
        token: str,
        query_id: str,
        poll_interval_s: float = 5.0,
        max_polls: int = 24,
        timeout_s: float = 60.0,
        send_retries: int = 8,
        send_retry_wait_s: float = 30.0,
    ) -> None:
        if not token or not query_id:
            raise ValueError("Flex token and query id are required (see RUNBOOK.md §3)")
        self._token = token
        self._query_id = query_id
        self._poll_interval_s = poll_interval_s
        self._max_polls = max_polls
        self._timeout_s = timeout_s
        self._send_retries = send_retries
        self._send_retry_wait_s = send_retry_wait_s

    async def fetch_statement(self) -> FlexStatement:
        async with httpx.AsyncClient(
            timeout=self._timeout_s, headers={"User-Agent": USER_AGENT}
        ) as client:
            reference_code = await self._send_request(client)
            return await self._poll_statement(client, reference_code)

    async def _send_request(self, client: httpx.AsyncClient) -> str:
        """Submit the query and get a ReferenceCode. IBKR throttles this
        endpoint and answers a transient 'try again shortly' (1001/1019/1021)
        when called too soon, so we retry with spacing instead of failing —
        which is what caused every sync to fail and, in turn, the 1025
        'too many failed attempts' lock."""
        for attempt in range(1, self._send_retries + 1):
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
                log.info("flex_request_accepted", attempt=attempt)
                return reference_code
            code = root.findtext("ErrorCode") or "?"
            message = root.findtext("ErrorMessage") or resp.text[:200]
            if code in _RETRYABLE_CODES and attempt < self._send_retries:
                log.info("flex_request_pending", attempt=attempt, code=code)
                await asyncio.sleep(self._send_retry_wait_s)
                continue
            raise FlexError(code, message)
        raise FlexError("timeout", f"SendRequest not accepted after {self._send_retries} attempts")

    async def _poll_statement(self, client: httpx.AsyncClient, reference_code: str) -> FlexStatement:
        for attempt in range(1, self._max_polls + 1):
            resp = await client.get(
                BASE_URL + GET_PATH,
                params={"t": self._token, "q": reference_code, "v": "3"},
            )
            resp.raise_for_status()
            text = resp.text
            # A ready statement starts with <FlexQueryResponse; errors come as
            # a small <FlexStatementResponse> envelope.
            if "<FlexQueryResponse" in text[:200]:
                log.info("flex_statement_downloaded", bytes=len(text), polls=attempt)
                return FlexStatement(xml=text)
            root = SafeET.fromstring(text)
            code = root.findtext("ErrorCode") or "?"
            message = root.findtext("ErrorMessage") or "unknown Flex response"
            if code in _RETRYABLE_CODES:
                log.info("flex_statement_pending", attempt=attempt, code=code)
                await asyncio.sleep(self._poll_interval_s)
                continue
            raise FlexError(code, message)
        raise FlexError("timeout", f"statement not ready after {self._max_polls} polls")
