"""
Attendance Service ORM Models
===============================
AttendanceRecord (append-only), SyncBatch (idempotent), ProcessedClientEvent (dedup)

Key constraints:
- (school_id, student_id, date) unique — one attendance per student per day
- (school_id, device_id, sync_batch_id) unique — prevent batch replay
- (school_id, device_id, client_event_id) unique — prevent event replay
"""
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("school_id", "student_id", "date",
                         name="uq_attendance_student_date"),
        Index("ix_attendance_school_date", "school_id", "date"),
        Index("ix_attendance_school_class_date", "school_id", "class_id", "date"),
        Index("ix_attendance_school_student_date", "school_id", "student_id", "date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(String(2), nullable=False)  # P, A, L
    marked_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    device_id = Column(String(100), nullable=True)
    client_event_id = Column(String(100), nullable=True)
    last_modified_at = Column(DateTime(timezone=True), nullable=False,
                              default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SyncBatch(Base):
    __tablename__ = "sync_batches"
    __table_args__ = (
        UniqueConstraint("school_id", "device_id", "sync_batch_id",
                         name="uq_sync_batch"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    device_id = Column(String(100), nullable=False)
    sync_batch_id = Column(String(100), nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                         nullable=False)
    total_events = Column(Integer, nullable=False, default=0)
    accepted_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    ignored_count = Column(Integer, nullable=False, default=0)


class ProcessedClientEvent(Base):
    __tablename__ = "processed_client_events"
    __table_args__ = (
        UniqueConstraint("school_id", "device_id", "client_event_id",
                         name="uq_processed_event"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False)
    device_id = Column(String(100), nullable=False)
    client_event_id = Column(String(100), nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          nullable=False)
