"""Parent-life endpoints (Phase 12d/e/f).

Compact router covering the lower-priority parent-side surface. Each
domain gets a list + create endpoint at minimum; complex flows
(conference bookings, permission slips, grievances) get a small
additional verb (book / sign / resolve).

Privacy: every audit row logs the resource kind + id only. The free-
text fields (grievance body, permission slip body, newsletter body)
are NOT logged.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.parent_life import (
    SchoolEvent, SchoolPerformanceOptOut,
    ConferenceSlot, ConferenceBooking,
    PermissionSlip, PermissionSlipResponse,
    Grievance, TransportBus, TransportPing,
    MealCreditAccount, Donation,
    NewsletterPost, GalleryPhoto, SiblingDiscountRule,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)


router = APIRouter(tags=["Parent Life"])



def _actor(current_user: dict) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


# ─── 12d / P-010 — School events ──────────────────────────────────


class EventCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    kind: str = Field(default="other", max_length=32)
    visible_to_parents: bool = True


def _ser_event(e: SchoolEvent) -> dict:
    return {
        "id": e.id, "title": e.title, "description": e.description,
        "start_at": e.start_at.isoformat() if e.start_at else None,
        "end_at": e.end_at.isoformat() if e.end_at else None,
        "kind": e.kind, "visible_to_parents": bool(e.visible_to_parents),
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/school-events")
def list_school_events(
    request: Request,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(SchoolEvent).filter(SchoolEvent.school_id == str(school_id))
    if from_date:
        q = q.filter(
            SchoolEvent.start_at >= datetime.combine(
                from_date, datetime.min.time(), tzinfo=timezone.utc,
            )
        )
    if to_date:
        q = q.filter(
            SchoolEvent.start_at <= datetime.combine(
                to_date, datetime.max.time(), tzinfo=timezone.utc,
            )
        )
    # Non-admin callers only see visible-to-parents events.
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    if not any(r in ("admin", "principal") for r in roles):
        q = q.filter(SchoolEvent.visible_to_parents.is_(True))
    rows = q.order_by(SchoolEvent.start_at.asc()).all()
    return {"data": [_ser_event(r) for r in rows], "meta": _meta(request)}


@router.post("/school-events")
def create_school_event(
    payload: EventCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    e = SchoolEvent(
        school_id=str(school_id),
        title=payload.title, description=payload.description,
        start_at=payload.start_at, end_at=payload.end_at,
        kind=payload.kind,
        visible_to_parents=payload.visible_to_parents,
        created_by=str(_actor(current_user)),
    )
    db.add(e)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="school_event.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "school_event", "id": e.id},
        details={"kind": payload.kind},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_event(e), "meta": _meta(request)}


# ─── 12d / P-009 — Performance comparison opt-out ─────────────────


class OptOutPut(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


@router.get("/performance-opt-out")
def get_opt_out(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SchoolPerformanceOptOut)
        .filter(SchoolPerformanceOptOut.school_id == str(school_id))
        .first()
    )
    return {
        "data": {
            "school_id": str(school_id),
            "opted_out": row is not None,
            "reason": row.reason if row else None,
            "opted_out_at": (
                row.opted_out_at.isoformat() if row and row.opted_out_at else None
            ),
        },
        "meta": _meta(request),
    }


@router.put("/performance-opt-out")
def put_opt_out(
    payload: OptOutPut,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SchoolPerformanceOptOut)
        .filter(SchoolPerformanceOptOut.school_id == str(school_id))
        .first()
    )
    if row is None:
        row = SchoolPerformanceOptOut(
            school_id=str(school_id),
            opted_out_by=str(_actor(current_user)),
            reason=payload.reason,
        )
        db.add(row)
    else:
        row.reason = payload.reason
        row.opted_out_by = str(_actor(current_user))
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="performance_opt_out.updated",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "performance_opt_out", "id": str(school_id)},
        details={"opted_out": True},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": {"opted_out": True, "reason": row.reason},
            "meta": _meta(request)}


@router.delete("/performance-opt-out")
def delete_opt_out(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SchoolPerformanceOptOut)
        .filter(SchoolPerformanceOptOut.school_id == str(school_id))
        .first()
    )
    if row:
        db.delete(row)
        db.flush()
        record_audit_event(
            db, AuditLog, event_type="performance_opt_out.removed",
            school_id=school_id, actor_user_id=_actor(current_user),
            actor_role=(current_user.get("roles") or [None])[0],
            target={"resource": "performance_opt_out", "id": str(school_id)},
            details={},
            request_id=getattr(request.state, "request_id", None),
        )
        db.commit()
    return {"data": {"opted_out": False}, "meta": _meta(request)}


# ─── 12e / P-005 — Conference slots + bookings ────────────────────


class SlotCreate(BaseModel):
    teacher_user_id: uuid.UUID
    starts_at: datetime
    duration_minutes: int = Field(default=15, ge=5, le=120)


class BookingCreate(BaseModel):
    slot_id: uuid.UUID
    student_id: uuid.UUID
    notes: Optional[str] = Field(default=None, max_length=1000)


def _ser_slot(s: ConferenceSlot) -> dict:
    return {
        "id": s.id, "teacher_user_id": s.teacher_user_id,
        "starts_at": s.starts_at.isoformat() if s.starts_at else None,
        "duration_minutes": s.duration_minutes,
        "is_booked": bool(s.is_booked),
    }


def _ser_booking(b: ConferenceBooking) -> dict:
    return {
        "id": b.id, "slot_id": b.slot_id,
        "parent_user_id": b.parent_user_id, "student_id": b.student_id,
        "notes": b.notes,
        "confirmed_at": b.confirmed_at.isoformat() if b.confirmed_at else None,
        "cancelled_at": b.cancelled_at.isoformat() if b.cancelled_at else None,
    }


@router.get("/conference-slots")
def list_conference_slots(
    request: Request,
    teacher_user_id: Optional[uuid.UUID] = Query(None),
    available_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(ConferenceSlot).filter(
        ConferenceSlot.school_id == str(school_id),
    )
    if teacher_user_id:
        q = q.filter(ConferenceSlot.teacher_user_id == str(teacher_user_id))
    if available_only:
        q = q.filter(ConferenceSlot.is_booked.is_(False))
    rows = q.order_by(ConferenceSlot.starts_at.asc()).all()
    return {"data": [_ser_slot(r) for r in rows], "meta": _meta(request)}


@router.post("/conference-slots")
def create_conference_slot(
    payload: SlotCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    s = ConferenceSlot(
        school_id=str(school_id),
        teacher_user_id=str(payload.teacher_user_id),
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
    )
    db.add(s)
    db.flush()
    db.commit()
    return {"data": _ser_slot(s), "meta": _meta(request)}


@router.post("/conference-bookings")
def create_booking(
    payload: BookingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    slot = (
        db.query(ConferenceSlot)
        .filter(ConferenceSlot.id == str(payload.slot_id),
                ConferenceSlot.school_id == str(school_id))
        .first()
    )
    if slot is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Slot not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    if slot.is_booked:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "ALREADY_BOOKED",
                               "message": "Slot already booked.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = _actor(current_user)
    b = ConferenceBooking(
        school_id=str(school_id),
        slot_id=slot.id,
        parent_user_id=str(actor),
        student_id=str(payload.student_id),
        notes=payload.notes,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(b)
    slot.is_booked = True
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="conference.booked",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "conference_booking", "id": b.id,
                "slot_id": slot.id, "student_id": str(payload.student_id)},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_booking(b), "meta": _meta(request)}


# ─── 12e / P-006 — Permission slips ───────────────────────────────


class SlipCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., min_length=1)
    class_id: Optional[uuid.UUID] = None
    deadline: Optional[date] = None


class SlipResponseCreate(BaseModel):
    student_id: uuid.UUID
    decision: str = Field(..., pattern="^(approved|declined)$")
    signed_full_name: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=1000)


def _ser_slip(p: PermissionSlip) -> dict:
    return {
        "id": p.id, "title": p.title, "description": p.description,
        "class_id": p.class_id,
        "deadline": p.deadline.isoformat() if p.deadline else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _ser_response(r: PermissionSlipResponse) -> dict:
    return {
        "id": r.id, "slip_id": r.slip_id, "student_id": r.student_id,
        "decision": r.decision,
        "signed_full_name": r.signed_full_name,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
    }


@router.get("/permission-slips")
def list_slips(
    request: Request,
    class_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(PermissionSlip).filter(
        PermissionSlip.school_id == str(school_id),
    )
    if class_id:
        from sqlalchemy import or_
        q = q.filter(or_(
            PermissionSlip.class_id == str(class_id),
            PermissionSlip.class_id.is_(None),
        ))
    rows = q.order_by(desc(PermissionSlip.created_at)).all()
    return {"data": [_ser_slip(r) for r in rows], "meta": _meta(request)}


@router.post("/permission-slips")
def create_slip(
    payload: SlipCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = PermissionSlip(
        school_id=str(school_id),
        title=payload.title, description=payload.description,
        class_id=str(payload.class_id) if payload.class_id else None,
        deadline=payload.deadline,
        created_by=str(_actor(current_user)),
    )
    db.add(p)
    db.flush()
    db.commit()
    return {"data": _ser_slip(p), "meta": _meta(request)}


@router.post("/permission-slips/{slip_id}/responses")
def sign_slip(
    slip_id: uuid.UUID,
    payload: SlipResponseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = (
        db.query(PermissionSlip)
        .filter(PermissionSlip.id == str(slip_id),
                PermissionSlip.school_id == str(school_id))
        .first()
    )
    if p is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Permission slip not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = _actor(current_user)
    # Upsert by (slip, student): re-signing replaces the prior row.
    r = (
        db.query(PermissionSlipResponse)
        .filter(PermissionSlipResponse.slip_id == p.id,
                PermissionSlipResponse.student_id == str(payload.student_id))
        .first()
    )
    if r:
        r.decision = payload.decision
        r.signed_full_name = payload.signed_full_name
        r.notes = payload.notes
        r.submitted_at = datetime.now(timezone.utc)
        r.parent_user_id = str(actor)
    else:
        r = PermissionSlipResponse(
            school_id=str(school_id), slip_id=p.id,
            student_id=str(payload.student_id),
            parent_user_id=str(actor),
            decision=payload.decision,
            signed_full_name=payload.signed_full_name,
            notes=payload.notes,
        )
        db.add(r)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="permission_slip.signed",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "permission_slip_response", "id": r.id,
                "slip_id": p.id, "student_id": str(payload.student_id)},
        # The signed name IS the audit story (it's the e-signature
        # record) — log it. Notes are NOT logged.
        details={"decision": payload.decision,
                 "signed_full_name": payload.signed_full_name},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_response(r), "meta": _meta(request)}


# ─── 12e / P-007 — Grievances ─────────────────────────────────────


class GrievanceCreate(BaseModel):
    student_id: Optional[uuid.UUID] = None
    subject: str = Field(..., max_length=200)
    body: str = Field(..., min_length=1)


class GrievanceResolve(BaseModel):
    status: str = Field(..., pattern="^(in_review|resolved|dismissed)$")
    resolution_notes: Optional[str] = None


def _ser_grievance(g: Grievance) -> dict:
    return {
        "id": g.id, "parent_user_id": g.parent_user_id,
        "student_id": g.student_id,
        "subject": g.subject, "body": g.body,
        "status": g.status,
        "resolved_at": g.resolved_at.isoformat() if g.resolved_at else None,
        "resolved_by_user_id": g.resolved_by_user_id,
        "resolution_notes": g.resolution_notes,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


@router.get("/grievances")
def list_grievances(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Grievance).filter(Grievance.school_id == str(school_id))
    if status:
        q = q.filter(Grievance.status == status)
    # Non-admin callers see only their own submissions.
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    if not any(r in ("admin", "principal") for r in roles):
        q = q.filter(Grievance.parent_user_id == str(_actor(current_user)))
    return {
        "data": [_ser_grievance(r) for r in
                 q.order_by(desc(Grievance.created_at)).all()],
        "meta": _meta(request),
    }


@router.post("/grievances")
def create_grievance(
    payload: GrievanceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = _actor(current_user)
    g = Grievance(
        school_id=str(school_id),
        parent_user_id=str(actor),
        student_id=str(payload.student_id) if payload.student_id else None,
        subject=payload.subject, body=payload.body,
    )
    db.add(g)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="grievance.submitted",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "grievance", "id": g.id},
        # Body is NOT logged — could contain anything from "the
        # canteen food is bad" to "teacher X did Y." Length is the
        # admin-debuggable signal.
        details={"length": len(payload.body)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_grievance(g), "meta": _meta(request)}


@router.put("/grievances/{gid}")
def resolve_grievance(
    gid: uuid.UUID, payload: GrievanceResolve,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    g = (
        db.query(Grievance)
        .filter(Grievance.id == str(gid),
                Grievance.school_id == str(school_id))
        .first()
    )
    if g is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Grievance not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    g.status = payload.status
    g.resolution_notes = payload.resolution_notes
    if payload.status in ("resolved", "dismissed"):
        g.resolved_at = datetime.now(timezone.utc)
        g.resolved_by_user_id = str(_actor(current_user))
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=f"grievance.{payload.status}",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "grievance", "id": g.id},
        details={"status": payload.status},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_grievance(g), "meta": _meta(request)}


# ─── 12e / P-012 — Transport ──────────────────────────────────────


class BusCreate(BaseModel):
    label: str = Field(..., max_length=120)
    plate_number: Optional[str] = Field(default=None, max_length=32)
    route_description: Optional[str] = None


class PingCreate(BaseModel):
    bus_id: uuid.UUID
    status: str = Field(..., pattern="^(departed|en_route|arrived|delayed)$")
    lat: Optional[float] = None
    lng: Optional[float] = None
    note: Optional[str] = Field(default=None, max_length=500)


@router.get("/transport-buses")
def list_buses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(TransportBus)
        .filter(TransportBus.school_id == str(school_id),
                TransportBus.is_active.is_(True))
        .all()
    )
    # Latest ping per bus.
    out = []
    for b in rows:
        latest = (
            db.query(TransportPing)
            .filter(TransportPing.bus_id == b.id)
            .order_by(desc(TransportPing.occurred_at))
            .first()
        )
        out.append({
            "id": b.id, "label": b.label,
            "plate_number": b.plate_number,
            "route_description": b.route_description,
            "latest_ping": (
                {
                    "status": latest.status,
                    "lat": float(latest.lat) if latest.lat is not None else None,
                    "lng": float(latest.lng) if latest.lng is not None else None,
                    "note": latest.note,
                    "occurred_at": latest.occurred_at.isoformat(),
                }
                if latest else None
            ),
        })
    return {"data": out, "meta": _meta(request)}


@router.post("/transport-buses")
def create_bus(
    payload: BusCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    b = TransportBus(
        school_id=str(school_id),
        label=payload.label,
        plate_number=payload.plate_number,
        route_description=payload.route_description,
    )
    db.add(b)
    db.flush()
    db.commit()
    return {"data": {"id": b.id, "label": b.label},
            "meta": _meta(request)}


@router.post("/transport-pings")
def create_ping(
    payload: PingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    bus = (
        db.query(TransportBus)
        .filter(TransportBus.id == str(payload.bus_id),
                TransportBus.school_id == str(school_id))
        .first()
    )
    if bus is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Bus not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    p = TransportPing(
        school_id=str(school_id), bus_id=bus.id,
        status=payload.status,
        lat=payload.lat, lng=payload.lng,
        note=payload.note,
    )
    db.add(p)
    db.flush()
    db.commit()
    return {"data": {"id": p.id, "status": payload.status},
            "meta": _meta(request)}


# ─── 12f / P-013 — Meal credit ────────────────────────────────────


class MealTopup(BaseModel):
    student_id: uuid.UUID
    amount_cents: int = Field(..., gt=0)


@router.get("/meal-credit/{student_id}")
def get_meal_balance(
    student_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(MealCreditAccount)
        .filter(MealCreditAccount.student_id == str(student_id),
                MealCreditAccount.school_id == str(school_id))
        .first()
    )
    balance = row.balance_cents if row else 0
    return {"data": {"student_id": str(student_id),
                     "balance_cents": balance},
            "meta": _meta(request)}


@router.post("/meal-credit/topup")
def meal_topup(
    payload: MealTopup,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(MealCreditAccount)
        .filter(MealCreditAccount.student_id == str(payload.student_id),
                MealCreditAccount.school_id == str(school_id))
        .first()
    )
    if row is None:
        row = MealCreditAccount(
            school_id=str(school_id),
            student_id=str(payload.student_id),
            balance_cents=payload.amount_cents,
        )
        db.add(row)
    else:
        row.balance_cents += payload.amount_cents
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="meal_credit.topup",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "meal_credit", "student_id": str(payload.student_id)},
        # Amount IS the audit story (money move).
        details={"amount_cents": payload.amount_cents,
                 "new_balance_cents": row.balance_cents},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": {"student_id": str(payload.student_id),
                     "balance_cents": row.balance_cents},
            "meta": _meta(request)}


# ─── 12f / P-014 — Donations ──────────────────────────────────────


class DonationCreate(BaseModel):
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    purpose: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = None
    anonymous: bool = False


@router.get("/donations")
def list_donations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Parents see their own; admins see all.
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    is_admin = any(r in ("admin", "principal") for r in roles)
    q = db.query(Donation).filter(Donation.school_id == str(school_id))
    if not is_admin:
        q = q.filter(Donation.donor_user_id == str(_actor(current_user)))
    rows = q.order_by(desc(Donation.created_at)).all()
    return {
        "data": [
            {
                "id": d.id,
                # Anonymous donor: hide donor_user_id from non-admin readers.
                "donor_user_id": (
                    d.donor_user_id if (is_admin or d.donor_user_id) else None
                ),
                "amount_cents": d.amount_cents,
                "currency": d.currency,
                "purpose": d.purpose,
                "note": d.note,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ],
        "meta": _meta(request),
    }


@router.post("/donations")
def create_donation(
    payload: DonationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = _actor(current_user)
    d = Donation(
        school_id=str(school_id),
        donor_user_id=None if payload.anonymous else str(actor),
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        purpose=payload.purpose,
        note=payload.note,
    )
    db.add(d)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="donation.recorded",
        school_id=school_id,
        actor_user_id=(None if payload.anonymous else actor),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "donation", "id": d.id},
        # Amount + currency are the audit story.
        details={"amount_cents": payload.amount_cents,
                 "currency": payload.currency,
                 "anonymous": payload.anonymous},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": {"id": d.id, "amount_cents": d.amount_cents},
            "meta": _meta(request)}


# ─── 12f / P-015 — Newsletter ─────────────────────────────────────


class NewsletterCreate(BaseModel):
    title: str = Field(..., max_length=200)
    body: str = Field(..., min_length=1)


@router.get("/newsletter")
def list_newsletter(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(NewsletterPost)
        .filter(NewsletterPost.school_id == str(school_id))
        .order_by(desc(NewsletterPost.published_at))
        .limit(50).all()
    )
    return {
        "data": [
            {"id": r.id, "title": r.title, "body": r.body,
             "published_at": r.published_at.isoformat()}
            for r in rows
        ],
        "meta": _meta(request),
    }


@router.post("/newsletter")
def create_newsletter(
    payload: NewsletterCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    n = NewsletterPost(
        school_id=str(school_id),
        title=payload.title, body=payload.body,
        author_user_id=str(_actor(current_user)),
    )
    db.add(n)
    db.flush()
    db.commit()
    return {"data": {"id": n.id, "title": n.title},
            "meta": _meta(request)}


# ─── 12f / P-016 — Gallery photos ─────────────────────────────────


class GalleryCreate(BaseModel):
    attachment_id: uuid.UUID
    caption: Optional[str] = Field(default=None, max_length=500)
    visibility: str = Field(default="all_parents", max_length=64)


@router.get("/gallery")
def list_gallery(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(GalleryPhoto)
        .filter(GalleryPhoto.school_id == str(school_id))
        .order_by(desc(GalleryPhoto.published_at))
        .limit(100).all()
    )
    return {
        "data": [
            {"id": p.id, "attachment_id": p.attachment_id,
             "caption": p.caption, "visibility": p.visibility,
             "published_at": p.published_at.isoformat()}
            for p in rows
        ],
        "meta": _meta(request),
    }


@router.post("/gallery")
def create_gallery(
    payload: GalleryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = GalleryPhoto(
        school_id=str(school_id),
        attachment_id=str(payload.attachment_id),
        caption=payload.caption,
        visibility=payload.visibility,
        published_by=str(_actor(current_user)),
    )
    db.add(p)
    db.flush()
    db.commit()
    return {"data": {"id": p.id}, "meta": _meta(request)}


# ─── 12f / P-017 — Sibling discount rule ──────────────────────────


class SiblingRulePut(BaseModel):
    rule: dict = Field(...)
    is_active: bool = True


@router.get("/sibling-discount-rule")
def get_sibling_rule(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SiblingDiscountRule)
        .filter(SiblingDiscountRule.school_id == str(school_id))
        .first()
    )
    if row is None:
        return {"data": {"is_active": False, "rule": None},
                "meta": _meta(request)}
    try:
        rule = json.loads(row.rule_json)
    except (TypeError, ValueError):
        rule = None
    return {"data": {"is_active": bool(row.is_active),
                     "rule": rule,
                     "updated_at": row.updated_at.isoformat()},
            "meta": _meta(request)}


@router.put("/sibling-discount-rule")
def put_sibling_rule(
    payload: SiblingRulePut,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    row = (
        db.query(SiblingDiscountRule)
        .filter(SiblingDiscountRule.school_id == str(school_id))
        .first()
    )
    if row is None:
        row = SiblingDiscountRule(
            school_id=str(school_id),
            rule_json=json.dumps(payload.rule),
            is_active=payload.is_active,
            updated_by=str(_actor(current_user)),
        )
        db.add(row)
    else:
        row.rule_json = json.dumps(payload.rule)
        row.is_active = payload.is_active
        row.updated_by = str(_actor(current_user))
    db.flush()
    db.commit()
    return {"data": {"is_active": bool(row.is_active)},
            "meta": _meta(request)}
