"""Jina AI implementation of :class:`RerankProvider`.

Calls Jina's hosted ``/v1/rerank`` endpoint — a real cross-encoder, scoring
each passage jointly with the query, on the same free tier and the same API key
as the embeddings provider this project already uses. A thin httpx client keeps
the wire format unit-testable with ``httpx.MockTransport``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.platform.registry import register_provider

_DEFAULT_BASE_URL = "https://api.jina.ai/v1"


@register_provider(kind="rerank", name="jina")
class JinaRerankProvider:
    """Cross-encoder reranking via Jina AI's hosted rerank API."""

    name = "jina"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("Jina API key is required")
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._model = model

    async def rerank(
        self, query: str, documents: Sequence[str], *, top_k: int | None = None
    ) -> list[tuple[int, float]]:
        if not documents:
            return []

        body: dict[str, Any] = {
            "model": self._model,
            "query": query,
            "documents": list(documents),
        }
        if top_k is not None:
            body["top_n"] = top_k

        response = await self._client.post("/rerank", json=body)
        response.raise_for_status()
        payload = response.json()

        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError(f"Jina returned a malformed rerank response: {payload!r:.200}")

        ranked: list[tuple[int, float]] = []
        for item in results:
            index = int(item["index"])
            # A provider must never invent a passage the caller did not send:
            # an out-of-range index would silently cite the wrong document.
            if not 0 <= index < len(documents):
                raise ValueError(
                    f"Jina returned index {index} for {len(documents)} documents"
                )
            ranked.append((index, float(item.get("relevance_score", 0.0))))

        # The API returns them ordered, but the contract is ours to guarantee.
        ranked.sort(key=lambda item: -item[1])
        return ranked
