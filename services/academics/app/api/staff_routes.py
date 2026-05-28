"""Staff + HR + admissions + transfers endpoints — Phase 13a."""
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
from app.models.staff import (
    NonTeachingStaff, LeaveRequest, EmploymentContract,
    SalarySlip, PerformanceReview, AdmissionApplication, StudentTransfer,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Staff & HR"])


STAFF_ROLE_CATEGORIES = {
    "accountant", "driver", "security", "cleaner", "it_support",
    "nurse", "cook", "librarian", "groundskeeper", "other",
}
LEAVE_TYPES = {
    "annual", "sick", "unpaid", "compassionate",
    "study", "maternity", "paternity", "other",
}
LEAVE_STATUSES = {"open", "approved", "rejected", "cancelled"}
ADMISSION_STATUSES = {"submitted", "in_review", "accepted", "rejected", "enrolled"}
PERF_RATINGS = {"outstanding", "satisfactory", "needs_improvement", "unsatisfactory"}
TRANSFER_DIRECTIONS = {"inbound", "outbound"}


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _actor(current_user: dict) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


def _err(code, msg, request, status_code=400):
    return JSONResponse(
        status_code=status_code,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


# ─── A-001 — Non-teaching staff ───────────────────────────────────


class StaffCreate(BaseModel):
    role_category: str = Field(default="other", max_length=32)
    staff_code: str = Field(..., max_length=50)
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    user_id: Optional[uuid.UUID] = None
    hired_on: Optional[date] = None


def _ser_staff(s: NonTeachingStaff) -> dict:
    return {
        "id": s.id, "role_category": s.role_category,
        "staff_code": s.staff_code,
        "first_name": s.first_name, "last_name": s.last_name,
        "phone": s.phone, "email": s.email, "user_id": s.user_id,
        "hired_on": s.hired_on.isoformat() if s.hired_on else None,
        "terminated_on": s.terminated_on.isoformat() if s.terminated_on else None,
        "is_active": bool(s.is_active),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/staff")
def list_staff(
    request: Request,
    role_category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(NonTeachingStaff).filter(
        NonTeachingStaff.school_id == str(school_id),
    )
    if role_category:
        q = q.filter(NonTeachingStaff.role_category == role_category)
    if active_only:
        q = q.filter(NonTeachingStaff.is_active.is_(True))
    rows = q.order_by(NonTeachingStaff.created_at.desc()).all()
    return {"data": [_ser_staff(r) for r in rows], "meta": _meta(request)}


@router.post("/staff")
def create_staff(
    payload: StaffCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.role_category not in STAFF_ROLE_CATEGORIES:
        return _err("INVALID_ROLE_CATEGORY",
                    f"must be in {sorted(STAFF_ROLE_CATEGORIES)}", request)
    s = NonTeachingStaff(
        school_id=str(school_id),
        role_category=payload.role_category,
        staff_code=payload.staff_code,
        first_name=payload.first_name, last_name=payload.last_name,
        phone=payload.phone, email=payload.email,
        user_id=str(payload.user_id) if payload.user_id else None,
        hired_on=payload.hired_on,
    )
    db.add(s)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="staff.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "non_teaching_staff", "id": s.id},
        # Role + code are admin-debuggable; names + contact info are PII.
        details={"role_category": payload.role_category},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_staff(s), "meta": _meta(request)}


@router.post("/staff/{sid}/terminate")
def terminate_staff(
    sid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    s = (
        db.query(NonTeachingStaff)
        .filter(NonTeachingStaff.id == str(sid),
                NonTeachingStaff.school_id == str(school_id))
        .first()
    )
    if s is None or not s.is_active:
        return _err("NOT_FOUND", "Active staff record not found.", request, 404)
    s.is_active = False
    s.terminated_on = date.today()
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="staff.terminated",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "non_teaching_staff", "id": s.id},
        details={"role_category": s.role_category},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_staff(s), "meta": _meta(request)}


# ─── A-002 — Leave requests ───────────────────────────────────────


class LeaveCreate(BaseModel):
    leave_type: str = Field(default="annual", max_length=32)
    starts_on: date
    ends_on: date
    reason: Optional[str] = None


class LeaveDecide(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    decision_notes: Optional[str] = Field(default=None, max_length=500)


def _ser_leave(l: LeaveRequest) -> dict:
    return {
        "id": l.id, "user_id": l.user_id,
        "leave_type": l.leave_type,
        "starts_on": l.starts_on.isoformat() if l.starts_on else None,
        "ends_on": l.ends_on.isoformat() if l.ends_on else None,
        "reason": l.reason, "status": l.status,
        "decided_by_user_id": l.decided_by_user_id,
        "decided_at": l.decided_at.isoformat() if l.decided_at else None,
        "decision_notes": l.decision_notes,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


@router.get("/leave-requests")
def list_leave(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(LeaveRequest).filter(LeaveRequest.school_id == str(school_id))
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    is_admin = any(r in ("admin", "principal") for r in roles)
    if not is_admin:
        q = q.filter(LeaveRequest.user_id == str(_actor(current_user)))
    elif user_id:
        q = q.filter(LeaveRequest.user_id == str(user_id))
    if status:
        q = q.filter(LeaveRequest.status == status)
    rows = q.order_by(desc(LeaveRequest.created_at)).all()
    return {"data": [_ser_leave(r) for r in rows], "meta": _meta(request)}


@router.post("/leave-requests")
def create_leave(
    payload: LeaveCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.leave_type not in LEAVE_TYPES:
        return _err("INVALID_LEAVE_TYPE",
                    f"must be in {sorted(LEAVE_TYPES)}", request)
    if payload.ends_on < payload.starts_on:
        return _err("INVALID_WINDOW",
                    "ends_on must be on or after starts_on", request)
    actor = _actor(current_user)
    l = LeaveRequest(
        school_id=str(school_id), user_id=str(actor),
        leave_type=payload.leave_type,
        starts_on=payload.starts_on, ends_on=payload.ends_on,
        reason=payload.reason,
    )
    db.add(l)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="leave.requested",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "leave_request", "id": l.id},
        details={"leave_type": payload.leave_type,
                 "days": (payload.ends_on - payload.starts_on).days + 1},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_leave(l), "meta": _meta(request)}


@router.put("/leave-requests/{lid}/decide")
def decide_leave(
    lid: uuid.UUID, payload: LeaveDecide,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    l = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == str(lid),
                LeaveRequest.school_id == str(school_id))
        .first()
    )
    if l is None:
        return _err("NOT_FOUND", "Leave request not found.", request, 404)
    if l.status != "open":
        return _err("ALREADY_DECIDED", "Request already decided.", request, 409)
    actor = _actor(current_user)
    l.status = payload.status
    l.decided_by_user_id = str(actor)
    l.decided_at = datetime.now(timezone.utc)
    l.decision_notes = payload.decision_notes
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=f"leave.{payload.status}",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "leave_request", "id": l.id},
        details={"leave_type": l.leave_type},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_leave(l), "meta": _meta(request)}


# ─── A-002 — Contracts ────────────────────────────────────────────


class ContractCreate(BaseModel):
    user_id: uuid.UUID
    role_title: str = Field(..., max_length=120)
    salary_band: Optional[str] = Field(default=None, max_length=32)
    starts_on: date
    ends_on: Optional[date] = None
    attachment_id: Optional[uuid.UUID] = None


def _ser_contract(c: EmploymentContract) -> dict:
    return {
        "id": c.id, "user_id": c.user_id, "role_title": c.role_title,
        "salary_band": c.salary_band,
        "starts_on": c.starts_on.isoformat() if c.starts_on else None,
        "ends_on": c.ends_on.isoformat() if c.ends_on else None,
        "attachment_id": c.attachment_id,
        "terminated_at": c.terminated_at.isoformat() if c.terminated_at else None,
        "termination_reason": c.termination_reason,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/contracts")
def list_contracts(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(EmploymentContract).filter(
        EmploymentContract.school_id == str(school_id),
    )
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    is_admin = any(r in ("admin", "principal") for r in roles)
    if not is_admin:
        q = q.filter(EmploymentContract.user_id == str(_actor(current_user)))
    elif user_id:
        q = q.filter(EmploymentContract.user_id == str(user_id))
    rows = q.order_by(desc(EmploymentContract.created_at)).all()
    return {"data": [_ser_contract(r) for r in rows], "meta": _meta(request)}


@router.post("/contracts")
def create_contract(
    payload: ContractCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = _actor(current_user)
    c = EmploymentContract(
        school_id=str(school_id),
        user_id=str(payload.user_id),
        role_title=payload.role_title,
        salary_band=payload.salary_band,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        attachment_id=str(payload.attachment_id) if payload.attachment_id else None,
        created_by_user_id=str(actor),
    )
    db.add(c)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="contract.issued",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "employment_contract", "id": c.id,
                "user_id": str(payload.user_id)},
        # Phase 19d audit fix: role_title is free String — admins were
        # entering "Bursar - Mr. Mhondoro temporary" style values that
        # leaked PII through the audit log. Band is the only safe
        # signal here (already documented as admin-debuggable).
        details={"salary_band": payload.salary_band},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_contract(c), "meta": _meta(request)}


# ─── A-002 — Salary slips ─────────────────────────────────────────


class SalarySlipCreate(BaseModel):
    user_id: uuid.UUID
    period_year: int = Field(..., ge=2020, le=2099)
    period_month: int = Field(..., ge=1, le=12)
    gross_cents: int = Field(..., ge=0)
    deductions_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=3)
    attachment_id: Optional[uuid.UUID] = None


def _ser_slip(s: SalarySlip) -> dict:
    return {
        "id": s.id, "user_id": s.user_id,
        "period_year": s.period_year, "period_month": s.period_month,
        "gross_cents": s.gross_cents,
        "deductions_cents": s.deductions_cents,
        "net_cents": s.net_cents, "currency": s.currency,
        "attachment_id": s.attachment_id,
        "issued_at": s.issued_at.isoformat() if s.issued_at else None,
    }


@router.get("/salary-slips")
def list_slips(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    is_admin = any(r in ("admin", "principal") for r in roles)
    target_user = (user_id if (is_admin and user_id) else _actor(current_user))
    rows = (
        db.query(SalarySlip)
        .filter(SalarySlip.school_id == str(school_id),
                SalarySlip.user_id == str(target_user))
        .order_by(desc(SalarySlip.period_year), desc(SalarySlip.period_month))
        .all()
    )
    return {"data": [_ser_slip(r) for r in rows], "meta": _meta(request)}


@router.post("/salary-slips")
def create_slip(
    payload: SalarySlipCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = _actor(current_user)
    net = payload.gross_cents - payload.deductions_cents
    s = SalarySlip(
        school_id=str(school_id),
        user_id=str(payload.user_id),
        period_year=payload.period_year,
        period_month=payload.period_month,
        gross_cents=payload.gross_cents,
        deductions_cents=payload.deductions_cents,
        net_cents=net,
        currency=payload.currency,
        attachment_id=str(payload.attachment_id) if payload.attachment_id else None,
    )
    db.add(s)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="salary_slip.issued",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "salary_slip", "id": s.id,
                "user_id": str(payload.user_id)},
        # Net amount IS the audit story for a money move per ADR 018.
        details={"net_cents": net, "currency": payload.currency,
                 "period": f"{payload.period_year}-{payload.period_month:02d}"},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_slip(s), "meta": _meta(request)}


# ─── A-002 — Performance reviews ─────────────────────────────────


class PerfCreate(BaseModel):
    user_id: uuid.UUID
    period_label: str = Field(..., max_length=80)
    overall_rating: str = Field(..., max_length=32)
    criteria: Optional[dict] = None
    summary: Optional[str] = None


def _ser_perf(p: PerformanceReview) -> dict:
    try:
        crit = json.loads(p.criteria_json) if p.criteria_json else None
    except (TypeError, ValueError):
        crit = None
    return {
        "id": p.id, "user_id": p.user_id,
        "reviewer_user_id": p.reviewer_user_id,
        "period_label": p.period_label,
        "overall_rating": p.overall_rating,
        "criteria": crit, "summary": p.summary,
        "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
    }


@router.get("/performance-reviews")
def list_perf(
    request: Request,
    user_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    is_admin = any(r in ("admin", "principal") for r in roles)
    target_user = user_id if (is_admin and user_id) else _actor(current_user)
    rows = (
        db.query(PerformanceReview)
        .filter(PerformanceReview.school_id == str(school_id),
                PerformanceReview.user_id == str(target_user))
        .order_by(desc(PerformanceReview.submitted_at))
        .all()
    )
    return {"data": [_ser_perf(r) for r in rows], "meta": _meta(request)}


@router.post("/performance-reviews")
def create_perf(
    payload: PerfCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.overall_rating not in PERF_RATINGS:
        return _err("INVALID_RATING",
                    f"must be in {sorted(PERF_RATINGS)}", request)
    actor = _actor(current_user)
    p = PerformanceReview(
        school_id=str(school_id),
        user_id=str(payload.user_id),
        reviewer_user_id=str(actor),
        period_label=payload.period_label,
        overall_rating=payload.overall_rating,
        criteria_json=json.dumps(payload.criteria) if payload.criteria else None,
        summary=payload.summary,
    )
    db.add(p)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="performance_review.submitted",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "performance_review", "id": p.id,
                "user_id": str(payload.user_id)},
        # Rating + period are admin-debuggable; summary text is NOT.
        details={"rating": payload.overall_rating,
                 "period": payload.period_label},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_perf(p), "meta": _meta(request)}


# ─── A-003 — Admissions ──────────────────────────────────────────


class AdmissionCreate(BaseModel):
    applicant_first_name: str = Field(..., max_length=255)
    applicant_last_name: str = Field(..., max_length=255)
    applicant_dob: Optional[date] = None
    applicant_gender: Optional[str] = Field(default=None, max_length=10)
    guardian_first_name: str = Field(..., max_length=255)
    guardian_last_name: str = Field(..., max_length=255)
    guardian_phone: str = Field(..., max_length=20)
    guardian_email: Optional[str] = Field(default=None, max_length=255)
    target_class_label: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = None


class AdmissionDecide(BaseModel):
    status: str = Field(..., pattern="^(in_review|accepted|rejected|enrolled)$")
    decision_notes: Optional[str] = Field(default=None, max_length=500)
    # When `status=enrolled`, the admin can pass the resulting Student.id.
    student_id: Optional[uuid.UUID] = None


def _ser_admission(a: AdmissionApplication) -> dict:
    return {
        "id": a.id,
        "applicant_first_name": a.applicant_first_name,
        "applicant_last_name": a.applicant_last_name,
        "applicant_dob": a.applicant_dob.isoformat() if a.applicant_dob else None,
        "applicant_gender": a.applicant_gender,
        "guardian_first_name": a.guardian_first_name,
        "guardian_last_name": a.guardian_last_name,
        "guardian_phone": a.guardian_phone,
        "guardian_email": a.guardian_email,
        "target_class_label": a.target_class_label,
        "notes": a.notes, "status": a.status,
        "decided_by_user_id": a.decided_by_user_id,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "decision_notes": a.decision_notes,
        "student_id": a.student_id,
        "enrolled_at": a.enrolled_at.isoformat() if a.enrolled_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/admissions")
def list_admissions(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(AdmissionApplication).filter(
        AdmissionApplication.school_id == str(school_id),
    )
    if status:
        q = q.filter(AdmissionApplication.status == status)
    rows = q.order_by(desc(AdmissionApplication.created_at)).all()
    return {"data": [_ser_admission(r) for r in rows], "meta": _meta(request)}


@router.post("/admissions")
def create_admission(
    payload: AdmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = AdmissionApplication(
        school_id=str(school_id),
        applicant_first_name=payload.applicant_first_name,
        applicant_last_name=payload.applicant_last_name,
        applicant_dob=payload.applicant_dob,
        applicant_gender=payload.applicant_gender,
        guardian_first_name=payload.guardian_first_name,
        guardian_last_name=payload.guardian_last_name,
        guardian_phone=payload.guardian_phone,
        guardian_email=payload.guardian_email,
        target_class_label=payload.target_class_label,
        notes=payload.notes,
    )
    db.add(a)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="admission.submitted",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "admission_application", "id": a.id},
        # Class hint is admin-debuggable; names + contacts are PII.
        details={"target_class_label": payload.target_class_label},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_admission(a), "meta": _meta(request)}


@router.put("/admissions/{aid}/decide")
def decide_admission(
    aid: uuid.UUID, payload: AdmissionDecide,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = (
        db.query(AdmissionApplication)
        .filter(AdmissionApplication.id == str(aid),
                AdmissionApplication.school_id == str(school_id))
        .first()
    )
    if a is None:
        return _err("NOT_FOUND", "Admission application not found.", request, 404)
    if payload.status not in ADMISSION_STATUSES:
        return _err("INVALID_STATUS",
                    f"must be in {sorted(ADMISSION_STATUSES)}", request)
    actor = _actor(current_user)
    a.status = payload.status
    a.decided_by_user_id = str(actor)
    a.decided_at = datetime.now(timezone.utc)
    a.decision_notes = payload.decision_notes
    if payload.status == "enrolled":
        if payload.student_id is None:
            return _err("STUDENT_ID_REQUIRED",
                        "student_id required when enrolling.", request)
        a.student_id = str(payload.student_id)
        a.enrolled_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=f"admission.{payload.status}",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "admission_application", "id": a.id,
                "student_id": a.student_id},
        details={"status": payload.status},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_admission(a), "meta": _meta(request)}


# ─── A-004 — Transfers ───────────────────────────────────────────


class TransferCreate(BaseModel):
    student_id: uuid.UUID
    direction: str = Field(..., pattern="^(inbound|outbound)$")
    counterparty_school_name: Optional[str] = Field(default=None, max_length=255)
    counterparty_school_contact: Optional[str] = Field(default=None, max_length=255)
    reason: Optional[str] = None
    transcript_attachment_id: Optional[uuid.UUID] = None
    effective_date: date


def _ser_transfer(t: StudentTransfer) -> dict:
    return {
        "id": t.id, "student_id": t.student_id,
        "direction": t.direction,
        "counterparty_school_name": t.counterparty_school_name,
        "counterparty_school_contact": t.counterparty_school_contact,
        "reason": t.reason,
        "transcript_attachment_id": t.transcript_attachment_id,
        "effective_date": t.effective_date.isoformat() if t.effective_date else None,
        "initiated_by_user_id": t.initiated_by_user_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/transfers")
def list_transfers(
    request: Request,
    direction: Optional[str] = Query(None),
    student_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(StudentTransfer).filter(
        StudentTransfer.school_id == str(school_id),
    )
    if direction:
        q = q.filter(StudentTransfer.direction == direction)
    if student_id:
        q = q.filter(StudentTransfer.student_id == str(student_id))
    rows = q.order_by(desc(StudentTransfer.created_at)).all()
    return {"data": [_ser_transfer(r) for r in rows], "meta": _meta(request)}


@router.post("/transfers")
def create_transfer(
    payload: TransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.direction not in TRANSFER_DIRECTIONS:
        return _err("INVALID_DIRECTION",
                    f"must be in {sorted(TRANSFER_DIRECTIONS)}", request)
    actor = _actor(current_user)
    t = StudentTransfer(
        school_id=str(school_id),
        student_id=str(payload.student_id),
        direction=payload.direction,
        counterparty_school_name=payload.counterparty_school_name,
        counterparty_school_contact=payload.counterparty_school_contact,
        reason=payload.reason,
        transcript_attachment_id=(
            str(payload.transcript_attachment_id)
            if payload.transcript_attachment_id else None
        ),
        effective_date=payload.effective_date,
        initiated_by_user_id=str(actor),
    )
    db.add(t)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=f"transfer.{payload.direction}",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "student_transfer", "id": t.id,
                "student_id": str(payload.student_id)},
        details={"direction": payload.direction,
                 "effective_date": payload.effective_date.isoformat()},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_transfer(t), "meta": _meta(request)}
