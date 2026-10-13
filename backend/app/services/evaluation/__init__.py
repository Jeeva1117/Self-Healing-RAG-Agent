"""Phase 9 Evaluation and Quality Intelligence Engine package exports."""

from app.services.evaluation.dataset import (
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_VERSION,
    PHASE15_DATASET_NAME,
    PHASE15_DATASET_VERSION,
    EvaluationDatasetRegistry,
    get_default_evaluation_dataset,
    get_phase15_evaluation_dataset,
)
from app.services.evaluation.metrics import (
    compute_answer_relevance,
    compute_chunk_coverage,
    compute_citation_validity,
    compute_groundedness,
    compute_key_fact_coverage,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from app.services.evaluation.models import (
    AnswerMetrics,
    BaselineComparison,
    CaseEvaluationResult,
    EvaluationCategory,
    EvaluationTestCase,
    RetrievalMetrics,
    RunEvaluationSummary,
    SelfHealingMetrics,
)
from app.services.evaluation.runner import BaselineComparator, EvaluationRunner

__all__ = [
    "DEFAULT_DATASET_NAME",
    "DEFAULT_DATASET_VERSION",
    "PHASE15_DATASET_NAME",
    "PHASE15_DATASET_VERSION",
    "AnswerMetrics",
    "BaselineComparator",
    "BaselineComparison",
    "CaseEvaluationResult",
    "EvaluationCategory",
    "EvaluationDatasetRegistry",
    "EvaluationRunner",
    "EvaluationTestCase",
    "RetrievalMetrics",
    "RunEvaluationSummary",
    "SelfHealingMetrics",
    "compute_answer_relevance",
    "compute_chunk_coverage",
    "compute_citation_validity",
    "compute_groundedness",
    "compute_key_fact_coverage",
    "compute_ndcg_at_k",
    "compute_precision_at_k",
    "compute_recall_at_k",
    "compute_reciprocal_rank",
    "get_default_evaluation_dataset",
    "get_phase15_evaluation_dataset",
]
