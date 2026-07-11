"""Wire-format tests for the Chroma vector-store provider (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
from app.infrastructure.vectorstore import ChromaVectorStore

_PREFIX = "/api/v2/tenants/default_tenant/databases/default_database"


class _Server:
    """Minimal scripted Chroma server recording every request."""

    def __init__(self, query_response: dict[str, Any] | None = None) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.query_response = query_response or {"ids": [[]]}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.requests.append((request.url.path, body))
        if request.url.path == f"{_PREFIX}/collections":
            return httpx.Response(200, json={"id": "col-123", "name": body["name"]})
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json=self.query_response)
        return httpx.Response(200, json={})


def _store(server: _Server) -> ChromaVectorStore:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(server), base_url="http://chroma.test"
    )
    return ChromaVectorStore(
        base_url="http://chroma.test", collection="autopilot_documents", client=client
    )


async def test_upsert_creates_collection_once_and_sends_payload() -> None:
    server = _Server()
    store = _store(server)

    await store.upsert(
        ids=["a"], embeddings=[[0.1]], documents=["text a"], metadatas=[{"k": 1}]
    )
    await store.upsert(
        ids=["b"], embeddings=[[0.2]], documents=["text b"], metadatas=[{"k": 2}]
    )

    paths = [path for path, _ in server.requests]
    assert paths.count(f"{_PREFIX}/collections") == 1  # get-or-create cached
    assert paths.count(f"{_PREFIX}/collections/col-123/upsert") == 2
    _, create_body = server.requests[0]
    assert create_body == {"name": "autopilot_documents", "get_or_create": True}
    _, upsert_body = server.requests[1]
    assert upsert_body == {
        "ids": ["a"],
        "embeddings": [[0.1]],
        "documents": ["text a"],
        "metadatas": [{"k": 1}],
    }


async def test_query_parses_matches() -> None:
    server = _Server(
        query_response={
            "ids": [["v1", "v2"]],
            "documents": [["first text", "second text"]],
            "metadatas": [[{"document_id": "d1"}, {"document_id": "d2"}]],
            "distances": [[0.12, 0.34]],
        }
    )
    store = _store(server)

    matches = await store.query([0.5, 0.5], top_k=2, where={"user_id": "u1"})

    assert [match.id for match in matches] == ["v1", "v2"]
    assert matches[0].text == "first text"
    assert matches[0].metadata == {"document_id": "d1"}
    assert matches[0].distance == 0.12
    _, query_body = server.requests[-1]
    assert query_body["query_embeddings"] == [[0.5, 0.5]]
    assert query_body["n_results"] == 2
    assert query_body["where"] == {"user_id": "u1"}
    assert set(query_body["include"]) == {"documents", "metadatas", "distances"}


async def test_delete_sends_ids() -> None:
    server = _Server()
    store = _store(server)

    await store.delete(["v1", "v2"])

    path, body = server.requests[-1]
    assert path == f"{_PREFIX}/collections/col-123/delete"
    assert body == {"ids": ["v1", "v2"]}


async def test_empty_upsert_and_delete_make_no_requests() -> None:
    server = _Server()
    store = _store(server)

    await store.upsert(ids=[], embeddings=[], documents=[], metadatas=[])
    await store.delete([])

    assert server.requests == []
