"""API endpoints for Phase 9 RAG Evaluation & Quality Intelligence Engine."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_authenticated_user
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import (
    EvaluationCaseResultRecord,
    EvaluationRun,
    KnowledgeBase,
    User,
)
from app.infrastructure.database.session import get_db_session
from app.schemas.common import ApiResponse, MetaInfo
from app.schemas.evaluation import (
    EvaluationDatasetItem,
    EvaluationRunDetailResponse,
    EvaluationRunListItem,
    EvaluationSummaryStats,
    TriggerEvaluationRequest,
)
from app.services.evaluation.dataset import (
    EvaluationDatasetRegistry,
    get_default_evaluation_dataset,
)
from app.services.evaluation.models import (
    AnswerMetrics,
    BaselineComparison,
    CaseEvaluationResult,
    EvaluationCategory,
    RetrievalMetrics,
    RunEvaluationSummary,
    SelfHealingMetrics,
)
from app.services.evaluation.runner import BaselineComparator, EvaluationRunner

logger = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluation (Phase 9)"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.get(
    "/datasets",
    response_model=ApiResponse[list[EvaluationDatasetItem]],
    summary="List available registered evaluation test datasets",
)
async def list_datasets(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
) -> ApiResponse[list[EvaluationDatasetItem]]:
    """Returns all registered golden evaluation test datasets."""
    raw_datasets = EvaluationDatasetRegistry.list_datasets()
    items = [
        EvaluationDatasetItem(
            name=d["name"],
            version=d["version"],
            case_count=d["case_count"],
            description=d["description"],
        )
        for d in raw_datasets
    ]
    return ApiResponse(
        data=items,
        meta=_create_meta(request),
        message=f"Found {len(items)} evaluation datasets.",
    )


@router.get(
    "/runs",
    response_model=ApiResponse[list[EvaluationRunListItem]],
    summary="List historical evaluation benchmark runs",
)
async def list_evaluation_runs(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[EvaluationRunListItem]]:
    """Lists past evaluation benchmark runs for current user."""
    stmt = (
        select(EvaluationRun)
        .where(EvaluationRun.user_id == current_user.id)
        .order_by(desc(EvaluationRun.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    runs = result.scalars().all()

    items = [
        EvaluationRunListItem(
            id=r.id,
            name=r.name,
            dataset_name=r.dataset_name,
            dataset_version=r.dataset_version,
            status=r.status,
            total_cases=r.total_cases,
            passed_cases=r.passed_cases,
            failed_cases=r.failed_cases,
            pass_rate=r.pass_rate,
            created_at=r.created_at.isoformat() if r.created_at else datetime.now(UTC).isoformat(),
            summary_metrics=r.summary_metrics or {},
        )
        for r in runs
    ]

    return ApiResponse(
        data=items,
        meta=_create_meta(request),
        message=f"Retrieved {len(items)} evaluation runs.",
    )


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[EvaluationRunDetailResponse],
    summary="Get detailed evaluation run results including case breakdowns",
)
async def get_evaluation_run(
    run_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[EvaluationRunDetailResponse]:
    """Retrieves an individual evaluation run with full case-level breakdown."""
    stmt = (
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.case_results))
        .where(EvaluationRun.id == run_id, EvaluationRun.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise AppError(
            code="EVALUATION_RUN_NOT_FOUND",
            message="Evaluation run not found or access denied.",
            status_code=404,
        )

    case_results = [
        CaseEvaluationResult(
            test_case_id=c.test_case_id,
            category=EvaluationCategory(c.category)
            if c.category in EvaluationCategory.__members__.values()
            else EvaluationCategory.ANSWERABLE,
            passed=c.passed,
            status=c.status,
            failure_reasons=c.failure_reasons or [],
            query=c.query,
            retrieval_metrics=RetrievalMetrics(**(c.retrieval_metrics or {})),
            answer_metrics=AnswerMetrics(**(c.answer_metrics or {})),
            recovery_metrics=SelfHealingMetrics(**(c.recovery_metrics or {})),
            actual_response_summary=c.actual_response_summary or "",
            total_latency_ms=c.total_latency_ms,
        )
        for c in run.case_results
    ]

    detail = EvaluationRunDetailResponse(
        id=run.id,
        name=run.name,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        status=run.status,
        total_cases=run.total_cases,
        passed_cases=run.passed_cases,
        failed_cases=run.failed_cases,
        pass_rate=run.pass_rate,
        created_at=run.created_at.isoformat() if run.created_at else datetime.now(UTC).isoformat(),
        summary_metrics=run.summary_metrics or {},
        run_config=run.run_config,
        case_results=case_results,
    )

    return ApiResponse(
        data=detail,
        meta=_create_meta(request),
        message=f"Retrieved evaluation run {run_id}.",
    )


@router.post(
    "/runs",
    response_model=ApiResponse[EvaluationRunDetailResponse],
    summary="Trigger a new evaluation benchmark run",
)
async def trigger_evaluation_run(
    payload: TriggerEvaluationRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[EvaluationRunDetailResponse]:
    """Executes a selected dataset benchmark against the live retrieval and LangGraph pipeline."""
    # 1. Resolve authorized knowledge base scope
    kb_id = payload.knowledge_base_id
    if kb_id:
        kb_stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
        kb_res = await session.execute(kb_stmt)
        kb = kb_res.scalar_one_or_none()
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Target knowledge base not found or access denied.",
                status_code=404,
            )
    else:
        # Resolve user's first available knowledge base
        kb_stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == current_user.id)
            .order_by(KnowledgeBase.created_at)
            .limit(1)
        )
        kb_res = await session.execute(kb_stmt)
        kb = kb_res.scalar_one_or_none()
        kb_id = kb.id if kb else uuid.uuid4()

    # 2. Retrieve test dataset
    cases = EvaluationDatasetRegistry.get(payload.dataset_name, payload.dataset_version)
    if not cases:
        # Fallback to default generated dataset scoped to user KB
        cases = get_default_evaluation_dataset(knowledge_base_id=kb_id)

    # Rebind knowledge_base_id for scoped cases
    configured_cases = []
    for c in cases:
        if c.category in (EvaluationCategory.PERMISSION_BOUNDARY, EvaluationCategory.NON_RECOVERABLE_FAILURE):
            configured_cases.append(c)
        else:
            configured_cases.append(c.model_copy(update={"knowledge_base_id": kb_id}))

    # 3. Execute runner
    runner = EvaluationRunner(session=session)
    summary, case_results = await runner.run_suite(
        cases=configured_cases,
        user_id=current_user.id,
        k_values=payload.k_values,
    )

    # 4. Handle baseline comparison if requested
    baseline_comparison: BaselineComparison | None = None
    if payload.baseline_run_id:
        base_stmt = select(EvaluationRun).where(
            EvaluationRun.id == payload.baseline_run_id,
            EvaluationRun.user_id == current_user.id,
        )
        base_res = await session.execute(base_stmt)
        base_run = base_res.scalar_one_or_none()
        if base_run:
            base_summary = RunEvaluationSummary(**(base_run.summary_metrics or {}))
            baseline_comparison = BaselineComparator.compare(
                candidate=summary,
                baseline=base_summary,
                candidate_meta={"dataset_name": payload.dataset_name, "dataset_version": payload.dataset_version},
                baseline_meta={
                    "id": base_run.id,
                    "dataset_name": base_run.dataset_name,
                    "dataset_version": base_run.dataset_version,
                },
            )

    # 5. Persist run and case results
    run_name = payload.name or f"Benchmark Run {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"
    eval_run = EvaluationRun(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=run_name,
        dataset_name=payload.dataset_name,
        dataset_version=payload.dataset_version,
        status="completed",
        total_cases=summary.total_cases,
        passed_cases=summary.passed_cases,
        failed_cases=summary.failed_cases,
        pass_rate=summary.pass_rate,
        summary_metrics=summary.model_dump(),
        run_config={"k_values": payload.k_values, "kb_id": str(kb_id)},
    )
    session.add(eval_run)
    await session.flush()

    for cr in case_results:
        case_rec = EvaluationCaseResultRecord(
            id=uuid.uuid4(),
            run_id=eval_run.id,
            test_case_id=cr.test_case_id,
            category=cr.category.value,
            passed=cr.passed,
            status=cr.status,
            query=cr.query,
            retrieval_metrics=cr.retrieval_metrics.model_dump(),
            answer_metrics=cr.answer_metrics.model_dump(),
            recovery_metrics=cr.recovery_metrics.model_dump(),
            failure_reasons=cr.failure_reasons,
            total_latency_ms=cr.total_latency_ms,
            actual_response_summary=cr.actual_response_summary,
        )
        session.add(case_rec)

    await session.commit()

    detail = EvaluationRunDetailResponse(
        id=eval_run.id,
        name=eval_run.name,
        dataset_name=eval_run.dataset_name,
        dataset_version=eval_run.dataset_version,
        status=eval_run.status,
        total_cases=eval_run.total_cases,
        passed_cases=eval_run.passed_cases,
        failed_cases=eval_run.failed_cases,
        pass_rate=eval_run.pass_rate,
        created_at=eval_run.created_at.isoformat() if eval_run.created_at else datetime.now(UTC).isoformat(),
        summary_metrics=eval_run.summary_metrics,
        run_config=eval_run.run_config,
        case_results=case_results,
        baseline_comparison=baseline_comparison,
    )

    return ApiResponse(
        data=detail,
        meta=_create_meta(request),
        message=f"Evaluation benchmark completed ({summary.passed_cases}/{summary.total_cases} passed).",
    )


@router.get(
    "/runs/{run_id}/compare/{baseline_run_id}",
    response_model=ApiResponse[BaselineComparison],
    summary="Compare a candidate run against a baseline run",
)
async def compare_runs(
    run_id: uuid.UUID,
    baseline_run_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[BaselineComparison]:
    """Compares candidate run against baseline run and identifies metric improvements/regressions."""
    runs_stmt = select(EvaluationRun).where(
        EvaluationRun.id.in_([run_id, baseline_run_id]),
        EvaluationRun.user_id == current_user.id,
    )
    res = await session.execute(runs_stmt)
    runs = {r.id: r for r in res.scalars().all()}

    if run_id not in runs or baseline_run_id not in runs:
        raise AppError(
            code="EVALUATION_RUN_NOT_FOUND",
            message="One or both evaluation runs were not found.",
            status_code=404,
        )

    cand = runs[run_id]
    base = runs[baseline_run_id]

    cand_summary = RunEvaluationSummary(**(cand.summary_metrics or {}))
    base_summary = RunEvaluationSummary(**(base.summary_metrics or {}))

    comparison = BaselineComparator.compare(
        candidate=cand_summary,
        baseline=base_summary,
        candidate_meta={"id": cand.id, "dataset_name": cand.dataset_name, "dataset_version": cand.dataset_version},
        baseline_meta={"id": base.id, "dataset_name": base.dataset_name, "dataset_version": base.dataset_version},
    )

    return ApiResponse(
        data=comparison,
        meta=_create_meta(request),
        message="Comparison generated successfully.",
    )


@router.get(
    "/metrics/summary",
    response_model=ApiResponse[EvaluationSummaryStats],
    summary="Get aggregated quality intelligence scores across all runs",
)
async def get_metrics_summary(
    request: Request,
    current_user: Annotated[User, Depends(require_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[EvaluationSummaryStats]:
    """Returns average quality intelligence scores across recent benchmark runs."""
    stmt = (
        select(EvaluationRun)
        .where(EvaluationRun.user_id == current_user.id)
        .order_by(desc(EvaluationRun.created_at))
        .limit(10)
    )
    res = await session.execute(stmt)
    runs = res.scalars().all()

    if not runs:
        return ApiResponse(
            data=EvaluationSummaryStats(),
            meta=_create_meta(request),
            message="No historical runs found.",
        )

    total_runs = len(runs)
    avg_pass = sum(r.pass_rate for r in runs) / total_runs

    grounded_scores: list[float] = []
    p5_scores: list[float] = []
    r5_scores: list[float] = []
    mrr_scores: list[float] = []
    rec_scores: list[float] = []

    for r in runs:
        m = r.summary_metrics or {}
        if m.get("mean_groundedness") is not None:
            grounded_scores.append(m["mean_groundedness"])
        if m.get("mean_precision_at_k", {}).get("5") is not None:
            p5_scores.append(m["mean_precision_at_k"]["5"])
        elif m.get("mean_precision_at_k", {}).get(5) is not None:
            p5_scores.append(m["mean_precision_at_k"][5])
        if m.get("mean_recall_at_k", {}).get("5") is not None:
            r5_scores.append(m["mean_recall_at_k"]["5"])
        elif m.get("mean_recall_at_k", {}).get(5) is not None:
            r5_scores.append(m["mean_recall_at_k"][5])
        if m.get("mean_mrr") is not None:
            mrr_scores.append(m["mean_mrr"])
        if m.get("recovery_success_rate") is not None:
            rec_scores.append(m["recovery_success_rate"])

    stats = EvaluationSummaryStats(
        total_runs=total_runs,
        average_pass_rate=round(avg_pass, 4),
        average_groundedness=round(sum(grounded_scores) / len(grounded_scores), 4) if grounded_scores else 0.0,
        average_precision_at_5=round(sum(p5_scores) / len(p5_scores), 4) if p5_scores else 0.0,
        average_recall_at_5=round(sum(r5_scores) / len(r5_scores), 4) if r5_scores else 0.0,
        average_mrr=round(sum(mrr_scores) / len(mrr_scores), 4) if mrr_scores else 0.0,
        recovery_success_rate=round(sum(rec_scores) / len(rec_scores), 4) if rec_scores else 0.0,
        latest_run_id=runs[0].id,
    )

    return ApiResponse(
        data=stats,
        meta=_create_meta(request),
        message="Quality intelligence summary generated.",
    )
