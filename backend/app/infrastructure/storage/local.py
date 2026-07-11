"""Local-filesystem implementation of :class:`StorageProvider`.

Security posture (blueprint §27): files live outside the webroot in a
configurable base directory, are stored under random UUID names (never the
client-supplied filename), and every lookup is resolved against the base
directory to defeat path traversal. Blocking file I/O is offloaded to a worker
thread so the event loop is never stalled.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from app.platform.registry import register_provider


@register_provider(kind="storage", name="local")
class LocalStorageProvider:
    """Stores objects as files beneath a single base directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    def _resolve(self, path: str) -> Path:
        """Resolve a stored key to an absolute path, rejecting traversal."""
        resolved = (self._base / path).resolve()
        if not resolved.is_relative_to(self._base):
            raise ValueError(f"Storage path escapes base directory: {path!r}")
        return resolved

    async def save(self, content: bytes, *, suffix: str = "") -> str:
        name = uuid4().hex + suffix
        # Shard by the first two hex chars to keep directory listings small.
        relative = f"{name[:2]}/{name}"
        target = self._resolve(relative)

        def _write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        await asyncio.to_thread(_write)
        return relative

    async def get(self, path: str) -> bytes:
        target = self._resolve(path)
        return await asyncio.to_thread(target.read_bytes)

    async def delete(self, path: str) -> None:
        target = self._resolve(path)

        def _unlink() -> None:
            target.unlink(missing_ok=True)

        await asyncio.to_thread(_unlink)

    def url_for(self, path: str) -> str:
        return self._resolve(path).as_uri()
