"""Structured logging configuration.

Provides JSON logging for production (parseable by log aggregators)
and human-readable logging for development.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from core.context import get_request_id


class StructuredFormatter(logging.Formatter):
    """JSON formatter for production logging.

    Output format:
        {"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "logger": "api.main",
         "message": "Request processed", "request_id": "abc123"}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request ID if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key in ("user_id", "duration_ms", "status_code", "method", "path"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data, default=str)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for local development.

    Output format:
        2024-01-15 10:30:00 [INFO] api.main: Request processed (req_id=abc123)
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        request_id = get_request_id()
        req_suffix = f" (req_id={request_id})" if request_id else ""

        message = f"{timestamp} [{record.levelname}] {record.name}: {record.getMessage()}{req_suffix}"

        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


def configure_logging(
    level: str = "INFO",
    *,
    structured: bool | None = None,
) -> None:
    """Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        structured: Use JSON format. If None, auto-detect based on environment.
    """
    # Auto-detect: use structured logging if not running in a TTY (production)
    if structured is None:
        structured = not sys.stderr.isatty()

    # Create appropriate formatter
    formatter = StructuredFormatter() if structured else DevelopmentFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stream handler with formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
