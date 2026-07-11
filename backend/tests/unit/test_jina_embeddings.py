"""Wire-format tests for the Jina embedding provider (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.infrastructure.embeddings import JinaEmbeddingProvider


def _provider(handler: Any, **kwargs: Any) -> JinaEmbeddingProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://jina.test/v1"
    )
    return JinaEmbeddingProvider(
        api_key="jina-test", model="jina-embeddings-v3", client=client, **kwargs
    )


async def test_embed_sends_model_input_and_parses_vectors() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    vectors = await _provider(handler, dimensions=768).embed(["a", "b"])

    assert requests[0]["model"] == "jina-embeddings-v3"
    assert requests[0]["input"] == ["a", "b"]
    assert requests[0]["dimensions"] == 768
    # Returned in input order regardless of response ordering.
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_batches_large_inputs() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        batch = json.loads(request.content)["input"]
        return httpx.Response(
            200,
            json={"data": [{"index": i, "embedding": [float(i)]} for i in range(len(batch))]},
        )

    vectors = await _provider(handler, batch_size=2).embed(["a", "b", "c"])
    assert calls == 2  # 2 + 1
    assert len(vectors) == 3


async def test_malformed_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    with pytest.raises(ValueError, match="malformed"):
        await _provider(handler).embed(["a"])


def test_empty_api_key_rejected() -> None:
    with pytest.raises(ValueError, match="API key"):
        JinaEmbeddingProvider(api_key="", model="x")
