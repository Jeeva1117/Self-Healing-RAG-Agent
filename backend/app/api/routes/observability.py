"""API endpoints for Phase 10 Observability, Distributed Tracing, and Reliability Intelligence."""

from datetime import UTC, datetime
from typing import Annotated, Any

from app.api.deps import require_authenticated_user
from app.core.logging import get_logger
from app.infrastructure.database.models import User, UserRole
from app.infrastructure.database.session import get_db_session
from app.schemas.common import ApiResponse, MetaInfo
from app.services.health_service import HealthService
from app.services.observability.cost import CostIntelligenceEngine
from app.services.observability.schemas import (
    AlertRecord,
    OverviewStats,
    ReliabilityMetrics,
    TraceRecord,
)
from app.services.observability.service import ObservabilityService
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.api.observability")

router = APIRouter(prefix="/observability", tags=["Observability & Distributed Traces (Phase 10 & 11)"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.get(
    "/traces",
    response_model=ApiResponse[dict[str, Any]],
    summary="List distributed request execution traces with filtering and pagination",
)
async def list_execution_traces(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    status: str | None = Query(default=None, description="Filter by status: completed, failed, recovered"),
    search: str | None = Query(default=None, description="Search term for query or trace_id"),
) -> ApiResponse[dict[str, Any]]:
    """Retrieves execution traces scoped to the current user (or all if admin)."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    traces, total = await obs_service.list_traces(
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        user_id=user_scope,
    )

    data = {
        "items": [t.model_dump() for t in traces],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    return ApiResponse(success=True, data=data, meta=_create_meta(request))


@router.get(
    "/traces/{trace_id}",
    response_model=ApiResponse[TraceRecord],
    summary="Retrieve a single trace with complete span waterfall and operational metadata",
)
async def get_execution_trace(
    trace_id: str,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[TraceRecord]:
    """Retrieves full details for a trace including nested spans and redacted parameters."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    trace = await obs_service.get_trace(trace_id=trace_id, user_id=user_scope)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace record not found or access denied.")

    return ApiResponse(success=True, data=trace, meta=_create_meta(request))


@router.get(
    "/metrics",
    response_model=ApiResponse[ReliabilityMetrics],
    summary="Retrieve live runtime reliability metrics, latency percentiles, and stage breakdowns",
)
async def get_reliability_metrics(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ReliabilityMetrics]:
    """Calculates P50, P95, P99 latency percentiles and error rates from authentic execution traces."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    metrics = await obs_service.get_metrics(user_id=user_scope)
    return ApiResponse(success=True, data=metrics, meta=_create_meta(request))


@router.get(
    "/alerts",
    response_model=ApiResponse[list[AlertRecord]],
    summary="List active reliability alerts and threshold evaluation history",
)
async def get_reliability_alerts(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[list[AlertRecord]]:
    """Evaluates metrics against alert rules and returns active alerts with cooldown deduplication."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    alerts = await obs_service.get_alerts(user_id=user_scope)
    return ApiResponse(success=True, data=alerts, meta=_create_meta(request))


@router.get(
    "/overview",
    response_model=ApiResponse[OverviewStats],
    summary="Phase 11 Overview KPIs: total requests, percentiles, token usage, cost attribution, and recovery rates",
)
async def get_observability_overview(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[OverviewStats]:
    """Computes comprehensive system-wide or tenant-scoped KPIs for the production observability dashboard."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    overview = await obs_service.get_overview(user_id=user_scope)
    return ApiResponse(success=True, data=overview, meta=_create_meta(request))


@router.get(
    "/errors",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="Error Explorer: structured failure taxonomy, root cause analysis, and safe debugging suggestions",
)
async def get_error_explorer(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=200, description="Max error incidents to retrieve"),
) -> ApiResponse[list[dict[str, Any]]]:
    """Returns classified failure incidents with retry status and suggested remediation."""
    obs_service = ObservabilityService(session)
    user_scope = None if current_user.role == UserRole.ADMIN.value else current_user.id

    error_items = await obs_service.get_error_explorer(limit=limit, user_id=user_scope)
    return ApiResponse(success=True, data=error_items, meta=_create_meta(request))


@router.get(
    "/pricing",
    response_model=ApiResponse[list[dict[str, Any]]],
    summary="Model pricing catalog with input/output rates per million tokens and currency metadata",
)
async def get_model_pricing_catalog(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
) -> ApiResponse[list[dict[str, Any]]]:
    """Returns the official pricing catalog used for calculating token cost intelligence."""
    catalog = CostIntelligenceEngine.list_catalog()
    return ApiResponse(success=True, data=catalog, meta=_create_meta(request))


@router.get(
    "/health/ready",
    summary="Detailed readiness health check for downstream dependencies and services",
)
async def get_readiness_check(
    request: Request,
) -> Any:
    """Evaluates readiness of database, vector extensions, and caching dependencies."""
    start_time = getattr(request.app.state, "start_time", 0.0)
    health_svc = HealthService(start_time=start_time)
    readiness = await health_svc.get_readiness()
    return readiness
