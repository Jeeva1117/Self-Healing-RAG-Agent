"""Genuine BM25 Okapi lexical keyword retrieval over document chunks."""

import re
from typing import Any
from uuid import UUID

from rank_bm25 import BM25Plus
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.models import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.schemas.retrieval import RetrievalResultItem

logger = get_logger(__name__)

# Regular expression tokenizer for English and alphanumeric identifiers
_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z0-9_\-\.]+\b")


def tokenize_text(text: str) -> list[str]:
    """Tokenizes text preserving technical terms, identifiers, and numbers."""
    if not text:
        return []
    tokens = _TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if len(t) > 1]


class BM25Retriever:
    """Performs genuine BM25 keyword and lexical search over scoped document chunks."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def retrieve(
        self,
        kb_id: UUID,
        user_id: UUID,
        query: str,
        candidate_limit: int = 20,
    ) -> list[RetrievalResultItem]:
        """Executes BM25 retrieval strictly scoped to the user's Knowledge Base."""
        query_tokens = tokenize_text(query)
        if not query_tokens:
            return []

        # 1. Fetch all eligible chunks belonging to this Knowledge Base and user with active version filtering
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
                DocumentChunk.token_count,
                DocumentChunk.character_count,
                DocumentChunk.page_number,
                DocumentChunk.section_title,
                DocumentChunk.chunk_metadata,
                Document.original_filename,
                DocumentChunk.document_version_id,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .outerjoin(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .where(
                Document.knowledge_base_id == kb_id,
                Document.owner_id == user_id,
                Document.status == DocumentStatus.READY,
                or_(DocumentVersion.id.is_(None), DocumentVersion.is_active.is_(True)),
            )
        )

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        if not rows:
            logger.info("BM25Retriever: No eligible chunks found for kb_id=%s", kb_id)
            return []

        # 2. Tokenize chunk corpus
        corpus_tokens: list[list[str]] = []
        valid_rows: list[Any] = []
        for row in rows:
            tokens = tokenize_text(row[3])
            # Include even sparse chunks so BM25 average document length (avgdl) is accurate
            corpus_tokens.append(tokens)
            valid_rows.append(row)

        if not corpus_tokens:
            return []

        # 3. Fit BM25Plus model (guarantees positive scores with lower-bound delta smoothing)
        bm25 = BM25Plus(corpus_tokens)
        doc_scores = bm25.get_scores(query_tokens)

        # 4. Filter matches containing at least one query token with positive score
        query_set = set(query_tokens)
        scored_candidates: list[tuple[float, Any]] = []
        for idx, score in enumerate(doc_scores):
            doc_token_set = set(corpus_tokens[idx])
            if any(q in doc_token_set for q in query_set) and score > 0.0:
                scored_candidates.append((float(score), valid_rows[idx]))

        if not scored_candidates:
            return []

        # 5. Deterministic tie-breaking sort: descending by score, ascending by chunk UUID string
        scored_candidates.sort(key=lambda x: (-round(x[0], 6), str(x[1][0])))

        # 6. Build RetrievalResultItem objects
        retrieved_items: list[RetrievalResultItem] = []
        for rank_idx, (score, row) in enumerate(scored_candidates[:candidate_limit], start=1):
            item = RetrievalResultItem(
                chunk_id=row[0],
                document_id=row[1],
                document_version_id=row[10],
                document_name=row[9] or "Unknown Document",
                content=row[3],
                page_number=row[6],
                section_title=row[7],
                chunk_index=row[2],
                token_count=row[4],
                character_count=row[5],
                metadata=row[8] or {},
                vector_rank=None,
                vector_score=None,
                semantic_rank=None,
                semantic_score=None,
                lexical_rank=rank_idx,
                lexical_score=round(score, 4),
                keyword_rank=rank_idx,
                bm25_score=round(score, 4),
                rrf_rank=None,
                rrf_score=None,
                reranker_rank=None,
                reranker_score=None,
                rerank_score=None,
                final_rank=rank_idx,
                stage_provenance="lexical",
            )
            retrieved_items.append(item)

        return retrieved_items
