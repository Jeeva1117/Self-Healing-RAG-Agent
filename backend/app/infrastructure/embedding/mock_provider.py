"""Mock / Deterministic embedding provider for hermetic testing."""

import hashlib
import math

from app.core.config import settings
from app.domain.interfaces.embeddings import EmbeddingProviderInterface


class MockEmbeddingProvider(EmbeddingProviderInterface):
    """Deterministic embedding provider that creates normalized hash-based vectors."""

    def __init__(
        self,
        dimension: int | None = None,
        model_name: str = "mock-deterministic-v1",
    ):
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    def _generate_vector(self, text: str) -> list[float]:
        # Deterministically compute vector from SHA256 of text
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self._dimension):
            byte_val = digest[i % len(digest)]
            val = (byte_val / 255.0) * 2.0 - 1.0  # Range [-1.0, 1.0]
            vec.append(val)

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._generate_vector(text)
