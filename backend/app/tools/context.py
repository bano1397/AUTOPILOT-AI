"""Dependency bundle handed to tools at construction time.

Tools are constructed per invocation with the providers they declare in
``ToolMeta.dependencies``. Bundling them keeps every tool's constructor identical
so the registry can instantiate any tool uniformly, without a per-tool factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.search import SearchProvider
from app.domain.interfaces.vector_store import VectorStoreProvider


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool may need, resolved at call time from ``app.state``."""

    # The workspace identity the invocation runs as; tools that touch
    # owner-scoped data must filter by it.
    user_id: UUID
    db: DatabaseProvider
    embeddings: EmbeddingProvider
    vector_store: VectorStoreProvider
    search: SearchProvider
