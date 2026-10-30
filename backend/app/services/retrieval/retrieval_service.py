"""High-level Retrieval Service orchestrating Vector, BM25, RRF Fusion, and Neural Reranking."""

import time
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.domain.interfaces.reranker import RerankerInterface
from app.infrastructure.embedding.factory import get_embedding_provider
from app.infrastructure.rerank.factory import get_reranker
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.retrieval import (
    ComparisonResponse,
    RetrievalLatencyBreakdown,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResultItem,
)
from app.services.retrieval.bm25_retriever import BM25Retriever
from app.services.retrieval.reciprocal_rank_fusion import ReciprocalRankFusion
from app.services.retrieval.vector_retriever import VectorRetriever
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class RetrievalService:
    """Production-grade hybrid retrieval orchestrator with tenant isolation and latency tracing."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProviderInterface | None = None,
        reranker: RerankerInterface | None = None,
    ):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.embeddings = embedding_provider or get_embedding_provider()
        self.reranker = reranker or get_reranker()
        self.vector_retriever = VectorRetriever(session, self.embeddings)
        self.bm25_retriever = BM25Retriever(session)

    async def _verify_kb_ownership(self, kb_id: UUID, user_id: UUID) -> None:
        """Enforces server-side authorization: user must own the requested Knowledge Base."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

    async def search(
        self,
        request: RetrievalRequest,
        user_id: UUID,
    ) -> RetrievalResponse:
        """Executes full retrieval pipeline based on requested mode and reranking settings."""
        t_total_start = time.perf_counter()

        # 1. Enforce strict Knowledge Base ownership check
        await self._verify_kb_ownership(request.knowledge_base_id, user_id)

        vector_ms = 0.0
        lexical_ms = 0.0
        fusion_ms = 0.0
        rerank_ms = 0.0

        candidates: list[RetrievalResultItem] = []

        # 2. Execute retrieval stages based on requested mode
        if request.mode == RetrievalMode.HYBRID:
            # 1. Vector retrieval
            t_vec_start = time.perf_counter()
            vec_res = await self.vector_retriever.retrieve(
                kb_id=request.knowledge_base_id,
                user_id=user_id,
                query=request.query,
                candidate_limit=request.candidate_limit,
                similarity_threshold=request.similarity_threshold,
            )
            vector_ms = (time.perf_counter() - t_vec_start) * 1000.0

            # 2. Lexical retrieval (BM25)
            t_lex_start = time.perf_counter()
            lex_res = await self.bm25_retriever.retrieve(
                kb_id=request.knowledge_base_id,
                user_id=user_id,
                query=request.query,
                candidate_limit=request.candidate_limit,
            )
            lexical_ms = (time.perf_counter() - t_lex_start) * 1000.0

            # Fuse with Reciprocal Rank Fusion
            t_fuse_start = time.perf_counter()
            candidates = ReciprocalRankFusion.fuse(
                vector_results=vec_res,
                lexical_results=lex_res,
                rrf_k=request.rrf_k,
                candidate_limit=request.candidate_limit,
            )
            fusion_ms = (time.perf_counter() - t_fuse_start) * 1000.0

        elif request.mode == RetrievalMode.VECTOR:
            t_vec_start = time.perf_counter()
            candidates = await self.vector_retriever.retrieve(
                kb_id=request.knowledge_base_id,
                user_id=user_id,
                query=request.query,
                candidate_limit=request.candidate_limit,
                similarity_threshold=request.similarity_threshold,
            )
            vector_ms = (time.perf_counter() - t_vec_start) * 1000.0

        elif request.mode == RetrievalMode.LEXICAL:
            t_lex_start = time.perf_counter()
            candidates = await self.bm25_retriever.retrieve(
                kb_id=request.knowledge_base_id,
                user_id=user_id,
                query=request.query,
                candidate_limit=request.candidate_limit,
            )
            lexical_ms = (time.perf_counter() - t_lex_start) * 1000.0

        candidate_count = len(candidates)
        reranking_applied = False
        warnings: list[str] = []

        # 3. Neural Cross-Encoder Reranking (if enabled and candidates available)
        if request.enable_reranking and candidates:
            t_rerank_start = time.perf_counter()
            rerank_pool = candidates[: min(len(candidates), settings.RERANKER_MAX_CANDIDATES)]

            docs_for_rerank = []
            for c in rerank_pool:
                doc_title = c.document_name or (c.metadata.get("source_filename") if c.metadata else "") or ""
                clean_title = doc_title.rsplit(".", 1)[0].replace("_", " ") if "." in doc_title else doc_title
                section = c.section_title or ""

                header = f"Document: {clean_title}"
                if section and not section.startswith("Page "):
                    header += f" | Section: {section}"

                passage_text = f"{header}\n{c.content}"

                docs_for_rerank.append(
                    {
                        "id": str(c.chunk_id),
                        "content": passage_text,
                        "metadata": c.metadata,
                        "original_rank": c.final_rank,
                    }
                )

            try:
                ranked_docs = await self.reranker.rerank(
                    query=request.query,
                    documents=docs_for_rerank,
                    top_k=request.top_k,
                )

                # Re-map cross-encoder scores and reorder candidates
                score_map = {
                    r.document_id: (r.relevance_score, rank_i) for rank_i, r in enumerate(ranked_docs, start=1)
                }
                reranked_items: list[RetrievalResultItem] = []

                for c in candidates:
                    cid_str = str(c.chunk_id)
                    if cid_str in score_map:
                        score, r_rank = score_map[cid_str]
                        c.reranker_score = score
                        c.reranker_rank = r_rank
                        c.rerank_score = score
                        reranked_items.append(c)

                # Sort by neural reranker score descending
                reranked_items.sort(key=lambda x: x.reranker_score or 0.0, reverse=True)

                for rank_idx, item in enumerate(reranked_items, start=1):
                    item.final_rank = rank_idx

                candidates = reranked_items
                reranking_applied = True
            except Exception as e:
                logger.warning("Cross-encoder reranking failed: %s", e)
                if request.reranking_required:
                    raise AppError(
                        code="RERANKING_FAILED",
                        message=f"Neural reranking failed: {e}",
                        status_code=502,
                    ) from e
                reranking_applied = False
                warnings.append("Neural reranking failed; safely fell back to pre-reranked order.")

            rerank_ms = (time.perf_counter() - t_rerank_start) * 1000.0
        elif not request.enable_reranking:
            reranking_applied = False

        # 4. Final top_k cutoff
        final_results = candidates[: request.top_k]
        for rank_idx, item in enumerate(final_results, start=1):
            item.final_rank = rank_idx
            item.sync_score_aliases()

        total_ms = (time.perf_counter() - t_total_start) * 1000.0

        latency = RetrievalLatencyBreakdown(
            vector_ms=round(vector_ms, 2),
            lexical_ms=round(lexical_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            rerank_ms=round(rerank_ms, 2),
            total_ms=round(total_ms, 2),
        )

        logger.info(
            "RETRIEVAL_COMPLETED: kb=%s mode=%s rerank_app=%s candidates=%d returned=%d total_ms=%.2f",
            request.knowledge_base_id,
            request.mode.value,
            reranking_applied,
            candidate_count,
            len(final_results),
            total_ms,
        )

        return RetrievalResponse(
            query=request.query,
            knowledge_base_id=request.knowledge_base_id,
            mode=request.mode.value,
            retrieval_mode=request.mode.value,
            enable_reranking=request.enable_reranking,
            reranking_enabled=request.enable_reranking,
            reranking_applied=reranking_applied,
            candidate_count=candidate_count,
            returned_count=len(final_results),
            total_results=len(final_results),
            results=final_results,
            latency=latency,
            latency_ms=round(total_ms, 2),
            warnings=warnings,
        )

    async def compare(
        self,
        request: RetrievalRequest,
        user_id: UUID,
    ) -> ComparisonResponse:
        """Executes Vector, Lexical, and Hybrid retrieval for side-by-side comparison in Playground."""
        t_start = time.perf_counter()
        await self._verify_kb_ownership(request.knowledge_base_id, user_id)

        req_vec = request.model_copy(update={"mode": RetrievalMode.VECTOR, "enable_reranking": False})
        req_lex = request.model_copy(update={"mode": RetrievalMode.LEXICAL, "enable_reranking": False})
        req_hyb = request.model_copy(
            update={"mode": RetrievalMode.HYBRID, "enable_reranking": request.enable_reranking}
        )

        vec_res = await self.search(req_vec, user_id)
        lex_res = await self.search(req_lex, user_id)
        hyb_res = await self.search(req_hyb, user_id)

        total_ms = (time.perf_counter() - t_start) * 1000.0

        all_warnings = list(set(vec_res.warnings + lex_res.warnings + hyb_res.warnings))

        return ComparisonResponse(
            query=request.query,
            knowledge_base_id=request.knowledge_base_id,
            vector_results=vec_res.results,
            lexical_results=lex_res.results,
            hybrid_results=hyb_res.results,
            latency=RetrievalLatencyBreakdown(
                vector_ms=vec_res.latency.vector_ms,
                lexical_ms=lex_res.latency.lexical_ms,
                fusion_ms=hyb_res.latency.fusion_ms,
                rerank_ms=hyb_res.latency.rerank_ms,
                total_ms=round(total_ms, 2),
            ),
            warnings=all_warnings,
        )
