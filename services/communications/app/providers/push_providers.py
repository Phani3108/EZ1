"""Push providers (Phase 12c)."""
from __future__ import annotations

import os
from typing import Optional

from app.providers.notification_provider import (
    NotificationProvider, NotificationResult, NotificationStatus,
    NotificationProviderError,
)


class FcmPushProvider:
    channel = "push"
    name = "fcm"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        if not os.environ.get("FCM_SERVER_KEY"):
            raise NotificationProviderError(
                "FCM server key not set. Configure FCM_SERVER_KEY "
                "or pick another push provider in school settings."
            )
        # SDK call lives in the legacy push dispatcher; this adapter
        # exists for the abstraction surface only.
        raise NotificationProviderError(
            "FCM adapter: use the legacy push dispatcher until the "
            "Phase 12c unification follow-up lands."
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        raise NotificationProviderError("not implemented")


class ManualPushProvider:
    channel = "push"
    name = "manual"

    def send(self, *, recipient, subject, body, meta=None) -> NotificationResult:
        return NotificationResult(
            provider_message_id=None,
            status="MANUAL_PENDING",
            raw_response={"channel": "push", "recipient": recipient},
        )

    def status(self, *, provider_message_id) -> NotificationStatus:
        return NotificationStatus(
            provider_message_id=provider_message_id,
            status="MANUAL_PENDING", raw_response={},
        )
