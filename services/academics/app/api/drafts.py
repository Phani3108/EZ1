"""Phase 15a — Student & Parent draft queue.

Teachers (with `student:draft`) submit draft records into a per-school
queue. Admins (`school:manage`) review and approve / reject.

On approval:
  * a real `Student` row is created (with all draft fields).
  * an `Enrollment` is created if `class_id` was supplied.
  * if parent contact info is present, a `ParentDraft` is spawned in
    `pending` state (the admin reviews that draft next, OR can
    auto-approve in a single click — admins can opt to auto-approve
    parent contacts from a trusted teacher).

Audit invariants (ADR 018):
  * Submit: target = {school_id, draft_id, resource="student_draft"}.
    Details = {class_id, has_parent_contact}. NO names, NO DOB.
  * Approve: target = {school_id, draft_id, student_id}.
    Details = {approved_by}. NO names.
  * Reject: target = {school_id, draft_id}.
    Details = {approved_by, rejection_reason}. rejection_reason IS
    free text — admin-supplied and 200-char-capped (single place we
    log admin-supplied text into audit details).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.onboarding import StudentDraft, ParentDraft
from app.models.student import Student, Parent, StudentParent, Enrollment, EnrollmentStatus
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Drafts"])


DRAFT_STATUSES = ("pending", "approved", "rejected")


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _actor(current_user) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


def _err(code: str, msg: str, request: Request, status: int = 400):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request: Request, status: int = 200):
    return JSONResponse(status_code=status,
                        content={"data": data, "meta": _meta(request)})


def _ser_student_draft(d: StudentDraft) -> dict:
    return {
        "id": str(d.id),
        "school_id": str(d.school_id),
        "student_code": d.student_code,
        "first_name": d.first_name,
        "last_name": d.last_name,
        "dob": d.dob.isoformat() if d.dob else None,
        "gender": d.gender,
        "admission_date": d.admission_date.isoformat() if d.admission_date else None,
        "class_id": str(d.class_id) if d.class_id else None,
        "parent_first_name": d.parent_first_name,
        "parent_last_name": d.parent_last_name,
        "parent_phone": d.parent_phone,
        "parent_email": d.parent_email,
        "parent_relationship_type": d.parent_relationship_type,
        "submitted_by_user_id": str(d.submitted_by_user_id),
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "review_status": d.review_status,
        "reviewed_by_user_id": (
            str(d.reviewed_by_user_id) if d.reviewed_by_user_id else None
        ),
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "rejection_reason": d.rejection_reason,
        "approved_student_id": (
            str(d.approved_student_id) if d.approved_student_id else None
        ),
    }


def _ser_parent_draft(d: ParentDraft) -> dict:
    return {
        "id": str(d.id),
        "school_id": str(d.school_id),
        "first_name": d.first_name,
        "last_name": d.last_name,
        "phone": d.phone,
        "email": d.email,
        "relationship_type": d.relationship_type,
        "student_id": str(d.student_id) if d.student_id else None,
        "submitted_by_user_id": str(d.submitted_by_user_id),
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "review_status": d.review_status,
        "reviewed_by_user_id": (
            str(d.reviewed_by_user_id) if d.reviewed_by_user_id else None
        ),
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "rejection_reason": d.rejection_reason,
        "approved_parent_id": (
            str(d.approved_parent_id) if d.approved_parent_id else None
        ),
    }


def _audit(db: Session, request: Request, *, event_type: str,
           school_id: uuid.UUID, actor: uuid.UUID,
           target: dict, details: Optional[dict] = None):
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    try:
        record_audit_event(
            db, AuditLog,
            event_type=event_type,
            school_id=school_id,
            actor_user_id=actor,
            target=target,
            details=details or {},
            request_id=request_id,
        )
    except Exception:
        pass


# ─── Schemas ──────────────────────────────────────────────────────


class StudentDraftSubmit(BaseModel):
    student_code: Optional[str] = Field(default=None, max_length=50)
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    dob: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=10)
    admission_date: Optional[date] = None
    class_id: Optional[uuid.UUID] = None
    parent_first_name: Optional[str] = Field(default=None, max_length=255)
    parent_last_name: Optional[str] = Field(default=None, max_length=255)
    parent_phone: Optional[str] = Field(default=None, max_length=32)
    parent_email: Optional[EmailStr] = None
    parent_relationship_type: Optional[str] = Field(default=None, max_length=20)


class DraftApprove(BaseModel):
    student_code: Optional[str] = Field(default=None, max_length=50)
    class_id: Optional[uuid.UUID] = None
    academic_year_id: Optional[uuid.UUID] = None


class DraftReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)


# ─── Endpoints ────────────────────────────────────────────────────


@router.post("/drafts/students")
def submit_student_draft(
    body: StudentDraftSubmit,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Teacher submits a draft. Tenant scoped to the teacher's school."""
    d = StudentDraft(
        id=uuid.uuid4(),
        school_id=school_id,
        student_code=body.student_code,
        first_name=body.first_name,
        last_name=body.last_name,
        dob=body.dob,
        gender=body.gender,
        admission_date=body.admission_date,
        class_id=body.class_id,
        parent_first_name=body.parent_first_name,
        parent_last_name=body.parent_last_name,
        parent_phone=body.parent_phone,
        parent_email=str(body.parent_email) if body.parent_email else None,
        parent_relationship_type=body.parent_relationship_type,
        submitted_by_user_id=_actor(current_user),
    )
    db.add(d)
    db.flush()
    has_parent_contact = bool(body.parent_phone or body.parent_email)
    _audit(
        db, request,
        event_type="student.draft.submitted",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "student_draft", "id": str(d.id),
                "school_id": str(school_id)},
        details={"class_id": str(body.class_id) if body.class_id else None,
                 "has_parent_contact": has_parent_contact},
    )
    db.commit()
    return _ok(_ser_student_draft(d), request, status=201)


