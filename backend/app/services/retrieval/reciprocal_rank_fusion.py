"""Reciprocal Rank Fusion (RRF) for combining vector and lexical rankings."""

from uuid import UUID

from app.schemas.retrieval import RetrievalResultItem


class ReciprocalRankFusion:
    """Fuses multi-retriever candidate rankings using standard Reciprocal Rank Fusion.

    Formula:
        RRF_score(d) = sum over retrievers of 1 / (k + rank(d))

    Where k is a smoothing constant (standard default: 60) and rank(d) is 1-indexed.
    """

    @staticmethod
    def fuse(
        vector_results: list[RetrievalResultItem],
        lexical_results: list[RetrievalResultItem],
        rrf_k: int = 60,
        candidate_limit: int = 20,
    ) -> list[RetrievalResultItem]:
        """Fuses independent vector and lexical results by chunk ID with transparent score tracking."""
        merged_map: dict[UUID, RetrievalResultItem] = {}
        rrf_scores: dict[UUID, float] = {}
        in_vector: set[UUID] = set()
        in_lexical: set[UUID] = set()

        # 1. Process vector results
        for rank_idx, item in enumerate(vector_results, start=1):
            chunk_id = item.chunk_id
            in_vector.add(chunk_id)
            score_contrib = 1.0 / (rrf_k + rank_idx)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score_contrib

            clone = item.model_copy()
            clone.vector_rank = rank_idx
            clone.semantic_rank = rank_idx
            clone.semantic_score = item.semantic_score or item.vector_score
            merged_map[chunk_id] = clone

        # 2. Process lexical results
        for rank_idx, item in enumerate(lexical_results, start=1):
            chunk_id = item.chunk_id
            in_lexical.add(chunk_id)
            score_contrib = 1.0 / (rrf_k + rank_idx)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score_contrib

            if chunk_id in merged_map:
                # Merge lexical fields into existing item
                target = merged_map[chunk_id]
                target.lexical_rank = rank_idx
                target.lexical_score = item.lexical_score
                target.keyword_rank = rank_idx
                target.bm25_score = item.bm25_score or item.lexical_score
            else:
                clone = item.model_copy()
                clone.lexical_rank = rank_idx
                clone.keyword_rank = rank_idx
                clone.bm25_score = item.bm25_score or item.lexical_score
                merged_map[chunk_id] = clone

        if not merged_map:
            return []

        # 3. Determine stage provenance and assign rrf_score
        fused_items: list[RetrievalResultItem] = []
        for chunk_id, item in merged_map.items():
            item.rrf_score = round(rrf_scores[chunk_id], 6)

            if chunk_id in in_vector and chunk_id in in_lexical:
                item.stage_provenance = "hybrid"
            elif chunk_id in in_vector:
                item.stage_provenance = "vector"
            else:
                item.stage_provenance = "lexical"

            fused_items.append(item)

        # 4. Deterministic tie-breaking sort:
        # Sort by rrf_score (desc), then vector_score (desc), then lexical_score (desc), then chunk_id (asc)
        fused_items.sort(
            key=lambda x: (
                round(x.rrf_score or 0.0, 8),
                x.vector_score or 0.0,
                x.lexical_score or 0.0,
                str(x.chunk_id),
            ),
            reverse=True,
        )

        # 5. Assign rrf_rank and final_rank
        final_candidates: list[RetrievalResultItem] = []
        for rank_idx, item in enumerate(fused_items[:candidate_limit], start=1):
            item.rrf_rank = rank_idx
            item.final_rank = rank_idx
            final_candidates.append(item)

        return final_candidates
