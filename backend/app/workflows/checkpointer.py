"""LangGraph checkpointer lifecycle.

Wraps :class:`AsyncSqliteSaver` so the application (lifespan) and tests can own
its connection explicitly: ``start()`` before use, ``stop()`` on shutdown.
Graphs compiled with the saver persist their state per ``thread_id`` (we use the
workflow run id), enabling pause (interrupt) and resume across requests.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


class WorkflowCheckpointer:
    """Owns an ``AsyncSqliteSaver`` and its underlying connection."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._context: Any = None
        self.saver: AsyncSqliteSaver | None = None

    async def start(self) -> None:
        if self.saver is not None:
            return
        self._context = AsyncSqliteSaver.from_conn_string(self._path)
        self.saver = await self._context.__aenter__()

    async def stop(self) -> None:
        if self._context is not None:
            await self._context.__aexit__(None, None, None)
            self._context = None
            self.saver = None
