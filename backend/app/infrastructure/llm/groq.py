"""Groq implementation of :class:`LLMProvider`.

Groq serves open models (Llama, etc.) behind an OpenAI-compatible
``/openai/v1/chat/completions`` endpoint over HTTPS, with a generous free tier —
the cloud counterpart to the local Ollama provider. A thin httpx client keeps the
wire format unit-testable with ``httpx.MockTransport``; Groq does not return a
generation duration, so it is measured client-side.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.domain.interfaces.llm import ChatMessage, LLMResult, StreamChunk
from app.platform.registry import register_provider

_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


@register_provider(kind="llm", name="groq")
class GroqLLMProvider:
    """Chat completion via Groq's OpenAI-compatible API."""

    # Read by AiExecutionRecorder for the provider column; without it every
    # Groq call was audited as "unknown" and the cost dashboard could not
    # attribute spend.
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("Groq API key is required")
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._model = model

    def _body(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "stream": stream,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            # Without this the terminal SSE frame carries no usage block and
            # the audit record would report zero tokens for every streamed call.
            body["stream_options"] = {"include_usage": True}
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

        started = time.perf_counter()
        response = await self._client.post("/chat/completions", json=body)
        response.raise_for_status()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        payload = response.json()

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"Groq returned no choices: {payload!r:.200}")
        message = choices[0].get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError(f"Groq returned a malformed chat response: {payload!r:.200}")

        usage = payload.get("usage") or {}
        return LLMResult(
            content=str(message["content"]),
            model=str(payload.get("model", self._model)),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            duration_ms=elapsed_ms,
        )

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the reply over Server-Sent Events.

        Groq speaks the OpenAI SSE dialect: ``data: {json}`` lines, terminated
        by ``data: [DONE]``. Deltas are accumulated here so the terminal chunk
        can carry the whole message — callers should never have to re-join the
        pieces to know what was said.
        """
        body = self._body(
            messages, temperature=temperature, max_tokens=max_tokens, stream=True
        )

        started = time.perf_counter()
        parts: list[str] = []
        model = self._model
        prompt_tokens = 0
        completion_tokens = 0

        async with self._client.stream(
            "POST", "/chat/completions", json=body
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    # A malformed frame must not abort a reply that is already
                    # part-delivered; skip it and keep reading.
                    continue

                usage = payload.get("usage")
                if isinstance(usage, dict):
                    prompt_tokens = int(usage.get("prompt_tokens", prompt_tokens))
                    completion_tokens = int(
                        usage.get("completion_tokens", completion_tokens)
                    )
                model = str(payload.get("model", model))

                for choice in payload.get("choices") or []:
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        parts.append(str(delta))
                        yield StreamChunk(delta=str(delta))

        yield StreamChunk(
            done=True,
            result=LLMResult(
                content="".join(parts),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=int((time.perf_counter() - started) * 1000),
            ),
        )
