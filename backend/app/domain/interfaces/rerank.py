"""Reranking interface (port).

Retrieval optimises for recall: get the right passage into the top ~20 cheaply.
Reranking optimises for precision: score each candidate *against the query
jointly*, which a bi-encoder cannot do because it embedded the passage before
it ever saw the query. It is the stage that turns "the answer is somewhere in
these ten chunks" into "it is this one" (blueprint §17, provider #7).

Implementations live in ``app.infrastructure.rerank``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class RerankProvider(Protocol):
    """Contract for scoring candidate passages against a query."""

    async def rerank(
        self, query: str, documents: Sequence[str], *, top_k: int | None = None
    ) -> list[tuple[int, float]]:
        """Return ``(index, score)`` into ``documents``, most relevant first.

        Indices refer to positions in the input sequence, so the caller keeps
        ownership of whatever metadata it attached. Scores are comparable only
        within one call. Implementations may return fewer results than they
        were given when ``top_k`` is set, but never more, and never an index
        they were not given.
        """
        ...
