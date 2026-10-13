"""Comprehensive production test suite for Phase 8 Self-Healing Recovery Engine.

Validates:
1. Normal query succeeds without recovery.
2. Relevant answer and valid citations pass verification.
3. Empty retrieval triggers the correct bounded recovery path.
4. Low-relevance retrieval triggers an appropriate alternate strategy (query rewriting / expansion).
5. Persistent insufficient evidence ends safely.
6. Transient database or provider error follows retry policy.
7. Permanent authorization failure is never retried.
8. Invalid citation IDs are rejected/repaired.
9. Unsupported answers are not marked successful.
10. Recovery succeeds after a recoverable failure.
11. Recovery fails safely after exhausting retry budget.
12. Repeated identical recovery actions do not create infinite loops (cycle detection).
13. Workflow timeout terminates execution.
14. Recovery attempt cannot access another user's knowledge base (tenant isolation).
15. Malformed model output is handled safely.
16. Provider rate limits (429) do not cause unlimited retries.
17-20. Classifier, Policy, Rewriter, and Verifier unit invariants.
"""

import time
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    KnowledgeBase,
    User,
)
from app.schemas.chat import ChatRequest, ChatResponseStatus
from app.services.agent.graph import AgenticRAGOrchestrator
from app.services.recovery import (
    AnswerVerifier,
    FailureCategory,
    FailureClassifier,
    FailureDiagnosis,
    QueryRewriter,
    RecoveryAction,
    RecoveryPolicy,
)


class PredictableMockLLM(LLMProviderInterface):
    """Mock LLM allowing customizable per-call responses or exceptions."""

    def __init__(self, responses: list[str | Exception] | None = None):
        self.responses = list(responses or ["Python operators include arithmetic (+, -) and comparison (==, !=) [1]."])
        self.call_count = 0
        self.last_messages: list[LLMMessage] = []

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.call_count += 1
        self.last_messages = messages
        resp = self.responses[min(self.call_count - 1, len(self.responses) - 1)]
        if isinstance(resp, Exception):
            raise resp
        return LLMResponse(
            content=resp,
            model="mock-phase8-llm",
            total_tokens=64,
        )

    async def generate_stream(self, messages: list[LLMMessage], **kwargs):
        resp = await self.generate(messages, **kwargs)
        yield resp.content


@pytest.fixture
async def phase8_env(db_session: AsyncSession, user_a: User, user_b: User):
    """Sets up user and knowledge base data for Phase 8 recovery testing."""
    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="User A Technical Docs",
        description="Python documentation and reference",
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
# 1. Normal query succeeds without recovery
# ======================================================================

