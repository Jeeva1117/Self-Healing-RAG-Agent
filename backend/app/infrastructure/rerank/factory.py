"""Factory for cross-encoder reranker providers."""

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interfaces.reranker import RerankerInterface
from app.infrastructure.rerank.flashrank_reranker import FlashRankReranker
from app.infrastructure.rerank.mock_reranker import MockReranker

logger = get_logger(__name__)


def get_reranker(provider_name: str | None = None) -> RerankerInterface:
    """Instantiates configured cross-encoder reranker provider."""
    provider = (provider_name or settings.RERANKER_PROVIDER).lower()

    if provider == "mock" or settings.APP_ENV == "test":
        return MockReranker()

    if provider == "flashrank":
        try:
            return FlashRankReranker()
        except Exception as e:
            logger.warning("FlashRank initialization failed, falling back to MockReranker: %s", e)
            return MockReranker()

    logger.warning("Unknown reranker provider '%s', defaulting to FlashRankReranker", provider)
    return FlashRankReranker()
