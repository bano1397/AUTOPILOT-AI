"""Unit tests for the MCP layer: protocol parsing, adapter, and discovery."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.mcp.adapter import build_adapter, build_input_model
from app.mcp.client import HttpMCPClient
from app.mcp.protocol import (
    McpProtocolError,
    McpToolDescriptor,
    parse_call_result,
    parse_tools,
    request,
    result_of,
)
from app.mcp.registry import (
    NAME_PREFIX,
    McpServerDefinition,
    discover_mcp_tools,
    parse_server_definitions,
    register_server_tools,
)
from app.platform.registry import tool_registry


class FakeMcpClient:
    """In-memory MCP peer."""

    def __init__(self, tools: list[McpToolDescriptor], result: dict[str, Any] | None = None):
        self.name = "fake"
        self._tools = tools
        self._result = result or {"ok": True}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[McpToolDescriptor]:
        return self._tools

    async def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, arguments))
        return self._result


DESCRIPTOR = McpToolDescriptor(
    name="read_file",
    description="Read a file from disk",
    input_schema={
        "properties": {
            "path": {"type": "string", "description": "Absolute path"},
            "limit": {"type": "integer"},
        },
        "required": ["path"],
    },
)


# --- protocol ---------------------------------------------------------------


def test_request_envelope() -> None:
    assert request("tools/list", {"a": 1}, id=7) == {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/list",
        "params": {"a": 1},
    }


def test_result_of_raises_on_jsonrpc_error() -> None:
    with pytest.raises(McpProtocolError, match="MCP error -32601"):
        result_of({"error": {"code": -32601, "message": "nope"}})


def test_result_of_requires_a_result_object() -> None:
    with pytest.raises(McpProtocolError, match="no result object"):
        result_of({"id": 1})


def test_parse_tools_skips_unnamed_entries() -> None:
    tools = parse_tools(
        {
            "tools": [
                {"name": "good", "description": "d", "inputSchema": {"properties": {}}},
                {"description": "no name"},
                "not a dict",
            ]
        }
    )

    assert [tool.name for tool in tools] == ["good"]


def test_parse_tools_accepts_both_schema_spellings() -> None:
    camel = parse_tools({"tools": [{"name": "a", "inputSchema": {"x": 1}}]})
    snake = parse_tools({"tools": [{"name": "a", "input_schema": {"x": 1}}]})

    assert camel[0].input_schema == snake[0].input_schema == {"x": 1}


def test_parse_call_result_prefers_structured_content() -> None:
    assert parse_call_result({"structuredContent": {"a": 1}}) == {"a": 1}


def test_parse_call_result_decodes_json_text() -> None:
    payload = {"content": [{"type": "text", "text": json.dumps({"b": 2})}]}

    assert parse_call_result(payload) == {"b": 2}


def test_parse_call_result_wraps_plain_text() -> None:
    payload = {"content": [{"type": "text", "text": "hello"}]}

    assert parse_call_result(payload) == {"text": "hello"}


def test_parse_call_result_raises_on_tool_error() -> None:
    payload = {"isError": True, "content": [{"type": "text", "text": "boom"}]}

    with pytest.raises(McpProtocolError, match="boom"):
        parse_call_result(payload)


# --- http client ------------------------------------------------------------


async def test_http_client_initializes_then_lists() -> None:
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body["method"])
        if body["method"] == "initialize":
            return httpx.Response(200, json={"id": 1, "result": {"capabilities": {}}})
        return httpx.Response(
            200,
            json={"id": 1, "result": {"tools": [{"name": "t", "inputSchema": {}}]}},
        )

    client = HttpMCPClient(
        "peer",
        "https://peer/mcp",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    tools = await client.list_tools()

    assert seen == ["initialize", "tools/list"]
    assert [tool.name for tool in tools] == ["t"]


async def test_http_client_surfaces_transport_failure() -> None:
    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = HttpMCPClient(
        "peer",
        "https://peer/mcp",
        client=httpx.AsyncClient(transport=httpx.MockTransport(boom)),
    )

    with pytest.raises(McpProtocolError, match="unreachable"):
        await client.list_tools()


# --- adapter ----------------------------------------------------------------


def test_input_model_is_built_from_remote_schema() -> None:
    model = build_input_model(DESCRIPTOR)
    fields = model.model_fields

    assert set(fields) == {"path", "limit"}
    assert fields["path"].is_required()
    assert not fields["limit"].is_required()


def test_input_model_validates_remote_requirements() -> None:
    model = build_input_model(DESCRIPTOR)

    assert model.model_validate({"path": "/etc/hosts"}).path == "/etc/hosts"  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        model.model_validate({})


def test_schemaless_tool_accepts_empty_arguments() -> None:
    model = build_input_model(McpToolDescriptor("ping", "", {}))

    assert model.model_validate({}) is not None


def test_adapter_meta_marks_origin_mcp() -> None:
    client = FakeMcpClient([DESCRIPTOR])
    adapter = build_adapter(client, DESCRIPTOR, name_prefix=NAME_PREFIX)

    assert adapter.meta.name == "mcp__read_file"
    assert adapter.meta.origin == "mcp"
    assert adapter.meta.category == "mcp"
    assert adapter.meta.dependencies == ("MCPServer:fake",)


async def test_adapter_calls_remote_tool_and_drops_unset_arguments() -> None:
    client = FakeMcpClient([DESCRIPTOR], result={"content": "abc"})
    adapter = build_adapter(client, DESCRIPTOR)
    args = build_input_model(DESCRIPTOR).model_validate({"path": "/tmp/x"})

    output = await adapter(context=None).run(args)

    # `limit` was never supplied, so it must not be sent as null.
    assert client.calls == [("read_file", {"path": "/tmp/x"})]
    assert output.result == {"content": "abc"}


# --- configuration ----------------------------------------------------------


def test_parse_definitions_reads_both_transports() -> None:
    raw = json.dumps(
        [
            {"name": "http-one", "transport": "http", "url": "https://h/mcp"},
            {"name": "cli", "transport": "stdio", "command": "srv", "args": ["/data"]},
        ]
    )

    definitions = parse_server_definitions(raw)

    assert [d.name for d in definitions] == ["http-one", "cli"]
    assert definitions[1].args == ("/data",)


@pytest.mark.parametrize("raw", ["", None, "not json", '{"not": "a list"}'])
def test_malformed_config_yields_no_servers(raw: str | None) -> None:
    assert parse_server_definitions(raw) == []


def test_entries_without_a_name_are_skipped() -> None:
    assert parse_server_definitions(json.dumps([{"transport": "http"}])) == []


def test_definition_requires_transport_specific_fields() -> None:
    with pytest.raises(ValueError, match="requires a url"):
        McpServerDefinition(name="a", transport="http").build_client()
    with pytest.raises(ValueError, match="requires a command"):
        McpServerDefinition(name="a", transport="stdio").build_client()
    with pytest.raises(ValueError, match="unknown transport"):
        McpServerDefinition(name="a", transport="carrier-pigeon").build_client()


# --- discovery --------------------------------------------------------------


async def test_registered_mcp_tools_join_the_native_registry() -> None:
    definition = McpServerDefinition(name="fake", transport="http", url="https://x")
    client = FakeMcpClient([DESCRIPTOR])
    try:
        names = await register_server_tools(definition, client=client)

        assert names == ["mcp__read_file"]
        # Callable through exactly the same registry agents use.
        assert tool_registry.get("mcp__read_file").meta.origin == "mcp"
    finally:
        tool_registry._entries.pop("mcp__read_file", None)


async def test_unreachable_server_is_isolated_not_fatal() -> None:
    raw = json.dumps([{"name": "dead", "transport": "http", "url": "http://127.0.0.1:1"}])

    summary = await discover_mcp_tools(raw)

    assert summary["servers"] == 0
    assert summary["failed"] == ["dead"]


async def test_no_configuration_is_a_no_op() -> None:
    assert await discover_mcp_tools(None) == {"servers": 0, "tools": 0, "failed": []}
