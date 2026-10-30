"""API endpoints for Phase 6 grounded chat and citation generation."""

from datetime import UTC, datetime
from typing import Annotated

from app.api.deps import require_authenticated_user
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ApiResponse, MetaInfo
from app.services.chat.chat_service import ChatService
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat & Generation (Phase 6)"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.post(
    "",
    response_model=ApiResponse[ChatResponse],
    summary="Execute grounded chat generation scoped to a knowledge base",
)
async def chat_endpoint(
    chat_request: ChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ChatResponse]:
    """Retrieves chunks from the selected Knowledge Base and generates an evidence-grounded answer with citations."""
    chat_service = ChatService(session)
    response_data = await chat_service.send_message(
        request=chat_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))
