"""Conditional routing edges for Phase 7 & 8 agentic RAG and self-healing recovery."""

from app.services.agent.state import AgenticRAGState
from app.services.recovery.models import FailureCategory, RecoveryAction


def route_after_query_analysis(state: AgenticRAGState) -> str:
    """Routes to clarification if query is ambiguous, otherwise proceeds to authorization."""
    if state.get("is_ambiguous", False):
        return "ambiguous"
    return "proceed"


def route_after_scope(state: AgenticRAGState) -> str:
    """Routes to safe finalization if unauthorized, otherwise proceeds to strategy selection."""
    if not state.get("is_authorized", False):
        return "unauthorized"
    return "authorized"


def route_after_assessment(state: AgenticRAGState) -> str:
    """Routes to self-healing recovery, error handling, or answer generation based on evidence."""
    evidence_status = state.get("evidence_status", "insufficient")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)
    answer_mode = state.get("answer_mode", "grounded")

    if evidence_status == "retrieval_error":
        if retry_count < max_retries:
            return "retry"
        return "error"

    if evidence_status in ("insufficient", "low_relevance"):
        if retry_count < max_retries:
            # Check if policy previously terminated insufficient evidence
            if state.get("recovery_action") == RecoveryAction.TERMINATE_INSUFFICIENT.value:
                return "finalize"
            return "retry"

        # When retries are exhausted, general AI inquiries route to generation
        if answer_mode == "general":
            return "generate"
        return "finalize"

    return "generate"


def route_after_recovery(state: AgenticRAGState) -> str:
    """Routes from recovery node to appropriate retry point or safe finalization."""
    action = state.get("recovery_action")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)
    failure_cat = state.get("failure_category")

    if action in (
        RecoveryAction.TERMINATE_INSUFFICIENT.value,
        RecoveryAction.TERMINATE_NON_RECOVERABLE.value,
    ) or retry_count > max_retries:
        return "finalize"

    if action in (
        RecoveryAction.REGENERATE_WITH_FEEDBACK.value,
        RecoveryAction.REPAIR_CITATIONS.value,
    ):
        return "retry_generation"

    if action == RecoveryAction.RETRY_TRANSIENT.value:
        if failure_cat == FailureCategory.GENERATION_FAILURE.value:
            return "retry_generation"
        return "retry_retrieval"

    # Default retrieval-related recovery actions (REWRITE_QUERY, EXPAND_RETRIEVAL, FALLBACK_STRATEGY)
    return "retry_retrieval"


def route_after_generation(state: AgenticRAGState) -> str:
    """Routes to citation validation, recovery on provider failure, or direct finalization."""
    if state.get("is_ambiguous", False) or state.get("is_insufficient_evidence", False):
        return "finalize"

    exec_status = state.get("execution_status")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)

    if exec_status in ("provider_error", "retrieval_error"):
        if retry_count < max_retries:
            return "recover"
        return "finalize"

    return "validate"


def route_after_citation_validation(state: AgenticRAGState) -> str:
    """Routes to answer verification or self-healing citation repair."""
    validation_passed = state.get("citation_validation_passed", True)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)

    if not validation_passed and retry_count < max_retries:
        return "recover"

    return "verify"


def route_after_verification(state: AgenticRAGState) -> str:
    """Routes to finalization on successful verification or self-healing on audit warning."""
    verification_passed = state.get("verification_passed", True)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)

    if not verification_passed and retry_count < max_retries:
        return "recover"

    return "finalize"
