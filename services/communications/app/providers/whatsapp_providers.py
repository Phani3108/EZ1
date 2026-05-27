"""WhatsApp providers (Phase 12c)."""
from __future__ import annotations

import os

from app.providers.notification_provider import (
    NotificationProvider, NotificationResult, NotificationStatus,
    NotificationProviderError,
)


class MetaCloudWhatsAppProvider:
    channel = "whatsapp"
    name = "meta_cloud"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        # The full Meta Cloud integration lives in
        # `app/services/whatsapp_provider.py` (separate from this
        # abstraction). Adapter raises so the registry can fall back
        # gracefully when the credentials aren't set.
        if not os.environ.get("WHATSAPP_PHONE_NUMBER_ID"):
            raise NotificationProviderError(
                "WhatsApp Cloud API not configured. Set "
                "WHATSAPP_PHONE_NUMBER_ID + WHATSAPP_ACCESS_TOKEN."
            )
        raise NotificationProviderError(
            "MetaCloudWhatsAppProvider adapter: use the legacy "
            "services/whatsapp_provider.py path until unification."
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        raise NotificationProviderError("not implemented")


class ManualWhatsAppProvider:
    channel = "whatsapp"
    name = "manual"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        return NotificationResult(
            provider_message_id=None,
            status="MANUAL_PENDING",
            raw_response={"channel": "whatsapp", "recipient": recipient},
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        return NotificationStatus(
            provider_message_id=provider_message_id,
            status="MANUAL_PENDING", raw_response={},
        )
