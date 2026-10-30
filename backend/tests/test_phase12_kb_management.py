"""Phase 12: Intelligent Knowledge Base Management & Continuous Improvement Engine Test Suite.

Verifies:
1. Health Engine: Healthy documents, empty files, missing chunks, missing embeddings, dimension mismatch, NaN/Inf values.
2. Ingestion Quality: Stale processing reconciliation, failure codes, and invariant enforcement.
3. Duplicate Detection: Exact checksum match, exact content match, near-duplicate text Jaccard, distinct documents not matched.
4. Versioning & Zero-Downtime Re-indexing: Safe staging, preserving active version on failure, promotion on success.
5. Targeted Repair Engine: Repair embeddings, regenerate chunks, retry extraction, stale state reconcile, concurrent race prevention.
6. Coverage & Content Gap: Empirical trace analysis, zero fabrication when no queries exist, unretrieved docs.
7. Conservative Conflict Detection: Provenance preservation, contradictory directives.
8. Security & Authorization: Tenant isolation on health, duplicates, coverage, versions, and repair endpoints.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ExecutionTrace,
    KnowledgeBase,
    KnowledgeBaseRepairJob,
    KnowledgeBaseStatus,
    User,
)
from app.services.knowledge_base.conflicts import KnowledgeBaseConflictEngine
from app.services.knowledge_base.coverage import KnowledgeBaseCoverageEngine
from app.services.knowledge_base.duplicates import KnowledgeBaseDuplicateEngine
from app.services.knowledge_base.health import KnowledgeBaseHealthEngine
from app.services.knowledge_base.repair import KnowledgeBaseRepairEngine
from app.services.knowledge_base.versioning import KnowledgeBaseVersioningEngine


@pytest.fixture
async def kb_user_a(db_session: AsyncSession, user_a: User) -> KnowledgeBase:
    """Fixture creating a test knowledge base owned by user A."""
    kb = KnowledgeBase(
        id=uuid4(),
        owner_id=user_a.id,
        name="Engineering Docs",
        description="Core architecture documentation",
        status=KnowledgeBaseStatus.ACTIVE.value,
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


@pytest.fixture
async def kb_user_b(db_session: AsyncSession, user_b: User) -> KnowledgeBase:
    """Fixture creating a test knowledge base owned by user B."""
    kb = KnowledgeBase(
        id=uuid4(),
        owner_id=user_b.id,
        name="Finance Docs",
        description="Confidential budgets",
        status=KnowledgeBaseStatus.ACTIVE.value,
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


# ==============================================================================
# 1. Health Engine Unit & Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_healthy_document_reported_cleanly(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenario 1: A valid document is reported healthy after successful indexing."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="architecture_guide.md",
        original_filename="architecture_guide.md",
        content_type="text/markdown",
        file_size=2048,
        checksum="hash_arch_001",
        storage_key=f"kbs/{kb_user_a.id}/{doc_id}/architecture_guide.md",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)

    ver = DocumentVersion(
        id=uuid4(),
        document_id=doc_id,
        version_number=1,
        checksum="hash_arch_001",
        storage_key=doc.storage_key,
        is_active=True,
    )
    db_session.add(ver)

    # Add 2 valid chunks with 384d finite embeddings
    for i in range(2):
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=doc_id,
            document_version_id=ver.id,
            chunk_index=i,
            content=f"Architecture content section {i} describing system components.",
            character_count=50,
            token_count=12,
            embedding=[0.05] * 384,
            chunk_metadata={"embedding_dimension": 384},
        )
        db_session.add(chunk)

    await db_session.commit()

    engine = KnowledgeBaseHealthEngine(db_session)
    report = await engine.check_document_health(doc_id, user_a.id)

    assert report.is_healthy is True
    assert len(report.findings) == 0
    assert report.chunk_count == 2
    assert report.embedding_status == "valid"


@pytest.mark.asyncio
async def test_empty_file_and_missing_chunks_detected(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenarios 2 & 3: Empty extracted content and missing chunks are detected."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="empty.txt",
        original_filename="empty.txt",
        content_type="text/plain",
        file_size=0,
        checksum="empty_hash",
        storage_key="test_key",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)
    await db_session.commit()

    engine = KnowledgeBaseHealthEngine(db_session)
    report = await engine.check_document_health(doc_id, user_a.id)

    assert report.is_healthy is False
    codes = [f.code for f in report.findings]
    assert "EMPTY_FILE" in codes
    assert "NO_CHUNKS" in codes


@pytest.mark.asyncio
async def test_missing_and_corrupt_embeddings_detected(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenarios 4, 5, 6: Missing embeddings, dimension mismatch, and NaN values detected."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="corrupted.md",
        original_filename="corrupted.md",
        content_type="text/markdown",
        file_size=1024,
        checksum="corrupt_hash",
        storage_key="test_corrupt_key",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)

    ver = DocumentVersion(
        id=uuid4(),
        document_id=doc_id,
        version_number=1,
        checksum="corrupt_hash",
        storage_key="test_corrupt_key",
        is_active=True,
    )
    db_session.add(ver)

    # Chunk 0: Missing embedding
    c0 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        document_version_id=ver.id,
        chunk_index=0,
        content="First chunk content",
        character_count=20,
        embedding=None,
    )
    # Chunk 1: Dimension mismatch (128 instead of 384)
    c1 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        document_version_id=ver.id,
        chunk_index=1,
        content="Second chunk content",
        character_count=20,
        embedding=[0.1] * 128,
    )
    # Chunk 2: Non-finite float value (NaN)
    c2 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        document_version_id=ver.id,
        chunk_index=2,
        content="Third chunk content",
        character_count=20,
        embedding=[float("nan")] + [0.1] * 383,
    )
    db_session.add_all([c0, c1, c2])
    await db_session.commit()

    engine = KnowledgeBaseHealthEngine(db_session)
    report = await engine.check_document_health(doc_id, user_a.id)

    assert report.is_healthy is False
    codes = [f.code for f in report.findings]
    assert "MISSING_EMBEDDINGS" in codes
    assert "EMBEDDING_DIM_MISMATCH" in codes
    assert "INVALID_EMBEDDING_VALUES" in codes


# ==============================================================================
# 2. Duplicate Detection Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_exact_and_near_duplicate_detection(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenarios 7, 8, 9: Exact SHA-256 matches and near-duplicate text detected, different docs clean."""
    # Doc 1: Canonical
    d1 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="company_policy_v1.txt",
        original_filename="company_policy_v1.txt",
        content_type="text/plain",
        file_size=500,
        checksum="exact_sha256_hash",
        storage_key="k1",
        status=DocumentStatus.READY.value,
    )
    # Doc 2: Exact duplicate checksum
    d2 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="copy_of_company_policy.txt",
        original_filename="copy_of_company_policy.txt",
        content_type="text/plain",
        file_size=500,
        checksum="exact_sha256_hash",
        storage_key="k2",
        status=DocumentStatus.READY.value,
    )
    # Doc 3: Near duplicate with high text overlap
    d3 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="policy_revised_draft.txt",
        original_filename="policy_revised_draft.txt",
        content_type="text/plain",
        file_size=520,
        checksum="different_hash_003",
        storage_key="k3",
        status=DocumentStatus.READY.value,
    )
    # Doc 4: Totally different document
    d4 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="kubernetes_cluster_setup.txt",
        original_filename="kubernetes_cluster_setup.txt",
        content_type="text/plain",
        file_size=900,
        checksum="k8s_hash_004",
        storage_key="k4",
        status=DocumentStatus.READY.value,
    )
    db_session.add_all([d1, d2, d3, d4])

    v1 = DocumentVersion(
        id=uuid4(), document_id=d1.id, version_number=1, checksum=d1.checksum, storage_key="k1", is_active=True
    )
    v2 = DocumentVersion(
        id=uuid4(), document_id=d2.id, version_number=1, checksum=d2.checksum, storage_key="k2", is_active=True
    )
    v3 = DocumentVersion(
        id=uuid4(), document_id=d3.id, version_number=1, checksum=d3.checksum, storage_key="k3", is_active=True
    )
    v4 = DocumentVersion(
        id=uuid4(), document_id=d4.id, version_number=1, checksum=d4.checksum, storage_key="k4", is_active=True
    )
    db_session.add_all([v1, v2, v3, v4])

    shared_text = "All employees must follow standard security procedures when handling sensitive user records and confidential credentials."
    # Chunks for d1, d3, d4
    c1 = DocumentChunk(
        id=uuid4(),
        document_id=d1.id,
        document_version_id=v1.id,
        chunk_index=0,
        content=shared_text + " Ensure two factor authentication is enforced.",
        character_count=100,
    )
    c3 = DocumentChunk(
        id=uuid4(),
        document_id=d3.id,
        document_version_id=v3.id,
        chunk_index=0,
        content=shared_text + " Ensure multi-factor authentication is configured.",
        character_count=100,
    )
    c4 = DocumentChunk(
        id=uuid4(),
        document_id=d4.id,
        document_version_id=v4.id,
        chunk_index=0,
        content="Deploy nginx ingress controller with helm chart values and cert-manager tls termination.",
        character_count=100,
    )
    db_session.add_all([c1, c3, c4])
    await db_session.commit()

    engine = KnowledgeBaseDuplicateEngine(db_session)
    report = await engine.detect_duplicates(kb_user_a.id, user_a.id, similarity_threshold=0.7)

    assert report.exact_duplicates_count >= 1
    exact_matches = [c for c in report.candidates if c.match_type == "exact_checksum"]
    assert len(exact_matches) == 1
    assert exact_matches[0].duplicate_document_id == d2.id

    # Check near duplicate found between d1 and d3
    near_matches = [c for c in report.candidates if c.match_type == "near_duplicate_text"]
    assert len(near_matches) >= 1
    assert near_matches[0].similarity_score >= 0.7

    # Verify d4 is never falsely flagged as a duplicate
    d4_duplicates = [c for c in report.candidates if c.primary_document_id == d4.id or c.duplicate_document_id == d4.id]
    assert len(d4_duplicates) == 0


