"""Document status, chunk viewing, deletion, and reprocessing API routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    Request,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import AsyncSessionLocal, get_db_session
from app.schemas.common import ApiResponse, MetaInfo
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentResponse,
    ReprocessResponse,
)
from app.services.ingestion_service import IngestionService

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Document Lifecycle"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


async def _run_background_reprocess(doc_id: UUID, user_id: UUID):
    """Executes asynchronous reprocessing inside isolated session."""
    async with AsyncSessionLocal() as session:
        try:
            ingestion = IngestionService(session)
            await ingestion.reprocess_document(doc_id, user_id)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Reprocessing failed for %s: %s", doc_id, e, exc_info=True)


@router.get(
    "/{id}",
    response_model=ApiResponse[DocumentResponse],
    summary="Get document details, status, and chunk count",
)
async def get_document(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DocumentResponse]:
    ingestion = IngestionService(session)
    result = await ingestion.get_document(id, current_user.id)
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.get(
    "/{id}/download",
    summary="Download original uploaded document file enforcing ownership",
)
async def download_document(
    id: UUID,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    ingestion = IngestionService(session)
    file_bytes, filename, content_type = await ingestion.get_document_file(id, current_user.id)
    return Response(
        content=file_bytes,
        media_type=content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{id}/chunks",
    response_model=ApiResponse[DocumentChunkListResponse],
    summary="Get chunks for a specific document with citation metadata",
)
async def get_document_chunks(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ApiResponse[DocumentChunkListResponse]:

    ingestion = IngestionService(session)
    items, total = await ingestion.get_document_chunks(
        document_id=id, user_id=current_user.id, offset=offset, limit=limit
    )
    return ApiResponse(
        success=True,
        data=DocumentChunkListResponse(items=items, total=total, limit=limit, offset=offset),
        meta=_create_meta(request),
    )


@router.delete(
    "/{id}",
    response_model=ApiResponse[dict[str, str]],
    summary="Delete document and clean up physical storage and vector chunks",
)
async def delete_document(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict[str, str]]:
    ingestion = IngestionService(session)
    await ingestion.delete_document(id, current_user.id)
    return ApiResponse(
        success=True,
        data={"message": "Document and associated chunks successfully deleted."},
        meta=_create_meta(request),
    )


@router.post(
    "/{id}/reprocess",
    response_model=ApiResponse[ReprocessResponse],
    summary="Reprocess a document, rebuilding chunks and embeddings",
)
async def reprocess_document(
    id: UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ReprocessResponse]:
    ingestion = IngestionService(session)
    # Validate document exists and belongs to user first
    doc = await ingestion.get_document(id, current_user.id)

    # Trigger reprocessing pipeline
    background_tasks.add_task(_run_background_reprocess, id, current_user.id)

    return ApiResponse(
        success=True,
        data=ReprocessResponse(
            document_id=doc.id,
            status=doc.status,
            message="Document reprocessing initiated.",
        ),
        meta=_create_meta(request),
    )
