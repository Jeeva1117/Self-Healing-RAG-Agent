"""Deterministic mock reranker for unit tests."""

from typing import Any

from app.domain.interfaces.reranker import RankedDocument, RerankerInterface


class MockReranker(RerankerInterface):
    """Deterministic mock cross-encoder reranker for hermetic unit testing."""

    def __init__(self, model_name: str = "mock-cross-encoder-v1"):
        self.model_name = model_name

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[RankedDocument]:
        if not documents:
            return []

        # Simple deterministic scoring based on term overlap or inverse original rank
        query_words = set(query.lower().split())
        scored: list[tuple[float, dict[str, Any], int]] = []

        for idx, doc in enumerate(documents):
            content = str(doc.get("content") or doc.get("text") or "").lower()
            overlap = sum(1 for w in query_words if w in content)
            base_score = 0.5 + (0.1 * min(overlap, 4)) - (0.01 * idx)
            score = max(0.01, min(0.99, base_score))
            orig_rank = int(doc.get("original_rank", idx + 1))
            scored.append((score, doc, orig_rank))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[RankedDocument] = []
        for s, d, r in scored[:top_k]:
            results.append(
                RankedDocument(
                    document_id=str(d.get("id") or d.get("document_id") or ""),
                    content=str(d.get("content") or d.get("text") or ""),
                    relevance_score=round(s, 4),
                    original_rank=r,
                    metadata=d.get("metadata", {}),
                )
            )

        return results
