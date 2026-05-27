"""NotificationProvider protocol (Phase 12c)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class NotificationResult:
    """Result of `send()`. `provider_message_id` is the provider's
    own id (used to query status / handle webhooks)."""
    provider_message_id: Optional[str]
    # Normalised: "QUEUED" | "SENT" | "DELIVERED" | "FAILED" | "MANUAL_PENDING"
    status: str
    raw_response: dict


@dataclass(frozen=True)
class NotificationStatus:
    provider_message_id: str
    status: str
    raw_response: dict


class NotificationProviderError(Exception):
    """Raised on integration failure. Routes typically swallow and
    mark the outbox row FAILED with retry_count++."""


class NotificationProvider(Protocol):
    """Each provider serves ONE channel ("sms" | "push" | "email" |
    "whatsapp"). The channel a provider serves is fixed at registration
    time; the registry maps `(channel, provider_name)` → instance.
    """
    channel: str
    name: str

    def send(
        self,
        *,
        recipient: str,
        subject: Optional[str],
        body: str,
        # Provider-specific extras: template id, image url, etc.
        meta: Optional[dict] = None,
    ) -> NotificationResult: ...

    def status(self, *, provider_message_id: str) -> NotificationStatus: ...
