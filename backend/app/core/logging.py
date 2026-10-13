"""Structured logging system with contextvars for request correlation tracing."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables for storing correlation IDs across async tasks
request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_ctx_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_id_ctx_var: ContextVar[str | None] = ContextVar("span_id", default=None)


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON with correlation IDs and redaction."""

    def __init__(self, service_name: str = "self-healing-rag-agent"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Import lazily to avoid circular imports
        from app.services.observability.redaction import redact_sensitive_data

        msg = record.getMessage()
        sanitized_msg = redact_sensitive_data(msg)

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": sanitized_msg,
            "request_id": request_id_ctx_var.get() or getattr(record, "request_id", None),
            "trace_id": trace_id_ctx_var.get() or getattr(record, "trace_id", None),
            "span_id": span_id_ctx_var.get() or getattr(record, "span_id", None),
        }

        # Include route / method info if attached to record
        for attr in ("route", "method", "status_code", "duration_ms", "client_ip", "error_code"):
            if hasattr(record, attr):
                log_data[attr] = redact_sensitive_data(getattr(record, attr))

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO", service_name: str = "self-healing-rag-agent") -> logging.Logger:
    """Configures structured JSON logging for the application root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter(service_name=service_name))
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(JSONFormatter(service_name=service_name))

    # Suppress overly chatty third-party loggers if needed
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger."""
    return logging.getLogger(name)
