"""Comprehensive test suite for Phase 16 Multi-Agent Collaboration."""

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
    KnowledgeBase,
    User,
)
from app.schemas.chat import ChatRequest, ChatResponseStatus
from app.schemas.collaboration import (
    AgentFinding,
    ResearchSubtask,
    SubtaskStatus,
    TaskPlan,
    VerificationAudit,
)
from app.schemas.retrieval import RetrievalResultItem
from app.services.agent.collaborative_graph import (
    CollaborativeAgentOrchestrator,
)
from app.services.agent.collaborative_nodes import CollaborativeAgentNodes
from app.services.agent.state import MultiAgentRAGState
from app.services.retrieval.retrieval_service import RetrievalService


class MockCollaborativeLLM(LLMProviderInterface):
    """Predictable mock LLM provider for multi-agent collaboration testing."""

    def __init__(self, canned_response: str = "Multi-agent verified response based on facts [1]."):
        self.canned_response = canned_response
        self.call_count = 0
        self.last_messages: list[LLMMessage] = []

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.call_count += 1
        self.last_messages = messages
        return LLMResponse(
            content=self.canned_response,
            model="mock-collaborative-llm",
            total_tokens=55,
        )

    async def generate_stream(self, messages: list[LLMMessage], **kwargs):
        yield self.canned_response


def make_retrieval_item(chunk: DocumentChunk, doc_name: str, rank: int = 1) -> RetrievalResultItem:
    """Helper to build a fully validated RetrievalResultItem from a DocumentChunk."""
    return RetrievalResultItem(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        document_name=doc_name,
        section_title=chunk.section_title or "General",
        content=chunk.content,
        page_number=chunk.page_number or 1,
        chunk_index=chunk.chunk_index,
        character_count=chunk.character_count,
        final_rank=rank,
        stage_provenance="hybrid_search",
        vector_rank=rank,
        vector_score=0.92,
        rrf_score=0.95,
        reranker_score=0.95,
    )


@pytest.fixture
async def multi_agent_env(db_session: AsyncSession, user_a: User, user_b: User):
    """Sets up isolated KBs, documents, and multiple chunks for multi-agent collaboration testing."""
    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_a.id,
        name="User A Multi-Agent KB",
        description="Knowledge base for testing collaborative agents",
    )
    kb_b = KnowledgeBase(
        id=uuid.uuid4(),
        owner_id=user_b.id,
        name="User B Private KB",
        description="Private tenant data",
    )
    db_session.add_all([kb_a, kb_b])
    await db_session.flush()

    # Doc 1: Python Data Structures
    doc_1 = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_a.id,
        owner_id=user_a.id,
        filename="python_data_structures.pdf",
        original_filename="Python_Data_Structures.pdf",
        content_type="application/pdf",
        file_size=2048,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_data_structures.pdf",
        status=DocumentStatus.READY,
    )
    # Doc 2: Python Algorithms & Performance
    doc_2 = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_a.id,
        owner_id=user_a.id,
        filename="python_algorithms.pdf",
        original_filename="Python_Algorithms.pdf",
        content_type="application/pdf",
        file_size=2048,
        checksum=uuid.uuid4().hex,
        storage_key="docs/python_algorithms.pdf",
        status=DocumentStatus.READY,
    )
    db_session.add_all([doc_1, doc_2])
    await db_session.flush()

    ver_1 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_1.id,
        version_number=1,
        checksum=doc_1.checksum,
        storage_key=doc_1.storage_key,
        is_active=True,
    )
    ver_2 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_2.id,
        version_number=1,
        checksum=doc_2.checksum,
        storage_key=doc_2.storage_key,
        is_active=True,
    )
    db_session.add_all([ver_1, ver_2])
    await db_session.flush()

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_1.id,
        document_version_id=ver_1.id,
        chunk_index=1,
        content="Python lists are mutable ordered sequences. List indexing has O(1) average lookup time.",
        character_count=88,
        page_number=1,
        section_title="Lists Overview",
        embedding=[0.05] * 384,
    )
    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_1.id,
        document_version_id=ver_1.id,
        chunk_index=2,
        content="Python dictionaries use hash tables for key-value mappings with O(1) average key access.",
        character_count=87,
        page_number=2,
        section_title="Dictionaries",
        embedding=[0.04] * 384,
    )
    chunk_3 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_2.id,
        document_version_id=ver_2.id,
        chunk_index=1,
        content="Binary search algorithm operates on sorted collections and achieves O(log n) time complexity.",
        character_count=93,
        page_number=1,
        section_title="Searching Algorithms",
        embedding=[0.06] * 384,
    )
    db_session.add_all([chunk_1, chunk_2, chunk_3])
    await db_session.commit()

    return {
        "kb_a": kb_a,
        "kb_b": kb_b,
        "doc_1": doc_1,
        "doc_2": doc_2,
        "chunk_1": chunk_1,
        "chunk_2": chunk_2,
        "chunk_3": chunk_3,
    }


