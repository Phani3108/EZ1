"""
Reporting Service — Projection Tables (Materialized Aggregates)
================================================================
These are NOT source-of-truth tables. They are projections
rebuilt from domain events. Every row is derived data.

ProcessedEvent inbox ensures idempotent consumption.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer,
    Numeric, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ProcessedEvent(Base):
    """Inbox table — ensures each event is consumed exactly once."""
    __tablename__ = "processed_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)
    school_id = Column(UUID(as_uuid=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          nullable=False)


class DashboardStats(Base):
    """Per-school dashboard aggregate — single row per school."""
    __tablename__ = "dashboard_stats"

    school_id = Column(UUID(as_uuid=True), primary_key=True)
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    total_enrollments = Column(Integer, nullable=False, default=0)
    attendance_today_present = Column(Integer, nullable=False, default=0)
    attendance_today_total = Column(Integer, nullable=False, default=0)
    total_invoiced = Column(Numeric(14, 2), nullable=False, default=0)
    total_paid = Column(Numeric(14, 2), nullable=False, default=0)
    announcements_this_month = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)


class AttendanceDailyAggregate(Base):
    """Daily attendance aggregate per school."""
    __tablename__ = "attendance_daily_aggregate"
    __table_args__ = (
        UniqueConstraint("school_id", "date", name="uq_att_daily_school_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(Date, nullable=False)
    present_count = Column(Integer, nullable=False, default=0)
    absent_count = Column(Integer, nullable=False, default=0)
    late_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)


class FinancialSummary(Base):
    """Financial aggregate per school + academic year."""
    __tablename__ = "financial_summary"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", name="uq_fin_school_year"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), nullable=False)
    total_invoiced = Column(Numeric(14, 2), nullable=False, default=0)
    total_paid = Column(Numeric(14, 2), nullable=False, default=0)
    total_outstanding = Column(Numeric(14, 2), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)


class StudentCountProjection(Base):
    """Student count per school + academic year."""
    __tablename__ = "student_count_projection"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", name="uq_sc_school_year"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), nullable=False)
    total_students = Column(Integer, nullable=False, default=0)
    active_students = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)
