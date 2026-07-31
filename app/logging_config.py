"""Privacy-aware logging configuration for Hey Joey services."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.settings import JoeySettings


_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"
    ),
    re.compile(
        r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+"
    ),
)
_HANDLER_NAME = "hey-joey-console"


def redact_secrets(
    value: object,
) -> str:
    """Redact credential-like values from one log message."""

    text = str(value)

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(
            r"\1[REDACTED]",
            text,
        )

    return text


class JoeyJsonFormatter(logging.Formatter):
    """Emit compact structured logs without request bodies."""

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(
                record.getMessage()
            ),
        }

        event = getattr(
            record,
            "event",
            None,
        )
        if event:
            payload["event"] = str(event)

        if record.exc_info:
            payload["exception"] = redact_secrets(
                self.formatException(
                    record.exc_info
                )
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def configure_logging(
    settings: JoeySettings,
) -> None:
    """Configure one reusable console handler for Joey-owned loggers."""

    logger = logging.getLogger(
        "hey_joey"
    )
    logger.setLevel(
        settings.log_level
    )
    logger.propagate = False

    for handler in list(
        logger.handlers
    ):
        if getattr(
            handler,
            "name",
            None,
        ) == _HANDLER_NAME:
            logger.removeHandler(
                handler
            )

    handler = logging.StreamHandler()
    handler.name = _HANDLER_NAME
    handler.setLevel(
        settings.log_level
    )

    if settings.log_format == "json":
        formatter: logging.Formatter = JoeyJsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    handler.setFormatter(
        formatter
    )
    logger.addHandler(
        handler
    )
