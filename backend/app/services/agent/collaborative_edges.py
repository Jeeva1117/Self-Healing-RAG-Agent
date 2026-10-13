"""Conditional routing edges for Phase 16 Multi-Agent Collaboration."""

from app.services.agent.state import MultiAgentRAGState


def route_after_query_understanding(state: MultiAgentRAGState) -> str:
    """Routes to direct clarification on ambiguity or proceeds to scope authorization."""
    if state.get("is_ambiguous", False):
        return "ambiguous"
    return "proceed"


def route_after_scope_authorization(state: MultiAgentRAGState) -> str:
    """Routes to supervisor finalization on unauthorized KB, or proceeds to planning."""
    if not state.get("is_authorized", False):
        return "unauthorized"
    return "authorized"


def route_after_verification(state: MultiAgentRAGState) -> str:
    """Routes to bounded retrieval retry or proceeds to grounded answer generation."""
    recommendation = state.get("verification_recommendation", "proceed")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 1)

    if recommendation == "retry_retrieval" and retry_count < max_retries:
        return "retry"

    return "generate"
