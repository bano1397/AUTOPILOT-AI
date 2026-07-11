"""In-memory fake providers for tests.

Deterministic stand-ins for the embedding and vector-store ports so pipeline
tests run without external services while still asserting real interactions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.interfaces.llm import ChatMessage, LLMResult
from app.domain.interfaces.search import SearchResult
from app.domain.interfaces.vector_store import VectorMatch


class FakeEmbeddingProvider:
    """Returns a small deterministic vector per text; can simulate failure."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.fail:
            raise RuntimeError("embedding service unavailable")
        batch = list(texts)
        self.calls.append(batch)
        return [[float(len(text)), 1.0, 0.0] for text in batch]


class FakeVectorStore:
    """Records upserts/deletes in a dict keyed by vector id."""

    def __init__(self) -> None:
        self.vectors: dict[str, dict[str, Any]] = {}

    async def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        for position, vector_id in enumerate(ids):
            self.vectors[vector_id] = {
                "embedding": list(embeddings[position]),
                "document": documents[position],
                "metadata": dict(metadatas[position]),
            }

    async def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        matches = [
            VectorMatch(
                id=vector_id, text=str(entry["document"]), metadata=dict(entry["metadata"])
            )
            for vector_id, entry in self.vectors.items()
            if not where
            or all(entry["metadata"].get(key) == value for key, value in where.items())
        ]
        return matches[:top_k]

    async def delete(self, ids: Sequence[str]) -> None:
        for vector_id in ids:
            self.vectors.pop(vector_id, None)


class FakeLLMProvider:
    """Returns a canned (or scripted) reply and records every conversation.

    Pass ``replies`` to script consecutive calls (e.g. a supervisor routing
    reply followed by a worker agent's answer); once the queue is exhausted the
    fixed ``reply`` is returned.
    """

    name = "fake"

    def __init__(
        self,
        *,
        reply: str = "fake answer",
        replies: list[str] | None = None,
        fail: bool = False,
    ) -> None:
        self.reply = reply
        self.replies = list(replies) if replies else []
        self.fail = fail
        self.calls: list[list[ChatMessage]] = []

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        if self.fail:
            raise RuntimeError("llm service unavailable")
        self.calls.append(list(messages))
        content = self.replies.pop(0) if self.replies else self.reply
        return LLMResult(
            content=content,
            model="fake-llm",
            prompt_tokens=7,
            completion_tokens=3,
            duration_ms=5,
        )


class FakeSearchProvider:
    """Canned web search results and page contents."""

    name = "fake-search"

    def __init__(
        self,
        *,
        results: list[SearchResult] | None = None,
        pages: dict[str, str] | None = None,
        fail: bool = False,
    ) -> None:
        self.results = results if results is not None else []
        self.pages = pages or {}
        self.fail = fail
        self.queries: list[str] = []
        self.fetched: list[str] = []

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        if self.fail:
            raise RuntimeError("search service unavailable")
        self.queries.append(query)
        return self.results[:max_results]

    async def fetch(self, url: str) -> str:
        self.fetched.append(url)
        if url not in self.pages:
            raise RuntimeError(f"no page for {url}")
        return self.pages[url]
