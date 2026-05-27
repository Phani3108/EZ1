"""Phase 15a / I-001: Invitation model.

A pre-staged User row + a one-time activation token. The same primitive
covers four invitation flows:

  * SchoolAdmin invite (issued by Ministry+Provisioner / EduZimOps when
    a new school is created).
  * Teacher invite (issued from bulk-teacher import in academics).
  * Parent invite (issued from bulk-student import in academics, when a
    parent contact column is present).
  * Self-claim invite (admin manually invites someone they linked).

Privacy contract (ADR 018):
  * `contact_email` and `contact_phone` live on this row (we need them
    to send the invite) but they MUST NOT appear in any AuditLog row's
    `details` or `target` JSON. The audit `target` carries
    invitation_id + role + school_id only. See `audit.py` for the
    enforced shape.

Token contract:
  * `token_hash = sha256(raw_token).hexdigest()` — same crypto as
    `PasswordResetToken`. The raw token is shown to the caller exactly
    once on creation and to the manual-mode admin via a separate
    `manual_code` field (6 digits — short enough to read over the
    phone but rate-limited on accept).
  * The token-bearing URL form is the default; the `manual_code` form
    is the offline fallback. Both resolve to the same row.

Idempotency:
  * Unique constraint on `(school_id, role, COALESCE(contact_email, contact_phone))`
    so we never queue two duplicate invitations for the same
    (school, role, contact) tuple. Re-invoking POST /invitations with
    the same input is a no-op on the row but DOES re-dispatch via
    InviteDispatcher (the caller gets the existing token back).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Integer, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        # SQLite doesn't enforce COALESCE-style unique indexes, but
        # Postgres will. We also enforce this at the application layer
        # in `POST /invitations` so the SQLite test path is still safe.
        Index("ix_invitations_school_role", "school_id", "role"),
        Index("ix_invitations_token_hash", "token_hash"),
        Index("ix_invitations_manual_code", "manual_code"),
        Index("ix_invitations_user_id", "user_id"),
        UniqueConstraint(
            "school_id", "role", "contact_email", "contact_phone",
            name="uq_invitations_school_role_contact",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)

    # Hash of the URL-form token (sha256 hex). The raw token is shown
    # to the caller once on create + once on resend.
    token_hash = Column(String(255), nullable=False)

    # 6-digit manual code (e.g., "847301") for the offline fallback.
    # Same row — either accept path lands the same User activation.
    manual_code = Column(String(6), nullable=False)

    # Role to grant on accept. Free-form string matching the role
    # `name` column in the seed (SchoolAdmin | Teacher | Parent |
    # Student | Ministry | Provisioner | EduZimOps).
    role = Column(String(32), nullable=False)

    # The pre-staged user that this invite will activate. The row is
    # created at the moment we generate the invitation; password_hash
    # stays NULL until the user accepts.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional cross-service back-reference. e.g., for a Parent invite,
    # this is the academics-side Parent.id; for a Teacher invite it
    # might be empty (the User row + ClassTeacherAssignment is enough).
    # Stored as String(36) so we don't bind on Postgres UUID type.
    target_resource_id = Column(String(36), nullable=True)
    target_resource_type = Column(String(32), nullable=True)

    # Where we tried to send this — what shows up in the
    # `channel_attempted` audit field. NEVER includes the actual
    # address; that's on this row.
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(32), nullable=True)
    channel_attempted = Column(String(16), nullable=True)
    channel_sent_at = Column(DateTime(timezone=True), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    created_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
