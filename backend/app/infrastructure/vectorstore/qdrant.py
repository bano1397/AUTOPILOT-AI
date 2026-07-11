"""Qdrant implementation of :class:`VectorStoreProvider`.

Speaks Qdrant's REST API directly over httpx (thin client, unit-testable with
``httpx.MockTransport``) — the cloud counterpart to the local ChromaDB store,
with a free managed tier. Two impedance mismatches are bridged here:

* Qdrant point ids must be uint64 or UUID; caller ids are arbitrary strings, so
  each is mapped to a deterministic UUIDv5 and the original id is kept in the
  payload (and restored on read).
* Qdrant returns a cosine *similarity* score (higher = closer); the port's
  contract is a *distance* (smaller = closer), so ``distance = 1 - score`` —
  which keeps ``relevance = 1 - distance`` identical to the Chroma path.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.interfaces.vector_store import VectorMatch
from app.platform.registry import register_provider

_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
_DOCUMENT_KEY = "_document"
_ID_KEY = "_source_id"


def _point_id(source_id: str) -> str:
    """Deterministic UUIDv5 for an arbitrary caller id (stable across calls)."""
    return str(uuid.uuid5(_NAMESPACE, source_id))


@register_provider(kind="vectorstore", name="qdrant")
class QdrantVectorStore:
    """Vector storage and similarity search on a Qdrant server."""

    def __init__(
        self,
        base_url: str,
        collection: str,
        *,
        dimension: int,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        headers = {"api-key": api_key} if api_key else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, headers=headers
        )
        self._collection = collection
        self._dimension = dimension
        self._ready = False
        self._lock = asyncio.Lock()

    async def _ensure_collection(self) -> None:
        """Create the collection on first use (idempotent get-or-create)."""
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            existing = await self._client.get(f"/collections/{self._collection}")
            if existing.status_code == 404:
                created = await self._client.put(
                    f"/collections/{self._collection}",
                    json={
                        "vectors": {"size": self._dimension, "distance": "Cosine"}
                    },
                )
                created.raise_for_status()
            else:
                existing.raise_for_status()
            self._ready = True

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
        await self._ensure_collection()
        points: list[dict[str, Any]] = []
        for position, source_id in enumerate(ids):
            payload: dict[str, Any] = dict(metadatas[position])
            payload[_DOCUMENT_KEY] = documents[position]
            payload[_ID_KEY] = source_id
            points.append(
                {
                    "id": _point_id(source_id),
                    "vector": [float(value) for value in embeddings[position]],
                    "payload": payload,
                }
            )
        response = await self._client.put(
            f"/collections/{self._collection}/points",
            params={"wait": "true"},
            json={"points": points},
        )
        response.raise_for_status()

    async def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        await self._ensure_collection()
        body: dict[str, Any] = {
            "vector": [float(value) for value in embedding],
            "limit": top_k,
            "with_payload": True,
        }
        if where:
            body["filter"] = {
                "must": [
                    {"key": key, "match": {"value": value}}
                    for key, value in where.items()
                ]
            }
        response = await self._client.post(
            f"/collections/{self._collection}/points/search", json=body
        )
        response.raise_for_status()
        results = response.json().get("result") or []

        matches: list[VectorMatch] = []
        for item in results:
            payload = dict(item.get("payload") or {})
            text = str(payload.pop(_DOCUMENT_KEY, ""))
            source_id = str(payload.pop(_ID_KEY, item.get("id", "")))
            score = float(item.get("score", 0.0))
            matches.append(
                VectorMatch(
                    id=source_id,
                    text=text,
                    metadata=payload,
                    distance=1.0 - score,
                )
            )
        return matches

    async def delete(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        await self._ensure_collection()
        response = await self._client.post(
            f"/collections/{self._collection}/points/delete",
            params={"wait": "true"},
            json={"points": [_point_id(source_id) for source_id in ids]},
        )
        response.raise_for_status()
