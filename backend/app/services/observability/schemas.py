"""Pydantic schemas and data contracts for Phase 11 Observability & Production Intelligence."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCategory(StrEnum):
    """Normalized error classification taxonomy across the entire RAG pipeline."""

    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    INVALID_REQUEST = "invalid_request"
    RETRIEVAL_FAILURE = "retrieval_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    RERANKER_FAILURE = "reranker_failure"
    LLM_PROVIDER_FAILURE = "llm_provider_failure"
    EMBEDDING_PROVIDER_FAILURE = "embedding_provider_failure"
    CITATION_VALIDATION_FAILURE = "citation_validation_failure"
    WORKFLOW_FAILURE = "workflow_failure"
    TIMEOUT = "timeout"
    DATABASE_FAILURE = "database_failure"
    RATE_LIMITING = "rate_limiting"
    RECOVERY_EXHAUSTED = "recovery_exhausted"
    UNEXPECTED_INTERNAL_ERROR = "unexpected_internal_error"


class SpanStatus(StrEnum):
    """Lifecycle execution status of a trace span."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RECOVERED = "recovered"


class ChunkScoreProvenance(BaseModel):
    """Transparent multi-stage retrieval score provenance for an individual candidate chunk."""

    chunk_id: str
    document_name: str
    vector_score: float | None = None
    vector_rank: int | None = None
    lexical_score: float | None = None
    lexical_rank: int | None = None
    rrf_score: float | None = None
    rrf_rank: int | None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    final_rank: int = 1
    stage_provenance: str = "hybrid"


class SpanRecord(BaseModel):
    """A granular execution span within a distributed request trace."""

    span_id: str
    parent_span_id: str | None = None
    trace_id: str
    name: str
    step_type: str
    status: str = SpanStatus.COMPLETED.value
    start_time: float
    end_time: float
    duration_ms: float
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    error_category: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tokens_total: int | None = None
    estimated_cost_usd: float | None = None
    cost_status: str | None = None
    is_skipped: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceRecord(BaseModel):
    """An end-to-end distributed execution trace for a single chat/workflow request."""

    trace_id: str
    request_id: str | None = None
    user_id: str | None = None
    knowledge_base_id: str | None = None
    query: str
    status: str = "completed"
    start_time: float
    end_time: float
    duration_ms: float
    tokens_total: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str = "default"
    estimated_cost_usd: float | None = None
    cost_status: str = "unavailable"
    cost_currency: str = "USD"
    pricing_source: str | None = None
    model_calls_count: int = 1
    error_category: str | None = None
    recovery_count: int = 0
    retrieval_method: str | None = None
    retrieval_candidate_count: int | None = None
    retrieval_returned_count: int | None = None
    retrieval_scores: list[ChunkScoreProvenance] = Field(default_factory=list)
    evidence_sufficiency: str | None = None
    citation_validation_passed: bool | None = None
    verification_status: str | None = None
    created_at: str
    spans: list[SpanRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReliabilityMetrics(BaseModel):
    """Real runtime reliability metrics calculated from authentic execution traces."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    recovered_requests: int = 0
    error_rate: float = 0.0

    avg_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None

    retrieval_latency_ms: float | None = None
    reranking_latency_ms: float | None = None
    generation_latency_ms: float | None = None
    citation_validation_latency_ms: float | None = None
    recovery_latency_ms: float | None = None

    timeout_count: int = 0
    retry_count: int = 0
    insufficient_evidence_count: int = 0
    empty_retrieval_count: int = 0
    citation_validation_failure_count: int = 0

    workflow_completion_rate: float = 0.0
    workflow_failure_rate: float = 0.0

    llm_provider_error_count: int = 0
    embedding_provider_error_count: int = 0
    database_error_count: int = 0

    stage_breakdown: dict[str, float] = Field(default_factory=dict)


class OverviewStats(BaseModel):
    """Production intelligence high-level overview statistics and financial accounting."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    recovered_requests: int = 0
    success_rate: float = 0.0
    error_rate: float = 0.0

    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    avg_latency_ms: float | None = None

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_estimated_cost_usd: float | None = None
    avg_cost_per_query_usd: float | None = None
    cost_status: str = "unavailable"
    cost_currency: str = "USD"

    models_used: dict[str, int] = Field(default_factory=dict)
    retrieval_methods_used: dict[str, int] = Field(default_factory=dict)
    recovery_attempts: int = 0
    recovery_success_count: int = 0


class AlertSeverity(StrEnum):
    """Severity tier for in-app reliability alerts."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertRecord(BaseModel):
    """An active or historical alert event evaluated against runtime metrics."""

    id: str
    name: str
    severity: str = AlertSeverity.WARNING.value
    condition: str
    threshold: float | str
    current_value: float | str
    status: str = "active"  # "active", "cooldown", "resolved"
    triggered_at: str
    message: str
    category: str = "reliability"
