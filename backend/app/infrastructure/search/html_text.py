"""Readable-text extraction from HTML using only the standard library."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIPPED_TAGS = {"script", "style", "noscript", "head", "template", "svg"}


class _TextCollector(HTMLParser):
    """Collects visible text, skipping non-content tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    @property
    def text(self) -> str:
        return " ".join(self._chunks)


def html_to_text(html: str, *, max_chars: int = 8000) -> str:
    """Strip an HTML document down to whitespace-normalized visible text."""
    collector = _TextCollector()
    collector.feed(html)
    text = re.sub(r"\s+", " ", collector.text).strip()
    return text[:max_chars]
