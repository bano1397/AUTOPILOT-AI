"""Jina AI implementation of :class:`EmbeddingProvider`.

Calls Jina's hosted ``/v1/embeddings`` endpoint (OpenAI-shaped) over HTTPS — the
cloud counterpart to the local Ollama embedder, with a free tier that needs no
card. A thin httpx client keeps the wire format unit-testable with
``httpx.MockTransport``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.platform.registry import register_provider

_DEFAULT_BASE_URL = "https://api.jina.ai/v1"


@register_provider(kind="embedding", name="jina")
class JinaEmbeddingProvider:
    """Embeds text batches via Jina AI's hosted embeddings API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        dimensions: int | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        batch_size: int = 32,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("Jina API key is required")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            body: dict[str, Any] = {"model": self._model, "input": batch}
            if self._dimensions is not None:
                body["dimensions"] = self._dimensions
            response = await self._client.post("/embeddings", json=body)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError(
                    "Jina returned a malformed embedding response "
                    f"({len(batch)} inputs, got {data!r:.100})"
                )
            # The API preserves input order, but sort by index defensively.
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            embeddings.extend(
                [[float(value) for value in item["embedding"]] for item in ordered]
            )
        return embeddings
