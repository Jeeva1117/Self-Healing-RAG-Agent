"""Health and readiness evaluation application service."""

import time
from datetime import UTC, datetime

from app.core.config import settings
from app.infrastructure.cache.redis_client import redis_service
from app.infrastructure.database.session import check_database_connection
from app.schemas.health import DependencyHealth, HealthResponse, LivenessResponse, ReadinessResponse


class HealthService:
    """Evaluates runtime service health, process liveness, and downstream readiness."""

    def __init__(self, start_time: float):
        self._start_time = start_time

    def get_basic_health(self) -> HealthResponse:
        """Returns instantaneous service alive confirmation."""
        return HealthResponse(
            status="ok",
            service=settings.APP_NAME,
            version=settings.APP_VERSION,
            timestamp=datetime.now(UTC),
        )

    def get_liveness(self) -> LivenessResponse:
        """Returns process liveness and uptime duration."""
        uptime = round(time.time() - self._start_time, 2)
        return LivenessResponse(
            status="alive",
            service=settings.APP_NAME,
            uptime_seconds=uptime,
        )

    async def get_readiness(self) -> ReadinessResponse:
        """Queries actual database and Redis connectivity to determine system readiness."""
        db_check = await check_database_connection()
        redis_check = (
            await redis_service.check_health()
            if settings.REDIS_ENABLED
            else {
                "status": "disabled",
                "connected": False,
                "latency_ms": 0.0,
            }
        )

        dependencies: dict[str, DependencyHealth] = {
            "database": DependencyHealth(
                status=db_check.get("status", "unhealthy"),
                connected=db_check.get("connected", False),
                latency_ms=db_check.get("latency_ms"),
                details={
                    "pgvector_extension": db_check.get("pgvector_extension", False),
                    "error": db_check.get("error"),
                }
                if db_check.get("error") or db_check.get("pgvector_extension") is not None
                else None,
            ),
            "redis": DependencyHealth(
                status=redis_check.get("status", "unhealthy"),
                connected=redis_check.get("connected", False),
                latency_ms=redis_check.get("latency_ms"),
                details={"error": redis_check.get("error")} if redis_check.get("error") else None,
            ),
        }

        # Overall readiness evaluation
        db_ready = db_check.get("connected", False)
        redis_ready = redis_check.get("connected", False) or not settings.REDIS_ENABLED

        if db_ready and redis_ready:
            status = "ready"
            ready = True
        elif db_ready or redis_ready:
            status = "degraded"
            ready = False
        else:
            status = "not_ready"
            ready = False

        return ReadinessResponse(
            status=status,
            service=settings.APP_NAME,
            ready=ready,
            dependencies=dependencies,
        )
