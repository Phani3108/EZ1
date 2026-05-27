"""Phase 16a — Ministry-side National Curriculum reference.

These rows are global (no school_id). EduZimOps / Ministry+Provisioner
publishes them once via `POST /ministry/national-curriculum/*` or the
`scripts/import_zimsec.py` seeder. Each school then clicks "Adopt" on a
subject they offer — the unit + topic tree clones into the school's
local `Unit` + `Topic` tables (with back-references via
`Unit.national_unit_id` / `Topic.national_topic_id`).

Publish flow
------------
A subject is invisible to schools until `ministry_published_at` is set
on the NationalSubject row. Schools can browse only published subjects
via `GET /ministry/national-curriculum/subjects?published_only=true`
(default).

Versioning
----------
v1 of this scheme is a flat publish: when EduZimOps changes a national
topic, the school-side clones are NOT auto-updated. Schools see "stale
copy" badges in the UI and choose to re-adopt. Phase 17 will add proper
version semantics; for v16 we deliberately keep it simple.

Tenancy
-------
NO school_id on any of these rows. They are global. The Ministry RBAC
gate (`school:create`) is the only write protection — readers need
`ministry:read` OR `school:manage` (so SchoolAdmins can browse).
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


class NationalSubject(Base):
    __tablename__ = "national_subjects"
    __table_args__ = (
        UniqueConstraint("country", "code", name="uq_national_subject_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country = Column(String(5), nullable=False, default="ZW")
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    # Free-text — describes typical grade levels (e.g.
    # "Forms 1-4 secondary"). Schools narrow this to specific grades
    # in their adoption call.
    description = Column(Text, nullable=True)
    # Publish gate. Until set, schools cannot adopt this subject.
    ministry_published_at = Column(DateTime(timezone=True), nullable=True)
    # Phase 17d — curriculum version. Bumped each time the Ministry
    # re-publishes a revised tree. Schools that adopted v=N see a
    # "stale copy" indicator until they upgrade via
    # POST /curriculum/upgrade-subject (which re-runs the clone
    # preserving local customisations).
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False,
    )


class NationalUnit(Base):
    __tablename__ = "national_units"
    __table_args__ = (
        UniqueConstraint(
            "national_subject_id", "code",
            name="uq_national_unit_subject_code",
        ),
        Index("ix_national_units_subject", "national_subject_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    national_subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("national_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(64), nullable=False)
    sequence_order = Column(Integer, nullable=False, default=0)
    grade_level = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class NationalTopic(Base):
    __tablename__ = "national_topics"
    __table_args__ = (
        UniqueConstraint(
            "national_unit_id", "code",
            name="uq_national_topic_unit_code",
        ),
        Index("ix_national_topics_unit", "national_unit_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    national_unit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("national_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    # One level of sub-topic nesting (same shape as the school-local
    # `Topic` table). Cross-table self-ref.
    parent_topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("national_topics.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(String(255), nullable=False)
    code = Column(String(64), nullable=False)
    sequence_order = Column(Integer, nullable=False, default=0)
    learning_outcomes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
