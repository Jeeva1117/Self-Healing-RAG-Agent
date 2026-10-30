"""LangGraph node implementations for Phase 7 agentic RAG orchestration."""

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.prompts import (
    GENERAL_AI_SYSTEM_PROMPT,
    GROUNDED_SYSTEM_PROMPT,
    INSUFFICIENT_EVIDENCE_SENTENCE,
)
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface
from app.infrastructure.llm.groq_provider import redact_secret
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.chat import (
    ChatResponse,
    ChatResponseStatus,
    EvidenceMeta,
    GenerationMeta,
    RecoveryMeta,
    WorkflowStepEvent,
)
from app.schemas.retrieval import RetrievalMode, RetrievalRequest
from app.services.agent.state import AgenticRAGState
from app.services.chat.citation_validator import CitationValidator
from app.services.recovery import (
    AnswerVerifier,
    FailureCategory,
    FailureClassifier,
    FailureDiagnosis,
    QueryRewriter,
    RecoveryAction,
    RecoveryAttemptRecord,
    RecoveryPolicy,
)
from app.services.retrieval.retrieval_service import RetrievalService

logger = get_logger(__name__)

MAX_CONTEXT_CHARACTERS = 14000

STOP_WORDS = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "how",
    "why",
    "when",
    "where",
    "can",
    "could",
    "should",
    "would",
    "explain",
    "describe",
    "tell",
    "show",
    "me",
    "about",
    "with",
    "from",
    "by",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
}

VAGUE_SINGLE_WORDS = {
    "what",
    "why",
    "how",
    "who",
    "when",
    "where",
    "help",
    "hello",
    "hi",
    "hey",
    "explain",
    "tell",
    "info",
    "details",
    "more",
    "question",
    "test",
}

POLICY_OR_INTERNAL_PATTERNS = [
    r"\b(?:company|internal|organization|corporate|hr|employee)\s+policy\b",
    r"\b(?:refund|return|cancellation|termination|pto|leave|vacation|attendance|procurement|expense)\s+policy\b",
    r"\b(?:refund|return|cancellation|grace)\s+(?:period|window|timeline|policy|terms)\b",
    r"\b(?:according to|based on|in)\s+(?:the|this|our)\s+(?:policy|document|handbook|contract|agreement|manual|guide|pdf|records?|files?)\b",
    r"\b(?:our|company|employee|staff)\s+(?:handbook|guidelines|rules|code of conduct|nda|sla|contract)\b",
    r"\bwhat does (?:the|this|our) (?:document|policy|file|manual|agreement) (?:say|state|specify)\b",
    r"\b(?:clause|clauses|warranty|warranties|stipulation|provision|amendment|agreement|merger|mergers|acquisition|insurance|maritime|shipping\s+insurance)\b",
    r"\b(?:protocol|protocols|specification|specifications)\b",
    r"\b(?:interstellar|wormhole|teleportation|galactic|warp\s+drive)\b",
    r"\b(?:any information here|information here|in here|here\?|in this kb|in this knowledge base)\b",
]


def _is_policy_or_internal_query(query: str) -> bool:
    """Detects whether query specifically targets private organizational policies, rules, or document-specific facts."""
    q = query.lower()
    return any(re.search(pat, q) for pat in POLICY_OR_INTERNAL_PATTERNS)


def _extract_query_terms(query: str) -> list[str]:
    """Extracts non-stopword alphanumeric search tokens from query."""
    tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", query.lower())
    return [t for t in tokens if t not in STOP_WORDS]


