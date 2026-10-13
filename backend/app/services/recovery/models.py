"""Domain models and failure taxonomy for Phase 8 Self-Healing Recovery Engine."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FailureCategory(StrEnum):
    """Explicit taxonomy of detectable RAG failure modes."""

    RETRIEVAL_FAILURE = "retrieval_failure"
    LOW_RELEVANCE_EVIDENCE = "low_relevance_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    GENERATION_FAILURE = "generation_failure"
    CITATION_FAILURE = "citation_failure"
    VERIFICATION_FAILURE = "verification_failure"
    NON_RECOVERABLE_FAILURE = "non_recoverable_failure"


class RecoveryAction(StrEnum):
    """Strictly allowlisted adaptive recovery actions."""

    RETRY_TRANSIENT = "retry_transient"
    REWRITE_QUERY = "rewrite_query"
    EXPAND_RETRIEVAL = "expand_retrieval"
    FALLBACK_STRATEGY = "fallback_strategy"
    REPAIR_CITATIONS = "repair_citations"
    REGENERATE_WITH_FEEDBACK = "regenerate_with_feedback"
    TERMINATE_INSUFFICIENT = "terminate_insufficient"
    TERMINATE_NON_RECOVERABLE = "terminate_non_recoverable"


class FailureDiagnosis(BaseModel):
    """Structured diagnosis emitted by failure classification nodes."""

    category: FailureCategory
    reason: str
    is_recoverable: bool
    suggested_action: RecoveryAction
    details: dict[str, Any] = Field(default_factory=dict)


class RecoveryAttemptRecord(BaseModel):
    """Immutable audit record of a single recovery attempt in the self-healing loop."""

    attempt_number: int
    failure_category: FailureCategory
    action_taken: RecoveryAction
    query_before: str
    query_after: str
    strategy_before: str
    strategy_after: str
    candidate_limit: int
    timestamp: str
    details: dict[str, Any] = Field(default_factory=dict)
