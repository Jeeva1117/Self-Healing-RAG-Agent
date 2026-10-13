"""Health check API endpoints."""

from fastapi import APIRouter, Depends, Request

from app.schemas.health import HealthResponse, LivenessResponse, ReadinessResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["Health"])


def get_health_service(request: Request) -> HealthService:
    start_time = getattr(request.app.state, "start_time", 0.0)
    return HealthService(start_time=start_time)


@router.get("", response_model=HealthResponse, summary="Basic health status")
async def health(
    health_svc: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """Returns basic health confirmation of the service."""
    return health_svc.get_basic_health()


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def liveness(
    health_svc: HealthService = Depends(get_health_service),
) -> LivenessResponse:
    """Kubernetes / container liveness probe."""
    return health_svc.get_liveness()


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(
    health_svc: HealthService = Depends(get_health_service),
) -> ReadinessResponse:
    """Kubernetes / container readiness probe checking downstream dependencies."""
    return await health_svc.get_readiness()
