"""Knowledge Base Duplicate Engine: identifies exact and near-duplicate documents and chunks."""

import re
from uuid import UUID

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import Document, DocumentChunk
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import DuplicateCandidate, DuplicateReport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.services.kb.duplicates")


def _tokenize_words(text: str) -> set[str]:
    """Tokenize text into lowercased word set for Jaccard similarity."""
    if not text:
        return set()
    words = re.findall(r"\b\w{3,}\b", text.lower())
    return set(words)


def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """Computes Jaccard index between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return round(intersection / union, 4) if union > 0 else 0.0


class KnowledgeBaseDuplicateEngine:
    """Detects deterministic exact checksum/content duplicates and near-duplicate documents."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)

    async def detect_duplicates(
        self,
        knowledge_base_id: UUID,
        user_id: UUID,
        similarity_threshold: float = 0.85,
    ) -> DuplicateReport:
        """Audits a knowledge base for exact and near-duplicate documents within the user's boundary."""
        kb = await self.kb_repo.get_by_id_and_owner(knowledge_base_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # Retrieve all documents owned by user in this KB
        query = (
            select(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.owner_id == user_id,
            )
            .order_by(Document.created_at.asc())
        )
        result = await self.session.execute(query)
        documents = list(result.scalars().all())

        candidates: list[DuplicateCandidate] = []
        exact_count = 0
        near_count = 0
        savings_bytes = 0

        # Also pull chunks for text comparison if available
        doc_ids = [d.id for d in documents]
        doc_chunks_map: dict[UUID, str] = {d.id: "" for d in documents}

        if doc_ids:
            chunk_query = (
                select(DocumentChunk.document_id, DocumentChunk.content)
                .where(DocumentChunk.document_id.in_(doc_ids))
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
            )
            chunk_res = await self.session.execute(chunk_query)
            for doc_id, content in chunk_res.all():
                if content:
                    doc_chunks_map[doc_id] += " " + content

        # Precompute word tokens for near-duplicate search
        doc_tokens: dict[UUID, set[str]] = {
            doc.id: _tokenize_words(doc_chunks_map.get(doc.id, "") or doc.filename) for doc in documents
        }

        # Pairwise comparison (bounded to KB documents)
        checked_pairs: set[tuple[UUID, UUID]] = set()

        for i in range(len(documents)):
            doc_a = documents[i]
            for j in range(i + 1, len(documents)):
                doc_b = documents[j]
                pair_key = (min(doc_a.id, doc_b.id), max(doc_a.id, doc_b.id))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                # 1. Exact Checksum Match
                if doc_a.checksum and doc_b.checksum and doc_a.checksum == doc_b.checksum:
                    exact_count += 1
                    storage = doc_b.file_size or 0
                    savings_bytes += storage
                    candidates.append(
                        DuplicateCandidate(
                            match_type="exact_checksum",
                            similarity_score=1.0,
                            primary_document_id=doc_a.id,
                            primary_filename=doc_a.filename,
                            duplicate_document_id=doc_b.id,
                            duplicate_filename=doc_b.filename,
                            shared_checksum=doc_a.checksum,
                            storage_impact_bytes=storage,
                            explanation=(
                                f"Identical cryptographic checksum ({doc_a.checksum[:12]}...). "
                                f"File content is bit-for-bit identical to '{doc_a.filename}'."
                            ),
                        )
                    )
                    continue

                # 2. Exact Extracted Text Match
                text_a = doc_chunks_map.get(doc_a.id, "").strip()
                text_b = doc_chunks_map.get(doc_b.id, "").strip()
                if text_a and text_b and text_a == text_b:
                    exact_count += 1
                    storage = doc_b.file_size or 0
                    savings_bytes += storage
                    candidates.append(
                        DuplicateCandidate(
                            match_type="exact_content",
                            similarity_score=1.0,
                            primary_document_id=doc_a.id,
                            primary_filename=doc_a.filename,
                            duplicate_document_id=doc_b.id,
                            duplicate_filename=doc_b.filename,
                            shared_checksum=doc_b.checksum,
                            storage_impact_bytes=storage,
                            explanation=(
                                f"Extracted text content matches exactly with '{doc_a.filename}' "
                                f"({len(text_a)} characters across all chunks)."
                            ),
                        )
                    )
                    continue

                # 3. Near-Duplicate Analysis via Lexical Jaccard Similarity
                tokens_a = doc_tokens.get(doc_a.id, set())
                tokens_b = doc_tokens.get(doc_b.id, set())
                if len(tokens_a) >= 10 and len(tokens_b) >= 10:
                    sim = _jaccard_similarity(tokens_a, tokens_b)
                    if sim >= similarity_threshold:
                        near_count += 1
                        candidates.append(
                            DuplicateCandidate(
                                match_type="near_duplicate_text",
                                similarity_score=sim,
                                primary_document_id=doc_a.id,
                                primary_filename=doc_a.filename,
                                duplicate_document_id=doc_b.id,
                                duplicate_filename=doc_b.filename,
                                shared_checksum=None,
                                storage_impact_bytes=doc_b.file_size or 0,
                                explanation=(
                                    f"Lexical Jaccard similarity is {sim:.2f} (threshold {similarity_threshold}). "
                                    f"Documents share high vocabulary overlap across chunks."
                                ),
                            )
                        )

        return DuplicateReport(
            knowledge_base_id=knowledge_base_id,
            exact_duplicates_count=exact_count,
            near_duplicates_count=near_count,
            potential_storage_savings_bytes=savings_bytes,
            candidates=candidates,
        )
