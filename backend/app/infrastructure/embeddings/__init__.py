"""Embedding provider implementations."""

from app.infrastructure.embeddings.jina import JinaEmbeddingProvider
from app.infrastructure.embeddings.ollama import OllamaEmbeddingProvider

__all__ = ["JinaEmbeddingProvider", "OllamaEmbeddingProvider"]
