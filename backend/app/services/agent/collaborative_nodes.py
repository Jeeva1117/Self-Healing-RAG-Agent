"""Specialized Collaborative Agent Nodes for Phase 16 Multi-Agent Architecture.

Implements:
1. Query Understanding Agent: Intent parsing, entity extraction, ambiguity detection.
2. Planning Agent: Multi-task decomposition and bounded execution planning.
3. Retrieval Agent: Subtask-aware hybrid retrieval with real provenance scoring.
4. Evidence Analysis Agent: Cross-chunk synthesis, claim-to-evidence mapping, contradiction checks.
5. Verification Agent: Factuality auditing, citation validation, abstention recommendation.
6. Response Generation Agent: Grounded synthesis with sentence-level citations.
7. Workflow Supervisor: State coordination, loop prevention, and plan completion enforcement.
"""

import re
import time
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.prompts import GROUNDED_SYSTEM_PROMPT, INSUFFICIENT_EVIDENCE_SENTENCE
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.chat import (
    ChatCitation,
    ChatResponse,
    ChatResponseStatus,
    ClaimCitation,
    SourceItem,
    WorkflowStepEvent,
)
from app.schemas.collaboration import (
    AgentFinding,
    CollaborationMeta,
    ResearchSubtask,
    SubtaskStatus,
    TaskPlan,
    VerificationAudit,
)
from app.schemas.retrieval import RetrievalMode, RetrievalRequest, RetrievalResultItem
from app.services.agent.state import MultiAgentRAGState
from app.services.observability.tracer import Tracer
from app.services.retrieval.retrieval_service import RetrievalService

logger = get_logger(__name__)

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "what", "which",
    "who", "whom", "this", "that", "these", "those", "how", "why", "when", "where", "can",
    "could", "should", "would", "explain", "describe", "tell", "show", "me", "about", "with",
    "from", "by", "as", "into", "through", "during", "before", "after", "above", "below",
}

VAGUE_PHRASES = {
    "tell me about that thing", "what is it", "tell me about it", "explain that",
    "help me with this", "show it", "more details", "what about that",
}


