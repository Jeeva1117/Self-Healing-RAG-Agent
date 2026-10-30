"""Knowledge Base Coverage Engine: evidence-based content gap analysis from real retrieval history."""

from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import (
    Document,
    DocumentStatus,
    ExecutionTrace,
)
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import CoverageGapItem, CoverageReport

logger = get_logger("app.services.kb.coverage")


def _extract_top_score(retrieval_scores: object) -> float | None:
    """Safely extracts the top retrieval score whether scores are stored as a dict or a list of chunk score records."""
    if not retrieval_scores:
        return None
    if isinstance(retrieval_scores, dict):
        val = retrieval_scores.get("top_score")
        if isinstance(val, int | float):
            return float(val)
        return None
    if isinstance(retrieval_scores, list):
        scores: list[float] = []
        for item in retrieval_scores:
            if isinstance(item, dict):
                score = (
                    item.get("rerank_score")
                    or item.get("rrf_score")
                    or item.get("vector_score")
                    or item.get("score")
                )
                if isinstance(score, int | float):
                    scores.append(float(score))
            elif isinstance(item, int | float):
                scores.append(float(item))
        return max(scores) if scores else None
    return None


class KnowledgeBaseCoverageEngine:
    """Measures evidence gaps and retrieval efficacy from stored user query traces."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)

    async def analyze_coverage(
        self,
        knowledge_base_id: UUID,
        user_id: UUID,
        limit: int = 200,
    ) -> CoverageReport:
        """Analyzes real query traces against knowledge base documents to detect empirical coverage gaps."""
        kb = await self.kb_repo.get_by_id_and_owner(knowledge_base_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # 1. Fetch user traces for this knowledge base
        stmt = (
            select(ExecutionTrace)
            .where(
                ExecutionTrace.knowledge_base_id == knowledge_base_id,
                ExecutionTrace.user_id == user_id,
            )
            .order_by(ExecutionTrace.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        traces = list(result.scalars().all())

        total_queries = len(traces)
        if total_queries == 0:
            return CoverageReport(
                knowledge_base_id=knowledge_base_id,
                total_queries_analyzed=0,
                insufficient_evidence_rate=0.0,
                unretrieved_documents=[],
                evidence_gaps=[],
                recommendations=[
                    "No query execution traces found for this Knowledge Base.",
                    "Execute queries or run an evaluation suite to collect real empirical coverage metrics.",
                ],
            )

        # 2. Analyze insufficient evidence and retrieval failure rates safely across list/dict retrieval_scores
        insufficient_traces = []
        for t in traces:
            top_score = _extract_top_score(t.retrieval_scores)
            is_insufficient = (
                bool(t.evidence_sufficiency and "insufficient" in t.evidence_sufficiency.lower())
                or bool(t.error_category and "INSUFFICIENT" in t.error_category.upper())
                or (t.retrieval_scores is not None and top_score is None)
            )
            if is_insufficient:
                insufficient_traces.append(t)
        insufficient_rate = round(len(insufficient_traces) / total_queries, 4)

        # Group repeating queries that failed evidence verification
        failed_query_counter = Counter(t.query.strip() for t in insufficient_traces if t.query.strip())
        evidence_gaps: list[CoverageGapItem] = []

        for q_text, count in failed_query_counter.most_common(15):
            matching_traces = [t for t in insufficient_traces if t.query.strip() == q_text]
            avg_score = None
            scores: list[float] = []
            for t in matching_traces:
                sc = _extract_top_score(t.retrieval_scores)
                if sc is not None:
                    scores.append(sc)
            if scores:
                avg_score = round(sum(scores) / len(scores), 3)

            evidence_gaps.append(
                CoverageGapItem(
                    query=q_text,
                    frequency=count,
                    avg_similarity=avg_score,
                    gap_type="insufficient_evidence" if avg_score and avg_score > 0 else "empty_retrieval",
                    affected_topics=[],
                    suggested_action=(
                        f"Add source documentation addressing '{q_text}' or update existing chunks with related terminology."
                    ),
                )
            )

        # 3. Identify unretrieved documents
        doc_stmt = (
            select(Document.id, Document.filename)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.owner_id == user_id,
                Document.status == DocumentStatus.READY,
            )
        )
        doc_res = await self.session.execute(doc_stmt)
        docs = doc_res.all()

        # Check citations and spans in traces to find referenced document IDs
        retrieved_doc_ids: set[str] = set()
        for t in traces:
            if t.trace_metadata and "retrieved_doc_ids" in t.trace_metadata:
                for did in t.trace_metadata["retrieved_doc_ids"]:
                    retrieved_doc_ids.add(str(did))
            for span in t.spans:
                if span.outputs and "document_id" in span.outputs:
                    retrieved_doc_ids.add(str(span.outputs["document_id"]))

        unretrieved_docs = [
            {"document_id": str(d_id), "filename": f_name}
            for d_id, f_name in docs
            if str(d_id) not in retrieved_doc_ids
        ]

        # 4. Generate data-driven recommendations
        recs: list[str] = []
        if insufficient_rate > 0.3:
            recs.append(
                f"High insufficient evidence rate ({insufficient_rate * 100:.1f}%). "
                f"Consider expanding knowledge base coverage for top failing queries."
            )
        if len(unretrieved_docs) > 0 and total_queries >= 10:
            recs.append(
                f"{len(unretrieved_docs)} active documents have never been cited or retrieved across "
                f"{total_queries} queries. Review if content is obsolete or search queries differ."
            )
        if not recs:
            recs.append("Knowledge base demonstrates healthy retrieval coverage across analyzed queries.")

        return CoverageReport(
            knowledge_base_id=knowledge_base_id,
            total_queries_analyzed=total_queries,
            insufficient_evidence_rate=insufficient_rate,
            unretrieved_documents=unretrieved_docs[:20],
            evidence_gaps=evidence_gaps,
            recommendations=recs,
        )
