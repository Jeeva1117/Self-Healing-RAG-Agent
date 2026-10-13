"""Asynchronous database engine, session factory, and connectivity checking."""

import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.infrastructure.database")

# Create Async Engine
engine_kwargs: dict[str, Any] = {
    "echo": settings.DB_ECHO,
}

if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_pre_ping": True,
            "connect_args": {
                "command_timeout": 30.0,
            },
        }
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a managed AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> dict[str, Any]:
    """Tests connectivity to PostgreSQL and checks for pgvector extension presence."""
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            # Test connectivity
            await conn.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Check pgvector extension availability if PostgreSQL
            pgvector_available = False
            if "postgresql" in settings.DATABASE_URL:
                try:
                    res = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                    pgvector_available = res.scalar() is not None
                except Exception:
                    pgvector_available = False

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "pgvector_extension": pgvector_available,
            }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning(f"Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": latency_ms,
            "error": str(e),
        }
