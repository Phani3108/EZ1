"""Organisation / staffing models — Phase 11f (T-016, T-017, T-018, T-019).

  * Co-teacher mode (T-016): there's no new table. The existing
    `class_teacher_assignments` unique constraint was
    `(school_id, class_id, academic_year_id)` — exactly one teacher
    per class per year. The accompanying migration relaxes it to
    `(school_id, class_id, academic_year_id, teacher_user_id)` so
    multiple teachers can share a class. Existing authorisation
    checks (which already use `.first()` / `.exists()` style queries
    on the table) keep working unchanged.

  * Head-of-Department (T-017): `HeadOfDepartmentAssignment` —
    (school_id, subject_id, user_id) tuples. Read access for HoD to
    every class teaching their subject is enforced at the route /
    view layer; the table is just the persistence.

  * CPD tracker (T-018): `CpdRecord` — one row per training event
    a teacher attends. Categorical + hours + certificate URI.

  * Self-evaluation (T-019): `SelfEvaluationForm` — one row per
    submission. The form schema is school-defined and stored as
    JSON in `responses_json`. Aggregation at the admin side groups
    by (school_id, term_id).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Date, Integer, Numeric,
    Index, UniqueConstraint,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── T-017 — HoD assignments ───────────────────────────────────────


class HeadOfDepartmentAssignment(Base):
    __tablename__ = "hod_assignments"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "subject_id", "user_id",
            name="uq_hod_subject_user",
        ),
        Index("ix_hod_school_subject", "school_id", "subject_id"),
        Index("ix_hod_school_user", "school_id", "user_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    subject_id = Column(UUID_STR, nullable=False)
    user_id = Column(UUID_STR, nullable=False)
    granted_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


# ─── T-018 — CPD tracker ──────────────────────────────────────────


class CpdRecord(Base):
    __tablename__ = "cpd_records"
    __table_args__ = (
        Index("ix_cpd_school_user", "school_id", "user_id"),
        Index("ix_cpd_school_year", "school_id", "academic_year_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    academic_year_id = Column(UUID_STR, nullable=True)
    # workshop | course | conference | webinar | other
    category = Column(String(32), nullable=False, default="other")
    title = Column(String(200), nullable=False)
    provider = Column(String(200), nullable=True)
    completed_on = Column(Date, nullable=False)
    hours = Column(Numeric(5, 2), nullable=False, default=0)
    certificate_uri = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── T-019 — Self-evaluation forms ────────────────────────────────


class SelfEvaluationForm(Base):
    __tablename__ = "self_evaluation_forms"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "user_id", "term_id",
            name="uq_self_eval_user_term",
        ),
        Index("ix_self_eval_school_term", "school_id", "term_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    user_id = Column(UUID_STR, nullable=False)
    term_id = Column(UUID_STR, nullable=False)
    # The school can configure their own questionnaire shape.
    responses_json = Column(Text, nullable=False)
    overall_reflection = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
