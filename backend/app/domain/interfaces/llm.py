"""Domain abstraction for Large Language Model (LLM) providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, assistant, tool")
    content: str = Field(..., description="Message text content")
    name: str | None = None


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProviderInterface(ABC):
    """Abstract interface to allow swappable LLM backends (OpenAI, Anthropic, Ollama, vLLM, etc.)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generates a non-streamed response."""
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streams text chunks token-by-token."""
        pass
