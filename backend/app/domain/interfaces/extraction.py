"""Text-extraction interface (port).

Turns stored binary document content into plain text for the RAG pipeline.
Per-format implementations live in ``app.infrastructure.extraction``; an OCR
implementation for scanned documents can be added behind the same contract
(blueprint §5, provider #6).
"""

from __future__ import annotations

from typing import Protocol


class TextExtractionError(Exception):
    """Raised when content cannot be converted to text."""


class TextExtractor(Protocol):
    """Contract for converting one document format to plain text."""

    async def extract(self, content: bytes) -> str:
        """Return the plain text contained in ``content``.

        Raises :class:`TextExtractionError` when the content is malformed or
        yields no text.
        """
        ...
