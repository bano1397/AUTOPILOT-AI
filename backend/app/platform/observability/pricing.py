"""Provider/model pricing.

Cost per execution is computed from a ``(provider, model) -> per-1k-token``
price table. Local Ollama models are free, so the table starts empty and every
unknown pair costs $0 — but the moment a paid provider/model is added here, the
cost dashboard is correct with no other code changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1,000 tokens."""

    prompt_per_1k: float
    completion_per_1k: float


# (provider, model) -> price. Extend when paid providers are enabled.
PRICE_TABLE: dict[tuple[str, str], ModelPrice] = {}


def compute_cost(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Return the USD cost of an execution (0.0 for unpriced local models)."""
    price = PRICE_TABLE.get((provider, model))
    if price is None:
        return 0.0
    cost = (
        prompt_tokens / 1000 * price.prompt_per_1k
        + completion_tokens / 1000 * price.completion_per_1k
    )
    return round(cost, 6)
