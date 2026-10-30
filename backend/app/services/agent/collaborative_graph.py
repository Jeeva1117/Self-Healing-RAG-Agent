"""Multi-Agent StateGraph assembly and orchestrator for Phase 16."""

import time
import uuid
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProviderInterface
from app.infrastructure.llm.factory import get_llm_provider
from app.schemas.chat import ChatRequest, ChatResponse, ChatResponseStatus
from app.services.agent.collaborative_edges import (
    route_after_query_understanding,
    route_after_scope_authorization,
    route_after_verification,
)
from app.services.agent.collaborative_nodes import CollaborativeAgentNodes
from app.services.agent.state import MultiAgentRAGState
from app.services.observability.service import ObservabilityService
from app.services.observability.tracer import Tracer
from app.services.retrieval.retrieval_service import RetrievalService
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def build_collaborative_rag_graph(nodes: CollaborativeAgentNodes) -> CompiledStateGraph:
    """Builds and compiles the production Multi-Agent Collaborative LangGraph workflow."""
    workflow = StateGraph(MultiAgentRAGState)

    # 1. Register Specialized Agent Nodes
    workflow.add_node("query_understanding", nodes.query_understanding_node)
    workflow.add_node("scope_authorization", nodes.scope_authorization_node)
    workflow.add_node("planning", nodes.planning_node)
    workflow.add_node("retrieval_agent", nodes.retrieval_agent_node)
    workflow.add_node("evidence_analysis", nodes.evidence_analysis_node)
    workflow.add_node("verification_agent", nodes.verification_agent_node)
    workflow.add_node("response_generation", nodes.response_generation_node)
    workflow.add_node("supervisor", nodes.supervisor_coordinator_node)

    # 2. Add Conditional Routing & Edges
    workflow.add_edge(START, "query_understanding")

    # Agent 1 -> Ambiguity guard
    workflow.add_conditional_edges(
        "query_understanding",
        route_after_query_understanding,
        {
            "ambiguous": "response_generation",
            "proceed": "scope_authorization",
        },
    )

    # Tenant boundary guard
    workflow.add_conditional_edges(
        "scope_authorization",
        route_after_scope_authorization,
        {
            "unauthorized": "supervisor",
            "authorized": "planning",
        },
    )

    # Agent 2 (Planning) -> Agent 3 (Retrieval) -> Agent 4 (Analysis) -> Agent 5 (Verification)
    workflow.add_edge("planning", "retrieval_agent")
    workflow.add_edge("retrieval_agent", "evidence_analysis")
    workflow.add_edge("evidence_analysis", "verification_agent")

    # Agent 5 (Verification) -> Bounded retrieval retry or Agent 6 (Generation)
    workflow.add_conditional_edges(
        "verification_agent",
        route_after_verification,
        {
            "retry": "planning",
            "generate": "response_generation",
        },
    )

    # Agent 6 (Generation) -> Agent 7 (Supervisor) -> END
    workflow.add_edge("response_generation", "supervisor")
    workflow.add_edge("supervisor", END)

    return workflow.compile()


class CollaborativeAgentOrchestrator:
    """Orchestrates multi-agent collaboration across the specialized LangGraph roles."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        retrieval_service: RetrievalService | None = None,
        llm_provider: LLMProviderInterface | None = None,
        *,
        db_session: AsyncSession | None = None,
        llm: LLMProviderInterface | None = None,
    ):
        actual_session = session or db_session
        if actual_session is None:
            raise ValueError("session or db_session must be provided to CollaborativeAgentOrchestrator")
        self.session = actual_session
        self.retrieval_service = retrieval_service or RetrievalService(actual_session)
        self.llm_provider = llm_provider or llm or get_llm_provider()
        self.nodes = CollaborativeAgentNodes(
            session=self.session,
            retrieval_service=self.retrieval_service,
            llm_provider=self.llm_provider,
        )
        self.graph = build_collaborative_rag_graph(self.nodes)

    async def run(
        self,
        request: ChatRequest,
        user_id: UUID,
        max_retries: int | None = None,
        deadline: float | None = None,
    ) -> ChatResponse:
        """Executes the typed, collaborative multi-agent LangGraph workflow."""
        t_start = time.perf_counter()
        effective_max_retries = max_retries if max_retries is not None else 1
        effective_deadline = deadline if deadline is not None else (time.time() + settings.RECOVERY_TIMEOUT_SECONDS)

        # 1. Initialize distributed trace
        trace = Tracer.start_trace(
            query=request.prompt,
            user_id=str(user_id),
            knowledge_base_id=str(request.knowledge_base_id) if request.knowledge_base_id else None,
        )

        # Gateway span
        Tracer.record_manual_span(
            name="Multi-Agent Gateway & Routing Init",
            step_type="gateway",
            duration_ms=1.2,
            inputs={"knowledge_base_id": str(request.knowledge_base_id) if request.knowledge_base_id else None},
            outputs={"trace_id": trace.trace_id, "mode": "multi_agent_collaboration"},
        )

        initial_state: MultiAgentRAGState = {
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

        # 2. Invoke Collaborative LangGraph StateGraph
        final_state = await self.graph.ainvoke(
            initial_state,
            config={"recursion_limit": 25},
        )
        total_ms = (time.perf_counter() - t_start) * 1000.0

        # If authorization failed, record telemetry and raise AppError
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
            resp = ChatResponse(
                content="An unexpected workflow state occurred during multi-agent collaboration.",
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

        # Completion span
        Tracer.record_manual_span(
            name="Multi-Agent Completion & Assembly",
            step_type="completion",
            duration_ms=1.0,
            outputs={"status": resp.status.value, "total_ms": resp.total_ms},
        )

        finished_trace = Tracer.finish_trace(
            status="completed" if resp.status == ChatResponseStatus.ANSWERED else "recovered",
            tokens_total=resp.tokens_used or 0,
            model=resp.model or "collaborative-multi-agent",
            recovery_count=resp.retry_count or 0,
            verification_status=resp.verification_status,
        )
        if finished_trace:
            try:
                await ObservabilityService(self.session).record_trace(finished_trace)
            except Exception as e:
                logger.warning("Telemetry save error: %s", e)

        return resp
