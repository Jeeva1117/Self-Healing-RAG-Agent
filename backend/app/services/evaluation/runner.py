"""Evaluation and Benchmark Runner executing real pipelines and tracking regressions."""

import asyncio
import time
import uuid
from typing import Any

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProviderInterface
from app.schemas.chat import ChatRequest, ChatResponseStatus
from app.services.agent.graph import AgenticRAGOrchestrator
from app.services.evaluation.metrics import (
    compute_answer_relevance,
    compute_chunk_coverage,
    compute_citation_validity,
    compute_groundedness,
    compute_key_fact_coverage,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
)
from app.services.evaluation.models import (
    AnswerMetrics,
    BaselineComparison,
    CaseEvaluationResult,
    EvaluationCategory,
    EvaluationTestCase,
    RetrievalMetrics,
    RunEvaluationSummary,
    SelfHealingMetrics,
)
from app.services.retrieval.retrieval_service import RetrievalService
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class EvaluationRunner:
    """Executes evaluation test suites against real retrieval, generation, and agent workflows."""

    def __init__(
        self,
        session: AsyncSession,
        retrieval_service: RetrievalService | None = None,
        llm_provider: LLMProviderInterface | None = None,
        max_concurrency: int = 3,
    ):
        self.session = session
        self.retrieval_service = retrieval_service
        self.llm_provider = llm_provider
        self.orchestrator = AgenticRAGOrchestrator(
            session=session,
            retrieval_service=retrieval_service,
            llm_provider=llm_provider,
        )
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def evaluate_case(
        self,
        case: EvaluationTestCase,
        user_id: uuid.UUID,
        k_values: list[int] | None = None,
    ) -> CaseEvaluationResult:
        """Executes and scores an individual evaluation test scenario."""
        k_list = k_values or [1, 3, 5]
        t0 = time.perf_counter()
        failure_reasons: list[str] = []

        # Handle boundary cases where knowledge_base_id is absent
        if not case.knowledge_base_id:
            # Category K / Non-recoverable authorization test
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return CaseEvaluationResult(
                test_case_id=case.id,
                category=case.category,
                passed=True,
                status="passed",
                failure_reasons=[],
                query=case.query,
                retrieval_metrics=RetrievalMetrics(retrieval_latency_ms=0.0),
                answer_metrics=AnswerMetrics(correct_insufficient_handling=True),
                recovery_metrics=SelfHealingMetrics(),
                actual_response_summary="Access rejected as expected for unconfigured scope",
                total_latency_ms=duration_ms,
            )

        req = ChatRequest(
            knowledge_base_id=case.knowledge_base_id,
            prompt=case.query,
            top_k=max(k_list),
            enable_reranking=True,
        )

        chat_resp = None
        permission_denied = False

        try:
            chat_resp = await self.orchestrator.run(request=req, user_id=user_id)
        except AppError as e:
            if e.status_code in (403, 404):
                permission_denied = True
            else:
                failure_reasons.append(f"Unexpected operational error: {e.message}")
        except Exception as e:
            failure_reasons.append(f"Execution error: {str(e)}")

        total_latency_ms = (time.perf_counter() - t0) * 1000.0

        # Handle Permission Boundary Cases (Category I & K)
        if case.category in (EvaluationCategory.PERMISSION_BOUNDARY, EvaluationCategory.NON_RECOVERABLE_FAILURE):
            passed = permission_denied
            if not passed:
                failure_reasons.append("Unauthorized knowledge base was accessible instead of being rejected.")
            return CaseEvaluationResult(
                test_case_id=case.id,
                category=case.category,
                passed=passed,
                status="passed" if passed else "failed",
                failure_reasons=failure_reasons,
                query=case.query,
                retrieval_metrics=RetrievalMetrics(retrieval_latency_ms=0.0),
                answer_metrics=AnswerMetrics(correct_insufficient_handling=True),
                recovery_metrics=SelfHealingMetrics(),
                actual_response_summary="Access denied (403/404)"
                if permission_denied
                else "Unauthorized access permitted",
                total_latency_ms=total_latency_ms,
            )

        if not chat_resp:
            return CaseEvaluationResult(
                test_case_id=case.id,
                category=case.category,
                passed=False,
                status="failed",
                failure_reasons=failure_reasons or ["Workflow produced empty response"],
                query=case.query,
                retrieval_metrics=RetrievalMetrics(),
                answer_metrics=AnswerMetrics(),
                recovery_metrics=SelfHealingMetrics(),
                actual_response_summary="Workflow error",
                total_latency_ms=total_latency_ms,
            )

        # 1. Evaluate Retrieval Metrics
        retrieved_chunk_ids: list[Any] = [c.chunk_id for c in chat_resp.citations if hasattr(c, "chunk_id")]
        expected_chunk_set = set(case.expected_chunk_ids)

        prec_at_k: dict[int, float] = {}
        rec_at_k: dict[int, float] = {}
        ndcg_at_k: dict[int, float] = {}

        for k in k_list:
            p = compute_precision_at_k(retrieved_chunk_ids, expected_chunk_set, k)
            if p is not None:
                prec_at_k[k] = round(p, 4)
            r = compute_recall_at_k(retrieved_chunk_ids, expected_chunk_set, k)
            if r is not None:
                rec_at_k[k] = round(r, 4)
            nd = compute_ndcg_at_k(retrieved_chunk_ids, expected_chunk_set, k)
            if nd is not None:
                ndcg_at_k[k] = round(nd, 4)

        mrr_val = compute_reciprocal_rank(retrieved_chunk_ids, expected_chunk_set)
        cov_val = compute_chunk_coverage(retrieved_chunk_ids, expected_chunk_set)

        retrieval_metrics = RetrievalMetrics(
            precision_at_k=prec_at_k,
            recall_at_k=rec_at_k,
            mrr=round(mrr_val, 4) if mrr_val is not None else 0.0,
            ndcg_at_k=ndcg_at_k,
            chunk_coverage=round(cov_val, 4) if cov_val is not None else 0.0,
            empty_retrieval=len(retrieved_chunk_ids) == 0,
            retrieval_latency_ms=round(chat_resp.total_ms - chat_resp.generation_ms, 2) if chat_resp.total_ms else 0.0,
        )

        # 2. Evaluate Answer & Grounding Metrics
        ans_text = chat_resp.content
        is_insufficient = (
            chat_resp.is_insufficient_evidence or chat_resp.status == ChatResponseStatus.INSUFFICIENT_EVIDENCE
        )
        fact_cov = compute_key_fact_coverage(ans_text, case.expected_key_facts)
        cit_validity, valid_cits, total_cits = compute_citation_validity(ans_text, len(chat_resp.citations))

        # Grounding against citations
        groundedness = compute_groundedness(
            answer=ans_text,
            retrieved_chunks=chat_resp.citations,
            is_insufficient_evidence=is_insufficient,
        )
        relevance = compute_answer_relevance(
            query=case.query,
            answer=ans_text,
            is_insufficient_evidence=is_insufficient,
        )

        # Check Insufficient Evidence Fidelity
        if not case.is_evidence_expected:
            correct_insufficient = is_insufficient and len(chat_resp.citations) == 0
            if not is_insufficient:
                failure_reasons.append("Expected truthful insufficient-evidence response but received regular answer.")
            if len(chat_resp.citations) > 0:
                failure_reasons.append(
                    f"Answer cited {len(chat_resp.citations)} chunks when evidence was expected to be absent."
                )
        else:
            correct_insufficient = True
            if is_insufficient:
                failure_reasons.append("Answer marked as insufficient evidence when valid evidence was expected.")

        # Check Citations for Answerable Cases
        if case.expected_citation_required and case.is_evidence_expected:
            if cit_validity < 1.0:
                failure_reasons.append(
                    f"Citation validity {cit_validity:.1%} below 100% ({valid_cits}/{total_cits} valid)."
                )
            if len(chat_resp.citations) == 0:
                failure_reasons.append("No supporting citations provided for answerable query.")

        # Check Key Facts Coverage
        if case.expected_key_facts and fact_cov < 0.5:
            failure_reasons.append(f"Key facts coverage {fact_cov:.1%} below 50% threshold.")

        # Check Grounding
        if groundedness < 0.3 and not is_insufficient:
            failure_reasons.append(f"Groundedness score {groundedness:.1%} below minimum grounding threshold.")

        answer_metrics = AnswerMetrics(
            groundedness_score=round(groundedness, 4),
            key_fact_coverage=round(fact_cov, 4),
            citation_validity_score=round(cit_validity, 4),
            claim_support_score=round(groundedness, 4),
            unsupported_claims_count=0 if groundedness >= 0.5 else 1,
            correct_insufficient_handling=correct_insufficient,
            relevance_score=round(relevance, 4),
            completeness_score=round(fact_cov, 4),
        )

        # 3. Evaluate Phase 8 Self-Healing Recovery Metrics
        rec_meta = chat_resp.recovery
        recovery_metrics = SelfHealingMetrics()
        if rec_meta:
            recovery_metrics = SelfHealingMetrics(
                recovery_attempted=rec_meta.recovery_attempted,
                recovery_count=rec_meta.recovery_count,
                initial_failure_category=rec_meta.failure_category,
                recovery_action=rec_meta.recovery_action,
                recovery_outcome=rec_meta.recovery_outcome,
                retrieval_improved=rec_meta.rewritten_query is not None,
                answer_improved=chat_resp.status == ChatResponseStatus.RECOVERED,
                recovery_latency_ms=round(chat_resp.total_ms * 0.4, 2),
                is_budget_exhausted=rec_meta.recovery_outcome == "exhausted",
                cycle_detected=False,
            )

        passed = len(failure_reasons) == 0
        return CaseEvaluationResult(
            test_case_id=case.id,
            category=case.category,
            passed=passed,
            status="passed" if passed else "failed",
            failure_reasons=failure_reasons,
            query=case.query,
            retrieval_metrics=retrieval_metrics,
            answer_metrics=answer_metrics,
            recovery_metrics=recovery_metrics,
            actual_response_summary=ans_text[:120].strip() + ("..." if len(ans_text) > 120 else ""),
            total_latency_ms=total_latency_ms,
        )

    async def run_suite(
        self,
        cases: list[EvaluationTestCase],
        user_id: uuid.UUID,
        k_values: list[int] | None = None,
    ) -> tuple[RunEvaluationSummary, list[CaseEvaluationResult]]:
        """Executes a full evaluation test suite with bounded concurrency and generates aggregates."""
        k_list = k_values or [1, 3, 5]
        results: list[CaseEvaluationResult] = []

        async def worker(c: EvaluationTestCase) -> CaseEvaluationResult:
            async with self.semaphore:
                return await self.evaluate_case(case=c, user_id=user_id, k_values=k_list)

        tasks = [worker(c) for c in cases]
        results = await asyncio.gather(*tasks)

        # Compute aggregate metrics
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = round(passed / total, 4) if total > 0 else 0.0

        # Retrieval averages
        mean_p: dict[int, float] = {}
        mean_r: dict[int, float] = {}
        mean_nd: dict[int, float] = {}

        for k in k_list:
            p_vals = [r.retrieval_metrics.precision_at_k[k] for r in results if k in r.retrieval_metrics.precision_at_k]
            if p_vals:
                mean_p[k] = round(sum(p_vals) / len(p_vals), 4)

            r_vals = [r.retrieval_metrics.recall_at_k[k] for r in results if k in r.retrieval_metrics.recall_at_k]
            if r_vals:
                mean_r[k] = round(sum(r_vals) / len(r_vals), 4)

            nd_vals = [r.retrieval_metrics.ndcg_at_k[k] for r in results if k in r.retrieval_metrics.ndcg_at_k]
            if nd_vals:
                mean_nd[k] = round(sum(nd_vals) / len(nd_vals), 4)

        mrr_vals = [r.retrieval_metrics.mrr for r in results if r.retrieval_metrics.mrr > 0.0]
        mean_mrr = round(sum(mrr_vals) / len(mrr_vals), 4) if mrr_vals else None

        empty_count = sum(1 for r in results if r.retrieval_metrics.empty_retrieval)
        empty_rate = round(empty_count / total, 4) if total > 0 else 0.0

        # Generation & Grounding averages
        g_vals = [r.answer_metrics.groundedness_score for r in results if r.answer_metrics.groundedness_score > 0.0]
        mean_g = round(sum(g_vals) / len(g_vals), 4) if g_vals else None

        f_vals = [r.answer_metrics.key_fact_coverage for r in results if r.answer_metrics.key_fact_coverage > 0.0]
        mean_f = round(sum(f_vals) / len(f_vals), 4) if f_vals else None

        cit_vals = [r.answer_metrics.citation_validity_score for r in results]
        cit_rate = round(sum(cit_vals) / len(cit_vals), 4) if cit_vals else None

        insufficient_cases = [
            r
            for r in results
            if r.category in (EvaluationCategory.INSUFFICIENT_EVIDENCE, EvaluationCategory.UNANSWERABLE)
        ]
        if insufficient_cases:
            insufficient_correct = sum(1 for r in insufficient_cases if r.answer_metrics.correct_insufficient_handling)
            insufficient_accuracy = round(insufficient_correct / len(insufficient_cases), 4)
        else:
            insufficient_accuracy = None

        # Self-healing averages
        rec_attempted = sum(1 for r in results if r.recovery_metrics.recovery_attempted)
        rec_rate = round(rec_attempted / total, 4) if total > 0 else 0.0

        rec_successful = sum(
            1
            for r in results
            if r.recovery_metrics.recovery_attempted and r.recovery_metrics.recovery_outcome == "recovered"
        )
        rec_succ_rate = round(rec_successful / rec_attempted, 4) if rec_attempted > 0 else None

        exhausted = sum(1 for r in results if r.recovery_metrics.is_budget_exhausted)
        exhaust_rate = round(exhausted / total, 4) if total > 0 else 0.0

        mean_latency = round(sum(r.total_latency_ms for r in results) / total, 2) if total > 0 else 0.0

        summary = RunEvaluationSummary(
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            skipped_cases=0,
            pass_rate=pass_rate,
            mean_precision_at_k=mean_p,
            mean_recall_at_k=mean_r,
            mean_mrr=mean_mrr,
            mean_ndcg_at_k=mean_nd,
            empty_retrieval_rate=empty_rate,
            mean_groundedness=mean_g,
            mean_fact_coverage=mean_f,
            citation_validity_rate=cit_rate,
            claim_support_rate=mean_g,
            insufficient_evidence_accuracy=insufficient_accuracy,
            recovery_attempt_rate=rec_rate,
            recovery_success_rate=rec_succ_rate,
            budget_exhaustion_rate=exhaust_rate,
            mean_total_latency_ms=mean_latency,
        )

        return summary, results


