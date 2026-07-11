"""Wire-format tests for the Qdrant vector-store provider (MockTransport)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from app.infrastructure.vectorstore import QdrantVectorStore
from app.infrastructure.vectorstore.qdrant import _point_id

_COLLECTION = "autopilot_documents"


class _Server:
    """Minimal scripted Qdrant server; collection missing until created."""

    def __init__(self, search_result: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.exists = False
        self.search_result = search_result or []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.method, request.url.path, body))
        path = request.url.path
        if path == f"/collections/{_COLLECTION}" and request.method == "GET":
            if self.exists:
                return httpx.Response(200, json={"result": {}})
            return httpx.Response(404, json={"status": {"error": "not found"}})
        if path == f"/collections/{_COLLECTION}" and request.method == "PUT":
            self.exists = True
            return httpx.Response(200, json={"result": True})
        if path.endswith("/points/search"):
            return httpx.Response(200, json={"result": self.search_result})
        return httpx.Response(200, json={"result": {"status": "acknowledged"}})


def _store(server: _Server) -> QdrantVectorStore:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(server), base_url="http://qdrant.test"
    )
    return QdrantVectorStore(
        base_url="http://qdrant.test",
        collection=_COLLECTION,
        dimension=3,
        api_key="q-key",
        client=client,
    )


async def test_upsert_creates_collection_once_and_maps_ids() -> None:
    server = _Server()
    store = _store(server)

    await store.upsert(
        ids=["doc1:0"], embeddings=[[0.1, 0.2, 0.3]], documents=["hello"], metadatas=[{"k": 1}]
    )
    await store.upsert(
        ids=["doc1:1"], embeddings=[[0.4, 0.5, 0.6]], documents=["world"], metadatas=[{"k": 2}]
    )

    methods_paths = [(m, p) for m, p, _ in server.requests]
    # Collection existence checked, created once (PUT), then reused.
    assert methods_paths.count(("PUT", f"/collections/{_COLLECTION}")) == 1
    upserts = [b for m, p, b in server.requests if p.endswith("/points") and m == "PUT"]
    assert len(upserts) == 2
    point = upserts[0]["points"][0]
    assert point["id"] == _point_id("doc1:0")  # deterministic uuid5
    assert point["vector"] == [0.1, 0.2, 0.3]
    assert point["payload"]["_source_id"] == "doc1:0"
    assert point["payload"]["_document"] == "hello"
    assert point["payload"]["k"] == 1


async def test_query_converts_score_to_distance_and_restores_id() -> None:
    server = _Server(
        search_result=[
            {
                "id": str(uuid.uuid4()),
                "score": 0.9,
                "payload": {"_document": "hello", "_source_id": "doc1:0", "document_id": "doc1"},
            }
        ]
    )
    server.exists = True
    store = _store(server)

    matches = await store.query([0.1, 0.2, 0.3], top_k=5, where={"document_id": "doc1"})

    assert len(matches) == 1
    assert matches[0].id == "doc1:0"
    assert matches[0].text == "hello"
    assert matches[0].metadata == {"document_id": "doc1"}  # internal keys stripped
    assert abs(matches[0].distance - 0.1) < 1e-9  # 1 - score
    search_body = server.requests[-1][2]
    assert search_body["filter"] == {
        "must": [{"key": "document_id", "match": {"value": "doc1"}}]
    }
    assert search_body["limit"] == 5


async def test_delete_maps_ids_to_uuids() -> None:
    server = _Server()
    server.exists = True
    store = _store(server)

    await store.delete(["doc1:0", "doc1:1"])

    delete_body = server.requests[-1][2]
    assert delete_body["points"] == [_point_id("doc1:0"), _point_id("doc1:1")]


async def test_empty_upsert_and_delete_make_no_requests() -> None:
    server = _Server()
    store = _store(server)

    await store.upsert(ids=[], embeddings=[], documents=[], metadatas=[])
    await store.delete([])

    assert server.requests == []