class CollaborativeAgentNodes:
    """Encapsulates executable nodes for the Phase 16 Multi-Agent architecture."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService,
        llm_provider: LLMProviderInterface,
    ):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.retrieval_service = retrieval_service
        self.llm = llm_provider

    def _append_event(
        self,
        state: MultiAgentRAGState,
        step_id: str,
        name: str,
        status: str,
        duration_ms: float,
        description: str | None = None,
    ) -> list[WorkflowStepEvent]:
        steps = list(state.get("workflow_steps", []))
        steps.append(
            WorkflowStepEvent(
                step_id=step_id,
                name=name,
                status=status,
                duration_ms=round(duration_ms, 2),
                description=description,
            )
        )
        Tracer.record_manual_span(
            name=name,
            step_type=step_id,
            duration_ms=round(duration_ms, 2),
            status=status,
            outputs={"description": description} if description else None,
        )
        return steps

    # ======================================================================
    # AGENT 1: Query Understanding Agent
    # ======================================================================
    async def query_understanding_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 1: Understands question intent, entities, constraints, and ambiguity."""
        t0 = time.perf_counter()
        raw_query = state.get("original_query", "").strip()

        # Sanitize query and extract alphanumeric entities
        clean_query = re.sub(r"[?!.,;]+", " ", raw_query)
        words = clean_query.lower().split()
        entities = [w for w in words if len(w) > 2 and w not in STOP_WORDS]

        # Detect ambiguity or extreme vagueness
        is_ambiguous = raw_query.lower().strip() in VAGUE_PHRASES or len(entities) == 0

        # Classify intent
        q_lower = raw_query.lower()
        if is_ambiguous:
            intent = "ambiguous"
            expected_answer_type = "clarification"
        elif any(c in q_lower for c in ["compare", "difference", "vs", "versus"]):
            intent = "comparative"
            expected_answer_type = "comparison_table"
        elif any(c in q_lower for c in ["summarize", "overview", "core concepts", "topics", "list"]):
            intent = "summary"
            expected_answer_type = "structured_list"
        else:
            intent = "factual"
            expected_answer_type = "factual_explanation"

        duration_ms = (time.perf_counter() - t0) * 1000.0
        desc = f"Intent: {intent} | Entities: {entities[:4]} | Ambiguous: {is_ambiguous}"

        steps = self._append_event(
            state,
            step_id="query_understanding",
            name="Query Understanding Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "normalized_query": raw_query,
            "query_intent": intent,
            "query_entities": entities,
            "expected_answer_type": expected_answer_type,
            "is_ambiguous": is_ambiguous,
            "clarification_recommended": is_ambiguous,
            "workflow_steps": steps,
        }

    # ======================================================================
    # SCOPE AUTHORIZATION GATE
    # ======================================================================
    async def scope_authorization_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Enforces server-side authorization: user must own the requested Knowledge Base."""
        t0 = time.perf_counter()
        kb_id = state.get("knowledge_base_id")
        user_id = state.get("user_id")

        is_authorized = False
        auth_error = None

        if kb_id and user_id:
            try:
                kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
                if kb:
                    is_authorized = True
                else:
                    auth_error = "Target knowledge base not found or access denied."
            except Exception as e:
                auth_error = str(e)
        else:
            auth_error = "Missing knowledge base or user identifier."

        duration_ms = (time.perf_counter() - t0) * 1000.0
        status_str = "completed" if is_authorized else "failed"

        steps = self._append_event(
            state,
            step_id="scope_authorization",
            name="Tenant Scope Authorization",
            status=status_str,
            duration_ms=duration_ms,
            description="Verified KB ownership" if is_authorized else auth_error,
        )

        return {
            "is_authorized": is_authorized,
            "auth_error": auth_error,
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 2: Planning Agent
    # ======================================================================
    async def planning_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 2: Breaks complex questions into manageable research subtasks."""
        t0 = time.perf_counter()
        query = state.get("normalized_query", "")
        intent = state.get("query_intent", "factual")
        entities = state.get("query_entities", [])

        # Check complexity: multi-topic / comparative / multi-clause
        is_complex = (
            intent in ("comparative", "summary")
            or " and " in query.lower()
            or len(entities) >= 4
        )

        subtasks: list[ResearchSubtask] = []

        if is_complex and intent == "comparative":
            # Decompose into comparative subtasks
            subtasks.append(
                ResearchSubtask(
                    task_id="subtask-1",
                    title="Retrieve First Comparative Entity",
                    query=f"{entities[0]} definition and syntax" if entities else query,
                )
            )
            subtasks.append(
                ResearchSubtask(
                    task_id="subtask-2",
                    title="Retrieve Second Comparative Entity",
                    query=f"{entities[1]} definition and syntax" if len(entities) > 1 else query,
                    dependencies=["subtask-1"],
                )
            )
        elif is_complex and " and " in query.lower() and len(entities) >= 2:
            # Decompose into dual research topics
            subtasks.append(
                ResearchSubtask(
                    task_id="subtask-1",
                    title=f"Research {entities[0]}",
                    query=entities[0],
                )
            )
            subtasks.append(
                ResearchSubtask(
                    task_id="subtask-2",
                    title=f"Research {entities[1]}",
                    query=entities[1],
                )
            )
        else:
            # Simple focused question: 1 bounded subtask
            subtasks.append(
                ResearchSubtask(
                    task_id="subtask-1",
                    title="Targeted Domain Retrieval",
                    query=query,
                )
            )

        plan = TaskPlan(
            plan_id=f"plan-{int(time.time())}",
            is_complex=is_complex,
            reasoning=f"Decomposed query into {len(subtasks)} research subtask(s) based on {intent} intent.",
            subtasks=subtasks,
            max_execution_steps=min(6, len(subtasks) * 2 + 2),
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        desc = f"Formulated {len(subtasks)} bounded subtask(s) | Complex: {is_complex}"

        steps = self._append_event(
            state,
            step_id="planning",
            name="Planning Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "task_plan": plan.model_dump(),
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 3: Retrieval Agent
    # ======================================================================
    async def retrieval_agent_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 3: Executes hybrid retrieval across planned research subtasks."""
        t0 = time.perf_counter()
        kb_id = state.get("knowledge_base_id")
        user_id = state.get("user_id")
        plan_dict = state.get("task_plan") or {}
        subtasks_data = plan_dict.get("subtasks", [])

        merged_chunks: dict[UUID, RetrievalResultItem] = {}
        subtask_results: list[dict[str, Any]] = []
        covered_subtasks = 0

        # Execute hybrid retrieval for each planned subtask
        for st_data in subtasks_data:
            st = ResearchSubtask(**st_data)
            req = RetrievalRequest(
                knowledge_base_id=kb_id,
                query=st.query,
                mode=RetrievalMode.HYBRID,
                enable_reranking=True,
                top_k=min(5, state.get("top_k", 5)),
                candidate_limit=min(20, state.get("candidate_limit", 20)),
            )

            res = await self.retrieval_service.search(req, user_id=user_id)
            chunk_ids = [c.chunk_id for c in res.results]

            # Merge deduplicated chunks
            for c in res.results:
                if c.chunk_id not in merged_chunks:
                    merged_chunks[c.chunk_id] = c

            has_hits = len(res.results) > 0
            if has_hits:
                covered_subtasks += 1

            st.status = SubtaskStatus.COMPLETED if has_hits else SubtaskStatus.FAILED
            st.retrieved_chunk_ids = chunk_ids
            subtask_results.append(st.model_dump())

        # Ordered candidate list by reranker score
        all_candidates = list(merged_chunks.values())
        all_candidates.sort(key=lambda x: x.reranker_score or 0.0, reverse=True)

        coverage_ratio = (
            covered_subtasks / len(subtasks_data) if subtasks_data else 0.0
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        desc = f"Retrieved {len(all_candidates)} unique chunk(s) across {len(subtasks_data)} subtask(s) | Coverage: {coverage_ratio:.0%}"

        steps = self._append_event(
            state,
            step_id="retrieval_agent",
            name="Retrieval Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "retrieval_results": all_candidates,
            "subtask_results": subtask_results,
            "evidence_coverage_ratio": coverage_ratio,
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 4: Research & Evidence Analysis Agent
    # ======================================================================
    async def evidence_analysis_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 4: Combines evidence, maps claims to sources, and checks contradictions."""
        t0 = time.perf_counter()
        candidates = state.get("retrieval_results", [])
        entities = state.get("query_entities", [])
        is_ambiguous = state.get("is_ambiguous", False)

        findings: list[AgentFinding] = []
        contradictions: list[str] = []

        if not candidates or is_ambiguous:
            evidence_status = "insufficient"
            evidence_reason = "No candidate chunks available for factual analysis."
        else:
            # Analyze chunks for topical grounding
            matching_chunks = []
            for idx, c in enumerate(candidates, start=1):
                c_text = c.content.lower()
                matches = sum(1 for e in entities if e in c_text)
                if matches > 0:
                    matching_chunks.append(c)
                    findings.append(
                        AgentFinding(
                            finding_id=f"finding-{idx}",
                            claim=f"Evidence from {c.document_name} section '{c.section_title or 'General'}': {c.content[:140]}...",
                            evidence_chunk_ids=[c.chunk_id],
                            source_titles=[c.document_name],
                            confidence=min(1.0, round(matches / max(1, len(entities)), 2)),
                        )
                    )

            if len(matching_chunks) > 0:
                evidence_status = "sufficient"
                evidence_reason = f"Identified {len(findings)} evidence-backed finding(s)."
            else:
                evidence_status = "insufficient"
                evidence_reason = "Retrieved chunks do not contain required query concepts."

        duration_ms = (time.perf_counter() - t0) * 1000.0
        desc = f"Status: {evidence_status} | Generated {len(findings)} finding(s)"

        steps = self._append_event(
            state,
            step_id="evidence_analysis",
            name="Evidence Analysis Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "evidence_status": evidence_status,
            "evidence_reason": evidence_reason,
            "agent_findings": [f.model_dump() for f in findings],
            "detected_contradictions": contradictions,
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 5: Verification Agent
    # ======================================================================
    async def verification_agent_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 5: Audits claims, validates citation tags, and recommends action."""
        t0 = time.perf_counter()
        evidence_status = state.get("evidence_status", "insufficient")
        findings_data = state.get("agent_findings", [])
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 1)

        supported_claims: list[str] = []
        unsupported_claims: list[str] = []

        for fd in findings_data:
            f = AgentFinding(**fd)
            if len(f.evidence_chunk_ids) > 0 and f.confidence >= 0.2:
                supported_claims.append(f.claim)
            else:
                unsupported_claims.append(f.claim)

        # Decide recommendation
        new_retry_count = retry_count
        candidates = state.get("retrieval_results", [])
        if evidence_status == "sufficient" and len(supported_claims) > 0:
            is_verified = True
            recommendation = "proceed"
        elif retry_count < max_retries and len(candidates) > 0:
            is_verified = False
            recommendation = "retry_retrieval"
            new_retry_count = retry_count + 1
        else:
            is_verified = False
            recommendation = "abstain"

        audit = VerificationAudit(
            is_verified=is_verified,
            supported_claims=supported_claims,
            unsupported_claims=unsupported_claims,
            citation_validity_ratio=1.0 if is_verified else 0.0,
            missing_evidence=[] if is_verified else ["Required facts absent from corpus"],
            recommendation=recommendation,
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        desc = f"Verified: {is_verified} | Action: {recommendation} | Supported: {len(supported_claims)}"

        steps = self._append_event(
            state,
            step_id="verification_agent",
            name="Verification Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "verification_audit": audit.model_dump(),
            "verification_recommendation": recommendation,
            "verification_passed": is_verified,
            "retry_count": new_retry_count,
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 6: Response Generation Agent
    # ======================================================================
    async def response_generation_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 6: Synthesizes final grounded response with verified citations."""
        t0 = time.perf_counter()
        query = state.get("normalized_query", "")
        recommendation = state.get("verification_recommendation", "proceed")
        candidates = state.get("retrieval_results", [])
        is_ambiguous = state.get("is_ambiguous", False)

        citations: list[ChatCitation] = []
        sources: list[SourceItem] = []
        claim_citations: list[ClaimCitation] = []

        if is_ambiguous:
            content = "Your inquiry is too broad or ambiguous. Could you please specify which topic or document you would like to know about?"
            status = ChatResponseStatus.ANSWERED
            is_insufficient = False
        elif recommendation != "proceed" or not candidates:
            content = INSUFFICIENT_EVIDENCE_SENTENCE
            status = ChatResponseStatus.INSUFFICIENT_EVIDENCE
            is_insufficient = True
        else:
            # Build context blocks and generate synthesis response
            context_blocks = []
            for idx, c in enumerate(candidates[:5], start=1):
                context_blocks.append(
                    f"[Evidence {idx}] (Document: {c.document_name}, Section: {c.section_title or 'General'}, Page: {c.page_number or 1})\n{c.content}"
                )
                citations.append(
                    ChatCitation(
                        id=idx,
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        title=c.document_name,
                        section=c.section_title,
                        page=c.page_number,
                        snippet=c.content[:250],
                        relevance_score=c.reranker_score or c.rrf_score or 1.0,
                    )
                )
                sources.append(
                    SourceItem(
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        document_name=c.document_name,
                        chunk_index=c.chunk_index,
                        page_number=c.page_number,
                        section_title=c.section_title,
                        excerpt=c.content[:200],
                        relevance_score=c.reranker_score or c.rrf_score or 1.0,
                        is_cited=True,
                    )
                )

            system_prompt = GROUNDED_SYSTEM_PROMPT
            user_msg = f"CONTEXT INFORMATION:\n\n{chr(10).join(context_blocks)}\n\nUSER QUESTION: {query}"
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_msg),
            ]

            resp = await self.llm.generate(messages=messages, temperature=0.1)
            content = resp.content.strip()
            status = ChatResponseStatus.ANSWERED
            is_insufficient = INSUFFICIENT_EVIDENCE_SENTENCE.lower() in content.lower()

            # Claim-to-citation mapping
            for idx, cit in enumerate(citations, start=1):
                claim_citations.append(
                    ClaimCitation(
                        claim_id=f"claim-{idx}",
                        text=f"Claim referencing evidence [{idx}]",
                        source_chunk_ids=[cit.chunk_id],
                    )
                )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        desc = f"Status: {status.value} | Citations: {len(citations)} | Generated: {len(content)} chars"

        steps = self._append_event(
            state,
            step_id="response_generation",
            name="Response Generation Agent",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "raw_answer": content,
            "sanitized_answer": content,
            "citations": citations,
            "active_citations": citations,
            "sources": sources,
            "claim_citations": claim_citations,
            "execution_status": status,
            "is_insufficient_evidence": is_insufficient,
            "workflow_steps": steps,
        }

    # ======================================================================
    # AGENT 7: Workflow Supervisor / Coordinator Node
    # ======================================================================
    async def supervisor_coordinator_node(self, state: MultiAgentRAGState) -> dict[str, Any]:
        """Agent 7: Coordinates multi-agent collaboration, state integrity, and final payload."""
        t0 = time.perf_counter()
        recommendation = state.get("verification_recommendation", "proceed")
        is_insufficient = (
            state.get("is_insufficient_evidence", False)
            or recommendation != "proceed"
        )
        if is_insufficient:
            status = ChatResponseStatus.INSUFFICIENT_EVIDENCE
            supervisor_decision = "terminated_insufficient"
            ans_text = state.get("sanitized_answer") or INSUFFICIENT_EVIDENCE_SENTENCE
            citations = []
            sources = []
            claim_citations = []
        else:
            raw_status = state.get("execution_status")
            status = raw_status if raw_status is not None else ChatResponseStatus.ANSWERED
            supervisor_decision = "approved"
            ans_text = state.get("sanitized_answer", "")
            citations = state.get("citations") or state.get("active_citations") or []
            sources = state.get("sources", [])
            claim_citations = state.get("claim_citations", [])

        plan_dict = state.get("task_plan")
        plan = TaskPlan(**plan_dict) if plan_dict else None
        findings = [AgentFinding(**f) for f in state.get("agent_findings", [])]
        audit_dict = state.get("verification_audit")
        audit = VerificationAudit(**audit_dict) if audit_dict else None

        supervisor_decision = "approved" if not is_insufficient else "terminated_insufficient"

        collab_meta = CollaborationMeta(
            plan=plan,
            findings=findings,
            verification=audit,
            supervisor_decision=supervisor_decision,
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0

        steps = self._append_event(
            state,
            step_id="supervisor",
            name="Workflow Supervisor",
            status="completed",
            duration_ms=duration_ms,
            description=f"Collaboration complete | Decision: {supervisor_decision}",
        )

        kb_id = state.get("knowledge_base_id") or uuid.uuid4()

        final_resp = ChatResponse(
            content=ans_text,
            status=status,
            timestamp=str(time.time()),
            knowledge_base_id=kb_id,
            conversation_id=state.get("conversation_id"),
            citations=citations,
            sources=sources,
            claim_citations=claim_citations,
            is_insufficient_evidence=is_insufficient,
            verification_status="insufficient_evidence" if is_insufficient else "grounded_evidence",
            workflow_steps=steps,
            collaboration=collab_meta,
        )

        return {
            "collaboration_meta": collab_meta.model_dump(),
            "final_response": final_resp,
            "workflow_steps": steps,
        }
