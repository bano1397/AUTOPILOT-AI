"""Telegram notification provider (Bot API over plain httpx)."""

from __future__ import annotations

from uuid import UUID

import httpx

from app.platform.registry import register_provider

_TIMEOUT_SECONDS = 15.0


@register_provider(kind="notification", name="telegram")
class TelegramNotificationProvider:
    """Sends notifications to a configured chat via the Telegram Bot API."""

    name = "telegram"

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._client = client

    async def send(
        self, *, user_id: UUID, email: str, kind: str, title: str, body: str
    ) -> None:
        payload = {"chat_id": self._chat_id, "text": f"{title}\n\n{body}"}
        if self._client is not None:
            response = await self._client.post(self._url, json=payload)
        else:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(self._url, json=payload)
        response.raise_for_status()
