"""Comprehensive test suite for Phase 5 Hybrid Retrieval, RRF Fusion, and Neural Reranking."""

import io
import math
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.infrastructure.database.models import User
from app.infrastructure.embedding.mock_provider import MockEmbeddingProvider
from app.infrastructure.rerank.flashrank_reranker import FlashRankReranker
from app.infrastructure.rerank.mock_reranker import MockReranker
from app.schemas.retrieval import RetrievalMode, RetrievalRequest, RetrievalResultItem
from app.services.retrieval.bm25_retriever import tokenize_text
from app.services.retrieval.reciprocal_rank_fusion import ReciprocalRankFusion
from app.services.retrieval.retrieval_service import RetrievalService

# ==============================================================================
# 1. Unit Tests: Reciprocal Rank Fusion (Mathematical Correctness & Tie-Breaking)
# ==============================================================================


def test_rrf_mathematical_fusion_and_deduplication():
    """Verify RRF score formula: sum(1 / (k + rank)) and deduplication by chunk ID."""
    chunk_a = uuid4()
    chunk_b = uuid4()
    chunk_c = uuid4()

    doc_id = uuid4()

    # Vector results: chunk_a at rank 1, chunk_b at rank 2
    vec_results = [
        RetrievalResultItem(
            chunk_id=chunk_a,
            document_id=doc_id,
            document_name="doc.txt",
            content="content a",
            chunk_index=0,
            character_count=9,
            vector_rank=1,
            vector_score=0.95,
            final_rank=1,
            stage_provenance="vector",
        ),
        RetrievalResultItem(
            chunk_id=chunk_b,
            document_id=doc_id,
            document_name="doc.txt",
            content="content b",
            chunk_index=1,
            character_count=9,
            vector_rank=2,
            vector_score=0.85,
            final_rank=2,
            stage_provenance="vector",
        ),
    ]

    # Lexical results: chunk_b at rank 1, chunk_c at rank 2
    lex_results = [
        RetrievalResultItem(
            chunk_id=chunk_b,
            document_id=doc_id,
            document_name="doc.txt",
            content="content b",
            chunk_index=1,
            character_count=9,
            lexical_rank=1,
            lexical_score=4.5,
            final_rank=1,
            stage_provenance="lexical",
        ),
        RetrievalResultItem(
            chunk_id=chunk_c,
            document_id=doc_id,
            document_name="doc.txt",
            content="content c",
            chunk_index=2,
            character_count=9,
            lexical_rank=2,
            lexical_score=3.2,
            final_rank=2,
            stage_provenance="lexical",
        ),
    ]

    k = 60
    fused = ReciprocalRankFusion.fuse(vec_results, lex_results, rrf_k=k, candidate_limit=10)

    # Must contain 3 deduplicated items
    assert len(fused) == 3

    # chunk_b is present in both: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.016129 + 0.016393 = 0.032522
    expected_b = round(1.0 / (60 + 2) + 1.0 / (60 + 1), 6)
    b_item = next(item for item in fused if item.chunk_id == chunk_b)
    assert b_item.rrf_score == expected_b
    assert b_item.stage_provenance == "hybrid"
    assert b_item.vector_rank == 2
    assert b_item.lexical_rank == 1

    # chunk_b must be top ranked because it appeared in both retrievers
    assert fused[0].chunk_id == chunk_b
    assert fused[0].final_rank == 1

    # chunk_a: 1/(60+1) = 0.016393
    a_item = next(item for item in fused if item.chunk_id == chunk_a)
    assert a_item.rrf_score == round(1.0 / 61, 6)
    assert a_item.stage_provenance == "vector"

    # chunk_c: 1/(60+2) = 0.016129
    c_item = next(item for item in fused if item.chunk_id == chunk_c)
    assert c_item.rrf_score == round(1.0 / 62, 6)
    assert c_item.stage_provenance == "lexical"


