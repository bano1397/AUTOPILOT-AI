"""Ollama implementation of :class:`EmbeddingProvider`.

Calls the local Ollama server's ``/api/embed`` endpoint (which accepts batch
input) over plain HTTP. The client is injectable so tests can verify the exact
wire format with ``httpx.MockTransport``.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.platform.registry import register_provider


@register_provider(kind="embedding", name="ollama")
class OllamaEmbeddingProvider:
    """Embeds text batches via a local Ollama instance."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        client: httpx.AsyncClient | None = None,
        batch_size: int = 32,
        timeout_seconds: float = 120.0,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._model = model
        self._batch_size = batch_size

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = await self._client.post(
                "/api/embed", json={"model": self._model, "input": batch}
            )
            response.raise_for_status()
            payload = response.json()
            batch_embeddings = payload.get("embeddings")
            if not isinstance(batch_embeddings, list) or len(batch_embeddings) != len(batch):
                raise ValueError(
                    "Ollama returned a malformed embedding response "
                    f"({len(batch)} inputs, got {batch_embeddings!r:.100})"
                )
            embeddings.extend([[float(value) for value in vector] for vector in batch_embeddings])
        return embeddings
