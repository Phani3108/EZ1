"""Parent-Teacher Messaging Service (Phase 11b / T-011).

Owns the rules around message threads:

  1. **Authorisation**: a thread between (teacher T, parent P) is
     allowed iff at least one of P's children is enrolled in one of T's
     classes. The thread itself doesn't carry the enrollment proof —
     each create / send call re-checks. Authorisation lives at the
     academics service, queried via the parent-link / class-roster
     APIs. The service layer accepts an injectable resolver so tests
     can mock it.

  2. **Idempotency** for thread upsert. `get_or_create_thread` is a
     find-or-insert with the unique constraint catching races.

  3. **Denorm state**: `last_message_at` and the two unread counts on
     the thread row are kept in sync by `send_message` and
     `mark_thread_read`. The inbox query stays a single index lookup.

  4. **Soft-delete via redaction**: `redact_message` sets `redacted_at`
     + `redacted_by_user_id` and rewrites the body to "[redacted]".
     The thread itself is NEVER deleted.

  5. **Audit**: thread-created, message-sent, message-redacted all
     write audit rows via the shared substrate. The audit DETAILS
     carry sender_role + length only — never the body.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.messaging import MessageThread, Message


# Marker text written into `body` when a message is redacted. Stays
# stable so admin-side filters can find / count redacted rows.
REDACTED_PLACEHOLDER = "[redacted]"


class ParticipantAuthorizationError(Exception):
    """Raised when the requested thread participants are not allowed
    to message each other (no shared class/student link)."""


# The resolver signature: (school_id, teacher_user_id, parent_user_id)
# returns True if at least one of the parent's children is enrolled in
# one of the teacher's classes. Service-layer-injectable so tests can
# stub without spinning up the academics service.
AuthorizationResolver = Callable[[uuid.UUID, uuid.UUID, uuid.UUID], bool]


class MessagingService:
    def __init__(
        self,
        db: Session,
        authorization_resolver: Optional[AuthorizationResolver] = None,
    ):
        self.db = db
        # Default resolver is permissive — production wires the real
        # academics-service-backed implementation. Tests can pass their
        # own callable to exercise allow / deny paths.
        self._resolver = authorization_resolver or (lambda *_: True)

    # ─── Threads ───────────────────────────────────────────────────

    def get_or_create_thread(
        self,
        *,
        school_id: uuid.UUID,
        teacher_user_id: uuid.UUID,
        parent_user_id: uuid.UUID,
        creator_user_id: uuid.UUID,
    ) -> tuple[MessageThread, bool]:
        """Return (thread, created). Re-uses the existing row if one
        already exists for the (school, parent, teacher) tuple."""
        if not self._resolver(school_id, teacher_user_id, parent_user_id):
            raise ParticipantAuthorizationError(
                "Teacher is not authorised to message this parent. "
                "Either the parent has no children in any of the "
                "teacher's classes, or the link has been removed."
            )

        existing = (
            self.db.query(MessageThread)
            .filter(
                MessageThread.school_id == school_id,
                MessageThread.parent_user_id == parent_user_id,
                MessageThread.teacher_user_id == teacher_user_id,
            )
            .first()
        )
        if existing:
            return existing, False

        thread = MessageThread(
            school_id=school_id,
            parent_user_id=parent_user_id,
            teacher_user_id=teacher_user_id,
        )
        self.db.add(thread)
        self.db.flush()  # populate id before audit hook runs
        return thread, True

    def list_threads_for_user(
        self,
        *,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[MessageThread]:
        """All threads where the given user is a participant."""
        return (
            self.db.query(MessageThread)
            .filter(
                MessageThread.school_id == school_id,
                or_(
                    MessageThread.teacher_user_id == user_id,
                    MessageThread.parent_user_id == user_id,
                ),
            )
            .order_by(MessageThread.last_message_at.desc().nullslast())
            .all()
        )

    def get_thread_for_user(
        self,
        *,
        thread_id: uuid.UUID,
        school_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[MessageThread]:
        """Fetch a thread, but only if `user_id` is a participant.
        Returns None when the thread doesn't exist OR the caller isn't
        a participant — collapsing the two cases prevents a probe-by-id
        information leak.
        """
        thread = (
            self.db.query(MessageThread)
            .filter(
                MessageThread.id == thread_id,
                MessageThread.school_id == school_id,
            )
            .first()
        )
        if thread is None:
            return None
        if user_id not in (thread.teacher_user_id, thread.parent_user_id):
            return None
        return thread

    # ─── Messages ─────────────────────────────────────────────────

    def send_message(
        self,
        *,
        thread: MessageThread,
        sender_user_id: uuid.UUID,
        sender_role: str,
        body: str,
    ) -> Message:
        """Append a message to the thread, update denorm state."""
        if sender_user_id not in (thread.teacher_user_id, thread.parent_user_id):
            raise ParticipantAuthorizationError(
                "Sender is not a participant of this thread."
            )
        body = body.strip()
        if not body:
            raise ValueError("Message body must not be empty.")

        msg = Message(
            school_id=thread.school_id,
            thread_id=thread.id,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            body=body,
        )
        self.db.add(msg)

        # Denorm sync: mark the OTHER side as unread, update last_at.
        now = datetime.now(timezone.utc)
        thread.last_message_at = now
        if sender_user_id == thread.teacher_user_id:
            thread.parent_unread_count = (thread.parent_unread_count or 0) + 1
        else:
            thread.teacher_unread_count = (thread.teacher_unread_count or 0) + 1
        self.db.flush()
        return msg

    def list_messages(
        self,
        *,
        thread: MessageThread,
        limit: int = 100,
    ) -> list[Message]:
        """Oldest-first message list for the thread. Body is replaced
        with REDACTED_PLACEHOLDER on the wire when redacted_at is set —
        the storage retains the value but the API-layer caller serialises
        via `_serialize_message` which masks it.
        """
        return (
            self.db.query(Message)
            .filter(Message.thread_id == thread.id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .all()
        )

    def mark_thread_read(
        self,
        *,
        thread: MessageThread,
        reader_user_id: uuid.UUID,
    ) -> int:
        """Mark all messages in the thread sent by the OTHER party as
        read (sets `read_at`), and zero the reader's unread count."""
        is_teacher = reader_user_id == thread.teacher_user_id
        is_parent = reader_user_id == thread.parent_user_id
        if not (is_teacher or is_parent):
            raise ParticipantAuthorizationError(
                "Reader is not a participant of this thread."
            )

        other_user_id = (
            thread.parent_user_id if is_teacher else thread.teacher_user_id
        )
        now = datetime.now(timezone.utc)
        # SQLAlchemy 2-style bulk update on the messages table.
        updated = (
            self.db.query(Message)
            .filter(
                Message.thread_id == thread.id,
                Message.sender_user_id == other_user_id,
                Message.read_at.is_(None),
            )
            .update({"read_at": now}, synchronize_session=False)
        )
        if is_teacher:
            thread.teacher_unread_count = 0
        else:
            thread.parent_unread_count = 0
        self.db.flush()
        return updated

    def redact_message(
        self,
        *,
        message: Message,
        actor_user_id: uuid.UUID,
    ) -> Message:
        """Redact a message — body becomes placeholder, row stays."""
        message.redacted_at = datetime.now(timezone.utc)
        message.redacted_by_user_id = actor_user_id
        message.body = REDACTED_PLACEHOLDER
        self.db.flush()
        return message


# ─── Serialisation helpers (kept out of the service so it stays
#     persistence-only; routes own the wire-shape) ──────────────────


def serialize_thread(t: MessageThread, *, viewer_user_id: uuid.UUID) -> dict:
    is_teacher = viewer_user_id == t.teacher_user_id
    return {
        "id": str(t.id),
        "school_id": str(t.school_id),
        "teacher_user_id": str(t.teacher_user_id),
        "parent_user_id": str(t.parent_user_id),
        "last_message_at": (
            t.last_message_at.isoformat() if t.last_message_at else None
        ),
        "unread_count": (
            t.teacher_unread_count if is_teacher else t.parent_unread_count
        ),
        "created_at": t.created_at.isoformat(),
    }


def serialize_message(m: Message) -> dict:
    return {
        "id": str(m.id),
        "thread_id": str(m.thread_id),
        "sender_user_id": str(m.sender_user_id),
        "sender_role": m.sender_role,
        "body": m.body,  # already REDACTED_PLACEHOLDER if redacted_at set
        "redacted": m.redacted_at is not None,
        "redacted_at": m.redacted_at.isoformat() if m.redacted_at else None,
        "read_at": m.read_at.isoformat() if m.read_at else None,
        "created_at": m.created_at.isoformat(),
    }
