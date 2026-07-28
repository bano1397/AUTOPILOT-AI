"""Integration tests for the MCP server endpoint (AutoPilot as an MCP provider).

External MCP clients speak JSON-RPC to ``POST /api/v1/tools/mcp``. These tests
drive that endpoint the way such a client would.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from app.domain.interfaces.search import SearchResult
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.platform.registry import discover_plugins, tool_registry
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore

MCP_PATH = "/api/v1/tools/mcp"


class FakeSearch:
    name = "fake"

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        return [SearchResult(title="Hit", url="https://example.com", snippet="s")]

    async def fetch(self, url: str) -> str:  # pragma: no cover - unused
        return ""


@pytest.fixture(autouse=True)
def _plugins_loaded() -> None:
    if "vector_search" not in tool_registry:
        discover_plugins()


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.search = FakeSearch()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _rpc(api: AsyncClient, method: str, params: dict[str, Any] | None = None) -> dict:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    response = await api.post(MCP_PATH, json=payload)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_initialize_returns_server_info(api: AsyncClient) -> None:
    body = await _rpc(api, "initialize")

    assert body["jsonrpc"] == "2.0"
    assert body["result"]["serverInfo"]["name"] == "autopilot-ai"
    assert "tools" in body["result"]["capabilities"]


async def test_tools_list_advertises_native_tools_with_schemas(api: AsyncClient) -> None:
    body = await _rpc(api, "tools/list")

    tools = {tool["name"]: tool for tool in body["result"]["tools"]}
    assert {"vector_search", "web_search", "create_task"} <= set(tools)
    assert "query" in tools["web_search"]["inputSchema"]["properties"]


async def test_tools_call_executes_and_returns_structured_content(
    api: AsyncClient,
) -> None:
    body = await _rpc(
        api, "tools/call", {"name": "create_task", "arguments": {"title": "Via MCP"}}
    )

    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["title"] == "Via MCP"
    # Text content mirrors the structured payload for text-only clients.
    assert "Via MCP" in result["content"][0]["text"]

    # The task really exists in the workspace.
    listing = await api.get("/api/v1/tasks")
    assert [task["title"] for task in listing.json()["data"]] == ["Via MCP"]


async def test_unknown_tool_is_a_jsonrpc_method_error(api: AsyncClient) -> None:
    body = await _rpc(api, "tools/call", {"name": "nope", "arguments": {}})

    assert body["error"]["code"] == -32601


async def test_invalid_arguments_are_a_jsonrpc_param_error(api: AsyncClient) -> None:
    body = await _rpc(api, "tools/call", {"name": "web_search", "arguments": {}})

    assert body["error"]["code"] == -32602


async def test_unknown_method_is_rejected(api: AsyncClient) -> None:
    body = await _rpc(api, "resources/list")

    assert body["error"]["code"] == -32601


async def test_mcp_origin_tools_are_not_re_exposed(api: AsyncClient) -> None:
    """The server must not become a proxy hop back to another MCP server."""
    from app.mcp.adapter import build_adapter
    from app.mcp.protocol import McpToolDescriptor

    class _Peer:
        name = "peer"

        async def list_tools(self) -> list[McpToolDescriptor]:  # pragma: no cover
            return []

        async def call_tool(self, tool: str, arguments: dict) -> dict:  # pragma: no cover
            return {}

    adapter = build_adapter(_Peer(), McpToolDescriptor("remote_thing", "", {}), name_prefix="mcp__")
    tool_registry.register(adapter.meta.name, adapter)
    try:
        body = await _rpc(api, "tools/list")
        assert "mcp__remote_thing" not in {t["name"] for t in body["result"]["tools"]}
    finally:
        tool_registry._entries.pop(adapter.meta.name, None)
