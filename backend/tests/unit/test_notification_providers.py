"""Unit tests for notification providers and the dispatcher."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
from app.features.notifications.dispatcher import NotificationDispatcher
from app.infrastructure.notifications import (
    TelegramNotificationProvider,
    build_notification_providers,
)


async def test_telegram_wire_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TelegramNotificationProvider(
            bot_token="abc123", chat_id="42", client=client
        )
        await provider.send(
            user_id=uuid4(),
            email="a@example.com",
            kind="workflow_failed",
            title="Workflow failed",
            body="Something broke",
        )

    assert captured["url"] == "https://api.telegram.org/botabc123/sendMessage"
    assert captured["body"] == {
        "chat_id": "42",
        "text": "Workflow failed\n\nSomething broke",
    }


async def test_telegram_http_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TelegramNotificationProvider(
            bot_token="bad", chat_id="42", client=client
        )
        try:
            await provider.send(
                user_id=uuid4(), email="a@b.c", kind="k", title="t", body="b"
            )
            raise AssertionError("expected HTTPStatusError")
        except httpx.HTTPStatusError:
            pass


class _RecordingProvider:
    name = "recording"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    async def send(
        self, *, user_id: object, email: str, kind: str, title: str, body: str
    ) -> None:
        if self.fail:
            raise RuntimeError("channel down")
        self.sent.append(title)


class _FakeUserDb:
    """Database stub whose session yields a user-repo-compatible object."""

    def __init__(self, email: str | None) -> None:
        self._email = email

    def session(self) -> object:
        email = self._email

        class _Ctx:
            async def __aenter__(self) -> object:
                class _Session:
                    async def get(self, model: object, key: object) -> object | None:
                        if email is None:
                            return None

                        class _User:
                            pass

                        user = _User()
                        user.email = email  # type: ignore[attr-defined]
                        return user

                return _Session()

            async def __aexit__(self, *args: object) -> None:
                return None

        return _Ctx()


async def test_dispatcher_isolates_channel_failures() -> None:
    failing = _RecordingProvider(fail=True)
    working = _RecordingProvider()
    dispatcher = NotificationDispatcher(
        _FakeUserDb("user@example.com"),  # type: ignore[arg-type]
        [failing, working],
    )

    await dispatcher.dispatch(uuid4(), kind="k", title="Hello", body="World")

    assert working.sent == ["Hello"]  # the healthy channel still delivered


async def test_dispatcher_skips_unknown_user() -> None:
    provider = _RecordingProvider()
    dispatcher = NotificationDispatcher(
        _FakeUserDb(None),  # type: ignore[arg-type]
        [provider],
    )

    await dispatcher.dispatch(uuid4(), kind="k", title="Hello", body="World")

    assert provider.sent == []


def test_provider_assembly_is_config_gated() -> None:
    from app.core.config import Settings

    db = _FakeUserDb("a@b.c")

    bare = build_notification_providers(Settings(), db)  # type: ignore[arg-type]
    assert [provider.name for provider in bare] == ["in_app"]

    full = build_notification_providers(
        Settings(
            telegram_bot_token="t",
            telegram_chat_id="c",
            smtp_host="mail.example.com",
            smtp_from="bot@example.com",
        ),
        db,  # type: ignore[arg-type]
    )
    assert [provider.name for provider in full] == ["in_app", "telegram", "smtp"]
