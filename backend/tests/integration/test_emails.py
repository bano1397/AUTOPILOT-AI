"""Integration tests for the email agent vertical.

Covers the whole path: sync → classify → ground → draft → human sends or
discards. The send gate is the point of these tests — a draft must never reach
SMTP without an explicit human call.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from app.domain.interfaces.email import InboundEmail
from app.features.emails.models import EmailIntent, EmailStatus
from app.infrastructure.database.sqlalchemy_provider import SqlAlchemyDatabaseProvider
from app.infrastructure.storage import LocalStorageProvider
from app.platform.observability import AiExecution, AiExecutionRecorder
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.fakes import (
    FakeEmailReader,
    FakeEmailSender,
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeVectorStore,
)

_CLASSIFY = json.dumps(
    {
        "intent": "invoice",
        "entities": {"amounts": ["$420.00"], "order_ids": ["INV-2231"]},
        "summary": "Asks when invoice INV-2231 will be paid.",
    }
)
_DRAFT = "Thanks for the nudge — invoice INV-2231 is scheduled for payment [1]."


def _message(uid: str = "1", message_id: str = "<a@example.com>") -> InboundEmail:
    return InboundEmail(
        uid=uid,
        message_id=message_id,
        sender="billing@vendor.test",
        subject="Invoice INV-2231 overdue",
        body="Hello, when will invoice INV-2231 for $420.00 be paid?",
        received_at=datetime(2026, 7, 28, 9, 0, tzinfo=UTC),
    )


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    # Two calls per triage: classification, then the draft.
    return FakeLLMProvider(replies=[_CLASSIFY, _DRAFT])


@pytest.fixture
def reader() -> FakeEmailReader:
    return FakeEmailReader([_message()])


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest_asyncio.fixture
async def api(
    app: FastAPI,
    db: SqlAlchemyDatabaseProvider,
    tmp_path: Path,
    fake_llm: FakeLLMProvider,
    reader: FakeEmailReader,
    sender: FakeEmailSender,
) -> AsyncIterator[AsyncClient]:
    app.state.db = db
    app.state.storage = LocalStorageProvider(tmp_path / "docs")
    app.state.embeddings = FakeEmbeddingProvider()
    app.state.vector_store = FakeVectorStore()
    app.state.llm = fake_llm
    app.state.ai_recorder = AiExecutionRecorder(db=db, bus=app.state.event_bus)
    app.state.email_reader = reader
    app.state.email_sender = sender
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _sync(api: AsyncClient) -> dict:
    response = await api.post("/api/v1/emails/sync")
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


async def _first(api: AsyncClient) -> dict:
    listing = await api.get("/api/v1/emails")
    assert listing.status_code == 200, listing.text
    return dict(listing.json()["data"][0])


# --- sync + triage ----------------------------------------------------------


async def test_sync_classifies_extracts_and_drafts(api: AsyncClient) -> None:
    summary = await _sync(api)

    assert summary == {"fetched": 1, "triaged": 1, "skipped": 0, "failed": 0}
    mail = await _first(api)
    assert mail["intent"] == EmailIntent.INVOICE.value
    assert mail["entities"]["order_ids"] == ["INV-2231"]
    assert mail["entities"]["summary"] == ["Asks when invoice INV-2231 will be paid."]
    assert mail["draft"] == _DRAFT
    # A draft exists, so it waits for a human — it is not sent.
    assert mail["status"] == EmailStatus.AWAITING_APPROVAL.value
    assert mail["sent_at"] is None


async def test_sync_marks_messages_seen(api: AsyncClient, reader: FakeEmailReader) -> None:
    await _sync(api)

    assert reader.seen == ["1"]


async def test_resync_does_not_duplicate_the_same_message(api: AsyncClient) -> None:
    await _sync(api)
    second = await _sync(api)

    assert second["skipped"] == 1
    assert second["triaged"] == 0
    listing = await api.get("/api/v1/emails")
    assert listing.json()["meta"]["total"] == 1


async def test_draft_is_grounded_in_indexed_documents(
    api: AsyncClient, app: FastAPI
) -> None:
    store: FakeVectorStore = app.state.vector_store
    me = await api.get("/api/v1/users/me")
    await store.upsert(
        ids=["v1"],
        embeddings=[[0.1, 0.2, 0.3]],
        documents=["Invoices are paid net 30 from receipt."],
        metadatas=[
            {
                "user_id": me.json()["data"]["id"],
                "filename": "finance-policy.pdf",
                "chunk_index": 0,
                "document_id": "d1",
            }
        ],
    )

    await _sync(api)

    mail = await _first(api)
    assert mail["grounded"] is True


async def test_draft_without_matching_documents_is_ungrounded(api: AsyncClient) -> None:
    await _sync(api)

    assert (await _first(api))["grounded"] is False


async def test_both_llm_calls_are_audited_with_prompt_provenance(
    api: AsyncClient, db: SqlAlchemyDatabaseProvider
) -> None:
    await _sync(api)

    async with db.session() as session:
        rows = (await session.execute(select(AiExecution))).scalars().all()

    by_feature = {row.feature: row for row in rows}
    assert set(by_feature) == {"email.classify", "email.draft"}
    assert by_feature["email.classify"].prompt_key == "agent.email.classify"
    assert by_feature["email.draft"].prompt_key == "agent.email.draft"
    assert all(row.prompt_version == 1 for row in rows)
    assert all(row.agent_name == "email" for row in rows)


async def test_spam_is_classified_but_never_drafted(
    api: AsyncClient, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.replies = [json.dumps({"intent": "spam"})]

    await _sync(api)

    mail = await _first(api)
    assert mail["intent"] == EmailIntent.SPAM.value
    assert mail["draft"] is None
    assert mail["status"] == EmailStatus.DISCARDED.value
    # Only the classification call happened — no tokens spent drafting spam.
    assert len(fake_llm.calls) == 1


async def test_retrieval_outage_still_produces_an_ungrounded_draft(
    api: AsyncClient, app: FastAPI
) -> None:
    app.state.embeddings = FakeEmbeddingProvider(fail=True)

    await _sync(api)

    mail = await _first(api)
    assert mail["status"] == EmailStatus.AWAITING_APPROVAL.value
    assert mail["grounded"] is False


async def test_llm_failure_marks_one_message_failed_without_losing_it(
    api: AsyncClient, app: FastAPI
) -> None:
    app.state.llm = FakeLLMProvider(fail=True)

    summary = await _sync(api)

    assert summary["failed"] == 1
    mail = await _first(api)
    assert mail["status"] == EmailStatus.FAILED.value
    assert mail["error"]


async def test_mailbox_outage_returns_502(api: AsyncClient, reader: FakeEmailReader) -> None:
    reader.fail = True

    response = await api.post("/api/v1/emails/sync")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_SERVICE_ERROR"


async def test_sync_without_a_configured_mailbox_returns_502(
    api: AsyncClient, app: FastAPI
) -> None:
    app.state.email_reader = None

    response = await api.post("/api/v1/emails/sync")

    assert response.status_code == 502


# --- the human gate ---------------------------------------------------------


async def test_send_delivers_the_draft_and_threads_the_reply(
    api: AsyncClient, sender: FakeEmailSender
) -> None:
    await _sync(api)
    mail = await _first(api)

    response = await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == EmailStatus.SENT.value
    assert data["sent_at"] is not None
    assert sender.sent == [
        {
            "to": "billing@vendor.test",
            "subject": "Re: Invoice INV-2231 overdue",
            "body": _DRAFT,
            "in_reply_to": "<a@example.com>",
        }
    ]


async def test_send_can_use_an_edited_body(
    api: AsyncClient, sender: FakeEmailSender
) -> None:
    await _sync(api)
    mail = await _first(api)

    await api.post(f"/api/v1/emails/{mail['id']}/send", json={"body": "Edited reply."})

    assert sender.sent[0]["body"] == "Edited reply."
    assert (await _first(api))["draft"] == "Edited reply."


async def test_nothing_is_sent_without_an_explicit_call(
    api: AsyncClient, sender: FakeEmailSender
) -> None:
    """The whole point of the gate: triage alone must not send anything."""
    await _sync(api)

    assert sender.sent == []


async def test_discard_never_sends(api: AsyncClient, sender: FakeEmailSender) -> None:
    await _sync(api)
    mail = await _first(api)

    response = await api.post(f"/api/v1/emails/{mail['id']}/discard")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == EmailStatus.DISCARDED.value
    assert sender.sent == []


async def test_sending_twice_is_a_conflict(api: AsyncClient) -> None:
    await _sync(api)
    mail = await _first(api)
    await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    second = await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


async def test_failed_send_leaves_the_draft_decidable(
    api: AsyncClient, sender: FakeEmailSender
) -> None:
    """A dead SMTP server must not leave the row claiming a reply was sent."""
    await _sync(api)
    mail = await _first(api)
    sender.fail = True

    response = await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    assert response.status_code == 502
    after = await _first(api)
    assert after["status"] == EmailStatus.AWAITING_APPROVAL.value
    assert after["sent_at"] is None


async def test_send_without_outbound_configuration_returns_502(
    api: AsyncClient, app: FastAPI
) -> None:
    await _sync(api)
    mail = await _first(api)
    app.state.email_sender = None

    response = await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    assert response.status_code == 502


async def test_retriage_redrafts_a_failed_message(
    api: AsyncClient, app: FastAPI
) -> None:
    app.state.llm = FakeLLMProvider(fail=True)
    await _sync(api)
    mail = await _first(api)
    assert mail["status"] == EmailStatus.FAILED.value

    app.state.llm = FakeLLMProvider(replies=[_CLASSIFY, _DRAFT])
    response = await api.post(f"/api/v1/emails/{mail['id']}/retriage")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == EmailStatus.AWAITING_APPROVAL.value


async def test_retriage_after_sending_is_a_conflict(api: AsyncClient) -> None:
    await _sync(api)
    mail = await _first(api)
    await api.post(f"/api/v1/emails/{mail['id']}/send", json={})

    response = await api.post(f"/api/v1/emails/{mail['id']}/retriage")

    assert response.status_code == 409


# --- listing ----------------------------------------------------------------


async def test_listing_filters_by_status(api: AsyncClient) -> None:
    await _sync(api)

    awaiting = await api.get("/api/v1/emails?status=awaiting_approval")
    sent = await api.get("/api/v1/emails?status=sent")

    assert awaiting.json()["meta"]["total"] == 1
    assert sent.json()["meta"]["total"] == 0


async def test_unknown_email_returns_404(api: AsyncClient) -> None:
    from uuid import uuid4

    response = await api.get(f"/api/v1/emails/{uuid4()}")

    assert response.status_code == 404
