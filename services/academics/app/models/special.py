"""Special configurations — Phase 13e (boarding + multi-campus).

  * A-018 — `BoardingRoom` + `BoardingAssignment` — hostel rooms and
    per-student assignments to a room.
  * A-021 — `Campus` — multi-campus support. A school can declare
    sub-campuses (primary + secondary on different grounds). The
    Student / Class / Asset / Visitor records optionally reference
    a Campus by name (no FK to avoid cross-domain coupling — campus
    matching is convention).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Date, Integer, Boolean, Text,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── A-018 — Boarding ─────────────────────────────────────────────


class BoardingRoom(Base):
    __tablename__ = "boarding_rooms"
    __table_args__ = (
        UniqueConstraint("school_id", "room_code",
                         name="uq_boarding_room_code"),
        Index("ix_boarding_room_school", "school_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    room_code = Column(String(32), nullable=False)
    # Optional campus segregation — admin convention.
    campus = Column(String(64), nullable=True)
    # boys | girls | mixed | staff
    occupancy_kind = Column(String(16), nullable=False, default="mixed")
    capacity = Column(Integer, nullable=False, default=4)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class BoardingAssignment(Base):
    """Append-only: each row is an assignment for a term (or
    open-ended). To "unassign", the admin sets `ended_on`."""
    __tablename__ = "boarding_assignments"
    __table_args__ = (
        Index("ix_boarding_assignment_room", "room_id"),
        Index("ix_boarding_assignment_student", "student_id"),
        Index("ix_boarding_assignment_active", "school_id", "ended_on"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    room_id = Column(UUID_STR, nullable=False)
    student_id = Column(UUID_STR, nullable=False)
    bed_label = Column(String(16), nullable=True)  # "Bed 1" / "Top bunk"
    starts_on = Column(Date, nullable=False)
    ended_on = Column(Date, nullable=True)
    assigned_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-021 — Multi-campus ─────────────────────────────────────────


class Campus(Base):
    """Sub-site of a school. Primary + secondary buildings on
    different grounds, an attached annex, etc. The Student / Class /
    Asset rows reference a campus by NAME rather than FK to keep the
    cross-table coupling soft — a school with a single campus can
    ignore this table entirely."""
    __tablename__ = "campuses"
    __table_args__ = (
        UniqueConstraint("school_id", "code", name="uq_campus_code"),
        Index("ix_campus_school", "school_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    code = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    # primary | secondary | combined | annex | other
    campus_type = Column(String(16), nullable=False, default="combined")
    address = Column(Text, nullable=True)
    province_code = Column(String(8), nullable=True)
    district_code = Column(String(16), nullable=True)
    lat = Column(String(16), nullable=True)
    lng = Column(String(16), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
