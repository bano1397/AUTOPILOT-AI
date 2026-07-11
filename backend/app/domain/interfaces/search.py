"""Web search provider interface (port)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    """One web search hit."""

    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    """Contract for web search and page retrieval."""

    name: str

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Return the top results for ``query``."""
        ...

    async def fetch(self, url: str) -> str:
        """Return the readable text content of a page."""
        ...
