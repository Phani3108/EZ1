"""Student life models — Phase 11e (T-004, T-006, T-003).

Three domains in one module:

  * `BehaviorIncident` — T-004. Teacher-created log of disciplinary
    / behavioural events; school admins can roll them up in reports.
    Severity field constrained to (minor / moderate / serious /
    critical). Notification of parent/guardian is a follow-up — for
    now we record the fact (`parent_notified_at`) when the teacher
    confirms they've reached out.

  * `SubstituteGrant` — T-006. Time-bound read-grant from teacher A
    (the absent one) to teacher B (the substitute). The grant is
    issued by a school admin to prevent teachers from grant-stacking
    on their own behalf. While the grant is active, the substitute
    can read teacher A's roster + lesson plans for the listed classes.
    The grant is read-only on purpose.

  * `Homework` + `HomeworkSubmission` — T-003. Teacher assigns; student
    (via parent or self) submits; teacher grades. The submission body
    can carry text + attachment ids (the T-008 polymorphic attachments
    machinery accepts owner_kind="homework").
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Date, Integer, ForeignKey,
    Index, UniqueConstraint,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── T-004 — Behaviour incidents ──────────────────────────────────


class BehaviorIncident(Base):
    __tablename__ = "behavior_incidents"
    __table_args__ = (
        Index("ix_incident_school_student", "school_id", "student_id"),
        Index("ix_incident_school_date", "school_id", "occurred_at"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False)
    class_id = Column(UUID_STR, nullable=True)
    reported_by = Column(UUID_STR, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False,
                         default=_utcnow)
    # minor | moderate | serious | critical — validated at route.
    severity = Column(String(16), nullable=False, default="minor")
    # Free-form categorical (bullying / late / uniform / disruption / other).
    category = Column(String(32), nullable=False, default="other")
    summary = Column(String(500), nullable=False)
    details = Column(Text, nullable=True)
    parent_notified_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── T-006 — Substitute grants ─────────────────────────────────────


class SubstituteGrant(Base):
    """Read-grant: substitute (grantee) → absent teacher's class set,
    valid for the [starts_at, ends_at] window."""
    __tablename__ = "substitute_grants"
    __table_args__ = (
        Index("ix_substitute_active", "school_id", "ends_at", "revoked_at"),
        Index("ix_substitute_grantee", "school_id", "grantee_user_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    absent_teacher_user_id = Column(UUID_STR, nullable=False)
    grantee_user_id = Column(UUID_STR, nullable=False)
    # JSON-encoded list of class ids the grant covers. NULL = all of
    # the absent teacher's classes.
    class_ids_json = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    granted_by_user_id = Column(UUID_STR, nullable=False)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(UUID_STR, nullable=True)


# ─── T-003 — Homework + submissions ────────────────────────────────


class Homework(Base):
    __tablename__ = "homework"
    __table_args__ = (
        Index("ix_homework_school_class", "school_id", "class_id"),
        Index("ix_homework_due", "school_id", "due_date"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    class_id = Column(UUID_STR, nullable=False)
    subject_id = Column(UUID_STR, nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    due_date = Column(Date, nullable=False)
    # Phase 16b — Topic↔Resource cross-index. JSON array of Topic UUIDs.
    topic_ids = Column(Text, nullable=True)
    # Phase 16d — when this Homework was instantiated from a template.
    template_source_id = Column(UUID_STR, nullable=True, index=True)
    assigned_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)


class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"
    __table_args__ = (
        UniqueConstraint(
            "homework_id", "student_id",
            name="uq_homework_submission_student",
        ),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    homework_id = Column(
        UUID_STR,
        ForeignKey("homework.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False, index=True)
    body = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False,
                          default=_utcnow)
    grade_marks = Column(String(20), nullable=True)
    grade_remarks = Column(String(500), nullable=True)
    graded_by = Column(UUID_STR, nullable=True)
    graded_at = Column(DateTime(timezone=True), nullable=True)
