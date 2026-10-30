"""API endpoints for Phase 5 Hybrid Retrieval, Semantic Search, and Neural Reranking."""

from datetime import UTC, datetime
from typing import Annotated

from app.api.deps import require_authenticated_user
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.schemas.common import ApiResponse, MetaInfo
from app.schemas.retrieval import ComparisonResponse, RetrievalRequest, RetrievalResponse
from app.services.retrieval.retrieval_service import RetrievalService
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/retrieval", tags=["Retrieval Engine (Phase 5)"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.post(
    "/search",
    response_model=ApiResponse[RetrievalResponse],
    summary="Execute hybrid, semantic vector, or BM25 lexical retrieval with optional cross-encoder reranking",
)
async def search_documents(
    search_request: RetrievalRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[RetrievalResponse]:
    """Retrieves document chunks using semantic vector search, BM25 keyword search, or RRF hybrid fusion."""
    retrieval_service = RetrievalService(session)
    response_data = await retrieval_service.search(
        request=search_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


@router.post(
    "/compare",
    response_model=ApiResponse[ComparisonResponse],
    summary="Compare Vector, BM25 Lexical, and Hybrid retrieval side-by-side in the Playground",
)
async def compare_retrieval_modes(
    search_request: RetrievalRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ComparisonResponse]:
    """Executes Vector, Lexical, and Hybrid retrieval in parallel and returns side-by-side results."""
    retrieval_service = RetrievalService(session)
    response_data = await retrieval_service.compare(
        request=search_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


search_alias_router = APIRouter(prefix="/search", tags=["Retrieval Engine (Phase 5)"])


@search_alias_router.post(
    "",
    response_model=ApiResponse[RetrievalResponse],
    summary="Alias for /retrieval/search",
)
async def search_alias_endpoint(
    search_request: RetrievalRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[RetrievalResponse]:
    return await search_documents(search_request, request, current_user, session)