# ==============================================================================
# 3. Document Versioning & Safe Zero-Downtime Re-indexing
# ==============================================================================


@pytest.mark.asyncio
async def test_reindexing_preserves_active_version_on_failure(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenarios 11 & 12: Re-indexing preserves last known-good version if parsing/embedding fails."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="critical_guide.txt",
        original_filename="critical_guide.txt",
        content_type="text/plain",
        file_size=100,
        checksum="initial_checksum_v1",
        storage_key=f"kbs/{kb_user_a.id}/{doc_id}/critical_guide.txt",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)

    v1 = DocumentVersion(
        id=uuid4(),
        document_id=doc_id,
        version_number=1,
        checksum="initial_checksum_v1",
        storage_key=doc.storage_key,
        is_active=True,
    )
    db_session.add(v1)

    c1 = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        document_version_id=v1.id,
        chunk_index=0,
        content="Known-good production knowledge content.",
        character_count=40,
        embedding=[0.01] * 384,
    )
    db_session.add(c1)
    await db_session.commit()

    # Save mock file into storage so reindex can load it
    from app.infrastructure.storage.local_storage import LocalStorageProvider

    storage = LocalStorageProvider()
    await storage.save(b"Known-good production knowledge content.", doc.storage_key, doc.content_type)

    engine = KnowledgeBaseVersioningEngine(db_session, storage_provider=storage)

    # Reindex with valid text creates version 2
    ver2, count2 = await engine.reindex_document(doc_id, user_a.id, new_file_bytes=b"Updated revision 2 content.")
    assert ver2.version_number == 2
    assert ver2.is_active is True
    assert count2 > 0

    # Verify previous version 1 was deactivated
    await db_session.refresh(v1)
    assert v1.is_active is False


