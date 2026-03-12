"""
Communication Service ORM Models
===================================
Announcement (persisted before delivery), NotificationOutbox (async delivery tracking)

Key constraints:
- Announcement soft-deletable
- Outbox: (school_id, status) indexed for polling
- Outbox tracks retry_count, last_attempt_at, error_message
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, ForeignKey,
    UniqueConstraint, Index, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    audience_type = Column(String(20), nullable=False)  # ALL, CLASS, ROLE
    audience_class_id = Column(UUID(as_uuid=True), nullable=True)
    audience_role = Column(String(50), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    outbox_entries = relationship("NotificationOutbox", back_populates="announcement",
                                  cascade="all, delete-orphan")


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", "channel",
                         name="uq_outbox_announcement_user_channel"),
        Index("ix_outbox_school_status", "school_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    announcement_id = Column(UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    channel = Column(String(20), nullable=False)  # IN_APP, SMS
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, SENT, FAILED
    retry_count = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)

    announcement = relationship("Announcement", back_populates="outbox_entries")
