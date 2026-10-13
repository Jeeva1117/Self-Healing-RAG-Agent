import os
from functools import lru_cache

from app.core.config import settings
from app.domain.interfaces.llm import LLMProviderInterface
from app.infrastructure.llm.groq_provider import GroqProvider
from app.infrastructure.llm.grounded_synthesis_provider import GroundedSynthesisProvider
from app.infrastructure.llm.openai_provider import OpenAICompatibleProvider


@lru_cache(maxsize=4)
def get_llm_provider(provider_type: str | None = None) -> LLMProviderInterface:
    """Returns the configured LLM provider singleton."""
    provider = (provider_type or settings.LLM_PROVIDER).lower()

    if provider == "groq":
        groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        is_test_env = settings.APP_ENV == "test" or os.getenv("APP_ENV") == "test"
        if is_test_env and os.getenv("LIVE_GROQ_TEST", "").lower() != "true":
            return GroundedSynthesisProvider()
        if is_test_env and not groq_key:
            return GroundedSynthesisProvider()
        return GroqProvider()

    if provider in {"synthesis", "local", "grounded"}:
        return GroundedSynthesisProvider()

    if settings.APP_ENV == "test" and not provider_type:
        return GroundedSynthesisProvider()

    if provider in {"openai", "vllm", "ollama"}:
        base_url = settings.LLM_BASE_URL or "https://api.openai.com/v1"
        if provider == "ollama" and not settings.LLM_BASE_URL:
            base_url = "http://localhost:11434/v1"
        return OpenAICompatibleProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=base_url,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )

    return GroundedSynthesisProvider()
