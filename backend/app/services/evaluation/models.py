"""Data models and schemas for Phase 9 Evaluation and Quality Intelligence Engine."""

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class EvaluationCategory(StrEnum):
    """Evaluation test case taxonomy categories."""

    ANSWERABLE = "answerable"
    PRECISE_TOPIC = "precise_topic"
    MULTI_CHUNK = "multi_chunk"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNANSWERABLE = "unanswerable"
    CONTRADICTORY = "contradictory"
    MALFORMED_INPUT = "malformed_input"
    PERMISSION_BOUNDARY = "permission_boundary"
    RECOVERABLE_FAILURE = "recoverable_failure"
    NON_RECOVERABLE_FAILURE = "non_recoverable_failure"
    MULTI_DOCUMENT = "multi_document"
    NUMERICAL_TECHNICAL = "numerical_technical"
    MISLEADING_PREMISE = "misleading_premise"
    IRRELEVANT_RETRIEVAL = "irrelevant_retrieval"


class EvaluationTestCase(BaseModel):
    """Specification of an individual evaluation test scenario."""

    id: str = Field(description="Unique stable identifier for the test case (e.g. tc-ans-01)")
    category: EvaluationCategory = Field(description="Category under evaluation taxonomy")
    query: str = Field(description="User prompt or inquiry under test")
    knowledge_base_id: uuid.UUID | None = Field(default=None, description="Authorized KB scope if applicable")
    expected_document_ids: list[uuid.UUID] = Field(default_factory=list, description="Ground truth relevant doc IDs")
    expected_chunk_ids: list[uuid.UUID] = Field(default_factory=list, description="Ground truth relevant chunk IDs")
    expected_key_facts: list[str] = Field(default_factory=list, description="Key facts required in grounded answer")
    reference_answer: str | None = Field(default=None, description="Gold-standard reference answer")
    is_evidence_expected: bool = Field(default=True, description="True if evidence should exist; False for unanswerable")
    expected_citation_required: bool = Field(default=True, description="Whether citations are required")
    expected_outcome: str = Field(default="answered", description="Expected ChatResponseStatus or recovery outcome")
    difficulty: str = Field(default="medium", description="Difficulty tier: easy, medium, hard, adversarial")
    expected_source_version: int | None = Field(default=None, description="Expected active document version number")
    description: str = Field(default="", description="Human-readable description of what this case verifies")


class RetrievalMetrics(BaseModel):
    """Computed retrieval-quality indicators."""

    precision_at_k: dict[int, float] = Field(default_factory=dict, description="Precision at each evaluated K")
    recall_at_k: dict[int, float] = Field(default_factory=dict, description="Recall at each evaluated K")
    mrr: float = Field(default=0.0, description="Mean Reciprocal Rank")
    ndcg_at_k: dict[int, float] = Field(default_factory=dict, description="Normalized Discounted Cumulative Gain at K")
    chunk_coverage: float = Field(default=0.0, description="Ratio of expected chunks retrieved")
    empty_retrieval: bool = Field(default=False, description="True if 0 candidate chunks returned")
    retrieval_latency_ms: float = Field(default=0.0, description="Measured retrieval pipeline latency")


class AnswerMetrics(BaseModel):
    """Groundedness, citation validity, and factuality evaluation metrics."""

    groundedness_score: float = Field(default=0.0, description="Lexical & structural evidence grounding (0.0 to 1.0)")
    key_fact_coverage: float = Field(default=0.0, description="Fraction of required key facts present in answer")
    citation_validity_score: float = Field(default=0.0, description="Ratio of valid, in-bounds citation IDs")
    claim_support_score: float = Field(default=0.0, description="Ratio of claims supported by cited chunks")
    unsupported_claims_count: int = Field(default=0, description="Number of claims lacking cited chunk support")
    correct_insufficient_handling: bool = Field(default=True, description="Honest limitation when unanswerable")
    relevance_score: float = Field(default=0.0, description="Topical overlap with user question intent")
    completeness_score: float = Field(default=0.0, description="Completeness for multi-part or list questions")


class SelfHealingMetrics(BaseModel):
    """Phase 8 Recovery effectiveness and reliability metrics."""

    recovery_attempted: bool = Field(default=False, description="True if self-healing recovery loop ran")
    recovery_count: int = Field(default=0, description="Number of recovery iterations executed")
    initial_failure_category: str | None = Field(default=None, description="First failure category diagnosed")
    recovery_action: str | None = Field(default=None, description="Recovery action executed")
    recovery_outcome: str | None = Field(default=None, description="Final outcome (e.g. recovered, exhausted)")
    retrieval_improved: bool = Field(default=False, description="True if retry increased candidate recall")
    answer_improved: bool = Field(default=False, description="True if retry satisfied verification")
    recovery_latency_ms: float = Field(default=0.0, description="Latency spent in recovery loops")
    is_budget_exhausted: bool = Field(default=False, description="True if max retry attempts reached")
    cycle_detected: bool = Field(default=False, description="True if cycle protection pivoted action")


class CaseEvaluationResult(BaseModel):
    """Evaluation result for a single test case."""

    test_case_id: str
    category: EvaluationCategory
    passed: bool
    status: str = Field(description="passed, failed, or partial")
    failure_reasons: list[str] = Field(default_factory=list)
    query: str
    retrieval_metrics: RetrievalMetrics
    answer_metrics: AnswerMetrics
    recovery_metrics: SelfHealingMetrics
    actual_response_summary: str = Field(default="")
    total_latency_ms: float = Field(default=0.0)


class RunEvaluationSummary(BaseModel):
    """Aggregated statistics across an evaluation run."""

    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    pass_rate: float = 0.0

    # Retrieval aggregates
    mean_precision_at_k: dict[int, float] = Field(default_factory=dict)
    mean_recall_at_k: dict[int, float] = Field(default_factory=dict)
    mean_mrr: float | None = None
    mean_ndcg_at_k: dict[int, float] = Field(default_factory=dict)
    empty_retrieval_rate: float = 0.0

    # Generation & Grounding aggregates
    mean_groundedness: float | None = None
    mean_fact_coverage: float | None = None
    citation_validity_rate: float | None = None
    claim_support_rate: float | None = None
    insufficient_evidence_accuracy: float | None = None

    # Self-healing aggregates
    recovery_attempt_rate: float = 0.0
    recovery_success_rate: float | None = None
    budget_exhaustion_rate: float = 0.0

    # Performance
    mean_total_latency_ms: float = 0.0


class BaselineComparison(BaseModel):
    """Regression and improvement diff against an earlier compatible run."""

    baseline_run_id: uuid.UUID
    is_compatible: bool = True
    warning: str | None = None
    improvements: dict[str, float] = Field(default_factory=dict, description="Metric changes > +2%")
    regressions: dict[str, float] = Field(default_factory=dict, description="Metric changes < -2%")
    unchanged: dict[str, float] = Field(default_factory=dict, description="Metric changes within +/- 2%")
    missing_metrics: list[str] = Field(default_factory=list, description="Metrics present in one run but not other")
