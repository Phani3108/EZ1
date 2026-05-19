"""
WhatsApp message tracking — bridges outbox entries to Meta wamids.

A row is created the moment we hand a message to the provider.  Delivery
callbacks update ``last_callback_status`` so we have a complete audit trail
even after the corresponding ``NotificationOutbox`` row has been retried.

The ``provider_message_id`` (wamid) is unique — Meta dedup'es by it on the
wire and we mirror that guarantee in storage.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Index, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        UniqueConstraint("provider_message_id", name="uq_whatsapp_wamid"),
        Index("ix_whatsapp_outbox", "outbox_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    outbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_outbox.id", ondelete="CASCADE"),
        nullable=True,
    )
    to_phone = Column(String(32), nullable=False)
    provider_message_id = Column(String(128), nullable=True, unique=True)
    template_name = Column(String(255), nullable=True)
    body_preview = Column(String(500), nullable=True)
    last_callback_status = Column(String(32), nullable=True)
    last_callback_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
