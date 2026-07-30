"""Integration tests for the query-side RAG pipeline (blueprint §17).

Hybrid retrieval → fusion → rerank → compression, driven through the real HTTP
surface against a real database, with the stub embedding provider and the
in-process vector store standing in for the model layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.embeddings.stub import StubEmbeddingProvider
from app.infrastructure.storage import LocalStorageProvider
from app.infrastructure.vectorstore import InMemoryVectorStore
from app.platform.observability import AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeLLMProvider

# A rare token no embedding of a paraphrase will land near, but that BM25
# matches exactly. This is the case hybrid retrieval exists for.
RARE_TOKEN = "zylonite"


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, tmp_path: Path
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = StubEmbeddingProvider(dimensions=256)
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm = FakeLLMProvider(reply="Grounded answer [1].")
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _upload(api: AsyncClient, name: str, text: str) -> str:
    response = await api.post(
        "/api/v1/documents", files={"file": (name, text.encode(), "text/plain")}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["data"]["id"])


async def _query(api: AsyncClient, query: str, **extra: object) -> list[dict]:
    response = await api.post(
        "/api/v1/rag/query", json={"query": query, "top_k": 5, **extra}
    )
    assert response.status_code == 200, response.text
    return list(response.json()["data"]["matches"])


class TestKeywordRecall:
    """The gap vector search leaves: identifiers, codes, product names."""

    async def test_rare_token_is_retrieved_and_labelled(self, api: AsyncClient) -> None:
        await _upload(
            api,
            "spec.txt",
            f"The {RARE_TOKEN} assembly ships in April and replaces the older unit.",
        )
        await _upload(api, "other.txt", "Parking permits are issued quarterly.")

        matches = await _query(api, RARE_TOKEN)

        assert matches, "the rare token should be retrievable"
        top = matches[0]
        assert RARE_TOKEN in top["text"]
        assert top["retrieval"] in {"keyword", "hybrid"}

    async def test_keyword_only_hits_report_no_distance(
        self, api: AsyncClient
    ) -> None:
        """Reporting a vector distance for a chunk no vector search ranked
        would be an invention; the API returns null instead."""
        await _upload(api, "spec.txt", f"{RARE_TOKEN} assembly notes.")

        matches = await _query(api, RARE_TOKEN)
        keyword_only = [m for m in matches if m["retrieval"] == "keyword"]

        for match in keyword_only:
            assert match["distance"] is None

    async def test_hybrid_can_be_disabled(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.config import get_settings

        await _upload(api, "spec.txt", f"{RARE_TOKEN} assembly notes.")

        settings = get_settings()
        monkeypatch.setattr(settings, "rag_hybrid_enabled", False)
        matches = await _query(api, RARE_TOKEN)

        assert all(match["retrieval"] == "vector" for match in matches)


class TestFusion:
    async def test_a_chunk_found_by_both_is_labelled_hybrid(
        self, api: AsyncClient
    ) -> None:
        await _upload(
            api,
            "policy.txt",
            "Employees receive twenty vacation days per year.",
        )

        matches = await _query(api, "vacation days")

        assert matches[0]["retrieval"] == "hybrid"

    async def test_every_match_carries_a_fused_score(self, api: AsyncClient) -> None:
        await _upload(api, "a.txt", "vacation days accrue monthly")
        await _upload(api, "b.txt", "parking permits renew annually")

        matches = await _query(api, "vacation")

        assert all(match["score"] > 0 for match in matches)

    async def test_results_are_ordered_by_score(self, api: AsyncClient) -> None:
        for index in range(4):
            await _upload(api, f"doc{index}.txt", f"topic{index} vacation days text")

        matches = await _query(api, "vacation days")
        scores = [match["score"] for match in matches]

        assert scores == sorted(scores, reverse=True)

    async def test_top_k_is_respected(self, api: AsyncClient) -> None:
        for index in range(8):
            await _upload(api, f"doc{index}.txt", f"topic{index} shared vacation text")

        assert len(await _query(api, "vacation", top_k=3)) == 3


class TestReranking:
    async def test_a_configured_reranker_reorders_results(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        class ReverseReranker:
            """Stands in for a cross-encoder: deterministic, and visibly
            different from the fused order."""

            async def rerank(
                self, query: str, documents: list[str], *, top_k: int | None = None
            ) -> list[tuple[int, float]]:
                indices = list(reversed(range(len(documents))))
                return [(index, float(rank)) for rank, index in enumerate(indices)]

        for index in range(4):
            await _upload(api, f"doc{index}.txt", f"topic{index} vacation days text")

        before = await _query(api, "vacation days")
        app.state.reranker = ReverseReranker()
        after = await _query(api, "vacation days")

        assert [m["text"] for m in after] != [m["text"] for m in before]

    async def test_a_failing_reranker_leaves_the_fused_order_intact(
        self, api: AsyncClient, app: FastAPI
    ) -> None:
        """A reranker outage must cost precision, not the answer."""

        class BrokenReranker:
            async def rerank(
                self, query: str, documents: list[str], *, top_k: int | None = None
            ) -> list[tuple[int, float]]:
                raise RuntimeError("rerank service unavailable")

        for index in range(3):
            await _upload(api, f"doc{index}.txt", f"topic{index} vacation days text")

        before = await _query(api, "vacation days")
        app.state.reranker = BrokenReranker()
        after = await _query(api, "vacation days")

        assert [m["text"] for m in after] == [m["text"] for m in before]


class TestCompression:
    async def test_ask_context_stays_within_the_token_budget(
        self, api: AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.config import get_settings

        fake_llm = FakeLLMProvider(reply="Answer [1].")
        app.state.llm = fake_llm
        for index in range(6):
            await _upload(api, f"doc{index}.txt", f"topic{index} vacation " + "filler " * 300)

        monkeypatch.setattr(get_settings(), "rag_context_budget_tokens", 300)
        response = await api.post(
            "/api/v1/rag/ask", json={"query": "vacation", "top_k": 6}
        )

        assert response.status_code == 200, response.text
        # Sources reported must be exactly the ones the model was shown.
        sources = response.json()["data"]["sources"]
        prompt = fake_llm.calls[0][-1].content
        assert len(sources) < 6, "the budget should have dropped something"
        for source in sources:
            assert source["text"][:60] in prompt

    async def test_answer_is_still_grounded_after_compression(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.config import get_settings

        await _upload(api, "policy.txt", "Employees receive twenty vacation days.")
        monkeypatch.setattr(get_settings(), "rag_context_budget_tokens", 2000)

        response = await api.post("/api/v1/rag/ask", json={"query": "vacation days"})

        assert response.json()["data"]["grounded"] is True


class TestReindex:
    async def test_reindex_rebuilds_chunks_and_keeps_the_document_id(
        self, api: AsyncClient
    ) -> None:
        document_id = await _upload(
            api, "policy.txt", f"{RARE_TOKEN} appears in this policy document."
        )

        response = await api.post(f"/api/v1/documents/{document_id}/reindex")

        assert response.status_code == 200, response.text
        assert response.json()["data"]["id"] == document_id
        assert response.json()["data"]["status"] == "indexed"

        # Still retrievable, and not duplicated by the rebuild.
        matches = await _query(api, RARE_TOKEN)
        assert len({match["text"] for match in matches}) == len(matches)

    async def test_reindex_of_an_unknown_document_is_404(
        self, api: AsyncClient
    ) -> None:
        response = await api.post(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/reindex"
        )

        assert response.status_code == 404

    async def test_reindex_makes_a_pre_hybrid_chunk_keyword_searchable(
        self, api: AsyncClient, db: SqlAlchemyDatabaseProvider
    ) -> None:
        """Chunks written before the content column existed have NULL text.
        Re-indexing is the documented way to bring them back."""
        from app.features.documents.models import DocumentChunk
        from sqlalchemy import update

        document_id = await _upload(api, "old.txt", f"{RARE_TOKEN} legacy content.")

        # Simulate the pre-migration state.
        async with db.session() as session:
            await session.execute(update(DocumentChunk).values(content=None))
            await session.commit()

        stale = await _query(api, RARE_TOKEN)
        assert all(match["retrieval"] == "vector" for match in stale)

        await api.post(f"/api/v1/documents/{document_id}/reindex")

        healed = await _query(api, RARE_TOKEN)
        assert any(match["retrieval"] in {"keyword", "hybrid"} for match in healed)
