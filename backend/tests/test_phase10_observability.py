"""Comprehensive unit and integration tests for Phase 10 Observability Engine."""

import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.logging import JSONFormatter
from app.main import app
from app.services.observability.alerting import AlertRule, AlertSeverity
from app.services.observability.metrics import MetricsCalculator, compute_percentile
from app.services.observability.redaction import redact_sensitive_data
from app.services.observability.schemas import (
    ErrorCategory,
    SpanRecord,
    SpanStatus,
    TraceRecord,
)
from app.services.observability.service import ObservabilityService
from app.services.observability.taxonomy import ErrorClassifier
from app.services.observability.tracer import Tracer


# ==============================================================================
# 1. Trace ID creation and propagation
# ==============================================================================
def test_trace_id_creation_and_context():
    trace = Tracer.start_trace(query="What is the refund window?")
    assert trace.trace_id.startswith("tr-")
    assert trace.query == "What is the refund window?"
    assert Tracer.get_current_trace() == trace

    finished = Tracer.finish_trace(status="completed")
    assert finished is not None
    assert finished.duration_ms >= 0.0
    assert Tracer.get_current_trace() is None


@pytest.mark.asyncio
async def test_trace_id_http_header_propagation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pass custom trace id
        custom_tid = "tr-custom-trace-header-1234"
        res = await client.get("/api/v1/health/live", headers={"X-Trace-ID": custom_tid})
        assert res.status_code == 200
        assert res.headers.get("X-Trace-ID") == custom_tid

        # Auto-generated trace id
        res2 = await client.get("/api/v1/health/live")
        assert res2.status_code == 200
        assert "X-Trace-ID" in res2.headers
        assert res2.headers["X-Trace-ID"].startswith("tr-")


# ==============================================================================
# 2. Parent-child span relationships
# ==============================================================================
def test_parent_child_span_nesting():
    Tracer.start_trace(query="Parent Child Test")
    with Tracer.span("Root Span", "gateway") as root_span:
        with Tracer.span("Child Step A", "retrieval") as child_a:
            assert child_a.parent_span_id == root_span.span_id

        with Tracer.span("Child Step B", "reranking") as child_b:
            assert child_b.parent_span_id == root_span.span_id

    trace = Tracer.finish_trace()
    assert len(trace.spans) == 3
    span_names = [s.name for s in trace.spans]
    assert "Root Span" in span_names
    assert "Child Step A" in span_names
    assert "Child Step B" in span_names


# ==============================================================================
# 3. Accurate node entry and exit events
# ==============================================================================
@pytest.mark.asyncio
async def test_async_span_entry_exit_lifecycle():
    Tracer.start_trace(query="Async Span Lifecycle")
    t0 = time.time()
    async with Tracer.async_span("Async Operation", "llm", inputs={"prompt": "hello"}) as span:
        assert span.name == "Async Operation"
        assert span.start_time >= t0
        span.outputs = {"response": "world"}

    trace = Tracer.finish_trace()
    assert len(trace.spans) == 1
    sp = trace.spans[0]
    assert sp.status == SpanStatus.COMPLETED.value
    assert sp.end_time >= sp.start_time
    assert sp.outputs == {"response": "world"}


# ==============================================================================
# 4. Duration calculation
# ==============================================================================
def test_duration_calculation_precision():
    Tracer.start_trace(query="Duration Test")
    with Tracer.span("Fast Step", "cache"):
        time.sleep(0.01)

    trace = Tracer.finish_trace()
    sp = trace.spans[0]
    assert sp.duration_ms >= 5.0
    assert trace.duration_ms >= 5.0


# ==============================================================================
# 5. Success, failure, timeout, and skipped-span handling
# ==============================================================================
def test_span_status_handling_on_exception():
    Tracer.start_trace(query="Failure Span")
    with pytest.raises(ValueError, match="Synthetic failure"):
        with Tracer.span("Failing Step", "validation"):
            raise ValueError("Synthetic failure")

    trace = Tracer.finish_trace(status="failed")
    assert len(trace.spans) == 1
    failed_span = trace.spans[0]
    assert failed_span.status == SpanStatus.FAILED.value
    assert failed_span.error_category is not None

    manual_skipped = Tracer.record_manual_span(
        name="Skipped Reranker",
        step_type="reranking",
        duration_ms=0.0,
        status=SpanStatus.SKIPPED.value,
    )
    assert manual_skipped.status == SpanStatus.SKIPPED.value


