"""Administrator-only API endpoints requiring ADMIN role."""

from datetime import UTC, datetime

from app.api.deps import require_admin
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AdminUserListResponse, UserResponse
from app.schemas.common import ApiResponse, MetaInfo
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.get(
    "/users",
    response_model=ApiResponse[AdminUserListResponse],
    summary="List all users with administrative details",
)
async def list_all_users(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[AdminUserListResponse]:
    """Retrieves paginated list of users. Strictly requires ADMIN role."""
    user_repo = UserRepository(session)
    users, total = await user_repo.list_paginated(skip=skip, limit=limit)

    return ApiResponse(
        success=True,
        data=AdminUserListResponse(
            users=[UserResponse.model_validate(u) for u in users],
            total=total,
        ),
        meta=_create_meta(request),
    )
