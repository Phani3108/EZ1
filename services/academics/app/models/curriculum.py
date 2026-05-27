"""Phase 16a — School-local curriculum hierarchy.

  * `Unit`   — a logical chunk of a subject for a given grade level
               (e.g. "Form 3 Math · Unit 4: Algebra").
  * `Topic`  — a teachable item under a unit (e.g. "Quadratics").
               Sub-topics nest one level deeper via `parent_topic_id`
               (self-referential, optional).

Both rows are per-school (school_id-scoped). When a school adopts a
Ministry-published ZIMSEC subject via `POST /curriculum/adopt-subject`,
the cloned Unit + Topic rows carry back-references to the matching
NationalUnit / NationalTopic via `national_*_id` columns. Custom rows
have those columns null.

Tagging
-------
Every academic-content row (LessonPlan, Homework, Assessment,
FormativeAssessment, Question) carries a `topic_ids` JSON column
pointing at zero or more `Topic.id` values from this table. The
cross-index endpoint `GET /curriculum/topics/{id}/resources` returns
the inverse — every row that tagged a given topic.

Tenancy
-------
- `Unit.school_id` is FK-like to schools (no formal FK to keep migrations
  simple across the multi-DB layout) and indexed.
- `Topic.school_id` likewise.
- `(school_id, subject_id, code)` is unique on Unit (so unit codes can be
  repeated across subjects but not within the same subject).
- `(school_id, unit_id, code)` is unique on Topic.

Audit
-----
- `curriculum.unit.created` / `curriculum.topic.created` — target carries
  IDs only; details record `{has_parent}` for topics (parent_topic_id
  presence) and `{has_national_ref}` for either model. No names.
- `curriculum.subject.adopted` — see `app/api/curriculum_routes.py`;
  target carries the trio of school_id + subject_id + national_subject_id,
  details record `{units_cloned, topics_cloned}` (counts only).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, Integer,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Unit(Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "subject_id", "code",
            name="uq_curriculum_unit_subject_code",
        ),
        Index("ix_curriculum_units_school_subject",
              "school_id", "subject_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(64), nullable=False)
    sequence_order = Column(Integer, nullable=False, default=0)
    grade_level = Column(String(32), nullable=True)
    # Cross-tenant ref to NationalUnit.id when this row was cloned via
    # the adopt flow. Plain String(36) — no FK across logical tenants.
    national_unit_id = Column(String(36), nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)


class Topic(Base):
    __tablename__ = "curriculum_topics"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "unit_id", "code",
            name="uq_curriculum_topic_unit_code",
        ),
        Index("ix_curriculum_topics_school_unit",
              "school_id", "unit_id"),
        Index("ix_curriculum_topics_school_subject",
              "school_id", "subject_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    unit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Self-ref: parent topic for one level of sub-topic nesting.
    # Keep it one-deep — deeper trees should be modelled as units.
    parent_topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_topics.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(64), nullable=False)
    sequence_order = Column(Integer, nullable=False, default=0)
    # Free-text learning outcomes. ZIMSEC syllabi list these as bullet
    # points — admin pastes them in as a single block; render with
    # whitespace preserved in the UI.
    learning_outcomes = Column(Text, nullable=True)
    national_topic_id = Column(String(36), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)
