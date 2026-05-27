"""Phase 15a — InviteOutbox.

Persistent record of every dispatched invitation. Separate from
NotificationOutbox because that one has a hard FK on `announcement_id`;
invites are not announcements.

Privacy contract:
  * `recipient_phone` / `recipient_email` are stored here for delivery
    bookkeeping and retry. They are NEVER copied into the audit log's
    `target` or `details` (ADR 018).
  * The 6-digit `manual_code` is stored so an admin can re-read it
    over the phone if the original SMS / WhatsApp message bounced.
    Pre-image of the URL-form token is NOT stored (only the
    identity-side hash is, in the `invitations` table).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class InviteOutbox(Base):
    __tablename__ = "invite_outbox"
    __table_args__ = (
        Index("ix_invite_outbox_school_status", "school_id", "status"),
        Index("ix_invite_outbox_invitation", "invitation_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)

    # Identity-side invitation row. String(36) — no FK across services.
    invitation_id = Column(String(36), nullable=False)

    # sms | whatsapp | email | manual
    channel = Column(String(16), nullable=False)
    provider_name = Column(String(32), nullable=True)

    recipient_email = Column(String(255), nullable=True)
    recipient_phone = Column(String(32), nullable=True)

    # Rendered body that was/will be sent. Free text. Kept here so an
    # admin can re-read what they sent. NOT logged in audit details.
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)

    # 6-digit code for the manual-mode fallback (offline path). The
    # admin reads this over the phone. Stored verbatim because that's
    # what the invitee will type into the parent-web /invite/code
    # form. The same code lives on the identity `invitations` row.
    manual_code = Column(String(6), nullable=True)

    # Identity-side URL where the invitee can land. Built at dispatch
    # time from FRONTEND_URL + the raw token. NOT a foreign-key — just
    # a convenience so the admin UI can show "the link we sent".
    invite_url = Column(String(500), nullable=True)

    # queued | sent | delivered | failed | manual_pending
    status = Column(String(20), nullable=False, default="queued")
    retry_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
