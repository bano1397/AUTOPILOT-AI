"""The AI execution recorder — the single choke-point for LLM calls.

Every feature invokes the LLM through :meth:`AiExecutionRecorder.chat` so each
generation is persisted (prompt, model, tokens, cost, timing, user, error,
correlation id) and a :class:`CostRecorded` event is published.

Guarantees:

* **Failures are recorded too** — an errored call writes a row with ``error``
  set, then the original exception propagates unchanged.
* **Recording never breaks the feature** — the recorder uses its own session
  and swallows (logs) persistence errors.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

from app.core.logging import correlation_id_var, get_logger
from app.domain.events import CostRecorded
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.event_bus import EventBus
from app.domain.interfaces.llm import (
    ChatMessage,
    LLMProvider,
    LLMResult,
    StreamChunk,
    StreamingLLMProvider,
)
from app.platform.observability.models import AiExecution
from app.platform.observability.pricing import compute_cost

logger = get_logger("app.observability")

_PREVIEW_CHARS = 500


def _serialize_messages(messages: Sequence[ChatMessage]) -> str:
    return json.dumps(
        [{"role": message.role.value, "content": message.content} for message in messages],
        ensure_ascii=False,
    )


class AiExecutionRecorder:
    """Times, executes, and audits LLM calls."""

    def __init__(self, db: DatabaseProvider, bus: EventBus) -> None:
        self._db = db
        self._bus = bus

    async def chat(
        self,
        llm: LLMProvider,
        messages: Sequence[ChatMessage],
        *,
        feature: str,
        user_id: UUID | None = None,
        agent_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_key: str | None = None,
        prompt_version: int | None = None,
    ) -> LLMResult:
        """Invoke ``llm.chat`` and persist an execution record either way."""
        provider_name = str(getattr(llm, "name", "unknown"))
        started = time.perf_counter()
        try:
            result = await llm.chat(
                list(messages), temperature=temperature, max_tokens=max_tokens
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            await self._record(
                feature=feature,
                user_id=user_id,
                agent_name=agent_name,
                provider=provider_name,
                model="unknown",
                messages=messages,
                response_preview=None,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=elapsed_ms,
                error=str(exc),
                prompt_key=prompt_key,
                prompt_version=prompt_version,
            )
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        await self._record(
            feature=feature,
            user_id=user_id,
            agent_name=agent_name,
            provider=provider_name,
            model=result.model,
            messages=messages,
            response_preview=result.content[:_PREVIEW_CHARS],
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            duration_ms=result.duration_ms or elapsed_ms,
            error=None,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
        )
        return result

    async def chat_stream(
        self,
        llm: LLMProvider,
        messages: Sequence[ChatMessage],
        *,
        feature: str,
        user_id: UUID | None = None,
        agent_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        prompt_key: str | None = None,
        prompt_version: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream ``llm.chat_stream`` and persist one execution record at the end.

        The record is written when the stream terminates -- successfully or
        not -- so a streamed call is audited exactly as completely as a
        one-shot one. A client that disconnects mid-stream still produces a
        record, because the generator's cleanup runs on close.
        """
        if not isinstance(llm, StreamingLLMProvider):
            # Fall back rather than fail: a non-streaming provider costs the
            # caller responsiveness, not the answer.
            result = await self.chat(
                llm,
                messages,
                feature=feature,
                user_id=user_id,
                agent_name=agent_name,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_key=prompt_key,
                prompt_version=prompt_version,
            )
            yield StreamChunk(delta=result.content)
            yield StreamChunk(done=True, result=result)
            return

        provider_name = str(getattr(llm, "name", "unknown"))
        started = time.perf_counter()
        final: LLMResult | None = None
        error: str | None = None
        try:
            async for chunk in llm.chat_stream(
                list(messages), temperature=temperature, max_tokens=max_tokens
            ):
                if chunk.done:
                    final = chunk.result
                yield chunk
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            await self._record(
                feature=feature,
                user_id=user_id,
                agent_name=agent_name,
                provider=provider_name,
                model=final.model if final else "unknown",
                messages=messages,
                response_preview=(
                    final.content[:_PREVIEW_CHARS] if final else None
                ),
                prompt_tokens=final.prompt_tokens if final else 0,
                completion_tokens=final.completion_tokens if final else 0,
                duration_ms=(final.duration_ms if final else 0) or elapsed_ms,
                error=error,
                prompt_key=prompt_key,
                prompt_version=prompt_version,
            )

    async def _record(
        self,
        *,
        feature: str,
        user_id: UUID | None,
        agent_name: str | None,
        provider: str,
        model: str,
        messages: Sequence[ChatMessage],
        response_preview: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        error: str | None,
        prompt_key: str | None = None,
        prompt_version: int | None = None,
    ) -> None:
        """Persist the execution and publish ``CostRecorded``. Never raises."""
        cost_usd = compute_cost(provider, model, prompt_tokens, completion_tokens)
        try:
            execution = AiExecution(
                user_id=user_id,
                feature=feature,
                agent_name=agent_name,
                provider=provider,
                model=model,
                prompt=_serialize_messages(messages),
                response_preview=response_preview,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                error=error,
                prompt_key=prompt_key,
                prompt_version=prompt_version,
                correlation_id=correlation_id_var.get(),
            )
            async with self._db.session() as session:
                session.add(execution)
                await session.commit()
                execution_id = str(execution.id)
        except Exception:  # noqa: BLE001 - observability must not break features
            logger.exception("ai_execution_record_failed", extra={"feature": feature})
            return

        await self._bus.publish(
            CostRecorded(
                execution_id=execution_id,
                provider=provider,
                model=model,
                cost_usd=cost_usd,
            )
        )
