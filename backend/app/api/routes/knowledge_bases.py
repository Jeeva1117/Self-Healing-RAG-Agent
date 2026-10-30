"""Knowledge Base management and document upload API routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.api.deps import require_authenticated_user
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import AsyncSessionLocal, get_db_session
from app.repositories.repair_job_repository import RepairJobRepository
from app.schemas.common import ApiResponse, MetaInfo
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.knowledge_base import (
    ConflictReport,
    CoverageReport,
    DocumentHealthReport,
    DocumentVersionHistoryResponse,
    DocumentVersionItem,
    DuplicateReport,
    KnowledgeBaseCreate,
    KnowledgeBaseHealthReport,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    RepairActionRequest,
    RepairJobResponse,
)
from app.schemas.retrieval import KBSearchBody, RetrievalRequest, RetrievalResponse
from app.services.ingestion_service import IngestionService
from app.services.knowledge_base import (
    KnowledgeBaseConflictEngine,
    KnowledgeBaseCoverageEngine,
    KnowledgeBaseDuplicateEngine,
    KnowledgeBaseHealthEngine,
    KnowledgeBaseRepairEngine,
    KnowledgeBaseVersioningEngine,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.retrieval.retrieval_service import RetrievalService
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)
router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Base Management"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


async def _run_background_ingestion(doc_id: UUID):
    """Executes asynchronous document ingestion pipeline inside dedicated session context."""
    async with AsyncSessionLocal() as session:
        try:
            ingestion = IngestionService(session)
            await ingestion.run_ingestion_pipeline(doc_id)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Asynchronous document ingestion failed for %s: %s", doc_id, e, exc_info=True)


@router.post(
    "",
    response_model=ApiResponse[KnowledgeBaseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new knowledge base",
)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[KnowledgeBaseResponse]:
    service = KnowledgeBaseService(session)
    result = await service.create_knowledge_base(current_user.id, data)
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.get(
    "",
    response_model=ApiResponse[KnowledgeBaseListResponse],
    summary="List all knowledge bases for the authenticated user",
)
async def list_knowledge_bases(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ApiResponse[KnowledgeBaseListResponse]:
    service = KnowledgeBaseService(session)
    result = await service.list_knowledge_bases(current_user.id, offset=offset, limit=limit)
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.get(
    "/{id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="Get knowledge base details",
)
async def get_knowledge_base(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[KnowledgeBaseResponse]:
    service = KnowledgeBaseService(session)
    result = await service.get_knowledge_base(id, current_user.id)
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.patch(
    "/{id}",
    response_model=ApiResponse[KnowledgeBaseResponse],
    summary="Update knowledge base metadata",
)
async def update_knowledge_base(
    id: UUID,
    data: KnowledgeBaseUpdate,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[KnowledgeBaseResponse]:
    service = KnowledgeBaseService(session)
    result = await service.update_knowledge_base(id, current_user.id, data)
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.delete(
    "/{id}",
    response_model=ApiResponse[dict[str, str]],
    summary="Delete knowledge base and all associated documents and chunks",
)
async def delete_knowledge_base(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict[str, str]]:
    service = KnowledgeBaseService(session)
    await service.delete_knowledge_base(id, current_user.id)
    return ApiResponse(
        success=True,
        data={"message": "Knowledge base and associated resources successfully deleted."},
        meta=_create_meta(request),
    )


@router.post(
    "/{id}/documents",
    response_model=ApiResponse[DocumentResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document to knowledge base and start asynchronous ingestion",
)
async def upload_document(
    id: UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[DocumentResponse]:
    # Bounded stream reading to enforce upload limits and prevent memory exhaustion
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        mb_size = file.size / (1024 * 1024)
        raise AppError(
            code="FILE_TOO_LARGE",
            message=f"File size ({mb_size:.2f}MB) exceeds configured limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            status_code=413,
        )

    buffer = bytearray()
    chunk_size = 1024 * 1024
    while chunk := await file.read(chunk_size):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            mb_size = len(buffer) / (1024 * 1024)
            raise AppError(
                code="FILE_TOO_LARGE",
                message=f"File size ({mb_size:.2f}MB) exceeds configured limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                status_code=413,
            )
    file_bytes = bytes(buffer)
    ingestion = IngestionService(session)

    created_doc = await ingestion.validate_and_create_document(
        kb_id=id,
        user_id=current_user.id,
        filename=file.filename or "unknown_file",
        content_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
    )
    await session.commit()

    # Trigger asynchronous ingestion pipeline via BackgroundTasks
    background_tasks.add_task(_run_background_ingestion, created_doc.id)

    response_data = DocumentResponse(
        id=created_doc.id,
        knowledge_base_id=created_doc.knowledge_base_id,
        owner_id=created_doc.owner_id,
        filename=created_doc.filename,
        original_filename=created_doc.original_filename,
        content_type=created_doc.content_type,
        file_size=created_doc.file_size,
        checksum=created_doc.checksum,
        storage_key=created_doc.storage_key,
        status=created_doc.status,
        ingestion_error=created_doc.ingestion_error,
        created_at=created_doc.created_at,
        updated_at=created_doc.updated_at,
        chunk_count=0,
        active_version=1,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


@router.get(
    "/{id}/documents",
    response_model=ApiResponse[DocumentListResponse],
    summary="List documents for a specific knowledge base",
)
async def list_kb_documents(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> ApiResponse[DocumentListResponse]:
    ingestion = IngestionService(session)
    items, total = await ingestion.list_documents(kb_id=id, user_id=current_user.id, offset=offset, limit=limit)

    return ApiResponse(
        success=True,
        data=DocumentListResponse(items=items, total=total, limit=limit, offset=offset),
        meta=_create_meta(request),
    )


@router.post(
    "/{id}/search",
    response_model=ApiResponse[RetrievalResponse],
    summary="Execute hybrid, semantic vector, or BM25 retrieval scoped to this knowledge base",
)
async def search_knowledge_base_documents(
    id: UUID,
    search_body: KBSearchBody,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[RetrievalResponse]:
    """Retrieves document chunks scoped strictly to the specified authorized knowledge base."""
    retrieval_request = RetrievalRequest(
        knowledge_base_id=id,
        query=search_body.query,
        mode=search_body.mode,
        enable_reranking=search_body.enable_reranking,
        reranking_required=search_body.reranking_required,
        candidate_limit=search_body.candidate_limit,
        top_k=search_body.top_k,
        similarity_threshold=search_body.similarity_threshold,
        rrf_k=search_body.rrf_k,
    )
    retrieval_service = RetrievalService(session)
    response_data = await retrieval_service.search(
        request=retrieval_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


# ==============================================================================
# Phase 12: Health, Duplicates, Versioning, Coverage, Conflicts & Repair Routes
# ==============================================================================


@router.get(
    "/{id}/health",
    response_model=ApiResponse[KnowledgeBaseHealthReport],
    summary="Evaluate comprehensive health and indexing integrity across knowledge base",
)
async def get_knowledge_base_health(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[KnowledgeBaseHealthReport]:
    engine = KnowledgeBaseHealthEngine(session)
    report = await engine.check_knowledge_base_health(id, current_user.id)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.get(
    "/{id}/documents/{document_id}/health",
    response_model=ApiResponse[DocumentHealthReport],
    summary="Evaluate granular health findings for a specific document",
)
async def get_document_health(
    id: UUID,
    document_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DocumentHealthReport]:
    engine = KnowledgeBaseHealthEngine(session)
    report = await engine.check_document_health(document_id, current_user.id)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.get(
    "/{id}/duplicates",
    response_model=ApiResponse[DuplicateReport],
    summary="Detect exact checksum/content duplicates and near-duplicate documents",
)
async def get_knowledge_base_duplicates(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    threshold: float = Query(0.85, ge=0.5, le=1.0, description="Similarity threshold for near-duplicates"),
) -> ApiResponse[DuplicateReport]:
    engine = KnowledgeBaseDuplicateEngine(session)
    report = await engine.detect_duplicates(id, current_user.id, similarity_threshold=threshold)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.get(
    "/{id}/coverage",
    response_model=ApiResponse[CoverageReport],
    summary="Analyze empirical knowledge coverage and evidence sufficiency gaps",
)
async def get_knowledge_base_coverage(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(200, ge=1, le=1000, description="Maximum traces to analyze"),
) -> ApiResponse[CoverageReport]:
    engine = KnowledgeBaseCoverageEngine(session)
    report = await engine.analyze_coverage(id, current_user.id, limit=limit)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.get(
    "/{id}/conflicts",
    response_model=ApiResponse[ConflictReport],
    summary="Identify conservative factual or policy contradictions between documents",
)
async def get_knowledge_base_conflicts(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ConflictReport]:
    engine = KnowledgeBaseConflictEngine(session)
    report = await engine.detect_conflicts(id, current_user.id)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.get(
    "/{id}/documents/{document_id}/versions",
    response_model=ApiResponse[DocumentVersionHistoryResponse],
    summary="List complete version history and chunk counts for a document",
)
async def get_document_version_history(
    id: UUID,
    document_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DocumentVersionHistoryResponse]:
    engine = KnowledgeBaseVersioningEngine(session)
    report = await engine.get_version_history(document_id, current_user.id)
    return ApiResponse(success=True, data=report, meta=_create_meta(request))


@router.post(
    "/{id}/documents/{document_id}/reindex",
    response_model=ApiResponse[DocumentVersionItem],
    summary="Safely reindex a document with zero downtime staging",
)
async def reindex_document(
    id: UUID,
    document_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[DocumentVersionItem]:
    engine = KnowledgeBaseVersioningEngine(session)
    version, count = await engine.reindex_document(document_id, current_user.id)
    item = DocumentVersionItem(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        checksum=version.checksum,
        storage_key=version.storage_key,
        is_active=version.is_active,
        chunk_count=count,
        created_at=version.created_at,
    )
    return ApiResponse(success=True, data=item, meta=_create_meta(request))


@router.post(
    "/{id}/documents/{document_id}/repair",
    response_model=ApiResponse[RepairJobResponse],
    summary="Execute targeted, idempotent repair operation on a document",
)
async def repair_document(
    id: UUID,
    document_id: UUID,
    body: RepairActionRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[RepairJobResponse]:
    engine = KnowledgeBaseRepairEngine(session)
    result = await engine.execute_repair(
        knowledge_base_id=id,
        document_id=document_id,
        user_id=current_user.id,
        action=body.action,
        dry_run=body.dry_run,
    )
    return ApiResponse(success=True, data=result, meta=_create_meta(request))


@router.get(
    "/{id}/repair-jobs/{job_id}",
    response_model=ApiResponse[RepairJobResponse],
    summary="Get status and audit details for a specific repair job",
)
async def get_repair_job(
    id: UUID,
    job_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[RepairJobResponse]:
    repo = RepairJobRepository(session)
    job = await repo.get_by_id_and_owner(job_id, current_user.id)
    if not job or job.knowledge_base_id != id:
        return ApiResponse(
            success=False,
            error={"code": "REPAIR_JOB_NOT_FOUND", "message": "Repair job not found or access denied."},
            meta=_create_meta(request),
        )
    resp = RepairJobResponse(
        job_id=job.id,
        knowledge_base_id=job.knowledge_base_id,
        document_id=job.document_id,
        action=job.action,
        status=job.status,
        dry_run=job.dry_run,
        findings_addressed=job.findings_addressed or [],
        details=job.details or {},
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
    return ApiResponse(success=True, data=resp, meta=_create_meta(request))


@router.get(
    "/{id}/repair-jobs",
    response_model=ApiResponse[list[RepairJobResponse]],
    summary="List recent repair jobs for this knowledge base",
)
async def list_repair_jobs(
    id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[RepairJobResponse]]:
    repo = RepairJobRepository(session)
    jobs, _ = await repo.list_by_kb(id, current_user.id, offset=offset, limit=limit)
    items = [
        RepairJobResponse(
            job_id=j.id,
            knowledge_base_id=j.knowledge_base_id,
            document_id=j.document_id,
            action=j.action,
            status=j.status,
            dry_run=j.dry_run,
            findings_addressed=j.findings_addressed or [],
            details=j.details or {},
            error_message=j.error_message,
            started_at=j.started_at,
            completed_at=j.completed_at,
        )
        for j in jobs
    ]
    return ApiResponse(success=True, data=items, meta=_create_meta(request))
