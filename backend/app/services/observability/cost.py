"""Model pricing catalog and token cost accounting engine for Phase 11."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelPricing:
    """Pricing configuration for an AI model per million tokens."""

    model_id: str
    provider: str
    input_cost_per_1m: float  # USD per 1M input / prompt tokens
    output_cost_per_1m: float  # USD per 1M output / completion tokens
    currency: str = "USD"
    pricing_source: str = "standard_catalog_2026"
    last_updated: str = "2026-10-01"


# Verified model pricing catalog (USD per 1M tokens)
STANDARD_MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI Models
    "gpt-4o": ModelPricing(
        model_id="gpt-4o",
        provider="openai",
        input_cost_per_1m=2.50,
        output_cost_per_1m=10.00,
    ),
    "gpt-4o-mini": ModelPricing(
        model_id="gpt-4o-mini",
        provider="openai",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
    ),
    "gpt-3.5-turbo": ModelPricing(
        model_id="gpt-3.5-turbo",
        provider="openai",
        input_cost_per_1m=0.50,
        output_cost_per_1m=1.50,
    ),
    # Anthropic Models
    "claude-3-5-sonnet": ModelPricing(
        model_id="claude-3-5-sonnet",
        provider="anthropic",
        input_cost_per_1m=3.00,
        output_cost_per_1m=15.00,
    ),
    "claude-3-haiku": ModelPricing(
        model_id="claude-3-haiku",
        provider="anthropic",
        input_cost_per_1m=0.25,
        output_cost_per_1m=1.25,
    ),
    # Google Models
    "gemini-1.5-pro": ModelPricing(
        model_id="gemini-1.5-pro",
        provider="google",
        input_cost_per_1m=3.50,
        output_cost_per_1m=10.50,
    ),
    "gemini-1.5-flash": ModelPricing(
        model_id="gemini-1.5-flash",
        provider="google",
        input_cost_per_1m=0.35,
        output_cost_per_1m=1.05,
    ),
    # Embeddings
    "text-embedding-3-small": ModelPricing(
        model_id="text-embedding-3-small",
        provider="openai",
        input_cost_per_1m=0.02,
        output_cost_per_1m=0.00,
    ),
    "text-embedding-3-large": ModelPricing(
        model_id="text-embedding-3-large",
        provider="openai",
        input_cost_per_1m=0.13,
        output_cost_per_1m=0.00,
    ),
    # Mock / Local
    "mock": ModelPricing(
        model_id="mock",
        provider="local",
        input_cost_per_1m=0.00,
        output_cost_per_1m=0.00,
        pricing_source="local_zero_cost",
    ),
    "default": ModelPricing(
        model_id="default",
        provider="local",
        input_cost_per_1m=0.00,
        output_cost_per_1m=0.00,
        pricing_source="local_zero_cost",
    ),
}


@dataclass
class CostCalculationResult:
    """Explicit calculation result distinguishing estimates, provider charges, and unavailable states."""

    estimated_cost_usd: float | None
    cost_status: str  # "estimated" | "provider_reported" | "unavailable"
    currency: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int
    pricing_source: str | None
    is_exact_provider_charge: bool


class CostIntelligenceEngine:
    """Calculates model execution costs with transparent provenance and safe guards."""

    @classmethod
    def get_pricing(cls, model_name: str) -> ModelPricing | None:
        """Finds pricing configuration matching model name or substring."""
        if not model_name:
            return None
        m_lower = model_name.lower()
        if m_lower in STANDARD_MODEL_PRICING:
            return STANDARD_MODEL_PRICING[m_lower]

        for k, pricing in STANDARD_MODEL_PRICING.items():
            if k in m_lower:
                return pricing
        return None

    @classmethod
    def calculate_cost(
        cls,
        model: str | None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        provider_reported_cost: float | None = None,
    ) -> CostCalculationResult:
        """Calculates model cost, strictly distinguishing provider charges from estimates or unknown states."""
        # 1. Exact provider-reported cost takes precedence if present
        if provider_reported_cost is not None:
            return CostCalculationResult(
                estimated_cost_usd=round(provider_reported_cost, 6),
                cost_status="provider_reported",
                currency="USD",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens or ((prompt_tokens or 0) + (completion_tokens or 0)),
                pricing_source="provider_api_metadata",
                is_exact_provider_charge=True,
            )

        # 2. Check if model and token metadata are available
        tot = total_tokens or ((prompt_tokens or 0) + (completion_tokens or 0))
        if not model or (prompt_tokens is None and completion_tokens is None and not tot):
            return CostCalculationResult(
                estimated_cost_usd=None,
                cost_status="unavailable",
                currency="USD",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tot,
                pricing_source=None,
                is_exact_provider_charge=False,
            )

        pricing = cls.get_pricing(model)
        if not pricing:
            return CostCalculationResult(
                estimated_cost_usd=None,
                cost_status="unavailable",
                currency="USD",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tot,
                pricing_source=None,
                is_exact_provider_charge=False,
            )

        # If zero cost model (mock/local)
        if pricing.input_cost_per_1m == 0.0 and pricing.output_cost_per_1m == 0.0:
            return CostCalculationResult(
                estimated_cost_usd=0.0,
                cost_status="estimated",
                currency=pricing.currency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tot,
                pricing_source=pricing.pricing_source,
                is_exact_provider_charge=False,
            )

        # If prompt/completion split is missing, estimate proportional breakdown (75% in, 25% out)
        p_tok = prompt_tokens if prompt_tokens is not None else int(tot * 0.75)
        c_tok = completion_tokens if completion_tokens is not None else int(tot * 0.25)

        input_cost = (p_tok / 1_000_000.0) * pricing.input_cost_per_1m
        output_cost = (c_tok / 1_000_000.0) * pricing.output_cost_per_1m
        total_cost = round(input_cost + output_cost, 6)

        return CostCalculationResult(
            estimated_cost_usd=total_cost,
            cost_status="estimated",
            currency=pricing.currency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=tot,
            pricing_source=pricing.pricing_source,
            is_exact_provider_charge=False,
        )

    @classmethod
    def list_catalog(cls) -> list[dict[str, Any]]:
        """Returns all registered pricing definitions."""
        return [
            {
                "model_id": p.model_id,
                "provider": p.provider,
                "input_cost_per_1m": p.input_cost_per_1m,
                "output_cost_per_1m": p.output_cost_per_1m,
                "currency": p.currency,
                "pricing_source": p.pricing_source,
                "last_updated": p.last_updated,
            }
            for p in STANDARD_MODEL_PRICING.values()
        ]
