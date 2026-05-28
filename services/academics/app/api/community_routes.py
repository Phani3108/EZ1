"""Community endpoints — Phase 13d (policy docs, sponsors, alumni)."""
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
from app.models.community import PolicyDocument, Sponsor, Sponsorship, Alumnus
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err,
)


router = APIRouter(tags=["Community"])


POLICY_CATEGORIES = {
    "uniform", "discipline", "academic", "fees",
    "child_protection", "data_privacy", "other",
}
SPONSOR_TYPES = {"corporate", "individual", "ngo", "government", "other"}
SPONSORSHIP_PURPOSES = {
    "bursary", "infrastructure", "equipment", "sports", "program", "other",
}
SPONSORSHIP_STATUSES = {"pending", "active", "completed", "terminated"}



def _actor(current_user: dict) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))



# ─── A-017 — Policy documents ─────────────────────────────────────


class PolicyCreate(BaseModel):
    code: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    summary: Optional[str] = None
    category: str = Field(default="other")
    attachment_id: Optional[uuid.UUID] = None
    version: int = Field(default=1, ge=1)
    effective_from: date
    visible_to_parents: bool = True


def _ser_policy(p: PolicyDocument) -> dict:
    return {
        "id": p.id, "code": p.code, "title": p.title,
        "summary": p.summary, "category": p.category,
        "attachment_id": p.attachment_id,
        "version": p.version,
        "effective_from": p.effective_from.isoformat() if p.effective_from else None,
        "superseded_at": p.superseded_at.isoformat() if p.superseded_at else None,
        "visible_to_parents": bool(p.visible_to_parents),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/policies")
def list_policies(
    request: Request,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(PolicyDocument).filter(
        PolicyDocument.school_id == str(school_id),
    )
    if category:
        q = q.filter(PolicyDocument.category == category)
    # Non-admin sees only visible policies + current versions only.
    roles = [r.lower() for r in (current_user.get("roles") or [])
             if isinstance(r, str)]
    if not any(r in ("admin", "principal") for r in roles):
        q = q.filter(
            PolicyDocument.visible_to_parents.is_(True),
            PolicyDocument.superseded_at.is_(None),
        )
    rows = q.order_by(PolicyDocument.code.asc(),
                      desc(PolicyDocument.version)).all()
    return {"data": [_ser_policy(r) for r in rows], "meta": _meta(request)}


@router.post("/policies")
def create_policy(
    payload: PolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.category not in POLICY_CATEGORIES:
        return _err("INVALID_CATEGORY",
                    f"must be in {sorted(POLICY_CATEGORIES)}", request)
    # Issuing a new version supersedes the previous one for the same code.
    if payload.version > 1:
        prev = (
            db.query(PolicyDocument)
            .filter(PolicyDocument.school_id == str(school_id),
                    PolicyDocument.code == payload.code,
                    PolicyDocument.superseded_at.is_(None))
            .first()
        )
        if prev:
            prev.superseded_at = datetime.now(timezone.utc)
    p = PolicyDocument(
        school_id=str(school_id),
        code=payload.code, title=payload.title,
        summary=payload.summary, category=payload.category,
        attachment_id=str(payload.attachment_id) if payload.attachment_id else None,
        version=payload.version,
        effective_from=payload.effective_from,
        visible_to_parents=payload.visible_to_parents,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(p)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="policy.published",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "policy_document", "id": p.id,
                "code": payload.code},
        details={"category": payload.category, "version": payload.version},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_policy(p), "meta": _meta(request)}


# ─── A-019 — Sponsors ─────────────────────────────────────────────


class SponsorCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sponsor_type: str = Field(default="other")
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = None


def _ser_sponsor(s: Sponsor) -> dict:
    return {
        "id": s.id, "name": s.name, "sponsor_type": s.sponsor_type,
        "contact_name": s.contact_name, "contact_email": s.contact_email,
        "contact_phone": s.contact_phone, "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/sponsors")
def list_sponsors(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(Sponsor)
        .filter(Sponsor.school_id == str(school_id))
        .order_by(Sponsor.name.asc())
        .all()
    )
    return {"data": [_ser_sponsor(r) for r in rows], "meta": _meta(request)}


@router.post("/sponsors")
def create_sponsor(
    payload: SponsorCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.sponsor_type not in SPONSOR_TYPES:
        return _err("INVALID_SPONSOR_TYPE",
                    f"must be in {sorted(SPONSOR_TYPES)}", request)
    s = Sponsor(
        school_id=str(school_id),
        name=payload.name, sponsor_type=payload.sponsor_type,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        notes=payload.notes,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(s)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="sponsor.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "sponsor", "id": s.id},
        details={"sponsor_type": payload.sponsor_type},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_sponsor(s), "meta": _meta(request)}


class SponsorshipCreate(BaseModel):
    sponsor_id: uuid.UUID
    purpose: str = Field(default="other")
    committed_cents: int = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    notes: Optional[str] = None


class SponsorshipUpdate(BaseModel):
    received_cents: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None


def _ser_sponsorship(s: Sponsorship) -> dict:
    return {
        "id": s.id, "sponsor_id": s.sponsor_id, "purpose": s.purpose,
        "committed_cents": s.committed_cents,
        "received_cents": s.received_cents,
        "currency": s.currency, "status": s.status,
        "starts_on": s.starts_on.isoformat() if s.starts_on else None,
        "ends_on": s.ends_on.isoformat() if s.ends_on else None,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/sponsorships")
def list_sponsorships(
    request: Request,
    sponsor_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Sponsorship).filter(Sponsorship.school_id == str(school_id))
    if sponsor_id:
        q = q.filter(Sponsorship.sponsor_id == str(sponsor_id))
    if status:
        q = q.filter(Sponsorship.status == status)
    rows = q.order_by(desc(Sponsorship.created_at)).all()
    return {"data": [_ser_sponsorship(r) for r in rows], "meta": _meta(request)}


@router.post("/sponsorships")
def create_sponsorship(
    payload: SponsorshipCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.purpose not in SPONSORSHIP_PURPOSES:
        return _err("INVALID_PURPOSE",
                    f"must be in {sorted(SPONSORSHIP_PURPOSES)}", request)
    sp = Sponsorship(
        school_id=str(school_id),
        sponsor_id=str(payload.sponsor_id),
        purpose=payload.purpose,
        committed_cents=payload.committed_cents,
        currency=payload.currency,
        starts_on=payload.starts_on, ends_on=payload.ends_on,
        notes=payload.notes,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(sp)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="sponsorship.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "sponsorship", "id": sp.id,
                "sponsor_id": str(payload.sponsor_id)},
        details={"purpose": payload.purpose,
                 "committed_cents": payload.committed_cents,
                 "currency": payload.currency},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_sponsorship(sp), "meta": _meta(request)}


@router.put("/sponsorships/{sid}")
def update_sponsorship(
    sid: uuid.UUID, payload: SponsorshipUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    sp = (
        db.query(Sponsorship)
        .filter(Sponsorship.id == str(sid),
                Sponsorship.school_id == str(school_id))
        .first()
    )
    if sp is None:
        return _err("NOT_FOUND", "Sponsorship not found.", request, 404)
    changed = []
    if payload.received_cents is not None:
        sp.received_cents = payload.received_cents
        changed.append("received_cents")
    if payload.status is not None:
        if payload.status not in SPONSORSHIP_STATUSES:
            return _err("INVALID_STATUS",
                        f"must be in {sorted(SPONSORSHIP_STATUSES)}",
                        request)
        sp.status = payload.status
        changed.append("status")
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="sponsorship.updated",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "sponsorship", "id": sp.id},
        details={"changed_fields": changed},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_sponsorship(sp), "meta": _meta(request)}


# ─── A-020 — Alumni ───────────────────────────────────────────────


class AlumnusCreate(BaseModel):
    student_id: uuid.UUID
    full_name: str = Field(..., max_length=255)
    graduation_year: int = Field(..., ge=1900, le=2099)
    final_class_label: Optional[str] = Field(default=None, max_length=80)
    current_email: Optional[str] = Field(default=None, max_length=255)
    current_phone: Optional[str] = Field(default=None, max_length=20)


class AlumnusUpdate(BaseModel):
    current_email: Optional[str] = Field(default=None, max_length=255)
    current_phone: Optional[str] = Field(default=None, max_length=20)
    current_occupation: Optional[str] = Field(default=None, max_length=255)
    current_university: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


def _ser_alumnus(a: Alumnus) -> dict:
    return {
        "id": a.id, "student_id": a.student_id,
        "full_name": a.full_name,
        "graduation_year": a.graduation_year,
        "final_class_label": a.final_class_label,
        "current_email": a.current_email,
        "current_phone": a.current_phone,
        "current_occupation": a.current_occupation,
        "current_university": a.current_university,
        "last_contacted_at": (
            a.last_contacted_at.isoformat() if a.last_contacted_at else None
        ),
        "notes": a.notes,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.get("/alumni")
def list_alumni(
    request: Request,
    graduation_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Alumnus).filter(Alumnus.school_id == str(school_id))
    if graduation_year:
        q = q.filter(Alumnus.graduation_year == graduation_year)
    rows = q.order_by(desc(Alumnus.graduation_year),
                      Alumnus.full_name.asc()).limit(500).all()
    return {"data": [_ser_alumnus(r) for r in rows], "meta": _meta(request)}


@router.post("/alumni")
def create_alumnus(
    payload: AlumnusCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = Alumnus(
        school_id=str(school_id),
        student_id=str(payload.student_id),
        full_name=payload.full_name,
        graduation_year=payload.graduation_year,
        final_class_label=payload.final_class_label,
        current_email=payload.current_email,
        current_phone=payload.current_phone,
    )
    db.add(a)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="alumnus.recorded",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "alumnus", "id": a.id,
                "student_id": str(payload.student_id)},
        # Name + contact are PII — log year only.
        details={"graduation_year": payload.graduation_year},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_alumnus(a), "meta": _meta(request)}


@router.put("/alumni/{aid}")
def update_alumnus(
    aid: uuid.UUID, payload: AlumnusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = (
        db.query(Alumnus)
        .filter(Alumnus.id == str(aid),
                Alumnus.school_id == str(school_id))
        .first()
    )
    if a is None:
        return _err("NOT_FOUND", "Alumnus not found.", request, 404)
    changed = []
    for field in (
        "current_email", "current_phone",
        "current_occupation", "current_university", "notes",
    ):
        val = getattr(payload, field)
        if val is not None and getattr(a, field) != val:
            setattr(a, field, val)
            changed.append(field)
    if changed:
        a.last_contacted_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="alumnus.updated",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "alumnus", "id": a.id},
        # Field NAMES only.
        details={"changed_fields": changed},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_alumnus(a), "meta": _meta(request)}