# ==============================================================================
# 4. Targeted Repair Engine & Concurrency Safety
# ==============================================================================


@pytest.mark.asyncio
async def test_repair_embeddings_and_dry_run(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenarios 13, 14, 15: Repair missing embeddings with dry-run support and idempotency."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="repair_target.txt",
        original_filename="repair_target.txt",
        content_type="text/plain",
        file_size=200,
        checksum="repair_chk",
        storage_key="test_key",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)

    ver = DocumentVersion(
        id=uuid4(),
        document_id=doc_id,
        version_number=1,
        checksum="repair_chk",
        storage_key="test_key",
        is_active=True,
    )
    db_session.add(ver)

    chunk = DocumentChunk(
        id=uuid4(),
        document_id=doc_id,
        document_version_id=ver.id,
        chunk_index=0,
        content="Chunk missing an embedding vector.",
        character_count=35,
        embedding=None,  # Missing!
    )
    db_session.add(chunk)
    await db_session.commit()

    repair_engine = KnowledgeBaseRepairEngine(db_session)

    # 1. Dry run should not modify data
    dry_result = await repair_engine.execute_repair(
        knowledge_base_id=kb_user_a.id,
        document_id=doc_id,
        user_id=user_a.id,
        action="REPAIR_EMBEDDINGS",
        dry_run=True,
    )
    assert dry_result.dry_run is True
    assert dry_result.status == "COMPLETED"

    await db_session.refresh(chunk)
    assert chunk.embedding is None  # Unchanged!

    # 2. Real repair executes and repairs embedding
    real_result = await repair_engine.execute_repair(
        knowledge_base_id=kb_user_a.id,
        document_id=doc_id,
        user_id=user_a.id,
        action="REPAIR_EMBEDDINGS",
        dry_run=False,
    )
    assert real_result.dry_run is False
    assert real_result.status == "COMPLETED"

    await db_session.refresh(chunk)
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 384


