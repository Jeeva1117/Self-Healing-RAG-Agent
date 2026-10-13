"""Context-aware distributed request tracer and span collector for Phase 10."""

import contextlib
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger, span_id_ctx_var, trace_id_ctx_var
from app.services.observability.redaction import redact_sensitive_data
from app.services.observability.schemas import SpanRecord, SpanStatus, TraceRecord
from app.services.observability.taxonomy import ErrorClassifier

logger = get_logger("app.observability.tracer")

# Context variables for tracking active trace and current span across async execution
active_trace_ctx: ContextVar[TraceRecord | None] = ContextVar("active_trace_ctx", default=None)
active_span_ctx: ContextVar[str | None] = ContextVar("active_span_ctx", default=None)


class Tracer:
    """Manages distributed request traces, nested spans, latency profiling, and error binding."""

    @classmethod
    def get_current_trace(cls) -> TraceRecord | None:
        """Returns the active trace for the current async task context."""
        return active_trace_ctx.get()

    @classmethod
    def get_current_span_id(cls) -> str | None:
        """Returns the innermost span ID in the current execution stack."""
        return active_span_ctx.get()

    @classmethod
    def start_trace(
        cls,
        query: str,
        request_id: str | None = None,
        user_id: str | None = None,
        knowledge_base_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceRecord:
        """Initializes a new request-level trace and binds correlation context variables."""
        tid = trace_id or f"tr-{uuid.uuid4().hex[:12]}"
        now = time.time()

        trace = TraceRecord(
            trace_id=tid,
            request_id=request_id or tid,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=redact_sensitive_data(query),
            status="in_progress",
            start_time=now,
            end_time=now,
            duration_ms=0.0,
            tokens_total=0,
            model="default",
            created_at=datetime.now(UTC).isoformat(),
            spans=[],
            metadata=redact_sensitive_data(metadata or {}),
        )

        active_trace_ctx.set(trace)
        trace_id_ctx_var.set(tid)
        return trace

    @classmethod
    @contextlib.contextmanager
    def span(
        cls,
        name: str,
        step_type: str,
        inputs: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanRecord, None, None]:
        """Synchronous context manager that instruments an execution span with timing and error classification."""
        current_trace = cls.get_current_trace()
        trace_id = current_trace.trace_id if current_trace else (trace_id_ctx_var.get() or "tr-detached")
        actual_parent = parent_span_id or cls.get_current_span_id()
        span_id = f"sp-{uuid.uuid4().hex[:8]}"

        t_start_perf = time.perf_counter()
        t_start_wall = time.time()

        span_record = SpanRecord(
            span_id=span_id,
            parent_span_id=actual_parent,
            trace_id=trace_id,
            name=name,
            step_type=step_type,
            status=SpanStatus.COMPLETED.value,
            start_time=t_start_wall,
            end_time=t_start_wall,
            duration_ms=0.0,
            inputs=redact_sensitive_data(inputs or {}),
            outputs={},
            metadata=redact_sensitive_data(metadata or {}),
        )

        # Update span context
        token_span = active_span_ctx.set(span_id)
        token_log_span = span_id_ctx_var.set(span_id)

        try:
            yield span_record
            span_record.status = SpanStatus.COMPLETED.value
        except Exception as exc:
            duration = (time.perf_counter() - t_start_perf) * 1000.0
            span_record.duration_ms = round(duration, 2)
            span_record.end_time = time.time()
            span_record.status = SpanStatus.FAILED.value

            classification = ErrorClassifier.classify(exc, stage=step_type)
            span_record.error_category = classification.category.value
            span_record.error_code = classification.safe_code
            span_record.error_message = classification.diagnostic_summary

            if current_trace:
                current_trace.error_category = classification.category.value
                current_trace.spans.append(span_record)
            raise
        else:
            duration = (time.perf_counter() - t_start_perf) * 1000.0
            span_record.duration_ms = round(duration, 2)
            span_record.end_time = time.time()
            # Redact any outputs populated on the record
            span_record.outputs = redact_sensitive_data(span_record.outputs)
            if current_trace:
                current_trace.spans.append(span_record)
        finally:
            active_span_ctx.reset(token_span)
            span_id_ctx_var.reset(token_log_span)

    @classmethod
    @contextlib.asynccontextmanager
    async def async_span(
        cls,
        name: str,
        step_type: str,
        inputs: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[SpanRecord, None]:
        """Asynchronous context manager for measuring async operations with accurate timing."""
        current_trace = cls.get_current_trace()
        trace_id = current_trace.trace_id if current_trace else (trace_id_ctx_var.get() or "tr-detached")
        actual_parent = parent_span_id or cls.get_current_span_id()
        span_id = f"sp-{uuid.uuid4().hex[:8]}"

        t_start_perf = time.perf_counter()
        t_start_wall = time.time()

        span_record = SpanRecord(
            span_id=span_id,
            parent_span_id=actual_parent,
            trace_id=trace_id,
            name=name,
            step_type=step_type,
            status=SpanStatus.COMPLETED.value,
            start_time=t_start_wall,
            end_time=t_start_wall,
            duration_ms=0.0,
            inputs=redact_sensitive_data(inputs or {}),
            outputs={},
            metadata=redact_sensitive_data(metadata or {}),
        )

        token_span = active_span_ctx.set(span_id)
        token_log_span = span_id_ctx_var.set(span_id)

        try:
            yield span_record
            span_record.status = SpanStatus.COMPLETED.value
        except Exception as exc:
            duration = (time.perf_counter() - t_start_perf) * 1000.0
            span_record.duration_ms = round(duration, 2)
            span_record.end_time = time.time()
            span_record.status = SpanStatus.FAILED.value

            classification = ErrorClassifier.classify(exc, stage=step_type)
            span_record.error_category = classification.category.value
            span_record.error_code = classification.safe_code
            span_record.error_message = classification.diagnostic_summary

            if current_trace:
                current_trace.error_category = classification.category.value
                current_trace.spans.append(span_record)
            raise
        else:
            duration = (time.perf_counter() - t_start_perf) * 1000.0
            span_record.duration_ms = round(duration, 2)
            span_record.end_time = time.time()
            span_record.outputs = redact_sensitive_data(span_record.outputs)
            if current_trace:
                current_trace.spans.append(span_record)
        finally:
            active_span_ctx.reset(token_span)
            span_id_ctx_var.reset(token_log_span)

    @classmethod
    def record_manual_span(
        cls,
        name: str,
        step_type: str,
        duration_ms: float,
        status: str = SpanStatus.COMPLETED.value,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
        error_category: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        tokens_total: int | None = None,
        estimated_cost_usd: float | None = None,
        cost_status: str | None = None,
        is_skipped: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> SpanRecord:
        """Appends an explicit span measurement directly to the active trace."""
        current_trace = cls.get_current_trace()
        trace_id = current_trace.trace_id if current_trace else (trace_id_ctx_var.get() or "tr-detached")
        span_id = f"sp-{uuid.uuid4().hex[:8]}"
        now = time.time()

        span_record = SpanRecord(
            span_id=span_id,
            parent_span_id=parent_span_id or cls.get_current_span_id(),
            trace_id=trace_id,
            name=name,
            step_type=step_type,
            status=status,
            start_time=now - (duration_ms / 1000.0),
            end_time=now,
            duration_ms=round(duration_ms, 2),
            inputs=redact_sensitive_data(inputs or {}),
            outputs=redact_sensitive_data(outputs or {}),
            error_category=error_category,
            error_code=error_code,
            error_message=error_message,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_total=tokens_total,
            estimated_cost_usd=estimated_cost_usd,
            cost_status=cost_status,
            is_skipped=is_skipped,
            metadata=redact_sensitive_data(metadata or {}),
        )

        if current_trace:
            current_trace.spans.append(span_record)
        return span_record

    @classmethod
    def record_skipped_span(
        cls,
        name: str,
        step_type: str,
        reason: str,
        parent_span_id: str | None = None,
    ) -> SpanRecord:
        """Explicitly records an unexecuted or conditionally skipped pipeline stage."""
        return cls.record_manual_span(
            name=name,
            step_type=step_type,
            duration_ms=0.0,
            status=SpanStatus.SKIPPED.value,
            is_skipped=True,
            outputs={"skip_reason": reason},
            parent_span_id=parent_span_id,
        )

    @classmethod
    def finish_trace(
        cls,
        status: str = "completed",
        tokens_total: int = 0,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        model: str = "default",
        error_category: str | None = None,
        recovery_count: int = 0,
        retrieval_method: str | None = None,
        retrieval_candidate_count: int | None = None,
        retrieval_returned_count: int | None = None,
        retrieval_scores: list[Any] | None = None,
        evidence_sufficiency: str | None = None,
        citation_validation_passed: bool | None = None,
        verification_status: str | None = None,
        provider_reported_cost: float | None = None,
    ) -> TraceRecord | None:
        """Closes the active trace, attributes tokens and costs, and detaches the context variable."""
        from app.services.observability.cost import CostIntelligenceEngine

        trace = active_trace_ctx.get()
        if not trace:
            return None

        trace.end_time = time.time()
        trace.duration_ms = round((trace.end_time - trace.start_time) * 1000.0, 2)
        trace.status = status
        trace.tokens_total = tokens_total
        trace.prompt_tokens = prompt_tokens
        trace.completion_tokens = completion_tokens
        trace.model = model
        trace.recovery_count = recovery_count
        if error_category:
            trace.error_category = error_category

        # Retrieval provenance & evidence
        trace.retrieval_method = retrieval_method
        trace.retrieval_candidate_count = retrieval_candidate_count
        trace.retrieval_returned_count = retrieval_returned_count
        if retrieval_scores:
            trace.retrieval_scores = retrieval_scores
        trace.evidence_sufficiency = evidence_sufficiency
        trace.citation_validation_passed = citation_validation_passed
        trace.verification_status = verification_status

        # Cost Intelligence calculation
        cost_calc = CostIntelligenceEngine.calculate_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=tokens_total,
            provider_reported_cost=provider_reported_cost,
        )
        trace.estimated_cost_usd = cost_calc.estimated_cost_usd
        trace.cost_status = cost_calc.cost_status
        trace.cost_currency = cost_calc.currency
        trace.pricing_source = cost_calc.pricing_source

        # Reset active trace context
        active_trace_ctx.set(None)
        return trace
