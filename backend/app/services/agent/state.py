"""LangGraph state schema for Phase 7 production-grade agentic RAG orchestration."""

from typing import Any, TypedDict
from uuid import UUID

from app.schemas.chat import (
    ChatCitation,
    ChatResponse,
    ChatResponseStatus,
    ClaimCitation,
    SourceItem,
    WorkflowStepEvent,
)
from app.schemas.retrieval import RetrievalLatencyBreakdown, RetrievalResultItem


class AgenticRAGState(TypedDict, total=False):
    """Explicit, serializable state passed between LangGraph nodes."""

    # Identity and Scope
    request_id: str
    user_id: UUID
    knowledge_base_id: UUID
    conversation_id: str | None

    # Query Analysis
    original_query: str
    normalized_query: str
    is_ambiguous: bool
    ambiguity_reason: str | None
    is_topic_listing: bool
    is_policy_or_internal_query: bool
    extracted_terms: list[str]

    # Authorization & Scope Validation
    is_authorized: bool
    auth_error: str | None

    # Retrieval Strategy & Execution
    retrieval_strategy: str  # "hybrid", "dense", "lexical"
    strategy_reason: str
    candidate_limit: int
    top_k: int
    enable_reranking: bool
    retrieval_results: list[RetrievalResultItem]
    retrieval_latency: RetrievalLatencyBreakdown | None

    # Evidence Assessment & Hybrid Answer Routing
    evidence_status: str  # "sufficient", "insufficient", "low_relevance", "conflicting", "retrieval_error"
    evidence_reason: str
    answer_mode: str  # "grounded", "general", "insufficient_evidence", "mixed"
    has_relevant_evidence: bool
    llm_invoked: bool
    answer_type: str  # "document_grounded", "general_ai", "insufficient_evidence", "provider_error"

    # Bounded Retry & Phase 8 Self-Healing Recovery
    retry_count: int
    max_retries: int
    deadline: float
    current_query: str
    query_history: list[str]
    action_history: list[str]
    failure_category: str | None
    failure_reason: str | None
    recovery_action: str | None
    recovery_count: int
    max_recovery_attempts: int
    recovery_history: list[dict[str, Any]]
    verification_passed: bool
    verification_feedback: str | None
    is_recovered: bool
    recovery_meta: dict[str, Any] | None

    # Grounded Answer Generation & Citation Validation
    raw_answer: str
    sanitized_answer: str
    sources: list[SourceItem]
    claim_citations: list[ClaimCitation]
    active_citations: list[ChatCitation]
    citation_validation_passed: bool
    used_source_count: int
    is_context_truncated: bool
    is_insufficient_evidence: bool

    # Execution Telemetry & Final Response
    execution_status: ChatResponseStatus
    error_message: str | None
    generation_provider: str
    generation_model: str
    generation_ms: float
    total_ms: float
    tokens_used: int | None
    workflow_steps: list[WorkflowStepEvent]
    final_response: ChatResponse | None


class MultiAgentRAGState(AgenticRAGState, total=False):
    """Extended state schema for Phase 16 Multi-Agent Collaboration."""

    # 1. Query Understanding Agent Output
    query_intent: str
    query_entities: list[str]
    expected_answer_type: str
    clarification_recommended: bool

    # 2. Planning Agent Output
    task_plan: dict[str, Any]  # Serialized TaskPlan
    current_subtask_index: int

    # 3. Retrieval Agent Output
    subtask_results: list[dict[str, Any]]
    evidence_coverage_ratio: float
    missing_evidence_details: list[str]

    # 4. Research and Evidence Analysis Agent Output
    agent_findings: list[dict[str, Any]]  # Serialized AgentFinding items
    detected_contradictions: list[str]

    # 5. Verification Agent Output
    verification_audit: dict[str, Any]  # Serialized VerificationAudit
    verification_recommendation: str

    # 6. Workflow Supervisor Output
    supervisor_decision: str
    supervisor_step_count: int
    collaboration_meta: dict[str, Any]  # Serialized CollaborationMeta
    citations: list[ChatCitation]
