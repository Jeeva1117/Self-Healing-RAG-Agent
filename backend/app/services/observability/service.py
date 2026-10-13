"""Persistence, retrieval, and metric aggregation service for Phase 11 Observability."""

from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.models import ExecutionTrace, KnowledgeBase, TraceSpanRecord
from app.services.observability.alerting import alert_manager
from app.services.observability.exporter import telemetry_exporter
from app.services.observability.metrics import MetricsCalculator
from app.services.observability.schemas import (
    AlertRecord,
    ChunkScoreProvenance,
    OverviewStats,
    ReliabilityMetrics,
    SpanRecord,
    TraceRecord,
)
from app.services.observability.taxonomy import ErrorClassifier

logger = get_logger("app.observability.service")


class ObservabilityService:
    """Manages execution trace persistence, querying, cost attribution, and reliability intelligence."""

    # In-memory circular buffer for fast metrics computation and zero-downtime fallback
    _recent_traces: deque[TraceRecord] = deque(maxlen=200)

    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    @classmethod
    def record_to_buffer(cls, trace: TraceRecord) -> None:
        """Records a trace to the in-memory circular buffer."""
        cls._recent_traces.append(trace)

    @classmethod
    def get_buffered_traces(cls) -> list[TraceRecord]:
        """Returns all traces in the active memory buffer."""
        return list(cls._recent_traces)

    @classmethod
    def clear_buffer(cls) -> None:
        """Clears the in-memory buffer (useful in tests)."""
        cls._recent_traces.clear()

    async def record_trace(self, trace: TraceRecord) -> None:
        """Persists a completed TraceRecord to buffer, database, and optional exporter with fault isolation."""
        # 1. Always record in memory buffer
        self.record_to_buffer(trace)

        # 2. Safely dispatch to external exporter (OpenTelemetry / LangSmith) if configured
        try:
            await telemetry_exporter.export_trace(trace)
        except Exception as exp_err:
            logger.warning("Telemetry exporter error (isolated): %s", exp_err)

        # 3. Persist to database if session is present and not currently flushing, isolated from caller
        sync_sess = getattr(self.session, "sync_session", None)
        is_flushing = (
            getattr(self.session, "_flushing", False)
            or (sync_sess is not None and getattr(sync_sess, "_flushing", False))
        )
        if self.session and not is_flushing:
            try:
                async with self.session.begin_nested():
                    # Resolve valid knowledge_base_id and guard against FK violation on non-existent KBs
                    kb_id = UUID(trace.knowledge_base_id) if trace.knowledge_base_id else None
                    if kb_id:
                        kb_row = await self.session.get(KnowledgeBase, kb_id)
                        if not kb_row:
                            # Non-existent or unauthorized KB: store in metadata to prevent FK violation
                            trace.metadata = trace.metadata or {}
                            trace.metadata["requested_knowledge_base_id"] = str(kb_id)
                            kb_id = None

                    retrieval_scores_data = None
                    if trace.retrieval_scores:
                        retrieval_scores_data = [s.model_dump() for s in trace.retrieval_scores]

                    db_trace = ExecutionTrace(
                        trace_id=trace.trace_id,
                        request_id=trace.request_id,
                        user_id=UUID(trace.user_id) if trace.user_id else None,
                        knowledge_base_id=kb_id,
                        query=trace.query,
                        status=trace.status,
                        duration_ms=trace.duration_ms,
                        tokens_total=trace.tokens_total,
                        prompt_tokens=trace.prompt_tokens,
                        completion_tokens=trace.completion_tokens,
                        model=trace.model,
                        estimated_cost_usd=trace.estimated_cost_usd,
                        cost_status=trace.cost_status,
                        cost_currency=trace.cost_currency,
                        pricing_source=trace.pricing_source,
                        error_category=trace.error_category,
                        recovery_count=trace.recovery_count,
                        retrieval_method=trace.retrieval_method,
                        retrieval_scores=retrieval_scores_data,
                        evidence_sufficiency=trace.evidence_sufficiency,
                        citation_validation_passed=trace.citation_validation_passed,
                        verification_status=trace.verification_status,
                        trace_metadata=trace.metadata,
                    )
                    self.session.add(db_trace)

                    for sp in trace.spans:
                        db_span = TraceSpanRecord(
                            trace_id=trace.trace_id,
                            span_id=sp.span_id,
                            parent_span_id=sp.parent_span_id,
                            name=sp.name,
                            step_type=sp.step_type,
                            duration_ms=sp.duration_ms,
                            status=sp.status,
                            inputs=sp.inputs,
                            outputs=sp.outputs,
                            error_code=sp.error_code,
                            error_message=sp.error_message,
                            prompt_tokens=sp.prompt_tokens,
                            completion_tokens=sp.completion_tokens,
                            estimated_cost_usd=sp.estimated_cost_usd,
                            is_skipped=sp.is_skipped,
                            span_metadata=sp.metadata,
                        )
                        self.session.add(db_span)

                    await self.session.flush()
            except Exception as e:
                logger.warning("Failed to persist execution trace to database (non-blocking): %s", e)

    async def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        model: str | None = None,
        search: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[TraceRecord], int]:
        """Queries execution traces with pagination, search, status, and model filtering."""
        if self.session:
            try:
                query = select(ExecutionTrace)
                if user_id:
                    query = query.where(ExecutionTrace.user_id == user_id)
                if status and status.lower() != "all":
                    query = query.where(ExecutionTrace.status == status.lower())
                if model and model.lower() != "all":
                    query = query.where(ExecutionTrace.model.ilike(f"%{model}%"))
                if search:
                    query = query.where(
                        (ExecutionTrace.trace_id.ilike(f"%{search}%"))
                        | (ExecutionTrace.query.ilike(f"%{search}%"))
                    )

                query = query.order_by(desc(ExecutionTrace.created_at)).offset(offset).limit(limit)
                result = await self.session.execute(query)
                rows = result.scalars().all()

                traces: list[TraceRecord] = []
                for r in rows:
                    scores = []
                    if r.retrieval_scores and isinstance(r.retrieval_scores, list):
                        scores = [ChunkScoreProvenance(**sc) for sc in r.retrieval_scores if isinstance(sc, dict)]

                    traces.append(
                        TraceRecord(
                            trace_id=r.trace_id,
                            request_id=r.request_id,
                            user_id=str(r.user_id) if r.user_id else None,
                            knowledge_base_id=str(r.knowledge_base_id) if r.knowledge_base_id else None,
                            query=r.query,
                            status=r.status,
                            start_time=r.created_at.timestamp() if r.created_at else 0.0,
                            end_time=(r.created_at.timestamp() + (r.duration_ms / 1000.0)) if r.created_at else 0.0,
                            duration_ms=r.duration_ms,
                            tokens_total=r.tokens_total,
                            prompt_tokens=r.prompt_tokens,
                            completion_tokens=r.completion_tokens,
                            model=r.model,
                            estimated_cost_usd=r.estimated_cost_usd,
                            cost_status=r.cost_status or "unavailable",
                            cost_currency=r.cost_currency or "USD",
                            pricing_source=r.pricing_source,
                            error_category=r.error_category,
                            recovery_count=r.recovery_count,
                            retrieval_method=r.retrieval_method,
                            retrieval_scores=scores,
                            evidence_sufficiency=r.evidence_sufficiency,
                            citation_validation_passed=r.citation_validation_passed,
                            verification_status=r.verification_status,
                            created_at=r.created_at.isoformat() if r.created_at else datetime.now(UTC).isoformat(),
                            spans=[
                                SpanRecord(
                                    span_id=s.span_id,
                                    parent_span_id=s.parent_span_id,
                                    trace_id=s.trace_id,
                                    name=s.name,
                                    step_type=s.step_type,
                                    status=s.status,
                                    start_time=s.created_at.timestamp() if s.created_at else 0.0,
                                    end_time=(s.created_at.timestamp() + (s.duration_ms / 1000.0)) if s.created_at else 0.0,
                                    duration_ms=s.duration_ms,
                                    inputs=s.inputs or {},
                                    outputs=s.outputs or {},
                                    error_code=s.error_code,
                                    error_message=s.error_message,
                                    prompt_tokens=s.prompt_tokens,
                                    completion_tokens=s.completion_tokens,
                                    estimated_cost_usd=s.estimated_cost_usd,
                                    is_skipped=s.is_skipped or False,
                                    metadata=s.span_metadata or {},
                                )
                                for s in r.spans
                            ],
                            metadata=r.trace_metadata or {},
                        )
                    )
                return traces, len(traces)
            except Exception as e:
                logger.warning("Database error reading execution traces, falling back to buffer: %s", e)

        # Fallback to buffer
        buffer_traces = list(self._recent_traces)
        if user_id:
            buffer_traces = [t for t in buffer_traces if t.user_id == str(user_id)]
        if status and status.lower() != "all":
            buffer_traces = [t for t in buffer_traces if t.status.lower() == status.lower()]
        if model and model.lower() != "all":
            buffer_traces = [t for t in buffer_traces if model.lower() in t.model.lower()]
        if search:
            s_low = search.lower()
            buffer_traces = [t for t in buffer_traces if s_low in t.trace_id.lower() or s_low in t.query.lower()]

        total = len(buffer_traces)
        paginated = buffer_traces[offset : offset + limit]
        return paginated, total

    async def get_trace(self, trace_id: str, user_id: UUID | None = None) -> TraceRecord | None:
        """Retrieves a single TraceRecord with spans, enforcing tenant/user boundaries."""
        if self.session:
            try:
                stmt = select(ExecutionTrace).where(ExecutionTrace.trace_id == trace_id)
                if user_id:
                    stmt = stmt.where(ExecutionTrace.user_id == user_id)
                res = await self.session.execute(stmt)
                r = res.scalar_one_or_none()
                if r:
                    scores = []
                    if r.retrieval_scores and isinstance(r.retrieval_scores, list):
                        scores = [ChunkScoreProvenance(**sc) for sc in r.retrieval_scores if isinstance(sc, dict)]

                    return TraceRecord(
                        trace_id=r.trace_id,
                        request_id=r.request_id,
                        user_id=str(r.user_id) if r.user_id else None,
                        knowledge_base_id=str(r.knowledge_base_id) if r.knowledge_base_id else None,
                        query=r.query,
                        status=r.status,
                        start_time=r.created_at.timestamp() if r.created_at else 0.0,
                        end_time=(r.created_at.timestamp() + (r.duration_ms / 1000.0)) if r.created_at else 0.0,
                        duration_ms=r.duration_ms,
                        tokens_total=r.tokens_total,
                        prompt_tokens=r.prompt_tokens,
                        completion_tokens=r.completion_tokens,
                        model=r.model,
                        estimated_cost_usd=r.estimated_cost_usd,
                        cost_status=r.cost_status or "unavailable",
                        cost_currency=r.cost_currency or "USD",
                        pricing_source=r.pricing_source,
                        error_category=r.error_category,
                        recovery_count=r.recovery_count,
                        retrieval_method=r.retrieval_method,
                        retrieval_scores=scores,
                        evidence_sufficiency=r.evidence_sufficiency,
                        citation_validation_passed=r.citation_validation_passed,
                        verification_status=r.verification_status,
                        created_at=r.created_at.isoformat() if r.created_at else datetime.now(UTC).isoformat(),
                        spans=[
                            SpanRecord(
                                span_id=s.span_id,
                                parent_span_id=s.parent_span_id,
                                trace_id=s.trace_id,
                                name=s.name,
                                step_type=s.step_type,
                                status=s.status,
                                start_time=s.created_at.timestamp() if s.created_at else 0.0,
                                end_time=(s.created_at.timestamp() + (s.duration_ms / 1000.0)) if s.created_at else 0.0,
                                duration_ms=s.duration_ms,
                                inputs=s.inputs or {},
                                outputs=s.outputs or {},
                                error_code=s.error_code,
                                error_message=s.error_message,
                                prompt_tokens=s.prompt_tokens,
                                completion_tokens=s.completion_tokens,
                                estimated_cost_usd=s.estimated_cost_usd,
                                is_skipped=s.is_skipped or False,
                                metadata=s.span_metadata or {},
                            )
                            for s in r.spans
                        ],
                        metadata=r.trace_metadata or {},
                    )
            except Exception as e:
                logger.warning("Database error fetching trace %s: %s", trace_id, e)

        # Fallback to buffer
        for t in self._recent_traces:
            if t.trace_id == trace_id:
                if user_id and t.user_id and t.user_id != str(user_id):
                    return None
                return t
        return None

    async def get_metrics(self, user_id: UUID | None = None) -> ReliabilityMetrics:
        """Computes live reliability metrics across recorded execution traces."""
        traces, _ = await self.list_traces(limit=200, user_id=user_id)
        if not traces:
            traces = [t for t in self._recent_traces if not user_id or t.user_id == str(user_id)]

        return MetricsCalculator.calculate(traces)

    async def get_overview(self, user_id: UUID | None = None) -> OverviewStats:
        """Aggregates high-level production intelligence KPIs and token spend analytics."""
        traces, _ = await self.list_traces(limit=200, user_id=user_id)
        if not traces:
            traces = [t for t in self._recent_traces if not user_id or t.user_id == str(user_id)]

        total = len(traces)
        if total == 0:
            return OverviewStats()

        succ = 0
        failed = 0
        rec = 0
        tot_tok = 0
        prompt_tok = 0
        comp_tok = 0
        tot_cost = 0.0
        has_cost = False

        models_map: dict[str, int] = {}
        retrieval_map: dict[str, int] = {}
        durations: list[float] = []
        total_recovery_attempts = 0

        for t in traces:
            st = t.status.lower()
            if st in ("completed", "success"):
                succ += 1
            elif st == "recovered":
                rec += 1
                succ += 1
            else:
                failed += 1

            durations.append(t.duration_ms)
            tot_tok += t.tokens_total
            if t.prompt_tokens:
                prompt_tok += t.prompt_tokens
            if t.completion_tokens:
                comp_tok += t.completion_tokens

            if t.estimated_cost_usd is not None:
                tot_cost += t.estimated_cost_usd
                has_cost = True

            m = t.model or "default"
            models_map[m] = models_map.get(m, 0) + 1

            rm = t.retrieval_method or "hybrid"
            retrieval_map[rm] = retrieval_map.get(rm, 0) + 1

            total_recovery_attempts += t.recovery_count

        durations.sort()
        from app.services.observability.metrics import compute_percentile

        p50 = compute_percentile(durations, 50.0) if len(durations) >= 3 else None
        p95 = compute_percentile(durations, 95.0) if len(durations) >= 3 else None
        p99 = compute_percentile(durations, 99.0) if len(durations) >= 3 else None
        avg_lat = round(sum(durations) / len(durations), 2) if durations else None

        avg_cost = round(tot_cost / total, 6) if (has_cost and total > 0) else None

        return OverviewStats(
            total_requests=total,
            successful_requests=succ,
            failed_requests=failed,
            recovered_requests=rec,
            success_rate=round(succ / total, 4) if total > 0 else 0.0,
            error_rate=round(failed / total, 4) if total > 0 else 0.0,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            avg_latency_ms=avg_lat,
            total_tokens=tot_tok,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            total_estimated_cost_usd=round(tot_cost, 6) if has_cost else None,
            avg_cost_per_query_usd=avg_cost,
            cost_status="estimated" if has_cost else "unavailable",
            cost_currency="USD",
            models_used=models_map,
            retrieval_methods_used=retrieval_map,
            recovery_attempts=total_recovery_attempts,
            recovery_success_count=rec,
        )

    async def get_error_explorer(
        self,
        limit: int = 50,
        user_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Extracts and classifies all failed or recovery-diverted requests with safe debugging suggestions."""
        traces, _ = await self.list_traces(limit=200, user_id=user_id)
        if not traces:
            traces = [t for t in self._recent_traces if not user_id or t.user_id == str(user_id)]

        error_traces = [t for t in traces if t.status in ("failed", "recovered") or t.error_category]
        error_items = []

        for t in error_traces[:limit]:
            diag = ErrorClassifier.classify(
                error=t.error_category or "Execution failure",
                stage="rag_pipeline",
                retry_attempted=t.recovery_count > 0,
                recovery_succeeded=t.status == "recovered",
            )
            error_items.append({
                "trace_id": t.trace_id,
                "query": t.query,
                "created_at": t.created_at,
                "duration_ms": t.duration_ms,
                "error_category": diag.category.value,
                "safe_code": diag.safe_code,
                "diagnostic_summary": diag.diagnostic_summary,
                "affected_stage": diag.affected_stage,
                "is_retryable": diag.is_infrastructure_failure or diag.category.value == "citation_validation_failure",
                "recovery_succeeded": diag.recovery_succeeded,
                "suggested_action": diag.suggested_action,
                "is_infrastructure_failure": diag.is_infrastructure_failure,
            })

        return error_items

    async def get_alerts(self, user_id: UUID | None = None) -> list[AlertRecord]:
        """Evaluates active metrics against threshold rules and returns current alerts."""
        metrics = await self.get_metrics(user_id=user_id)
        return alert_manager.evaluate(metrics)