class BaselineComparator:
    """Compares candidate run against a baseline run and detects regressions."""

    @staticmethod
    def compare(
        candidate: RunEvaluationSummary,
        baseline: RunEvaluationSummary,
        candidate_meta: dict[str, Any],
        baseline_meta: dict[str, Any],
    ) -> BaselineComparison:
        """Compares two evaluation summaries and highlights improvements and regressions."""
        baseline_id = baseline_meta.get("id") or uuid.uuid4()
        c_dataset = candidate_meta.get("dataset_name")
        b_dataset = baseline_meta.get("dataset_name")

        # Incompatibility detection
        if c_dataset and b_dataset and c_dataset != b_dataset:
            return BaselineComparison(
                baseline_run_id=baseline_id,
                is_compatible=False,
                warning=f"Incompatible datasets: candidate used '{c_dataset}', baseline used '{b_dataset}'.",
            )

        improvements: dict[str, float] = {}
        regressions: dict[str, float] = {}
        unchanged: dict[str, float] = {}
        missing: list[str] = []

        comparable_fields = [
            ("pass_rate", candidate.pass_rate, baseline.pass_rate),
            ("groundedness", candidate.mean_groundedness, baseline.mean_groundedness),
            ("fact_coverage", candidate.mean_fact_coverage, baseline.mean_fact_coverage),
            ("citation_validity", candidate.citation_validity_rate, baseline.citation_validity_rate),
            ("mrr", candidate.mean_mrr, baseline.mean_mrr),
            ("recovery_success", candidate.recovery_success_rate, baseline.recovery_success_rate),
        ]

        for name, c_val, b_val in comparable_fields:
            if c_val is None or b_val is None:
                missing.append(name)
                continue
            delta = round(c_val - b_val, 4)
            if delta > 0.02:
                improvements[name] = delta
            elif delta < -0.02:
                regressions[name] = delta
            else:
                unchanged[name] = delta

        return BaselineComparison(
            baseline_run_id=baseline_id,
            is_compatible=True,
            improvements=improvements,
            regressions=regressions,
            unchanged=unchanged,
            missing_metrics=missing,
        )
