"""Embedding providers infrastructure package."""

from app.infrastructure.embedding.factory import get_embedding_provider
from app.infrastructure.embedding.fastembed_provider import FastEmbedProvider
from app.infrastructure.embedding.mock_provider import MockEmbeddingProvider

__all__ = [
    "get_embedding_provider",
    "FastEmbedProvider",
    "MockEmbeddingProvider",
]
