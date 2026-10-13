"""Domain abstraction for text embedding models."""

from abc import ABC, abstractmethod


class EmbeddingProviderInterface(ABC):
    """Abstract interface to allow swappable embedding backends (OpenAI, HuggingFace, Cohere, etc.)."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of documents."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generates an embedding for a single user query."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the vector dimensionality for this embedding model."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the specific model identifier (e.g. BAAI/bge-small-en-v1.5)."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider name (e.g. fastembed, openai)."""
        pass
