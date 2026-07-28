"""Integration tests for the tool marketplace (listing + invocation).

Covers the registry seam: tools are discovered by the plugin scanner, described
from their own ``ToolMeta``, and invoked through validated input models.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.domain.interfaces.search import SearchResult
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.platform.registry import discover_plugins, tool_registry
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore


class FakeSearch:
    """Deterministic SearchProvider stand-in."""

    name = "fake"

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results if results is not None else []
        self.queries: list[str] = []

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return self.results[:max_results]

    async def fetch(self, url: str) -> str:  # pragma: no cover - unused here
        return ""


@pytest.fixture(autouse=True)
def _plugins_loaded() -> None:
    # The lifespan (which normally scans) doesn't run under ASGITransport.
    if "vector_search" not in tool_registry:
        discover_plugins()


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch(
        [
            SearchResult(
                title="LangGraph docs", url="https://example.com/lg", snippet="graphs"
            ),
            SearchResult(
                title="RAG primer", url="https://example.com/rag", snippet="retrieval"
            ),
        ]
    )


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, fake_search: FakeSearch
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.search = fake_search
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_listing_describes_registered_tools(api: AsyncClient) -> None:
    response = await api.get("/api/v1/tools")

    assert response.status_code == 200, response.text
    tools = {tool["name"]: tool for tool in response.json()["data"]}
    assert {"vector_search", "web_search", "create_task"} <= set(tools)

    search = tools["vector_search"]
    assert search["category"] == "retrieval"
    assert search["origin"] == "native"
    assert search["permissions"] == ["documents:read"]
    assert search["dependencies"] == ["EmbeddingProvider", "VectorStoreProvider"]
    # The JSON schema comes from the tool's own pydantic input model.
    assert "query" in search["input_schema"]["properties"]
    assert "matches" in search["output_schema"]["properties"]


async def test_listing_can_be_filtered_by_category(api: AsyncClient) -> None:
    response = await api.get("/api/v1/tools", params={"category": "productivity"})

    names = [tool["name"] for tool in response.json()["data"]]
    assert names == ["create_task"]


async def test_categories_endpoint(api: AsyncClient) -> None:
    response = await api.get("/api/v1/tools/categories")

    assert response.status_code == 200
    assert {"retrieval", "research", "productivity"} <= set(response.json()["data"])


async def test_invoke_web_search_returns_results(
    api: AsyncClient, fake_search: FakeSearch
) -> None:
    response = await api.post(
        "/api/v1/tools/web_search/invoke",
        json={"args": {"query": "langgraph", "max_results": 1}},
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["tool"] == "web_search"
    assert body["result"]["results"] == [
        {
            "title": "LangGraph docs",
            "url": "https://example.com/lg",
            "snippet": "graphs",
        }
    ]
    assert fake_search.queries == ["langgraph"]


async def test_invoke_create_task_persists_a_task(api: AsyncClient) -> None:
    invoked = await api.post(
        "/api/v1/tools/create_task/invoke",
        json={"args": {"title": "From a tool", "priority": "high"}},
    )

    assert invoked.status_code == 200, invoked.text
    assert invoked.json()["data"]["result"]["title"] == "From a tool"

    # Visible through the normal tasks API — same owner, same data.
    listing = await api.get("/api/v1/tasks")
    tasks = listing.json()["data"]
    assert [task["title"] for task in tasks] == ["From a tool"]
    assert tasks[0]["priority"] == "high"


async def test_invoke_vector_search_with_empty_index(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/tools/vector_search/invoke", json={"args": {"query": "anything"}}
    )

    assert response.status_code == 200
    assert response.json()["data"]["result"]["matches"] == []


async def test_unknown_tool_returns_404(api: AsyncClient) -> None:
    response = await api.post("/api/v1/tools/nope/invoke", json={"args": {}})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_invalid_arguments_return_422(api: AsyncClient) -> None:
    missing_required = await api.post(
        "/api/v1/tools/web_search/invoke", json={"args": {}}
    )
    out_of_range = await api.post(
        "/api/v1/tools/web_search/invoke",
        json={"args": {"query": "x", "max_results": 99}},
    )

    assert missing_required.status_code == 422
    assert out_of_range.status_code == 422
    assert missing_required.json()["error"]["code"] == "VALIDATION_ERROR"
