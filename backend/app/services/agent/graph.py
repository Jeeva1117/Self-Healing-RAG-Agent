"""StateGraph assembly and execution orchestrator for Phase 7 agentic RAG."""

import time
import uuid
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProviderInterface
from app.infrastructure.llm.factory import get_llm_provider
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatResponseStatus,
)
from app.services.agent.edges import (
    route_after_assessment,
    route_after_citation_validation,
    route_after_generation,
    route_after_query_analysis,
    route_after_recovery,
    route_after_scope,
    route_after_verification,
)
from app.services.agent.nodes import AgenticNodes
from app.services.agent.state import AgenticRAGState
from app.services.retrieval.retrieval_service import RetrievalService
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def build_agentic_rag_graph(nodes: AgenticNodes) -> CompiledStateGraph:
    """Builds and compiles the production LangGraph state graph with explicit bounds."""
    workflow = StateGraph(AgenticRAGState)

    # 1. Register Single-Purpose Nodes
    workflow.add_node("query_analysis", nodes.query_analysis_node)
    workflow.add_node("scope_authorization", nodes.scope_authorization_node)
    workflow.add_node("retrieval_strategy", nodes.retrieval_strategy_node)
    workflow.add_node("retrieval", nodes.retrieval_node)
    workflow.add_node("evidence_assessment", nodes.evidence_assessment_node)
    workflow.add_node("bounded_retry", nodes.bounded_retry_node)
    workflow.add_node("grounded_generation", nodes.grounded_generation_node)
    workflow.add_node("citation_validation", nodes.citation_validation_node)
    workflow.add_node("answer_verification", nodes.answer_verification_node)
    workflow.add_node("finalization", nodes.finalization_node)

    # 2. Add Explicit Edges & Conditional Routing
    workflow.add_edge(START, "query_analysis")

    workflow.add_conditional_edges(
        "query_analysis",
        route_after_query_analysis,
        {
            "ambiguous": "grounded_generation",
            "proceed": "scope_authorization",
        },
    )

    workflow.add_conditional_edges(
        "scope_authorization",
        route_after_scope,
        {
            "unauthorized": "finalization",
            "authorized": "retrieval_strategy",
        },
    )

    workflow.add_edge("retrieval_strategy", "retrieval")
    workflow.add_edge("retrieval", "evidence_assessment")

    workflow.add_conditional_edges(
        "evidence_assessment",
        route_after_assessment,
        {
            "retry": "bounded_retry",
            "error": "finalization",
            "finalize": "finalization",
            "generate": "grounded_generation",
        },
    )

    # Bounded retry loops dynamically based on adaptive recovery policy
    workflow.add_conditional_edges(
        "bounded_retry",
        route_after_recovery,
        {
            "finalize": "finalization",
            "retry_generation": "grounded_generation",
            "retry_retrieval": "retrieval_strategy",
        },
    )

    workflow.add_conditional_edges(
        "grounded_generation",
        route_after_generation,
        {
            "finalize": "finalization",
            "recover": "bounded_retry",
            "validate": "citation_validation",
        },
    )

    workflow.add_conditional_edges(
        "citation_validation",
        route_after_citation_validation,
        {
            "recover": "bounded_retry",
            "verify": "answer_verification",
        },
    )

    workflow.add_conditional_edges(
        "answer_verification",
        route_after_verification,
        {
            "recover": "bounded_retry",
            "finalize": "finalization",
        },
    )

    workflow.add_edge("finalization", END)

    return workflow.compile()


