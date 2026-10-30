"""Production-grade Grounded Chat Service orchestrating hybrid retrieval, synthesis, and citation provenance."""

from uuid import UUID

from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProviderInterface
from app.infrastructure.llm.factory import get_llm_provider
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)
from app.services.retrieval.retrieval_service import RetrievalService
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Max characters budget for context injection (~3000 tokens)
MAX_CONTEXT_CHARACTERS = 14000


class ChatService:
    """Production-grade grounded RAG chat service with claim-level citation auditing."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService | None = None,
        llm_provider: LLMProviderInterface | None = None,
    ):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.retrieval_service = retrieval_service or RetrievalService(session)
        self.llm = llm_provider or get_llm_provider()

    def _build_context(
        self,
        retrieved_results: list,
    ) -> tuple[str, bool]:
        """Constructs an untrusted context prompt with budget limits and truncation flags."""
        evidence_blocks: list[str] = []
        current_chars = 0
        truncated = False

        for idx, item in enumerate(retrieved_results, start=1):
            meta_parts = [f"Document: {item.document_name}"]
            if item.page_number:
                meta_parts.append(f"Page: {item.page_number}")
            if item.section_title:
                meta_parts.append(f"Section: {item.section_title}")
            meta_str = ", ".join(meta_parts)

            # Untrusted evidence container
            block = f"[Evidence {idx}] ({meta_str})\n{item.content}"
            if current_chars + len(block) > MAX_CONTEXT_CHARACTERS and evidence_blocks:
                truncated = True
                break

            evidence_blocks.append(block)
            current_chars += len(block)

        context_text = "\n\n".join(evidence_blocks)
        return context_text, truncated

    async def send_message(
        self,
        request: ChatRequest,
        user_id: UUID,
    ) -> ChatResponse:
        """Executes full agentic grounded RAG generation pipeline via LangGraph orchestration."""
        from app.services.agent.graph import AgenticRAGOrchestrator

        orchestrator = AgenticRAGOrchestrator(
            session=self.session,
            retrieval_service=self.retrieval_service,
            llm_provider=self.llm,
        )
        return await orchestrator.run(request=request, user_id=user_id)
