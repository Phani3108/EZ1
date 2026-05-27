"""Planning endpoints (Phase 11d).

Covers:
  * /periods                       — T-010 school period schedule (admin manage; everyone read)
  * /lesson-plans                  — T-005 templates + per-class instances
  * /formative-assessments         — T-013 polls / exit tickets / quizzes
  * /formative-assessments/{id}/responses — students respond
  * /exam-seat-plans               — T-012 seat-plan JSON store

Endpoints are deliberately compact. Every write goes through the
audit substrate; reads do not (volume).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.planning import (
    SchoolPeriod, LessonPlan, FormativeAssessment,
    FormativeResponse, ExamSeatPlan,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Planning"])


FORMATIVE_KINDS = {"poll", "exit_ticket", "quiz"}


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── T-010 — school periods ────────────────────────────────────────


class PeriodCreate(BaseModel):
    period_number: int = Field(..., ge=1, le=20)
    name: str = Field(..., max_length=80)
    start_time: time
    end_time: time


def _ser_period(p: SchoolPeriod) -> dict:
    return {
        "id": p.id, "period_number": p.period_number,
        "name": p.name,
        "start_time": p.start_time.isoformat() if p.start_time else None,
        "end_time": p.end_time.isoformat() if p.end_time else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/periods")
def list_periods(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(SchoolPeriod)
        .filter(SchoolPeriod.school_id == str(school_id))
        .order_by(SchoolPeriod.period_number.asc())
        .all()
    )
    return {"data": [_ser_period(r) for r in rows], "meta": _meta(request)}


@router.post("/periods")
def create_period(
    payload: PeriodCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = SchoolPeriod(
        school_id=str(school_id),
        period_number=payload.period_number,
        name=payload.name,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(p)
    db.flush()
    actor = uuid.UUID(str(current_user["sub"]))
    record_audit_event(
        db, AuditLog, event_type="period.created",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "school_period", "id": p.id},
        details={"period_number": payload.period_number},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_period(p), "meta": _meta(request)}


# ─── T-005 — lesson plans ──────────────────────────────────────────


class LessonPlanCreate(BaseModel):
    title: str = Field(..., max_length=200)
    subject_id: Optional[uuid.UUID] = None
    class_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    objectives: Optional[str] = None
    activities: Optional[str] = None
    resources: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_period_number: Optional[int] = Field(default=None, ge=0, le=99)


class LessonPlanUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    objectives: Optional[str] = None
    activities: Optional[str] = None
    resources: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_period_number: Optional[int] = Field(default=None, ge=0, le=99)


def _ser_lesson(p: LessonPlan) -> dict:
    return {
        "id": p.id, "title": p.title,
        "subject_id": p.subject_id, "class_id": p.class_id,
        "template_id": p.template_id,
        "is_template": p.class_id is None,
        "objectives": p.objectives, "activities": p.activities,
        "resources": p.resources,
        "scheduled_date": p.scheduled_date.isoformat() if p.scheduled_date else None,
        "scheduled_period_number": p.scheduled_period_number,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "archived_at": p.archived_at.isoformat() if p.archived_at else None,
    }


@router.get("/lesson-plans")
def list_lesson_plans(
    request: Request,
    class_id: Optional[uuid.UUID] = Query(None),
    templates_only: bool = Query(False),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(LessonPlan).filter(LessonPlan.school_id == str(school_id))
    if templates_only:
        q = q.filter(LessonPlan.class_id.is_(None))
    elif class_id:
        q = q.filter(LessonPlan.class_id == str(class_id))
    if not include_archived:
        q = q.filter(LessonPlan.archived_at.is_(None))
    rows = q.order_by(LessonPlan.created_at.desc()).all()
    return {"data": [_ser_lesson(r) for r in rows], "meta": _meta(request)}


@router.post("/lesson-plans")
def create_lesson_plan(
    payload: LessonPlanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = uuid.UUID(str(current_user["sub"]))
    p = LessonPlan(
        school_id=str(school_id),
        title=payload.title,
        subject_id=str(payload.subject_id) if payload.subject_id else None,
        class_id=str(payload.class_id) if payload.class_id else None,
        template_id=str(payload.template_id) if payload.template_id else None,
        objectives=payload.objectives, activities=payload.activities,
        resources=payload.resources,
        scheduled_date=payload.scheduled_date,
        scheduled_period_number=payload.scheduled_period_number,
        created_by=str(actor),
    )
    db.add(p)
    db.flush()
    record_audit_event(
        db, AuditLog,
        event_type=(
            "lesson_plan.template.created" if p.class_id is None
            else "lesson_plan.instance.created"
        ),
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "lesson_plan", "id": p.id},
        details={"has_class": p.class_id is not None,
                 "has_template": p.template_id is not None},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_lesson(p), "meta": _meta(request)}


@router.put("/lesson-plans/{lp_id}")
def update_lesson_plan(
    lp_id: uuid.UUID,
    payload: LessonPlanUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = (
        db.query(LessonPlan)
        .filter(LessonPlan.id == str(lp_id),
                LessonPlan.school_id == str(school_id))
        .first()
    )
    if p is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Lesson plan not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    changed = []
    for field in (
        "title", "objectives", "activities", "resources",
        "scheduled_date", "scheduled_period_number",
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(p, field, val)
            changed.append(field)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="lesson_plan.updated",
        school_id=school_id,
        actor_user_id=uuid.UUID(str(current_user["sub"])),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "lesson_plan", "id": p.id},
        details={"changed_fields": changed},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_lesson(p), "meta": _meta(request)}


# ─── T-013 — formative assessments ─────────────────────────────────


class FormativeCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=200)
    formative_kind: str = Field(..., pattern="^(poll|exit_ticket|quiz)$")
    prompt: str = Field(..., min_length=1)
    payload: Optional[dict] = None


class FormativeResponseCreate(BaseModel):
    student_id: uuid.UUID
    response_text: str = Field(..., min_length=1, max_length=4000)


def _ser_formative(f: FormativeAssessment, response_count: int = 0) -> dict:
    payload = None
    if f.payload:
        try:
            payload = json.loads(f.payload)
        except (TypeError, ValueError):
            payload = f.payload
    return {
        "id": f.id, "class_id": f.class_id,
        "subject_id": f.subject_id,
        "title": f.title, "formative_kind": f.formative_kind,
        "prompt": f.prompt, "payload": payload,
        "created_by": f.created_by,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "closed_at": f.closed_at.isoformat() if f.closed_at else None,
        "response_count": response_count,
    }


@router.get("/formative-assessments")
def list_formative(
    request: Request,
    class_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(FormativeAssessment)
        .filter(
            FormativeAssessment.school_id == str(school_id),
            FormativeAssessment.class_id == str(class_id),
        )
        .order_by(FormativeAssessment.created_at.desc())
        .all()
    )
    counts: dict[str, int] = {}
    if rows:
        ids = [r.id for r in rows]
        from sqlalchemy import func
        crows = (
            db.query(FormativeResponse.formative_assessment_id, func.count())
            .filter(FormativeResponse.formative_assessment_id.in_(ids))
            .group_by(FormativeResponse.formative_assessment_id)
            .all()
        )
        counts = {fid: int(c) for fid, c in crows}
    return {
        "data": [_ser_formative(r, counts.get(r.id, 0)) for r in rows],
        "meta": _meta(request),
    }


@router.post("/formative-assessments")
def create_formative(
    payload: FormativeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.formative_kind not in FORMATIVE_KINDS:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_KIND",
                               "message": "formative_kind invalid",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    f = FormativeAssessment(
        school_id=str(school_id),
        class_id=str(payload.class_id),
        subject_id=str(payload.subject_id) if payload.subject_id else None,
        title=payload.title,
        formative_kind=payload.formative_kind,
        prompt=payload.prompt,
        payload=json.dumps(payload.payload) if payload.payload is not None else None,
        created_by=str(actor),
    )
    db.add(f)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="formative.created",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "formative_assessment", "id": f.id},
        details={"kind": payload.formative_kind},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_formative(f, 0), "meta": _meta(request)}


@router.post("/formative-assessments/{fid}/responses")
def submit_formative_response(
    fid: uuid.UUID,
    payload: FormativeResponseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    f = (
        db.query(FormativeAssessment)
        .filter(FormativeAssessment.id == str(fid),
                FormativeAssessment.school_id == str(school_id))
        .first()
    )
    if f is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Formative not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    if f.closed_at is not None:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "CLOSED",
                               "message": "Submissions are closed.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    # Upsert: one response per student.
    existing = (
        db.query(FormativeResponse)
        .filter(
            FormativeResponse.formative_assessment_id == str(fid),
            FormativeResponse.student_id == str(payload.student_id),
        )
        .first()
    )
    if existing:
        existing.response_text = payload.response_text
        existing.submitted_at = datetime.now(timezone.utc)
        r = existing
    else:
        r = FormativeResponse(
            formative_assessment_id=str(fid),
            school_id=str(school_id),
            student_id=str(payload.student_id),
            response_text=payload.response_text,
        )
        db.add(r)
    db.flush()
    db.commit()
    return {
        "data": {"id": r.id, "submitted_at": r.submitted_at.isoformat()},
        "meta": _meta(request),
    }


# ─── T-012 — exam seat plans ──────────────────────────────────────


class SeatPlanCreate(BaseModel):
    assessment_id: uuid.UUID
    room: Optional[str] = Field(default=None, max_length=80)
    layout: list[list[Optional[uuid.UUID]]]
    notes: Optional[str] = None


def _ser_seatplan(p: ExamSeatPlan) -> dict:
    try:
        layout = json.loads(p.layout_json) if p.layout_json else []
    except (TypeError, ValueError):
        layout = []
    return {
        "id": p.id, "assessment_id": p.assessment_id,
        "room": p.room, "layout": layout, "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/exam-seat-plans")
def list_seat_plans(
    request: Request,
    assessment_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(ExamSeatPlan)
        .filter(ExamSeatPlan.school_id == str(school_id),
                ExamSeatPlan.assessment_id == str(assessment_id))
        .order_by(ExamSeatPlan.created_at.desc())
        .all()
    )
    return {"data": [_ser_seatplan(r) for r in rows], "meta": _meta(request)}


@router.post("/exam-seat-plans")
def create_seat_plan(
    payload: SeatPlanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = uuid.UUID(str(current_user["sub"]))
    p = ExamSeatPlan(
        school_id=str(school_id),
        assessment_id=str(payload.assessment_id),
        room=payload.room,
        layout_json=json.dumps([
            [str(c) if c else None for c in row] for row in payload.layout
        ]),
        notes=payload.notes,
        created_by=str(actor),
    )
    db.add(p)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="exam_seat_plan.created",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "exam_seat_plan", "id": p.id,
                "assessment_id": p.assessment_id},
        details={"rows": len(payload.layout)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_seatplan(p), "meta": _meta(request)}
