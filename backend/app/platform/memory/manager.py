"""``MemoryManager`` — one facade over the six memory levels (blueprint §16).

| Level | Store | Lifespan | Owner |
|---|---|---|---|
| 1 Working | in-process dict | single run | :class:`WorkingMemory` (here) |
| 2 Conversation | SQL ``messages`` | per thread | ``ConversationService`` |
| 3 Long-term | ``memory_entries`` + vectors | durable | ``LongTermMemoryService`` |
| 4 Knowledge | ``document_chunks`` + vectors | durable | ``RagService`` |
| 5 Preference | ``workspace_preferences`` | durable | ``PreferencesService`` |
| 6 Workflow | LangGraph checkpoints | per run | ``WorkflowCheckpointer`` |

The facade exists so callers depend on *one* collaborator instead of five, and
so "what can this platform remember?" has a single answer. It deliberately owns
no storage of its own beyond working memory: each level's service remains the
source of truth and stays independently usable. Levels are optional — a caller
that only needs recall constructs the manager with just the long-term service,
and asking for an absent level raises rather than silently returning nothing.

This lives under ``app/platform/`` rather than the ``app/memory/`` the blueprint
sketched, matching where the other cross-cutting platform concerns already sit
(``platform/prompts``, ``platform/events``, ``platform/registry``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.features.conversations.service import ConversationService
from app.features.memory.models import MemoryEntry, MemoryKind
from app.features.memory.service import LongTermMemoryService, Recollection
from app.features.preferences.models import WorkspacePreferences
from app.features.preferences.service import PreferencesService
from app.features.rag.service import RagService

DEFAULT_RECALL_LIMIT = 3


class WorkingMemory:
    """Level 1: ephemeral scratch space for a single run.

    Intentionally trivial and in-process — working memory that outlived the run
    would be a different level. Values are JSON-friendly so a run's scratch can
    be logged or checkpointed alongside its state.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def update(self, values: dict[str, Any]) -> None:
        self._values.update(values)

    def all(self) -> dict[str, Any]:
        """Return a copy, so callers cannot mutate the scratch by reference."""
        return dict(self._values)

    def clear(self) -> None:
        self._values.clear()


class MemoryManager:
    """Unified access to every memory level the platform has."""

    def __init__(
        self,
        *,
        long_term: LongTermMemoryService | None = None,
        conversations: ConversationService | None = None,
        knowledge: RagService | None = None,
        preferences: PreferencesService | None = None,
        checkpointer: object | None = None,
    ) -> None:
        self._long_term = long_term
        self._conversations = conversations
        self._knowledge = knowledge
        self._preferences = preferences
        self._checkpointer = checkpointer
        self.working = WorkingMemory()

    # -- Level 3: long-term ------------------------------------------------

    async def remember(
        self,
        user_id: UUID,
        content: str,
        *,
        kind: MemoryKind = MemoryKind.FACT,
        source: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> MemoryEntry:
        """Store a durable fact."""
        return await self._require_long_term().remember(
            user_id, content, kind=kind, source=source, meta=meta
        )

    async def recall(
        self, user_id: UUID, query: str, *, top_k: int = DEFAULT_RECALL_LIMIT
    ) -> list[Recollection]:
        """Retrieve durable facts similar to ``query``.

        Propagates upstream failures. Callers that would rather answer without
        memory should use :meth:`recall_or_empty`.
        """
        return await self._require_long_term().recall(user_id, query, top_k=top_k)

    async def recall_or_empty(
        self, user_id: UUID, query: str, *, top_k: int = DEFAULT_RECALL_LIMIT
    ) -> list[Recollection]:
        """Recall, degrading to no memories on any failure.

        For call sites where memory is an enhancement, not the answer: an
        unavailable embedding provider should cost the caller its recollections,
        not its response.
        """
        if self._long_term is None:
            return []
        try:
            return await self._long_term.recall(user_id, query, top_k=top_k)
        except Exception:  # noqa: BLE001 - degradation is the point
            return []

    # -- Level 2: conversation ---------------------------------------------

    async def history(self, conversation_id: UUID) -> list[dict[str, str]]:
        """Recent turns of a thread, as role/content dicts."""
        if self._conversations is None:
            raise RuntimeError("MemoryManager has no conversation service configured")
        return await self._conversations.history(conversation_id)

    # -- Level 4: knowledge -------------------------------------------------

    async def search_knowledge(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[Any]:
        """Semantic search over indexed document chunks."""
        if self._knowledge is None:
            raise RuntimeError("MemoryManager has no knowledge service configured")
        return await self._knowledge.query(user_id, query, top_k=top_k)

    # -- Level 5: preferences ------------------------------------------------

    async def preferences(self) -> WorkspacePreferences:
        """The workspace preference row."""
        if self._preferences is None:
            raise RuntimeError("MemoryManager has no preferences service configured")
        return await self._preferences.get()

    # -- Level 6: workflow ---------------------------------------------------

    @property
    def checkpointer(self) -> object | None:
        """The LangGraph checkpoint saver, or None when running without one."""
        return self._checkpointer

    # -- internals -----------------------------------------------------------

    def _require_long_term(self) -> LongTermMemoryService:
        if self._long_term is None:
            raise RuntimeError("MemoryManager has no long-term service configured")
        return self._long_term