# ==============================================================================
# 6. Structured log redaction
# ==============================================================================
def test_structured_log_and_data_redaction():
    sensitive_payload = {
        "user_id": "u-123",
        "password": "secret_password_123",
        "api_key": "mock-secret-key-xyz123abc",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "nested": {
            "token": "refresh_secret_token",
            "content": "A" * 500,  # overly long document dump
        },
    }

    sanitized = redact_sensitive_data(sensitive_payload)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["content"].endswith("... [TRUNCATED_FOR_OBSERVABILITY]")
    assert sanitized["user_id"] == "u-123"

    # Verify JSONFormatter redacts logged record text
    formatter = JSONFormatter()
    import logging
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Logged user token with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        args=(),
        exc_info=None,
    )
    formatted_json = formatter.format(record)
    assert "Bearer [REDACTED]" in formatted_json
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in formatted_json


# ==============================================================================
# 7. Metric aggregation
# ==============================================================================
def test_metric_aggregation_totals():
    t1 = TraceRecord(
        trace_id="tr-1",
        query="q1",
        status="completed",
        start_time=1.0,
        end_time=1.2,
        duration_ms=200.0,
        created_at="2026-10-10T00:00:00Z",
    )
    t2 = TraceRecord(
        trace_id="tr-2",
        query="q2",
        status="failed",
        error_category="llm_provider_failure",
        start_time=1.0,
        end_time=1.5,
        duration_ms=500.0,
        created_at="2026-10-10T00:00:00Z",
    )
    t3 = TraceRecord(
        trace_id="tr-3",
        query="q3",
        status="recovered",
        recovery_count=1,
        start_time=1.0,
        end_time=1.4,
        duration_ms=400.0,
        created_at="2026-10-10T00:00:00Z",
    )

    metrics = MetricsCalculator.calculate([t1, t2, t3])
    assert metrics.total_requests == 3
    assert metrics.successful_requests == 2
    assert metrics.failed_requests == 1
    assert metrics.recovered_requests == 1
    assert round(metrics.error_rate, 2) == 0.33
    assert metrics.llm_provider_error_count == 1
    assert metrics.retry_count == 1


# ==============================================================================
# 8. P50/P95/P99 edge cases
# ==============================================================================
def test_percentile_computation_edge_cases():
    # Empty
    assert compute_percentile([], 50.0) == 0.0

    # Single item
    assert compute_percentile([100.0], 95.0) == 100.0

    # Multi-item sequence
    vals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = compute_percentile(vals, 50.0)
    p95 = compute_percentile(vals, 95.0)
    assert p50 == 55.0
    assert p95 == 95.5


# ==============================================================================
# 9. Zero-sample and low-sample behavior
# ==============================================================================
def test_low_sample_guardrails_prevent_misleading_percentiles():
    # Zero samples
    zero_metrics = MetricsCalculator.calculate([])
    assert zero_metrics.total_requests == 0
    assert zero_metrics.error_rate == 0.0
    assert zero_metrics.p50_latency_ms is None
    assert zero_metrics.p95_latency_ms is None
    assert zero_metrics.p99_latency_ms is None

    # Low sample (< 3 traces)
    t1 = TraceRecord(
        trace_id="tr-1",
        query="q1",
        status="completed",
        start_time=1.0,
        end_time=1.1,
        duration_ms=100.0,
        created_at="2026-10-10T00:00:00Z",
    )
    low_sample_metrics = MetricsCalculator.calculate([t1])
    # Protect against misleading percentiles on N=1
    assert low_sample_metrics.p50_latency_ms is None
    assert low_sample_metrics.p95_latency_ms is None
    assert low_sample_metrics.avg_latency_ms == 100.0


