"""Groq implementation of :class:`LLMProvider`.

Groq serves open models (Llama, etc.) behind an OpenAI-compatible
``/openai/v1/chat/completions`` endpoint over HTTPS, with a generous free tier —
the cloud counterpart to the local Ollama provider. A thin httpx client keeps the
wire format unit-testable with ``httpx.MockTransport``; Groq does not return a
generation duration, so it is measured client-side.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.domain.interfaces.llm import ChatMessage, LLMResult
from app.platform.registry import register_provider

_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


@register_provider(kind="llm", name="groq")
class GroqLLMProvider:
    """Chat completion via Groq's OpenAI-compatible API."""

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

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

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
