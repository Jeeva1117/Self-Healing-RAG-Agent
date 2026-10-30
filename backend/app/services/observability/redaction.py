"""Safe data redaction and sanitization utilities for Phase 10 Observability."""

import re
from typing import Any

SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|token|secret|api_key|apikey|authorization|bearer|cookie|auth_header|private_key|access_token|refresh_token)",
    re.IGNORECASE,
)

BEARER_PATTERN = re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]+)", re.IGNORECASE)
MAX_DOCUMENT_CONTENT_LEN = 250


def redact_sensitive_value(key: str, value: Any) -> Any:
    """Masks sensitive values based on key name or content pattern."""
    if SENSITIVE_KEY_PATTERNS.search(key):
        return "[REDACTED]"

    if isinstance(value, str):
        # Check for inline bearer tokens
        if BEARER_PATTERN.search(value):
            return BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        # Prevent unrestricted document dumps in span inputs/outputs
        if key in ("content", "document_content", "raw_content", "text") and len(value) > MAX_DOCUMENT_CONTENT_LEN:
            return value[:MAX_DOCUMENT_CONTENT_LEN] + " ... [TRUNCATED_FOR_OBSERVABILITY]"

    return value


def redact_sensitive_data(data: Any) -> Any:
    """Recursively traverses dictionaries and lists to sanitize credentials, secrets, and raw dumps."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if SENSITIVE_KEY_PATTERNS.search(str(k)):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict | list):
                sanitized[k] = redact_sensitive_data(v)
            else:
                sanitized[k] = redact_sensitive_value(str(k), v)
        return sanitized
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        if BEARER_PATTERN.search(data):
            return BEARER_PATTERN.sub("Bearer [REDACTED]", data)
        return data
    else:
        return data
