"""Groq LLM provider using asynchronous httpx with OpenAI-compatible API."""

import json
import os
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse

logger = get_logger(__name__)

# Redact potential API keys (e.g. gsk_...) and Bearer tokens from log messages
KEY_REDACT_REGEX = re.compile(r"(gsk_[a-zA-Z0-9_\-]{10,}|Bearer\s+[a-zA-Z0-9_\-\.]{10,})", re.IGNORECASE)


def redact_secret(text: str) -> str:
    """Redacts Groq or other API keys from strings."""
    if not text:
        return text
    return KEY_REDACT_REGEX.sub("***REDACTED_SECRET***", text)


class GroqProvider(LLMProviderInterface):
    """Production-grade Groq provider communicating with GroqCloud chat completions."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 2,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = str(
                os.getenv("GROQ_API_KEY")
                or getattr(settings, "GROQ_API_KEY", "")
                or getattr(settings, "LLM_API_KEY", "")
                or ""
            )
        if model is not None:
            self.model = model
        else:
            self.model = str(
                os.getenv("GROQ_MODEL")
                or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
                or "llama-3.3-70b-versatile"
            )
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = str(
                os.getenv("GROQ_BASE_URL")
                or getattr(settings, "GROQ_BASE_URL", None)
                or getattr(settings, "LLM_BASE_URL", None)
                or "https://api.groq.com/openai/v1"
            ).rstrip("/")
        self.timeout = timeout_seconds or getattr(settings, "LLM_TIMEOUT_SECONDS", 30.0)
        self.max_retries = max_retries
        self.provider_name = "groq"
        self.model_name = self.model

    def validate_configuration(self) -> None:
        """Validates that a non-empty API key is present."""
        if not self.api_key or not self.api_key.strip():
            raise AppError(
                code="LLM_CONFIG_ERROR",
                message="Groq API key is not configured. Please set GROQ_API_KEY in the environment.",
                status_code=500,
            )

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        """Executes chat completion with truthful error reporting and bounded retry."""
        self.validate_configuration()

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

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if not choices:
                            raise AppError(
                                code="LLM_MALFORMED_RESPONSE",
                                message="Groq returned empty choices array in response.",
                                status_code=502,
                            )

                        choice = choices[0]
                        content = choice.get("message", {}).get("content", "")
                        usage = data.get("usage", {})

                        return LLMResponse(
                            content=content,
                            model=self.model,
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                            finish_reason=choice.get("finish_reason"),
                            metadata={
                                "provider": "groq",
                                "model": self.model,
                                "attempt": attempt + 1,
                            },
                        )

                    # Handle HTTP Errors
                    if res.status_code == 401:
                        logger.error("Groq authentication failure (HTTP 401)")
                        raise AppError(
                            code="LLM_AUTH_ERROR",
                            message="Groq authentication failed. Please verify that GROQ_API_KEY is valid and active.",
                            status_code=401,
                        )

                    if res.status_code == 429:
                        error_body = redact_secret(res.text[:300])
                        logger.warning("Groq rate limit exceeded (HTTP 429): %s", error_body)
                        if attempt < self.max_retries:
                            import asyncio

                            await asyncio.sleep(min(1.0 * (attempt + 1), 2.5))
                            continue
                        raise AppError(
                            code="LLM_RATE_LIMIT",
                            message="Groq API rate limit reached. Please retry after a brief delay.",
                            status_code=429,
                        )

                    if res.status_code == 400:
                        error_body = redact_secret(res.text[:300])
                        logger.error("Groq bad request (HTTP 400): %s", error_body)
                        raise AppError(
                            code="LLM_BAD_REQUEST",
                            message=f"Groq rejected request: {error_body}",
                            status_code=400,
                        )

                    # 5xx server error: retry
                    if res.status_code >= 500 and attempt < self.max_retries:
                        import asyncio

                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue

                    error_body = redact_secret(res.text[:300])
                    raise AppError(
                        code="LLM_PROVIDER_ERROR",
                        message=f"Groq API returned HTTP {res.status_code}: {error_body}",
                        status_code=502,
                    )

            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("Groq request timed out (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    import asyncio

                    await asyncio.sleep(0.5)
                    continue
                raise AppError(
                    code="LLM_TIMEOUT",
                    message=f"Groq request timed out after {self.timeout} seconds.",
                    status_code=504,
                ) from exc

            except AppError:
                raise

            except Exception as exc:
                last_error = exc
                redacted_msg = redact_secret(str(exc))
                logger.error("Unexpected error during Groq API call: %s", redacted_msg)
                if attempt < self.max_retries:
                    import asyncio

                    await asyncio.sleep(0.5)
                    continue
                raise AppError(
                    code="LLM_PROVIDER_ERROR",
                    message=f"Groq communication error: {redacted_msg}",
                    status_code=502,
                ) from exc

        raise AppError(
            code="LLM_PROVIDER_ERROR",
            message=f"Groq API call failed after {self.max_retries + 1} attempts: {last_error}",
            status_code=502,
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streams chat completion tokens from Groq."""
        self.validate_configuration()

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
                        raw_bytes = await response.aread()
                        decoded_err = raw_bytes.decode("utf-8", errors="replace")
                        err_text = redact_secret(decoded_err)
                        raise AppError(
                            code="LLM_STREAM_ERROR",
                            message=f"Groq stream error (HTTP {response.status_code}): {err_text[:200]}",
                            status_code=502,
                        )

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
        except AppError:
            raise
        except Exception as exc:
            redacted_msg = redact_secret(str(exc))
            raise AppError(
                code="LLM_STREAM_ERROR",
                message=f"Groq streaming connection failed: {redacted_msg}",
                status_code=502,
            ) from exc
