"""Notification channel implementations and their config-driven assembly."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.domain.interfaces.database import DatabaseProvider
from app.domain.interfaces.notification import NotificationProvider
from app.infrastructure.notifications.inapp import InAppNotificationProvider
from app.infrastructure.notifications.smtp import SmtpNotificationProvider
from app.infrastructure.notifications.telegram import TelegramNotificationProvider


def build_notification_providers(
    settings: Settings,
    db: DatabaseProvider,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[NotificationProvider]:
    """Assemble the enabled channels: in-app always, others when configured."""
    providers: list[NotificationProvider] = [InAppNotificationProvider(db)]
    if settings.telegram_bot_token and settings.telegram_chat_id:
        providers.append(
            TelegramNotificationProvider(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                client=http_client,
            )
        )
    if settings.smtp_host and settings.smtp_from:
        providers.append(
            SmtpNotificationProvider(
                host=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                sender=settings.smtp_from,
            )
        )
    return providers


__all__ = [
    "InAppNotificationProvider",
    "SmtpNotificationProvider",
    "TelegramNotificationProvider",
    "build_notification_providers",
]