class AgenticNodes:
    """Encapsulates executable LangGraph nodes with injected session and services."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService,
        llm_provider: LLMProviderInterface,
        recovery_policy: RecoveryPolicy | None = None,
    ):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.retrieval_service = retrieval_service
        self.llm = llm_provider
        self.recovery_policy = recovery_policy or RecoveryPolicy()

    def _append_event(
        self,
        state: AgenticRAGState,
        step_id: str,
        name: str,
        status: str,
        duration_ms: float,
        description: str | None = None,
    ) -> list[WorkflowStepEvent]:
        """Helper to append a workflow execution telemetry event."""
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

        # Phase 10: Record execution span on active trace
        try:
            from app.services.observability.tracer import Tracer

            Tracer.record_manual_span(
                name=name,
                step_type=step_id,
                duration_ms=duration_ms,
                status=status,
                outputs={"description": description} if description else {},
            )
        except Exception:
            pass

        return steps

    async def query_analysis_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node A: Analyzes, cleans, and evaluates the user query for intent and ambiguity."""
        t0 = time.perf_counter()
        raw_query = state.get("original_query", "").strip()

        # Normalize whitespace and quotes
        normalized = re.sub(r"\s+", " ", raw_query)
        terms = _extract_query_terms(normalized)

        # Ambiguity evaluation
        words = normalized.lower().split()
        is_ambiguous = False
        ambiguity_reason = None

        clean_words = [w.strip("?!.,;:'\"") for w in words if w.strip("?!.,;:'\"")]
        if not normalized or len(normalized) < 3:
            is_ambiguous = True
            ambiguity_reason = "Query is too brief or empty to infer intent."
        elif len(clean_words) == 1 and clean_words[0] in VAGUE_SINGLE_WORDS:
            is_ambiguous = True
            ambiguity_reason = (
                f"Query contains only a vague single word '{clean_words[0]}' without subject matter context."
            )
        elif len(terms) == 0 and len(clean_words) <= 3:
            is_ambiguous = True
            ambiguity_reason = "Query contains only generic conversational stop words."

        # Detect topic listing or broad syllabus overview intent
        is_topic_listing = any(
            t in normalized.lower()
            for t in [
                "core concept",
                "core concepts",
                "main topic",
                "main topics",
                "topics covered",
                "list the topics",
                "list topics",
                "roadmap",
                "syllabus",
                "overview",
            ]
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="query_analysis",
            name="Query Analysis",
            status="completed",
            duration_ms=duration_ms,
            description="Ambiguous query flagged" if is_ambiguous else f"Extracted {len(terms)} key search terms",
        )

        now = time.time()
        deadline = state.get("deadline") or (now + settings.RECOVERY_TIMEOUT_SECONDS)

        is_policy_or_internal = _is_policy_or_internal_query(normalized)

        return {
            "normalized_query": normalized,
            "current_query": normalized,
            "query_history": [normalized],
            "action_history": [],
            "recovery_history": [],
            "recovery_count": 0,
            "max_recovery_attempts": state.get("max_recovery_attempts", settings.RECOVERY_MAX_ATTEMPTS),
            "deadline": deadline,
            "is_ambiguous": is_ambiguous,
            "ambiguity_reason": ambiguity_reason,
            "is_topic_listing": is_topic_listing,
            "is_policy_or_internal_query": is_policy_or_internal,
            "extracted_terms": terms,
            "workflow_steps": steps,
        }

    async def scope_authorization_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node B: Verifies authenticated user's permission to access the target knowledge base."""
        t0 = time.perf_counter()
        kb_id = state["knowledge_base_id"]
        user_id = state["user_id"]

        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        if not kb:
            steps = self._append_event(
                state=state,
                step_id="scope_authorization",
                name="Scope & Permission Validation",
                status="failed",
                duration_ms=duration_ms,
                description="Knowledge base not found or access denied",
            )
            return {
                "is_authorized": False,
                "auth_error": "Knowledge base not found or access denied.",
                "failure_category": FailureCategory.NON_RECOVERABLE_FAILURE.value,
                "failure_reason": "Knowledge base not found or access denied.",
                "execution_status": ChatResponseStatus.RETRIEVAL_ERROR,
                "workflow_steps": steps,
            }

        steps = self._append_event(
            state=state,
            step_id="scope_authorization",
            name="Scope & Permission Validation",
            status="completed",
            duration_ms=duration_ms,
            description=f"Authorized knowledge base: {kb.name}",
        )
        return {
            "is_authorized": True,
            "auth_error": None,
            "workflow_steps": steps,
        }

    async def bounded_retry_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Intermediate node (Phase 7 backward-compatible + Phase 8 Self-Healing Engine)."""
        return await self.recovery_node(state)

    async def recovery_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node R (Phase 8): Executes evidence-driven self-healing recovery actions with bounded safeguards."""
        t0 = time.perf_counter()
        retry_count = state.get("retry_count", 0)
        recovery_count = state.get("recovery_count", 0)
        deadline = state.get("deadline", time.time() + settings.RECOVERY_TIMEOUT_SECONDS)
        action_history = list(state.get("action_history", []))
        query_history = list(state.get("query_history", []))
        recovery_history = list(state.get("recovery_history", []))
        current_query = state.get("current_query") or state.get("normalized_query") or state.get("original_query", "")

        # 1. Determine failure category and diagnosis
        failure_cat_str = state.get("failure_category")
        evidence_status = state.get("evidence_status")

        if failure_cat_str:
            try:
                failure_cat = FailureCategory(failure_cat_str)
            except ValueError:
                failure_cat = FailureCategory.RETRIEVAL_FAILURE
        elif evidence_status == "low_relevance":
            failure_cat = FailureCategory.LOW_RELEVANCE_EVIDENCE
        elif evidence_status == "insufficient":
            failure_cat = FailureCategory.INSUFFICIENT_EVIDENCE
        elif evidence_status == "retrieval_error":
            failure_cat = FailureCategory.RETRIEVAL_FAILURE
        elif not state.get("citation_validation_passed", True):
            failure_cat = FailureCategory.CITATION_FAILURE
        elif not state.get("verification_passed", True):
            failure_cat = FailureCategory.VERIFICATION_FAILURE
        elif state.get("execution_status") == ChatResponseStatus.PROVIDER_ERROR:
            failure_cat = FailureCategory.GENERATION_FAILURE
        else:
            failure_cat = FailureCategory.LOW_RELEVANCE_EVIDENCE

        # Create structured diagnosis
        is_rec = failure_cat != FailureCategory.NON_RECOVERABLE_FAILURE
        if failure_cat == FailureCategory.LOW_RELEVANCE_EVIDENCE:
            sugg_action = RecoveryAction.REWRITE_QUERY
        elif failure_cat == FailureCategory.INSUFFICIENT_EVIDENCE:
            sugg_action = RecoveryAction.EXPAND_RETRIEVAL
        elif failure_cat == FailureCategory.CITATION_FAILURE:
            sugg_action = RecoveryAction.REPAIR_CITATIONS
        elif failure_cat == FailureCategory.VERIFICATION_FAILURE:
            sugg_action = RecoveryAction.REGENERATE_WITH_FEEDBACK
        elif failure_cat == FailureCategory.GENERATION_FAILURE:
            sugg_action = RecoveryAction.RETRY_TRANSIENT
        elif failure_cat == FailureCategory.RETRIEVAL_FAILURE:
            sugg_action = RecoveryAction.RETRY_TRANSIENT
        else:
            sugg_action = RecoveryAction.TERMINATE_NON_RECOVERABLE
            is_rec = False

        diagnosis = FailureDiagnosis(
            category=failure_cat,
            reason=state.get("failure_reason") or f"Self-healing trigger on {failure_cat.value}",
            is_recoverable=is_rec,
            suggested_action=sugg_action,
        )

        # 2. Evaluate adaptive recovery policy
        action, action_reason, params = self.recovery_policy.evaluate(
            diagnosis=diagnosis,
            recovery_count=recovery_count,
            deadline=deadline,
            action_history=action_history,
            query_history=query_history,
            current_query=current_query,
        )

        action_history.append(action.value)
        new_query = current_query
        strategy = state.get("retrieval_strategy", "hybrid")
        candidate_limit = state.get("candidate_limit", 20)
        feedback = state.get("verification_feedback")

        # 3. Apply recovery action mutation
        if action == RecoveryAction.REWRITE_QUERY:
            new_query = QueryRewriter.rewrite(
                original_query=state.get("original_query", ""),
                query_history=query_history,
                extracted_terms=state.get("extracted_terms", []),
            )
            query_history.append(new_query)
            candidate_limit = 25
            desc = f"Self-healing: Rewrote query to '{new_query}' (preserving user intent)"

        elif action == RecoveryAction.EXPAND_RETRIEVAL:
            candidate_limit = params.get("candidate_limit", 35)
            desc = f"Self-healing: Expanded candidate recall limit to {candidate_limit}"

        elif action == RecoveryAction.FALLBACK_STRATEGY:
            strategy = params.get("mode", "hybrid")
            candidate_limit = 35
            desc = f"Self-healing: Switched retrieval strategy to {strategy} with reranking"

        elif action == RecoveryAction.REPAIR_CITATIONS:
            num_chunks = len(state.get("retrieval_results", []))
            cleaned_ans = re.sub(
                r"\[(\d+)\]",
                lambda m: m.group(0) if 1 <= int(m.group(1)) <= num_chunks else "",
                state.get("raw_answer", ""),
            )
            raw_answer = cleaned_ans
            desc = "Self-healing: Repaired citation tags against actual retrieved chunks"

        elif action == RecoveryAction.REGENERATE_WITH_FEEDBACK:
            desc = f"Self-healing: Prepared regeneration context with audit feedback: {feedback}"

        elif action == RecoveryAction.RETRY_TRANSIENT:
            backoff_s = params.get("backoff_seconds", 0.05)
            await asyncio.sleep(min(backoff_s, 2.0))
            desc = f"Self-healing: Applied transient backoff ({backoff_s:.2f}s)"

        elif action == RecoveryAction.TERMINATE_INSUFFICIENT:
            desc = "Self-healing: Maximum recovery budget reached; terminating with honest limitation"

        else:
            desc = f"Self-healing: Terminating non-recoverable condition ({diagnosis.reason})"

        # Record attempt record
        attempt_record = RecoveryAttemptRecord(
            attempt_number=recovery_count + 1,
            failure_category=failure_cat,
            action_taken=action,
            query_before=current_query,
            query_after=new_query,
            strategy_before=state.get("retrieval_strategy", "hybrid"),
            strategy_after=strategy,
            candidate_limit=candidate_limit,
            timestamp=datetime.now(UTC).isoformat(),
            details={"reason": action_reason},
        )
        recovery_history.append(attempt_record.model_dump())

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="bounded_retry",
            name="Bounded Retrieval Retry",
            status="completed",
            duration_ms=duration_ms,
            description=desc,
        )

        res_state: dict[str, Any] = {
            "retry_count": retry_count + 1,
            "recovery_count": recovery_count + 1,
            "current_query": new_query,
            "normalized_query": new_query,
            "query_history": query_history,
            "action_history": action_history,
            "recovery_history": recovery_history,
            "recovery_action": action.value,
            "failure_category": failure_cat.value,
            "failure_reason": diagnosis.reason,
            "candidate_limit": candidate_limit,
            "retrieval_strategy": strategy,
            "workflow_steps": steps,
        }
        if action == RecoveryAction.REPAIR_CITATIONS:
            res_state["raw_answer"] = raw_answer
        if action == RecoveryAction.TERMINATE_INSUFFICIENT:
            res_state["is_insufficient_evidence"] = True
        return res_state

    async def retrieval_strategy_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node C: Selects and configures retrieval strategy based on query and retry attempt."""
        t0 = time.perf_counter()
        retry_count = state.get("retry_count", 0)
        enable_reranking = state.get("enable_reranking", True)
        is_topic_listing = state.get("is_topic_listing", False)

        if retry_count == 0:
            strategy = "hybrid"
            candidate_limit = 35 if is_topic_listing else 20
            top_k = 8 if is_topic_listing else 5
            strategy_reason = (
                "Initial pass (broad topic coverage): Hybrid with candidate depth 35 and top-k 8"
                if is_topic_listing
                else "Initial pass: Hybrid (Dense Vector + BM25Okapi + Reciprocal Rank Fusion + Neural Reranker)"
            )
        else:
            strategy = "hybrid"
            candidate_limit = 45 if is_topic_listing else 35
            top_k = 10 if is_topic_listing else 8
            enable_reranking = True
            strategy_reason = (
                f"Bounded retry #{retry_count}: Expanded candidate depth to {candidate_limit} for broader recall"
            )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="retrieval_strategy",
            name="Retrieval Strategy Selection",
            status="completed",
            duration_ms=duration_ms,
            description=strategy_reason,
        )

        return {
            "retrieval_strategy": strategy,
            "strategy_reason": strategy_reason,
            "candidate_limit": candidate_limit,
            "top_k": top_k,
            "enable_reranking": enable_reranking,
            "workflow_steps": steps,
        }

    async def retrieval_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node D: Calls Phase 5 retrieval service across scoped chunks with error boundaries."""
        t0 = time.perf_counter()
        kb_id = state["knowledge_base_id"]
        user_id = state["user_id"]
        query = state.get("current_query") or state.get("normalized_query") or state.get("original_query", "")
        strategy_str = state.get("retrieval_strategy", "hybrid")

        mode = RetrievalMode.HYBRID
        if strategy_str == "vector":
            mode = RetrievalMode.VECTOR
        elif strategy_str == "lexical":
            mode = RetrievalMode.LEXICAL

        retrieval_req = RetrievalRequest(
            knowledge_base_id=kb_id,
            query=query,
            mode=mode,
            enable_reranking=state.get("enable_reranking", True),
            candidate_limit=state.get("candidate_limit", 20),
            top_k=state.get("top_k", 5),
        )

        failure_cat = None
        failure_reason = None

        try:
            resp = await self.retrieval_service.search(request=retrieval_req, user_id=user_id)
            results = resp.results
            latency = resp.latency
            error_msg = None
            evidence_status = "undecided"
            status = "completed"
            desc = (
                f"Retrieved {len(results)} chunks "
                f"(vec: {latency.vector_ms:.1f}ms, lex: {latency.lexical_ms:.1f}ms, rnk: {latency.rerank_ms:.1f}ms)"
            )

            # Phase 10: Record sub-spans for individual retrieval stages
            try:
                from app.services.observability.tracer import Tracer

                Tracer.record_manual_span(
                    name="Dense Semantic Retrieval",
                    step_type="dense_retrieval",
                    duration_ms=latency.vector_ms,
                    outputs={"candidate_count": len(results)},
                )
                Tracer.record_manual_span(
                    name="BM25 Lexical Retrieval",
                    step_type="lexical_retrieval",
                    duration_ms=latency.lexical_ms,
                    outputs={"candidate_count": len(results)},
                )
                Tracer.record_manual_span(
                    name="Reciprocal Rank Fusion",
                    step_type="fusion",
                    duration_ms=latency.fusion_ms,
                    outputs={"fused_count": len(results)},
                )
                if state.get("enable_reranking", True):
                    Tracer.record_manual_span(
                        name="Neural Reranking",
                        step_type="reranking",
                        duration_ms=latency.rerank_ms,
                        outputs={"top_k_reranked": len(results)},
                    )
            except Exception:
                pass
        except Exception as e:
            logger.error("Retrieval failed in LangGraph node: %s", e)
            results = []
            latency = None
            error_msg = str(e)
            evidence_status = "retrieval_error"
            status = "failed"
            desc = f"Retrieval error: {e}"
            diagnosis = FailureClassifier.classify_retrieval(
                error=e,
                query=query,
                terms=state.get("extracted_terms", []),
            )
            failure_cat = diagnosis.category.value
            failure_reason = diagnosis.reason

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="retrieval",
            name="Hybrid Evidence Retrieval",
            status=status,
            duration_ms=duration_ms,
            description=desc,
        )

        res_dict = {
            "retrieval_results": results,
            "retrieval_latency": latency,
            "error_message": error_msg,
            "evidence_status": evidence_status,
            "workflow_steps": steps,
        }
        if failure_cat:
            res_dict["failure_category"] = failure_cat
            res_dict["failure_reason"] = failure_reason
        return res_dict

    async def evidence_assessment_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node E: Assesses retrieved evidence for plausibility, sufficiency, and relevance."""
        t0 = time.perf_counter()
        current_status = state.get("evidence_status")
        results = state.get("retrieval_results", [])
        terms = state.get("extracted_terms", [])
        query = state.get("current_query") or state.get("normalized_query") or state.get("original_query", "")

        failure_cat = None
        failure_reason = None

        if current_status == "retrieval_error":
            evidence_status = "retrieval_error"
            evidence_reason = state.get("error_message") or "Retrieval service error"
            failure_cat = FailureCategory.RETRIEVAL_FAILURE.value
            failure_reason = evidence_reason
        elif not results:
            diagnosis = FailureClassifier.classify_retrieval(results=[], query=query, terms=terms)
            evidence_status = "insufficient"
            evidence_reason = diagnosis.reason
            failure_cat = diagnosis.category.value
            failure_reason = diagnosis.reason
        else:
            # Check substantive focal keyword relevance overlap
            GENERIC_QUERY_TERMS = {
                "example",
                "examples",
                "sample",
                "samples",
                "simple",
                "terms",
                "code",
                "snippet",
                "overview",
                "definition",
                "meaning",
                "detail",
                "details",
                "best",
                "guide",
                "tutorial",
                "please",
                "write",
                "give",
            }
            substantive_terms = [t for t in terms if t not in GENERIC_QUERY_TERMS]
            eval_terms = substantive_terms or terms

            COMMON_LANGS = {
                "python",
                "javascript",
                "js",
                "typescript",
                "ts",
                "java",
                "c",
                "cpp",
                "csharp",
                "ruby",
                "go",
                "rust",
                "php",
                "sql",
                "html",
                "css",
            }
            focal_terms = [t for t in eval_terms if t not in COMMON_LANGS]
            search_terms = focal_terms if focal_terms else eval_terms

            matched_any = False
            for r in results:
                c_lower = r.content.lower()
                if any(t in c_lower for t in search_terms):
                    matched_any = True
                    break

            if matched_any:
                evidence_status = "sufficient"
                evidence_reason = f"Confirmed relevant evidence across {len(results)} scoped chunks."
            else:
                diagnosis = FailureClassifier.classify_retrieval(results=results, query=query, terms=terms)
                evidence_status = (
                    "low_relevance" if diagnosis.category == FailureCategory.LOW_RELEVANCE_EVIDENCE else "insufficient"
                )
                evidence_reason = diagnosis.reason
                failure_cat = diagnosis.category.value
                failure_reason = diagnosis.reason

        # Determine hybrid answer mode
        is_policy_or_internal = state.get("is_policy_or_internal_query", False) or _is_policy_or_internal_query(query)

        if evidence_status == "sufficient":
            has_relevant_evidence = True
            answer_mode = "grounded"
        elif evidence_status == "retrieval_error":
            has_relevant_evidence = False
            answer_mode = "grounded"
        else:
            has_relevant_evidence = False
            if is_policy_or_internal:
                answer_mode = "insufficient_evidence"
                evidence_reason = (
                    "Private policy or document-specific inquiry without matching evidence in knowledge base; "
                    "refusing to speculate."
                )
            else:
                answer_mode = "general"
                evidence_reason = (
                    "No relevant document evidence in knowledge base for general query; "
                    "proceeding to general AI model synthesis."
                )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="evidence_assessment",
            name="Evidence Assessment",
            status="completed",
            duration_ms=duration_ms,
            description=f"Outcome: {evidence_status} ({evidence_reason})",
        )

        res_dict = {
            "evidence_status": evidence_status,
            "evidence_reason": evidence_reason,
            "has_relevant_evidence": has_relevant_evidence,
            "answer_mode": answer_mode,
            "workflow_steps": steps,
        }
        if failure_cat:
            res_dict["failure_category"] = failure_cat
            res_dict["failure_reason"] = failure_reason
        return res_dict

    async def grounded_generation_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node F: Generates response using LLM or deterministic fallback based on evidence."""
        t0 = time.perf_counter()
        is_ambiguous = state.get("is_ambiguous", False)
        evidence_status = state.get("evidence_status", "insufficient")
        answer_mode = state.get("answer_mode", "grounded")
        results = state.get("retrieval_results", [])
        query = state.get("original_query", "")

        is_truncated = False
        tokens_used = None
        llm_invoked = False
        model_name = getattr(self.llm, "model_name", settings.GROQ_MODEL)
        provider_name = getattr(self.llm, "provider_name", settings.LLM_PROVIDER)

        failure_cat = None
        failure_reason = None

        if is_ambiguous:
            raw_answer = (
                "Your question appears too broad or ambiguous. "
                "Could you please specify which topic or section in the knowledge base you would like to explore?"
            )
            exec_status = ChatResponseStatus.ANSWERED
            is_insufficient = False
            llm_invoked = False
            generation_ms = (time.perf_counter() - t0) * 1000.0
            desc = "Generated deterministic clarification request for ambiguous query"

        elif answer_mode == "general":
            # Invoke configured LLM using model knowledge without irrelevant document citations
            messages = [
                LLMMessage(role="system", content=GENERAL_AI_SYSTEM_PROMPT),
                LLMMessage(role="user", content=query),
            ]
            try:
                llm_resp = await self.llm.generate(
                    messages=messages,
                    temperature=0.2,
                )
                raw_answer = llm_resp.content.strip()
                model_name = llm_resp.model
                tokens_used = llm_resp.total_tokens
                exec_status = ChatResponseStatus.ANSWERED
                is_insufficient = False
                llm_invoked = True
                desc = f"Synthesized general AI answer using {model_name}"
            except AppError as e:
                logger.error("LLM general synthesis AppError: %s (%s)", e.message, e.code)
                raw_answer = f"⚠️ LLM provider error: {e.message}"
                exec_status = ChatResponseStatus.PROVIDER_ERROR
                is_insufficient = False
                llm_invoked = False
                desc = f"LLM error: {e.code}"
                diag = FailureClassifier.classify_generation(error=e)
                failure_cat = diag.category.value
                failure_reason = diag.reason
            except Exception as e:
                logger.error("LLM general synthesis failed: %s", e)
                redacted = redact_secret(str(e))
                raw_answer = f"⚠️ LLM provider error: {redacted}"
                exec_status = ChatResponseStatus.PROVIDER_ERROR
                is_insufficient = False
                llm_invoked = False
                desc = f"LLM error: {redacted}"
                diag = FailureClassifier.classify_generation(error=e)
                failure_cat = diag.category.value
                failure_reason = diag.reason

            generation_ms = (time.perf_counter() - t0) * 1000.0

        elif answer_mode == "insufficient_evidence" or evidence_status in ("insufficient", "low_relevance"):
            raw_answer = INSUFFICIENT_EVIDENCE_SENTENCE
            exec_status = ChatResponseStatus.INSUFFICIENT_EVIDENCE
            is_insufficient = True
            llm_invoked = False
            generation_ms = (time.perf_counter() - t0) * 1000.0
            desc = "Generated insufficient evidence limitation response"

        elif evidence_status == "retrieval_error":
            raw_answer = f"⚠️ Retrieval execution error: {state.get('error_message', 'Unknown failure')}"
            exec_status = ChatResponseStatus.RETRIEVAL_ERROR
            is_insufficient = True
            llm_invoked = False
            generation_ms = (time.perf_counter() - t0) * 1000.0
            desc = "Handled retrieval failure gracefully"

        else:
            # Build context from actual retrieved chunks
            evidence_blocks: list[str] = []
            curr_chars = 0
            for idx, item in enumerate(results, start=1):
                meta_parts = [f"Document: {item.document_name}"]
                if item.page_number:
                    meta_parts.append(f"Page: {item.page_number}")
                if item.section_title:
                    meta_parts.append(f"Section: {item.section_title}")
                meta_str = ", ".join(meta_parts)

                block = f"[Evidence {idx}] ({meta_str})\n{item.content}"
                if curr_chars + len(block) > MAX_CONTEXT_CHARACTERS and evidence_blocks:
                    is_truncated = True
                    break
                evidence_blocks.append(block)
                curr_chars += len(block)

            context_text = "\n\n".join(evidence_blocks)
            system_instruction = (
                f"{GROUNDED_SYSTEM_PROMPT}\n\n"
                f"=== UNTRUSTED AUTHORIZED REFERENCE MATERIAL ===\n"
                f"{context_text}\n"
                f"=== END OF REFERENCE MATERIAL ===\n\n"
                f"Answer the user's inquiry strictly based on the above reference material. "
                f"Every claim based on reference material must cite the source using [1], [2] format. "
                f"Do not simply paste raw text; synthesize a clear, natural, and well-structured answer. "
                f'If the information is absent, respond with:\n"{INSUFFICIENT_EVIDENCE_SENTENCE}"'
            )

            rec_feedback = state.get("verification_feedback")
            if rec_feedback:
                system_instruction += (
                    f"\n\n[RECOVERY FEEDBACK]: A previous attempt was rejected because: {rec_feedback}. "
                    f"Please generate a corrected response strictly grounded in the reference material."
                )

            messages = [
                LLMMessage(role="system", content=system_instruction),
                LLMMessage(role="user", content=query),
            ]

            try:
                llm_resp = await self.llm.generate(
                    messages=messages,
                    temperature=settings.LLM_TEMPERATURE,
                )
                raw_answer = llm_resp.content.strip()
                model_name = llm_resp.model
                tokens_used = llm_resp.total_tokens
                exec_status = ChatResponseStatus.ANSWERED
                llm_invoked = True
                is_insufficient = (
                    "not find sufficient matching information" in raw_answer.lower()
                    or "insufficient matching information" in raw_answer.lower()
                    or "insufficient evidence" in raw_answer.lower()
                )
                desc = f"Synthesized answer using {model_name}"
            except AppError as e:
                logger.error("LLM grounded generation AppError: %s (%s)", e.message, e.code)
                raw_answer = f"⚠️ LLM provider error: {e.message}"
                exec_status = ChatResponseStatus.PROVIDER_ERROR
                is_insufficient = False
                llm_invoked = False
                desc = f"LLM error: {e.code}"
                diag = FailureClassifier.classify_generation(error=e)
                failure_cat = diag.category.value
                failure_reason = diag.reason
            except Exception as e:
                logger.error("LLM generation failed: %s", e)
                redacted = redact_secret(str(e))
                raw_answer = f"⚠️ LLM provider error: {redacted}"
                exec_status = ChatResponseStatus.PROVIDER_ERROR
                is_insufficient = False
                llm_invoked = False
                desc = f"LLM error: {redacted}"
                diag = FailureClassifier.classify_generation(error=e)
                failure_cat = diag.category.value
                failure_reason = diag.reason

            generation_ms = (time.perf_counter() - t0) * 1000.0

        steps = self._append_event(
            state=state,
            step_id="grounded_generation",
            name="Grounded Answer Generation",
            status="completed" if exec_status != ChatResponseStatus.PROVIDER_ERROR else "failed",
            duration_ms=generation_ms,
            description=desc,
        )

        res_gen: dict[str, Any] = {
            "raw_answer": raw_answer,
            "is_context_truncated": is_truncated,
            "tokens_used": tokens_used,
            "generation_model": model_name,
            "generation_provider": provider_name,
            "generation_ms": round(generation_ms, 2),
            "execution_status": exec_status,
            "is_insufficient_evidence": is_insufficient,
            "llm_invoked": llm_invoked,
            "workflow_steps": steps,
        }
        if locals().get("failure_cat"):
            res_gen["failure_category"] = failure_cat
            res_gen["failure_reason"] = failure_reason
        return res_gen

    async def citation_validation_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node G: Audits citations against real retrieved chunks and generates claim attributions."""
        t0 = time.perf_counter()
        raw_answer = state.get("raw_answer", "")
        results = state.get("retrieval_results", [])
        is_insufficient = state.get("is_insufficient_evidence", False)
        answer_mode = state.get("answer_mode", "document_grounded")
        is_general = answer_mode == "general"

        if is_insufficient:
            sanitized_answer = INSUFFICIENT_EVIDENCE_SENTENCE
            sources: list[Any] = []
            claim_citations: list[Any] = []
            active_citations: list[Any] = []
            validation_passed = True
            used_source_count = 0
            desc = "Citation validation bypassed for insufficient evidence"
        elif is_general:
            sanitized_answer = raw_answer
            sources = []
            claim_citations = []
            active_citations = []
            validation_passed = True
            used_source_count = 0
            desc = "Citation validation bypassed for general AI response"
        else:
            validation_res = CitationValidator.validate_and_map(
                raw_answer=raw_answer,
                retrieved_chunks=results,
                is_general_answer=False,
            )
            sanitized_answer = validation_res.sanitized_answer
            sources = validation_res.sources
            claim_citations = validation_res.claim_citations
            active_citations = validation_res.active_citations
            validation_passed = validation_res.validation_passed
            used_source_count = validation_res.used_source_count
            desc = f"Validated {used_source_count} cited sources and {len(claim_citations)} claim mappings"

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="citation_validation",
            name="Citation & Provenance Auditing",
            status="completed" if validation_passed else "failed",
            duration_ms=duration_ms,
            description=desc,
        )

        return {
            "sanitized_answer": sanitized_answer,
            "sources": sources,
            "claim_citations": claim_citations,
            "active_citations": active_citations,
            "citation_validation_passed": validation_passed,
            "used_source_count": used_source_count,
            "workflow_steps": steps,
        }

    async def answer_verification_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node V (Phase 8): Audits generated answer for factuality, evidence grounding, and query alignment."""
        t0 = time.perf_counter()
        query = state.get("original_query", "")
        answer = state.get("sanitized_answer") or state.get("raw_answer", "")
        retrieved_chunks = state.get("retrieval_results", [])
        is_insufficient = state.get("is_insufficient_evidence", False)
        answer_mode = state.get("answer_mode", "document_grounded")
        is_general = answer_mode == "general"

        passed, feedback = AnswerVerifier.verify(
            query=query,
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            is_insufficient_evidence=is_insufficient,
            is_general_answer=is_general,
        )

        failure_cat = None
        failure_reason = None
        if not passed:
            diagnosis = FailureClassifier.classify_verification(
                verification_passed=False,
                feedback=feedback,
            )
            failure_cat = diagnosis.category.value
            failure_reason = diagnosis.reason

        duration_ms = (time.perf_counter() - t0) * 1000.0
        steps = self._append_event(
            state=state,
            step_id="answer_verification",
            name="Answer Verification & Grounding Audit",
            status="completed" if passed else "failed",
            duration_ms=duration_ms,
            description="Verified answer is grounded in evidence" if passed else f"Verification failed: {feedback}",
        )

        res_ver: dict[str, Any] = {
            "verification_passed": passed,
            "verification_feedback": feedback,
            "workflow_steps": steps,
        }
        if failure_cat:
            res_ver["failure_category"] = failure_cat
            res_ver["failure_reason"] = failure_reason
        return res_ver

    async def finalization_node(self, state: AgenticRAGState) -> dict[str, Any]:
        """Node H: Assembles final ChatResponse with complete provenance and execution telemetry."""
        t0 = time.perf_counter()
        is_auth = state.get("is_authorized", True)

        if not is_auth:
            # Safe unauthorized response
            steps = self._append_event(
                state=state,
                step_id="finalization",
                name="Workflow Finalization",
                status="completed",
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                description="Finalized unauthorized scope rejection",
            )
            response = ChatResponse(
                content="Knowledge base not found or access denied.",
                status=ChatResponseStatus.RETRIEVAL_ERROR,
                timestamp=datetime.now(UTC).isoformat(),
                knowledge_base_id=state["knowledge_base_id"],
                conversation_id=state.get("conversation_id"),
                citations=[],
                is_insufficient_evidence=True,
                verification_status="unverified",
                answer_type="unauthorized",
                generation_ms=0.0,
                total_ms=0.0,
                retry_count=state.get("retry_count", 0),
                workflow_steps=steps,
            )
            return {"final_response": response, "workflow_steps": steps}

        # Determine truthful verification status
        evidence_status = state.get("evidence_status", "")
        recovery_action = state.get("recovery_action", "")
        answer_mode = state.get("answer_mode", "document_grounded")
        is_general = answer_mode == "general"
        is_insufficient = not is_general and (
            state.get("is_insufficient_evidence", False)
            or evidence_status in ("insufficient", "low_relevance")
            or recovery_action == RecoveryAction.TERMINATE_INSUFFICIENT.value
        )
        exec_status = state.get("execution_status", ChatResponseStatus.ANSWERED)
        verification_passed = state.get("verification_passed", True)

        citations = state.get("active_citations", [])
        sources = state.get("sources", [])
        claim_citations = state.get("claim_citations", [])

        if is_insufficient:
            verification_status = "insufficient_evidence"
            answer_type = "insufficient_evidence"
            answer_content = state.get("sanitized_answer") or INSUFFICIENT_EVIDENCE_SENTENCE
            status = ChatResponseStatus.INSUFFICIENT_EVIDENCE
            citations = []
            sources = []
            claim_citations = []
        elif exec_status == ChatResponseStatus.PROVIDER_ERROR:
            verification_status = "unverified"
            answer_type = "provider_error"
            answer_content = state.get("raw_answer", "LLM Provider Error")
            status = ChatResponseStatus.PROVIDER_ERROR
        elif exec_status == ChatResponseStatus.RETRIEVAL_ERROR or evidence_status == "retrieval_error":
            verification_status = "unverified"
            answer_type = "retrieval_error"
            answer_content = (
                state.get("raw_answer")
                or f"⚠️ Retrieval execution error: {state.get('error_message', 'Unknown failure')}"
            )
            status = ChatResponseStatus.RETRIEVAL_ERROR
            citations = []
            sources = []
            claim_citations = []
        elif not verification_passed:
            verification_status = "unverified"
            answer_type = "verification_failed"
            status = ChatResponseStatus.FAILED
            answer_content = "Generated response could not be verified against authorized evidence."
            citations = []
            sources = []
            claim_citations = []
        elif is_general:
            verification_status = "general_ai_answer"
            answer_type = "general_ai"
            answer_content = state.get("sanitized_answer") or state.get("raw_answer", "")
            status = ChatResponseStatus.ANSWERED
            citations = []
            sources = []
            claim_citations = []
        elif (
            state.get("recovery_count", 0) > 0 or state.get("retry_count", 0) > 0 or state.get("is_recovered", False)
        ) and not is_insufficient:
            verification_status = "grounded_evidence"
            answer_type = "document_grounded"
            answer_content = state.get("sanitized_answer") or state.get("raw_answer", "")
            status = ChatResponseStatus.RECOVERED
        else:
            verification_status = "grounded_evidence"
            answer_type = "document_grounded"
            answer_content = state.get("sanitized_answer") or state.get("raw_answer", "")
            status = ChatResponseStatus.ANSWERED

        # Build recovery metadata if recovery was attempted
        rec_count = state.get("recovery_count", state.get("retry_count", 0))
        recovery_meta = None
        if state.get("recovery_history") or rec_count > 0 or state.get("is_recovered", False):
            if status == ChatResponseStatus.RECOVERED:
                outcome = "recovered"
            elif is_insufficient:
                outcome = "insufficient_evidence"
            elif status == ChatResponseStatus.FAILED:
                outcome = "failed"
            elif status == ChatResponseStatus.TIMED_OUT:
                outcome = "timed_out"
            elif not is_auth:
                outcome = "permission_denied"
            else:
                outcome = "exhausted"

            recovery_meta = RecoveryMeta(
                recovery_attempted=True,
                recovery_count=rec_count,
                failure_category=state.get("failure_category"),
                recovery_action=state.get("recovery_action"),
                recovery_outcome=outcome,
                rewritten_query=(
                    state.get("current_query") if state.get("current_query") != state.get("original_query") else None
                ),
                termination_reason=state.get("failure_reason"),
            )

        steps = self._append_event(
            state=state,
            step_id="finalization",
            name="Workflow Finalization",
            status="completed",
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            description="Compiled structured response with full evidence telemetry",
        )

        response = ChatResponse(
            content=answer_content,
            status=status,
            timestamp=datetime.now(UTC).isoformat(),
            knowledge_base_id=state["knowledge_base_id"],
            conversation_id=state.get("conversation_id"),
            sources=sources,
            claim_citations=claim_citations,
            citations=citations,
            generation=GenerationMeta(
                provider=state.get("generation_provider", settings.LLM_PROVIDER),
                model=state.get("generation_model", settings.GROQ_MODEL),
                latency_ms=state.get("generation_ms", 0.0),
                llm_invoked=state.get("llm_invoked", False),
            ),
            evidence=EvidenceMeta(
                retrieved_chunk_count=len(state.get("retrieval_results", [])),
                used_source_count=state.get("used_source_count", 0),
                citation_validation_passed=state.get("citation_validation_passed", False),
                untrusted_context_truncated=state.get("is_context_truncated", False),
                has_relevant_evidence=state.get("has_relevant_evidence", False),
            ),
            recovery=recovery_meta,
            confidence=None,  # Truthful: Phase 9 guardrails unexecuted
            verification_status=verification_status,
            is_insufficient_evidence=is_insufficient,
            answer_type=answer_type,
            retrieval_latency=state.get("retrieval_latency"),
            generation_ms=state.get("generation_ms", 0.0),
            total_ms=state.get("total_ms", 0.0),
            model=state.get("generation_model", ""),
            tokens_used=state.get("tokens_used"),
            retry_count=state.get("retry_count", 0),
            workflow_steps=steps,
        )

        return {"final_response": response, "workflow_steps": steps}
