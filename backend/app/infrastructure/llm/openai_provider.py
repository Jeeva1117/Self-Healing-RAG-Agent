"""OpenAI-compatible LLM provider using asynchronous httpx."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse
from app.infrastructure.llm.grounded_synthesis_provider import GroundedSynthesisProvider

logger = get_logger(__name__)


class OpenAICompatibleProvider(LLMProviderInterface):
    """Integrates with OpenAI, Groq, or any OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL or "gpt-4o"
        self.base_url = (base_url or getattr(settings, "LLM_BASE_URL", None) or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout_seconds
        self._fallback_provider = GroundedSynthesisProvider()

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Executes a chat completion call with automatic graceful fallback if key is missing or invalid."""
        if not self.api_key:
            logger.info("OpenAICompatibleProvider: No API key configured, using GroundedSynthesisProvider")
            return await self._fallback_provider.generate(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if res.status_code != 200:
                    logger.warning(
                        "LLM completion failed with status %d: %s. Falling back to GroundedSynthesisProvider.",
                        res.status_code,
                        res.text[:200],
                    )
                    return await self._fallback_provider.generate(
                        messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                    )

                data = res.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    model=self.model,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    finish_reason=choice.get("finish_reason"),
                    metadata={"provider": "openai_compatible"},
                )
        except Exception as e:
            logger.warning("Error during LLM API call: %s. Using GroundedSynthesisProvider fallback.", e)
            return await self._fallback_provider.generate(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streams chat completion tokens."""
        if not self.api_key:
            async for token in self._fallback_provider.generate_stream(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            ):
                yield token
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        async for token in self._fallback_provider.generate_stream(
                            messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                        ):
                            yield token
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception:
            async for token in self._fallback_provider.generate_stream(
                messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            ):
                yield token
