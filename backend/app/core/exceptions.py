"""Compatibility re-exports for application errors and exceptions."""

from app.core.errors import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)

# AppError alias for AppException
AppError = AppException

__all__ = [
    "AppException",
    "AppError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "ServiceUnavailableError",
]
