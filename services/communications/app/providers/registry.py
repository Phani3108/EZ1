"""NotificationProvider registry (Phase 12c)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

from app.providers.notification_provider import NotificationProvider
from app.providers.sms_providers import (
    AfricasTalkingSmsProvider, ManualSmsProvider,
)
from app.providers.push_providers import (
    FcmPushProvider, ManualPushProvider,
)
from app.providers.email_providers import (
    SendGridEmailProvider, ManualEmailProvider,
)
from app.providers.whatsapp_providers import (
    MetaCloudWhatsAppProvider, ManualWhatsAppProvider,
)


SUPPORTED_CHANNELS = ("sms", "push", "email", "whatsapp")


# (channel, provider_name) → instance
PROVIDER_REGISTRY: dict[tuple[str, str], NotificationProvider] = {
    ("sms", "africastalking"): AfricasTalkingSmsProvider(),
    ("sms", "manual"): ManualSmsProvider(),
    ("push", "fcm"): FcmPushProvider(),
    ("push", "manual"): ManualPushProvider(),
    ("email", "sendgrid"): SendGridEmailProvider(),
    ("email", "manual"): ManualEmailProvider(),
    ("whatsapp", "meta_cloud"): MetaCloudWhatsAppProvider(),
    ("whatsapp", "manual"): ManualWhatsAppProvider(),
}


# System defaults per channel — used when a school hasn't configured.
DEFAULT_PROVIDER_NAMES: dict[str, str] = {
    "sms": "africastalking",
    "push": "fcm",
    "email": "sendgrid",
    "whatsapp": "meta_cloud",
}


def get_provider_for_school_channel(
    db: "Session", school_id: uuid.UUID, channel: str,
) -> NotificationProvider:
    """Resolve the configured provider for (school, channel). Falls
    back to the system default + then to the channel's manual
    provider so callers always get a usable instance."""
    from app.models.notification_config import SchoolNotificationConfig
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"unsupported channel: {channel}")

    row = (
        db.query(SchoolNotificationConfig)
        .filter(
            SchoolNotificationConfig.school_id == school_id,
            SchoolNotificationConfig.channel == channel,
        )
        .first()
    )
    name = (row.provider_name if row else DEFAULT_PROVIDER_NAMES[channel]).lower()
    provider = PROVIDER_REGISTRY.get((channel, name))
    if provider:
        return provider
    # Fallback: school configured a name we don't recognise; degrade
    # to manual rather than crash. The audit log captures this in the
    # config-update audit row.
    return PROVIDER_REGISTRY[(channel, "manual")]
