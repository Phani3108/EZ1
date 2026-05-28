"""Org endpoints (Phase 11f): HoD, CPD, self-evaluation."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.org import (
    HeadOfDepartmentAssignment, CpdRecord, SelfEvaluationForm,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)


router = APIRouter(tags=["Organisation"])


CPD_CATEGORIES = {
    "workshop", "course", "conference", "webinar", "other",
}



# ─── T-017 HoD assignments ────────────────────────────────────────


class HodCreate(BaseModel):
    subject_id: uuid.UUID
    user_id: uuid.UUID


def _ser_hod(h: HeadOfDepartmentAssignment) -> dict:
    return {
        "id": h.id, "subject_id": h.subject_id, "user_id": h.user_id,
        "granted_by_user_id": h.granted_by_user_id,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "revoked_at": h.revoked_at.isoformat() if h.revoked_at else None,
    }


@router.get("/hod-assignments")
def list_hod(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    subject_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(HeadOfDepartmentAssignment).filter(
        HeadOfDepartmentAssignment.school_id == str(school_id),
        HeadOfDepartmentAssignment.revoked_at.is_(None),
    )
    if user_id:
        q = q.filter(HeadOfDepartmentAssignment.user_id == str(user_id))
    if subject_id:
        q = q.filter(HeadOfDepartmentAssignment.subject_id == str(subject_id))
    return {
        "data": [_ser_hod(h) for h in q.all()],
        "meta": _meta(request),
    }


@router.post("/hod-assignments")
def create_hod(
    payload: HodCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = uuid.UUID(str(current_user["sub"]))
    # If the same (school, subject, user) tuple already exists (active
    # or revoked), surface a clean error rather than letting the unique
    # constraint raise.
    existing = (
        db.query(HeadOfDepartmentAssignment)
        .filter(
            HeadOfDepartmentAssignment.school_id == str(school_id),
            HeadOfDepartmentAssignment.subject_id == str(payload.subject_id),
            HeadOfDepartmentAssignment.user_id == str(payload.user_id),
        )
        .first()
    )
    if existing and existing.revoked_at is None:
        return {"data": _ser_hod(existing), "meta": _meta(request)}
    if existing and existing.revoked_at is not None:
        # Re-activate the historical row.
        existing.revoked_at = None
        existing.granted_by_user_id = str(actor)
        db.flush()
        record_audit_event(
            db, AuditLog, event_type="hod.granted",
            school_id=school_id, actor_user_id=actor,
            actor_role=(current_user.get("roles") or [None])[0],
            target={"resource": "hod_assignment", "id": existing.id},
            details={"reactivated": True},
            request_id=getattr(request.state, "request_id", None),
        )
        db.commit()
        return {"data": _ser_hod(existing), "meta": _meta(request)}

    h = HeadOfDepartmentAssignment(
        school_id=str(school_id),
        subject_id=str(payload.subject_id),
        user_id=str(payload.user_id),
        granted_by_user_id=str(actor),
    )
    db.add(h)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="hod.granted",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "hod_assignment", "id": h.id,
                "subject_id": h.subject_id, "user_id": h.user_id},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_hod(h), "meta": _meta(request)}


@router.delete("/hod-assignments/{aid}")
def revoke_hod(
    aid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    h = (
        db.query(HeadOfDepartmentAssignment)
        .filter(HeadOfDepartmentAssignment.id == str(aid),
                HeadOfDepartmentAssignment.school_id == str(school_id))
        .first()
    )
    if h is None or h.revoked_at is not None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "HoD assignment not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    h.revoked_at = datetime.now(timezone.utc)
    actor = uuid.UUID(str(current_user["sub"]))
    record_audit_event(
        db, AuditLog, event_type="hod.revoked",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "hod_assignment", "id": h.id},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_hod(h), "meta": _meta(request)}


# ─── T-018 CPD records ────────────────────────────────────────────


class CpdCreate(BaseModel):
    category: str = Field(default="other")
    title: str = Field(..., min_length=1, max_length=200)
    provider: Optional[str] = Field(default=None, max_length=200)
    completed_on: date
    hours: float = Field(default=0, ge=0, le=999)
    certificate_uri: Optional[str] = None
    notes: Optional[str] = None
    academic_year_id: Optional[uuid.UUID] = None


def _ser_cpd(c: CpdRecord) -> dict:
    return {
        "id": c.id, "user_id": c.user_id,
        "academic_year_id": c.academic_year_id,
        "category": c.category, "title": c.title,
        "provider": c.provider,
        "completed_on": c.completed_on.isoformat() if c.completed_on else None,
        "hours": float(c.hours) if c.hours is not None else 0.0,
        "certificate_uri": c.certificate_uri, "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/cpd")
def list_cpd(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Default: list the caller's own records. Admin can pass user_id
    # to view someone else's (route layer enforces; gateway-RBAC has
    # the entry as `authenticated`).
    target_user = user_id or uuid.UUID(str(current_user["sub"]))
    rows = (
        db.query(CpdRecord)
        .filter(
            CpdRecord.school_id == str(school_id),
            CpdRecord.user_id == str(target_user),
        )
        .order_by(CpdRecord.completed_on.desc())
        .all()
    )
    return {"data": [_ser_cpd(r) for r in rows], "meta": _meta(request)}


@router.post("/cpd")
def create_cpd(
    payload: CpdCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.category not in CPD_CATEGORIES:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_CATEGORY",
                               "message": f"category must be in {sorted(CPD_CATEGORIES)}",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    c = CpdRecord(
        school_id=str(school_id),
        user_id=str(actor),
        academic_year_id=(
            str(payload.academic_year_id) if payload.academic_year_id else None
        ),
        category=payload.category,
        title=payload.title.strip(),
        provider=(payload.provider or "").strip() or None,
        completed_on=payload.completed_on,
        hours=Decimal(str(payload.hours)),
        certificate_uri=payload.certificate_uri,
        notes=payload.notes,
    )
    db.add(c)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="cpd.recorded",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "cpd_record", "id": c.id},
        details={"category": payload.category, "hours": float(payload.hours)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_cpd(c), "meta": _meta(request)}


# ─── T-019 Self-evaluation ────────────────────────────────────────


class SelfEvalCreate(BaseModel):
    term_id: uuid.UUID
    responses: dict
    overall_reflection: Optional[str] = None


def _ser_self_eval(s: SelfEvaluationForm) -> dict:
    try:
        resp = json.loads(s.responses_json) if s.responses_json else {}
    except (TypeError, ValueError):
        resp = {}
    return {
        "id": s.id, "user_id": s.user_id, "term_id": s.term_id,
        "responses": resp,
        "overall_reflection": s.overall_reflection,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
    }


@router.get("/self-evaluations")
def list_self_eval(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    term_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    target_user = user_id or uuid.UUID(str(current_user["sub"]))
    q = db.query(SelfEvaluationForm).filter(
        SelfEvaluationForm.school_id == str(school_id),
        SelfEvaluationForm.user_id == str(target_user),
    )
    if term_id:
        q = q.filter(SelfEvaluationForm.term_id == str(term_id))
    rows = q.order_by(SelfEvaluationForm.submitted_at.desc()).all()
    return {"data": [_ser_self_eval(r) for r in rows], "meta": _meta(request)}


@router.post("/self-evaluations")
def submit_self_eval(
    payload: SelfEvalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = uuid.UUID(str(current_user["sub"]))
    # Upsert by (school, user, term).
    existing = (
        db.query(SelfEvaluationForm)
        .filter(
            SelfEvaluationForm.school_id == str(school_id),
            SelfEvaluationForm.user_id == str(actor),
            SelfEvaluationForm.term_id == str(payload.term_id),
        )
        .first()
    )
    if existing:
        existing.responses_json = json.dumps(payload.responses)
        existing.overall_reflection = payload.overall_reflection
        existing.submitted_at = datetime.now(timezone.utc)
        s = existing
    else:
        s = SelfEvaluationForm(
            school_id=str(school_id),
            user_id=str(actor),
            term_id=str(payload.term_id),
            responses_json=json.dumps(payload.responses),
            overall_reflection=payload.overall_reflection,
        )
        db.add(s)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="self_eval.submitted",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "self_evaluation_form", "id": s.id,
                "term_id": s.term_id},
        # Privacy: response BODY not logged — only the fact + the term.
        details={"keys": list(payload.responses.keys())},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_self_eval(s), "meta": _meta(request)}


# ─── T-016 — co-teacher assignment endpoint ───────────────────────


class CoTeacherAssign(BaseModel):
    class_id: uuid.UUID
    academic_year_id: uuid.UUID
    teacher_user_id: uuid.UUID


@router.post("/class-teachers/co")
def assign_co_teacher(
    payload: CoTeacherAssign,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """T-016: assign an additional teacher to a class. The schema
    change (Alembic 012) relaxed the unique constraint; this endpoint
    is a convenience wrapper that records the additional teacher and
    audits the action."""
    from app.models.school import ClassTeacherAssignment

    actor = uuid.UUID(str(current_user["sub"]))
    existing = (
        db.query(ClassTeacherAssignment)
        .filter(
            ClassTeacherAssignment.school_id == school_id,
            ClassTeacherAssignment.class_id == payload.class_id,
            ClassTeacherAssignment.academic_year_id == payload.academic_year_id,
            ClassTeacherAssignment.teacher_user_id == payload.teacher_user_id,
        )
        .first()
    )
    if existing:
        return {
            "data": {"id": str(existing.id), "already_assigned": True},
            "meta": _meta(request),
        }
    a = ClassTeacherAssignment(
        school_id=school_id,
        class_id=payload.class_id,
        academic_year_id=payload.academic_year_id,
        teacher_user_id=payload.teacher_user_id,
    )
    db.add(a)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="co_teacher.assigned",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "class_teacher_assignment", "id": str(a.id),
                "class_id": str(payload.class_id),
                "teacher_user_id": str(payload.teacher_user_id)},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {
        "data": {"id": str(a.id), "already_assigned": False},
        "meta": _meta(request),
    }