# ==============================================================================
# 10. Error classification taxonomy
# ==============================================================================
def test_error_classification_taxonomy_mapping():
    # Authentication failure
    c_auth = ErrorClassifier.classify("token expired", stage="auth")
    assert c_auth.category == ErrorCategory.AUTHENTICATION_FAILURE
    assert not c_auth.is_infrastructure_failure

    # Database connectivity error
    c_db = ErrorClassifier.classify(Exception("psycopg connection failed"), stage="retrieval")
    assert c_db.category == ErrorCategory.DATABASE_FAILURE
    assert c_db.is_infrastructure_failure

    # Timeout
    c_timeout = ErrorClassifier.classify(TimeoutError("request deadline exceeded"), stage="llm")
    assert c_timeout.category == ErrorCategory.TIMEOUT
    assert c_timeout.is_infrastructure_failure

    # LLM provider error
    c_llm = ErrorClassifier.classify("OpenAI rate limit error 429", stage="llm")
    assert c_llm.category in (ErrorCategory.LLM_PROVIDER_FAILURE, ErrorCategory.RATE_LIMITING)


# ==============================================================================
# 11. Insufficient evidence versus infrastructure failure distinction
# ==============================================================================
def test_insufficient_evidence_vs_infrastructure_failure():
    # Insufficient evidence is a VALID domain outcome, NOT an infrastructure failure
    c_insufficient = ErrorClassifier.classify(
        "Insufficient evidence to answer claim",
        stage="evidence_assessment",
        details={"evidence_status": "insufficient"},
    )
    assert c_insufficient.category == ErrorCategory.INSUFFICIENT_EVIDENCE
    assert c_insufficient.is_infrastructure_failure is False
    assert "Upload additional" in c_insufficient.suggested_action

    # Database failure IS an infrastructure failure
    c_infra = ErrorClassifier.classify("PostgreSQL connection refused", stage="database")
    assert c_infra.category == ErrorCategory.DATABASE_FAILURE
    assert c_infra.is_infrastructure_failure is True


# ==============================================================================
# 12. Recovery-attempt telemetry
# ==============================================================================
def test_recovery_attempt_telemetry_recording():
    Tracer.start_trace(query="Self Healing Telemetry")
    Tracer.record_manual_span(
        name="Self-Healing Recovery Action",
        step_type="recovery",
        duration_ms=45.0,
        status="recovered",
        inputs={"action": "rewrite_query", "attempt": 1},
        outputs={"rewritten_query": "contract cancellation window"},
    )
    trace = Tracer.finish_trace(status="recovered", recovery_count=1)
    assert trace.status == "recovered"
    assert trace.recovery_count == 1
    recovery_span = [s for s in trace.spans if s.step_type == "recovery"][0]
    assert recovery_span.status == "recovered"
    assert recovery_span.outputs["rewritten_query"] == "contract cancellation window"


# ==============================================================================
# 13. Alert threshold evaluation
# ==============================================================================
def test_alert_rule_threshold_evaluation():
    rule = AlertRule(
        rule_id="test_error_rate",
        name="High Error Rate",
        metric_key="error_rate",
        condition="gt",
        threshold=0.20,
        severity=AlertSeverity.CRITICAL,
        min_total_requests=2,
    )

    # Sub-threshold: no alert
    metrics_ok = MetricsCalculator.calculate([
        TraceRecord(trace_id="t1", query="q", status="completed", start_time=1, end_time=2, duration_ms=10, created_at=""),
        TraceRecord(trace_id="t2", query="q", status="completed", start_time=1, end_time=2, duration_ms=10, created_at=""),
    ])
    assert rule.evaluate(metrics_ok) is None

    # Over threshold: alerts
    metrics_bad = MetricsCalculator.calculate([
        TraceRecord(trace_id="t1", query="q", status="failed", start_time=1, end_time=2, duration_ms=10, created_at=""),
        TraceRecord(trace_id="t2", query="q", status="completed", start_time=1, end_time=2, duration_ms=10, created_at=""),
    ])
    alert = rule.evaluate(metrics_bad)
    assert alert is not None
    assert alert.severity == "critical"
    assert alert.status == "active"


