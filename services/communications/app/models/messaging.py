"""
Parent-Teacher Messaging Models (Phase 11b / T-011)
====================================================

Two-table domain:

  * `MessageThread` — one row per (parent, teacher) pair within a school.
    Inbox sorting + unread counts are denormalised onto the row so the
    "list my threads" query is a single index lookup, not a group-by
    over the messages table.

  * `Message` — append-only message rows. Soft-delete via `redacted_at`
    (the row stays so threading integrity is preserved; only the body
    becomes "[redacted]" — important for audit). Hard-delete only via
    the retention policy purge job.

Why per-(parent, teacher) and not per-(parent, teacher, student): the
1:1 model from task.md §2.1 is conversation-centric, not subject-centric.
A teacher who teaches three of a parent's children should not see three
duplicate threads in their inbox. Which child a specific message is
about is conversational context, not a thread-key concern.

Authorisation gating is handled at the service / API layer — a teacher
can only thread with parents whose children are enrolled in one of the
teacher's classes. This stops the obvious abuse vector (a teacher
discovering arbitrary parents by id).

Audit: every thread creation and every message send is written to
`audit_log` via the standard `record_audit_event(...)` substrate. The
audit `target` carries the thread / message id; `details` lists
event-meta only (sender_role, length) — NEVER the message body. The
body lives in `messages.body` which is itself subject to the retention
policy (90 days default; extendable by school).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Integer, ForeignKey, UniqueConstraint, Index, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class MessageThread(Base):
    __tablename__ = "message_threads"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "parent_user_id", "teacher_user_id",
            name="uq_message_thread_pair",
        ),
        Index("ix_msg_thread_parent", "school_id", "parent_user_id"),
        Index("ix_msg_thread_teacher", "school_id", "teacher_user_id"),
        Index("ix_msg_thread_last_message", "school_id", "last_message_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    parent_user_id = Column(UUID(as_uuid=True), nullable=False)
    teacher_user_id = Column(UUID(as_uuid=True), nullable=False)
    # Denormalised for inbox sorting; updated whenever a Message lands.
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    # Denormalised unread counts per side. Updated by the messaging
    # service when a message is sent / read.
    parent_unread_count = Column(Integer, nullable=False, default=0)
    teacher_unread_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "Message", back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_message_thread_created", "thread_id", "created_at"),
        Index("ix_message_school", "school_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_user_id = Column(UUID(as_uuid=True), nullable=False)
    # "Teacher" | "Parent" — captured at send-time so a future role
    # change doesn't rewrite history.
    sender_role = Column(String(32), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    # Soft delete — the row stays so the thread doesn't develop holes,
    # but the body becomes "[redacted]" on read. Hard delete happens via
    # the retention purge job after the legal hold period.
    redacted_at = Column(DateTime(timezone=True), nullable=True)
    redacted_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    # When the OTHER party read this message (null = unread).
    read_at = Column(DateTime(timezone=True), nullable=True)

    thread = relationship("MessageThread", back_populates="messages")
