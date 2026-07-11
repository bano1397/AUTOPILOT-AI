"""Opt-in round-trip tests against real Ollama and ChromaDB servers.

Skipped unless ``AUTOPILOT_EXTERNAL_TESTS=1`` (they need the services from
``docker compose up`` — Ollama with the embedding model pulled, and ChromaDB).
CI and the default local run never require them.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.infrastructure.embeddings import OllamaEmbeddingProvider
from app.infrastructure.llm import OllamaLLMProvider
from app.infrastructure.vectorstore import ChromaVectorStore

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOPILOT_EXTERNAL_TESTS") != "1",
    reason="external services (set AUTOPILOT_EXTERNAL_TESTS=1 with Ollama+Chroma running)",
)


async def test_ollama_embedding_round_trip() -> None:
    settings = get_settings()
    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url, model=settings.embedding_model
    )

    vectors = await provider.embed(["hello world", "goodbye world"])

    assert len(vectors) == 2
    assert len(vectors[0]) > 100  # real model dimensionality
    assert vectors[0] != vectors[1]


async def test_ollama_chat_round_trip() -> None:
    settings = get_settings()
    provider = OllamaLLMProvider(
        base_url=settings.ollama_base_url, model=settings.llm_model
    )

    result = await provider.chat(
        [
            ChatMessage(
                role=ChatRole.USER,
                content="Reply with exactly the single word: pong",
            )
        ],
        temperature=0.0,
    )

    assert "pong" in result.content.lower()
    assert result.completion_tokens > 0
    assert result.duration_ms > 0


async def test_chroma_upsert_query_delete_round_trip() -> None:
    settings = get_settings()
    store = ChromaVectorStore(
        base_url=settings.chroma_url, collection=f"test_{uuid4().hex[:8]}"
    )
    ids = [uuid4().hex, uuid4().hex]

    await store.upsert(
        ids=ids,
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        documents=["first", "second"],
        metadatas=[{"document_id": "d1"}, {"document_id": "d2"}],
    )
    matches = await store.query([1.0, 0.0, 0.0], top_k=1)

    assert matches
    assert matches[0].id == ids[0]
    assert matches[0].text == "first"
    assert matches[0].metadata["document_id"] == "d1"

    await store.delete(ids)
    assert await store.query([1.0, 0.0, 0.0], top_k=1) == []
