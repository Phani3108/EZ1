"""
Student Service ORM Models
===========================
Student, Parent, StudentParent (link), Enrollment

Key constraints:
- (school_id, student_code) unique for Student
- (student_id, parent_id) unique for StudentParent
- One primary guardian per student
- One active enrollment per student per academic year
- Student soft-deletable (deleted_at)
"""
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, ForeignKey,
    UniqueConstraint, Text, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class StudentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    TRANSFERRED = "TRANSFERRED"
    GRADUATED = "GRADUATED"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class RelationshipType(str, enum.Enum):
    FATHER = "FATHER"
    MOTHER = "MOTHER"
    GUARDIAN = "GUARDIAN"


class EnrollmentStatus(str, enum.Enum):
    ENROLLED = "ENROLLED"
    WITHDRAWN = "WITHDRAWN"
    PROMOTED = "PROMOTED"


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "student_code", name="uq_student_school_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    student_code = Column(String(50), nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    dob = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    admission_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default=StudentStatus.ACTIVE.value, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    parent_links = relationship("StudentParent", back_populates="student", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")


class Parent(Base):
    __tablename__ = "parents"
    __table_args__ = (
        UniqueConstraint("school_id", "phone", name="uq_parent_school_phone"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    relationship_type = Column(String(20), nullable=False, default=RelationshipType.GUARDIAN.value)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class StudentParent(Base):
    __tablename__ = "student_parents"
    __table_args__ = (
        UniqueConstraint("student_id", "parent_id", name="uq_student_parent"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parents.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    student = relationship("Student", back_populates="parent_links")
    parent = relationship("Parent")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("school_id", "student_id", "academic_year_id",
                         name="uq_enrollment_student_year"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    enrolled_at = Column(Date, default=date.today, nullable=False)
    status = Column(String(20), nullable=False, default=EnrollmentStatus.ENROLLED.value)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    student = relationship("Student", back_populates="enrollments")
