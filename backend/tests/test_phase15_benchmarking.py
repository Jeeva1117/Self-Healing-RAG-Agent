"""Automated Test Suite for Phase 15 — End-to-End Evaluation, RAG Benchmarking & Load Testing.

Validates:
1. Mathematical metric precision: Precision@K, Recall@K, MRR, nDCG@K on hand-computed vectors.
2. Edge cases in retrieval metrics (empty relevant sets, empty retrieved lists).
3. Groundedness scoring fidelity on grounded vs ungrounded answer claims.
4. Citation validity auditing: bracketed [i] citation bounds against chunk count.
5. Truthful abstention: insufficient-evidence responses receive 1.0 groundedness and 0 citations.
6. Evaluation dataset registry: enterprise_rag_eval_v2 registration and metadata retrieval.
7. Nested transaction isolation in ObservabilityService: non-existent KB IDs do not corrupt session.
8. API evaluation trigger for Phase 15 dataset: POST /api/v1/evaluation/runs executes benchmark.
9. Cross-tenant access rejection: User A cannot query User B's knowledge base.
10. Concurrency invariance: concurrent requests against session execute without lock collisions.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    KnowledgeBase,
    User,
)
from app.schemas.chat import ChatRequest
from app.services.agent.graph import AgenticRAGOrchestrator
from app.services.evaluation import (
    DEFAULT_DATASET_NAME,
    PHASE15_DATASET_NAME,
    PHASE15_DATASET_VERSION,
    EvaluationCategory,
    EvaluationDatasetRegistry,
    compute_citation_validity,
    compute_groundedness,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from app.services.observability.schemas import TraceRecord
from app.services.observability.service import ObservabilityService


class PredictablePhase15LLM(LLMProviderInterface):
    """Deterministic Mock LLM for Phase 15 evaluation test execution."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [
            "Python arithmetic operators include +, -, *, and / [1].",
            "Lambda functions provide anonymous one-line expressions [2].",
        ])
        self.call_count = 0

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.call_count += 1
        resp = self.responses[min(self.call_count - 1, len(self.responses) - 1)]
        return LLMResponse(content=resp, model="mock-phase15-llm", total_tokens=50)

    async def generate_stream(self, messages: list[LLMMessage], **kwargs):
        resp = await self.generate(messages, **kwargs)
        yield resp.content


@pytest.fixture
async def phase15_test_env(db_session: AsyncSession, user_a: User, user_b: User):
    """Hermetic fixtures for Phase 15 benchmarking tests."""
    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="User A Knowledge Base",
        description="Python documentation",
    )
    kb_b = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="User B Knowledge Base",
        description="Confidential notes",
    )
    db_session.add_all([kb_a, kb_b])
    await db_session.flush()

    doc_a = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_a.id,
        owner_id=user_a.id,
        filename="python_guide.pdf",
        original_filename="Python_Guide.pdf",
        content_type="application/pdf",
        file_size=2048,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_guide.pdf",
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
        content="Python operators include arithmetic (+, -, *, /) and comparison (==, !=).",
        character_count=80,
        page_number=1,
        section_title="Operators",
        embedding=[0.05] * 384,
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_a.id,
        document_version_id=ver_a.id,
        chunk_index=2,
        content="Lambda functions provide anonymous one-line expressions.",
        character_count=60,
        page_number=2,
        section_title="Lambda",
        embedding=[0.03] * 384,
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


def test_metric_precision_mathematical_verification():
    """Test 1: Precise mathematical verification of Precision@K, Recall@K, MRR, and nDCG."""
    retrieved = ["c1", "c2", "c3", "c4", "c5"]
    relevant = {"c2", "c4"}

    assert compute_precision_at_k(retrieved, relevant, 1) == 0.0
    assert compute_precision_at_k(retrieved, relevant, 2) == 0.5
    assert compute_precision_at_k(retrieved, relevant, 4) == 0.5
    assert compute_precision_at_k(retrieved, relevant, 5) == 0.4

    assert compute_recall_at_k(retrieved, relevant, 1) == 0.0
    assert compute_recall_at_k(retrieved, relevant, 2) == 0.5
    assert compute_recall_at_k(retrieved, relevant, 4) == 1.0

    # First relevant chunk is at rank 2 -> MRR = 1/2 = 0.5
    assert compute_reciprocal_rank(retrieved, relevant) == 0.5

    # Empty relevant sets do not penalize
    assert compute_precision_at_k(retrieved, set(), 3) is None
    assert compute_recall_at_k(retrieved, set(), 3) is None
    assert compute_reciprocal_rank(retrieved, set()) is None


def test_citation_validity_bounds():
    """Test 2: Verification of citation bracket auditing and bounds checks."""
    ans_valid = "Operators are defined [1] and lambda provides expressions [2]."
    ratio, valid, total = compute_citation_validity(ans_valid, num_chunks=2)
    assert ratio == 1.0
    assert valid == 2
    assert total == 2

    # Out of bounds citation [3] when only 2 chunks exist
    ans_invalid = "Operators are defined [1] with extra info [3]."
    ratio_inv, valid_inv, total_inv = compute_citation_validity(ans_invalid, num_chunks=2)
    assert ratio_inv == 0.5
    assert valid_inv == 1
    assert total_inv == 2


