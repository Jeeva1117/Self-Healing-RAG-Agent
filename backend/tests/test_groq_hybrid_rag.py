"""Automated tests for Groq LLM integration and Hybrid RAG behavior.

Covers:
1. Grounded answer with valid citations from retrieved document evidence.
2. General question without relevant document evidence -> General AI answer without fabricated citations.
3. Missing private policy inquiry -> Honest insufficient evidence refusal without hallucinations.
4. Mixed question handling.
5. Missing API key -> Clear configuration error (LLM_CONFIG_ERROR).
6. Invalid API key -> Handled authentication error (LLM_AUTH_ERROR) without secret leakage.
7. Rate limit (429) & timeout handling -> Bounded retry behavior.
8. Irrelevant retrieval results -> Not presented as evidence.
9. Citation IDs refer strictly to real retrieved sources.
10. Opt-in live Groq smoke test.
"""

import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.domain.interfaces.llm import LLMMessage, LLMResponse
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    KnowledgeBase,
    User,
)
from app.infrastructure.llm.groq_provider import GroqProvider, redact_secret
from app.schemas.chat import ChatRequest, ChatResponseStatus
from app.services.agent.graph import AgenticRAGOrchestrator


class MockGroqProvider(GroqProvider):
    """Deterministic mock provider simulating Groq API behaviors."""

    def __init__(self, response_text: str = "Mock answer [1]", model: str = "llama-3.3-70b-versatile"):
        super().__init__(api_key="mock_groq_test_key_1234567890", model=model)
        self.response_text = response_text
        self.invocation_count = 0
        self.last_messages: list[LLMMessage] = []

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        self.invocation_count += 1
        self.last_messages = messages
        return LLMResponse(
            content=self.response_text,
            model=self.model,
            prompt_tokens=50,
            completion_tokens=30,
            total_tokens=80,
            metadata={"provider": "groq", "model": self.model},
        )


@pytest.fixture
async def groq_test_env(db_session: AsyncSession, user_a: User):
    """Seeds a test knowledge base with Python technical guide chunks."""
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="Groq Test Docs",
        description="Python functions and syntax docs",
    )
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        owner_id=user_a.id,
        filename="python_functions.pdf",
        original_filename="Python_Functions.pdf",
        content_type="application/pdf",
        file_size=1024,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_functions.pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(doc)
    await db_session.flush()

    ver = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=1,
        checksum=doc.checksum,
        storage_key=doc.storage_key,
        is_active=True,
    )
    db_session.add(ver)
    await db_session.flush()

    chunk_functions = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        document_version_id=ver.id,
        chunk_index=1,
        content=(
            "Functions in Python are defined using the def keyword. "
            "They accept parameters and return values using the return statement [1]. "
            "Arguments can be passed by position or keyword."
        ),
        character_count=180,
        page_number=2,
        section_title="Defining Functions",
        embedding=[0.05] * 384,
    )
    db_session.add(chunk_functions)
    await db_session.flush()

    return {"kb": kb, "doc": doc, "chunk": chunk_functions}


# ==============================================================================
# 1. Relevant PDF evidence -> Groq invocation -> grounded answer with valid citations
# ==============================================================================

@pytest.mark.asyncio
async def test_grounded_answer_with_valid_citations(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 1: Relevant evidence invokes Groq LLM, producing answer with genuine citations."""
    kb = groq_test_env["kb"]
    expected_chunk_id = groq_test_env["chunk"].id

    mock_llm = MockGroqProvider(
        response_text="Functions in Python are defined with the def keyword and return values using return [1]."
    )
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="How do functions work in Python?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status in (ChatResponseStatus.ANSWERED, ChatResponseStatus.RECOVERED)
    assert resp.is_insufficient_evidence is False
    assert mock_llm.invocation_count >= 1
    assert resp.generation is not None
    assert resp.generation.llm_invoked is True
    assert resp.evidence is not None
    assert resp.evidence.has_relevant_evidence is True
    assert len(resp.citations) == 1
    assert resp.citations[0].chunk_id == expected_chunk_id
    assert resp.citations[0].title == "Python_Functions.pdf"
    assert resp.citations[0].page == 2


# ==============================================================================
# 2. No relevant evidence -> Groq general answer without fabricated citations
# ==============================================================================

@pytest.mark.asyncio
async def test_general_ai_answer_without_fabricated_citations(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 2: General questions without matching PDF evidence invoke Groq for general answer with 0 fake citations."""
    kb = groq_test_env["kb"]

    mock_llm = MockGroqProvider(
        response_text="Recursion is a programming technique where a function calls itself to solve smaller subproblems."
    )
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    # General concept question not present in the Python Functions doc
    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="Explain recursion in simple terms with a Python example",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id, max_retries=0)

    assert resp.status == ChatResponseStatus.ANSWERED
    assert resp.is_insufficient_evidence is False
    assert resp.answer_type == "general_ai"
    assert resp.verification_status == "general_ai_answer"
    # Never attach irrelevant PDF citations to a general question
    assert len(resp.citations) == 0
    assert resp.evidence is not None
    assert resp.evidence.has_relevant_evidence is False
    assert resp.generation is not None
    assert resp.generation.llm_invoked is True
    assert "recursion" in resp.content.lower()


