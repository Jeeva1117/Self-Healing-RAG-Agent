"""Domain abstraction for Agentic Tracing, Observability, and Metrics."""

from abc import ABC, abstractmethod
from typing import Any


class ObservabilityInterface(ABC):
    """Abstract interface to decouple tracing (LangSmith, OpenTelemetry, Arize Phoenix)."""

    @abstractmethod
    async def record_span(
        self,
        name: str,
        span_type: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> str:
        """Records an execution span for retrieval, verification, or generation."""
        pass

    @abstractmethod
    async def record_metric(
        self,
        metric_name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emits a quantitative metric."""
        pass