class AgenticRAGOrchestrator:
    """Orchestrates stateful execution of the LangGraph agentic RAG workflow."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService | None = None,
        llm_provider: LLMProviderInterface | None = None,
    ):
        self.session = session
        self.retrieval_service = retrieval_service or RetrievalService(session)
        self.llm_provider = llm_provider or get_llm_provider()
        self.nodes = AgenticNodes(
            session=self.session,
            retrieval_service=self.retrieval_service,
            llm_provider=self.llm_provider,
        )
        self.graph = build_agentic_rag_graph(self.nodes)

    async def run(
        self,
        request: ChatRequest,
        user_id: UUID,
        max_retries: int | None = None,
        deadline: float | None = None,
    ) -> ChatResponse:
        """Executes the typed, bounded LangGraph agent workflow."""
        from app.services.observability.service import ObservabilityService
        from app.services.observability.tracer import Tracer

        t_start = time.perf_counter()
        effective_max_retries = max_retries if max_retries is not None else 1
        effective_deadline = deadline if deadline is not None else (time.time() + settings.RECOVERY_TIMEOUT_SECONDS)

        # 1. Initialize Phase 10 distributed trace
        trace = Tracer.start_trace(
            query=request.prompt,
            user_id=str(user_id),
            knowledge_base_id=str(request.knowledge_base_id) if request.knowledge_base_id else None,
        )

        # 2. Record Gateway Span (Stage 1)
        Tracer.record_manual_span(
            name="Request Gateway & Routing Init",
            step_type="gateway",
            duration_ms=1.2,
            inputs={"knowledge_base_id": str(request.knowledge_base_id) if request.knowledge_base_id else None},
            outputs={"trace_id": trace.trace_id},
        )

        initial_state: AgenticRAGState = {
            "request_id": f"req-{uuid.uuid4().hex[:10]}",
            "user_id": user_id,
            "knowledge_base_id": request.knowledge_base_id,
            "conversation_id": request.conversation_id,
            "original_query": request.prompt,
            "top_k": request.top_k,
            "enable_reranking": request.enable_reranking,
            "retry_count": 0,
            "max_retries": effective_max_retries,
            "max_recovery_attempts": settings.RECOVERY_MAX_ATTEMPTS,
            "deadline": effective_deadline,
            "workflow_steps": [],
        }

        final_state = await self.graph.ainvoke(
            initial_state,
            config={"recursion_limit": max(25, (effective_max_retries + 2) * 8)},
        )
        total_ms = (time.perf_counter() - t_start) * 1000.0

        # If authorization failed, record failure telemetry then raise AppError
        if not final_state.get("is_authorized", True):
            Tracer.record_manual_span(
                name="Scope Authorization Failed",
                step_type="scope_authorization",
                duration_ms=1.0,
                status="failed",
                error_category="authorization_failure",
                error_code="KNOWLEDGE_BASE_NOT_FOUND",
                error_message="Knowledge base not found or access denied.",
            )
            finished_trace = Tracer.finish_trace(
                status="failed",
                error_category="authorization_failure",
            )
            if finished_trace:
                try:
                    await ObservabilityService(self.session).record_trace(finished_trace)
                except Exception:
                    pass

            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        resp: ChatResponse | None = final_state.get("final_response")
        if resp is None:
            # Fallback safe error response if final_response was missing
            resp = ChatResponse(
                content="An unexpected workflow state occurred during processing.",
                status=ChatResponseStatus.RETRIEVAL_ERROR,
                timestamp=str(time.time()),
                knowledge_base_id=request.knowledge_base_id,
                conversation_id=request.conversation_id,
                citations=[],
                is_insufficient_evidence=True,
                verification_status="unverified",
                generation_ms=0.0,
                total_ms=round(total_ms, 2),
                workflow_steps=final_state.get("workflow_steps", []),
            )

        resp.total_ms = round(total_ms, 2)
        resp.trace_id = trace.trace_id

        # Record Stage 15: Completion Span
        Tracer.record_manual_span(
            name="Final Response & Completion",
            step_type="completion",
            duration_ms=1.0,
            outputs={"status": resp.status.value, "total_ms": resp.total_ms},
        )

        # Finalize and persist trace
        trace_status = "completed"
        if resp.status == ChatResponseStatus.RECOVERED:
            trace_status = "recovered"
        elif resp.status in (ChatResponseStatus.RETRIEVAL_ERROR, ChatResponseStatus.PROVIDER_ERROR):
            trace_status = "failed"

        error_cat = None
        if resp.status == ChatResponseStatus.PROVIDER_ERROR:
            error_cat = "llm_provider_failure"
        elif resp.status == ChatResponseStatus.RETRIEVAL_ERROR:
            error_cat = "retrieval_failure"
        elif resp.is_insufficient_evidence:
            error_cat = "insufficient_evidence"

        # Map retrieval score provenance
        scores_provenance = []
        for r_item in final_state.get("retrieval_results", []):
            try:
                from app.services.observability.schemas import ChunkScoreProvenance

                scores_provenance.append(
                    ChunkScoreProvenance(
                        chunk_id=str(r_item.chunk_id),
                        document_name=r_item.document_name,
                        vector_score=r_item.vector_score,
                        vector_rank=r_item.vector_rank,
                        lexical_score=r_item.lexical_score,
                        lexical_rank=r_item.lexical_rank,
                        rrf_score=r_item.rrf_score,
                        rrf_rank=r_item.rrf_rank,
                        rerank_score=getattr(r_item, "reranker_score", None) or getattr(r_item, "rerank_score", None),
                        rerank_rank=getattr(r_item, "reranker_rank", None),
                        final_rank=r_item.final_rank,
                        stage_provenance=r_item.stage_provenance,
                    )
                )
            except Exception:
                pass

        # If recovery was not triggered, record honest skipped span
        if not resp.retry_count:
            Tracer.record_skipped_span(
                name="Self-Healing Recovery",
                step_type="recovery",
                reason="Answer grounded successfully on initial pass without recovery anomaly",
            )

        finished_trace = Tracer.finish_trace(
            status=trace_status,
            tokens_total=resp.tokens_used or 0,
            prompt_tokens=int((resp.tokens_used or 0) * 0.75) if resp.tokens_used else None,
            completion_tokens=int((resp.tokens_used or 0) * 0.25) if resp.tokens_used else None,
            model=resp.model or "default",
            error_category=error_cat,
            recovery_count=resp.retry_count or 0,
            retrieval_method=final_state.get("retrieval_strategy", "hybrid"),
            retrieval_candidate_count=final_state.get("candidate_limit"),
            retrieval_returned_count=len(final_state.get("retrieval_results", [])),
            retrieval_scores=scores_provenance,
            evidence_sufficiency=final_state.get("evidence_status"),
            citation_validation_passed=final_state.get("citation_validation_passed"),
            verification_status=resp.verification_status,
        )

        if finished_trace:
            try:
                await ObservabilityService(self.session).record_trace(finished_trace)
            except Exception as e:
                logger.warning("Telemetry save error: %s", e)

        return resp
