"""Integration tests for the event-driven ingestion pipeline.

The in-process bus delivers synchronously inside ``publish``, so by the time an
upload response returns, ingestion has already completed — no polling needed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from app.features.documents.models import DocumentChunk
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_vectors() -> FakeVectorStore:
    return FakeVectorStore()


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_embeddings: FakeEmbeddingProvider,
    fake_vectors: FakeVectorStore,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = fake_embeddings
    app.state.vector_store = fake_vectors
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _chunk_count(db: SqlAlchemyDatabaseProvider, document_id: str) -> int:
    async with db.session() as session:
        result = await session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == UUID(document_id))
        )
        return int(result.scalar_one())


async def test_upload_triggers_ingestion_to_indexed(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    body = ("The quick brown fox jumps over the lazy dog. " * 60).encode()

    created = await api.post(
        "/api/v1/documents",
        files={"file": ("fox.txt", body, "text/plain")},
    )
    assert created.status_code == 201
    document_id = created.json()["data"]["id"]

    fetched = await api.get(f"/api/v1/documents/{document_id}")

    data = fetched.json()["data"]
    assert data["status"] == "indexed"
    chunk_count = data["metadata"]["chunk_count"]
    assert chunk_count >= 2  # ~2700 chars with a 1000-char window
    assert await _chunk_count(db, document_id) == chunk_count


async def test_chunks_carry_previews_and_sequential_indexes(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    body = ("Paragraph one about revenue. " * 50).encode()
    created = await api.post(
        "/api/v1/documents",
        files={"file": ("report.txt", body, "text/plain")},
    )
    document_id = created.json()["data"]["id"]

    async with db.session() as session:
        result = await session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == UUID(document_id))
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.content_preview
        assert len(chunk.content_preview) <= 500
        assert chunk.vector_id == str(chunk.id)  # filled by the indexing stage
        assert chunk.chunk_metadata["chars"] >= len(chunk.content_preview)


async def test_unparseable_pdf_is_marked_failed(
    api: AsyncClient
) -> None:
    # Valid magic bytes (passes upload validation) but not a parseable PDF.
    created = await api.post(
        "/api/v1/documents",
        files={"file": ("broken.pdf", b"%PDF-1.7 garbage without structure", "application/pdf")},
    )
    assert created.status_code == 201
    document_id = created.json()["data"]["id"]

    fetched = await api.get(f"/api/v1/documents/{document_id}")

    data = fetched.json()["data"]
    assert data["status"] == "failed"
    assert data["metadata"]["error"]


async def test_delete_document_removes_chunks(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_vectors: FakeVectorStore,
) -> None:
    body = ("Some content to be chunked and then deleted. " * 40).encode()
    created = await api.post(
        "/api/v1/documents",
        files={"file": ("temp.txt", body, "text/plain")},
    )
    document_id = created.json()["data"]["id"]
    assert await _chunk_count(db, document_id) > 0
    assert len(fake_vectors.vectors) > 0

    deleted = await api.delete(f"/api/v1/documents/{document_id}")

    assert deleted.status_code == 200
    assert await _chunk_count(db, document_id) == 0
    assert fake_vectors.vectors == {}  # vectors removed with the document


async def test_indexing_upserts_vectors_with_metadata(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_embeddings: FakeEmbeddingProvider,
    fake_vectors: FakeVectorStore,
) -> None:
    body = ("Quarterly revenue grew by twelve percent. " * 50).encode()
    created = await api.post(
        "/api/v1/documents",
        files={"file": ("revenue.txt", body, "text/plain")},
    )
    document_id = created.json()["data"]["id"]

    async with db.session() as session:
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == UUID(document_id))
        )
        chunks = list(result.scalars().all())

    # One vector per chunk, keyed by the chunk row id.
    assert set(fake_vectors.vectors) == {str(chunk.id) for chunk in chunks}
    assert sum(len(call) for call in fake_embeddings.calls) == len(chunks)
    for chunk in chunks:
        entry = fake_vectors.vectors[str(chunk.id)]
        assert entry["document"].startswith(chunk.content_preview[:50])
        assert entry["metadata"]["document_id"] == document_id
        assert entry["metadata"]["chunk_index"] == chunk.chunk_index
        assert entry["metadata"]["filename"] == "revenue.txt"
        assert entry["metadata"]["user_id"]


async def test_embedding_failure_marks_document_failed(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    fake_embeddings: FakeEmbeddingProvider,
    fake_vectors: FakeVectorStore,
) -> None:
    fake_embeddings.fail = True
    body = ("Text that will fail to embed. " * 40).encode()
    created = await api.post(
        "/api/v1/documents",
        files={"file": ("doomed.txt", body, "text/plain")},
    )
    document_id = created.json()["data"]["id"]

    fetched = await api.get(f"/api/v1/documents/{document_id}")

    data = fetched.json()["data"]
    assert data["status"] == "failed"
    assert "embedding service unavailable" in data["metadata"]["error"]
    # The rollback discarded the chunk rows and nothing reached the store.
    assert await _chunk_count(db, document_id) == 0
    assert fake_vectors.vectors == {}
