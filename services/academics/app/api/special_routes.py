"""Special-config endpoints — Phase 13e (boarding + multi-campus)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.special import BoardingRoom, BoardingAssignment, Campus
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err,
)


router = APIRouter(tags=["Special"])


BOARDING_OCCUPANCY = {"boys", "girls", "mixed", "staff"}
CAMPUS_TYPES = {"primary", "secondary", "combined", "annex", "other"}



def _actor(current_user: dict) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))



# ─── A-018 — Boarding rooms ───────────────────────────────────────


class RoomCreate(BaseModel):
    room_code: str = Field(..., max_length=32)
    campus: Optional[str] = Field(default=None, max_length=64)
    occupancy_kind: str = Field(default="mixed")
    capacity: int = Field(default=4, ge=1, le=50)
    notes: Optional[str] = None


def _ser_room(r: BoardingRoom, occupied: int = 0) -> dict:
    return {
        "id": r.id, "room_code": r.room_code, "campus": r.campus,
        "occupancy_kind": r.occupancy_kind,
        "capacity": r.capacity, "notes": r.notes,
        "is_active": bool(r.is_active),
        "occupied": occupied,
        "available": max(0, r.capacity - occupied),
    }


@router.get("/boarding/rooms")
def list_rooms(
    request: Request,
    campus: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(BoardingRoom).filter(
        BoardingRoom.school_id == str(school_id),
        BoardingRoom.is_active.is_(True),
    )
    if campus:
        q = q.filter(BoardingRoom.campus == campus)
    rows = q.order_by(BoardingRoom.room_code.asc()).all()
    # Occupancy count per room
    if rows:
        room_ids = [r.id for r in rows]
        from sqlalchemy import func
        counts = dict(
            db.query(
                BoardingAssignment.room_id,
                func.count(BoardingAssignment.id),
            )
            .filter(
                BoardingAssignment.room_id.in_(room_ids),
                BoardingAssignment.ended_on.is_(None),
            )
            .group_by(BoardingAssignment.room_id)
            .all()
        )
    else:
        counts = {}
    return {
        "data": [_ser_room(r, int(counts.get(r.id, 0))) for r in rows],
        "meta": _meta(request),
    }


@router.post("/boarding/rooms")
def create_room(
    payload: RoomCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.occupancy_kind not in BOARDING_OCCUPANCY:
        return _err("INVALID_OCCUPANCY",
                    f"must be in {sorted(BOARDING_OCCUPANCY)}", request)
    r = BoardingRoom(
        school_id=str(school_id),
        room_code=payload.room_code, campus=payload.campus,
        occupancy_kind=payload.occupancy_kind,
        capacity=payload.capacity, notes=payload.notes,
    )
    db.add(r)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="boarding_room.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "boarding_room", "id": r.id,
                "room_code": payload.room_code},
        details={"occupancy_kind": payload.occupancy_kind,
                 "capacity": payload.capacity},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_room(r, 0), "meta": _meta(request)}


# ─── A-018 — Boarding assignments ─────────────────────────────────


class AssignmentCreate(BaseModel):
    room_id: uuid.UUID
    student_id: uuid.UUID
    bed_label: Optional[str] = Field(default=None, max_length=16)
    starts_on: date


class AssignmentEnd(BaseModel):
    ended_on: date


def _ser_assignment(a: BoardingAssignment) -> dict:
    return {
        "id": a.id, "room_id": a.room_id, "student_id": a.student_id,
        "bed_label": a.bed_label,
        "starts_on": a.starts_on.isoformat() if a.starts_on else None,
        "ended_on": a.ended_on.isoformat() if a.ended_on else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/boarding/assignments")
def list_assignments(
    request: Request,
    room_id: Optional[uuid.UUID] = Query(None),
    student_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(BoardingAssignment).filter(
        BoardingAssignment.school_id == str(school_id),
    )
    if room_id:
        q = q.filter(BoardingAssignment.room_id == str(room_id))
    if student_id:
        q = q.filter(BoardingAssignment.student_id == str(student_id))
    if active_only:
        q = q.filter(BoardingAssignment.ended_on.is_(None))
    rows = q.order_by(desc(BoardingAssignment.created_at)).all()
    return {"data": [_ser_assignment(r) for r in rows], "meta": _meta(request)}


@router.post("/boarding/assignments")
def create_assignment(
    payload: AssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Check capacity
    r = (
        db.query(BoardingRoom)
        .filter(BoardingRoom.id == str(payload.room_id),
                BoardingRoom.school_id == str(school_id))
        .first()
    )
    if r is None:
        return _err("NOT_FOUND", "Room not found.", request, 404)
    from sqlalchemy import func
    occupied = (
        db.query(func.count(BoardingAssignment.id))
        .filter(BoardingAssignment.room_id == r.id,
                BoardingAssignment.ended_on.is_(None))
        .scalar()
    ) or 0
    if occupied >= r.capacity:
        return _err("ROOM_FULL",
                    f"Room {r.room_code} is at capacity.",
                    request, 409)
    # Reject duplicate active assignment for same student.
    existing = (
        db.query(BoardingAssignment)
        .filter(
            BoardingAssignment.school_id == str(school_id),
            BoardingAssignment.student_id == str(payload.student_id),
            BoardingAssignment.ended_on.is_(None),
        )
        .first()
    )
    if existing:
        return _err("ALREADY_ASSIGNED",
                    "Student already has an active boarding assignment.",
                    request, 409)
    actor = _actor(current_user)
    a = BoardingAssignment(
        school_id=str(school_id),
        room_id=r.id,
        student_id=str(payload.student_id),
        bed_label=payload.bed_label,
        starts_on=payload.starts_on,
        assigned_by_user_id=str(actor),
    )
    db.add(a)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="boarding_assignment.created",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "boarding_assignment", "id": a.id,
                "room_id": r.id, "student_id": str(payload.student_id)},
        details={"bed_label": payload.bed_label},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_assignment(a), "meta": _meta(request)}


@router.post("/boarding/assignments/{aid}/end")
def end_assignment(
    aid: uuid.UUID, payload: AssignmentEnd,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = (
        db.query(BoardingAssignment)
        .filter(BoardingAssignment.id == str(aid),
                BoardingAssignment.school_id == str(school_id))
        .first()
    )
    if a is None or a.ended_on is not None:
        return _err("NOT_FOUND", "Active assignment not found.", request, 404)
    a.ended_on = payload.ended_on
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="boarding_assignment.ended",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "boarding_assignment", "id": a.id},
        details={"ended_on": payload.ended_on.isoformat()},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_assignment(a), "meta": _meta(request)}


# ─── A-021 — Multi-campus ─────────────────────────────────────────


class CampusCreate(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)
    campus_type: str = Field(default="combined")
    address: Optional[str] = None
    province_code: Optional[str] = Field(default=None, max_length=8)
    district_code: Optional[str] = Field(default=None, max_length=16)
    lat: Optional[str] = Field(default=None, max_length=16)
    lng: Optional[str] = Field(default=None, max_length=16)
    is_primary: bool = False


def _ser_campus(c: Campus) -> dict:
    return {
        "id": c.id, "code": c.code, "name": c.name,
        "campus_type": c.campus_type,
        "address": c.address,
        "province_code": c.province_code,
        "district_code": c.district_code,
        "lat": c.lat, "lng": c.lng,
        "is_primary": bool(c.is_primary),
        "is_active": bool(c.is_active),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/campuses")
def list_campuses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(Campus)
        .filter(Campus.school_id == str(school_id),
                Campus.is_active.is_(True))
        .order_by(desc(Campus.is_primary), Campus.code.asc())
        .all()
    )
    return {"data": [_ser_campus(r) for r in rows], "meta": _meta(request)}


@router.post("/campuses")
def create_campus(
    payload: CampusCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.campus_type not in CAMPUS_TYPES:
        return _err("INVALID_TYPE",
                    f"must be in {sorted(CAMPUS_TYPES)}", request)
    # If is_primary=true, clear primary on any existing campus.
    if payload.is_primary:
        for prev in (
            db.query(Campus)
            .filter(Campus.school_id == str(school_id),
                    Campus.is_primary.is_(True))
            .all()
        ):
            prev.is_primary = False
    c = Campus(
        school_id=str(school_id),
        code=payload.code, name=payload.name,
        campus_type=payload.campus_type,
        address=payload.address,
        province_code=payload.province_code,
        district_code=payload.district_code,
        lat=payload.lat, lng=payload.lng,
        is_primary=payload.is_primary,
    )
    db.add(c)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="campus.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "campus", "id": c.id, "code": payload.code},
        details={"campus_type": payload.campus_type,
                 "is_primary": payload.is_primary},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_campus(c), "meta": _meta(request)}
