"""Domain abstraction for Vector Database stores (pgvector, Qdrant, Milvus, Chroma)."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    id: str
    vector: list[float]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None


class VectorStoreInterface(ABC):
    """Abstract interface to decouple vector search from concrete databases."""

    @abstractmethod
    async def insert_vectors(self, collection_name: str, records: list[VectorRecord]) -> bool:
        """Inserts or updates vector records in the given collection."""
        pass

    @abstractmethod
    async def similarity_search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorRecord]:
        """Performs cosine / L2 / inner product similarity search."""
        pass

    @abstractmethod
    async def delete_vectors(self, collection_name: str, ids: list[str]) -> bool:
        """Removes vectors by identifier."""
        pass
