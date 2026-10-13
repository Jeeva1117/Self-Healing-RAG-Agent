"""Core HTTP middleware for Request ID tracing, request timing, and security headers."""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_ctx_var, trace_id_ctx_var

logger = get_logger("app.middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generates or propagates correlation Request ID and Trace ID via standard headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = incoming_request_id if incoming_request_id else str(uuid.uuid4())

        incoming_trace_id = request.headers.get("X-Trace-ID")
        trace_id = incoming_trace_id if incoming_trace_id else f"tr-{uuid.uuid4().hex[:12]}"

        # Set in context variables for logging
        token_req = request_id_ctx_var.set(request_id)
        token_tr = trace_id_ctx_var.set(trace_id)

        # Store in request state for access in route handlers
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Process-Time"] = f"{duration_ms}ms"

            # Log HTTP access
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} - {duration_ms}ms",
                extra={
                    "route": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Exception during request {request.method} {request.url.path} after {duration_ms}ms",
                exc_info=True,
                extra={
                    "route": request.url.path,
                    "method": request.method,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                    "trace_id": trace_id,
                },
            )
            raise
        finally:
            request_id_ctx_var.reset(token_req)
            trace_id_ctx_var.reset(token_tr)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces standard security response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
