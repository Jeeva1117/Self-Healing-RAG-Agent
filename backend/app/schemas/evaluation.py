"""Pydantic request and response schemas for Phase 9 Evaluation API."""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.services.evaluation.dataset import DEFAULT_DATASET_NAME, DEFAULT_DATASET_VERSION
from app.services.evaluation.models import BaselineComparison, CaseEvaluationResult


class TriggerEvaluationRequest(BaseModel):
    """Payload to trigger an asynchronous or synchronous benchmark run."""

    name: str | None = Field(default=None, description="Optional custom name for this evaluation run")
    dataset_name: str = Field(default=DEFAULT_DATASET_NAME, description="Target dataset name")
    dataset_version: str = Field(default=DEFAULT_DATASET_VERSION, description="Target dataset version")
    knowledge_base_id: uuid.UUID | None = Field(default=None, description="Knowledge base to evaluate against")
    k_values: list[int] = Field(default=[1, 3, 5], description="K ranking evaluation thresholds")
    baseline_run_id: uuid.UUID | None = Field(default=None, description="Optional prior run ID to compare against")


class EvaluationRunListItem(BaseModel):
    """Brief summary item for evaluation run listings."""

    id: uuid.UUID
    name: str
    dataset_name: str
    dataset_version: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    created_at: str
    summary_metrics: dict[str, Any]


class EvaluationRunDetailResponse(BaseModel):
    """Full detail of an evaluation run including all case-level breakdowns."""

    id: uuid.UUID
    name: str
    dataset_name: str
    dataset_version: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    created_at: str
    summary_metrics: dict[str, Any]
    run_config: dict[str, Any] | None = None
    case_results: list[CaseEvaluationResult] = Field(default_factory=list)
    baseline_comparison: BaselineComparison | None = None


class EvaluationDatasetItem(BaseModel):
    """Metadata for registered golden test datasets."""

    name: str
    version: str
    case_count: int
    description: str


class EvaluationSummaryStats(BaseModel):
    """Aggregated quality intelligence scores across recent benchmark runs."""

    total_runs: int = 0
    average_pass_rate: float = 0.0
    average_groundedness: float = 0.0
    average_precision_at_5: float = 0.0
    average_recall_at_5: float = 0.0
    average_mrr: float = 0.0
    recovery_success_rate: float = 0.0
    latest_run_id: uuid.UUID | None = None
