"""Pass-through reranker (``RERANK_PROVIDER=none``) — the default.

Reranking needs a cross-encoder. There is no way to approximate one locally
without either a heavyweight model dependency or a lexical heuristic dressed up
as reranking — and a heuristic here would be worse than nothing, because it
would reorder the fused ranking using a signal BM25 already contributed,
undoing fusion while looking like an improvement.

So the default does nothing and says so. Reranking is real when
``RERANK_PROVIDER=jina`` is configured; otherwise the pipeline is honestly one
stage shorter.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.platform.registry import register_provider


@register_provider(kind="rerank", name="none")
class NoopRerankProvider:
    """Preserves the input ranking exactly."""

    name = "none"

    async def rerank(
        self, query: str, documents: Sequence[str], *, top_k: int | None = None
    ) -> list[tuple[int, float]]:
        # Descending scores keep the contract's "most relevant first" true for
        # callers that sort defensively.
        total = len(documents)
        ranked = [(index, float(total - index)) for index in range(total)]
        return ranked[:top_k] if top_k is not None else ranked
