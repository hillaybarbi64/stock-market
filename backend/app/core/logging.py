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
_TOKEN_KEYS = {"token", "flex_token", "password", "secret", "authorization"}
_LONG_DIGITS_RE = re.compile(r"\b\d{15,}\b")


def _mask_value(value: str) -> str:
    value = _ACCOUNT_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", value)
    return _LONG_DIGITS_RE.sub("***", value)


def _masking_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if key.lower() in _TOKEN_KEYS:
            event_dict[key] = "***"
        elif isinstance(value, str):
            event_dict[key] = _mask_value(value)
    return event_dict


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")
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
            _masking_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