def test_rrf_deterministic_tie_breaking():
    """Verify deterministic tie-breaking when two chunks have identical RRF scores."""
    chunk_1 = UUID("11111111-1111-1111-1111-111111111111")
    chunk_2 = UUID("22222222-2222-2222-2222-222222222222")
    doc_id = uuid4()

    # Both items have rank 1 from independent single sources
    vec_results = [
        RetrievalResultItem(
            chunk_id=chunk_1,
            document_id=doc_id,
            document_name="doc.txt",
            content="content 1",
            chunk_index=0,
            character_count=9,
            vector_rank=1,
            vector_score=0.90,
            final_rank=1,
            stage_provenance="vector",
        )
    ]
    lex_results = [
        RetrievalResultItem(
            chunk_id=chunk_2,
            document_id=doc_id,
            document_name="doc.txt",
            content="content 2",
            chunk_index=1,
            character_count=9,
            lexical_rank=1,
            lexical_score=5.0,
            final_rank=1,
            stage_provenance="lexical",
        )
    ]

    # chunk_1 has vector_score=0.90, chunk_2 has vector_score=None -> chunk_1 ranks ahead
    fused = ReciprocalRankFusion.fuse(vec_results, lex_results, rrf_k=60)
    assert len(fused) == 2
    assert fused[0].chunk_id == chunk_1
    assert fused[1].chunk_id == chunk_2


# ==============================================================================
# 2. Unit Tests: Cross-Encoder Reranker
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_reranker_scoring_and_ordering():
    """Verify mock reranker scores documents and returns top-k ordered by relevance."""
    reranker = MockReranker()
    query = "database indexes"
    docs = [
        {"id": "doc1", "content": "Database indexes improve query performance.", "original_rank": 1},
        {"id": "doc2", "content": "The weather today is cloudy with light rain.", "original_rank": 2},
    ]

    ranked = await reranker.rerank(query, docs, top_k=2)
    assert len(ranked) == 2
    assert ranked[0].document_id == "doc1"
    assert ranked[0].relevance_score > ranked[1].relevance_score


@pytest.mark.asyncio
async def test_flashrank_reranker_real_inference():
    """Verify FlashRank cross-encoder computes real probability scores via ONNX."""
    reranker = FlashRankReranker()
    query = "fastapi async routing"
    docs = [
        {"id": "match", "content": "FastAPI provides asynchronous routing built on Starlette and Pydantic."},
        {"id": "irrelevant", "content": "The Eiffel Tower is located in Paris, France."},
    ]

    ranked = await reranker.rerank(query, docs, top_k=2)
    assert len(ranked) == 2
    assert ranked[0].document_id == "match"
    # Match should score significantly higher than irrelevant passage
    assert ranked[0].relevance_score > ranked[1].relevance_score


# ==============================================================================
# 3. Integration Tests: Vector, BM25, and Hybrid Retrieval
# ==============================================================================


@pytest.mark.asyncio
async def test_vector_and_bm25_retrieval_integration(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
    user_a: User,
):
    """Integration test verifying vector search, BM25 keyword search, and hybrid fusion."""
    # 1. Create KB for User A
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Retrieval Test KB"},
        headers=auth_headers_user_a,
    )
    kb_id = UUID(res_kb.json()["data"]["id"])

    # 2. Upload and ingest document
    doc_content = (
        "PostgreSQL pgvector extension enables efficient similarity search using dense vectors.\n\n"
        "BM25 Okapi is a probabilistic lexical ranking algorithm based on term frequency and document length.\n\n"
        "Hybrid search combines vector similarity and BM25 using Reciprocal Rank Fusion."
    )
    files = {"file": ("architecture.txt", io.BytesIO(doc_content.encode("utf-8")), "text/plain")}
    res_up = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    doc_id = UUID(res_up.json()["data"]["id"])

    # Synchronous pipeline execution for test
    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc_id)

    # 3. Test Vector Search
    retrieval = RetrievalService(db_session, embedding_provider=MockEmbeddingProvider(), reranker=MockReranker())

    req_vec = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="pgvector similarity search",
        mode=RetrievalMode.VECTOR,
        enable_reranking=False,
    )
    res_vec = await retrieval.search(req_vec, user_a.id)
    assert res_vec.returned_count > 0
    assert res_vec.mode == "vector"
    assert res_vec.results[0].vector_score is not None

    # 4. Test BM25 Lexical Search with exact keyword
    req_lex = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="probabilistic lexical ranking",
        mode=RetrievalMode.LEXICAL,
        enable_reranking=False,
    )
    res_lex = await retrieval.search(req_lex, user_a.id)
    assert res_lex.returned_count > 0
    assert res_lex.mode == "lexical"
    assert res_lex.results[0].lexical_score is not None
    assert "BM25" in res_lex.results[0].content

    # 5. Test Hybrid Search with RRF + Reranking
    req_hyb = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="hybrid search Reciprocal Rank Fusion",
        mode=RetrievalMode.HYBRID,
        enable_reranking=True,
    )
    res_hyb = await retrieval.search(req_hyb, user_a.id)
    assert res_hyb.returned_count > 0
    assert res_hyb.mode == "hybrid"
    assert res_hyb.results[0].rrf_score is not None
    assert res_hyb.results[0].reranker_score is not None
    assert res_hyb.latency.total_ms > 0


