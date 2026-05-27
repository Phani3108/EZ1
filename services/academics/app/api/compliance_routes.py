"""Compliance + health record + rollup endpoints — Phase 13b.

  * Compliance templates + submissions (A-005)
  * Disciplinary rollup (A-006): aggregates BehaviorIncident rows
  * Health records (A-007): PIA-gated CRUD with reads logged
  * Parent complaint rollup (A-010): already exists as Grievance;
    we expose an admin counts endpoint here.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.compliance import (
    ComplianceReportTemplate, ComplianceReportSubmission, HealthRecord,
)
from app.models.student_life import BehaviorIncident
from app.models.parent_life import Grievance
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Compliance"])


COMPLIANCE_STATUSES = {"draft", "submitted", "accepted", "rejected"}
CADENCES = {"quarterly", "termly", "annual", "adhoc"}


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


def _is_nurse_or_admin(current_user: dict) -> bool:
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    return any(r in ("admin", "principal", "nurse") for r in roles)


# ─── A-005 — Templates + submissions ──────────────────────────────


class TemplateCreate(BaseModel):
    code: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    cadence: str = Field(default="annual")
    schema: Optional[dict] = None


def _ser_tpl(t: ComplianceReportTemplate) -> dict:
    try:
        sch = json.loads(t.schema_json) if t.schema_json else None
    except (TypeError, ValueError):
        sch = None
    return {
        "id": t.id, "code": t.code, "title": t.title,
        "cadence": t.cadence, "schema": sch,
        "is_active": bool(t.is_active),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/compliance/templates")
def list_templates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(ComplianceReportTemplate)
        .filter(ComplianceReportTemplate.school_id == str(school_id),
                ComplianceReportTemplate.is_active.is_(True))
        .order_by(ComplianceReportTemplate.code.asc())
        .all()
    )
    return {"data": [_ser_tpl(r) for r in rows], "meta": _meta(request)}


@router.post("/compliance/templates")
def create_template(
    payload: TemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.cadence not in CADENCES:
        return _err("INVALID_CADENCE",
                    f"must be in {sorted(CADENCES)}", request)
    t = ComplianceReportTemplate(
        school_id=str(school_id),
        code=payload.code, title=payload.title,
        cadence=payload.cadence,
        schema_json=json.dumps(payload.schema) if payload.schema else None,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(t)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="compliance_template.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "compliance_report_template", "id": t.id,
                "code": payload.code},
        details={"cadence": payload.cadence},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_tpl(t), "meta": _meta(request)}


class SubmissionCreate(BaseModel):
    template_id: uuid.UUID
    period_label: str = Field(..., max_length=64)
    payload: dict = Field(...)
    attachment_id: Optional[uuid.UUID] = None


class SubmissionDecide(BaseModel):
    status: str = Field(..., pattern="^(submitted|accepted|rejected)$")
    rejection_notes: Optional[str] = Field(default=None, max_length=500)


def _ser_sub(s: ComplianceReportSubmission) -> dict:
    try:
        pl = json.loads(s.payload_json) if s.payload_json else None
    except (TypeError, ValueError):
        pl = None
    return {
        "id": s.id, "template_id": s.template_id,
        "period_label": s.period_label, "status": s.status,
        "payload": pl, "attachment_id": s.attachment_id,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        "accepted_at": s.accepted_at.isoformat() if s.accepted_at else None,
        "rejection_notes": s.rejection_notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/compliance/submissions")
def list_submissions(
    request: Request,
    template_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(ComplianceReportSubmission).filter(
        ComplianceReportSubmission.school_id == str(school_id),
    )
    if template_id:
        q = q.filter(
            ComplianceReportSubmission.template_id == str(template_id),
        )
    if status:
        q = q.filter(ComplianceReportSubmission.status == status)
    rows = q.order_by(desc(ComplianceReportSubmission.created_at)).all()
    return {"data": [_ser_sub(r) for r in rows], "meta": _meta(request)}


@router.post("/compliance/submissions")
def create_submission(
    payload: SubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    s = ComplianceReportSubmission(
        school_id=str(school_id),
        template_id=str(payload.template_id),
        period_label=payload.period_label,
        payload_json=json.dumps(payload.payload),
        attachment_id=str(payload.attachment_id) if payload.attachment_id else None,
        status="draft",
    )
    db.add(s)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="compliance_submission.drafted",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "compliance_report_submission", "id": s.id,
                "template_id": str(payload.template_id),
                "period_label": payload.period_label},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_sub(s), "meta": _meta(request)}


@router.put("/compliance/submissions/{sid}/decide")
def decide_submission(
    sid: uuid.UUID, payload: SubmissionDecide,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    s = (
        db.query(ComplianceReportSubmission)
        .filter(ComplianceReportSubmission.id == str(sid),
                ComplianceReportSubmission.school_id == str(school_id))
        .first()
    )
    if s is None:
        return _err("NOT_FOUND", "Submission not found.", request, 404)
    actor = _actor(current_user)
    s.status = payload.status
    if payload.status == "submitted":
        s.submitted_by_user_id = str(actor)
        s.submitted_at = datetime.now(timezone.utc)
    elif payload.status == "accepted":
        s.accepted_at = datetime.now(timezone.utc)
    elif payload.status == "rejected":
        s.rejection_notes = payload.rejection_notes
    db.flush()
    record_audit_event(
        db, AuditLog,
        event_type=f"compliance_submission.{payload.status}",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "compliance_report_submission", "id": s.id},
        details={"status": payload.status},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_sub(s), "meta": _meta(request)}


# ─── A-006 — Disciplinary rollup ──────────────────────────────────


@router.get("/compliance/discipline-rollup")
def discipline_rollup(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Aggregated incident counts by severity + category for the
    admin compliance dashboard. Reads from BehaviorIncident (Phase 11e)."""
    rows = (
        db.query(
            BehaviorIncident.severity,
            BehaviorIncident.category,
            func.count(BehaviorIncident.id).label("count"),
            func.count(BehaviorIncident.resolved_at).label("resolved"),
        )
        .filter(BehaviorIncident.school_id == str(school_id))
        .group_by(BehaviorIncident.severity, BehaviorIncident.category)
        .all()
    )
    out = [
        {"severity": r.severity, "category": r.category,
         "count": int(r.count), "resolved": int(r.resolved or 0)}
        for r in rows
    ]
    totals = {
        "incidents": sum(r["count"] for r in out),
        "resolved": sum(r["resolved"] for r in out),
        "open": sum(r["count"] - r["resolved"] for r in out),
    }
    return {"data": {"buckets": out, "totals": totals},
            "meta": _meta(request)}


