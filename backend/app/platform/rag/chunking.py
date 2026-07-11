"""Deterministic sliding-window text chunker.

Splits text into overlapping character windows, preferring to break at
whitespace in the back half of a window so words are not cut mid-token. Pure
logic with no I/O — every RAG source (documents now; emails, web pages later)
reuses it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """One chunk of a larger text."""

    index: int
    text: str


class TextChunker:
    """Splits text into chunks of ``chunk_size`` chars overlapping by ``chunk_overlap``."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")
        self._size = chunk_size
        self._overlap = chunk_overlap

    def split(self, text: str) -> list[TextChunk]:
        stripped = text.strip()
        if not stripped:
            return []

        chunks: list[TextChunk] = []
        length = len(stripped)
        start = 0
        while start < length:
            end = min(start + self._size, length)
            if end < length:
                # Soft break: the last whitespace in the back half of the window.
                window = stripped[start:end]
                break_offset = max(window.rfind(" "), window.rfind("\n"), window.rfind("\t"))
                if break_offset > self._size // 2:
                    end = start + break_offset
            piece = stripped[start:end].strip()
            if piece:
                chunks.append(TextChunk(index=len(chunks), text=piece))
            if end >= length:
                break
            # Overlap with the previous window while guaranteeing forward progress.
            start = max(end - self._overlap, start + 1)
        return chunks