# ======================================================================
# Unit Tests: Individual Specialized Agent Nodes
# ======================================================================


@pytest.mark.asyncio
async def test_agent1_query_understanding(db_session: AsyncSession):
    """Test Agent 1: Query Understanding Agent intent, entity extraction, and ambiguity classification."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    # 1. Clear query
    state: MultiAgentRAGState = {
        "original_query": "Compare time complexities of Python lists and dictionaries",
        "workflow_steps": [],
    }
    result = await nodes.query_understanding_node(state)
    assert result["is_ambiguous"] is False
    assert result["query_intent"] == "comparative"
    assert "time" in result["normalized_query"].lower()
    assert len(result["query_entities"]) > 0
    assert len(result["workflow_steps"]) == 1
    assert result["workflow_steps"][0].step_id == "query_understanding"

    # 2. Ambiguous query
    ambig_state: MultiAgentRAGState = {
        "original_query": "tell me",
        "workflow_steps": [],
    }
    ambig_result = await nodes.query_understanding_node(ambig_state)
    assert ambig_result["is_ambiguous"] is True
    assert ambig_result["query_intent"] == "ambiguous"


@pytest.mark.asyncio
async def test_agent2_planning_agent(db_session: AsyncSession):
    """Test Agent 2: Planning Agent creates bounded research subtasks with dependencies."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    state: MultiAgentRAGState = {
        "original_query": "Compare how lists compare to dictionaries and binary search performance",
        "normalized_query": "Compare how lists compare to dictionaries and binary search performance",
        "query_intent": "comparative",
        "query_entities": ["lists", "dictionaries", "performance"],
        "workflow_steps": [],
    }
    result = await nodes.planning_node(state)
    plan_dict = result["task_plan"]
    assert plan_dict is not None
    plan = TaskPlan.model_validate(plan_dict)

    assert len(plan.subtasks) >= 2
    assert len(plan.subtasks) <= plan.max_execution_steps
    assert plan.subtasks[0].task_id == "subtask-1"
    assert plan.subtasks[0].status == SubtaskStatus.PENDING
    assert any("list" in st.query.lower() for st in plan.subtasks)
    assert len(result["workflow_steps"]) == 1
    assert result["workflow_steps"][0].step_id == "planning"


