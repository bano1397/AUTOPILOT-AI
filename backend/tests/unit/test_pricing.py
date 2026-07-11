"""Unit tests for execution cost computation."""

from __future__ import annotations

from app.platform.observability.pricing import PRICE_TABLE, ModelPrice, compute_cost


def test_unpriced_model_costs_zero() -> None:
    assert compute_cost("ollama", "llama3", 1000, 1000) == 0.0


def test_priced_model_computes_cost() -> None:
    PRICE_TABLE[("acme", "gpt-x")] = ModelPrice(
        prompt_per_1k=0.01, completion_per_1k=0.03
    )
    try:
        # 2000 prompt tokens -> $0.02, 500 completion tokens -> $0.015
        assert compute_cost("acme", "gpt-x", 2000, 500) == 0.035
    finally:
        del PRICE_TABLE[("acme", "gpt-x")]


def test_zero_tokens_cost_zero_even_when_priced() -> None:
    PRICE_TABLE[("acme", "gpt-x")] = ModelPrice(
        prompt_per_1k=0.01, completion_per_1k=0.03
    )
    try:
        assert compute_cost("acme", "gpt-x", 0, 0) == 0.0
    finally:
        del PRICE_TABLE[("acme", "gpt-x")]
