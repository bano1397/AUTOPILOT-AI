"""Wire-format tests for streamed LLM replies.

Both cloud dialects are covered against ``httpx.MockTransport``: Groq speaks
OpenAI-style Server-Sent Events, Ollama speaks newline-delimited JSON. The
contract they share is what these pin — deltas in order, then exactly one
terminal chunk carrying the assembled text and usage.
"""

from __future__ import annotations

import httpx
import pytest
from app.domain.interfaces.llm import (
    ChatMessage,
    ChatRole,
    StreamChunk,
    StreamingLLMProvider,
)
from app.infrastructure.llm import (
    GroqLLMProvider,
    OllamaLLMProvider,
    StubLLMProvider,
)

MESSAGES = [ChatMessage(role=ChatRole.USER, content="hello")]


def _sse(*frames: str) -> str:
    return "".join(f"data: {frame}\n\n" for frame in frames) + "data: [DONE]\n\n"


def _groq(handler: object) -> GroqLLMProvider:
    return GroqLLMProvider(
        api_key="k",
        model="llama-3.1-8b-instant",
        client=httpx.AsyncClient(
            base_url="http://groq.test/v1",
            transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        ),
    )


def _ollama(handler: object) -> OllamaLLMProvider:
    return OllamaLLMProvider(
        base_url="http://ollama.test",
        model="llama3",
        client=httpx.AsyncClient(
            base_url="http://ollama.test",
            transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        ),
    )


async def _drain(provider: object) -> tuple[list[str], StreamChunk]:
    deltas: list[str] = []
    final: StreamChunk | None = None
    async for chunk in provider.chat_stream(MESSAGES):  # type: ignore[attr-defined]
        if chunk.done:
            final = chunk
        elif chunk.delta:
            deltas.append(chunk.delta)
    assert final is not None, "the stream must end with a terminal chunk"
    return deltas, final


class TestCapabilityDetection:
    def test_all_providers_advertise_streaming(self) -> None:
        """Callers branch on this, so the runtime check must actually hold."""
        assert isinstance(StubLLMProvider(), StreamingLLMProvider)
        assert isinstance(_groq(lambda r: httpx.Response(200)), StreamingLLMProvider)
        assert isinstance(_ollama(lambda r: httpx.Response(200)), StreamingLLMProvider)


class TestGroqStreaming:
    async def test_deltas_arrive_in_order_and_assemble(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=_sse(
                    '{"model":"m","choices":[{"delta":{"content":"Hello"}}]}',
                    '{"model":"m","choices":[{"delta":{"content":", "}}]}',
                    '{"model":"m","choices":[{"delta":{"content":"world"}}]}',
                    '{"model":"m","choices":[],"usage":'
                    '{"prompt_tokens":7,"completion_tokens":3}}',
                ),
            )

        deltas, final = await _drain(_groq(handler))

        assert deltas == ["Hello", ", ", "world"]
        assert final.result is not None
        assert final.result.content == "Hello, world"

    async def test_the_terminal_chunk_carries_usage(self) -> None:
        """Without it a streamed call would be audited as costing zero tokens."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=_sse(
                    '{"model":"m","choices":[{"delta":{"content":"hi"}}]}',
                    '{"model":"m","choices":[],"usage":'
                    '{"prompt_tokens":11,"completion_tokens":2}}',
                ),
            )

        _, final = await _drain(_groq(handler))

        assert final.result is not None
        assert final.result.prompt_tokens == 11
        assert final.result.completion_tokens == 2
        assert final.result.model == "m"

    async def test_requests_usage_in_the_stream(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured.update(json.loads(request.content))
            return httpx.Response(200, text=_sse())

        await _drain(_groq(handler))

        assert captured["stream"] is True
        assert captured["stream_options"] == {"include_usage": True}

    async def test_a_malformed_frame_does_not_abort_the_reply(self) -> None:
        """A part-delivered answer must survive one bad line."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=(
                    'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
                    "data: {not json\n\n"
                    'data: {"choices":[{"delta":{"content":"b"}}]}\n\n'
                    "data: [DONE]\n\n"
                ),
            )

        deltas, final = await _drain(_groq(handler))

        assert deltas == ["a", "b"]
        assert final.result is not None
        assert final.result.content == "ab"

    async def test_an_http_error_propagates(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "slow down"})

        with pytest.raises(httpx.HTTPStatusError):
            await _drain(_groq(handler))


class TestOllamaStreaming:
    async def test_ndjson_deltas_assemble_with_usage(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=(
                    '{"model":"llama3","message":{"content":"Hi"}}\n'
                    '{"model":"llama3","message":{"content":" there"}}\n'
                    '{"model":"llama3","done":true,"prompt_eval_count":5,'
                    '"eval_count":2,"total_duration":3000000}\n'
                ),
            )

        deltas, final = await _drain(_ollama(handler))

        assert deltas == ["Hi", " there"]
        assert final.result is not None
        assert final.result.content == "Hi there"
        assert final.result.prompt_tokens == 5
        assert final.result.completion_tokens == 2
        assert final.result.duration_ms == 3

    async def test_blank_and_malformed_lines_are_skipped(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text=(
                    '{"message":{"content":"x"}}\n'
                    "\n"
                    "oops\n"
                    '{"done":true,"eval_count":1}\n'
                ),
            )

        deltas, final = await _drain(_ollama(handler))

        assert deltas == ["x"]
        assert final.result is not None


class TestStubStreaming:
    async def test_streams_word_by_word_and_matches_the_one_shot_reply(self) -> None:
        """The streamed and non-streamed paths must not disagree about the
        answer, or the e2e suite would be testing two different systems."""
        stub = StubLLMProvider()

        deltas, final = await _drain(stub)
        one_shot = await stub.chat(MESSAGES)

        assert len(deltas) > 1, "should arrive in pieces, not one lump"
        assert "".join(deltas) == one_shot.content
        assert final.result is not None
        assert final.result.content == one_shot.content

    async def test_reports_usage(self) -> None:
        _, final = await _drain(StubLLMProvider())

        assert final.result is not None
        assert final.result.completion_tokens > 0
