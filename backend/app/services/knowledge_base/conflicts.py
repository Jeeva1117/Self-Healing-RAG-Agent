"""Knowledge Base Conflict Engine: conservative detection of factual and policy contradictions between documents."""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import Document, DocumentChunk, DocumentStatus
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import ConflictItem, ConflictReport

logger = get_logger("app.services.kb.conflicts")

# Conservative antonym / contradictory phrase pairs
CONTRADICTION_PATTERNS = [
    (r"\b(must|required|mandatory|obligatory)\b", r"\b(must not|prohibited|forbidden|optional|never)\b"),
    (r"\b(enabled|allowed|permitted|supported)\b", r"\b(disabled|disallowed|prohibited|unsupported)\b"),
    (r"\b(maximum|max)\s*:\s*(\d+)", r"\b(maximum|max)\s*:\s*(\d+)"),
    (r"\b(minimum|min)\s*:\s*(\d+)", r"\b(minimum|min)\s*:\s*(\d+)"),
]


class KnowledgeBaseConflictEngine:
    """Conservative knowledge conflict detector preserving full source provenance."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)

    async def detect_conflicts(
        self,
        knowledge_base_id: UUID,
        user_id: UUID,
    ) -> ConflictReport:
        """Audits documents within a knowledge base for conservative factual or policy contradictions."""
        kb = await self.kb_repo.get_by_id_and_owner(knowledge_base_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # 1. Fetch user's active documents in this KB
        query = (
            select(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.owner_id == user_id,
                Document.status == DocumentStatus.READY,
            )
            .order_by(Document.created_at.asc())
        )
        result = await self.session.execute(query)
        documents = list(result.scalars().all())

        if len(documents) < 2:
            return ConflictReport(
                knowledge_base_id=knowledge_base_id,
                total_conflicts_detected=0,
                items=[],
            )

        # Fetch chunks for each document
        doc_ids = [d.id for d in documents]
        chunk_query = (
            select(DocumentChunk.document_id, DocumentChunk.document_version_id, DocumentChunk.content)
            .where(DocumentChunk.document_id.in_(doc_ids))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        chunk_res = await self.session.execute(chunk_query)
        doc_chunks: dict[UUID, list[tuple[UUID | None, str]]] = {d.id: [] for d in documents}
        for d_id, v_id, content in chunk_res.all():
            if content:
                doc_chunks[d_id].append((v_id, content))

        conflicts: list[ConflictItem] = []

        # Pairwise conservative conflict analysis
        for i in range(len(documents)):
            doc_a = documents[i]
            chunks_a = doc_chunks.get(doc_a.id, [])

            for j in range(i + 1, len(documents)):
                doc_b = documents[j]
                chunks_b = doc_chunks.get(doc_b.id, [])

                # Compare chunks between doc_a and doc_b
                for _v_a, text_a in chunks_a:
                    for _v_b, text_b in chunks_b:
                        # Find overlapping keywords / topics
                        words_a = set(re.findall(r"\b\w{4,}\b", text_a.lower()))
                        words_b = set(re.findall(r"\b\w{4,}\b", text_b.lower()))
                        shared_vocab = words_a.intersection(words_b)

                        # Must share substantive topic context
                        if len(shared_vocab) < 5:
                            continue

                        # Check contradictory statements
                        for pat_pos, pat_neg in CONTRADICTION_PATTERNS:
                            m_pos_a = re.search(pat_pos, text_a, re.IGNORECASE)
                            m_neg_b = re.search(pat_neg, text_b, re.IGNORECASE)
                            m_pos_b = re.search(pat_pos, text_b, re.IGNORECASE)
                            m_neg_a = re.search(pat_neg, text_a, re.IGNORECASE)

                            is_conflict = False
                            summary = ""
                            if m_pos_a and m_neg_b:
                                is_conflict = True
                                summary = (
                                    f"Contradictory directives: '{doc_a.filename}' specifies '{m_pos_a.group(0)}' "
                                    f"while '{doc_b.filename}' specifies '{m_neg_b.group(0)}' on shared topic."
                                )
                            elif m_pos_b and m_neg_a:
                                is_conflict = True
                                summary = (
                                    f"Contradictory directives: '{doc_b.filename}' specifies '{m_pos_b.group(0)}' "
                                    f"while '{doc_a.filename}' specifies '{m_neg_a.group(0)}' on shared topic."
                                )

                            if is_conflict:
                                topic_sample = ", ".join(sorted(shared_vocab)[:4])
                                conflicts.append(
                                    ConflictItem(
                                        topic=f"Policy/Rule regarding {topic_sample}",
                                        document_a_id=doc_a.id,
                                        document_a_name=doc_a.filename,
                                        document_a_version=1,
                                        document_a_excerpt=text_a[:280] + ("..." if len(text_a) > 280 else ""),
                                        document_b_id=doc_b.id,
                                        document_b_name=doc_b.filename,
                                        document_b_version=1,
                                        document_b_excerpt=text_b[:280] + ("..." if len(text_b) > 280 else ""),
                                        conflict_summary=summary,
                                        remediation_guidance=(
                                            "Review authoritative source dates, reconcile conflicting directives, "
                                            "and archive or update the obsolete document version."
                                        ),
                                    )
                                )
                                break
                        if len(conflicts) >= 10:
                            break
                    if len(conflicts) >= 10:
                        break

        return ConflictReport(
            knowledge_base_id=knowledge_base_id,
            total_conflicts_detected=len(conflicts),
            items=conflicts,
        )