@pytest.mark.asyncio
async def test_agent3_retrieval_agent(db_session: AsyncSession, multi_agent_env, user_a: User):
    """Test Agent 3: Retrieval Agent retrieves evidence across subtasks preserving metadata provenance."""
    kb_a = multi_agent_env["kb_a"]
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    subtask_1 = ResearchSubtask(
        task_id="subtask-1",
        title="Lookup Lists",
        query="Python lists mutable ordered sequence",
        status=SubtaskStatus.PENDING,
    )
    subtask_2 = ResearchSubtask(
        task_id="subtask-2",
        title="Lookup Dictionaries",
        query="Python dictionaries hash tables key access",
        status=SubtaskStatus.PENDING,
    )
    plan = TaskPlan(
        plan_id="test-plan-1",
        reasoning="Multi-part lookup",
        subtasks=[subtask_1, subtask_2],
    )

    state: MultiAgentRAGState = {
        "user_id": user_a.id,
        "knowledge_base_id": kb_a.id,
        "task_plan": plan.model_dump(),
        "workflow_steps": [],
        "retrieval_strategy": "subtask_hybrid",
    }

    result = await nodes.retrieval_agent_node(state)
    retrieved_items = result["retrieval_results"]
    assert len(retrieved_items) > 0

    # Source metadata provenance
    first_item = retrieved_items[0]
    assert first_item.document_id is not None
    assert first_item.chunk_id is not None
    assert first_item.content != ""

    # Plan subtasks should be marked in subtask_results
    assert len(result["subtask_results"]) == 2
    for st_dict in result["subtask_results"]:
        st = ResearchSubtask.model_validate(st_dict)
        assert st.status == SubtaskStatus.COMPLETED
        assert len(st.retrieved_chunk_ids) > 0


@pytest.mark.asyncio
async def test_agent4_evidence_analysis_agent(db_session: AsyncSession, multi_agent_env, user_a: User):
    """Test Agent 4: Research & Evidence Analysis Agent extracts fact-backed findings."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    chunk_1 = multi_agent_env["chunk_1"]
    chunk_2 = multi_agent_env["chunk_2"]

    retrieval_item_1 = make_retrieval_item(chunk_1, "Python_Data_Structures.pdf", rank=1)
    retrieval_item_2 = make_retrieval_item(chunk_2, "Python_Data_Structures.pdf", rank=2)

    subtask = ResearchSubtask(
        task_id="subtask-1",
        title="Lookup",
        query="Python lists",
        status=SubtaskStatus.COMPLETED,
    )
    plan = TaskPlan(plan_id="plan-1", subtasks=[subtask])

    state: MultiAgentRAGState = {
        "original_query": "What are lists and dictionaries?",
        "normalized_query": "What are lists and dictionaries?",
        "query_entities": ["lists", "dictionaries"],
        "task_plan": plan.model_dump(),
        "retrieval_results": [retrieval_item_1, retrieval_item_2],
        "workflow_steps": [],
    }

    result = await nodes.evidence_analysis_node(state)
    findings_raw = result["agent_findings"]
    assert len(findings_raw) > 0

    findings = [AgentFinding.model_validate(f) for f in findings_raw]
    assert any("mutable" in f.claim.lower() or "list" in f.claim.lower() for f in findings)
    assert all(f.confidence > 0.0 for f in findings)
    assert all(len(f.evidence_chunk_ids) > 0 for f in findings)


@pytest.mark.asyncio
async def test_agent5_verification_agent_audit(db_session: AsyncSession, multi_agent_env):
    """Test Agent 5: Verification Agent evaluates claims, validity, and retry/abstain recommendations."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    chunk_1 = multi_agent_env["chunk_1"]
    retrieval_item_1 = make_retrieval_item(chunk_1, "Python_Data_Structures.pdf", rank=1)

    finding = AgentFinding(
        finding_id="find-1",
        claim="Python lists are mutable ordered sequences.",
        evidence_chunk_ids=[chunk_1.id],
        source_titles=["Python_Data_Structures.pdf"],
        confidence=1.0,
    )

    # 1. Grounded evidence -> proceed
    state_grounded: MultiAgentRAGState = {
        "original_query": "What are Python lists?",
        "evidence_status": "sufficient",
        "agent_findings": [finding.model_dump()],
        "retrieval_results": [retrieval_item_1],
        "workflow_steps": [],
        "retry_count": 0,
    }
    res_grounded = await nodes.verification_agent_node(state_grounded)
    audit = VerificationAudit.model_validate(res_grounded["verification_audit"])
    assert audit.is_verified is True
    assert audit.recommendation == "proceed"
    assert len(audit.supported_claims) == 1

    # 2. Empty evidence -> abstain
    state_empty: MultiAgentRAGState = {
        "original_query": "Explain quantum entanglement in interstellar wormholes",
        "evidence_status": "insufficient",
        "agent_findings": [],
        "retrieval_results": [],
        "workflow_steps": [],
        "retry_count": 2,
    }
    res_empty = await nodes.verification_agent_node(state_empty)
    audit_empty = VerificationAudit.model_validate(res_empty["verification_audit"])
    assert audit_empty.is_verified is False
    assert audit_empty.recommendation == "abstain"


