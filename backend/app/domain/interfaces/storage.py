"""File-storage interface (port).

Defines the contract the documents feature (and any future feature persisting
binary content) depends on. The default local-filesystem implementation lives in
``app.infrastructure.storage``; an S3/GCS/Azure implementation can be
substituted without changing callers (blueprint §5, provider #5).
"""

from __future__ import annotations

from typing import Protocol


class StorageProvider(Protocol):
    """Contract for binary object storage.

    Paths returned by :meth:`save` are opaque provider-relative keys; callers
    must not construct or interpret them.
    """

    async def save(self, content: bytes, *, suffix: str = "") -> str:
        """Persist ``content`` under a new random key and return that key.

        ``suffix`` (e.g. ``".pdf"``) is appended to the generated name so the
        stored object keeps a meaningful extension.
        """
        ...

    async def get(self, path: str) -> bytes:
        """Return the content stored under ``path``.

        Raises ``FileNotFoundError`` when the object does not exist.
        """
        ...

    async def delete(self, path: str) -> None:
        """Remove the object stored under ``path`` (no-op when absent)."""
        ...

    def url_for(self, path: str) -> str:
        """Return a provider-specific locator for the object (for diagnostics)."""
        ...
