"""Phase 16d — Homework + Lesson-Plan template library.

Sharing pattern (per ADR-022 / decisions locked in the Phase 16 plan):
  * A teacher publishes a homework or lesson plan as a TEMPLATE.
  * The template lives in a per-school library, owned by
    `maintained_by_user_id`.
  * A HoD (Phase 11f role) can publish a template school-wide so
    everyone in the subject sees it.
  * Other teachers INSTANTIATE the template → a real `Homework` or
    `LessonPlan` row is created in their class. Attachments are
    cloned (re-uploaded as fresh `Attachment` rows) so the instance
    is independent of the template.
  * `Homework.template_source_id` (added in the 2026_05_27_021
    migration) lets an instance pull-updates from its source template
    if the maintainer publishes a new version.

Both template tables intentionally do NOT carry `class_id` — that's
the whole point of a template. Per-instance class binding happens at
instantiation time.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Boolean, Date, Integer,
    Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class HomeworkTemplate(Base):
    """Reusable homework pattern."""
    __tablename__ = "homework_templates"
    __table_args__ = (
        Index("ix_homework_templates_school_subject",
              "school_id", "subject_id"),
        Index("ix_homework_templates_school_published",
              "school_id", "is_published_school_wide"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False)
    subject_id = Column(UUID_STR, nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    # Default due-window offset in days (instance UI prefills due_date
    # to today + this many days). Optional.
    default_due_days = Column(Integer, nullable=True)

    # Topic↔Resource cross-index (same shape as Homework / LessonPlan).
    topic_ids = Column(Text, nullable=True)
    # JSON array of grade-level labels this template applies to.
    grade_levels = Column(Text, nullable=True)

    # Visibility flags.
    is_published_school_wide = Column(Boolean, nullable=False, default=False)
    # Chained templates: a template can be derived from another.
    source_template_id = Column(UUID_STR, nullable=True, index=True)
    # Phase 18b — provenance for cross-school adopted templates.
    # When set, this row was cloned from the Ministry-distributed
    # NationalHomeworkTemplate / NationalLessonPlanTemplate with the
    # matching ID. Lets the UI show "Originally from Ministry" and
    # de-duplicates repeat adopt calls (idempotency key with school_id).
    source_national_template_id = Column(UUID_STR, nullable=True, index=True)

    maintained_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)


class LessonPlanTemplate(Base):
    """Reusable lesson-plan pattern."""
    __tablename__ = "lesson_plan_templates"
    __table_args__ = (
        Index("ix_lesson_plan_templates_school_subject",
              "school_id", "subject_id"),
        Index("ix_lesson_plan_templates_school_published",
              "school_id", "is_published_school_wide"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False)
    subject_id = Column(UUID_STR, nullable=True)

    title = Column(String(200), nullable=False)
    # Lesson plans have richer structured fields than homework.
    objectives = Column(Text, nullable=True)
    activities = Column(Text, nullable=True)
    resources = Column(Text, nullable=True)
    # Suggested period number (helps instances slot into a schedule).
    suggested_period_number = Column(Integer, nullable=True)

    topic_ids = Column(Text, nullable=True)
    grade_levels = Column(Text, nullable=True)

    is_published_school_wide = Column(Boolean, nullable=False, default=False)
    source_template_id = Column(UUID_STR, nullable=True, index=True)
    # Phase 18b — provenance for cross-school adopted templates.
    source_national_template_id = Column(UUID_STR, nullable=True, index=True)

    maintained_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)
