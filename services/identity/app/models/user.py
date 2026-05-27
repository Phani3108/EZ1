import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Table, Text,
    UniqueConstraint, Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


# --- Association Tables ---

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# --- Models ---

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "school_id", name="uq_user_email_school"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    # Phase 15a / I-002: password_hash is NULLABLE — an invited-but-not-
    # yet-activated user has none. Login service refuses to authenticate
    # users with NULL password_hash (see AuthService.login).
    password_hash = Column(String(255), nullable=True)
    # Phase 15a / I-002: phone is captured at invitation-time (preferred
    # SMS / WhatsApp address). Stored unhashed for delivery purposes but
    # NEVER logged in audit details.
    phone = Column(String(32), nullable=True, index=True)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Phase 15a / I-002: lifecycle timestamps for the invitation flow.
    # `invited_at` set when an Invitation row is created targeting this
    # user; `activated_at` set when the invite token is accepted and
    # the password_hash is written.
    invited_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    school_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # None = global role
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles", lazy="selectin")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions", lazy="selectin")


class RefreshToken(Base):
    """Refresh tokens stored in DB (hashed) for rotation and revocation."""
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    jti = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class TokenBlacklist(Base):
    """Blacklisted access tokens (compromised or on logout)."""
    __tablename__ = "token_blacklist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    blacklisted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PasswordResetToken(Base):
    """One-time password reset tokens."""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class LoginAudit(Base):
    """Audit log for all login attempts."""
    __tablename__ = "login_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    school_id = Column(UUID(as_uuid=True), nullable=True)
    success = Column(Boolean, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class UserPreference(Base):
    """
    Per-user accessibility, locale and theme preferences.

    `theme_pref` is server-validated against the user's role so a parent
    cannot escape into the sovereign (admin) theme by spoofing this field.
    A row is created lazily on first PATCH; defaults are derived from the
    user's roles at read time.
    """
    __tablename__ = "user_preferences"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    language = Column(String(8), nullable=False, default="en")          # en | sn | nd
    theme_pref = Column(String(16), nullable=False, default="focus")    # joyful | focus | sovereign
    text_size = Column(String(4), nullable=False, default="md")         # sm | md | lg | xl
    high_contrast = Column(Boolean, nullable=False, default=False)
    read_aloud_enabled = Column(Boolean, nullable=False, default=False)
    reduced_motion = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AuditLog(Base):
    """INFRA-018 / Q-016 (Phase 9): audit log of PII writes + sensitive actions.

    PH9 work-item status:
    - Schema landed here (this commit).
    - Helper `record_audit_event(...)` lives in `app/services/audit.py`.
    - Admin UI to browse this table is deferred to a later Phase 9 sub-task.
    - Full wiring of every PII write across services is the bigger Phase 9
      lift; this commit lands the storage substrate so future writes have
      somewhere to land.

    Retention: 2 years (per `docs/compliance/retention-policy.md`).
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        # Without this index a year of audit data is unqueryable.
        UniqueConstraint("id", name="uq_audit_log_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    actor_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_role = Column(String(32), nullable=True)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Free-form classification, e.g.:
    #   "auth.login.success", "auth.login.failed",
    #   "student.created", "student.deleted",
    #   "fee.payment.recorded", "fee.invoice.created",
    #   "permission.granted", "role.assigned",
    #   "secret.rotated", "data.exported".
    event_type = Column(String(64), nullable=False, index=True)

    # Target of the action. The shape is event-specific; usually
    # {"resource": "<type>", "id": "<uuid>"} or {"email": "<addr>"} for
    # pre-auth events that don't yet have a resolved actor.
    target = Column(Text, nullable=True)

    # Optional structured details. Stored as JSON-encoded text rather than
    # a JSONB column so the table doesn't require Postgres for unit tests.
    details = Column(Text, nullable=True)

    # Network forensics.
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
