"""Wire-format tests for the Ollama LLM provider (MockTransport)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.infrastructure.llm import OllamaLLMProvider

_MESSAGES = [
    ChatMessage(role=ChatRole.SYSTEM, content="You are helpful."),
    ChatMessage(role=ChatRole.USER, content="Hello!"),
]


def _provider(handler: Any) -> OllamaLLMProvider:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama.test"
    )
    return OllamaLLMProvider(base_url="http://ollama.test", model="llama3", client=client)


async def test_chat_sends_model_messages_and_maps_usage() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "model": "llama3",
                "message": {"role": "assistant", "content": "Hi there!"},
                "prompt_eval_count": 12,
                "eval_count": 4,
                "total_duration": 2_500_000_000,  # 2.5s in ns
            },
        )

    result = await _provider(handler).chat(_MESSAGES)

    assert requests == [
        {
            "model": "llama3",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ],
            "stream": False,
        }
    ]
    assert result.content == "Hi there!"
    assert result.model == "llama3"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 4
    assert result.duration_ms == 2500


async def test_chat_passes_generation_options() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["options"] == {"temperature": 0.1, "num_predict": 64}
        return httpx.Response(200, json={"message": {"content": "ok"}})

    result = await _provider(handler).chat(_MESSAGES, temperature=0.1, max_tokens=64)
    assert result.content == "ok"


async def test_missing_usage_fields_default_to_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "ok"}})

    result = await _provider(handler).chat(_MESSAGES)
    assert (result.prompt_tokens, result.completion_tokens, result.duration_ms) == (0, 0, 0)
    assert result.model == "llama3"  # falls back to the configured model


async def test_http_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'llama3' not found"})

    with pytest.raises(httpx.HTTPStatusError):
        await _provider(handler).chat(_MESSAGES)


async def test_malformed_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"done": True})  # no message

    with pytest.raises(ValueError, match="malformed"):
        await _provider(handler).chat(_MESSAGES)