# ==============================================================================
# 3. Missing private policy evidence -> honest refusal without hallucination
# ==============================================================================

@pytest.mark.asyncio
async def test_missing_policy_honest_refusal(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 3: Company policy inquiry absent from documents terminates with truthful insufficient evidence."""
    kb = groq_test_env["kb"]

    mock_llm = MockGroqProvider(response_text="We offer a 30-day refund policy.")
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="What is the refund period in our company policy?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id, max_retries=1)

    assert resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
    assert resp.is_insufficient_evidence is True
    assert "not find sufficient matching information" in resp.content.lower()
    assert len(resp.citations) == 0


# ==============================================================================
# 4. Mixed question -> Document claims cited, general explanation distinguished
# ==============================================================================

@pytest.mark.asyncio
async def test_mixed_question_behavior(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 4: Mixed query grounds document-specific facts while providing general explanation."""
    kb = groq_test_env["kb"]
    expected_chunk_id = groq_test_env["chunk"].id

    mock_llm = MockGroqProvider(
        response_text=(
            "According to the document, Python functions are declared using the def keyword [1]. "
            "In general programming theory, functions promote modularity and code reuse."
        )
    )
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="How do functions work in Python and why are functions useful in general programming?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status in (ChatResponseStatus.ANSWERED, ChatResponseStatus.RECOVERED)
    assert len(resp.citations) == 1
    assert resp.citations[0].chunk_id == expected_chunk_id


# ==============================================================================
# 5. Missing API key -> Clear configuration error
# ==============================================================================

def test_missing_api_key_configuration_failure():
    """Test 5: Empty or missing GROQ_API_KEY raises AppError(LLM_CONFIG_ERROR)."""
    provider = GroqProvider(api_key="")
    with pytest.raises(AppError) as exc_info:
        provider.validate_configuration()

    assert exc_info.value.code == "LLM_CONFIG_ERROR"
    assert "GROQ_API_KEY" in exc_info.value.message


# ==============================================================================
# 6. Invalid API key -> Handled authentication error without secret leakage
# ==============================================================================

@pytest.mark.asyncio
async def test_invalid_api_key_auth_error_no_secret_leak():
    """Test 6: HTTP 401 raises LLM_AUTH_ERROR without leaking raw key to exception or logs."""
    fake_secret = "mock_groq_super_secret_key_1234567890"
    provider = GroqProvider(api_key=fake_secret)

    mock_response = httpx.Response(
        status_code=401,
        json={"error": {"message": f"Invalid API key: {fake_secret}"}},
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(AppError) as exc_info:
            await provider.generate(messages=[LLMMessage(role="user", content="Hi")])

        assert exc_info.value.code == "LLM_AUTH_ERROR"
        assert exc_info.value.status_code == 401
        assert fake_secret not in exc_info.value.message


# ==============================================================================
# 7. Rate limit (429) & timeout -> Bounded retry behavior
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limit_and_timeout_bounded_retry():
    """Test 7: 429 rate limit triggers bounded retries up to max_retries before LLM_RATE_LIMIT."""
    provider = GroqProvider(api_key="mock_groq_valid_key_1234567890", max_retries=1)

    mock_429 = httpx.Response(
        status_code=429,
        text="Rate limit exceeded",
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_429) as mock_post:
        with pytest.raises(AppError) as exc_info:
            await provider.generate(messages=[LLMMessage(role="user", content="Hi")])

        assert exc_info.value.code == "LLM_RATE_LIMIT"
        assert exc_info.value.status_code == 429
        # Max retries = 1 -> Total 2 attempts
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_timeout_bounded_retry():
    """Test 7b: Request timeout triggers bounded retries before LLM_TIMEOUT."""
    provider = GroqProvider(api_key="mock_groq_valid_key_1234567890", max_retries=1, timeout_seconds=1.0)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Read timeout")) as mock_post:
        with pytest.raises(AppError) as exc_info:
            await provider.generate(messages=[LLMMessage(role="user", content="Hi")])

        assert exc_info.value.code == "LLM_TIMEOUT"
        assert exc_info.value.status_code == 504
        assert mock_post.call_count == 2


# ==============================================================================
# 8. Irrelevant retrieval results -> Not presented as evidence
# ==============================================================================

@pytest.mark.asyncio
async def test_irrelevant_chunks_not_presented_as_evidence(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 8: Chunks that have 0 relevance to query are rejected and not presented as evidence."""
    kb = groq_test_env["kb"]

    mock_llm = MockGroqProvider(response_text="General answer about biology.")
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    # Completely unrelated query to python functions doc
    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="Explain photosynthesis and cellular respiration in green plants",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id, max_retries=0)

    # Irrelevant chunks must not be cited
    assert len(resp.citations) == 0
    assert resp.evidence is not None
    assert resp.evidence.has_relevant_evidence is False


# ==============================================================================
# 9. Citation IDs refer strictly to real retrieved sources
# ==============================================================================

@pytest.mark.asyncio
async def test_citation_ids_refer_to_real_retrieved_sources(
    db_session: AsyncSession,
    user_a: User,
    groq_test_env: dict[str, Any],
):
    """Test 9: Fabricated citation markers like [99] are ignored and only real chunks are mapped."""
    kb = groq_test_env["kb"]
    expected_chunk_id = groq_test_env["chunk"].id

    mock_llm = MockGroqProvider(
        response_text="Functions use def keyword [1], but here is a hallucinated citation [99]."
    )
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=mock_llm)

    req = ChatRequest(
        knowledge_base_id=kb.id,
        prompt="How do functions work in Python?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    # Citation [99] should NOT create a fake citation source
    citation_chunk_ids = [c.chunk_id for c in resp.citations]
    assert expected_chunk_id in citation_chunk_ids
    assert len(resp.citations) == 1


# ==============================================================================
# 10. Secret Redaction Utility Tests
# ==============================================================================

def test_secret_redaction_utility():
    """Test 10: Secret redaction sanitizes gsk_ keys and Bearer tokens."""
    sample_gsk = "gsk_" + "1234567890abcdef123456"
    text_with_gsk = f"Error with key {sample_gsk} in request"
    redacted_gsk = redact_secret(text_with_gsk)
    assert sample_gsk not in redacted_gsk
    assert "***REDACTED_SECRET***" in redacted_gsk

    text_with_bearer = "Authorization header: Bearer abcdef1234567890abcdef123456"
    redacted_bearer = redact_secret(text_with_bearer)
    assert "Bearer abcdef1234567890" not in redacted_bearer


@pytest.mark.asyncio
async def test_groq_stream_error_decodes_bytes():
    """Test that stream errors with raw bytes decode cleanly and redact secrets without TypeError."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.core.exceptions import AppError
    from app.domain.interfaces.llm import LLMMessage

    provider = GroqProvider(api_key="test-key")
    fake_stream_resp = MagicMock()
    fake_stream_resp.status_code = 429
    fake_stream_resp.aread = AsyncMock(
        return_value=b'{"error": "rate_limit_exceeded for gsk_1234567890abcdef123456"}'
    )

    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_stream_context = MagicMock()
    mock_stream_context.__aenter__.return_value = fake_stream_resp
    mock_stream_context.__aexit__.return_value = None
    mock_client.stream.return_value = mock_stream_context

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AppError) as exc_info:
            async for _ in provider.generate_stream(
                messages=[LLMMessage(role="user", content="Hello")]
            ):
                pass

        assert exc_info.value.code == "LLM_STREAM_ERROR"
        assert exc_info.value.status_code == 502
        assert "gsk_1234567890abcdef123456" not in exc_info.value.message
        assert "***REDACTED_SECRET***" in exc_info.value.message


# ==============================================================================
# 11. Opt-In Live Groq Smoke Test
# ==============================================================================

@pytest.mark.asyncio
async def test_opt_in_live_groq_smoke_test():
    """Test 11: Live Groq API verification (OPT-IN ONLY).

    Runs only when LIVE_GROQ_TEST=true and GROQ_API_KEY is present in the environment.
    Never requires an API key in CI or default unit test runs.
    """
    from app.core.config import settings
    api_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")
    if os.getenv("LIVE_GROQ_TEST", "").lower() != "true" or not api_key:
        pytest.skip("Opt-in live Groq smoke test skipped. Set LIVE_GROQ_TEST=true and GROQ_API_KEY to run.")

    provider = GroqProvider(api_key=api_key)
    resp = await provider.generate(
        messages=[
            LLMMessage(role="system", content="You are a helpful assistant. Reply concisely in one sentence."),
            LLMMessage(role="user", content="What is 2 + 2?"),
        ],
        max_tokens=20,
    )

    assert resp.content is not None
    assert len(resp.content.strip()) > 0
    assert "4" in resp.content or "four" in resp.content.lower()
    assert resp.model == provider.model
