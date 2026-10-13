"""Factory for embedding providers."""

from functools import lru_cache

from app.core.config import settings
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.infrastructure.embedding.fastembed_provider import FastEmbedProvider
from app.infrastructure.embedding.mock_provider import MockEmbeddingProvider


@lru_cache(maxsize=1)
def get_embedding_provider(provider_type: str | None = None) -> EmbeddingProviderInterface:
    """Returns the configured embedding provider singleton."""
    provider = (provider_type or settings.EMBEDDING_PROVIDER).lower()

    if provider == "mock":
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    elif provider == "fastembed" or True:  # Default to local FastEmbed
        model_name = settings.EMBEDDING_MODEL
        if not model_name or "text-embedding" in model_name.lower():
            model_name = "BAAI/bge-small-en-v1.5"
        return FastEmbedProvider(
            model_name=model_name,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            dimension=settings.EMBEDDING_DIMENSION,
        )
