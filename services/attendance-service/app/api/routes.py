"""Attendance Service API Routes — Sync, Online Marking, Reporting."""
import uuid
from datetime import date, datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user, get_school_id, is_teacher_role,
    verify_teacher_class_authorization,
)
from app.services.attendance_service import AttendanceService
from app.events import publish_batch_event

router = APIRouter(tags=["Attendance"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request):
    return {"error": {"code": code, "message": msg, "details": {}, "request_id": _meta(request)["request_id"]}}


# ───── Schemas ─────

class AttendanceEvent(BaseModel):
    client_event_id: Optional[str] = None
    class_id: uuid.UUID
    student_id: uuid.UUID
    date: date
    status: str = Field(..., pattern="^[PAL]$")
    last_modified_at: Optional[datetime] = None

class SyncRequest(BaseModel):
    device_id: str = Field(..., max_length=100)
    sync_batch_id: str = Field(..., max_length=100)
    generated_at: Optional[datetime] = None
    events: List[AttendanceEvent]

class OnlineMarkRequest(BaseModel):
    records: List[AttendanceEvent]


# ───── Sync Endpoint ─────

@router.post("/attendance/sync")
async def sync_attendance(data: SyncRequest, request: Request,
                    db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user),
                    school_id: uuid.UUID = Depends(get_school_id)):
    # Teacher authorization: verify teacher is assigned to all classes in batch
    if is_teacher_role(current_user):
        teacher_id = uuid.UUID(current_user["sub"])
        class_ids = {e.class_id for e in data.events}
        for cid in class_ids:
            authorized = await verify_teacher_class_authorization(
                teacher_id, cid, school_id
            )
            if not authorized:
                raise HTTPException(
                    status_code=403,
                    detail=f"Teacher not authorized for class {cid}",
                )

    svc = AttendanceService(db)
    events = [e.model_dump() for e in data.events]
    result = svc.process_sync_batch(
        school_id, data.device_id, data.sync_batch_id,
        events, marked_by=uuid.UUID(current_user["sub"]),
    )

    # Kafka per-batch event
    if not result.get("already_processed") and result["accepted"] + result["updated"] > 0:
        dates = [e.date for e in data.events]
        date_range = {"min_date": min(dates).isoformat(), "max_date": max(dates).isoformat()}
        publish_batch_event(str(school_id), result, current_user["sub"], date_range)

    return {"data": result, "meta": _meta(request)}


# ───── Online Marking ─────

@router.post("/attendance/records")
def mark_records(data: OnlineMarkRequest, request: Request,
                 db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    records = [r.model_dump() for r in data.records]
    result = svc.mark_attendance(school_id, records,
                                  marked_by=uuid.UUID(current_user["sub"]))

    if result["accepted"] + result["updated"] > 0:
        dates = [r.date for r in data.records]
        date_range = {"min_date": min(dates).isoformat(), "max_date": max(dates).isoformat()}
        publish_batch_event(str(school_id), result, current_user["sub"], date_range)

    return {"data": result, "meta": _meta(request)}


# ───── Reporting ─────

@router.get("/attendance/daily")
def daily_report(request: Request, target_date: date = Query(..., alias="date"),
                 class_id: uuid.UUID = Query(None),
                 db: Session = Depends(get_db),
                 school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    result = svc.daily_summary(school_id, target_date, class_id)
    return {"data": result, "meta": _meta(request)}


@router.get("/attendance/student-trend")
def student_trend(request: Request, student_id: uuid.UUID = Query(...),
                  from_date: date = Query(..., alias="from"),
                  to_date: date = Query(..., alias="to"),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    result = svc.student_trend(school_id, student_id, from_date, to_date)
    return {"data": result, "meta": _meta(request)}


@router.get("/attendance/class-summary")
def class_summary_report(request: Request, class_id: uuid.UUID = Query(...),
                         from_date: date = Query(..., alias="from"),
                         to_date: date = Query(..., alias="to"),
                         db: Session = Depends(get_db),
                         school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    result = svc.class_summary(school_id, class_id, from_date, to_date)
    return {"data": result, "meta": _meta(request)}


# ───── Daily Records (per-student) ─────

@router.get("/attendance/daily/records")
def daily_records(request: Request, target_date: date = Query(..., alias="date"),
                  class_id: uuid.UUID = Query(...),
                  db: Session = Depends(get_db),
                  school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    result = svc.daily_records(school_id, target_date, class_id)
    return {"data": result, "meta": _meta(request)}


# ───── Sync Batches (admin) ─────

@router.get("/attendance/sync/batches")
def list_sync_batches(request: Request, limit: int = Query(20, ge=1, le=100),
                      db: Session = Depends(get_db),
                      current_user: dict = Depends(get_current_user),
                      school_id: uuid.UUID = Depends(get_school_id)):
    svc = AttendanceService(db)
    result = svc.list_sync_batches(school_id, limit)
    return {"data": result, "meta": _meta(request)}
