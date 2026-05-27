"""Phase 18b — Ministry-distributed (cross-school) template library.

The platform already has per-school HomeworkTemplate / LessonPlanTemplate
(Phase 16d). This module adds the Ministry/NGO-side parallel: templates
that any school can browse and "adopt" into its own local library —
mirroring the ZIMSEC publish/adopt pattern from Phase 16a.

Use-case
--------
NGOs and Ministry curriculum specialists publish canonical homework /
lesson-plan patterns. A SchoolAdmin / HoD adopts the ones their school
wants. The adopted copy lands in the school's own HomeworkTemplate /
LessonPlanTemplate table with a `source_national_template_id` back-ref,
so the school can:
  * edit the local copy freely (does not affect the national original)
  * re-publish school-wide at the HoD's discretion
  * instantiate to classes via the existing Phase 16d/17a flow

Topic resolution
----------------
National templates reference subjects + topics by **code**, not by ID,
because the school-local Subject/Topic IDs differ per-school. At adopt
time we resolve:
  * subject_code → school's local Subject (must already be adopted)
  * each topic_code → school's local Topic ID (best-effort; unresolved
    codes are dropped from the cloned `topic_ids` list and reported back
    so the HoD can patch them)

Attachments
-----------
v1 (Phase 18b) does NOT copy attachments cross-school — only the text
body + topic refs. Cross-tenant attachment cloning is deferred to a
later phase because it requires bypassing the tenant gate on the
Phase 17a clone endpoint. National templates are recommended to use
external URLs in the description body for now.

Tenancy
-------
NO school_id on either table — they are global. Write access gated to
`school:create` (Provisioner / EduZimOps / Ministry per ADR 021).
Reads open to any school with `school:manage`.

Audit invariants (per ADR 018, ADR 024)
---------------------------------------
| Event                           | Target                                                              | Details                                                  |
|---------------------------------|---------------------------------------------------------------------|----------------------------------------------------------|
| `national_template.created`     | `{template_id, kind}`                                              | `{subject_code, topic_codes_count}`. NO title, NO body.  |
| `national_template.published`   | `{template_id, kind}`                                              | `{}`.                                                    |
| `national_template.archived`    | `{template_id, kind}`                                              | `{}`.                                                    |
| `national_template.adopted`     | `{school_id, national_template_id, local_template_id, kind}`       | `{topics_resolved, topics_unresolved}`. NO names.        |
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Integer, UniqueConstraint, Index,
)

from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class NationalHomeworkTemplate(Base):
    """Ministry-distributed homework pattern. Schools adopt into their
    own `homework_templates` table.

    `code` is the natural key; (`code`) is unique so adopt is idempotent
    by source code + adopting school. Schools see only rows where
    `published_at IS NOT NULL AND archived_at IS NULL`.
    """
    __tablename__ = "national_homework_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_national_homework_template_code"),
        Index("ix_national_homework_templates_published", "published_at"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    code = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    # Subject reference — by national code, resolved per-school at
    # adopt time.
    subject_code = Column(String(64), nullable=True)
    # JSON array of national topic codes.
    topic_codes = Column(Text, nullable=True)
    # JSON array of grade-level labels (e.g. ["Form 1", "Form 2"]).
    grade_levels = Column(Text, nullable=True)

    # Default due-window offset in days for instances spawned from
    # adopted copies. Optional.
    default_due_days = Column(Integer, nullable=True)

    # Publish gate. Until set, schools cannot adopt this template.
    published_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )


class NationalLessonPlanTemplate(Base):
    """Ministry-distributed lesson-plan pattern."""
    __tablename__ = "national_lesson_plan_templates"
    __table_args__ = (
        UniqueConstraint(
            "code", name="uq_national_lesson_plan_template_code",
        ),
        Index("ix_national_lesson_plan_templates_published", "published_at"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    code = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    objectives = Column(Text, nullable=True)
    activities = Column(Text, nullable=True)
    resources = Column(Text, nullable=True)
    suggested_period_number = Column(Integer, nullable=True)

    subject_code = Column(String(64), nullable=True)
    topic_codes = Column(Text, nullable=True)
    grade_levels = Column(Text, nullable=True)

    published_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
