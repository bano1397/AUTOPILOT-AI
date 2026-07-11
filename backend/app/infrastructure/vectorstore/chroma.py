"""ChromaDB implementation of :class:`VectorStoreProvider`.

Speaks ChromaDB's v2 REST API directly over httpx rather than pulling in the
``chromadb`` client package: we need exactly four endpoints, and a thin client
keeps the dependency tree small and the wire format unit-testable with
``httpx.MockTransport``. The collection is created on first use (get-or-create)
and its id cached for the provider's lifetime.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.interfaces.vector_store import VectorMatch
from app.platform.registry import register_provider


@register_provider(kind="vectorstore", name="chroma")
class ChromaVectorStore:
    """Vector storage and similarity search on a ChromaDB server."""

    def __init__(
        self,
        base_url: str,
        collection: str,
        *,
        client: httpx.AsyncClient | None = None,
        tenant: str = "default_tenant",
        database: str = "default_database",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._collection_name = collection
        self._prefix = f"/api/v2/tenants/{tenant}/databases/{database}"
        self._collection_id: str | None = None
        self._collection_lock = asyncio.Lock()

    async def _collection(self) -> str:
        """Return the collection id, creating the collection on first use."""
        if self._collection_id is not None:
            return self._collection_id
        async with self._collection_lock:
            if self._collection_id is None:
                response = await self._client.post(
                    f"{self._prefix}/collections",
                    json={"name": self._collection_name, "get_or_create": True},
                )
                response.raise_for_status()
                self._collection_id = str(response.json()["id"])
        return self._collection_id

    async def upsert(
        self,
        *,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        collection_id = await self._collection()
        response = await self._client.post(
            f"{self._prefix}/collections/{collection_id}/upsert",
            json={
                "ids": list(ids),
                "embeddings": [list(vector) for vector in embeddings],
                "documents": list(documents),
                "metadatas": list(metadatas),
            },
        )
        response.raise_for_status()

    async def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        collection_id = await self._collection()
        body: dict[str, Any] = {
            "query_embeddings": [list(embedding)],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            body["where"] = where
        response = await self._client.post(
            f"{self._prefix}/collections/{collection_id}/query", json=body
        )
        response.raise_for_status()
        payload = response.json()

        ids: list[str] = payload["ids"][0] if payload.get("ids") else []
        documents = (payload.get("documents") or [[]])[0]
        metadatas = (payload.get("metadatas") or [[]])[0]
        distances = (payload.get("distances") or [[]])[0]
        matches: list[VectorMatch] = []
        for position, match_id in enumerate(ids):
            matches.append(
                VectorMatch(
                    id=str(match_id),
                    text=str(documents[position]) if position < len(documents) else "",
                    metadata=dict(metadatas[position] or {}) if position < len(metadatas) else {},
                    distance=float(distances[position]) if position < len(distances) else 0.0,
                )
            )
        return matches

    async def delete(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        collection_id = await self._collection()
        response = await self._client.post(
            f"{self._prefix}/collections/{collection_id}/delete", json={"ids": list(ids)}
        )
        response.raise_for_status()
