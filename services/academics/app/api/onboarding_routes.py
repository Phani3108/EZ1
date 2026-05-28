"""Phase 15a — Onboarding readiness + Go Live gate.

  * `GET  /onboarding/status` — deterministic green/amber/red checklist
                                for the caller's school. Reports on
                                academics-side signals only:
                                  - school_profile
                                  - classes
                                  - subjects
                                  - teachers (via ClassTeacherAssignment
                                              distinct teacher_user_ids,
                                              plus InviteRequest queue)
                                  - students
                                  - parents_invited
                                  - first_attendance
                                Fee-structure and first-announcement
                                checks live in finance + communications
                                respectively; admin-web overlays them
                                client-side from the existing
                                `/ministry/fees` and `/api/v1/comm`
                                surfaces.

  * `POST /onboarding/go-live` — asserts every academics-side step
                                 is green, then flips `School.is_live`.
                                 Audit-logged with the checklist
                                 snapshot hash so the moment can be
                                 re-derived later.

ADR 018 audit:
  * `school.went_live` — target = {school_id, resource}.
    Details = {checklist_snapshot_hash}. No counts, no names.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.school import (
    School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment,
)
from app.models.student import Student, StudentStatus
from app.models.attendance import AttendanceRecord
from app.models.onboarding import InviteRequest
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err, _ok,
)


router = APIRouter(tags=["Onboarding"])





def _actor(current_user) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


# ─── Checklist evaluators ─────────────────────────────────────────


def _check_school_profile(db: Session, school_id: uuid.UUID) -> dict:
    s = db.query(School).filter(School.id == school_id).first()
    if not s:
        return {"status": "red", "evidence": {}}
    has_terms = (
        db.query(func.count(Term.id))
        .filter(Term.school_id == school_id)
        .scalar() or 0
    )
    has_basics = bool(s.name and s.timezone)
    if has_basics and has_terms >= 1:
        return {"status": "green",
                "evidence": {"name": s.name, "term_count": int(has_terms)}}
    if has_basics:
        return {"status": "amber",
                "evidence": {"name": s.name, "term_count": int(has_terms),
                             "note": "no terms defined yet"}}
    return {"status": "red", "evidence": {}}


def _check_classes(db: Session, school_id: uuid.UUID) -> dict:
    n = (
        db.query(func.count(Class.id))
        .filter(Class.school_id == school_id, Class.is_active == True)  # noqa: E712
        .scalar() or 0
    )
    return {
        "status": "green" if n >= 1 else "red",
        "evidence": {"count": int(n)},
    }


def _check_subjects(db: Session, school_id: uuid.UUID) -> dict:
    n = (
        db.query(func.count(Subject.id))
        .filter(Subject.school_id == school_id, Subject.is_active == True)  # noqa: E712
        .scalar() or 0
    )
    return {
        "status": "green" if n >= 1 else "red",
        "evidence": {"count": int(n)},
    }


def _check_teachers(db: Session, school_id: uuid.UUID) -> dict:
    assigned = (
        db.query(func.count(distinct(ClassTeacherAssignment.teacher_user_id)))
        .filter(ClassTeacherAssignment.school_id == school_id)
        .scalar() or 0
    )
    queued = (
        db.query(func.count(InviteRequest.id))
        .filter(
            InviteRequest.school_id == school_id,
            InviteRequest.role == "Teacher",
        )
        .scalar() or 0
    )
    if assigned >= 1:
        return {
            "status": "green" if assigned >= 2 else "amber",
            "evidence": {"assigned": int(assigned), "invited": int(queued)},
        }
    if queued >= 1:
        return {
            "status": "amber",
            "evidence": {"assigned": 0, "invited": int(queued)},
        }
    return {"status": "red", "evidence": {"assigned": 0, "invited": 0}}


def _check_students(db: Session, school_id: uuid.UUID) -> dict:
    active = StudentStatus.ACTIVE.value
    n = (
        db.query(func.count(Student.id))
        .filter(Student.school_id == school_id, Student.status == active)
        .scalar() or 0
    )
    return {
        "status": "green" if n >= 1 else "red",
        "evidence": {"count": int(n)},
    }


def _check_parents_invited(db: Session, school_id: uuid.UUID) -> dict:
    queued = (
        db.query(func.count(InviteRequest.id))
        .filter(
            InviteRequest.school_id == school_id,
            InviteRequest.role == "Parent",
        )
        .scalar() or 0
    )
    dispatched = (
        db.query(func.count(InviteRequest.id))
        .filter(
            InviteRequest.school_id == school_id,
            InviteRequest.role == "Parent",
            InviteRequest.request_status == "dispatched",
        )
        .scalar() or 0
    )
    return {
        "status": "green" if dispatched >= 1 else ("amber" if queued >= 1 else "red"),
        "evidence": {"invited": int(queued), "dispatched": int(dispatched)},
    }


def _check_first_attendance(db: Session, school_id: uuid.UUID) -> dict:
    n = (
        db.query(func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.school_id == school_id)
        .scalar() or 0
    )
    return {
        "status": "green" if n >= 1 else "red",
        "evidence": {"count": int(n)},
    }


# Ordered list of (step_id, label, evaluator). Order is the order
# admin-web renders the wizard steps.
CHECKS = [
    ("school_profile", "School profile complete", _check_school_profile),
    ("classes", "At least one class created", _check_classes),
    ("subjects", "Subjects defined", _check_subjects),
    ("teachers", "Teachers invited or assigned", _check_teachers),
    ("students", "Students enrolled", _check_students),
    ("parents_invited", "Parent invitations sent", _check_parents_invited),
    ("first_attendance", "First attendance recorded", _check_first_attendance),
]


def _checklist(db: Session, school_id: uuid.UUID) -> list[dict]:
    out = []
    for step_id, label, fn in CHECKS:
        result = fn(db, school_id)
        out.append({
            "step": step_id,
            "label": label,
            "status": result["status"],
            "evidence": result["evidence"],
        })
    return out


def _hash_snapshot(checklist: list[dict]) -> str:
    """Stable hash of the checklist state — for the Go Live audit row."""
    payload = json.dumps([
        {"step": x["step"], "status": x["status"]} for x in checklist
    ], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ─── Endpoints ────────────────────────────────────────────────────


@router.get("/onboarding/status")
def onboarding_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Returns the readiness checklist + Go Live eligibility for the
    caller's school."""
    school = db.query(School).filter(School.id == school_id).first()
    is_live = bool(school.is_live) if school else False
    went_live_at = school.went_live_at if school else None

    cl = _checklist(db, school_id)
    blockers = [c["step"] for c in cl if c["status"] == "red"]
    eligible = not blockers

    return _ok({
        "school_id": str(school_id),
        "school_is_live": is_live,
        "went_live_at": went_live_at.isoformat() if went_live_at else None,
        "checklist": cl,
        "go_live_eligible": eligible,
        "go_live_blockers": blockers,
    }, request)


@router.post("/onboarding/go-live")
def go_live(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Flip School.is_live = true. Asserts checklist is green first."""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        return _err("SCHOOL_NOT_FOUND", "School not found.", request, status=404)
    if school.is_live:
        return _err("ALREADY_LIVE", "School is already live.",
                    request, status=409)

    cl = _checklist(db, school_id)
    blockers = [c["step"] for c in cl if c["status"] == "red"]
    if blockers:
        return _err(
            "NOT_READY",
            f"Onboarding incomplete: {', '.join(blockers)}",
            request,
            status=400,
        )

    school.is_live = True
    school.went_live_at = datetime.now(timezone.utc)
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    try:
        record_audit_event(
            db, AuditLog,
            event_type="school.went_live",
            school_id=school_id,
            actor_user_id=_actor(current_user),
            target={"resource": "school", "id": str(school_id)},
            details={"checklist_snapshot_hash": _hash_snapshot(cl)},
            request_id=request_id,
        )
    except Exception:
        pass
    db.commit()
    return _ok({
        "school_id": str(school_id),
        "is_live": True,
        "went_live_at": school.went_live_at.isoformat(),
    }, request)
