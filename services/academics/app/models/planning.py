"""Planning models — Phase 11d (T-005, T-010, T-012, T-013).

Four tables introduced in one migration:

  * `school_periods` — the school's own period schedule (number, name,
    start_time, end_time). The promotion path for the T-002 sentinel
    integer `attendance_records.period_number` lands here: once a
    school populates this table, the integer becomes a soft FK by
    convention (we don't add a DB-level FK to preserve the legacy
    daily mode = period_number 0 row).
  * `lesson_plans` — teacher-authored, optionally per-class instances
    of a template. The template flag is set when `class_id` is NULL
    (a reusable library row); per-class instances point back to the
    template via `template_id`.
  * `formative_assessments` — quick polls / exit tickets / in-class
    quizzes. Lightweight relative to the full Assessment model; no
    marks table is attached because the response shape is event-meta
    (count of responses + summary), not graded marks.
  * `formative_responses` — one row per student response to a
    formative_assessment. Body is opaque text or JSON.
  * `exam_seat_plans` — seat-by-row arrangement for an exam sitting.
    Stored as JSON for flexibility; the timer / paper tracking are
    client-side UI concerns.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Time, Date, Integer, Boolean,
    ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── T-010 — school periods ────────────────────────────────────────


class SchoolPeriod(Base):
    """Per-school period schedule (Period 1 = 08:00-08:45, etc.). The
    period_number column on attendance_records (T-002) becomes a soft
    FK to this table once a school populates it. Daily-mode schools
    leave this empty and continue using period_number=0."""
    __tablename__ = "school_periods"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "period_number",
            name="uq_school_period_number",
        ),
        Index("ix_school_periods_school", "school_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    period_number = Column(Integer, nullable=False)
    name = Column(String(80), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── T-005 — lesson plans ──────────────────────────────────────────


class LessonPlan(Base):
    """Lesson plan. When `class_id` is NULL the row is a template;
    when set, it's a per-class instance. `template_id` lets an
    instance point back to its template for cloning / updates."""
    __tablename__ = "lesson_plans"
    __table_args__ = (
        Index("ix_lesson_plans_school_class", "school_id", "class_id"),
        Index("ix_lesson_plans_template", "school_id", "template_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subject_id = Column(UUID_STR, nullable=True)
    class_id = Column(UUID_STR, nullable=True)
    template_id = Column(UUID_STR, nullable=True)
    objectives = Column(Text, nullable=True)
    activities = Column(Text, nullable=True)
    resources = Column(Text, nullable=True)
    scheduled_date = Column(Date, nullable=True)
    scheduled_period_number = Column(Integer, nullable=True)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)


# ─── T-013 — formative assessments ─────────────────────────────────


class FormativeAssessment(Base):
    """Quick poll / exit ticket / in-class quiz.

    Three formative_kinds:
      * 'poll'      — single-choice or multi-choice
      * 'exit_ticket' — short open response
      * 'quiz'      — multi-question quiz (questions in `payload` JSON)

    The grading rubric is intentionally NOT enforced here. Formative
    assessments are about pulse-checks, not grading; if a teacher
    needs a graded score, they use the full Assessment model.
    """
    __tablename__ = "formative_assessments"
    __table_args__ = (
        Index("ix_formative_school_class", "school_id", "class_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    class_id = Column(UUID_STR, nullable=False, index=True)
    subject_id = Column(UUID_STR, nullable=True)
    title = Column(String(200), nullable=False)
    formative_kind = Column(String(32), nullable=False)  # poll | exit_ticket | quiz
    prompt = Column(Text, nullable=False)
    # Optional JSON payload: options for polls, question list for quizzes.
    payload = Column(Text, nullable=True)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)


class FormativeResponse(Base):
    __tablename__ = "formative_responses"
    __table_args__ = (
        UniqueConstraint(
            "formative_assessment_id", "student_id",
            name="uq_formative_response_student",
        ),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    formative_assessment_id = Column(
        UUID_STR,
        ForeignKey("formative_assessments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True),
                          default=_utcnow, nullable=False)


# ─── T-012 — exam seat plans ──────────────────────────────────────


class ExamSeatPlan(Base):
    """Seat arrangement for an exam sitting. The actual layout is a
    JSON blob in `layout_json` — flexibility beats a rigid schema
    here (different schools draw seat plans differently)."""
    __tablename__ = "exam_seat_plans"
    __table_args__ = (
        Index("ix_seat_plan_assessment", "school_id", "assessment_id"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    assessment_id = Column(UUID_STR, nullable=False)
    room = Column(String(80), nullable=True)
    layout_json = Column(Text, nullable=False)  # JSON-encoded grid
    notes = Column(Text, nullable=True)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        onupdate=_utcnow, nullable=False)
