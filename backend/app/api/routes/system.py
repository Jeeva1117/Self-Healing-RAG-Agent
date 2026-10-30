"""System metadata API endpoints."""

from app.schemas.system import SystemInfoResponse
from app.services.system_service import system_service
from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/info", response_model=SystemInfoResponse, summary="System information")
async def system_info() -> SystemInfoResponse:
    """Returns runtime version, environment, and feature flags."""
    return system_service.get_info()
