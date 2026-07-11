"""Wire-format tests for the Ollama embedding provider (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.infrastructure.embeddings import OllamaEmbeddingProvider


def _client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )


def _provider(handler: Any, **kwargs: Any) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url="http://ollama.test", model="nomic-embed-text", client=_client(handler), **kwargs
    )


async def test_embed_sends_model_and_input_batch() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200, json={"embeddings": [[0.1, 0.2] for _ in body["input"]]}
        )

    vectors = await _provider(handler).embed(["alpha", "beta"])

    assert vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert requests == [{"model": "nomic-embed-text", "input": ["alpha", "beta"]}]


async def test_embed_batches_large_inputs() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        batch_sizes.append(len(body["input"]))
        return httpx.Response(200, json={"embeddings": [[1.0]] * len(body["input"])})

    vectors = await _provider(handler, batch_size=32).embed([f"t{i}" for i in range(70)])

    assert len(vectors) == 70
    assert batch_sizes == [32, 32, 6]


async def test_http_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model not found"})

    with pytest.raises(httpx.HTTPStatusError):
        await _provider(handler).embed(["alpha"])


async def test_malformed_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1]]})  # 1 vector for 2 inputs

    with pytest.raises(ValueError, match="malformed"):
        await _provider(handler).embed(["alpha", "beta"])


async def test_empty_input_makes_no_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request expected")

    assert await _provider(handler).embed([]) == []
