"""SMS providers (Phase 12c)."""
from __future__ import annotations

import os
from typing import Optional

from app.providers.notification_provider import (
    NotificationProvider, NotificationResult, NotificationStatus,
    NotificationProviderError,
)


class AfricasTalkingSmsProvider:
    channel = "sms"
    name = "africastalking"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        if not os.environ.get("AFRICASTALKING_API_KEY"):
            raise NotificationProviderError(
                "AfricasTalking API key not set. Configure "
                "AFRICASTALKING_API_KEY + AFRICASTALKING_USERNAME or "
                "pick another SMS provider in school settings."
            )
        # The actual SDK call is mounted in the legacy SMS dispatcher
        # (services/communications/app/services/communication_service.py).
        # This adapter exists so the provider abstraction is whole;
        # unification with the legacy path is a follow-up.
        raise NotificationProviderError(
            "AfricasTalking adapter: use the legacy SMS dispatcher "
            "until the Phase 12c follow-up unifies the paths."
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        raise NotificationProviderError("not implemented")


class ManualSmsProvider:
    """No-op + audit. School sends SMS externally (or chooses not to)."""
    channel = "sms"
    name = "manual"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        return NotificationResult(
            provider_message_id=None,
            status="MANUAL_PENDING",
            raw_response={
                "recipient": recipient,
                "preview": body[:80],
                "instructions": (
                    "Manual SMS provider: a school admin should send "
                    "this message externally and mark the outbox "
                    "row delivered."
                ),
            },
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        return NotificationStatus(
            provider_message_id=provider_message_id,
            status="MANUAL_PENDING", raw_response={},
        )
