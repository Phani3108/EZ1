"""Per-school per-channel notification provider config (Phase 12c)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SchoolNotificationConfig(Base):
    """One row per (school, channel). Picks the provider for that
    channel. When no row exists, the channel's system default
    (see providers/registry.DEFAULT_PROVIDER_NAMES) applies."""
    __tablename__ = "school_notification_config"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "channel",
            name="uq_school_notification_channel",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # "sms" | "push" | "email" | "whatsapp"
    channel = Column(String(16), nullable=False)
    # Provider name — see providers/registry.PROVIDER_REGISTRY.
    provider_name = Column(String(32), nullable=False)
    # Provider-specific opaque config (e.g. africastalking username,
    # sendgrid sender). JSON-text for portability.
    config_json = Column(Text, nullable=True)
    updated_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=_utcnow, onupdate=_utcnow,
    )
