"""RAG use-cases: hybrid retrieval, reranking, compression, grounded answering.

The full query-side pipeline from blueprint §17:

    hybrid search (vector + BM25, RRF) → rerank → compress → generate → cite

Every stage after retrieval degrades to a no-op rather than an error, so a
missing reranker or an unavailable keyword index costs quality, never
availability.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import UpstreamServiceError
from app.core.logging import get_logger
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.rerank import RerankProvider
from app.domain.interfaces.vector_store import VectorStoreProvider
from app.features.documents.repository import DocumentRepository
from app.features.rag.prompts import build_ask_messages
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.rag.compression import CompressionResult, compress
from app.platform.rag.fusion import reciprocal_rank_fusion
from app.platform.rag.keyword import bm25_rank, query_terms
from app.platform.rag.types import RetrievalSource, RetrievedChunk

logger = get_logger("app.features.rag")

# Returned without invoking the LLM when retrieval finds nothing: honest,
# hallucination-free, and free of token cost.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant to your question in your indexed "
    "documents. Try uploading related documents or rephrasing the question."
)


class RagService:
    """Hybrid retrieval over indexed document chunks."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vector_store: VectorStoreProvider,
        documents: DocumentRepository | None = None,
        reranker: RerankProvider | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store
        # Without a repository there is no keyword half and retrieval stays
        # vector-only. Optional so unit contexts can build the service with no
        # database.
        self._documents = documents
        self._reranker = reranker

    async def query(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[RetrievedChunk]:
        """Return the owner's ``top_k`` most relevant chunks for ``query``.

        Owner isolation holds on both paths: the vector half via the ``user_id``
        metadata filter stamped at indexing time, the keyword half via a join to
        ``documents`` on ``user_id``.
        """
        settings = get_settings()
        # Retrieve deeper than we return, so fusion and reranking have material
        # to work with. A reranker handed exactly top_k candidates can only
        # reorder what one retriever already chose.
        depth = max(top_k, settings.rerank_candidates)

        vector_hits = await self._vector_search(user_id, query, top_k=depth)
        keyword_hits: list[RetrievedChunk] = []
        if settings.rag_hybrid_enabled and self._documents is not None:
            keyword_hits = await self._keyword_search(user_id, query, top_k=depth)

        candidates = self._fuse(vector_hits, keyword_hits)
        if not candidates:
            return []

        reranked = await self._rerank(query, candidates, top_k=top_k)
        return reranked[:top_k]

    # -- Stage 1a: vector ----------------------------------------------------

    async def _vector_search(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[RetrievedChunk]:
        try:
            vectors = await self._embeddings.embed([query])
            (embedding,) = vectors
        except Exception as exc:
            logger.warning("rag.embedding_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Embedding provider is unavailable") from exc

        try:
            matches = await self._vector_store.query(
                embedding, top_k=top_k, where={"user_id": str(user_id)}
            )
        except Exception as exc:
            logger.warning("rag.vector_query_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Vector store is unavailable") from exc

        return [
            RetrievedChunk(
                chunk_id=match.id,
                document_id=str(match.metadata.get("document_id", "")),
                filename=str(match.metadata.get("filename", "")),
                chunk_index=int(match.metadata.get("chunk_index", 0)),
                text=match.text,
                source=RetrievalSource.VECTOR,
                distance=match.distance,
            )
            for match in matches
        ]

    # -- Stage 1b: keyword ---------------------------------------------------

    async def _keyword_search(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[RetrievedChunk]:
        """BM25 over the chunks the SQL prefilter matched.

        Degrades to no keyword results on failure: the keyword half is an
        enhancement, and losing it must not fail a query the vector half can
        already answer.
        """
        terms = query_terms(query)
        if not terms or self._documents is None:
            return []

        settings = get_settings()
        try:
            rows = await self._documents.search_chunk_text(
                user_id, terms, limit=settings.rag_keyword_candidates
            )
        except Exception as exc:  # noqa: BLE001 - degradation is deliberate
            logger.warning("rag.keyword_query_failed", extra={"error": str(exc)})
            return []

        if not rows:
            return []

        texts = [chunk.content or "" for chunk, _ in rows]
        ranked = bm25_rank(query, texts)
        return [
            RetrievedChunk(
                chunk_id=str(rows[index][0].id),
                document_id=str(rows[index][0].document_id),
                filename=rows[index][1],
                chunk_index=rows[index][0].chunk_index,
                text=texts[index],
                source=RetrievalSource.KEYWORD,
                score=score,
            )
            for index, score in ranked[:top_k]
        ]

    # -- Stage 2: fusion -----------------------------------------------------

    def _fuse(
        self,
        vector_hits: Sequence[RetrievedChunk],
        keyword_hits: Sequence[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Merge both rankings with RRF, keeping the richer record per id."""
        if not keyword_hits:
            return list(vector_hits)
        if not vector_hits:
            return list(keyword_hits)

        by_id: dict[str, RetrievedChunk] = {
            chunk.chunk_id: chunk for chunk in keyword_hits
        }
        for chunk in vector_hits:
            if chunk.chunk_id in by_id:
                # Found by both retrievers: keep the vector record, which
                # carries a real distance, and record the agreement.
                by_id[chunk.chunk_id] = RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    source=RetrievalSource.HYBRID,
                    distance=chunk.distance,
                )
            else:
                by_id[chunk.chunk_id] = chunk

        fused = reciprocal_rank_fusion(
            [
                [chunk.chunk_id for chunk in vector_hits],
                [chunk.chunk_id for chunk in keyword_hits],
            ]
        )
        return [by_id[chunk_id].with_score(score) for chunk_id, score in fused]

    # -- Stage 3: rerank -----------------------------------------------------

    async def _rerank(
        self, query: str, candidates: list[RetrievedChunk], *, top_k: int
    ) -> list[RetrievedChunk]:
        """Reorder candidates with the cross-encoder, when one is configured.

        Failure returns the fused order untouched: a reranker outage should
        cost precision, not the answer.
        """
        if self._reranker is None or len(candidates) <= 1:
            return candidates

        try:
            ranked = await self._reranker.rerank(
                query, [chunk.text for chunk in candidates], top_k=top_k
            )
        except Exception as exc:  # noqa: BLE001 - degradation is deliberate
            logger.warning("rag.rerank_failed", extra={"error": str(exc)})
            return candidates

        return [candidates[index].with_score(score) for index, score in ranked]


# A tagged union rather than (str, object): the router narrows on the tag, so
# rendering a `sources` frame as text (or vice versa) is a type error, not a
# runtime surprise halfway through a stream.
AskStreamEvent = (
    tuple[Literal["sources"], list[RetrievedChunk]]
    | tuple[Literal["delta"], str]
    | tuple[Literal["done"], dict[str, Any]]
    | tuple[Literal["error"], str]
)


@dataclass(frozen=True)
class AskResult:
    """Outcome of a grounded ask."""

    answer: str
    grounded: bool
    model: str | None
    matches: list[RetrievedChunk]
    # What compression did, so the caller can report or log it.
    compression: CompressionResult | None = None


class RagAskService:
    """Retrieval-grounded question answering (retrieve → compress → generate)."""

    def __init__(
        self,
        retrieval: RagService,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm
        self._recorder = recorder

    async def ask(
        self,
        user_id: UUID,
        question: str,
        *,
        top_k: int,
        feature: str = "rag.ask",
        agent_name: str | None = None,
        history: Sequence[dict[str, str]] = (),
    ) -> AskResult:
        """Answer ``question`` from the owner's documents, with citations.

        When retrieval finds nothing the LLM is skipped entirely — the answer
        is an honest "nothing found" rather than an ungrounded generation.
        ``feature``/``agent_name`` label the audit record (direct asks vs
        agent-initiated ones).
        """
        matches = await self._retrieval.query(user_id, question, top_k=top_k)
        if not matches:
            return AskResult(
                answer=NO_CONTEXT_ANSWER, grounded=False, model=None, matches=[]
            )

        # Compression runs before prompt building, so the citations returned to
        # the caller are exactly the ones the model saw. Dropping a chunk after
        # generation would leave the answer citing a source the caller was told
        # about but the model never read.
        settings = get_settings()
        compression = compress(
            matches, budget_tokens=settings.rag_context_budget_tokens
        )
        if compression.dropped or compression.truncated:
            logger.info(
                "rag.context_compressed",
                extra={
                    "retrieved": len(matches),
                    "kept": len(compression.chunks),
                    "duplicates": compression.dropped_duplicates,
                    "over_budget": compression.dropped_over_budget,
                    "truncated": compression.truncated,
                    "tokens": compression.used_tokens,
                },
            )

        kept = compression.chunks
        if not kept:
            # The budget could not fit even one chunk. Answering ungrounded
            # would be worse than saying nothing was usable.
            return AskResult(
                answer=NO_CONTEXT_ANSWER,
                grounded=False,
                model=None,
                matches=[],
                compression=compression,
            )

        messages = build_ask_messages(question, kept, history)
        try:
            result = await self._recorder.chat(
                self._llm,
                messages,
                feature=feature,
                agent_name=agent_name,
                user_id=user_id,
                temperature=0.2,
                prompt_key="rag.ask.system",
                prompt_version=1,
            )
        except Exception as exc:
            logger.warning("rag.ask_llm_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("LLM provider is unavailable") from exc

        return AskResult(
            answer=result.content,
            grounded=True,
            model=result.model,
            matches=kept,
            compression=compression,
        )

    async def ask_stream(
        self,
        user_id: UUID,
        question: str,
        *,
        top_k: int,
        feature: str = "rag.ask",
        history: Sequence[dict[str, str]] = (),
    ) -> AsyncIterator[AskStreamEvent]:
        """Answer as above, but emit the reply as it is generated.

        Yields ``(event, payload)`` pairs. Sources come **first**, before any
        text: the UI can render citations while the answer is still arriving,
        and a reader can see what the answer is grounded in before deciding
        whether to trust it.

        Retrieval and compression are identical to :meth:`ask` -- only the
        generation step differs -- so a streamed answer is grounded in exactly
        the same context a non-streamed one would have been.
        """
        matches = await self._retrieval.query(user_id, question, top_k=top_k)
        if not matches:
            yield "sources", []
            yield "delta", NO_CONTEXT_ANSWER
            yield "done", {"grounded": False, "model": None}
            return

        settings = get_settings()
        compression = compress(
            matches, budget_tokens=settings.rag_context_budget_tokens
        )
        kept = compression.chunks
        if not kept:
            yield "sources", []
            yield "delta", NO_CONTEXT_ANSWER
            yield "done", {"grounded": False, "model": None}
            return

        yield "sources", kept

        model: str | None = None
        try:
            async for chunk in self._recorder.chat_stream(
                self._llm,
                build_ask_messages(question, kept, history),
                feature=feature,
                user_id=user_id,
                temperature=0.2,
                prompt_key="rag.ask.system",
                prompt_version=1,
            ):
                if chunk.delta:
                    yield "delta", chunk.delta
                if chunk.done and chunk.result is not None:
                    model = chunk.result.model
        except Exception as exc:
            logger.warning("rag.ask_stream_failed", extra={"error": str(exc)})
            # The client has already received partial text, so an HTTP error
            # code is no longer available: report it in-band instead.
            yield "error", "The language model became unavailable mid-answer."
            return

        yield "done", {"grounded": True, "model": model}