@pytest.mark.asyncio
async def test_cross_user_knowledge_base_retrieval_isolation(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """User B cannot retrieve documents from User A's Knowledge Base (rejected with 404)."""
    # User A creates KB
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Alice Private KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    # User B attempts search against User A's KB
    search_payload = {
        "knowledge_base_id": kb_id,
        "query": "confidential specs",
        "mode": "hybrid",
    }
    res_b = await client.post("/api/v1/retrieval/search", json=search_payload, headers=auth_headers_user_b)
    assert res_b.status_code == 404
    assert res_b.json()["error"]["code"] == "KNOWLEDGE_BASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_unauthenticated_retrieval_rejected(client: AsyncClient):
    """Unauthenticated search request must return 401."""
    random_kb = uuid4()
    res = await client.post(
        "/api/v1/retrieval/search",
        json={"knowledge_base_id": str(random_kb), "query": "test query"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_empty_knowledge_base_returns_empty_results(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Searching an empty Knowledge Base returns empty result set without errors."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Empty KB"},
        headers=auth_headers_user_a,
    )
    kb_id = res_kb.json()["data"]["id"]

    res_search = await client.post(
        "/api/v1/retrieval/search",
        json={"knowledge_base_id": kb_id, "query": "anything", "mode": "hybrid"},
        headers=auth_headers_user_a,
    )
    assert res_search.status_code == 200
    data = res_search.json()["data"]
    assert data["returned_count"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_no_match_query_returns_empty_results(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """Query with terms completely absent from corpus returns 0 lexical matches."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Specific KB"},
        headers=auth_headers_user_a,
    )
    kb_id = UUID(res_kb.json()["data"]["id"])

    files = {"file": ("apple.txt", io.BytesIO(b"Apples are sweet red or green fruits."), "text/plain")}
    res_up = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    doc_id = UUID(res_up.json()["data"]["id"])

    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc_id)

    # Search for completely non-existent keyword in lexical mode
    res_search = await client.post(
        "/api/v1/retrieval/search",
        json={
            "knowledge_base_id": str(kb_id),
            "query": "supercalifragilisticexpialidocious_xyz123",
            "mode": "lexical",
        },
        headers=auth_headers_user_a,
    )
    assert res_search.status_code == 200
    assert res_search.json()["data"]["returned_count"] == 0


@pytest.mark.asyncio
async def test_comparison_endpoint_returns_all_three_modes(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """POST /api/v1/retrieval/compare returns vector, lexical, and hybrid results side-by-side."""
    res_kb = await client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Compare KB"},
        headers=auth_headers_user_a,
    )
    kb_id = UUID(res_kb.json()["data"]["id"])

    files = {"file": ("data.txt", io.BytesIO(b"Artificial intelligence machine learning deep learning."), "text/plain")}
    res_up = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    doc_id = UUID(res_up.json()["data"]["id"])

    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc_id)

    res_comp = await client.post(
        "/api/v1/retrieval/compare",
        json={"knowledge_base_id": str(kb_id), "query": "artificial intelligence", "top_k": 3},
        headers=auth_headers_user_a,
    )
    assert res_comp.status_code == 200
    data = res_comp.json()["data"]
    assert "vector_results" in data
    assert "lexical_results" in data
    assert "hybrid_results" in data
    assert "latency" in data


# ==============================================================================
# 4. Retrieval Evaluation Metrics (Recall@k, MRR@k, nDCG@k)
# ==============================================================================


def calculate_retrieval_metrics(
    retrieved_chunk_ids: list[UUID],
    relevant_chunk_ids: set[UUID],
    k: int = 5,
) -> dict[str, float]:
    """Computes standard Information Retrieval metrics: Recall@k, MRR@k, nDCG@k."""
    top_k_retrieved = retrieved_chunk_ids[:k]
    if not relevant_chunk_ids:
        return {"recall_at_k": 0.0, "mrr_at_k": 0.0, "ndcg_at_k": 0.0}

    # 1. Recall@k: proportion of relevant chunks retrieved
    hits = sum(1 for cid in top_k_retrieved if cid in relevant_chunk_ids)
    recall_at_k = hits / len(relevant_chunk_ids)

    # 2. MRR@k: reciprocal rank of the first relevant chunk
    mrr_at_k = 0.0
    for idx, cid in enumerate(top_k_retrieved, start=1):
        if cid in relevant_chunk_ids:
            mrr_at_k = 1.0 / idx
            break

    # 3. nDCG@k: normalized discounted cumulative gain
    dcg = 0.0
    for idx, cid in enumerate(top_k_retrieved, start=1):
        rel = 1.0 if cid in relevant_chunk_ids else 0.0
        dcg += rel / math.log2(idx + 1)

    # Ideal DCG (all relevant items ranked at the top)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant_chunk_ids), k) + 1))
    ndcg_at_k = dcg / idcg if idcg > 0.0 else 0.0

    return {
        "recall_at_k": round(recall_at_k, 4),
        "mrr_at_k": round(mrr_at_k, 4),
        "ndcg_at_k": round(ndcg_at_k, 4),
    }


def test_retrieval_evaluation_metrics_computation():
    """Verify Recall@k, MRR@k, and nDCG@k mathematical calculation."""
    c1, c2, c3, c4 = uuid4(), uuid4(), uuid4(), uuid4()
    relevant = {c2, c4}

    # Case 1: First hit at rank 2, second at rank 4
    retrieved = [c1, c2, c3, c4]
    metrics = calculate_retrieval_metrics(retrieved, relevant, k=4)
    assert metrics["recall_at_k"] == 1.0  # both relevant retrieved
    assert metrics["mrr_at_k"] == 0.5  # first hit at rank 2 -> 1/2
    assert 0.0 < metrics["ndcg_at_k"] <= 1.0

    # Case 2: Zero hits
    retrieved_zero = [c1, c3]
    metrics_zero = calculate_retrieval_metrics(retrieved_zero, relevant, k=2)
    assert metrics_zero["recall_at_k"] == 0.0
    assert metrics_zero["mrr_at_k"] == 0.0
    assert metrics_zero["ndcg_at_k"] == 0.0


# ==============================================================================
# 5. Unit Tests: Query Validation, Vector Mathematics, and Edge Cases
# ==============================================================================


def test_query_whitespace_and_empty_validation():
    """Verify empty and whitespace-only queries are strictly rejected by schema."""
    kb_id = uuid4()
    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="")

    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="   \t\n   ")


def test_invalid_top_k_and_candidate_limit_validation():
    """Verify top_k and candidate_limit boundary constraints."""
    kb_id = uuid4()
    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="valid query", top_k=0)

    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="valid query", top_k=51)

    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="valid query", candidate_limit=0)

    with pytest.raises(ValidationError):
        RetrievalRequest(knowledge_base_id=kb_id, query="valid query", candidate_limit=101)


def test_cosine_similarity_mathematical_precision():
    """Verify cosine similarity normalization: (cos_sim + 1.0) / 2.0."""
    import numpy as np

    # Identical vectors -> cos_sim = 1.0 -> normalized = 1.0
    v1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    v2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
    norm_score = (cos_sim + 1.0) / 2.0
    assert math.isclose(norm_score, 1.0, abs_tol=1e-5)

    # Orthogonal vectors -> cos_sim = 0.0 -> normalized = 0.5
    v_orth1 = np.array([1.0, 0.0], dtype=np.float32)
    v_orth2 = np.array([0.0, 1.0], dtype=np.float32)
    cos_orth = float(np.dot(v_orth1, v_orth2) / (np.linalg.norm(v_orth1) * np.linalg.norm(v_orth2)))
    norm_orth = (cos_orth + 1.0) / 2.0
    assert math.isclose(norm_orth, 0.5, abs_tol=1e-5)

    # Opposite vectors -> cos_sim = -1.0 -> normalized = 0.0
    v_opp1 = np.array([1.0, 0.0], dtype=np.float32)
    v_opp2 = np.array([-1.0, 0.0], dtype=np.float32)
    cos_opp = float(np.dot(v_opp1, v_opp2) / (np.linalg.norm(v_opp1) * np.linalg.norm(v_opp2)))
    norm_opp = max(0.0, (cos_opp + 1.0) / 2.0)
    assert math.isclose(norm_opp, 0.0, abs_tol=1e-5)


def test_bm25_tokenization_and_term_frequency_ranking():
    """Verify BM25 tokenization and scoring gives higher rank to higher term frequency."""
    from rank_bm25 import BM25Plus

    # Tokenizer preserves technical terms and alphanumeric tokens
    tokens = tokenize_text("FastAPI v0.115.0 & PostgreSQL pgvector!")
    assert "fastapi" in tokens
    assert "postgresql" in tokens
    assert "pgvector" in tokens

    doc1_tokens = ["rag", "agent", "retrieval", "retrieval", "retrieval"]
    doc2_tokens = ["rag", "agent", "retrieval", "unrelated", "tokens"]
    corpus = [doc1_tokens, doc2_tokens]

    bm25 = BM25Plus(corpus)
    scores = bm25.get_scores(["retrieval"])
    # Doc 1 has higher frequency of 'retrieval' than Doc 2
    assert scores[0] > scores[1]


# ==============================================================================
# 6. Integration Tests: Reranking Truthfulness, Failures, and KB Scoping
# ==============================================================================


class FailingReranker:
    """Mock reranker that simulates runtime failure or timeout."""

    @property
    def model_name(self) -> str:
        return "failing-model"

    async def rerank(self, query: str, documents: list[dict], top_k: int = 5):
        raise RuntimeError("ONNX inference device timeout or memory error")


@pytest.mark.asyncio
async def test_reranker_optional_failure_truthfulness(
    db_session: AsyncSession,
    user_a: User,
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """When reranking fails in optional mode, reranking_applied must be False and warning recorded."""
    # 1. Create KB
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Fallback KB"}, headers=auth_headers_user_a)
    kb_id = UUID(res_kb.json()["data"]["id"])

    # 2. Upload document
    files = {"file": ("fallback.txt", io.BytesIO(b"Semantic retrieval test content."), "text/plain")}
    res_up = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    doc_id = UUID(res_up.json()["data"]["id"])

    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc_id)

    # 3. Search with FailingReranker and optional reranking (default)
    service = RetrievalService(
        session=db_session,
        embedding_provider=MockEmbeddingProvider(),
        reranker=FailingReranker(),  # type: ignore[arg-type]
    )

    req = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="retrieval",
        mode=RetrievalMode.HYBRID,
        enable_reranking=True,
        reranking_required=False,
    )

    response = await service.search(req, user_a.id)
    # Must report reranking was NOT applied
    assert response.reranking_applied is False
    assert len(response.warnings) > 0
    assert "Neural reranking failed" in response.warnings[0]
    # No fake reranker score
    assert response.results[0].reranker_score is None


@pytest.mark.asyncio
async def test_reranker_required_failure_raises_error(
    db_session: AsyncSession,
    user_a: User,
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """When reranking is marked required and fails, request must raise AppError (502)."""
    res_kb = await client.post("/api/v1/knowledge-bases", json={"name": "Strict KB"}, headers=auth_headers_user_a)
    kb_id = UUID(res_kb.json()["data"]["id"])

    files = {"file": ("strict.txt", io.BytesIO(b"Strict reranking required content."), "text/plain")}
    res_up = await client.post(f"/api/v1/knowledge-bases/{kb_id}/documents", files=files, headers=auth_headers_user_a)
    doc_id = UUID(res_up.json()["data"]["id"])

    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc_id)

    service = RetrievalService(
        session=db_session,
        embedding_provider=MockEmbeddingProvider(),
        reranker=FailingReranker(),  # type: ignore[arg-type]
    )

    req = RetrievalRequest(
        knowledge_base_id=kb_id,
        query="strict",
        mode=RetrievalMode.HYBRID,
        enable_reranking=True,
        reranking_required=True,
    )

    with pytest.raises(AppError) as exc_info:
        await service.search(req, user_a.id)

    assert exc_info.value.code == "RERANKING_FAILED"
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_knowledge_base_path_search_endpoint_and_cross_kb_isolation(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_session: AsyncSession,
):
    """POST /api/v1/knowledge-bases/{id}/search works and prevents cross-KB leakage within the same user."""
    # 1. User A creates KB 1 and KB 2
    res_kb1 = await client.post("/api/v1/knowledge-bases", json={"name": "Alpha KB"}, headers=auth_headers_user_a)
    kb1_id = res_kb1.json()["data"]["id"]

    res_kb2 = await client.post("/api/v1/knowledge-bases", json={"name": "Beta KB"}, headers=auth_headers_user_a)
    kb2_id = res_kb2.json()["data"]["id"]

    # Ingest document into KB 1
    files1 = {"file": ("alpha.txt", io.BytesIO(b"Alpha project secret blueprint quantum computing."), "text/plain")}
    res_up1 = await client.post(
        f"/api/v1/knowledge-bases/{kb1_id}/documents",
        files=files1,
        headers=auth_headers_user_a,
    )
    doc1_id = UUID(res_up1.json()["data"]["id"])

    # Ingest document into KB 2
    files2 = {"file": ("beta.txt", io.BytesIO(b"Beta project confidential sales targets robotics."), "text/plain")}
    res_up2 = await client.post(
        f"/api/v1/knowledge-bases/{kb2_id}/documents",
        files=files2,
        headers=auth_headers_user_a,
    )
    doc2_id = UUID(res_up2.json()["data"]["id"])

    from app.services.ingestion_service import IngestionService

    ingestion = IngestionService(db_session, embedding_provider=MockEmbeddingProvider())
    await ingestion.run_ingestion_pipeline(doc1_id)
    await ingestion.run_ingestion_pipeline(doc2_id)

    # 2. Search KB 1 using the path endpoint
    search_payload = {"query": "quantum computing", "top_k": 5, "mode": "hybrid"}
    res_search1 = await client.post(
        f"/api/v1/knowledge-bases/{kb1_id}/search",
        json=search_payload,
        headers=auth_headers_user_a,
    )
    assert res_search1.status_code == 200
    data1 = res_search1.json()["data"]
    assert data1["returned_count"] > 0
    # Every chunk must belong to KB 1's doc1
    for item in data1["results"]:
        assert item["document_id"] == str(doc1_id)
        assert item["document_id"] != str(doc2_id)

    # 3. Search KB 2 using the path endpoint for KB 1 keywords
    res_search2 = await client.post(
        f"/api/v1/knowledge-bases/{kb2_id}/search",
        json={"query": "quantum computing", "mode": "lexical"},
        headers=auth_headers_user_a,
    )
    assert res_search2.status_code == 200
    # Must NOT find any chunks from KB 1 in KB 2
    assert res_search2.json()["data"]["returned_count"] == 0


@pytest.mark.asyncio
async def test_whitespace_and_invalid_params_rejected_at_api_level(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """API returns 422 for empty query or invalid top_k."""
    dummy_kb = uuid4()
    # Whitespace-only query
    res1 = await client.post(
        "/api/v1/retrieval/search",
        json={"knowledge_base_id": str(dummy_kb), "query": "   \n\t  "},
        headers=auth_headers_user_a,
    )
    assert res1.status_code == 422

    # Invalid top_k
    res2 = await client.post(
        "/api/v1/retrieval/search",
        json={"knowledge_base_id": str(dummy_kb), "query": "valid query", "top_k": 0},
        headers=auth_headers_user_a,
    )
    assert res2.status_code == 422
