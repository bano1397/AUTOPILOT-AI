"""Unit tests for the reranking providers.

The Jina provider is exercised against ``httpx.MockTransport``, the same way
every other cloud provider in this project is: the contract under test is the
wire format and the index-safety guarantee, not the model's judgement.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.infrastructure.rerank import JinaRerankProvider, NoopRerankProvider


def _provider(handler: Any) -> JinaRerankProvider:
    return JinaRerankProvider(
        api_key="test-key",
        model="jina-reranker-v2-base-multilingual",
        client=httpx.AsyncClient(
            base_url="https://api.jina.ai/v1", transport=httpx.MockTransport(handler)
        ),
    )


class TestNoopReranker:
    async def test_preserves_input_order(self) -> None:
        ranked = await NoopRerankProvider().rerank("q", ["a", "b", "c"])

        assert [index for index, _ in ranked] == [0, 1, 2]

    async def test_scores_descend_so_defensive_sorting_is_a_no_op(self) -> None:
        ranked = await NoopRerankProvider().rerank("q", ["a", "b", "c"])
        scores = [score for _, score in ranked]

        assert scores == sorted(scores, reverse=True)

    async def test_respects_top_k(self) -> None:
        ranked = await NoopRerankProvider().rerank("q", ["a", "b", "c"], top_k=2)

        assert [index for index, _ in ranked] == [0, 1]

    async def test_empty_input(self) -> None:
        assert await NoopRerankProvider().rerank("q", []) == []


class TestJinaReranker:
    async def test_sends_the_documented_request_shape(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["json"] = json.loads(request.content)
            return httpx.Response(
                200, json={"results": [{"index": 0, "relevance_score": 0.9}]}
            )

        await _provider(handler).rerank("vacation policy", ["a doc"], top_k=5)

        assert captured["url"].endswith("/rerank")
        assert captured["json"]["query"] == "vacation policy"
        assert captured["json"]["documents"] == ["a doc"]
        assert captured["json"]["top_n"] == 5

    async def test_the_default_client_carries_the_api_key(self) -> None:
        """Asserted on a self-built client: an injected one is a test seam and
        supplies its own headers (same convention as the embeddings provider)."""
        provider = JinaRerankProvider(api_key="test-key", model="m")

        assert provider._client.headers["authorization"] == "Bearer test-key"  # noqa: SLF001

    async def test_returns_indices_and_scores_best_first(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"index": 2, "relevance_score": 0.91},
                        {"index": 0, "relevance_score": 0.42},
                    ]
                },
            )

        ranked = await _provider(handler).rerank("q", ["a", "b", "c"])

        assert ranked == [(2, 0.91), (0, 0.42)]

    async def test_reorders_a_response_returned_out_of_order(self) -> None:
        """The ordering guarantee is ours, not the API's."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"index": 0, "relevance_score": 0.1},
                        {"index": 1, "relevance_score": 0.8},
                    ]
                },
            )

        ranked = await _provider(handler).rerank("q", ["a", "b"])

        assert [index for index, _ in ranked] == [1, 0]

    async def test_an_out_of_range_index_is_rejected(self) -> None:
        """Silently accepting it would cite a document that was never sent."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"results": [{"index": 7, "relevance_score": 0.9}]}
            )

        with pytest.raises(ValueError, match="index 7"):
            await _provider(handler).rerank("q", ["a", "b"])

    async def test_a_malformed_response_is_rejected(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": True})

        with pytest.raises(ValueError, match="malformed"):
            await _provider(handler).rerank("q", ["a"])

    async def test_an_http_error_propagates(self) -> None:
        """The caller degrades; the provider does not pretend to have ranked."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "rate limited"})

        with pytest.raises(httpx.HTTPStatusError):
            await _provider(handler).rerank("q", ["a"])

    async def test_no_documents_skips_the_call_entirely(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("should not call the API with no documents")

        assert await _provider(handler).rerank("q", []) == []

    async def test_an_empty_api_key_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="API key"):
            JinaRerankProvider(api_key="", model="m")