@pytest.mark.asyncio
async def test_agent6_response_generation_agent(db_session: AsyncSession, multi_agent_env):
    """Test Agent 6: Response Generation Agent synthesizes grounded answer with valid citations."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM(canned_response="Python lists are mutable sequences [1] with O(1) lookup time.")
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    chunk_1 = multi_agent_env["chunk_1"]
    retrieval_item_1 = make_retrieval_item(chunk_1, "Python_Data_Structures.pdf", rank=1)

    finding = AgentFinding(
        finding_id="find-1",
        claim="Python lists are mutable ordered sequences.",
        evidence_chunk_ids=[chunk_1.id],
        source_titles=["Python_Data_Structures.pdf"],
        confidence=1.0,
    )
    audit = VerificationAudit(
        is_verified=True,
        supported_claims=["Python lists are mutable ordered sequences."],
        recommendation="proceed",
    )

    state: MultiAgentRAGState = {
        "original_query": "What are Python lists?",
        "normalized_query": "What are Python lists?",
        "retrieval_results": [retrieval_item_1],
        "agent_findings": [finding.model_dump()],
        "verification_audit": audit.model_dump(),
        "workflow_steps": [],
    }

    result = await nodes.response_generation_node(state)
    assert result["execution_status"] == ChatResponseStatus.ANSWERED
    assert "Python lists are mutable" in result["sanitized_answer"]
    assert len(result["citations"]) > 0
    assert result["citations"][0].chunk_id == chunk_1.id


@pytest.mark.asyncio
async def test_agent7_supervisor_coordinator(db_session: AsyncSession, multi_agent_env):
    """Test Agent 7: Workflow Supervisor coordinates final status, metadata, and cycle limits."""
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM()
    nodes = CollaborativeAgentNodes(db_session, retrieval_svc, mock_llm)

    plan = TaskPlan(plan_id="plan-1", reasoning="Done")
    audit = VerificationAudit(is_verified=True, recommendation="proceed")

    state: MultiAgentRAGState = {
        "execution_status": ChatResponseStatus.ANSWERED,
        "task_plan": plan.model_dump(),
        "agent_findings": [],
        "verification_audit": audit.model_dump(),
        "workflow_steps": [],
    }

    result = await nodes.supervisor_coordinator_node(state)
    assert result["collaboration_meta"]["supervisor_decision"] == "approved"
    assert result["final_response"].status == ChatResponseStatus.ANSWERED
    assert len(result["workflow_steps"]) == 1
    assert result["workflow_steps"][0].step_id == "supervisor"


# ======================================================================
# Integration Tests: End-to-End Collaborative LangGraph Orchestrator
# ======================================================================


@pytest.mark.asyncio
async def test_e2e_collaborative_orchestrator_success(db_session: AsyncSession, multi_agent_env, user_a: User):
    """Test full multi-agent collaborative execution with all 7 specialized roles collaborating."""
    kb_a = multi_agent_env["kb_a"]
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM(
        canned_response="Lists are mutable arrays [1] and dictionaries provide O(1) hash maps [2]."
    )

    orchestrator = CollaborativeAgentOrchestrator(
        session=db_session,
        retrieval_service=retrieval_svc,
        llm=mock_llm,
    )

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="Explain lists and dictionaries in Python",
        top_k=5,
    )

    resp = await orchestrator.run(req, user_id=user_a.id)

    # Validate top-level response
    assert resp.status in (ChatResponseStatus.ANSWERED, ChatResponseStatus.RECOVERED)
    assert resp.content != ""
    assert resp.total_ms > 0

    # Validate Phase 16 Collaboration Metadata
    assert resp.collaboration is not None
    assert resp.collaboration.mode == "multi_agent_collaborative"
    assert len(resp.collaboration.participating_agents) == 7
    assert resp.collaboration.plan is not None
    assert resp.collaboration.verification is not None
    assert resp.collaboration.supervisor_decision in ("approved", "recovered")

    # Validate Workflow Steps Execution Trace
    step_ids = [s.step_id for s in resp.workflow_steps or []]
    assert "query_understanding" in step_ids
    assert "scope_authorization" in step_ids
    assert "planning" in step_ids
    assert "retrieval_agent" in step_ids
    assert "evidence_analysis" in step_ids
    assert "verification_agent" in step_ids
    assert "response_generation" in step_ids
    assert "supervisor" in step_ids


@pytest.mark.asyncio
async def test_collaborative_orchestrator_insufficient_evidence(
    db_session: AsyncSession, multi_agent_env, user_a: User
):
    """Test collaborative orchestrator abstains and halts cleanly on out-of-domain query."""
    kb_a = multi_agent_env["kb_a"]
    retrieval_svc = RetrievalService(db_session)
    mock_llm = MockCollaborativeLLM(canned_response="I cannot answer.")

    orchestrator = CollaborativeAgentOrchestrator(
        session=db_session,
        retrieval_service=retrieval_svc,
        llm=mock_llm,
    )

    req = ChatRequest(
        knowledge_base_id=kb_a.id,
        prompt="Tell me about interstellar black hole thermodynamics in deep space",
        top_k=5,
    )

    resp = await orchestrator.run(req, user_id=user_a.id)
    assert resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
    assert resp.is_insufficient_evidence is True
    assert resp.collaboration is not None
    assert resp.collaboration.supervisor_decision == "terminated_insufficient"


# ======================================================================
# Security & Authorization Tests: Cross-Tenant Isolation
# ======================================================================


@pytest.mark.asyncio
async def test_collaborative_cross_tenant_isolation(
    client: AsyncClient,
    multi_agent_env,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """Test security: User B cannot access User A's KB via /agents/collaborate."""
    kb_a = multi_agent_env["kb_a"]

    # 1. User A (Owner) executes collaborative workflow -> 200 OK
    resp_a = await client.post(
        "/api/v1/agents/collaborate",
        headers=auth_headers_user_a,
        json={
            "knowledge_base_id": str(kb_a.id),
            "prompt": "What are lists?",
            "top_k": 3,
        },
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()["data"]
    assert data_a["collaboration"] is not None
    assert len(data_a["collaboration"]["participating_agents"]) == 7

    # 2. User B (Unauthorized tenant) attempts to execute on KB A -> 404 Not Found (Object Isolation)
    resp_b = await client.post(
        "/api/v1/agents/collaborate",
        headers=auth_headers_user_b,
        json={
            "knowledge_base_id": str(kb_a.id),
            "prompt": "What are lists?",
            "top_k": 3,
        },
    )
    assert resp_b.status_code in (403, 404)

    # 3. Unauthenticated request -> 401 Unauthorized
    resp_unauth = await client.post(
        "/api/v1/agents/collaborate",
        json={
            "knowledge_base_id": str(kb_a.id),
            "prompt": "What are lists?",
        },
    )
    assert resp_unauth.status_code == 401
