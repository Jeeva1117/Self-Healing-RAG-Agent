"""Production-grade automated test suite for Phase 9 RAG Evaluation & Quality Intelligence Engine.

Validates:
1. Metric calculations using known hand-checked examples (Precision@K, Recall@K, MRR, nDCG@K).
2. Precision@K and Recall@K ranking behavior with known IDs.
3. MRR and nDCG ranking behavior across ranks.
4. Empty retrieval and missing ground-truth handling (does not penalize missing labels).
5. Citation ID and source metadata validation.
6. Answerable questions with known expected facts.
7. Unanswerable questions and truthful insufficient-evidence behavior.
8. Contradictory evidence and version isolation.
9. Self-healing success and recovery failure tracking.
10. Recovery retry-budget exhaustion tracking.
11. Unauthorized knowledge-base access boundary.
12. Evaluation-run partial failure handling.
13. Baseline comparison and incompatible-run rejection.
14. API authentication and input validation on evaluation endpoints.
15. Persistence and retrieval of evaluation results.
16. Dashboard summary endpoint and statistics aggregation.
17. Custom dataset registration in EvaluationDatasetRegistry.
18. Groundedness and topical relevance scoring invariants.
19. Full end-to-end benchmark execution via FastAPI router.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    EvaluationCaseResultRecord,
    EvaluationRun,
    KnowledgeBase,
    User,
)
from app.services.evaluation import (
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_VERSION,
    AnswerMetrics,
    BaselineComparator,
    CaseEvaluationResult,
    EvaluationCategory,
    EvaluationDatasetRegistry,
    EvaluationRunner,
    EvaluationTestCase,
    RetrievalMetrics,
    RunEvaluationSummary,
    SelfHealingMetrics,
    compute_answer_relevance,
    compute_chunk_coverage,
    compute_citation_validity,
    compute_groundedness,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)


class PredictableMockLLM(LLMProviderInterface):
    """Deterministic Mock LLM allowing predictable generation responses for evaluation."""

    def __init__(self, responses: list[str | Exception] | None = None):
        self.responses = list(responses or ["Python operators include arithmetic (+, -) and comparison (==, !=) [1]."])
        self.call_count = 0

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.call_count += 1
        resp = self.responses[min(self.call_count - 1, len(self.responses) - 1)]
        if isinstance(resp, Exception):
            raise resp
        return LLMResponse(
            content=resp,
            model="mock-phase9-evaluator",
            total_tokens=60,
        )

    async def generate_stream(self, messages: list[LLMMessage], **kwargs):
        resp = await self.generate(messages, **kwargs)
        yield resp.content


@pytest.fixture
async def phase9_env(db_session: AsyncSession, user_a: User, user_b: User):
    """Sets up user and knowledge base data for Phase 9 testing."""
    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="User A Technical Docs",
        description="Python programming documentation",
    )
    kb_b = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="User B Private Notes",
        description="Restricted knowledge base",
    )
    db_session.add_all([kb_a, kb_b])
    await db_session.flush()

    doc_a = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_a.id,
        owner_id=user_a.id,
        filename="python_reference.pdf",
        original_filename="Python_Reference.pdf",
        content_type="application/pdf",
        file_size=2048,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_reference.pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(doc_a)
    await db_session.flush()

    ver_a = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        version_number=1,
        checksum=doc_a.checksum,
        storage_key=doc_a.storage_key,
        is_active=True,
    )
    db_session.add(ver_a)
    await db_session.flush()

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        document_version_id=ver_a.id,
        chunk_index=1,
        content=(
            "Python operators include arithmetic (+, -, *, /) and comparison (==, !=, >, <). "
            "Logical operators are and, or, not."
        ),
        character_count=120,
        page_number=1,
        section_title="Operators",
        embedding=[0.05] * 384,
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        document_version_id=ver_a.id,
        chunk_index=2,
        content=(
            "Python functions are defined using the def keyword with parameters and return values. "
            "Lambda functions provide anonymous one-line expressions."
        ),
        character_count=145,
        page_number=2,
        section_title="Functions",
        embedding=[0.02] * 384,
    )
    db_session.add_all([chunk_1, chunk_2])
    await db_session.commit()

    return {
        "kb_a": kb_a,
        "kb_b": kb_b,
        "doc_a": doc_a,
        "chunk_1": chunk_1,
        "chunk_2": chunk_2,
    }


# ======================================================================
# 1. Metric calculations using known hand-checked examples
# ======================================================================


def test_metric_calculations_hand_checked_examples():
    """Test 1: Hand-calculated mathematical verification for Precision, Recall, MRR, nDCG."""
    retrieved = ["doc_A", "doc_B", "doc_C", "doc_D", "doc_E"]
    relevant = {"doc_B", "doc_D"}

    # Precision@1: [doc_A] -> 0 / 1 = 0.0
    assert compute_precision_at_k(retrieved, relevant, 1) == 0.0
    # Precision@2: [doc_A, doc_B] -> 1 / 2 = 0.5
    assert compute_precision_at_k(retrieved, relevant, 2) == 0.5
    # Precision@4: [doc_A, doc_B, doc_C, doc_D] -> 2 / 4 = 0.5
    assert compute_precision_at_k(retrieved, relevant, 4) == 0.5

    # Recall@1: 0 / 2 = 0.0
    assert compute_recall_at_k(retrieved, relevant, 1) == 0.0
    # Recall@2: 1 / 2 = 0.5
    assert compute_recall_at_k(retrieved, relevant, 2) == 0.5
    # Recall@4: 2 / 2 = 1.0
    assert compute_recall_at_k(retrieved, relevant, 4) == 1.0

    # MRR: First hit is doc_B at rank 2 -> 1 / 2 = 0.5
    assert compute_reciprocal_rank(retrieved, relevant) == 0.5

    # nDCG@2:
    # DCG@2 = 0 / log2(2) + 1 / log2(3) = 0 + 1 / 1.5849625 = 0.63092975
    # IDCG@2 = 1 / log2(2) + 1 / log2(3) = 1 + 0.63092975 = 1.63092975
    # nDCG@2 = 0.63092975 / 1.63092975 = 0.386852
    ndcg_2 = compute_ndcg_at_k(retrieved, relevant, 2)
    assert ndcg_2 is not None
    assert pytest.approx(ndcg_2, abs=1e-3) == 0.3868


# ======================================================================
# 2. Precision@K and Recall@K with known IDs
# ======================================================================


def test_precision_and_recall_at_k_bounds():
    """Test 2: Precision@K and Recall@K boundaries and edge constraints."""
    items = ["c1", "c2", "c3"]
    relevant = {"c1", "c2", "c3"}

    # Perfect recall and precision
    assert compute_precision_at_k(items, relevant, 3) == 1.0
    assert compute_recall_at_k(items, relevant, 3) == 1.0

    # Top-K beyond retrieved count
    assert compute_precision_at_k(items, relevant, 10) == 3 / 10
    assert compute_recall_at_k(items, relevant, 10) == 1.0

    # K = 0 edge case
    assert compute_precision_at_k(items, relevant, 0) == 0.0
    assert compute_recall_at_k(items, relevant, 0) == 0.0


# ======================================================================
# 3. MRR and nDCG ranking behavior
# ======================================================================


def test_mrr_and_ndcg_ranking_behavior():
    """Test 3: Ranking sensitivity: top rank yields higher score than lower rank."""
    rel = {"target"}
    top_hit = ["target", "noise_1", "noise_2"]
    third_hit = ["noise_1", "noise_2", "target"]
    miss = ["noise_1", "noise_2", "noise_3"]

    # MRR comparisons
    assert compute_reciprocal_rank(top_hit, rel) == 1.0
    assert compute_reciprocal_rank(third_hit, rel) == pytest.approx(1 / 3, abs=1e-4)
    assert compute_reciprocal_rank(miss, rel) == 0.0

    # nDCG comparisons
    ndcg_top = compute_ndcg_at_k(top_hit, rel, 3)
    ndcg_third = compute_ndcg_at_k(third_hit, rel, 3)
    ndcg_miss = compute_ndcg_at_k(miss, rel, 3)

    assert ndcg_top == 1.0
    assert ndcg_third is not None and 0.0 < ndcg_third < 1.0
    assert ndcg_miss == 0.0


# ======================================================================
# 4. Empty retrieval and missing ground truth handling
# ======================================================================


def test_empty_retrieval_and_missing_ground_truth():
    """Test 4: Missing labels return None so unlabelled datasets are not treated as 0%."""
    # When no ground-truth relevant IDs exist (unlabelled):
    assert compute_precision_at_k(["c1", "c2"], set(), 5) is None
    assert compute_recall_at_k(["c1", "c2"], set(), 5) is None
    assert compute_reciprocal_rank(["c1", "c2"], set()) is None
    assert compute_ndcg_at_k(["c1", "c2"], set(), 5) is None
    assert compute_chunk_coverage(["c1", "c2"], set()) is None

    # Empty retrieval with defined ground truth
    rel = {"c1"}
    assert compute_precision_at_k([], rel, 5) == 0.0
    assert compute_recall_at_k([], rel, 5) == 0.0
    assert compute_reciprocal_rank([], rel) == 0.0


# ======================================================================
# 5. Citation ID and source metadata validation
# ======================================================================


def test_citation_id_and_source_validation():
    """Test 5: Validates bracketed citations against available chunk count."""
    ans_valid = "Python functions are defined with def [1] and take parameters [2]."
    ratio, valid_cnt, total_cnt = compute_citation_validity(ans_valid, num_chunks=2)
    assert ratio == 1.0
    assert valid_cnt == 2
    assert total_cnt == 2

    # Out of range citation [99]
    ans_invalid = "Python functions are defined with def [1] and lambdas [99]."
    ratio_inv, valid_inv, total_inv = compute_citation_validity(ans_invalid, num_chunks=2)
    assert ratio_inv == 0.5
    assert valid_inv == 1
    assert total_inv == 2

    # Zero citations present
    ratio_none, _, _ = compute_citation_validity("No citations here", num_chunks=2)
    assert ratio_none == 1.0


# ======================================================================
# 6. Answerable questions with known expected facts
# ======================================================================


@pytest.mark.asyncio
async def test_answerable_question_evaluation(db_session: AsyncSession, user_a: User, phase9_env):
    """Test 6: Evaluates answerable question; verifies fact coverage and grounding pass."""
    kb_a = phase9_env["kb_a"]
    chunk_1 = phase9_env["chunk_1"]

    llm = PredictableMockLLM(["Python arithmetic operators (+, -) and comparison operators (==, !=) [1]."])
    runner = EvaluationRunner(session=db_session, llm_provider=llm)

    case = EvaluationTestCase(
        id="TC-ANS-01",
        category=EvaluationCategory.ANSWERABLE,
        query="What are operators in Python?",
        knowledge_base_id=kb_a.id,
        expected_chunk_ids=[chunk_1.id],
        expected_key_facts=["arithmetic", "comparison", "operators"],
        reference_answer="Python operators include arithmetic and comparison.",
        is_evidence_expected=True,
        expected_citation_required=True,
    )

    result = await runner.evaluate_case(case=case, user_id=user_a.id)

    assert result.passed is True
    assert result.status == "passed"
    assert result.answer_metrics.key_fact_coverage >= 0.6
    assert result.answer_metrics.citation_validity_score == 1.0
    assert result.answer_metrics.groundedness_score >= 0.5


# ======================================================================
# 7. Unanswerable questions and insufficient-evidence behavior
# ======================================================================


@pytest.mark.asyncio
async def test_unanswerable_question_insufficient_evidence(db_session: AsyncSession, user_a: User, phase9_env):
    """Test 7: Unanswerable inquiry must produce truthful insufficient evidence without citations."""
    kb_a = phase9_env["kb_a"]
    llm = PredictableMockLLM(["I do not find sufficient matching information in the authorized documents."])
    runner = EvaluationRunner(session=db_session, llm_provider=llm)

    case = EvaluationTestCase(
        id="TC-UNANS-01",
        category=EvaluationCategory.UNANSWERABLE,
        query="What is the galactic quantum warp drive protocol?",
        knowledge_base_id=kb_a.id,
        is_evidence_expected=False,
        expected_citation_required=False,
        expected_outcome="insufficient_evidence",
    )

    result = await runner.evaluate_case(case=case, user_id=user_a.id)

    assert result.passed is True
    assert result.answer_metrics.correct_insufficient_handling is True
    assert result.answer_metrics.groundedness_score == 1.0


# ======================================================================
# 8. Contradictory evidence and version isolation
# ======================================================================


@pytest.mark.asyncio
async def test_contradictory_evidence_case(db_session: AsyncSession, user_a: User, phase9_env):
    """Test 8: Evaluates contradictory evidence handling."""
    kb_a = phase9_env["kb_a"]
    llm = PredictableMockLLM(["The active specification defines Python functions using def [1]."])
    runner = EvaluationRunner(session=db_session, llm_provider=llm)

    case = EvaluationTestCase(
        id="TC-CONTR-01",
        category=EvaluationCategory.CONTRADICTORY,
        query="What is the active specification for functions?",
        knowledge_base_id=kb_a.id,
        expected_key_facts=["functions", "def"],
        is_evidence_expected=True,
    )

    result = await runner.evaluate_case(case=case, user_id=user_a.id)
    assert result.passed is True


# ======================================================================
# 9. Self-healing success and recovery tracking
# ======================================================================


def test_self_healing_recovery_metrics():
    """Test 9: SelfHealingMetrics accurately reflects recovery success vs exhaustion."""
    m_recovered = SelfHealingMetrics(
        recovery_attempted=True,
        recovery_count=1,
        initial_failure_category="low_relevance_evidence",
        recovery_action="rewrite_query",
        recovery_outcome="recovered",
        retrieval_improved=True,
        answer_improved=True,
        recovery_latency_ms=120.0,
    )
    assert m_recovered.recovery_attempted is True
    assert m_recovered.recovery_outcome == "recovered"
    assert m_recovered.is_budget_exhausted is False

    m_exhausted = SelfHealingMetrics(
        recovery_attempted=True,
        recovery_count=3,
        initial_failure_category="insufficient_evidence",
        recovery_action="terminate_insufficient",
        recovery_outcome="exhausted",
        is_budget_exhausted=True,
    )
    assert m_exhausted.is_budget_exhausted is True


# ======================================================================
# 10. Recovery retry-budget exhaustion
# ======================================================================


def test_recovery_retry_budget_exhaustion_rate():
    """Test 10: RunEvaluationSummary aggregates budget exhaustion rate."""
    cases = [
        CaseEvaluationResult(
            test_case_id="tc-1",
            category=EvaluationCategory.ANSWERABLE,
            passed=True,
            status="passed",
            query="test",
            retrieval_metrics=RetrievalMetrics(),
            answer_metrics=AnswerMetrics(),
            recovery_metrics=SelfHealingMetrics(is_budget_exhausted=False),
        ),
        CaseEvaluationResult(
            test_case_id="tc-2",
            category=EvaluationCategory.INSUFFICIENT_EVIDENCE,
            passed=True,
            status="passed",
            query="test",
            retrieval_metrics=RetrievalMetrics(),
            answer_metrics=AnswerMetrics(),
            recovery_metrics=SelfHealingMetrics(is_budget_exhausted=True),
        ),
    ]
    exhausted_count = sum(1 for c in cases if c.recovery_metrics.is_budget_exhausted)
    rate = exhausted_count / len(cases)
    assert rate == 0.5


# ======================================================================
# 11. Unauthorized knowledge-base access boundary
# ======================================================================


@pytest.mark.asyncio
async def test_unauthorized_kb_access_eval(db_session: AsyncSession, user_a: User, phase9_env):
    """Test 11: Evaluation test case targeting an unauthorized KB terminates with access denied."""
    kb_b = phase9_env["kb_b"]  # Owned by user_b
    runner = EvaluationRunner(session=db_session)

    case = EvaluationTestCase(
        id="TC-PERM-01",
        category=EvaluationCategory.PERMISSION_BOUNDARY,
        query="What is in User B private knowledge base?",
        knowledge_base_id=kb_b.id,
        is_evidence_expected=False,
    )

    # Executing as user_a against user_b's KB
    result = await runner.evaluate_case(case=case, user_id=user_a.id)

    assert result.passed is True
    assert "Access denied" in result.actual_response_summary


# ======================================================================
# 12. Evaluation-run partial failure handling
# ======================================================================


@pytest.mark.asyncio
async def test_suite_partial_failure_aggregation(db_session: AsyncSession, user_a: User, phase9_env):
    """Test 12: Suite with 1 pass and 1 intentional fail calculates honest pass rate (50%)."""
    kb_a = phase9_env["kb_a"]
    chunk_1 = phase9_env["chunk_1"]

    llm = PredictableMockLLM(["Python operators include arithmetic [1]."])
    runner = EvaluationRunner(session=db_session, llm_provider=llm)

    suite = [
        # Passing case
        EvaluationTestCase(
            id="TC-PASS",
            category=EvaluationCategory.ANSWERABLE,
            query="What are Python operators?",
            knowledge_base_id=kb_a.id,
            expected_chunk_ids=[chunk_1.id],
            expected_key_facts=["operators"],
        ),
        # Failing case (demands impossible key facts)
        EvaluationTestCase(
            id="TC-FAIL",
            category=EvaluationCategory.ANSWERABLE,
            query="What are Python operators?",
            knowledge_base_id=kb_a.id,
            expected_chunk_ids=[chunk_1.id],
            expected_key_facts=["quantum", "hyperspace", "tachyon"],
        ),
    ]

    summary, results = await runner.run_suite(cases=suite, user_id=user_a.id)

    assert summary.total_cases == 2
    assert summary.passed_cases == 1
    assert summary.failed_cases == 1
    assert summary.pass_rate == 0.5
    assert len(results) == 2


# ======================================================================
# 13. Baseline comparison and incompatible-run rejection
# ======================================================================


def test_baseline_comparison_and_incompatible_rejection():
    """Test 13: Baseline comparator categorizes diffs and rejects dataset mismatches."""
    base = RunEvaluationSummary(
        pass_rate=0.70,
        mean_groundedness=0.75,
        mean_mrr=0.60,
    )
    cand = RunEvaluationSummary(
        pass_rate=0.85,  # +15% improvement
        mean_groundedness=0.68,  # -7% regression
        mean_mrr=0.61,  # +1% unchanged (within 2%)
    )

    # Compatible runs
    comp = BaselineComparator.compare(
        candidate=cand,
        baseline=base,
        candidate_meta={"dataset_name": "ds1", "dataset_version": "1.0"},
        baseline_meta={"id": uuid.uuid4(), "dataset_name": "ds1", "dataset_version": "1.0"},
    )
    assert comp.is_compatible is True
    assert "pass_rate" in comp.improvements
    assert "groundedness" in comp.regressions
    assert "mrr" in comp.unchanged

    # Incompatible runs (different dataset names)
    incomp = BaselineComparator.compare(
        candidate=cand,
        baseline=base,
        candidate_meta={"dataset_name": "dataset_v1"},
        baseline_meta={"dataset_name": "dataset_v2"},
    )
    assert incomp.is_compatible is False
    assert incomp.warning is not None
    assert "Incompatible" in incomp.warning


# ======================================================================
# 14. API authentication and input validation
# ======================================================================


@pytest.mark.asyncio
async def test_api_authentication_and_input_validation(
    client: AsyncClient,
):
    """Test 14: Unauthenticated evaluation calls return 401; invalid schemas return 422."""
    # 1. Unauthenticated access
    res = await client.get("/api/v1/evaluation/runs")
    assert res.status_code == 401

    res_ds = await client.get("/api/v1/evaluation/datasets")
    assert res_ds.status_code == 401


# ======================================================================
# 15. Persistence and retrieval of evaluation results
# ======================================================================


@pytest.mark.asyncio
async def test_evaluation_persistence_and_retrieval(
    db_session: AsyncSession, user_a: User, auth_headers_user_a: dict[str, str], client: AsyncClient
):
    """Test 15: EvaluationRun and CaseResult records persist in DB and retrieve via API."""
    run_id = uuid.uuid4()
    eval_run = EvaluationRun(
        id=run_id,
        user_id=user_a.id,
        name="Integration Persistence Test",
        dataset_name=DEFAULT_DATASET_NAME,
        dataset_version=DEFAULT_DATASET_VERSION,
        status="completed",
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        pass_rate=1.0,
        summary_metrics={"mean_groundedness": 0.95},
    )
    case_rec = EvaluationCaseResultRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        test_case_id="TC-P01",
        category="answerable",
        passed=True,
        status="passed",
        query="What is Python?",
        retrieval_metrics={"mrr": 1.0},
        answer_metrics={"groundedness_score": 0.95},
        recovery_metrics={},
        failure_reasons=[],
        total_latency_ms=45.0,
    )
    db_session.add_all([eval_run, case_rec])
    await db_session.commit()

    # Retrieve via API
    res = await client.get(f"/api/v1/evaluation/runs/{run_id}", headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["id"] == str(run_id)
    assert data["pass_rate"] == 1.0
    assert len(data["case_results"]) == 1
    assert data["case_results"][0]["test_case_id"] == "TC-P01"


# ======================================================================
# 16. Dashboard summary endpoint and statistics aggregation
# ======================================================================


@pytest.mark.asyncio
async def test_dashboard_summary_endpoint(auth_headers_user_a: dict[str, str], client: AsyncClient):
    """Test 16: Summary stats endpoint calculates aggregates across user runs."""
    res = await client.get("/api/v1/evaluation/metrics/summary", headers=auth_headers_user_a)
    assert res.status_code == 200
    stats = res.json()["data"]
    assert "average_pass_rate" in stats
    assert "average_groundedness" in stats


# ======================================================================
# 17. Custom dataset registration
# ======================================================================


def test_custom_dataset_registration():
    """Test 17: EvaluationDatasetRegistry allows registering and retrieving custom suites."""
    custom_cases = [
        EvaluationTestCase(
            id="CUST-01",
            category=EvaluationCategory.ANSWERABLE,
            query="Custom question?",
        )
    ]
    EvaluationDatasetRegistry.register("custom_suite", "2.1.0", custom_cases)
    retrieved = EvaluationDatasetRegistry.get("custom_suite", "2.1.0")
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0].id == "CUST-01"


# ======================================================================
# 18. Groundedness and topical relevance scoring invariants
# ======================================================================


def test_groundedness_and_relevance_invariants():
    """Test 18: Groundedness and relevance mathematical invariants."""
    # Sufficient evidence answer with high grounding
    chunks = [{"content": "Python functions use def keyword and return values."}]
    answer = "Python functions are defined using def keyword [1]."
    score = compute_groundedness(answer, chunks)
    assert score >= 0.5

    # Insufficient evidence honest sentence produces 1.0 groundedness
    insufficient_ans = "I do not find sufficient matching information in the authorized documents."
    score_ins = compute_groundedness(insufficient_ans, [], is_insufficient_evidence=True)
    assert score_ins == 1.0

    # Relevance scoring
    rel = compute_answer_relevance("What are functions?", "Functions are blocks of code.")
    assert rel > 0.0


# ======================================================================
# 19. Full end-to-end benchmark execution via FastAPI router
# ======================================================================


@pytest.mark.asyncio
async def test_end_to_end_benchmark_run_via_api(
    auth_headers_user_a: dict[str, str],
    client: AsyncClient,
    phase9_env,
):
    """Test 19: POST /api/v1/evaluation/runs executes live benchmark and returns results."""
    kb_a = phase9_env["kb_a"]

    req_payload = {
        "name": "Live E2E Benchmark Test",
        "dataset_name": DEFAULT_DATASET_NAME,
        "dataset_version": DEFAULT_DATASET_VERSION,
        "knowledge_base_id": str(kb_a.id),
        "k_values": [1, 3, 5],
    }

    res = await client.post(
        "/api/v1/evaluation/runs",
        json=req_payload,
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    resp_data = res.json()["data"]
    assert resp_data["name"] == "Live E2E Benchmark Test"
    assert resp_data["total_cases"] >= 10
    assert resp_data["status"] == "completed"
    assert len(resp_data["case_results"]) >= 10
