"""Read-side projection table mappings (PH2-11).

These are the SAME tables maintained by the reporting-service consumer.
Academics opens a SECOND SQLAlchemy connection (reporting_db.py) and uses
these mappings to query them read-only when serving /api/v1/reports/*.

This module deliberately does NOT use `app.database.Base` — projection
tables live in a different database, and binding them to the academics
Base would cause `Base.metadata.create_all()` (which test fixtures call)
to try to materialise projection tables in academics_db, which is wrong.
We give them their own declarative_base instead.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Date,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base


ProjectionBase = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# NOTE: column types are PORTABLE rather than UUID-specific. The
# reporting-service uses `sqlalchemy.dialects.postgresql.UUID` because it
# writes to postgres in prod. Reading via plain String(36) works against
# both postgres (UUID is castable) and sqlite (the test fixture), so the
# read-side mapping is the more permissive of the two.


class ProcessedEvent(ProjectionBase):
    __tablename__ = "processed_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)
    school_id = Column(String(36), nullable=False)
    processed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DashboardStats(ProjectionBase):
    __tablename__ = "dashboard_stats"

    school_id = Column(String(36), primary_key=True)
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    total_enrollments = Column(Integer, nullable=False, default=0)
    attendance_today_present = Column(Integer, nullable=False, default=0)
    attendance_today_total = Column(Integer, nullable=False, default=0)
    total_invoiced = Column(Numeric(14, 2), nullable=False, default=0)
    total_paid = Column(Numeric(14, 2), nullable=False, default=0)
    announcements_this_month = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AttendanceDailyAggregate(ProjectionBase):
    __tablename__ = "attendance_daily_aggregate"
    __table_args__ = (
        UniqueConstraint("school_id", "date", name="uq_att_daily_school_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String(36), nullable=False, index=True)
    date = Column(Date, nullable=False)
    present_count = Column(Integer, nullable=False, default=0)
    absent_count = Column(Integer, nullable=False, default=0)
    late_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class FinancialSummary(ProjectionBase):
    __tablename__ = "financial_summary"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", name="uq_fin_school_year"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String(36), nullable=False, index=True)
    academic_year_id = Column(String(36), nullable=False)
    total_invoiced = Column(Numeric(14, 2), nullable=False, default=0)
    total_paid = Column(Numeric(14, 2), nullable=False, default=0)
    total_outstanding = Column(Numeric(14, 2), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class StudentCountProjection(ProjectionBase):
    __tablename__ = "student_count_projection"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", name="uq_sc_school_year"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String(36), nullable=False, index=True)
    academic_year_id = Column(String(36), nullable=False)
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