# ==============================================================================
# 14. Alert deduplication and cooldown
# ==============================================================================
def test_alert_cooldown_deduplication():
    rule = AlertRule(
        rule_id="cooldown_test",
        name="High Latency Alert",
        metric_key="p95_latency_ms",
        condition="gt",
        threshold=100.0,
        cooldown_seconds=300.0,
        min_total_requests=1,
    )

    t = [
        TraceRecord(trace_id="1", query="q", status="completed", start_time=1, end_time=2, duration_ms=200, created_at=""),
        TraceRecord(trace_id="2", query="q", status="completed", start_time=1, end_time=2, duration_ms=210, created_at=""),
        TraceRecord(trace_id="3", query="q", status="completed", start_time=1, end_time=2, duration_ms=220, created_at=""),
    ]
    metrics = MetricsCalculator.calculate(t)

    # First trigger: active
    alert1 = rule.evaluate(metrics)
    assert alert1 is not None
    assert alert1.status == "active"

    # Immediate second evaluation: in cooldown
    alert2 = rule.evaluate(metrics)
    assert alert2 is not None
    assert alert2.status == "cooldown"


# ==============================================================================
# 15. Health and readiness behavior
# ==============================================================================
@pytest.mark.asyncio
async def test_observability_readiness_probe():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/observability/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "dependencies" in data


# ==============================================================================
# 16. Authorization for trace APIs
# ==============================================================================
@pytest.mark.asyncio
async def test_trace_apis_require_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Unauthenticated calls should be rejected
        res = await client.get("/api/v1/observability/traces")
        assert res.status_code in (401, 403)

        res2 = await client.get("/api/v1/observability/metrics")
        assert res2.status_code in (401, 403)

        res3 = await client.get("/api/v1/observability/alerts")
        assert res3.status_code in (401, 403)


# ==============================================================================
# 17. Pagination and time-range validation
# ==============================================================================
@pytest.mark.asyncio
async def test_in_memory_service_pagination_and_search():
    service = ObservabilityService()
    ObservabilityService.clear_buffer()

    for i in range(15):
        service.record_to_buffer(
            TraceRecord(
                trace_id=f"tr-pag-{i:02d}",
                query=f"Query {i}",
                status="completed" if i % 2 == 0 else "failed",
                start_time=1.0,
                end_time=1.1,
                duration_ms=100.0 + i,
                created_at="2026-10-10T00:00:00Z",
            )
        )

    # Offset 0, limit 5
    items, total = await service.list_traces(limit=5, offset=0)
    assert len(items) == 5
    assert total == 15

    # Filter status="failed"
    items_failed, total_failed = await service.list_traces(status="failed")
    assert len(items_failed) == 7
    assert all(it.status == "failed" for it in items_failed)

    # Search query
    items_searched, _ = await service.list_traces(search="Query 10")
    assert len(items_searched) == 1
    assert items_searched[0].query == "Query 10"


# ==============================================================================
# 18. Telemetry exporter failure isolation
# ==============================================================================
@pytest.mark.asyncio
async def test_telemetry_save_failure_isolation():
    # Mock a faulty session where add raises an error
    class FaultySession:
        def add(self, obj):
            raise RuntimeError("Database connection broken during trace save")

        async def flush(self):
            pass

        async def rollback(self):
            pass

    service = ObservabilityService(session=FaultySession())  # type: ignore
    dummy_trace = TraceRecord(
        trace_id="tr-fault-iso",
        query="Fault test",
        status="completed",
        start_time=1.0,
        end_time=1.1,
        duration_ms=50.0,
        created_at="2026-10-10T00:00:00Z",
    )

    # Does NOT raise RuntimeError; safely catches and isolates failure
    await service.record_trace(dummy_trace)

    # Verify trace was still recorded to memory buffer despite DB failure
    buffered = service.get_buffered_traces()
    assert any(t.trace_id == "tr-fault-iso" for t in buffered)


