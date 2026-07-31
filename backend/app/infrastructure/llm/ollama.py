"""Ollama implementation of :class:`LLMProvider`.

Calls the local Ollama server's ``/api/chat`` endpoint over plain HTTP, in both
one-shot and streaming modes. The client is injectable so tests can verify the exact wire format
with ``httpx.MockTransport``. Generation is slow on CPU, hence the generous
default timeout.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.domain.interfaces.llm import ChatMessage, LLMResult, StreamChunk
from app.platform.registry import register_provider

_NS_PER_MS = 1_000_000


@register_provider(kind="llm", name="ollama")
class OllamaLLMProvider:
    """Chat completion via a local Ollama instance."""

    # Read by AiExecutionRecorder for the provider column.
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._model = model

    def _body(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "stream": stream,
        }
        if options:
            body["options"] = options
        return body

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        body = self._body(
            messages, temperature=temperature, max_tokens=max_tokens, stream=False
        )

        response = await self._client.post("/api/chat", json=body)
        response.raise_for_status()
        payload = response.json()

        message = payload.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError(f"Ollama returned a malformed chat response: {payload!r:.200}")

        return LLMResult(
            content=str(message["content"]),
            model=str(payload.get("model", self._model)),
            prompt_tokens=int(payload.get("prompt_eval_count", 0)),
            completion_tokens=int(payload.get("eval_count", 0)),
            duration_ms=int(payload.get("total_duration", 0)) // _NS_PER_MS,
        )

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the reply as newline-delimited JSON.

        Ollama emits one JSON object per line rather than SSE, with the final
        object carrying ``done: true`` plus the usage counters.
        """
        body = self._body(
            messages, temperature=temperature, max_tokens=max_tokens, stream=True
        )

        parts: list[str] = []
        model = self._model
        prompt_tokens = 0
        completion_tokens = 0
        duration_ms = 0

        async with self._client.stream("POST", "/api/chat", json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    # Never abort a part-delivered reply over one bad line.
                    continue

                model = str(payload.get("model", model))
                message = payload.get("message")
                if isinstance(message, dict):
                    delta = message.get("content")
                    if delta:
                        parts.append(str(delta))
                        yield StreamChunk(delta=str(delta))

                if payload.get("done"):
                    prompt_tokens = int(payload.get("prompt_eval_count", 0))
                    completion_tokens = int(payload.get("eval_count", 0))
                    duration_ms = int(payload.get("total_duration", 0)) // _NS_PER_MS

        yield StreamChunk(
            done=True,
            result=LLMResult(
                content="".join(parts),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
            ),
        )