@router.get("/drafts/students")
def list_student_drafts(
    request: Request,
    status: Optional[Literal["pending", "approved", "rejected"]] = Query(
        default="pending"
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(StudentDraft).filter(StudentDraft.school_id == school_id)
    if status:
        q = q.filter(StudentDraft.review_status == status)
    rows = q.order_by(StudentDraft.submitted_at.desc()).limit(500).all()
    return _ok([_ser_student_draft(r) for r in rows], request)


@router.post("/drafts/students/{draft_id}/approve")
def approve_student_draft(
    draft_id: uuid.UUID,
    body: DraftApprove,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Approve a pending draft. Creates real Student row + optional
    Enrollment + spawns a ParentDraft if parent contact info was
    captured."""
    d = (
        db.query(StudentDraft)
        .filter(StudentDraft.id == draft_id,
                StudentDraft.school_id == school_id)
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found in this school.",
                    request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)

    student_code = body.student_code or d.student_code
    if not student_code:
        return _err("STUDENT_CODE_REQUIRED",
                    "A student_code must be supplied (either on the "
                    "draft or in the approval body).",
                    request, status=400)

    # Idempotency / uniqueness — (school_id, student_code) unique.
    dup = (
        db.query(Student)
        .filter(Student.school_id == school_id,
                Student.student_code == student_code)
        .first()
    )
    if dup:
        return _err("STUDENT_CODE_TAKEN",
                    "A student with that code already exists.",
                    request, status=409)

    s = Student(
        id=uuid.uuid4(),
        school_id=school_id,
        student_code=student_code,
        first_name=d.first_name,
        last_name=d.last_name,
        dob=d.dob,
        gender=d.gender,
        admission_date=d.admission_date,
    )
    db.add(s)
    db.flush()

    if body.class_id and body.academic_year_id:
        e = Enrollment(
            id=uuid.uuid4(),
            school_id=school_id,
            student_id=s.id,
            class_id=body.class_id,
            academic_year_id=body.academic_year_id,
            status=EnrollmentStatus.ENROLLED.value,
        )
        db.add(e)
    elif d.class_id and body.academic_year_id:
        e = Enrollment(
            id=uuid.uuid4(),
            school_id=school_id,
            student_id=s.id,
            class_id=d.class_id,
            academic_year_id=body.academic_year_id,
            status=EnrollmentStatus.ENROLLED.value,
        )
        db.add(e)

    # Auto-spawn a ParentDraft if parent contact info was captured.
    if d.parent_phone or d.parent_email:
        pd = ParentDraft(
            id=uuid.uuid4(),
            school_id=school_id,
            first_name=d.parent_first_name or "(unknown)",
            last_name=d.parent_last_name or "(unknown)",
            phone=d.parent_phone or "",
            email=d.parent_email,
            relationship_type=d.parent_relationship_type or "GUARDIAN",
            student_id=s.id,
            submitted_by_user_id=_actor(current_user),
            review_status="pending",
        )
        db.add(pd)

    d.review_status = "approved"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.approved_student_id = s.id

    _audit(
        db, request,
        event_type="student.draft.approved",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "student_draft", "id": str(d.id),
                "school_id": str(school_id),
                "student_id": str(s.id)},
        details={"approved_by": str(_actor(current_user))},
    )
    db.commit()
    return _ok({
        "draft": _ser_student_draft(d),
        "student_id": str(s.id),
    }, request)


@router.post("/drafts/students/{draft_id}/reject")
def reject_student_draft(
    draft_id: uuid.UUID,
    body: DraftReject,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    d = (
        db.query(StudentDraft)
        .filter(StudentDraft.id == draft_id,
                StudentDraft.school_id == school_id)
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found in this school.",
                    request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)

    d.review_status = "rejected"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.rejection_reason = body.reason

    _audit(
        db, request,
        event_type="student.draft.rejected",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "student_draft", "id": str(d.id),
                "school_id": str(school_id)},
        details={"approved_by": str(_actor(current_user)),
                 "rejection_reason": body.reason},
    )
    db.commit()
    return _ok(_ser_student_draft(d), request)


@router.get("/drafts/parents")
def list_parent_drafts(
    request: Request,
    status: Optional[Literal["pending", "approved", "rejected"]] = Query(
        default="pending"
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(ParentDraft).filter(ParentDraft.school_id == school_id)
    if status:
        q = q.filter(ParentDraft.review_status == status)
    rows = q.order_by(ParentDraft.submitted_at.desc()).limit(500).all()
    return _ok([_ser_parent_draft(r) for r in rows], request)


@router.post("/drafts/parents/{draft_id}/approve")
def approve_parent_draft(
    draft_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    d = (
        db.query(ParentDraft)
        .filter(ParentDraft.id == draft_id,
                ParentDraft.school_id == school_id)
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found in this school.",
                    request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)

    # Reuse existing parent if phone matches (per uq_parent_school_phone).
    p = (
        db.query(Parent)
        .filter(Parent.school_id == school_id, Parent.phone == d.phone)
        .first()
    )
    if not p:
        p = Parent(
            id=uuid.uuid4(),
            school_id=school_id,
            first_name=d.first_name,
            last_name=d.last_name,
            phone=d.phone or "(unknown)",
            email=d.email,
            relationship_type=d.relationship_type or "GUARDIAN",
        )
        db.add(p)
        db.flush()

    # Link to the student if known.
    if d.student_id:
        existing_link = (
            db.query(StudentParent)
            .filter(StudentParent.student_id == d.student_id,
                    StudentParent.parent_id == p.id)
            .first()
        )
        if not existing_link:
            db.add(StudentParent(
                id=uuid.uuid4(),
                school_id=school_id,
                student_id=d.student_id,
                parent_id=p.id,
                is_primary=False,
            ))

    d.review_status = "approved"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.approved_parent_id = p.id

    _audit(
        db, request,
        event_type="parent.draft.approved",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "parent_draft", "id": str(d.id),
                "school_id": str(school_id),
                "parent_id": str(p.id)},
        details={"approved_by": str(_actor(current_user))},
    )
    db.commit()
    return _ok({
        "draft": _ser_parent_draft(d),
        "parent_id": str(p.id),
    }, request)


@router.post("/drafts/parents/{draft_id}/reject")
def reject_parent_draft(
    draft_id: uuid.UUID,
    body: DraftReject,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    d = (
        db.query(ParentDraft)
        .filter(ParentDraft.id == draft_id,
                ParentDraft.school_id == school_id)
        .first()
    )
    if not d:
        return _err("DRAFT_NOT_FOUND", "Draft not found in this school.",
                    request, status=404)
    if d.review_status != "pending":
        return _err("DRAFT_ALREADY_REVIEWED",
                    f"Draft is already {d.review_status}.",
                    request, status=409)

    d.review_status = "rejected"
    d.reviewed_by_user_id = _actor(current_user)
    d.reviewed_at = datetime.now(timezone.utc)
    d.rejection_reason = body.reason

    _audit(
        db, request,
        event_type="parent.draft.rejected",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "parent_draft", "id": str(d.id),
                "school_id": str(school_id)},
        details={"approved_by": str(_actor(current_user)),
                 "rejection_reason": body.reason},
    )
    db.commit()
    return _ok(_ser_parent_draft(d), request)