@pytest.mark.asyncio
async def test_normal_query_succeeds_without_recovery(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 1: Normal evidence-supported question completes on attempt 0 with ANSWERED status."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM(["Python operators include arithmetic and comparison operators [1]."])
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="What are Python operators?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status == ChatResponseStatus.ANSWERED
    assert resp.retry_count == 0
    assert resp.is_insufficient_evidence is False
    assert resp.verification_status == "grounded_evidence"
    assert len(resp.citations) == 1
    # Recovery was not needed
    if resp.recovery:
        assert resp.recovery.recovery_attempted is False
        assert resp.recovery.recovery_count == 0


# ======================================================================
# 2. Relevant answer and valid citations pass verification
# ======================================================================

@pytest.mark.asyncio
async def test_relevant_answer_and_valid_citations_pass_verification(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 2: Answer with valid citations passing AnswerVerifier is marked verified."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM(["Python functions are defined with def and parameters [1]."])
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="How are functions defined in Python?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status == ChatResponseStatus.ANSWERED
    assert resp.verification_status == "grounded_evidence"
    assert resp.citations[0].title == "Python_Guide.pdf"
    step_ids = [s.step_id for s in resp.workflow_steps]
    assert "answer_verification" in step_ids
    ver_step = next(s for s in resp.workflow_steps if s.step_id == "answer_verification")
    assert ver_step.status == "completed"


# ======================================================================
# 3. Empty retrieval triggers correct bounded recovery path
# ======================================================================

@pytest.mark.asyncio
async def test_empty_retrieval_triggers_bounded_recovery_path(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 3: Query retrieving zero chunks triggers bounded recovery loop."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="Tell me about corporate mergers and acquisitions warranty clauses",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
    assert resp.is_insufficient_evidence is True
    step_ids = [s.step_id for s in resp.workflow_steps]
    assert "bounded_retry" in step_ids
    assert resp.retry_count >= 1
    assert resp.recovery is not None
    assert resp.recovery.recovery_attempted is True


# ======================================================================
# 4. Low-relevance retrieval triggers query rewrite strategy
# ======================================================================

@pytest.mark.asyncio
async def test_low_relevance_retrieval_triggers_alternate_strategy():
    """Test 4: Low-relevance diagnosis correctly recommends query rewriting."""
    diag = FailureClassifier.classify_retrieval(
        error=None,
        results=[],
        query="Can you please explain operators in python?",
        terms=["operators", "python"],
    )
    assert diag.category == FailureCategory.LOW_RELEVANCE_EVIDENCE
    assert diag.suggested_action == RecoveryAction.REWRITE_QUERY
    assert diag.is_recoverable is True

    # Validate that rewriter strips conversational filler
    rewritten = QueryRewriter.rewrite(
        original_query="Can you please explain operators in python?",
        query_history=[],
        extracted_terms=["operators", "python"],
    )
    assert "can you please explain" not in rewritten.lower()
    assert "operators" in rewritten.lower()


# ======================================================================
# 5. Persistent insufficient evidence ends safely
# ======================================================================

@pytest.mark.asyncio
async def test_persistent_insufficient_evidence_ends_safely(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 5: Persistent insufficient evidence terminates with truthful response and no fake citations."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="What is the quantum teleportation protocol in interstellar communications?",
        top_k=5,
    )
    resp = await orchestrator.run(request=req, user_id=user_a.id)

    assert resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
    assert resp.is_insufficient_evidence is True
    assert "not find sufficient matching information" in resp.content.lower()
    assert len(resp.citations) == 0
    assert resp.recovery is not None
    assert resp.recovery.recovery_outcome in ("insufficient_evidence", "exhausted")


# ======================================================================
# 6. Transient database or provider error follows retry policy
# ======================================================================

@pytest.mark.asyncio
async def test_transient_database_or_provider_error_follows_retry_policy():
    """Test 6: Transient errors are classified as recoverable with RETRY_TRANSIENT action and backoff."""
    transient_errors = [
        Exception("Connection timeout while connecting to provider"),
        Exception("503 Service Unavailable: server overloaded"),
        Exception("429 Too Many Requests: rate limit exceeded"),
        Exception("Deadlock detected on transaction lock wait"),
    ]
    for err in transient_errors:
        diag = FailureClassifier.classify_retrieval(error=err)
        assert diag.category == FailureCategory.RETRIEVAL_FAILURE
        assert diag.is_recoverable is True
        assert diag.suggested_action == RecoveryAction.RETRY_TRANSIENT

    policy = RecoveryPolicy(max_attempts=2)
    action, reason, params = policy.evaluate(
        diagnosis=FailureDiagnosis(
            category=FailureCategory.RETRIEVAL_FAILURE,
            reason="Transient timeout",
            is_recoverable=True,
            suggested_action=RecoveryAction.RETRY_TRANSIENT,
        ),
        recovery_count=0,
        deadline=time.time() + 30.0,
    )
    assert action == RecoveryAction.RETRY_TRANSIENT
    assert "backoff_seconds" in params


# ======================================================================
# 7. Permanent authorization failure is never retried
# ======================================================================

@pytest.mark.asyncio
async def test_permanent_authorization_failure_never_retried(
    db_session: AsyncSession, user_b: User, phase8_env
):
    """Test 7: Access to unauthorized KB terminates immediately without retry."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="What are Python operators?",
    )

    with pytest.raises(AppError) as exc_info:
        await orchestrator.run(request=req, user_id=user_b.id)

    assert exc_info.value.code == "KNOWLEDGE_BASE_NOT_FOUND"
    # LLM was never called
    assert llm.call_count == 0


# ======================================================================
# 8. Invalid citation IDs are rejected/repaired
# ======================================================================

@pytest.mark.asyncio
async def test_invalid_citation_ids_are_rejected():
    """Test 8: Citations referencing non-existent chunk indexes fail verification."""
    fake_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        chunk_index=1,
        content="Python operators evaluate expressions.",
        character_count=40,
    )
    # Answer cites [99] when only 1 chunk exists
    passed, reason = AnswerVerifier.verify(
        query="What are operators?",
        answer="Operators evaluate expressions [99].",
        retrieved_chunks=[fake_chunk],
    )
    assert passed is False
    assert "non-existent citation index" in str(reason).lower()

    # Classification test
    diag = FailureClassifier.classify_citations(validation_passed=False, unmapped_indices=[99])
    assert diag.category == FailureCategory.CITATION_FAILURE
    assert diag.suggested_action == RecoveryAction.REPAIR_CITATIONS


# ======================================================================
# 9. Unsupported answers are not marked successful
# ======================================================================

@pytest.mark.asyncio
async def test_unsupported_answers_fail_verification():
    """Test 9: Answers containing claims totally unsupported by evidence fail verification."""
    fake_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        chunk_index=1,
        content="Python operators include arithmetic (+, -).",
        character_count=44,
    )
    # Answer discusses completely fabricated space warp mechanics
    passed, reason = AnswerVerifier.verify(
        query="What are Python operators?",
        answer="Interstellar spaceships travel through hyperspace wormholes at subatomic speeds [1].",
        retrieved_chunks=[fake_chunk],
    )
    assert passed is False
    assert "unsubstantiated" in str(reason).lower() or "topical overlap" in str(reason).lower()


# ======================================================================
# 10. Recovery succeeds after a recoverable failure
# ======================================================================

@pytest.mark.asyncio
async def test_recovery_succeeds_after_recoverable_failure(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 10: Initial generation failure recovers on feedback retry and marks status RECOVERED."""
    kb_a = phase8_env["kb_a"]
    # 1st attempt: ungrounded answer without citations (fails verification)
    # 2nd attempt: grounded answer with citation [1] (passes verification)
    llm = PredictableMockLLM([
        "Python operators are great features of the language.",  # Missing citations -> fails verifier
        "Python operators include arithmetic (+, -) and comparison (==, !=) [1].",  # Passes verifier
    ])
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="What are operators in Python?",
        top_k=5,
    )
    # Allow 1 recovery attempt
    resp = await orchestrator.run(request=req, user_id=user_a.id, max_retries=1)

    assert resp.status == ChatResponseStatus.RECOVERED
    assert resp.retry_count == 1
    assert resp.verification_status == "grounded_evidence"
    assert resp.recovery is not None
    assert resp.recovery.recovery_attempted is True
    assert resp.recovery.recovery_outcome == "recovered"
    assert len(resp.citations) >= 1


# ======================================================================
# 11. Recovery fails safely after exhausting retry budget
# ======================================================================

@pytest.mark.asyncio
async def test_recovery_fails_safely_after_exhausting_retry_budget(
    db_session: AsyncSession, user_a: User, phase8_env
):
    """Test 11: When retry budget is exhausted without evidence, pipeline terminates safely."""
    kb_a = phase8_env["kb_a"]
    llm = PredictableMockLLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="What is the international maritime shipping insurance clause 42?",
        top_k=5,
    )
    # Run with max_retries=2
    resp = await orchestrator.run(request=req, user_id=user_a.id, max_retries=2)

    assert resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
    assert resp.is_insufficient_evidence is True
    assert resp.retry_count >= 1
    assert resp.recovery is not None
    assert resp.recovery.recovery_outcome in ("insufficient_evidence", "exhausted")


# ======================================================================
# 12. Repeated identical recovery actions do not create infinite loops
# ======================================================================

@pytest.mark.asyncio
async def test_repeated_identical_recovery_actions_do_not_create_infinite_loops():
    """Test 12: Cycle detector in RecoveryPolicy pivots away from repeating identical actions."""
    policy = RecoveryPolicy(max_attempts=3)
    diag = FailureDiagnosis(
        category=FailureCategory.LOW_RELEVANCE_EVIDENCE,
        reason="Low relevance",
        is_recoverable=True,
        suggested_action=RecoveryAction.REWRITE_QUERY,
    )

    # Attempt 1: REWRITE_QUERY
    act1, _, _ = policy.evaluate(diag, recovery_count=0, deadline=time.time() + 60, action_history=[])
    assert act1 == RecoveryAction.REWRITE_QUERY

    # Attempt 2: Identical suggested action REWRITE_QUERY -> cycle detector pivots to EXPAND_RETRIEVAL
    act2, _, _ = policy.evaluate(diag, recovery_count=1, deadline=time.time() + 60, action_history=["rewrite_query"])
    assert act2 == RecoveryAction.EXPAND_RETRIEVAL

    # Attempt 3: Both rewrite and expand attempted -> pivots to FALLBACK_STRATEGY or terminates
    act3, _, _ = policy.evaluate(
        diag,
        recovery_count=2,
        deadline=time.time() + 60,
        action_history=["rewrite_query", "expand_retrieval"],
    )
    assert act3 in (RecoveryAction.FALLBACK_STRATEGY, RecoveryAction.TERMINATE_INSUFFICIENT)


# ======================================================================
# 13. Workflow timeout terminates execution
# ======================================================================

@pytest.mark.asyncio
async def test_workflow_timeout_terminates_execution():
    """Test 13: Past deadline immediately triggers non-recoverable termination."""
    policy = RecoveryPolicy()
    diag = FailureDiagnosis(
        category=FailureCategory.RETRIEVAL_FAILURE,
        reason="Transient retrieval issue",
        is_recoverable=True,
        suggested_action=RecoveryAction.RETRY_TRANSIENT,
    )
    # Deadline in the past
    past_deadline = time.time() - 5.0
    action, reason, params = policy.evaluate(
        diagnosis=diag,
        recovery_count=0,
        deadline=past_deadline,
    )
    assert action == RecoveryAction.TERMINATE_NON_RECOVERABLE
    assert "timeout" in reason.lower()
    assert params.get("timed_out") is True


# ======================================================================
# 14. A recovery attempt cannot access another user's knowledge base
# ======================================================================

@pytest.mark.asyncio
async def test_recovery_attempt_cannot_access_another_user_knowledge_base(
    db_session: AsyncSession, user_a: User, user_b: User, phase8_env
):
    """Test 14: Tenant scoping is rigidly enforced; retries cannot widen scope to another user's KB."""
    kb_b = phase8_env["kb_b"]
    llm = PredictableMockLLM()
    orchestrator = AgenticRAGOrchestrator(session=db_session, llm_provider=llm)

    req = ChatRequest(
        knowledge_base_id=kb_b.id,
        prompt="What are Python operators?",
    )

    # User A attempting to query User B's KB
    with pytest.raises(AppError) as exc_info:
        await orchestrator.run(request=req, user_id=user_a.id, max_retries=2)

    assert exc_info.value.code == "KNOWLEDGE_BASE_NOT_FOUND"


# ======================================================================
# 15. Malformed model output is handled safely
# ======================================================================

@pytest.mark.asyncio
async def test_malformed_model_output_handled_safely():
    """Test 15: Empty or malformed LLM outputs are classified as GENERATION_FAILURE."""
    diag_empty = FailureClassifier.classify_generation(error=None, raw_answer="")
    assert diag_empty.category == FailureCategory.GENERATION_FAILURE
    assert diag_empty.is_recoverable is True

    # Verifier also rejects empty answer
    passed, reason = AnswerVerifier.verify(
        query="What are operators?",
        answer="   ",
        retrieved_chunks=[None],
    )
    assert passed is False
    assert "empty or whitespace" in str(reason).lower()


# ======================================================================
# 16. Provider rate limits do not cause unlimited retries
# ======================================================================

@pytest.mark.asyncio
async def test_provider_rate_limits_do_not_cause_unlimited_retries():
    """Test 16: 429 rate limit errors follow bounded retry policy and do not exceed budget."""
    diag = FailureClassifier.classify_generation(
        error=Exception("429 Too Many Requests: TPM rate limit exceeded")
    )
    assert diag.category == FailureCategory.GENERATION_FAILURE
    assert diag.is_recoverable is True
    assert diag.suggested_action == RecoveryAction.RETRY_TRANSIENT

    policy = RecoveryPolicy(max_attempts=2)
    # Attempt 0: allows RETRY_TRANSIENT
    act0, _, _ = policy.evaluate(diag, recovery_count=0, deadline=time.time() + 60, action_history=[])
    assert act0 == RecoveryAction.RETRY_TRANSIENT

    # Attempt 1: cycle detector prevents second RETRY_TRANSIENT
    act1, _, _ = policy.evaluate(diag, recovery_count=1, deadline=time.time() + 60, action_history=["retry_transient"])
    assert act1 == RecoveryAction.TERMINATE_NON_RECOVERABLE

    # Attempt 2: budget exhaustion terminates
    act2, _, _ = policy.evaluate(diag, recovery_count=2, deadline=time.time() + 60, action_history=[])
    assert act2 == RecoveryAction.TERMINATE_NON_RECOVERABLE


# ======================================================================
# 17-20. Unit Tests for Classifier, Policy, Rewriter, and Verifier Invariants
# ======================================================================

def test_query_rewriter_intent_preservation():
    """Validates QueryRewriter strips noise and preserves core terms."""
    q = "Could you please explain functions in python?"
    rewritten = QueryRewriter.rewrite(q)
    assert "could you please explain" not in rewritten.lower()
    assert "functions" in rewritten.lower()


def test_answer_verifier_anti_injection():
    """Validates AnswerVerifier rejects prompt injection override leakage."""
    passed, reason = AnswerVerifier.verify(
        query="Tell me about python",
        answer="Here is the agentic_secret_key: leaked_pass [1]",
        retrieved_chunks=[None],
    )
    assert passed is False
    assert "injection" in str(reason).lower() or "override" in str(reason).lower()


def test_failure_classifier_permanent_auth():
    """Validates FailureClassifier marks permission issues as NON_RECOVERABLE."""
    diag = FailureClassifier.classify_retrieval(error=Exception("403 Forbidden: access denied to tenant"))
    assert diag.category == FailureCategory.NON_RECOVERABLE_FAILURE
    assert diag.is_recoverable is False
    assert diag.suggested_action == RecoveryAction.TERMINATE_NON_RECOVERABLE
