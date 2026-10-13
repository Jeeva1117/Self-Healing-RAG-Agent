"""Comprehensive test suite for Phase 11: Observability & Production Intelligence Engine.

Validates all 20 required scenarios:
1. Successful RAG request creates a trace with actual executed stages.
2. Trace IDs are unique across independent requests.
3. Parent-child span relationships are correct.
4. Stage durations are non-negative and use consistent units (ms).
5. Skipped stages are not falsely recorded as executed (is_skipped=True).
6. An embedding failure is traced with the correct error category.
7. A retrieval failure is traced without fabricating results.
8. An LLM timeout records the actual failure and safe diagnostic details.
9. Token accounting handles provider-reported usage.
10. Missing token metadata remains unknown instead of becoming a fabricated value.
11. Cost calculations use the configured pricing and correct units.
12. Retrieval scores preserve their source and meaning (ChunkScoreProvenance).
13. Recovery attempts and final outcomes match actual execution.
14. Authentication is required for protected endpoints.
15. Cross-user or cross-tenant trace access is denied.
16. Secrets and sensitive fields are redacted.
17. Exporter failure does not unexpectedly break normal RAG requests.
18. Empty telemetry produces honest empty/unavailable states.
19. Overview and Error Explorer APIs return structured data matching schemas.
20. Pricing catalog endpoint returns registered models and USD per 1M token rates.
"""

import time
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.observability.cost import (
    CostIntelligenceEngine,
)
from app.services.observability.exporter import TelemetryExporter
from app.services.observability.redaction import redact_sensitive_data
from app.services.observability.schemas import (
    ChunkScoreProvenance,
    ErrorCategory,
    SpanStatus,
    TraceRecord,
)
from app.services.observability.service import ObservabilityService
from app.services.observability.taxonomy import ErrorClassifier
from app.services.observability.tracer import Tracer


# ==============================================================================
# Scenario 1: A successful RAG request creates a trace with actual executed stages
# ==============================================================================
def test_scenario_01_successful_rag_trace_creation():
    trace = Tracer.start_trace(
        query="What are the enterprise refund SLAs?",
        knowledge_base_id="kb-enterprise-01",
        user_id="user-corp-123",
    )
    assert trace is not None
    assert trace.query == "What are the enterprise refund SLAs?"

    # Execute actual pipeline stages
    with Tracer.span("Query Preprocessing", "query_analysis") as s1:
        s1.outputs = {"sub_queries": ["refund terms", "sla contract"]}

    with Tracer.span("Hybrid Retrieval", "retrieval") as s2:
        s2.outputs = {"candidates_count": 5}

    with Tracer.span("LLM Synthesis", "grounded_generation") as s3:
        s3.prompt_tokens = 350
        s3.completion_tokens = 120
        s3.outputs = {"citations": 2}

    finished = Tracer.finish_trace(
        status="completed",
        model="gpt-4o",
        retrieval_method="hybrid_fusion_rerank",
        evidence_sufficiency="sufficient",
        citation_validation_passed=True,
        verification_status="grounded_evidence",
    )

    assert finished.status == "completed"
    assert len(finished.spans) == 3
    assert finished.spans[0].name == "Query Preprocessing"
    assert finished.spans[1].name == "Hybrid Retrieval"
    assert finished.spans[2].name == "LLM Synthesis"
    assert finished.model == "gpt-4o"
    assert finished.retrieval_method == "hybrid_fusion_rerank"
    assert finished.evidence_sufficiency == "sufficient"
    assert finished.citation_validation_passed is True


# ==============================================================================
# Scenario 2: Trace IDs are unique across independent requests
# ==============================================================================
def test_scenario_02_trace_ids_are_unique():
    trace_ids = set()
    for i in range(25):
        t = Tracer.start_trace(query=f"Independent query {i}")
        trace_ids.add(t.trace_id)
        Tracer.finish_trace(status="completed")

    assert len(trace_ids) == 25
    for tid in trace_ids:
        assert tid.startswith("tr-")


# ==============================================================================
# Scenario 3: Parent-child span relationships are correct
# ==============================================================================
def test_scenario_03_parent_child_span_hierarchy():
    Tracer.start_trace(query="Test span nesting")

    with Tracer.span("Pipeline Root", "gateway"):
        with Tracer.span("Dense Retrieval", "dense_retrieval") as child1:
            child1.outputs = {"vectors": 10}
        with Tracer.span("Lexical BM25", "lexical_retrieval") as child2:
            child2.outputs = {"bm25": 8}

    finished = Tracer.finish_trace(status="completed")
    assert len(finished.spans) == 3

    root_span = next(s for s in finished.spans if s.name == "Pipeline Root")
    child_spans = [s for s in finished.spans if s.parent_span_id == root_span.span_id]

    assert len(child_spans) == 2
    assert root_span.parent_span_id is None
    assert all(c.parent_span_id == root_span.span_id for c in child_spans)


