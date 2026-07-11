"""Dependency providers for the RAG feature."""

from __future__ import annotations

from fastapi import Depends

from app.core.dependencies import (
    get_ai_recorder,
    get_embeddings,
    get_llm,
    get_vector_store,
)
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.rag.service import RagAskService, RagService
from app.platform.observability.recorder import AiExecutionRecorder


def get_rag_service(
    embeddings: EmbeddingProvider = Depends(get_embeddings),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
) -> RagService:
    return RagService(embeddings, vector_store)


def get_rag_ask_service(
    retrieval: RagService = Depends(get_rag_service),
    llm: LLMProvider = Depends(get_llm),
    recorder: AiExecutionRecorder = Depends(get_ai_recorder),
) -> RagAskService:
    return RagAskService(retrieval, llm, recorder)
