"""Privacy-aware logging configuration for Hey Joey services."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.settings import JoeySettings


# Precompiled patterns identify common credential formats so sensitive
# values can be removed before messages or exceptions are written to logs.
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"
    ),
    re.compile(
        r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+"
    ),
)
# Give the application-owned handler a stable name so repeated logging
# configuration can replace it instead of adding duplicate handlers.
_HANDLER_NAME = "hey-joey-console"


def redact_secrets(
    value: object,
) -> str:
    """Redact credential-like values from one log message."""

    # Convert any log value to text before applying the redaction rules.
    text = str(value)

    # Apply every supported credential pattern because one message can
    # contain more than one type of sensitive value.
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
        # Emit a minimal structured payload containing operational metadata
        # rather than full request bodies or other potentially sensitive data.
        payload: dict[str, Any] = {
            # Use timezone-aware UTC timestamps so logs from different
            # environments can be compared consistently.
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            # Redact the rendered log message before it is serialised.
            "message": redact_secrets(
                record.getMessage()
            ),
        }

        # Include the optional structured event field only when a caller has
        # attached one to the LogRecord.
        event = getattr(
            record,
            "event",
            None,
        )
        if event:
            payload["event"] = str(event)

        # Exception text is passed through the same redaction function so
        # credentials are not exposed through stack traces.
        if record.exc_info:
            payload["exception"] = redact_secrets(
                self.formatException(
                    record.exc_info
                )
            )

        # Compact separators keep machine-readable JSON logs small while
        # preserving non-ASCII characters in the original message.
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def configure_logging(
    settings: JoeySettings,
) -> None:
    """Configure one reusable console handler for Joey-owned loggers."""

    # Configure only the application-owned logger namespace rather than
    # changing global/root logging behaviour for third-party libraries.
    logger = logging.getLogger(
        "hey_joey"
    )
    logger.setLevel(
        settings.log_level
    )
    # Prevent Joey log records from also reaching ancestor handlers, which
    # could otherwise duplicate output or bypass this formatter.
    logger.propagate = False

    # Remove any previous Joey console handler so repeated configuration is
    # idempotent and does not duplicate every log message.
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

    # A single console stream handler is shared by Joey-owned loggers.
    handler = logging.StreamHandler()
    handler.name = _HANDLER_NAME
    handler.setLevel(
        settings.log_level
    )

    # Choose structured JSON or human-readable text according to the
    # validated application settings.
    if settings.log_format == "json":
        formatter: logging.Formatter = JoeyJsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    # Attach the selected formatter only after handler level/configuration
    # has been established.
    handler.setFormatter(
        formatter
    )
    # Register the configured handler as the final step so partially
    # configured handlers are never exposed to active logging calls.
    logger.addHandler(
        handler
    )