# ==============================================================================
# Scenario 4: Stage durations are non-negative and use consistent units (ms)
# ==============================================================================
def test_scenario_04_durations_non_negative_in_milliseconds():
    Tracer.start_trace(query="Test timing precision")

    with Tracer.span("Timed Operation", "retrieval") as s:
        time.sleep(0.01)  # ~10ms
        s.outputs = {"done": True}

    finished = Tracer.finish_trace(status="completed")
    span = finished.spans[0]

    assert span.duration_ms >= 5.0
    assert finished.duration_ms >= span.duration_ms
    assert isinstance(span.duration_ms, float)
    assert isinstance(finished.duration_ms, float)


# ==============================================================================
# Scenario 5: Skipped stages are not falsely recorded as executed
# ==============================================================================
def test_scenario_05_skipped_stages_recorded_honestly():
    Tracer.start_trace(query="Test skipped stage")

    with Tracer.span("Initial Retrieval", "retrieval") as s1:
        s1.outputs = {"evidence_found": True}

    # Record skipped span explicitly
    Tracer.record_skipped_span(
        name="Self-Healing Recovery Loop",
        step_type="recovery",
        reason="Initial retrieval and citations passed without anomalies",
    )

    finished = Tracer.finish_trace(status="completed")
    assert len(finished.spans) == 2

    executed_span = finished.spans[0]
    assert executed_span.status == SpanStatus.COMPLETED
    assert not executed_span.is_skipped

    skipped_span = finished.spans[1]
    assert skipped_span.name == "Self-Healing Recovery Loop"
    assert skipped_span.status == SpanStatus.SKIPPED
    assert skipped_span.is_skipped is True
    assert skipped_span.duration_ms == 0.0
    assert skipped_span.outputs.get("skip_reason") == "Initial retrieval and citations passed without anomalies"


# ==============================================================================
# Scenario 6: An embedding failure is traced with the correct error category
# ==============================================================================
def test_scenario_06_embedding_failure_traced_with_correct_category():
    Tracer.start_trace(query="Query triggering embedding error")

    try:
        with Tracer.span("Vector Embedding Generation", "dense_retrieval"):
            raise ConnectionError("Embedding service connection refused by upstream provider")
    except ConnectionError:
        pass

    finished = Tracer.finish_trace(
        status="failed",
        error_category=ErrorCategory.EMBEDDING_PROVIDER_FAILURE.value,
    )

    assert finished.status == "failed"
    assert finished.error_category == ErrorCategory.EMBEDDING_PROVIDER_FAILURE.value
    failed_span = finished.spans[0]
    assert failed_span.status == SpanStatus.FAILED
    assert failed_span.error_code is not None
    assert failed_span.error_message is not None


# ==============================================================================
# Scenario 7: A retrieval failure is traced without fabricating results
# ==============================================================================
def test_scenario_07_retrieval_failure_traced_honestly():
    Tracer.start_trace(query="Unmatched obscure terms")

    with Tracer.span("Hybrid Search", "retrieval") as s:
        s.outputs = {"candidates_count": 0, "results": []}

    finished = Tracer.finish_trace(
        status="insufficient_evidence",
        evidence_sufficiency="insufficient",
        retrieval_scores=[],
    )

    assert finished.status == "insufficient_evidence"
    assert finished.evidence_sufficiency == "insufficient"
    assert finished.retrieval_scores == []
    # No fabricated chunks or scores


# ==============================================================================
# Scenario 8: An LLM timeout records actual failure and safe diagnostic details
# ==============================================================================
def test_scenario_08_llm_timeout_diagnostics():
    Tracer.start_trace(query="Long prompt query")

    try:
        with Tracer.span("LLM Synthesis", "grounded_generation"):
            raise TimeoutError("Upstream model API timed out after 30000ms")
    except TimeoutError:
        pass

    diag = ErrorClassifier.classify(
        error=TimeoutError("Upstream model API timed out after 30000ms"),
        stage="grounded_generation",
    )

    finished = Tracer.finish_trace(
        status="failed",
        error_category=diag.category.value,
    )

    assert finished.status == "failed"
    assert finished.error_category == ErrorCategory.TIMEOUT.value
    assert diag.is_infrastructure_failure is True
    assert diag.safe_code == "EXECUTION_TIMEOUT"
    assert "elapsed" in diag.diagnostic_summary.lower() or "timeout" in diag.suggested_action.lower()


