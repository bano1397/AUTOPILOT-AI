"""Ollama implementation of :class:`LLMProvider`.

Calls the local Ollama server's ``/api/chat`` endpoint (non-streaming) over
plain HTTP. The client is injectable so tests can verify the exact wire format
with ``httpx.MockTransport``. Generation is slow on CPU, hence the generous
default timeout.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.interfaces.llm import ChatMessage, LLMResult
from app.platform.registry import register_provider

_NS_PER_MS = 1_000_000


@register_provider(kind="llm", name="ollama")
class OllamaLLMProvider:
    """Chat completion via a local Ollama instance."""

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

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
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
            "stream": False,
        }
        if options:
            body["options"] = options

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
