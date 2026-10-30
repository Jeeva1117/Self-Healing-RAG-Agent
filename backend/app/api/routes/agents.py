"""API endpoints for Phase 7 LangGraph agentic RAG orchestration and workflow studio."""

from datetime import UTC, datetime
from typing import Annotated, Any

from app.api.deps import require_authenticated_user
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ApiResponse, MetaInfo
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents (Phase 7)"])
agents_router = router  # Backward compatibility alias


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


def _verify_langgraph_available() -> None:
    """Verifies that LangGraph is installed and functional."""
    try:
        from langgraph.graph import StateGraph  # noqa: F401
    except (ImportError, Exception) as exc:
        logger.error("LangGraph framework is not available: %s", exc)
        raise AppError(
            code="LANGGRAPH_NOT_CONFIGURED",
            message="LangGraph execution framework is not installed or configured on the server.",
            status_code=503,
        ) from exc


@router.post(
    "/run",
    response_model=ApiResponse[ChatResponse],
    summary="Execute LangGraph state graph workflow scoped to a knowledge base",
)
async def run_agent_workflow(
    run_request: ChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ChatResponse]:
    """Executes the full LangGraph Agentic RAG workflow with stateful routing and node telemetry."""
    _verify_langgraph_available()

    from app.services.agent.graph import AgenticRAGOrchestrator

    orchestrator = AgenticRAGOrchestrator(session=session)
    response_data = await orchestrator.run(
        request=run_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


@router.post(
    "/collaborate",
    response_model=ApiResponse[ChatResponse],
    summary="Execute Phase 16 Multi-Agent Collaborative workflow across specialized roles",
)
async def run_collaborative_workflow(
    run_request: ChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ChatResponse]:
    """Executes the Phase 16 Multi-Agent collaborative workflow with specialized agents."""
    _verify_langgraph_available()

    from app.services.agent.collaborative_graph import CollaborativeAgentOrchestrator

    orchestrator = CollaborativeAgentOrchestrator(session=session)
    response_data = await orchestrator.run(
        request=run_request,
        user_id=current_user.id,
    )
    return ApiResponse(success=True, data=response_data, meta=_create_meta(request))


@router.post(
    "/simulate",
    response_model=ApiResponse[ChatResponse],
    summary="Simulate LangGraph agent workflow execution (alias for /run)",
)
async def simulate_agent_workflow(
    run_request: ChatRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ChatResponse]:
    """Direct alias for /agents/run to execute real LangGraph workflow from Workflow Studio."""
    return await run_agent_workflow(
        run_request=run_request,
        request=request,
        current_user=current_user,
        session=session,
    )


@router.get(
    "/graph",
    summary="Retrieve active LangGraph orchestration graph topology and configuration",
)
async def get_agent_graph_topology(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
) -> ApiResponse[dict[str, Any]]:
    """Returns active LangGraph StateGraph topology, compiled nodes, conditional routing, and limits."""
    _verify_langgraph_available()

    try:
        import importlib.metadata

        langgraph_version = importlib.metadata.version("langgraph")
    except Exception:
        langgraph_version = "available"

    topology = {
        "graph_id": "agentic_rag_v1",
        "framework": "langgraph",
        "framework_version": langgraph_version,
        "status": "ready",
        "recursion_limit": 15,
        "max_retries": 1,
        "nodes": [
            {
                "id": "query_analysis",
                "name": "Query Analysis",
                "role": "Intent evaluation and ambiguity detection",
                "phase": "Phase 7",
            },
            {
                "id": "scope_authorization",
                "name": "Scope & Authorization",
                "role": "Tenant and knowledge base access verification",
                "phase": "Phase 7",
            },
            {
                "id": "retrieval_strategy",
                "name": "Retrieval Strategy Selection",
                "role": "Configures hybrid retrieval depth and candidate limits",
                "phase": "Phase 7",
            },
            {
                "id": "retrieval",
                "name": "Hybrid Evidence Retrieval",
                "role": "Executes dense vector + lexical BM25 + neural reranking",
                "phase": "Phase 5",
            },
            {
                "id": "evidence_assessment",
                "name": "Evidence Assessment",
                "role": "Evaluates candidate chunk sufficiency and topic overlap",
                "phase": "Phase 7",
            },
            {
                "id": "bounded_retry",
                "name": "Bounded Retrieval Retry",
                "role": "Expands recall candidates if evidence is insufficient",
                "phase": "Phase 7",
            },
            {
                "id": "grounded_generation",
                "name": "Grounded Answer Generation",
                "role": "Synthesizes response strictly from retrieved reference material",
                "phase": "Phase 6",
            },
            {
                "id": "citation_validation",
                "name": "Citation & Provenance Auditing",
                "role": "Audits claim citations and strips hallucinated references",
                "phase": "Phase 6",
            },
            {
                "id": "answer_verification",
                "name": "Answer Verification & Grounding Guard",
                "role": "Audits factuality, evidence support, and citation fidelity before final response",
                "phase": "Phase 8",
            },
            {
                "id": "finalization",
                "name": "Workflow Finalization",
                "role": "Compiles structured response with measured telemetry",
                "phase": "Phase 7",
            },
        ],
        "conditional_edges": [
            {
                "from": "query_analysis",
                "condition": "is_ambiguous",
                "branches": ["grounded_generation", "scope_authorization"],
            },
            {
                "from": "scope_authorization",
                "condition": "is_authorized",
                "branches": ["finalization", "retrieval_strategy"],
            },
            {
                "from": "evidence_assessment",
                "condition": "evidence_status",
                "branches": ["bounded_retry", "finalization", "grounded_generation"],
            },
            {
                "from": "bounded_retry",
                "condition": "recovery_action",
                "branches": ["finalization", "grounded_generation", "retrieval_strategy"],
            },
            {
                "from": "grounded_generation",
                "condition": "execution_status",
                "branches": ["finalization", "bounded_retry", "citation_validation"],
            },
            {
                "from": "citation_validation",
                "condition": "citation_validation_passed",
                "branches": ["bounded_retry", "answer_verification"],
            },
            {
                "from": "answer_verification",
                "condition": "verification_passed",
                "branches": ["bounded_retry", "finalization"],
            },
        ],
    }

    return ApiResponse(success=True, data=topology, meta=_create_meta(request))