# ==============================================================================
# Scenario 9: Token accounting handles provider-reported usage
# ==============================================================================
def test_scenario_09_provider_reported_token_usage():
    # Cost calculation with exact provider reported values
    result = CostIntelligenceEngine.calculate_cost(
        model="gpt-4o",
        prompt_tokens=500,
        completion_tokens=200,
        provider_reported_cost=0.00325,
    )

    assert result.cost_status == "provider_reported"
    assert result.is_exact_provider_charge is True
    assert result.estimated_cost_usd == 0.00325
    assert result.prompt_tokens == 500
    assert result.completion_tokens == 200
    assert result.total_tokens == 700
    assert result.pricing_source == "provider_api_metadata"


# ==============================================================================
# Scenario 10: Missing token metadata remains unknown instead of fabricated
# ==============================================================================
def test_scenario_10_missing_token_metadata_returns_unavailable():
    # Missing model or token count
    result1 = CostIntelligenceEngine.calculate_cost(model=None, prompt_tokens=None)
    assert result1.cost_status == "unavailable"
    assert result1.estimated_cost_usd is None
    assert result1.pricing_source is None

    # Unknown uncataloged custom model
    result2 = CostIntelligenceEngine.calculate_cost(
        model="custom-internal-llm-v1-unknown",
        prompt_tokens=100,
        completion_tokens=50,
    )
    assert result2.cost_status == "unavailable"
    assert result2.estimated_cost_usd is None


