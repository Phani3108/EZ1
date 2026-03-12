"""
Assessment & Marks ORM Models
================================
assessments — teacher-created assessment definitions
marks       — per-student grades for each assessment
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Numeric, Boolean, Date,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from app.database import Base

# Use String(36) for UUID portability across SQLite / PostgreSQL
UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ───────────── Assessment ─────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    academic_year_id = Column(UUID_STR, nullable=False)
    term_id = Column(UUID_STR, nullable=False)
    class_id = Column(UUID_STR, nullable=False, index=True)
    subject_id = Column(UUID_STR, nullable=False)
    name = Column(String(200), nullable=False)
    assessment_type = Column(
        SAEnum("QUIZ", "TEST", "EXAM", "ASSIGNMENT", name="assessment_type_enum",
               create_constraint=False, native_enum=False),
        nullable=False,
    )
    date = Column(Date, nullable=False)
    max_marks = Column(Numeric(6, 2), nullable=False)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    marks = relationship("Mark", back_populates="assessment", lazy="select")

    __table_args__ = (
        Index("ix_assessments_class_term", "class_id", "term_id"),
        Index("ix_assessments_class_subject_term", "class_id", "subject_id", "term_id"),
    )


# ───────────── Mark ─────────────

class Mark(Base):
    __tablename__ = "marks"

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    assessment_id = Column(UUID_STR, ForeignKey("assessments.id"), nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False, index=True)
    marks = Column(Numeric(6, 2), nullable=True)  # null when absent
    is_absent = Column(Boolean, default=False, nullable=False)
    remarks = Column(String(500), nullable=True)
    graded_by = Column(UUID_STR, nullable=False)
    graded_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    assessment = relationship("Assessment", back_populates="marks")

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_mark_assessment_student"),
        Index("ix_marks_student_school", "student_id", "school_id"),
    )