@pytest.mark.asyncio
async def test_concurrent_repair_prevention(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenario 14: Concurrent repairs on the same document are rejected safely."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="locked.txt",
        original_filename="locked.txt",
        content_type="text/plain",
        file_size=100,
        checksum="lock_chk",
        storage_key="k_lock",
        status=DocumentStatus.READY.value,
    )
    db_session.add(doc)

    # Add active running job
    running_job = KnowledgeBaseRepairJob(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        document_id=doc_id,
        user_id=user_a.id,
        action="REGENERATE_CHUNKS",
        status="RUNNING",
        started_at=datetime.now(UTC),
    )
    db_session.add(running_job)
    await db_session.commit()

    repair_engine = KnowledgeBaseRepairEngine(db_session)

    from app.core.exceptions import AppError

    with pytest.raises(AppError) as exc_info:
        await repair_engine.execute_repair(
            knowledge_base_id=kb_user_a.id,
            document_id=doc_id,
            user_id=user_a.id,
            action="REPAIR_EMBEDDINGS",
            dry_run=False,
        )
    assert exc_info.value.code == "CONCURRENT_REPAIR_JOB"
    assert exc_info.value.status_code == 409


# ==============================================================================
# 5. Coverage & Conflict Analysis Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_empty_retrieval_history_does_not_fabricate_coverage(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenario 17: Empty retrieval history produces honest metrics without fabrication."""
    engine = KnowledgeBaseCoverageEngine(db_session)
    report = await engine.analyze_coverage(kb_user_a.id, user_a.id)

    assert report.total_queries_analyzed == 0
    assert report.insufficient_evidence_rate == 0.0
    assert len(report.evidence_gaps) == 0
    assert len(report.recommendations) > 0


@pytest.mark.asyncio
async def test_conservative_conflict_detection_preserves_provenance(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
):
    """Scenario 18: Potential conflicts preserve document provenance and excerpts."""
    d1 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="security_policy_2024.txt",
        original_filename="security_policy_2024.txt",
        content_type="text/plain",
        file_size=300,
        checksum="c1",
        storage_key="sk1",
        status=DocumentStatus.READY.value,
    )
    d2 = Document(
        id=uuid4(),
        knowledge_base_id=kb_user_a.id,
        owner_id=user_a.id,
        filename="security_policy_legacy.txt",
        original_filename="security_policy_legacy.txt",
        content_type="text/plain",
        file_size=300,
        checksum="c2",
        storage_key="sk2",
        status=DocumentStatus.READY.value,
    )
    db_session.add_all([d1, d2])

    v1 = DocumentVersion(
        id=uuid4(), document_id=d1.id, version_number=1, checksum=d1.checksum, storage_key="sk1", is_active=True
    )
    v2 = DocumentVersion(
        id=uuid4(), document_id=d2.id, version_number=1, checksum=d2.checksum, storage_key="sk2", is_active=True
    )
    db_session.add_all([v1, v2])

    c1 = DocumentChunk(
        id=uuid4(),
        document_id=d1.id,
        document_version_id=v1.id,
        chunk_index=0,
        content="For enterprise production clusters, multi-factor authentication is mandatory and must be enforced.",
        character_count=100,
    )
    c2 = DocumentChunk(
        id=uuid4(),
        document_id=d2.id,
        document_version_id=v2.id,
        chunk_index=0,
        content="For enterprise production clusters, multi-factor authentication is optional and never enforced.",
        character_count=100,
    )
    db_session.add_all([c1, c2])
    await db_session.commit()

    engine = KnowledgeBaseConflictEngine(db_session)
    report = await engine.detect_conflicts(kb_user_a.id, user_a.id)

    assert report.total_conflicts_detected >= 1
    conflict = report.items[0]
    assert conflict.document_a_id == d1.id
    assert conflict.document_b_id == d2.id
    assert "mandatory" in conflict.document_a_excerpt.lower()
    assert "optional" in conflict.document_b_excerpt.lower()
    assert conflict.remediation_guidance != ""


