"""Main application factory and entry point for Self-Healing RAG Agent backend."""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_v1_router
from app.core.config import settings
from app.core.errors import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.infrastructure.cache.redis_client import redis_service

# Initialize root structured logging
setup_logging(level=settings.LOG_LEVEL, service_name=settings.APP_NAME)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle startup and shutdown events."""
    # Startup
    app.state.start_time = time.time()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in [{settings.APP_ENV}] mode",
        extra={"environment": settings.APP_ENV, "version": settings.APP_VERSION},
    )

    yield

    # Shutdown
    logger.info("Shutting down application resources...")
    await redis_service.close()
    logger.info("Application shutdown complete.")


def create_application() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title="Self-Healing RAG Agent API",
        description=(
            "Production-grade foundation for the Self-Healing RAG Agent platform. "
            "Supports hybrid retrieval, LangGraph workflows, verification, self-healing, and observability."
        ),
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # Global Middlewares (Execution order is bottom-to-top of declaration)
    # 1. Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # 3. Request ID & Audit Logging Middleware
    app.add_middleware(RequestIdMiddleware)

    # Global Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Mount API v1 router
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
