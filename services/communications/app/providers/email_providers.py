"""Email providers (Phase 12c)."""
from __future__ import annotations

import os

from app.providers.notification_provider import (
    NotificationProvider, NotificationResult, NotificationStatus,
    NotificationProviderError,
)


class SendGridEmailProvider:
    channel = "email"
    name = "sendgrid"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        if not os.environ.get("SENDGRID_API_KEY"):
            raise NotificationProviderError(
                "SendGrid API key not set. Configure SENDGRID_API_KEY "
                "or pick another email provider in school settings."
            )
        raise NotificationProviderError(
            "SendGrid adapter: not wired yet — schools using email "
            "today rely on SMS / WhatsApp."
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        raise NotificationProviderError("not implemented")


class ManualEmailProvider:
    channel = "email"
    name = "manual"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        return NotificationResult(
            provider_message_id=None,
            status="MANUAL_PENDING",
            raw_response={"channel": "email", "recipient": recipient,
                          "subject": subject},
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        return NotificationStatus(
            provider_message_id=provider_message_id,
            status="MANUAL_PENDING", raw_response={},
        )
