"""Wire-format tests for the Groq LLM provider (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.infrastructure.llm import GroqLLMProvider

_MESSAGES = [
    ChatMessage(role=ChatRole.SYSTEM, content="You are helpful."),
    ChatMessage(role=ChatRole.USER, content="Hello!"),
]


def _provider(handler: Any) -> GroqLLMProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://groq.test/openai/v1"
    )
    return GroqLLMProvider(api_key="sk-test", model="llama-3.1-8b-instant", client=client)


async def test_chat_sends_openai_format_and_maps_usage() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "llama-3.1-8b-instant",
                "choices": [{"message": {"role": "assistant", "content": "Hi there!"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    result = await _provider(handler).chat(_MESSAGES, temperature=0.2, max_tokens=64)

    assert requests[0]["model"] == "llama-3.1-8b-instant"
    assert requests[0]["messages"][0] == {"role": "system", "content": "You are helpful."}
    assert requests[0]["temperature"] == 0.2
    assert requests[0]["max_tokens"] == 64
    assert result.content == "Hi there!"
    assert result.model == "llama-3.1-8b-instant"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 4
    assert result.duration_ms >= 0


async def test_missing_usage_defaults_to_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    result = await _provider(handler).chat(_MESSAGES)
    assert (result.prompt_tokens, result.completion_tokens) == (0, 0)
    assert result.model == "llama-3.1-8b-instant"


async def test_http_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    with pytest.raises(httpx.HTTPStatusError):
        await _provider(handler).chat(_MESSAGES)


async def test_malformed_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(ValueError, match="no choices"):
        await _provider(handler).chat(_MESSAGES)


def test_empty_api_key_rejected() -> None:
    with pytest.raises(ValueError, match="API key"):
        GroqLLMProvider(api_key="", model="x")
