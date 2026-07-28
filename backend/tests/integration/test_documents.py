"""Integration tests for the documents API (upload, list, get, delete)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeEmbeddingProvider, FakeVectorStore

# httpx multipart file spec: name -> (filename, content, content_type)
FileSpec = dict[str, tuple[str, bytes, str]]


@pytest_asyncio.fixture
async def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "docs"


@pytest_asyncio.fixture
async def api(
    app: FastAPI, db: SqlAlchemyDatabaseProvider, storage_dir: Path
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(storage_dir)
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _txt(name: str = "notes.txt", body: bytes = b"hello world") -> FileSpec:
    return {"file": (name, body, "text/plain")}


def _stored_files(storage_dir: Path) -> list[Path]:
    if not storage_dir.exists():
        return []
    return [path for path in storage_dir.rglob("*") if path.is_file()]


async def test_upload_txt_document(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, storage_dir: Path
) -> None:

    response = await api.post("/api/v1/documents", files=_txt())

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["filename"] == "notes.txt"
    assert data["mime_type"] == "text/plain"
    assert data["size_bytes"] == len(b"hello world")
    assert data["status"] == "uploaded"
    # Exactly one file stored, under a random name (never the client filename).
    stored = _stored_files(storage_dir)
    assert len(stored) == 1
    assert stored[0].name != "notes.txt"
    assert stored[0].read_bytes() == b"hello world"


async def test_upload_pdf_document(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    response = await api.post(
        "/api/v1/documents",
        files={"file": ("report.pdf", b"%PDF-1.7 body", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["data"]["mime_type"] == "application/pdf"


async def test_upload_disallowed_type_is_rejected(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, storage_dir: Path
) -> None:

    response = await api.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert _stored_files(storage_dir) == []


async def test_upload_wrong_magic_bytes_is_rejected(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    response = await api.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"<html>not a pdf</html>", "application/pdf")},
    )

    assert response.status_code == 415


async def test_upload_oversized_file_is_rejected(
    api: AsyncClient,
    db: SqlAlchemyDatabaseProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)

    response = await api.post("/api/v1/documents", files=_txt())

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_get_missing_document_returns_404(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:

    response = await api.get(f"/api/v1/documents/{uuid4()}")

    assert response.status_code == 404


async def test_delete_removes_record_and_file(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider, storage_dir: Path
) -> None:
    created = await api.post("/api/v1/documents", files=_txt())
    document_id = created.json()["data"]["id"]
    assert len(_stored_files(storage_dir)) == 1

    response = await api.delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Document deleted"
    assert _stored_files(storage_dir) == []
    gone = await api.get(f"/api/v1/documents/{document_id}")
    assert gone.status_code == 404
