"""FlashRank local CPU/ONNX cross-encoder reranker implementation."""

import asyncio
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interfaces.reranker import RankedDocument, RerankerInterface
from flashrank import Ranker, RerankRequest

logger = get_logger(__name__)

# Global cached singleton instance so model is loaded once into memory
_GLOBAL_RANKER: Ranker | None = None


def _get_global_ranker(model_name: str) -> Ranker:
    global _GLOBAL_RANKER
    if _GLOBAL_RANKER is None:
        logger.info("Initializing FlashRank cross-encoder model: %s", model_name)
        _GLOBAL_RANKER = Ranker(model_name=model_name)
    return _GLOBAL_RANKER


class FlashRankReranker(RerankerInterface):
    """Production-grade cross-encoder reranker running locally via ONNX Runtime on CPU.

    Default model: ms-marco-TinyBERT-L-2-v2 (~3.26MB, ultra-fast CPU inference).
    """

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or settings.RERANKER_MODEL
        self._ranker = _get_global_ranker(self._model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def _sync_rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[RankedDocument]:
        if not documents or not query.strip():
            return []

        # Prepare passages for FlashRank with safe length truncation
        passages: list[dict[str, Any]] = []
        for idx, doc in enumerate(documents):
            text = str(doc.get("content") or doc.get("text") or "")
            # Truncate passage text to max 2000 chars for safe fast inference
            truncated_text = text[:2000] if len(text) > 2000 else text
            passages.append(
                {
                    "id": str(doc.get("id") or doc.get("document_id") or idx),
                    "text": truncated_text,
                    "meta": doc.get("metadata", {}),
                    "original_rank": doc.get("original_rank", idx + 1),
                }
            )

        rerank_req = RerankRequest(query=query[:500], passages=passages)
        raw_results = self._ranker.rerank(rerank_req)

        ranked_docs: list[RankedDocument] = []
        for item in raw_results[:top_k]:
            score = float(item.get("score", 0.0))
            ranked_docs.append(
                RankedDocument(
                    document_id=str(item.get("id")),
                    content=str(item.get("text")),
                    relevance_score=round(score, 6),
                    original_rank=int(item.get("original_rank", 1)),
                    metadata=item.get("meta", {}),
                )
            )

        return ranked_docs

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[RankedDocument]:
        """Executes cross-encoder scoring asynchronously offloading to thread pool."""
        if not documents or not query.strip():
            return []
        return await asyncio.to_thread(self._sync_rerank, query, documents, top_k)
