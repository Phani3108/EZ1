"""
School Service ORM Models
==========================
School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment

Key constraints:
- (school_id, name, section) unique for Class
- (school_id, code) unique for Subject
- One active academic year per school
- Term dates within academic year range
- One teacher per class per academic year
"""

import uuid
from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, ForeignKey,
    UniqueConstraint, Text, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Province(Base):
    """Reference table: Zimbabwe provinces (MoPSE codes)."""
    __tablename__ = "provinces"

    code = Column(String(8), primary_key=True)            # e.g. "HRE"
    name = Column(String(100), nullable=False, unique=True)
    region = Column(String(100), nullable=False)
    capital = Column(String(100), nullable=False)
    country = Column(String(5), nullable=False, default="ZW")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class District(Base):
    """Reference table: districts under each province."""
    __tablename__ = "districts"
    __table_args__ = (
        UniqueConstraint("province_code", "name", name="uq_district_province_name"),
    )

    code = Column(String(16), primary_key=True)           # e.g. "hre-cn"
    name = Column(String(150), nullable=False)
    province_code = Column(String(8), ForeignKey("provinces.code", ondelete="CASCADE"),
                           nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class School(Base):
    __tablename__ = "schools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    country = Column(String(5), nullable=False, default="ZW")
    timezone = Column(String(100), nullable=False, default="Africa/Harare")
    # Optional geography FKs (nullable so existing tenants are unaffected)
    province_code = Column(String(8), ForeignKey("provinces.code", ondelete="SET NULL"),
                           nullable=True, index=True)
    district_code = Column(String(16), ForeignKey("districts.code", ondelete="SET NULL"),
                           nullable=True, index=True)
    school_type = Column(String(20), nullable=True)        # PRIMARY | SECONDARY | COMBINED
    # DEC-009 / PH8-1: tenancy tier. `shared` = row-level isolation in the
    # cluster-wide academics_db (default for most schools). `dedicated` =
    # this school has its own DB; the shared library's TenancyResolver
    # routes traffic to it. `district` = traffic routes to a
    # district-grouped DB (Ministry rollouts).
    tenancy_tier = Column(
        String(20), nullable=False, default="shared", server_default="shared",
        index=True,
    )
    # Optional district code for tier=district; null on shared / dedicated.
    # Joined against `districts.code` at the routing layer.
    district_routing_code = Column(String(16), nullable=True)
    # PH8-3 maintenance window: when a promotion job is mid-flight, writes
    # are blocked so the snapshot is consistent. Cleared on success or
    # rollback. Always false for tier=shared schools.
    maintenance_mode = Column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    principal_name = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    founded_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    terms = relationship("Term", back_populates="academic_year", cascade="all, delete-orphan")


class Term(Base):
    __tablename__ = "terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    academic_year = relationship("AcademicYear", back_populates="terms")


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("school_id", "name", "section", name="uq_class_school_name_section"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    section = Column(String(20), nullable=False, default="A")
    capacity = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("school_id", "code", name="uq_subject_school_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ClassTeacherAssignment(Base):
    __tablename__ = "class_teacher_assignments"
    __table_args__ = (
        # Phase 11f / T-016 (co-teacher mode). The old unique was
        # `(school_id, class_id, academic_year_id)` — exactly one
        # teacher per class per year. T-016 needs multiple teachers
        # per class, so the constraint now includes teacher_user_id.
        # That preserves "no duplicate (class, year, teacher)
        # assignment" while allowing the same (class, year) to host
        # several teachers.
        UniqueConstraint(
            "school_id", "class_id", "academic_year_id", "teacher_user_id",
            name="uq_class_teacher_year_teacher",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    teacher_user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
