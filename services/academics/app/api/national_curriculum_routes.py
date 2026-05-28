"""Phase 16a — Ministry-side National Curriculum endpoints.

Cross-tenant (no school_id). Writes gated by `school:create` permission
(held by Provisioner + EduZimOps). Reads open to anyone with
`ministry:read` OR `school:manage` (so SchoolAdmins can browse the
adoption picker).

Gateway RBAC handles permission checks; here we just trust the
authenticated context.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.national_curriculum import (
    NationalSubject, NationalUnit, NationalTopic,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err, _ok, CROSS_SCHOOL_SENTINEL, make_audit_helper,
)


router = APIRouter(tags=["National Curriculum (Ministry)"])







_audit = make_audit_helper(AuditLog)

def _actor_id(current_user) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(current_user["sub"]))
    except Exception:
        return None



def _ser_subject(s: NationalSubject) -> dict:
    return {
        "id": str(s.id),
        "country": s.country,
        "code": s.code,
        "name": s.name,
        "description": s.description,
        # Phase 17d — version number; bumps each republish.
        "version": int(s.version or 1),
        "ministry_published_at": (
            s.ministry_published_at.isoformat()
            if s.ministry_published_at else None
        ),
    }


def _ser_unit(u: NationalUnit) -> dict:
    return {
        "id": str(u.id),
        "national_subject_id": str(u.national_subject_id),
        "name": u.name,
        "code": u.code,
        "sequence_order": int(u.sequence_order or 0),
        "grade_level": u.grade_level,
        "description": u.description,
    }


def _ser_topic(t: NationalTopic) -> dict:
    return {
        "id": str(t.id),
        "national_unit_id": str(t.national_unit_id),
        "parent_topic_id": str(t.parent_topic_id) if t.parent_topic_id else None,
        "name": t.name,
        "code": t.code,
        "sequence_order": int(t.sequence_order or 0),
        "learning_outcomes": t.learning_outcomes,
    }


# ─── Schemas ──────────────────────────────────────────────────────


class NationalSubjectCreate(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    country: str = Field(default="ZW", max_length=5)
    description: Optional[str] = None


class NationalUnitCreate(BaseModel):
    national_subject_id: uuid.UUID
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=64)
    sequence_order: int = Field(default=0, ge=0)
    grade_level: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = None


class NationalTopicCreate(BaseModel):
    national_unit_id: uuid.UUID
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=64)
    sequence_order: int = Field(default=0, ge=0)
    parent_topic_id: Optional[uuid.UUID] = None
    learning_outcomes: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────


@router.get("/ministry/national-curriculum/subjects")
def list_national_subjects(
    request: Request,
    published_only: bool = Query(True),
    country: str = Query("ZW"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    q = db.query(NationalSubject).filter(NationalSubject.country == country)
    if published_only:
        q = q.filter(NationalSubject.ministry_published_at.isnot(None))
    rows = q.order_by(NationalSubject.name.asc()).all()
    return _ok([_ser_subject(s) for s in rows], request)


@router.get("/ministry/national-curriculum/subjects/{subject_id}/tree")
def national_subject_tree(
    subject_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    s = db.query(NationalSubject).filter(NationalSubject.id == subject_id).first()
    if not s:
        return _err("NOT_FOUND", "National subject not found.", request, status=404)
    units = (
        db.query(NationalUnit)
        .filter(NationalUnit.national_subject_id == subject_id)
        .order_by(NationalUnit.sequence_order.asc())
        .all()
    )
    topics_by_unit: dict[str, list] = {}
    for t in (
        db.query(NationalTopic)
        .join(NationalUnit, NationalUnit.id == NationalTopic.national_unit_id)
        .filter(NationalUnit.national_subject_id == subject_id)
        .order_by(NationalTopic.sequence_order.asc())
        .all()
    ):
        topics_by_unit.setdefault(str(t.national_unit_id), []).append(_ser_topic(t))
    out_units = []
    for u in units:
        topics = topics_by_unit.get(str(u.id), [])
        by_parent: dict = {}
        roots = []
        for t in topics:
            if t["parent_topic_id"]:
                by_parent.setdefault(t["parent_topic_id"], []).append(t)
            else:
                roots.append(t)
        for r in roots:
            r["subtopics"] = by_parent.get(r["id"], [])
        u_ser = _ser_unit(u)
        u_ser["topics"] = roots
        out_units.append(u_ser)
    return _ok({"subject": _ser_subject(s), "units": out_units}, request)


@router.post("/ministry/national-curriculum/subjects")
def create_national_subject(
    body: NationalSubjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    dup = (
        db.query(NationalSubject)
        .filter(
            NationalSubject.country == body.country,
            NationalSubject.code == body.code,
        )
        .first()
    )
    if dup:
        return _err("NATIONAL_SUBJECT_CODE_TAKEN",
                    "A national subject with that code already exists.",
                    request, status=409)
    s = NationalSubject(
        id=uuid.uuid4(),
        country=body.country,
        code=body.code,
        name=body.name,
        description=body.description,
    )
    db.add(s)
    db.commit()
    _audit(
        db, request,
        event_type="national_curriculum.subject.created",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor_id(current_user),
        target={"resource": "national_subject", "id": str(s.id)},
        details={"country": body.country},
    )
    return _ok(_ser_subject(s), request, status=201)


@router.post("/ministry/national-curriculum/units")
def create_national_unit(
    body: NationalUnitCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    subj = db.query(NationalSubject).filter(NationalSubject.id == body.national_subject_id).first()
    if not subj:
        return _err("NATIONAL_SUBJECT_NOT_FOUND",
                    "Parent national subject not found.",
                    request, status=404)
    dup = (
        db.query(NationalUnit)
        .filter(
            NationalUnit.national_subject_id == body.national_subject_id,
            NationalUnit.code == body.code,
        )
        .first()
    )
    if dup:
        return _err("NATIONAL_UNIT_CODE_TAKEN",
                    "Unit code already exists in this subject.",
                    request, status=409)
    u = NationalUnit(
        id=uuid.uuid4(),
        national_subject_id=body.national_subject_id,
        name=body.name,
        code=body.code,
        sequence_order=body.sequence_order,
        grade_level=body.grade_level,
        description=body.description,
    )
    db.add(u)
    db.commit()
    _audit(
        db, request,
        event_type="national_curriculum.unit.created",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor_id(current_user),
        target={"resource": "national_unit", "id": str(u.id),
                "national_subject_id": str(body.national_subject_id)},
        details={},
    )
    return _ok(_ser_unit(u), request, status=201)


@router.post("/ministry/national-curriculum/topics")
def create_national_topic(
    body: NationalTopicCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    u = db.query(NationalUnit).filter(NationalUnit.id == body.national_unit_id).first()
    if not u:
        return _err("NATIONAL_UNIT_NOT_FOUND",
                    "Parent national unit not found.",
                    request, status=404)
    if body.parent_topic_id:
        parent = (
            db.query(NationalTopic)
            .filter(
                NationalTopic.id == body.parent_topic_id,
                NationalTopic.national_unit_id == body.national_unit_id,
            )
            .first()
        )
        if not parent:
            return _err("PARENT_TOPIC_NOT_FOUND",
                        "Parent topic must be in the same unit.",
                        request, status=400)
    dup = (
        db.query(NationalTopic)
        .filter(
            NationalTopic.national_unit_id == body.national_unit_id,
            NationalTopic.code == body.code,
        )
        .first()
    )
    if dup:
        return _err("NATIONAL_TOPIC_CODE_TAKEN",
                    "Topic code already exists in this unit.",
                    request, status=409)
    t = NationalTopic(
        id=uuid.uuid4(),
        national_unit_id=body.national_unit_id,
        parent_topic_id=body.parent_topic_id,
        name=body.name,
        code=body.code,
        sequence_order=body.sequence_order,
        learning_outcomes=body.learning_outcomes,
    )
    db.add(t)
    db.commit()
    _audit(
        db, request,
        event_type="national_curriculum.topic.created",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor_id(current_user),
        target={"resource": "national_topic", "id": str(t.id),
                "national_unit_id": str(body.national_unit_id)},
        details={"has_parent": bool(body.parent_topic_id)},
    )
    return _ok(_ser_topic(t), request, status=201)


@router.post("/ministry/national-curriculum/subjects/{subject_id}/publish")
def publish_national_subject(
    subject_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    s = db.query(NationalSubject).filter(NationalSubject.id == subject_id).first()
    if not s:
        return _err("NATIONAL_SUBJECT_NOT_FOUND",
                    "National subject not found.",
                    request, status=404)
    if s.ministry_published_at:
        return _err("ALREADY_PUBLISHED",
                    "This subject is already published.",
                    request, status=409)
    s.ministry_published_at = datetime.now(timezone.utc)
    db.commit()
    _audit(
        db, request,
        event_type="national_curriculum.subject.published",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor_id(current_user),
        target={"resource": "national_subject", "id": str(s.id)},
        details={"version": int(s.version or 1)},
    )
    return _ok(_ser_subject(s), request)


@router.post("/ministry/national-curriculum/subjects/{subject_id}/republish")
def republish_national_subject(
    subject_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Phase 17d — bump the subject's `version` + re-stamp the
    publish timestamp. Schools that adopted v=N see `is_stale: true`
    on the next subject listing and can upgrade via
    POST /curriculum/upgrade-subject."""
    s = db.query(NationalSubject).filter(NationalSubject.id == subject_id).first()
    if not s:
        return _err("NATIONAL_SUBJECT_NOT_FOUND",
                    "National subject not found.",
                    request, status=404)
    old_version = int(s.version or 1)
    s.version = old_version + 1
    s.ministry_published_at = datetime.now(timezone.utc)
    db.commit()
    _audit(
        db, request,
        event_type="national_curriculum.subject.republished",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor_id(current_user),
        target={"resource": "national_subject", "id": str(s.id)},
        details={
            "from_version": old_version,
            "to_version": int(s.version),
        },
    )
    return _ok({
        "subject": _ser_subject(s),
        "from_version": old_version,
        "to_version": int(s.version),
    }, request)
