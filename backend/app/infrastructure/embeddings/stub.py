"""Deterministic stub embeddings (``EMBEDDING_PROVIDER=stub``).

Hash-based bag-of-words vectors: no model, no network, and identical output for
identical input across processes and runs. Companion to the stub LLM — see
``app.infrastructure.llm.stub`` for why these exist.

The vectors carry *some* real signal (texts sharing words land nearer each
other), which is enough for an end-to-end suite to assert that retrieval
returns the document it just uploaded. It is not enough for useful semantic
search: unrelated texts that share common words will collide. Do not deploy it.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from app.platform.registry import register_provider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@register_provider(kind="embedding", name="stub")
class StubEmbeddingProvider:
    """Deterministic hashed bag-of-words vectors."""

    name = "stub"

    def __init__(self, *, dimensions: int = 768) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self._dimensions
            # Sign from a separate bit so different tokens can cancel rather
            # than only ever accumulating.
            vector[bucket] += 1.0 if digest[0] & 1 else -1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            # An empty or token-free text still needs a valid unit vector.
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]