# ─── A-010 — Grievance rollup ─────────────────────────────────────


@router.get("/compliance/grievance-rollup")
def grievance_rollup(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Counts of Grievance rows by status. Backs the admin "complaints
    handling" dashboard."""
    rows = (
        db.query(Grievance.status, func.count(Grievance.id))
        .filter(Grievance.school_id == str(school_id))
        .group_by(Grievance.status)
        .all()
    )
    counts = {status: int(count) for status, count in rows}
    return {
        "data": {
            "open": counts.get("open", 0),
            "in_review": counts.get("in_review", 0),
            "resolved": counts.get("resolved", 0),
            "dismissed": counts.get("dismissed", 0),
        },
        "meta": _meta(request),
    }


# ─── A-007 — Health records ──────────────────────────────────────


class HealthRecordPut(BaseModel):
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medications: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(default=None, max_length=255)
    emergency_contact_relation: Optional[str] = Field(default=None, max_length=64)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=20)
    vaccinations: Optional[dict] = None
    blood_group: Optional[str] = Field(default=None, max_length=8)
    notes: Optional[str] = None


def _ser_hr(h: HealthRecord) -> dict:
    try:
        vac = json.loads(h.vaccinations_json) if h.vaccinations_json else None
    except (TypeError, ValueError):
        vac = None
    return {
        "id": h.id, "student_id": h.student_id,
        "allergies": h.allergies,
        "chronic_conditions": h.chronic_conditions,
        "medications": h.medications,
        "emergency_contact_name": h.emergency_contact_name,
        "emergency_contact_relation": h.emergency_contact_relation,
        "emergency_contact_phone": h.emergency_contact_phone,
        "vaccinations": vac,
        "blood_group": h.blood_group,
        "notes": h.notes,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


@router.get("/health-records/{student_id}")
def get_health_record(
    student_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """RBAC: gateway gates on `school:manage`. The endpoint logs the
    READ event because health-data reads are themselves audit-worthy
    per ADR 007."""
    if not _is_nurse_or_admin(current_user):
        return _err("FORBIDDEN",
                    "Health records are restricted to admin or nurse roles.",
                    request, 403)
    h = (
        db.query(HealthRecord)
        .filter(HealthRecord.student_id == str(student_id),
                HealthRecord.school_id == str(school_id))
        .first()
    )
    if h is None:
        return _err("NOT_FOUND",
                    "No health record yet for this student.", request, 404)
    record_audit_event(
        db, AuditLog, event_type="health_record.read",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "health_record", "id": h.id,
                "student_id": str(student_id)},
        # Audit captures the FACT of access — never the body. ADR 007.
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_hr(h), "meta": _meta(request)}


@router.put("/health-records/{student_id}")
def upsert_health_record(
    student_id: uuid.UUID,
    payload: HealthRecordPut,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if not _is_nurse_or_admin(current_user):
        return _err("FORBIDDEN",
                    "Health records are restricted to admin or nurse roles.",
                    request, 403)
    h = (
        db.query(HealthRecord)
        .filter(HealthRecord.student_id == str(student_id),
                HealthRecord.school_id == str(school_id))
        .first()
    )
    actor = _actor(current_user)
    changed = []
    if h is None:
        h = HealthRecord(
            school_id=str(school_id),
            student_id=str(student_id),
            allergies=payload.allergies,
            chronic_conditions=payload.chronic_conditions,
            medications=payload.medications,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_relation=payload.emergency_contact_relation,
            emergency_contact_phone=payload.emergency_contact_phone,
            vaccinations_json=(
                json.dumps(payload.vaccinations) if payload.vaccinations else None
            ),
            blood_group=payload.blood_group,
            notes=payload.notes,
            updated_by_user_id=str(actor),
        )
        db.add(h)
        evt = "health_record.created"
    else:
        for field in (
            "allergies", "chronic_conditions", "medications",
            "emergency_contact_name", "emergency_contact_relation",
            "emergency_contact_phone", "blood_group", "notes",
        ):
            val = getattr(payload, field)
            if val is not None and getattr(h, field) != val:
                setattr(h, field, val)
                changed.append(field)
        if payload.vaccinations is not None:
            new_json = json.dumps(payload.vaccinations)
            if h.vaccinations_json != new_json:
                h.vaccinations_json = new_json
                changed.append("vaccinations")
        h.updated_by_user_id = str(actor)
        evt = "health_record.updated"
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=evt,
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "health_record", "id": h.id,
                "student_id": str(student_id)},
        # Field NAMES only — ADR 007.
        details={"changed_fields": changed} if changed else {},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_hr(h), "meta": _meta(request)}
