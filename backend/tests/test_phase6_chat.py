"""Comprehensive integration test suite for Phase 6 grounded chat and citation generation."""

import uuid

import pytest
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    KnowledgeBase,
    User,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def seeded_chat_env(db_session: AsyncSession, user_a: User, user_b: User):
    """Sets up two isolated knowledge bases with documents and chunks for user_a and user_b."""
    # 1. User A's Python Knowledge Base
    kb_python = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="Python Documentation",
        description="Python beginner and intermediate concepts",
    )
    # 2. User A's Business Policy Knowledge Base
    kb_policy = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="Company Policies",
        description="HR and procurement policies",
    )
    # 3. User B's Private Knowledge Base
    kb_user_b = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="User B Confidential",
        description="Private notes",
    )
    db_session.add_all([kb_python, kb_policy, kb_user_b])
    await db_session.flush()

    # Document in Python KB
    doc_python = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_python.id,
        owner_id=user_a.id,
        filename="python_guide.pdf",
        original_filename="Python_Guide.pdf",
        content_type="application/pdf",
        file_size=2048,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_guide.pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(doc_python)
    await db_session.flush()

    ver_python = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_python.id,
        version_number=1,
        checksum=doc_python.checksum,
        storage_key=doc_python.storage_key,
        is_active=True,
    )
    db_session.add(ver_python)
    await db_session.flush()

    chunk_operators = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_python.id,
        document_version_id=ver_python.id,
        chunk_index=1,
        content=(
            "4. Operators in Python\n"
            "Arithmetic operators include addition (+), subtraction (-), multiplication (*), and division (/).\n"
            "Comparison operators include ==, !=, >, < for evaluating conditional expressions.\n"
            "Logical operators include and, or, not."
        ),
        character_count=230,
        page_number=3,
        section_title="4. Operators",
        embedding=[0.05] * 384,
    )
    chunk_strings = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_python.id,
        document_version_id=ver_python.id,
        chunk_index=2,
        content="Strings in Python are immutable sequences of Unicode characters. Slicing uses [start:stop].",
        character_count=98,
        page_number=4,
        section_title="Strings",
        embedding=[0.02] * 384,
    )
    db_session.add_all([chunk_operators, chunk_strings])

    # Document in Policy KB
    doc_policy = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_policy.id,
        owner_id=user_a.id,
        filename="refund_policy.pdf",
        original_filename="Refund_Policy.pdf",
        content_type="application/pdf",
        file_size=1024,
        checksum=uuid.uuid4().hex,
        storage_key="docs/refund_policy.pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(doc_policy)
    await db_session.flush()

    ver_policy = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_policy.id,
        version_number=1,
        checksum=doc_policy.checksum,
        storage_key=doc_policy.storage_key,
        is_active=True,
    )
    db_session.add(ver_policy)
    await db_session.flush()

    chunk_policy = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_policy.id,
        document_version_id=ver_policy.id,
        chunk_index=1,
        content="Enterprise customers are entitled to a standard 14-day refund window upon license termination.",
        character_count=101,
        page_number=1,
        section_title="Refund Windows",
        embedding=[0.01] * 384,
    )
    db_session.add(chunk_policy)

    await db_session.commit()

    return {
        "kb_python_id": kb_python.id,
        "kb_policy_id": kb_policy.id,
        "kb_user_b_id": kb_user_b.id,
        "chunk_operators_id": chunk_operators.id,
    }


@pytest.mark.asyncio
async def test_grounded_chat_answers_from_correct_knowledge_base(
    client: AsyncClient, auth_headers_user_a: dict[str, str], seeded_chat_env: dict
):
    """Validates that chat retrieves chunks from the specified KB and generates an answer grounded in that content."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_python_id"]),
        "prompt": "What are operators in Python?",
        "top_k": 5,
    }

    res = await client.post("/api/v1/chat", json=payload, headers=auth_headers_user_a)
    assert res.status_code == 200, res.text
    data = res.json()["data"]

    assert data["is_insufficient_evidence"] is False
    assert "operators" in data["content"].lower() or "arithmetic" in data["content"].lower()
    assert len(data["citations"]) > 0
    # Verifies cited chunk is from python doc
    assert data["citations"][0]["title"] == "Python_Guide.pdf"
    assert data["verification_status"] == "grounded_evidence"
    assert data["confidence"] is None  # Truthful: Phase 9 guardrails unexecuted


@pytest.mark.asyncio
async def test_chat_unanswered_question_reports_insufficient_evidence(
    client: AsyncClient, auth_headers_user_a: dict[str, str], seeded_chat_env: dict
):
    """Validates that asking a question not answered in the KB reports insufficient evidence."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_python_id"]),
        "prompt": "What is the enterprise refund policy?",
        "top_k": 5,
    }

    res = await client.post("/api/v1/chat", json=payload, headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["is_insufficient_evidence"] is True
    assert "not find sufficient" in data["content"].lower() or "insufficient" in data["content"].lower()
    assert len(data["citations"]) == 0
    assert data["verification_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_cross_kb_isolation_does_not_leak_chunks(
    client: AsyncClient, auth_headers_user_a: dict[str, str], seeded_chat_env: dict
):
    """Validates that scoping to Policy KB does not retrieve or ground Python content."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_policy_id"]),
        "prompt": "What are operators in Python?",
        "top_k": 5,
    }

    res = await client.post("/api/v1/chat", json=payload, headers=auth_headers_user_a)
    assert res.status_code == 200
    data = res.json()["data"]

    # Python content must not leak into Policy KB chat
    assert "python" not in data["content"].lower() or data["is_insufficient_evidence"] is True
    for c in data["citations"]:
        assert c["title"] != "Python_Guide.pdf"


@pytest.mark.asyncio
async def test_tenant_isolation_unauthorized_kb_denied(
    client: AsyncClient, auth_headers_user_a: dict[str, str], seeded_chat_env: dict
):
    """Validates that User A cannot chat with User B's knowledge base."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_user_b_id"]),
        "prompt": "What are operators in Python?",
    }

    res = await client.post("/api/v1/chat", json=payload, headers=auth_headers_user_a)
    assert res.status_code == 404
    err = res.json()["error"]
    assert err["code"] == "KNOWLEDGE_BASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_unauthenticated_chat_rejected(client: AsyncClient, seeded_chat_env: dict):
    """Validates that unauthenticated requests are rejected with 401."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_python_id"]),
        "prompt": "What are operators?",
    }
    res = await client.post("/api/v1/chat", json=payload)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_empty_knowledge_base_reports_insufficient_evidence(
    client: AsyncClient, auth_headers_user_b: dict[str, str], seeded_chat_env: dict
):
    """Validates that querying a knowledge base with no documents returns clean insufficient evidence."""
    payload = {
        "knowledge_base_id": str(seeded_chat_env["kb_user_b_id"]),
        "prompt": "Any information here?",
    }

    res = await client.post("/api/v1/chat", json=payload, headers=auth_headers_user_b)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_insufficient_evidence"] is True
    assert len(data["citations"]) == 0
