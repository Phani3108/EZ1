"""Cross-service audit log (Phase 9 / INFRA-018 / Q-016).

The substrate that lets every service record PII writes and sensitive
actions to a per-service `audit_log` table. Centralised aggregation
(e.g., shipping to a separate audit DB or SIEM) is a follow-up — for
now each service keeps its own rows in its own DB, scoped by
`school_id` like every other domain table.

What this module provides:

  1. `AuditLogMixin` — SQLAlchemy declarative mixin with the canonical
     column set. Each service's model file does:

         from eduzim_shared.audit import AuditLogMixin
         from app.database import Base

         class AuditLog(AuditLogMixin, Base):
             __tablename__ = "audit_log"

     The shape stays in sync across services by keeping the columns
     in one place.

  2. `record_audit_event(db, ModelClass, ...)` — generic write helper.
     Same contract as the per-service helper that was in identity:
     never raises into the caller; logs on failure.

  3. `Event` — frozen dataclass of standard event names so callers
     don't typo them. Use `Event.STUDENT_CREATED` etc.

Privacy notes:
  * ADR 007 / Phase 9: `details` SHOULD NOT include PII unless the
    event explicitly captures it (e.g., a name change event needs to
    record old + new, by definition). Don't dump full student rows.
  * `ip_address` and `user_agent` are minimised — for production, see
    the per-service config. We collect IP only for security-relevant
    events (login, role grants, payments).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# ─────────────────── Canonical schema ─────────────────────────────


class AuditLogMixin:
    """Declarative mixin defining the canonical audit_log columns.

    Service usage:

        from eduzim_shared.audit import AuditLogMixin
        from app.database import Base

        class AuditLog(AuditLogMixin, Base):
            __tablename__ = "audit_log"

    Keeping the column definitions in one place means a schema drift
    across services is impossible. Adding a column to the canonical
    set means a new Alembic migration per service — but the column
    definition only changes here.
    """
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
    # Free-form classification. Use the `Event.*` constants below for
    # type safety.
    event_type = Column(String(64), nullable=False, index=True)
    # JSON-encoded as text (no JSONB; portable to SQLite for tests).
    target = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    # Network forensics.
    ip_address = Column(String(45), nullable=True)    # IPv6 max length
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)


# ─────────────────── Canonical event names ─────────────────────────


@dataclass(frozen=True)
class _Events:
    """Use these constants instead of stringly-typed event_type values.

    New event names should be ADDED here, not invented at call sites.
    Anything not in this list is technically valid (event_type is a
    free-form string), but linting against this constant set catches
    typos that would split metrics across multiple buckets.
    """
    # ─ Auth ─
    LOGIN_SUCCESS: str = "auth.login.success"
    LOGIN_FAILED: str = "auth.login.failed"
    LOGOUT: str = "auth.logout"
    TOKEN_REFRESH: str = "auth.token.refresh"
    PASSWORD_RESET: str = "auth.password.reset"
    ROLE_GRANTED: str = "auth.role.granted"
    ROLE_REVOKED: str = "auth.role.revoked"

    # ─ Students ─
    STUDENT_CREATED: str = "student.created"
    STUDENT_UPDATED: str = "student.updated"
    STUDENT_DELETED: str = "student.deleted"

    # ─ Parents ─
    PARENT_CREATED: str = "parent.created"
    PARENT_UPDATED: str = "parent.updated"
    PARENT_LINKED: str = "parent.linked_to_student"
    PARENT_UNLINKED: str = "parent.unlinked_from_student"

    # ─ Attendance ─
    ATTENDANCE_BATCH_RECORDED: str = "attendance.batch.recorded"

    # ─ Assessment ─
    ASSESSMENT_CREATED: str = "assessment.created"
    MARKS_RECORDED: str = "assessment.marks.recorded"

    # ─ Communications ─
    ANNOUNCEMENT_CREATED: str = "announcement.created"
    ANNOUNCEMENT_DELETED: str = "announcement.deleted"

    # ─ Finance ─
    FEE_STRUCTURE_CREATED: str = "fee.structure.created"
    INVOICE_CREATED: str = "fee.invoice.created"
    INVOICE_VOIDED: str = "fee.invoice.voided"
    PAYMENT_RECORDED: str = "fee.payment.recorded"

    # ─ Communications ─
    ANNOUNCEMENT_CREATED: str = "announcement.created"
    ANNOUNCEMENT_DELETED: str = "announcement.deleted"

    # ─ Data rights (ADR 007) ─
    DATA_EXPORT_SCHOOL: str = "data.export.school"
    DATA_EXPORT_PARENT: str = "data.export.parent"

    # ─ Tenancy (DEC-009 / Phase 8) ─
    TENANCY_PROMOTION_STARTED: str = "tenancy.promotion.started"
    TENANCY_PROMOTION_COMPLETED: str = "tenancy.promotion.completed"
    TENANCY_PROMOTION_FAILED: str = "tenancy.promotion.failed"

    # ─ Operational ─
    SECRET_ROTATED: str = "ops.secret.rotated"


Event = _Events()


# ─────────────────── Write helper ─────────────────────────────────


def record_audit_event(
    db: Session,
    audit_model,
    *,
    event_type: str,
    school_id: uuid.UUID,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_role: Optional[str] = None,
    target: Optional[dict] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Write one audit row. Never raises into the caller.

    Parameters
    ----------
    db : Session
        Service's request-scoped DB session.
    audit_model : type
        The service's `AuditLog` SQLAlchemy class. Pass the class itself,
        not an instance.
    event_type : str
        Use the constants in `Event` (e.g., `Event.STUDENT_CREATED`).
    school_id : uuid.UUID
        Always required — every audit row is school-scoped, like every
        other row in the system.
    actor_user_id : uuid.UUID | None
        The user who performed the action. None for system events
        (Kafka consumers, scheduled jobs).
    target : dict | None
        Shape is event-specific. Conventionally
        `{"resource": "<type>", "id": "<uuid>"}` for resource events,
        `{"email": "<addr>"}` for pre-auth events.
    details : dict | None
        Optional structured payload. PRIVACY: don't dump full PII
        objects here. Capture only the fields the event needs.

    Failure handling
    ----------------
    If the DB write fails (e.g., during shutdown), we log loudly so
    operators can see the gap, but we do NOT abort the caller's work.
    A login that crashes because the audit table is full is worse than
    a login that succeeds with no audit row.
    """
    try:
        row = audit_model(
            id=uuid.uuid4(),
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            school_id=school_id,
            event_type=event_type,
            target=json.dumps(target) if target is not None else None,
            details=json.dumps(details) if details is not None else None,
            ip_address=ip_address,
            user_agent=(user_agent[:255] if user_agent else None),
            request_id=request_id,
        )
        db.add(row)
        db.flush()  # surface constraint failures here, not at commit
    except Exception as e:
        logger.error(
            "audit.write_failed event=%s school=%s actor=%s err=%s",
            event_type, school_id, actor_user_id, e,
        )
