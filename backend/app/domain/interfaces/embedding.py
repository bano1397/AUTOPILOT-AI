"""Embedding interface (port).

Turns text into dense vectors for semantic indexing and retrieval. The default
implementation calls a local Ollama instance; hosted providers (OpenAI, Cohere,
...) can be substituted without changing callers (blueprint §5, provider #2).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Contract for text-embedding backends."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in input order."""
        ...
