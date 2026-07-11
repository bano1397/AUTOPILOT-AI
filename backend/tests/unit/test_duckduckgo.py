"""Unit tests for the DuckDuckGo search provider (wire format + parsing)."""

from __future__ import annotations

import httpx
import pytest
from app.infrastructure.search import DuckDuckGoSearchProvider
from app.infrastructure.search.html_text import html_to_text

_DDG_HTML = """
<html><body>
  <div class="result">
    <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpost&rut=x">
      Example <b>Post</b>
    </a>
    <a class="result__snippet" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpost">
      A snippet about the post.
    </a>
  </div>
  <div class="result">
    <a class="result__a" href="https://direct.example.org/page">Direct Result</a>
    <div class="result__snippet">Another snippet.</div>
  </div>
  <div class="result">
    <a class="result__a" href="javascript:alert(1)">Bad Scheme</a>
    <div class="result__snippet">Should be filtered.</div>
  </div>
</body></html>
"""


async def test_search_parses_results_and_decodes_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://html.duckduckgo.com/html/")
        assert b"q=langgraph+release" in request.content
        return httpx.Response(200, text=_DDG_HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client=client)
        results = await provider.search("langgraph release", max_results=5)

    assert len(results) == 2  # javascript: result filtered out
    assert results[0].title == "Example Post"
    assert results[0].url == "https://example.com/post"
    assert "snippet about the post" in results[0].snippet
    assert results[1].url == "https://direct.example.org/page"


async def test_search_respects_max_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_DDG_HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client=client)
        results = await provider.search("q", max_results=1)

    assert len(results) == 1


async def test_fetch_extracts_readable_text() -> None:
    page = (
        "<html><head><title>T</title><style>.x{color:red}</style></head>"
        "<body><script>var hidden = 1;</script>"
        "<h1>Heading</h1><p>Body   text.</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client=client)
        text = await provider.fetch("https://example.com/a")

    assert text == "Heading Body text."
    assert "hidden" not in text


async def test_fetch_rejects_non_http_schemes() -> None:
    provider = DuckDuckGoSearchProvider()
    with pytest.raises(ValueError, match="non-http"):
        await provider.fetch("file:///etc/passwd")


def test_html_to_text_caps_length() -> None:
    text = html_to_text("<p>" + "word " * 5000 + "</p>", max_chars=100)
    assert len(text) == 100
