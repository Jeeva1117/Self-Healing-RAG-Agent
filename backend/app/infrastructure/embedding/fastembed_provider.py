"""FastEmbed local CPU/ONNX embedding provider."""

import asyncio

from fastembed import TextEmbedding

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface

logger = get_logger(__name__)


class FastEmbedProvider(EmbeddingProviderInterface):
    """Generates dense vector embeddings locally using ONNX Runtime via fastembed.

    Default model: BAAI/bge-small-en-v1.5 (384-dimensional).
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int | None = None,
        dimension: int | None = None,
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        logger.info(
            "Initializing FastEmbed model: %s (batch_size=%d, dimension=%d)",
            self._model_name,
            self._batch_size,
            self._dimension,
        )
        self._model = TextEmbedding(model_name=self._model_name)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "fastembed"

    def _sync_embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        generator = self._model.embed(texts, batch_size=self._batch_size)
        return [vec.tolist() for vec in generator]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a batch of texts offloading to worker thread."""
        if not texts:
            return []
        return await asyncio.to_thread(self._sync_embed, texts)

    async def embed_query(self, text: str) -> list[float]:
        """Generates embedding for a single query text."""
        results = await self.embed_documents([text])
        if not results:
            return [0.0] * self._dimension
        return results[0]
