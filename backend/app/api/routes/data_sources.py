"""API endpoints for Data Sources and External Connectors."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.schemas.common import ApiResponse, MetaInfo
from app.schemas.data_source import (
    ConnectionTestResponse,
    ConnectorCatalogItem,
    DataSourceCreateRequest,
    DataSourceResponse,
    DataSourceUpdateRequest,
    SourceItemResponse,
    SyncRequest,
    SyncResponse,
)
from app.services.data_source_service import DataSourceService

logger = get_logger(__name__)
router = APIRouter(prefix="/data-sources", tags=["Data Sources & Connectors"])


def _create_meta(
    request: Request,
    total: int | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/catalog",
    response_model=ApiResponse[list[ConnectorCatalogItem]],
    summary="Get connector catalog and status",
)
async def get_connector_catalog(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[list[ConnectorCatalogItem]]:
    """Returns supported connectors metadata, setup guides, and configuration states."""
    service = DataSourceService(session)
    catalog = await service.get_catalog(current_user.id)
    return ApiResponse(data=catalog, meta=_create_meta(request))


@router.get(
    "",
    response_model=ApiResponse[list[DataSourceResponse]],
    summary="List configured data sources",
)
async def list_data_sources(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    source_type: Annotated[str | None, Query(description="Filter by connector type")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[DataSourceResponse]]:
    """Lists all configured external data sources for the current authenticated user."""
    service = DataSourceService(session)
    sources, total = await service.list_data_sources(
        user_id=current_user.id,
        source_type=source_type,
        offset=offset,
        limit=limit,
    )
    meta = _create_meta(request, total=total, offset=offset, limit=limit)
    return ApiResponse(data=sources, meta=meta)


@router.post(
    "",
    response_model=ApiResponse[DataSourceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new data source",
)
async def create_data_source(
    data: DataSourceCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DataSourceResponse]:
    """Creates a new external data source connector configuration."""
    service = DataSourceService(session)
    result = await service.create_data_source(user_id=current_user.id, req=data)
    return ApiResponse(data=result, meta=_create_meta(request))


@router.get(
    "/{source_id}",
    response_model=ApiResponse[DataSourceResponse],
    summary="Get data source details",
)
async def get_data_source(
    source_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DataSourceResponse]:
    """Retrieves configuration and sync status for a data source with credentials masked."""
    service = DataSourceService(session)
    result = await service.get_data_source(source_id=source_id, user_id=current_user.id)
    return ApiResponse(data=result, meta=_create_meta(request))


@router.put(
    "/{source_id}",
    response_model=ApiResponse[DataSourceResponse],
    summary="Update data source configuration",
)
async def update_data_source(
    source_id: UUID,
    data: DataSourceUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DataSourceResponse]:
    """Updates connector settings or target knowledge base for an existing data source."""
    service = DataSourceService(session)
    result = await service.update_data_source(source_id=source_id, user_id=current_user.id, req=data)
    return ApiResponse(data=result, meta=_create_meta(request))


@router.delete(
    "/{source_id}",
    response_model=ApiResponse[dict[str, bool]],
    summary="Disconnect and delete data source",
)
async def delete_data_source(
    source_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict[str, bool]]:
    """Disconnects and removes a configured external data source."""
    service = DataSourceService(session)
    await service.delete_data_source(source_id=source_id, user_id=current_user.id)
    return ApiResponse(data={"success": True}, meta=_create_meta(request))


@router.post(
    "/{source_id}/test",
    response_model=ApiResponse[ConnectionTestResponse],
    summary="Test connector credentials and reachability",
)
async def test_connection(
    source_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ConnectionTestResponse]:
    """Validates external connection, credentials, permissions, and network safety."""
    service = DataSourceService(session)
    result = await service.test_connection(source_id=source_id, user_id=current_user.id)
    return ApiResponse(data=result, meta=_create_meta(request))


@router.get(
    "/{source_id}/items",
    response_model=ApiResponse[list[SourceItemResponse]],
    summary="Browse discoverable source items",
)
async def list_source_items(
    source_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    parent_id: Annotated[str | None, Query(description="Parent directory or repo branch")] = None,
) -> ApiResponse[list[SourceItemResponse]]:
    """Discovers selectable files, repos, tables, or pages available for RAG synchronization."""
    service = DataSourceService(session)
    items = await service.list_source_items(source_id=source_id, user_id=current_user.id, parent_id=parent_id)
    return ApiResponse(data=items, meta=_create_meta(request))


@router.post(
    "/{source_id}/sync",
    response_model=ApiResponse[SyncResponse],
    summary="Synchronize selected items into knowledge base",
)
async def sync_data_source(
    source_id: UUID,
    data: SyncRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[SyncResponse]:
    """Extracts, normalizes, chunks, embeds, and indexes selected data source items into a Knowledge Base."""
    service = DataSourceService(session)
    result = await service.sync_data_source(source_id=source_id, user_id=current_user.id, req=data)
    return ApiResponse(data=result, meta=_create_meta(request))
