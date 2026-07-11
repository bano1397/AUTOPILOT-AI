"""DuckDuckGo search provider.

Uses the key-less HTML endpoint over plain httpx and parses results with the
standard library's ``html.parser`` — no scraping framework, no API key.
Result links are DDG redirects carrying the real URL in the ``uddg`` query
parameter, which is decoded here.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.logging import get_logger
from app.domain.interfaces.search import SearchResult
from app.infrastructure.search.html_text import html_to_text
from app.platform.registry import register_provider

logger = get_logger("app.infrastructure.search")

_SEARCH_URL = "https://html.duckduckgo.com/html/"
_TIMEOUT_SECONDS = 20.0
_USER_AGENT = "Mozilla/5.0 (compatible; AutoPilotAI/1.0; +https://localhost)"
_PAGE_MAX_CHARS = 8000


class _ResultParser(HTMLParser):
    """Extracts DDG result titles/links (``result__a``) and snippets."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._in_title = False
        self._in_snippet = False
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": _decode_redirect(attributes.get("href") or ""),
                "snippet": "",
            }
            self._in_title = True
        elif "result__snippet" in classes and self._current is not None:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_title and tag == "a":
            self._in_title = False
        elif self._in_snippet and tag in {"a", "div", "span", "td"}:
            self._in_snippet = False
            if self._current is not None:
                self.results.append(self._current)
                self._current = None

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._in_title:
            self._current["title"] += data
        elif self._in_snippet:
            self._current["snippet"] += data


def _decode_redirect(href: str) -> str:
    """Resolve DDG's ``/l/?uddg=<encoded>`` redirect links to the target URL."""
    parsed = urlparse(href)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return href


@register_provider(kind="search", name="duckduckgo")
class DuckDuckGoSearchProvider:
    """Key-less web search via DuckDuckGo's HTML interface."""

    name = "duckduckgo"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        response = await self._request(
            "POST",
            _SEARCH_URL,
            data={"q": query},
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()

        parser = _ResultParser()
        parser.feed(response.text)
        results = [
            SearchResult(
                title=entry["title"].strip(),
                url=entry["url"],
                snippet=entry["snippet"].strip(),
            )
            for entry in parser.results
            if entry["url"].startswith(("http://", "https://"))
        ]
        logger.info(
            "search.completed", extra={"query": query[:80], "results": len(results)}
        )
        return results[:max_results]

    async def fetch(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Refusing to fetch non-http(s) URL: {url!r}")
        response = await self._request(
            "GET", url, headers={"User-Agent": _USER_AGENT}
        )
        response.raise_for_status()
        return html_to_text(response.text, max_chars=_PAGE_MAX_CHARS)

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, **kwargs)  # type: ignore[arg-type]
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            return await client.request(method, url, **kwargs)  # type: ignore[arg-type]
