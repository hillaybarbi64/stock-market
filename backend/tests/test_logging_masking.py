"""The log masking layer must strip account ids and tokens no matter what
the call site passes — this is a security control, not a formatting nicety."""

import logging
import sys

import httpx
import structlog

from app.core.logging import _mask_value, _masking_processor, configure_logging


def test_account_id_is_masked():
    assert _mask_value("account U1234567 connected") == "account U***567 connected"
    assert _mask_value("paper DU7654321") == "paper DU***321"


def test_long_digit_tokens_are_masked():
    masked = _mask_value("token 123456789012345678901234 used")
    assert "123456789012345678901234" not in masked
    assert "***" in masked


def test_sensitive_keys_are_masked():
    event = _masking_processor(None, "", {"flex_token": "abc123", "password": "x", "msg": "hi"})
    assert event["flex_token"] == "***"
    assert event["password"] == "***"
    assert event["msg"] == "hi"


def test_nested_secrets_and_urls_are_masked():
    event = _masking_processor(
        None,
        "",
        {
            "payload": {"token": "SUPERSECRET", "query_id": "12345"},
            "items": ["https://example.test/path?t=ALSOSECRET&q=98765"],
        },
    )

    assert event["payload"] == {"token": "***", "query_id": "***"}
    assert "ALSOSECRET" not in str(event)
    assert "98765" not in str(event)


def test_settings_shaped_secrets_and_database_password_are_masked():
    event = _masking_processor(
        None,
        "",
        {
            "settings": {
                "ibkr_flex_token": "SHORTSECRET",
                "ibkr_flex_query_id": "12345",
                "postgres_password": "db-secret",
                "database_url": "postgresql://user:db-secret@example.test/app",
            }
        },
    )

    assert event["settings"] == {
        "ibkr_flex_token": "***",
        "ibkr_flex_query_id": "***",
        "postgres_password": "***",
        "database_url": "***",
    }
    assert (
        _mask_value("connect postgresql://user:db-secret@example.test/app")
        == "connect postgresql://user:***@example.test/app"
    )


def test_formatted_exception_url_is_redacted():
    request = httpx.Request(
        "GET",
        "https://example.test/FlexStatementService.SendRequest?t=SUPERSECRET&q=12345",
    )
    response = httpx.Response(503, request=request)
    try:
        raise httpx.HTTPStatusError("server error", request=request, response=response)
    except httpx.HTTPStatusError:
        event = structlog.processors.format_exc_info(
            None,
            "error",
            {"event": "request failed", "exc_info": sys.exc_info()},
        )

    masked = _masking_processor(None, "error", event)
    assert "SUPERSECRET" not in str(masked)
    assert "q=12345" not in str(masked)


def test_short_numbers_untouched():
    assert _mask_value("price 123.45 qty 8") == "price 123.45 qty 8"


def test_query_parameter_secrets_are_masked_even_when_alphanumeric():
    masked = _mask_value(
        "GET https://example.test/path?t=FLEXsecretABC123&q=42&token=FINNhubSecret"
    )
    assert "FLEXsecretABC123" not in masked
    assert "FINNhubSecret" not in masked
    assert "q=42" not in masked


def test_http_clients_do_not_log_request_urls_at_info():
    configure_logging()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