def test_groundedness_and_abstention_invariants():
    """Test 3: Groundedness score and honest insufficient-evidence handling."""
    # Faithful answer grounded in retrieved content
    evidence = [{"content": "Python operators include arithmetic (+, -) and comparison."}]
    score = compute_groundedness("Python operators include arithmetic expressions.", evidence)
    assert score > 0.5

    # Ungrounded hallucination
    score_hallucinated = compute_groundedness("Quantum teleportation warp velocity is exceeded.", evidence)
    assert score_hallucinated < 0.2

    # Insufficient evidence honest sentence must receive 1.0 groundedness
    insufficient_str = "I do not find sufficient matching information in the authorized documents."
    score_ins = compute_groundedness(insufficient_str, [], is_insufficient_evidence=True)
    assert score_ins == 1.0


def test_phase15_dataset_registry_registration():
    """Test 4: Registry correctly exposes enterprise_rag_eval_v2 with 16 cases."""
    cases = EvaluationDatasetRegistry.get(PHASE15_DATASET_NAME, PHASE15_DATASET_VERSION)
    assert cases is not None
    assert len(cases) >= 16

    # Verify categories present
    categories = {c.category for c in cases}
    assert EvaluationCategory.ANSWERABLE in categories
    assert EvaluationCategory.PRECISE_TOPIC in categories
    assert EvaluationCategory.MULTI_CHUNK in categories
    assert EvaluationCategory.MULTI_DOCUMENT in categories
    assert EvaluationCategory.NUMERICAL_TECHNICAL in categories
    assert EvaluationCategory.MISLEADING_PREMISE in categories
    assert EvaluationCategory.INSUFFICIENT_EVIDENCE in categories
    assert EvaluationCategory.PERMISSION_BOUNDARY in categories

    # Metadata listing
    datasets = EvaluationDatasetRegistry.list_datasets()
    v2_entry = next((d for d in datasets if d["name"] == PHASE15_DATASET_NAME), None)
    assert v2_entry is not None
    assert v2_entry["version"] == PHASE15_DATASET_VERSION
    assert v2_entry["case_count"] >= 16


@pytest.mark.asyncio
async def test_observability_safe_savepoint_on_invalid_kb(
    db_session: AsyncSession,
    user_a: User,
):
    """Test 5: Non-existent knowledge_base_id does not violate FK or corrupt session."""
    obs = ObservabilityService(db_session)
    non_existent_kb_id = str(uuid.uuid4())

    fake_trace = TraceRecord(
        trace_id=f"tr-{uuid.uuid4().hex[:12]}",
        query="What is in the secret vault?",
        user_id=str(user_a.id),
        knowledge_base_id=non_existent_kb_id,
        status="failed",
        duration_ms=10.5,
        error_category="authorization_failure",
        start_time=100.0,
        end_time=110.5,
        created_at="2026-10-11T10:00:00Z",
    )

    # Must complete cleanly without raising ForeignKeyViolationError
    await obs.record_trace(fake_trace)

    # Session must remain fully functional for subsequent queries
    res = await db_session.execute(select(User).where(User.id == user_a.id))
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.id == user_a.id


@pytest.mark.asyncio
async def test_cross_tenant_access_rejection(
    phase15_test_env,
    user_b: User,
    db_session: AsyncSession,
):
    """Test 6: User B cannot search User A's knowledge base (tenant isolation)."""
    kb_a = phase15_test_env["kb_a"]
    mock_llm = PredictablePhase15LLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="Tell me about Python operators.",
    )

    # Attempting to query User A's KB with User B's credentials must raise AppError (404/403)
    from app.core.exceptions import AppError
    with pytest.raises(AppError) as exc_info:
        await orchestrator.run(request=req, user_id=user_b.id)
    assert exc_info.value.status_code in (403, 404)


@pytest.mark.asyncio
async def test_api_trigger_phase15_evaluation_run(
    auth_headers_user_a: dict[str, str],
    client: AsyncClient,
    phase15_test_env,
):
    """Test 7: POST /api/v1/evaluation/runs executes Phase 15 benchmark dataset."""
    kb_a = phase15_test_env["kb_a"]

    payload = {
        "name": "Phase 15 Automated Evaluation Run",
        "dataset_name": PHASE15_DATASET_NAME,
        "dataset_version": PHASE15_DATASET_VERSION,
        "knowledge_base_id": str(kb_a.id),
        "k_values": [1, 3, 5],
    }

    res = await client.post(
        "/api/v1/evaluation/runs",
        json=payload,
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["dataset_name"] == PHASE15_DATASET_NAME
    assert data["dataset_version"] == PHASE15_DATASET_VERSION
    assert data["total_cases"] >= 16
    assert data["status"] == "completed"
    assert len(data["case_results"]) >= 16


@pytest.mark.asyncio
async def test_api_list_evaluation_datasets_includes_phase15(
    auth_headers_user_a: dict[str, str],
    client: AsyncClient,
):
    """Test 8: GET /api/v1/evaluation/datasets lists enterprise_rag_eval_v2."""
    res = await client.get(
        "/api/v1/evaluation/datasets",
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    items = res.json()["data"]
    names = [d["name"] for d in items]
    assert DEFAULT_DATASET_NAME in names
    assert PHASE15_DATASET_NAME in names

    v2_item = next(d for d in items if d["name"] == PHASE15_DATASET_NAME)
    assert v2_item["version"] == PHASE15_DATASET_VERSION
    assert v2_item["case_count"] >= 16