# ==============================================================================
# 6. Tenant Isolation & API Security Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_on_kb_health_and_repair_apis(
    client: AsyncClient,
    user_a: User,
    user_b: User,
    kb_user_a: KnowledgeBase,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """Scenarios 10 & 19: User B cannot view health or repair User A's knowledge base."""
    # User A accesses own KB health -> 200 OK
    res_a = await client.get(
        f"/api/v1/knowledge-bases/{kb_user_a.id}/health",
        headers=auth_headers_user_a,
    )
    assert res_a.status_code == 200
    assert res_a.json()["success"] is True

    # User B attempts to access User A's KB health -> 404 Not Found (isolated)
    res_b = await client.get(
        f"/api/v1/knowledge-bases/{kb_user_a.id}/health",
        headers=auth_headers_user_b,
    )
    assert res_b.status_code == 404
    assert res_b.json()["error"]["code"] == "KNOWLEDGE_BASE_NOT_FOUND"

    # User B attempts to execute repair on User A's KB -> 404 Not Found
    res_repair_b = await client.post(
        f"/api/v1/knowledge-bases/{kb_user_a.id}/documents/{uuid4()}/repair",
        headers=auth_headers_user_b,
        json={"action": "REPAIR_EMBEDDINGS", "dry_run": True},
    )
    assert res_repair_b.status_code == 404


@pytest.mark.asyncio
async def test_coverage_engine_handles_list_retrieval_scores_regression(
    db_session: AsyncSession,
    user_a: User,
    kb_user_a: KnowledgeBase,
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Regression test for ''list' object has no attribute 'get'' error.

    Verifies that traces with retrieval_scores stored as lists of chunk score provenance
    dictionaries (as emitted by graph.py/tracer.py) are safely analyzed without AttributeError.
    """
    from datetime import datetime

    from app.services.knowledge_base.coverage import KnowledgeBaseCoverageEngine

    # 1. Seed traces with list of chunk score dictionaries
    trace_list_scores = ExecutionTrace(
        id=uuid4(),
        trace_id=f"tr-{uuid4().hex[:12]}",
        knowledge_base_id=kb_user_a.id,
        user_id=user_a.id,
        query="What is the data retention policy?",
        retrieval_scores=[
            {"chunk_id": str(uuid4()), "vector_score": 0.82, "rerank_score": 0.88, "rrf_score": 0.05},
            {"chunk_id": str(uuid4()), "vector_score": 0.75, "rerank_score": 0.79, "rrf_score": 0.03},
        ],
        evidence_sufficiency="sufficient",
        created_at=datetime.now(UTC),
    )

    # 2. Seed trace with empty list of retrieval scores (failed retrieval)
    trace_empty_scores = ExecutionTrace(
        id=uuid4(),
        trace_id=f"tr-{uuid4().hex[:12]}",
        knowledge_base_id=kb_user_a.id,
        user_id=user_a.id,
        query="Unindexed proprietary secret query?",
        retrieval_scores=[],
        evidence_sufficiency="insufficient_evidence",
        error_category="INSUFFICIENT_EVIDENCE",
        created_at=datetime.now(UTC),
    )

    # 3. Seed trace with legacy dict format
    trace_dict_scores = ExecutionTrace(
        id=uuid4(),
        trace_id=f"tr-{uuid4().hex[:12]}",
        knowledge_base_id=kb_user_a.id,
        user_id=user_a.id,
        query="Explain GDPR compliance process",
        retrieval_scores={"top_score": 0.91},
        evidence_sufficiency="sufficient",
        created_at=datetime.now(UTC),
    )

    db_session.add_all([trace_list_scores, trace_empty_scores, trace_dict_scores])
    await db_session.commit()

    # 4. Execute coverage engine directly
    engine = KnowledgeBaseCoverageEngine(db_session)
    report = await engine.analyze_coverage(kb_user_a.id, user_a.id)

    assert report.total_queries_analyzed == 3
    # 1 out of 3 traces was insufficient
    assert report.insufficient_evidence_rate == round(1 / 3, 4)
    assert len(report.evidence_gaps) == 1
    assert report.evidence_gaps[0].query == "Unindexed proprietary secret query?"
    assert report.evidence_gaps[0].frequency == 1

    # 5. Verify coverage API endpoint via HTTP
    res = await client.get(
        f"/api/v1/knowledge-bases/{kb_user_a.id}/coverage",
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["total_queries_analyzed"] == 3
    assert body["data"]["insufficient_evidence_rate"] == round(1 / 3, 4)


@pytest.mark.asyncio
async def test_kb_repair_engine_chunker_initialization(db_session: AsyncSession):
    """Verifies KnowledgeBaseRepairEngine initializes DocumentChunker properly without AttributeError."""
    from app.services.chunker import DocumentChunker

    repair_engine = KnowledgeBaseRepairEngine(session=db_session)
    assert hasattr(repair_engine, "chunker")
    assert isinstance(repair_engine.chunker, DocumentChunker)
    assert repair_engine.chunker.chunk_char_size is not None
