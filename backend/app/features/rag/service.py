"""RAG use-cases: retrieval, and retrieval-grounded answering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import UpstreamServiceError
from app.core.logging import get_logger
from app.domain.interfaces.embedding import EmbeddingProvider
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.vector_store import VectorMatch, VectorStoreProvider
from app.features.rag.prompts import build_ask_messages
from app.platform.observability.recorder import AiExecutionRecorder

logger = get_logger("app.features.rag")

# Returned without invoking the LLM when retrieval finds nothing: honest,
# hallucination-free, and free of token cost.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant to your question in your indexed "
    "documents. Try uploading related documents or rephrasing the question."
)


class RagService:
    """Semantic retrieval over indexed document chunks."""

    def __init__(
        self, embeddings: EmbeddingProvider, vector_store: VectorStoreProvider
    ) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def query(
        self, user_id: UUID, query: str, *, top_k: int
    ) -> list[VectorMatch]:
        """Return the owner's ``top_k`` most similar chunks for ``query``.

        Results are owner-isolated at the vector-store level via the
        ``user_id`` metadata filter stamped on every vector at indexing time.
        """
        try:
            vectors = await self._embeddings.embed([query])
            (embedding,) = vectors
        except Exception as exc:
            logger.warning("rag.embedding_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Embedding provider is unavailable") from exc

        try:
            return await self._vector_store.query(
                embedding, top_k=top_k, where={"user_id": str(user_id)}
            )
        except Exception as exc:
            logger.warning("rag.vector_query_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Vector store is unavailable") from exc


@dataclass(frozen=True)
class AskResult:
    """Outcome of a grounded ask."""

    answer: str
    grounded: bool
    model: str | None
    matches: list[VectorMatch]


class RagAskService:
    """Retrieval-grounded question answering (retrieve → ground → generate)."""

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

        messages = build_ask_messages(question, matches, history)
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
            answer=result.content, grounded=True, model=result.model, matches=matches
        )
