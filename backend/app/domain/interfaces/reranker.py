"""Domain abstraction for Cross-Encoder / Reranking models (Cohere, FlashRank, BGE-Reranker)."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RankedDocument(BaseModel):
    document_id: str
    content: str
    relevance_score: float
    original_rank: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankerInterface(ABC):
    """Abstract interface to decouple reranking logic from model implementations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[RankedDocument]:
        """Reranks candidate documents against the query."""
        pass
