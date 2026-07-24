"""Structured logging with automatic masking of sensitive values.

Every log line passes through a masking processor so that Flex tokens and
account ids can never leak into log output, whatever the call site does.
"""

import logging
import re
import sys
from typing import Any

import structlog

# IBKR account ids look like U1234567 / DU1234567; Flex tokens are long digit strings.
_ACCOUNT_RE = re.compile(r"\b(D?U)(\d{2,})(\d{3})\b")
_TOKEN_KEYS = {
    "token",
    "flex_token",
    "query_id",
    "flex_query_id",
    "reference_code",
    "finnhub_api_key",
    "api_key",
    "password",
    "secret",
    "authorization",
    "app_secret_key",
    "confirmation_id",
}
_LONG_DIGITS_RE = re.compile(r"\b\d{15,}\b")
_SENSITIVE_QUERY_RE = re.compile(
    r"([?&](?:t|q|token|api[_-]?key|key)=)[^&\s]+",
    flags=re.IGNORECASE,
)
_URL_PASSWORD_RE = re.compile(
    r"(\b[a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s/]+(@)",
    flags=re.IGNORECASE,
)
_SENSITIVE_KEY_SUFFIXES = (
    "_token",
    "_password",
    "_secret",
    "_api_key",
    "_query_id",
    "_confirmation_id",
)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower()
    return (
        normalized in _TOKEN_KEYS
        or normalized == "database_url"
        or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)
    )


def _mask_value(value: str) -> str:
    value = _URL_PASSWORD_RE.sub(r"\1***\2", value)
    value = _SENSITIVE_QUERY_RE.sub(r"\1***", value)
    value = _ACCOUNT_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", value)
    return _LONG_DIGITS_RE.sub("***", value)


def _mask_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_key(key) else _mask_nested(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_nested(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_nested(item) for item in value)
    if isinstance(value, str):
        return _mask_value(value)
    return value


def _masking_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if _is_sensitive_key(key):
            event_dict[key] = "***"
        else:
            event_dict[key] = _mask_nested(value)
    return event_dict


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")
    # httpx/httpcore log full request URLs at INFO. Both Flex and Finnhub put
    # credentials in query parameters, so those libraries must never emit
    # request URLs in normal application logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Exception text is added by format_exc_info, so redaction must run
            # afterwards to cover URLs embedded in tracebacks.
            _masking_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