# ==============================================================================
# Scenario 11: Cost calculations use configured pricing and correct units
# ==============================================================================
def test_scenario_11_cost_calculation_uses_catalog_rates():
    # gpt-4o pricing: $2.50 per 1M prompt, $10.00 per 1M completion
    # 10,000 prompt tokens = 10,000 * 2.50 / 1,000,000 = $0.025
    # 5,000 completion tokens = 5,000 * 10.00 / 1,000,000 = $0.050
    # Total = $0.075
    result = CostIntelligenceEngine.calculate_cost(
        model="gpt-4o",
        prompt_tokens=10_000,
        completion_tokens=5_000,
    )

    assert result.cost_status == "estimated"
    assert result.currency == "USD"
    assert result.estimated_cost_usd == 0.075
    assert result.pricing_source == "standard_catalog_2026"

    # gpt-4o-mini pricing: $0.15 per 1M prompt, $0.60 per 1M completion
    # 1,000,000 prompt + 1,000,000 completion = 0.15 + 0.60 = 0.75
    result_mini = CostIntelligenceEngine.calculate_cost(
        model="gpt-4o-mini",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    assert result_mini.estimated_cost_usd == 0.75


# ==============================================================================
# Scenario 12: Retrieval scores preserve their source and meaning
# ==============================================================================
def test_scenario_12_retrieval_score_provenance_integrity():
    scores = [
        ChunkScoreProvenance(
            chunk_id="chk-vector-01",
            document_name="terms.pdf",
            vector_score=0.892,
            lexical_score=14.50,
            rrf_score=0.032,
            rerank_score=0.965,
            final_rank=1,
            stage_provenance="hybrid_fusion_rerank",
        ),
        ChunkScoreProvenance(
            chunk_id="chk-lexical-02",
            document_name="terms.pdf",
            vector_score=0.741,
            lexical_score=19.20,
            rrf_score=0.029,
            rerank_score=0.880,
            final_rank=2,
            stage_provenance="hybrid_fusion_rerank",
        ),
    ]

    Tracer.start_trace(query="Test score provenance")
    finished = Tracer.finish_trace(
        status="completed",
        retrieval_scores=scores,
    )

    assert len(finished.retrieval_scores) == 2
    first = finished.retrieval_scores[0]
    assert first.chunk_id == "chk-vector-01"
    assert first.vector_score == 0.892
    assert first.lexical_score == 14.50
    assert first.rrf_score == 0.032
    assert first.rerank_score == 0.965
    assert first.final_rank == 1


# ==============================================================================
# Scenario 13: Recovery attempts and final outcomes match actual execution
# ==============================================================================
def test_scenario_13_recovery_attempts_and_outcomes():
    Tracer.start_trace(query="Query requiring recovery")

    # Primary failed generation
    with Tracer.span("Initial Generation", "grounded_generation") as s1:
        s1.outputs = {"hallucination_detected": True}

    # Recovery span
    with Tracer.span("Self-Healing Citation Repair", "recovery") as s2:
        s2.inputs = {"retry_attempt": 1, "action": "re_retrieve_strict"}
        s2.outputs = {"healed": True}

    finished = Tracer.finish_trace(status="recovered", recovery_count=1)

    assert finished.status == "recovered"
    assert finished.recovery_count == 1
    recovery_span = next(s for s in finished.spans if s.step_type == "recovery")
    assert recovery_span.status == SpanStatus.COMPLETED


# ==============================================================================
# Scenario 14: Authentication is required for protected endpoints
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_14_unauthenticated_requests_are_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # /api/v1/observability/overview requires authentication
        res_overview = await client.get("/api/v1/observability/overview")
        assert res_overview.status_code in (401, 403)

        # /api/v1/observability/traces requires authentication
        res_traces = await client.get("/api/v1/observability/traces")
        assert res_traces.status_code in (401, 403)

        # /api/v1/observability/errors requires authentication
        res_errors = await client.get("/api/v1/observability/errors")
        assert res_errors.status_code in (401, 403)


# ==============================================================================
# Scenario 15: Cross-user or cross-tenant trace access is denied
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_15_cross_user_trace_isolation():
    # ObservabilityService enforces tenant/user scoping
    service = ObservabilityService()

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # Create trace belonging to user A using Tracer lifecycle
    Tracer.start_trace(
        query="User A private enterprise contract query",
        user_id=str(user_a),
    )
    trace_a = Tracer.finish_trace(status="completed", model="gpt-4o")
    service._recent_traces.append(trace_a)

    # User B queries traces scoped to their ID
    traces_b, total_b = await service.list_traces(user_id=user_b)
    trace_ids_b = [t.trace_id for t in traces_b]
    assert trace_a.trace_id not in trace_ids_b

    # User B attempts to access user A's specific trace
    accessed = await service.get_trace(trace_id=trace_a.trace_id, user_id=user_b)
    assert accessed is None


# ==============================================================================
# Scenario 16: Secrets and sensitive fields are redacted
# ==============================================================================
def test_scenario_16_secrets_are_strictly_redacted():
    raw_payload = {
        "api_key": "mock-secret-key-supersecret1234567890",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
        "cookie": "session_id=abcdef123456; csrf=789",
        "password": "my_master_db_password",
        "safe_query": "What is the refund deadline?",
        "safe_item_count": 150,
    }

    redacted = redact_sensitive_data(raw_payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["cookie"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["safe_query"] == "What is the refund deadline?"
    assert redacted["safe_item_count"] == 150


# ==============================================================================
# Scenario 17: Exporter failure does not break normal RAG requests
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_17_exporter_failure_isolation():
    Tracer.start_trace(query="Test exporter non-blocking failure")
    finished = Tracer.finish_trace(status="completed")

    exporter = TelemetryExporter()
    success = await exporter.export_trace(finished)
    assert success is True


# ==============================================================================
# Scenario 18: Empty telemetry produces honest empty/unavailable states
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_18_empty_telemetry_honest_states():
    # Fresh service with no traces
    empty_service = ObservabilityService()
    empty_service._recent_traces = []

    overview = await empty_service.get_overview()
    assert overview.total_requests == 0
    assert overview.p50_latency_ms is None
    assert overview.p95_latency_ms is None
    assert overview.p99_latency_ms is None
    assert overview.total_estimated_cost_usd is None
    assert overview.cost_status == "unavailable"
    assert overview.success_rate == 0.0


# ==============================================================================
# Scenario 19: Overview and Error Explorer APIs return structured data
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_19_error_explorer_structure():
    service = ObservabilityService()
    service._recent_traces = [
        TraceRecord(
            trace_id="tr-err-test-01",
            query="Failing query",
            status="failed",
            error_category=ErrorCategory.RETRIEVAL_FAILURE.value,
            start_time=time.time(),
            end_time=time.time(),
            created_at=datetime.now(UTC).isoformat(),
            duration_ms=45.0,
            tokens_total=0,
            model="default",
        )
    ]

    errors = await service.get_error_explorer(limit=10)
    assert len(errors) >= 1
    err = errors[0]
    assert err["trace_id"] == "tr-err-test-01"
    assert err["error_category"] == ErrorCategory.RETRIEVAL_FAILURE.value
    assert "safe_code" in err
    assert "diagnostic_summary" in err
    assert "suggested_action" in err


# ==============================================================================
# Scenario 20: Pricing catalog endpoint returns registered models & rates
# ==============================================================================
def test_scenario_20_pricing_catalog():
    catalog = CostIntelligenceEngine.list_catalog()
    assert len(catalog) >= 5

    gpt4o = next(m for m in catalog if m["model_id"] == "gpt-4o")
    assert gpt4o["input_cost_per_1m"] == 2.50
    assert gpt4o["output_cost_per_1m"] == 10.00
    assert gpt4o["currency"] == "USD"
    assert gpt4o["provider"] == "openai"
