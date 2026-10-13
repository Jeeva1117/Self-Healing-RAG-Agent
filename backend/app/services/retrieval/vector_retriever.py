"""Semantic vector similarity retrieval over stored document chunk embeddings."""

import math
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.infrastructure.database.models import Document, DocumentChunk, DocumentStatus, DocumentVersion
from app.schemas.retrieval import RetrievalResultItem

logger = get_logger(__name__)


class VectorRetriever:
    """Retrieves document chunks using semantic dense vector similarity search."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProviderInterface,
    ):
        self.session = session
        self.embeddings = embedding_provider

    async def retrieve(
        self,
        kb_id: UUID,
        user_id: UUID,
        query: str,
        candidate_limit: int = 20,
        similarity_threshold: float = 0.0,
    ) -> list[RetrievalResultItem]:
        """Executes vector retrieval scoped to the user's Knowledge Base.

        1. Generates dense query vector using active embedding provider.
        2. Queries database for eligible ready chunks belonging to user & KB.
        3. Computes high-precision cosine similarity across candidate vectors.
        4. Filters by similarity threshold and ranks candidates deterministically.
        """
        if not query.strip():
            return []

        # 1. Generate query embedding
        query_vector = await self.embeddings.embed_query(query)
        if not query_vector:
            raise AppError(
                code="EMBEDDING_GENERATION_FAILED",
                message="Embedding provider failed to generate a vector for query.",
                status_code=502,
            )

        if len(query_vector) != self.embeddings.dimension:
            raise AppError(
                code="VECTOR_DIMENSION_MISMATCH",
                message=(
                    f"Query embedding dimension ({len(query_vector)}) does not match "
                    f"configured dimension ({self.embeddings.dimension})."
                ),
                status_code=500,
            )

        # Validate query vector values are numeric and finite
        if any(not math.isfinite(x) for x in query_vector):
            raise AppError(
                code="INVALID_QUERY_EMBEDDING",
                message="Query embedding contains non-finite or NaN values.",
                status_code=502,
            )

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))
        if q_norm == 0.0 or not math.isfinite(q_norm):
            logger.warning("VectorRetriever: Query vector has zero or non-finite norm.")
            return []

        # 2. Query eligible chunks with tenant isolation & active document version filtering
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
                DocumentChunk.embedding,
                DocumentChunk.embedding_dimension,
                Document.original_filename,
                DocumentChunk.document_version_id,
                DocumentChunk.embedding_model,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .outerjoin(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .where(
                Document.knowledge_base_id == kb_id,
                Document.owner_id == user_id,
                Document.status == DocumentStatus.READY,
                or_(DocumentVersion.id.is_(None), DocumentVersion.is_active.is_(True)),
                DocumentChunk.embedding.isnot(None),
            )
        )

        result = await self.session.execute(stmt)
        rows = result.fetchall()

        if not rows:
            logger.info("VectorRetriever: No eligible chunks found for kb_id=%s", kb_id)
            return []

        # 3. Compute cosine similarity with vector validation
        scored_candidates: list[tuple[float, Any]] = []
        for row in rows:
            raw_emb = row[9]
            if raw_emb is None:
                continue

            try:
                emb_list = [float(x) for x in raw_emb] if isinstance(raw_emb, list) else [float(x) for x in raw_emb]
            except Exception:
                continue

            # Validate dimensions and values
            if len(emb_list) != len(query_vector):
                continue

            if any(not math.isfinite(x) for x in emb_list):
                continue

            doc_vec = np.array(emb_list, dtype=np.float32)
            doc_norm = float(np.linalg.norm(doc_vec))
            if doc_norm == 0.0 or not math.isfinite(doc_norm):
                continue

            # Cosine similarity in range [-1.0, 1.0]
            cos_sim = float(np.dot(q_vec, doc_vec) / (q_norm * doc_norm))
            if not math.isfinite(cos_sim):
                continue

            # Normalize to [0.0, 1.0] for standard display
            normalized_score = max(0.0, min(1.0, (cos_sim + 1.0) / 2.0))

            if normalized_score >= similarity_threshold:
                scored_candidates.append((normalized_score, row))

        # 4. Deterministic tie-breaking sort: descending by score, ascending by chunk UUID string
        scored_candidates.sort(key=lambda x: (-round(x[0], 6), str(x[1][0])))

        # 5. Format top candidates as RetrievalResultItem
        retrieved_items: list[RetrievalResultItem] = []
        for rank_idx, (score, row) in enumerate(scored_candidates[:candidate_limit], start=1):
            item = RetrievalResultItem(
                chunk_id=row[0],
                document_id=row[1],
                document_version_id=row[12],
                document_name=row[11] or "Unknown Document",
                content=row[3],
                page_number=row[6],
                section_title=row[7],
                chunk_index=row[2],
                token_count=row[4],
                character_count=row[5],
                metadata=row[8] or {},
                vector_rank=rank_idx,
                vector_score=round(score, 6),
                semantic_rank=rank_idx,
                semantic_score=round(score, 6),
                lexical_rank=None,
                lexical_score=None,
                keyword_rank=None,
                bm25_score=None,
                rrf_rank=None,
                rrf_score=None,
                reranker_rank=None,
                reranker_score=None,
                rerank_score=None,
                final_rank=rank_idx,
                stage_provenance="vector",
            )
            retrieved_items.append(item)

        return retrieved_items

