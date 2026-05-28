"""Student-life endpoints (Phase 11e)."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.student_life import (
    BehaviorIncident, SubstituteGrant, Homework, HomeworkSubmission,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)


router = APIRouter(tags=["Student Life"])


SEVERITIES = {"minor", "moderate", "serious", "critical"}
CATEGORIES = {
    "bullying", "late", "uniform", "disruption", "absence",
    "academic_dishonesty", "fighting", "other",
}



# ─── T-004 Behaviour incidents ─────────────────────────────────────


class IncidentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: Optional[uuid.UUID] = None
    occurred_at: Optional[datetime] = None
    severity: str = Field(default="minor")
    category: str = Field(default="other")
    summary: str = Field(..., min_length=1, max_length=500)
    details: Optional[str] = None


class IncidentUpdate(BaseModel):
    parent_notified_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    severity: Optional[str] = None
    details: Optional[str] = None


def _ser_incident(i: BehaviorIncident) -> dict:
    return {
        "id": i.id, "school_id": i.school_id, "student_id": i.student_id,
        "class_id": i.class_id, "reported_by": i.reported_by,
        "occurred_at": i.occurred_at.isoformat() if i.occurred_at else None,
        "severity": i.severity, "category": i.category,
        "summary": i.summary, "details": i.details,
        "parent_notified_at": i.parent_notified_at.isoformat() if i.parent_notified_at else None,
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@router.get("/incidents")
def list_incidents(
    request: Request,
    student_id: Optional[uuid.UUID] = Query(None),
    class_id: Optional[uuid.UUID] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(BehaviorIncident).filter(
        BehaviorIncident.school_id == str(school_id),
    )
    if student_id:
        q = q.filter(BehaviorIncident.student_id == str(student_id))
    if class_id:
        q = q.filter(BehaviorIncident.class_id == str(class_id))
    if severity:
        q = q.filter(BehaviorIncident.severity == severity)
    rows = q.order_by(BehaviorIncident.occurred_at.desc()).limit(500).all()
    return {"data": [_ser_incident(r) for r in rows], "meta": _meta(request)}


@router.post("/incidents")
def create_incident(
    payload: IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.severity not in SEVERITIES:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_SEVERITY",
                               "message": f"severity must be in {sorted(SEVERITIES)}",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    if payload.category not in CATEGORIES:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_CATEGORY",
                               "message": f"category must be in {sorted(CATEGORIES)}",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    i = BehaviorIncident(
        school_id=str(school_id),
        student_id=str(payload.student_id),
        class_id=str(payload.class_id) if payload.class_id else None,
        reported_by=str(actor),
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        severity=payload.severity,
        category=payload.category,
        summary=payload.summary.strip(),
        details=payload.details,
    )
    db.add(i)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="incident.created",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "behavior_incident", "id": i.id,
                "student_id": i.student_id},
        # Privacy: severity + category are admin-debuggable
        # classifications; the SUMMARY / DETAILS are not logged because
        # they often quote student behaviour verbatim.
        details={"severity": payload.severity, "category": payload.category},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_incident(i), "meta": _meta(request)}


@router.put("/incidents/{iid}")
def update_incident(
    iid: uuid.UUID,
    payload: IncidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    i = (
        db.query(BehaviorIncident)
        .filter(BehaviorIncident.id == str(iid),
                BehaviorIncident.school_id == str(school_id))
        .first()
    )
    if i is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Incident not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    changed = []
    if payload.parent_notified_at is not None:
        i.parent_notified_at = payload.parent_notified_at
        changed.append("parent_notified_at")
    if payload.resolved_at is not None:
        i.resolved_at = payload.resolved_at
        changed.append("resolved_at")
    if payload.severity is not None:
        if payload.severity not in SEVERITIES:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_SEVERITY",
                                   "message": "bad severity",
                                   "details": {},
                                   "request_id": _meta(request)["request_id"]}},
            )
        i.severity = payload.severity
        changed.append("severity")
    if payload.details is not None:
        i.details = payload.details
        changed.append("details")
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="incident.updated",
        school_id=school_id,
        actor_user_id=uuid.UUID(str(current_user["sub"])),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "behavior_incident", "id": i.id},
        details={"changed_fields": changed},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_incident(i), "meta": _meta(request)}


# ─── T-006 Substitute grants ──────────────────────────────────────


class SubstituteGrantCreate(BaseModel):
    absent_teacher_user_id: uuid.UUID
    grantee_user_id: uuid.UUID
    class_ids: Optional[list[uuid.UUID]] = None
    starts_at: datetime
    ends_at: datetime
    reason: Optional[str] = Field(default=None, max_length=200)


def _ser_grant(g: SubstituteGrant) -> dict:
    try:
        cids = json.loads(g.class_ids_json) if g.class_ids_json else None
    except (TypeError, ValueError):
        cids = None
    return {
        "id": g.id, "absent_teacher_user_id": g.absent_teacher_user_id,
        "grantee_user_id": g.grantee_user_id,
        "class_ids": cids,
        "starts_at": g.starts_at.isoformat() if g.starts_at else None,
        "ends_at": g.ends_at.isoformat() if g.ends_at else None,
        "granted_by_user_id": g.granted_by_user_id,
        "reason": g.reason,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None,
    }


@router.get("/substitute-grants")
def list_substitute_grants(
    request: Request,
    grantee_user_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(SubstituteGrant).filter(
        SubstituteGrant.school_id == str(school_id),
    )
    if grantee_user_id:
        q = q.filter(SubstituteGrant.grantee_user_id == str(grantee_user_id))
    if active_only:
        now = datetime.now(timezone.utc)
        q = q.filter(
            SubstituteGrant.revoked_at.is_(None),
            SubstituteGrant.ends_at >= now,
        )
    rows = q.order_by(SubstituteGrant.starts_at.desc()).all()
    return {"data": [_ser_grant(r) for r in rows], "meta": _meta(request)}


@router.post("/substitute-grants")
def create_substitute_grant(
    payload: SubstituteGrantCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.ends_at <= payload.starts_at:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_WINDOW",
                               "message": "ends_at must be after starts_at",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    if payload.absent_teacher_user_id == payload.grantee_user_id:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SELF_GRANT",
                               "message": "A teacher cannot substitute themselves.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    g = SubstituteGrant(
        school_id=str(school_id),
        absent_teacher_user_id=str(payload.absent_teacher_user_id),
        grantee_user_id=str(payload.grantee_user_id),
        class_ids_json=(
            json.dumps([str(c) for c in payload.class_ids])
            if payload.class_ids is not None else None
        ),
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        granted_by_user_id=str(actor),
        reason=payload.reason,
    )
    db.add(g)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="substitute.granted",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "substitute_grant", "id": g.id,
                "grantee_user_id": g.grantee_user_id,
                "absent_teacher_user_id": g.absent_teacher_user_id},
        details={"hours": round(
            (payload.ends_at - payload.starts_at).total_seconds() / 3600, 2,
        )},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_grant(g), "meta": _meta(request)}


@router.post("/substitute-grants/{gid}/revoke")
def revoke_substitute_grant(
    gid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    g = (
        db.query(SubstituteGrant)
        .filter(SubstituteGrant.id == str(gid),
                SubstituteGrant.school_id == str(school_id))
        .first()
    )
    if g is None or g.revoked_at is not None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Grant not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    g.revoked_at = datetime.now(timezone.utc)
    g.revoked_by_user_id = str(actor)
    record_audit_event(
        db, AuditLog, event_type="substitute.revoked",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "substitute_grant", "id": g.id},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_grant(g), "meta": _meta(request)}


# ─── T-003 Homework ───────────────────────────────────────────────


class HomeworkCreate(BaseModel):
    class_id: uuid.UUID
    subject_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=200)
    description: str = Field(..., min_length=1)
    due_date: date


class HomeworkSubmissionCreate(BaseModel):
    student_id: uuid.UUID
    body: Optional[str] = None


class HomeworkGradeUpdate(BaseModel):
    grade_marks: str = Field(..., max_length=20)
    grade_remarks: Optional[str] = Field(default=None, max_length=500)


def _ser_homework(h: Homework) -> dict:
    return {
        "id": h.id, "class_id": h.class_id, "subject_id": h.subject_id,
        "title": h.title, "description": h.description,
        "due_date": h.due_date.isoformat() if h.due_date else None,
        "assigned_by": h.assigned_by,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "archived_at": h.archived_at.isoformat() if h.archived_at else None,
    }


def _ser_submission(s: HomeworkSubmission) -> dict:
    return {
        "id": s.id, "homework_id": s.homework_id,
        "student_id": s.student_id, "body": s.body,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        "grade_marks": s.grade_marks, "grade_remarks": s.grade_remarks,
        "graded_by": s.graded_by,
        "graded_at": s.graded_at.isoformat() if s.graded_at else None,
    }


@router.get("/homework")
def list_homework(
    request: Request,
    class_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(Homework)
        .filter(
            Homework.school_id == str(school_id),
            Homework.class_id == str(class_id),
            Homework.archived_at.is_(None),
        )
        .order_by(Homework.due_date.asc())
        .all()
    )
    return {"data": [_ser_homework(r) for r in rows], "meta": _meta(request)}


@router.post("/homework")
def create_homework(
    payload: HomeworkCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = uuid.UUID(str(current_user["sub"]))
    h = Homework(
        school_id=str(school_id),
        class_id=str(payload.class_id),
        subject_id=str(payload.subject_id) if payload.subject_id else None,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        assigned_by=str(actor),
    )
    db.add(h)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="homework.assigned",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "homework", "id": h.id,
                "class_id": h.class_id},
        details={"due_date": h.due_date.isoformat()},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_homework(h), "meta": _meta(request)}


@router.post("/homework/{hid}/submissions")
def submit_homework(
    hid: uuid.UUID,
    payload: HomeworkSubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    h = (
        db.query(Homework)
        .filter(Homework.id == str(hid),
                Homework.school_id == str(school_id))
        .first()
    )
    if h is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Homework not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    existing = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == str(hid),
            HomeworkSubmission.student_id == str(payload.student_id),
        )
        .first()
    )
    if existing:
        existing.body = payload.body
        existing.submitted_at = datetime.now(timezone.utc)
        s = existing
    else:
        s = HomeworkSubmission(
            homework_id=str(hid),
            school_id=str(school_id),
            student_id=str(payload.student_id),
            body=payload.body,
        )
        db.add(s)
    db.flush()
    db.commit()
    return {"data": _ser_submission(s), "meta": _meta(request)}


@router.get("/homework/{hid}/submissions")
def list_submissions(
    hid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == str(hid),
            HomeworkSubmission.school_id == str(school_id),
        )
        .order_by(HomeworkSubmission.submitted_at.desc())
        .all()
    )
    return {"data": [_ser_submission(r) for r in rows], "meta": _meta(request)}


@router.put("/homework/submissions/{sid}/grade")
def grade_submission(
    sid: uuid.UUID,
    payload: HomeworkGradeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    s = (
        db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.id == str(sid),
                HomeworkSubmission.school_id == str(school_id))
        .first()
    )
    if s is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND",
                               "message": "Submission not found.",
                               "details": {},
                               "request_id": _meta(request)["request_id"]}},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    s.grade_marks = payload.grade_marks
    s.grade_remarks = payload.grade_remarks
    s.graded_by = str(actor)
    s.graded_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="homework.graded",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "homework_submission", "id": s.id,
                "homework_id": s.homework_id},
        # The grade itself is admin-visible; details capture the FACT
        # of grading, not the mark text.
        details={"length_remarks": len(payload.grade_remarks or "")},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_submission(s), "meta": _meta(request)}