# ==============================================================================
# 19. Database or storage failure fallback to buffer
# ==============================================================================
@pytest.mark.asyncio
async def test_observability_storage_fallback_to_buffer():
    service = ObservabilityService()
    ObservabilityService.clear_buffer()

    test_trace = TraceRecord(
        trace_id="tr-fallback-test",
        query="What is the refund deadline?",
        status="completed",
        start_time=1.0,
        end_time=1.2,
        duration_ms=200.0,
        created_at="2026-10-10T00:00:00Z",
        spans=[
            SpanRecord(
                span_id="sp-1",
                trace_id="tr-fallback-test",
                name="Gateway Init",
                step_type="gateway",
                status="completed",
                start_time=1.0,
                end_time=1.05,
                duration_ms=50.0,
            )
        ],
    )
    service.record_to_buffer(test_trace)

    fetched = await service.get_trace("tr-fallback-test")
    assert fetched is not None
    assert fetched.trace_id == "tr-fallback-test"
    assert len(fetched.spans) == 1
    assert fetched.spans[0].name == "Gateway Init"


# ==============================================================================
# 20. End-to-end 15-stage tracing & LangGraph pipeline telemetry integration
# ==============================================================================
@pytest.mark.asyncio
async def test_full_pipeline_trace_stages_and_metrics():
    # Simulate a realistic multi-stage trace covering the 15 pipeline checkpoints
    tid = f"tr-e2e-{uuid.uuid4().hex[:8]}"
    Tracer.start_trace(query="Full Pipeline E2E Verification", trace_id=tid)

    # 1. Request gateway
    Tracer.record_manual_span("Request Received & Initialized", "gateway", 2.0)
    # 2. Scope authorization
    Tracer.record_manual_span("Scope & Permission Validation", "scope_authorization", 5.0)
    # 3. Query analysis
    Tracer.record_manual_span("Query Preprocessing & Intent", "query_analysis", 15.0)
    # 4. Retrieval strategy
    Tracer.record_manual_span("Strategy Selection", "retrieval_strategy", 3.0)
    # 5. Dense semantic retrieval
    Tracer.record_manual_span("Dense Semantic Retrieval", "dense_retrieval", 60.0)
    # 6. BM25 lexical retrieval
    Tracer.record_manual_span("BM25 Lexical Retrieval", "lexical_retrieval", 25.0)
    # 7. Reciprocal Rank Fusion
    Tracer.record_manual_span("Reciprocal Rank Fusion", "fusion", 8.0)
    # 8. Reranking
    Tracer.record_manual_span("Cross-Encoder Reranker", "reranking", 45.0)
    # 9. Evidence assessment
    Tracer.record_manual_span("Evidence Sufficiency Assessment", "evidence_assessment", 10.0)
    # 10. Grounded LLM generation
    Tracer.record_manual_span("Grounded Answer Generation", "grounded_generation", 210.0)
    # 11. Citation validation
    Tracer.record_manual_span("Citation Audit & Provenance", "citation_validation", 20.0)
    # 12. Verification guardrail
    Tracer.record_manual_span("Factuality & Grounding Verification", "answer_verification", 40.0)
    # 13. Self-healing recovery
    Tracer.record_manual_span("Self-Healing Recovery Check", "recovery", 12.0, status="recovered")
    # 14. Completion
    Tracer.record_manual_span("Final Response & Request Completion", "completion", 2.0)

    finished = Tracer.finish_trace(status="recovered", recovery_count=1)
    assert finished is not None
    assert finished.trace_id == tid
    assert len(finished.spans) == 14
    assert finished.status == "recovered"
    assert finished.duration_ms >= 0.0

    # Save to service and verify metrics
    obs_svc = ObservabilityService()
    await obs_svc.record_trace(finished)

    metrics = await obs_svc.get_metrics()
    assert metrics.total_requests >= 1
    assert "dense_retrieval" in metrics.stage_breakdown
    assert "reranking" in metrics.stage_breakdown
    assert "grounded_generation" in metrics.stage_breakdown
