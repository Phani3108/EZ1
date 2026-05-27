"""Attachment model (Phase 11b / T-008).

A single polymorphic table for file attachments across the platform:
announcements, messages, incident reports (Phase 11e), marks (Phase 11c).
Each row records metadata only; the actual bytes live in object storage
(MinIO / S3 in production, local disk for dev). The `storage_uri` is
the addressable handle.

owner_kind values: "announcement", "message", "incident", "mark".
Service layers enforce that the owner exists + the actor has write
access to the owner before recording the attachment.

Privacy / retention: an attachment inherits its owner's retention. When
the owner is deleted (or redacted), the attachment row should also be
marked deleted by the same actor — this is enforced by the service
layer that owns the parent resource, not by FK because the polymorphic
shape prevents one.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


# Maximum upload size in bytes. 10 MB is generous for a phone photo
# (most are 2-3 MB) but capped to protect storage. Audio recordings
# (T-009 voice notes) compress well below this.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Mime types the platform accepts. Anything outside this list is
# rejected at the upload endpoint. The allow-list is conservative on
# purpose — we'd rather refuse a valid upload than open a vector.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "audio/mpeg", "audio/webm", "audio/ogg",   # T-009 voice notes
    "text/plain",
})


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachment_owner", "school_id", "owner_kind", "owner_id"),
        Index("ix_attachment_school", "school_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # Polymorphic owner — see module docstring for permitted values.
    owner_kind = Column(String(32), nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    # storage_uri is opaque to the API. Production = s3://bucket/key,
    # dev = file:///var/lib/eduzim/attachments/xxx.
    storage_uri = Column(Text, nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)
