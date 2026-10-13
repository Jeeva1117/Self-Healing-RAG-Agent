"""Centralized application exception definitions and error models."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.errors")

HTTP_422_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class AppException(Exception):
    """Base application exception for all domain and service exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "RESOURCE_NOT_FOUND",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ConflictError(AppException):
    def __init__(
        self,
        message: str = "Resource already exists",
        code: str = "RESOURCE_CONFLICT",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=status.HTTP_409_CONFLICT, details=details)


class ValidationError(AppException):
    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=HTTP_422_STATUS, details=details)


class UnauthorizedError(AppException):
    def __init__(
        self,
        message: str = "Authentication required",
        code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class ForbiddenError(AppException):
    def __init__(
        self,
        message: str = "Access denied",
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=status.HTTP_403_FORBIDDEN, details=details)


class ServiceUnavailableError(AppException):
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        code: str = "SERVICE_UNAVAILABLE",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, code=code, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


def format_error_response(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Formats standardized error payload without leaking internal information."""
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    return payload


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handles all custom application exceptions."""
    logger.warning(
        f"AppException: {exc.code} - {exc.message}",
        extra={"error_code": exc.code, "status_code": exc.status_code, "route": request.url.path},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc.code, exc.message, exc.details if exc.details else None),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handles standard Starlette / FastAPI HTTPExceptions."""
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "RESOURCE_NOT_FOUND"
    elif exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 405:
        code = "METHOD_NOT_ALLOWED"

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(code, str(exc.detail)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles request payload validation errors with clean field information."""
    formatted_errors = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", []) if x != "body"])
        formatted_errors.append(
            {
                "field": loc or "body",
                "message": err.get("msg", "Invalid input"),
                "type": err.get("type", "value_error"),
            }
        )

    return JSONResponse(
        status_code=HTTP_422_STATUS,
        content=format_error_response(
            "VALIDATION_ERROR",
            "Request validation failed",
            {"fields": formatted_errors},
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled unexpected exceptions without leaking stack traces or internal secrets."""
    logger.error(
        f"Unhandled exception processing {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
        extra={"route": request.url.path, "method": request.method, "status_code": 500},
    )
    is_dev = settings.DEBUG or settings.effective_environment in ("development", "test")
    msg = (
        f"Internal server error: {str(exc)}"
        if is_dev
        else "An unexpected internal error occurred. Please contact system support."
    )
    details = {"error_type": type(exc).__name__, "detail": str(exc)} if is_dev else None

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            "INTERNAL_SERVER_ERROR",
            msg,
            details,
        ),
    )
