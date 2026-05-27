"""Phase 16a — Curriculum endpoints (school-local).

  * `POST /curriculum/subjects`        — extends Subject creation with
                                          grade_levels.
  * `POST /curriculum/units`           — add a unit to a subject.
  * `POST /curriculum/topics`          — add a topic to a unit.
  * `GET  /curriculum/tree?subject_id` — full hierarchy for a subject.
  * `POST /curriculum/adopt-subject`   — clone a NationalSubject + its
                                          units + topics into this school
                                          (idempotent).

Audit (ADR 018):
  * `curriculum.unit.created`    — target=`{school_id, subject_id, unit_id}`.
                                    Details=`{has_national_ref}`. No name.
  * `curriculum.topic.created`   — target=`{school_id, subject_id, topic_id}`.
                                    Details=`{has_parent, has_national_ref}`. No name.
  * `curriculum.subject.adopted` — target=`{school_id, subject_id,
                                    national_subject_id}`.
                                    Details=`{units_cloned, topics_cloned}`.
                                    Counts only. No names.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.school import Subject
from app.models.curriculum import Unit, Topic
from app.models.national_curriculum import (
    NationalSubject, NationalUnit, NationalTopic,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Curriculum"])


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request, status=400):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request, status=200):
    return JSONResponse(status_code=status,
                        content={"data": data, "meta": _meta(request)})


def _actor(current_user) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


def _audit(db: Session, request: Request, *,
           event_type: str, school_id: uuid.UUID, actor: uuid.UUID,
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


# ─── Helpers ──────────────────────────────────────────────────────


def _ser_subject(s: Subject) -> dict:
    grade_levels: List[str] = []
    if s.grade_levels:
        try:
            grade_levels = json.loads(s.grade_levels)
        except Exception:
            grade_levels = []
    return {
        "id": str(s.id),
        "school_id": str(s.school_id),
        "name": s.name,
        "code": s.code,
        "is_active": bool(s.is_active),
        "grade_levels": grade_levels,
        "national_subject_id": s.national_subject_id,
    }


def _ser_unit(u: Unit) -> dict:
    return {
        "id": str(u.id),
        "school_id": str(u.school_id),
        "subject_id": str(u.subject_id),
        "name": u.name,
        "code": u.code,
        "sequence_order": int(u.sequence_order or 0),
        "grade_level": u.grade_level,
        "national_unit_id": u.national_unit_id,
        "description": u.description,
    }


def _ser_topic(t: Topic) -> dict:
    return {
        "id": str(t.id),
        "school_id": str(t.school_id),
        "subject_id": str(t.subject_id),
        "unit_id": str(t.unit_id),
        "parent_topic_id": str(t.parent_topic_id) if t.parent_topic_id else None,
        "name": t.name,
        "code": t.code,
        "sequence_order": int(t.sequence_order or 0),
        "learning_outcomes": t.learning_outcomes,
        "national_topic_id": t.national_topic_id,
    }


# ─── Schemas ──────────────────────────────────────────────────────


class SubjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=50)
    grade_levels: List[str] = Field(default_factory=list)


class UnitCreate(BaseModel):
    subject_id: uuid.UUID
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=64)
    sequence_order: int = Field(default=0, ge=0)
    grade_level: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = None


class TopicCreate(BaseModel):
    unit_id: uuid.UUID
    name: str = Field(..., max_length=255)
    code: str = Field(..., max_length=64)
    sequence_order: int = Field(default=0, ge=0)
    parent_topic_id: Optional[uuid.UUID] = None
    learning_outcomes: Optional[str] = None


class AdoptSubjectBody(BaseModel):
    national_subject_id: uuid.UUID
    grade_levels: Optional[List[str]] = None
    # Optional override for the local subject code/name (defaults to
    # the national row's code/name).
    code: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, max_length=255)


# ─── Endpoints ────────────────────────────────────────────────────


@router.post("/curriculum/subjects")
def create_subject(
    body: SubjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Create a school-local subject with optional grade_levels.

    Duplicates `(school_id, code)` are rejected with `SUBJECT_CODE_TAKEN`.
    """
    dup = (
        db.query(Subject)
        .filter(Subject.school_id == school_id, Subject.code == body.code)
        .first()
    )
    if dup:
        return _err("SUBJECT_CODE_TAKEN",
                    f"A subject with code '{body.code}' already exists.",
                    request, status=409)
    s = Subject(
        id=uuid.uuid4(),
        school_id=school_id,
        name=body.name,
        code=body.code,
        is_active=True,
        grade_levels=json.dumps(body.grade_levels) if body.grade_levels else None,
        national_subject_id=None,
    )
    db.add(s)
    db.commit()
    return _ok(_ser_subject(s), request, status=201)


@router.post("/curriculum/units")
def create_unit(
    body: UnitCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Verify the subject belongs to this school.
    s = (
        db.query(Subject)
        .filter(Subject.id == body.subject_id, Subject.school_id == school_id)
        .first()
    )
    if not s:
        return _err("SUBJECT_NOT_FOUND",
                    "Subject not found in this school.",
                    request, status=404)
    dup = (
        db.query(Unit)
        .filter(
            Unit.school_id == school_id,
            Unit.subject_id == body.subject_id,
            Unit.code == body.code,
        )
        .first()
    )
    if dup:
        return _err("UNIT_CODE_TAKEN",
                    "A unit with that code already exists in this subject.",
                    request, status=409)
    u = Unit(
        id=uuid.uuid4(),
        school_id=school_id,
        subject_id=body.subject_id,
        name=body.name,
        code=body.code,
        sequence_order=body.sequence_order,
        grade_level=body.grade_level,
        description=body.description,
        created_by=_actor(current_user),
    )
    db.add(u)
    db.flush()
    _audit(
        db, request,
        event_type="curriculum.unit.created",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "curriculum_unit", "id": str(u.id),
                "school_id": str(school_id),
                "subject_id": str(body.subject_id)},
        details={"has_national_ref": False},
    )
    db.commit()
    return _ok(_ser_unit(u), request, status=201)


@router.post("/curriculum/topics")
def create_topic(
    body: TopicCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    u = (
        db.query(Unit)
        .filter(Unit.id == body.unit_id, Unit.school_id == school_id)
        .first()
    )
    if not u:
        return _err("UNIT_NOT_FOUND",
                    "Unit not found in this school.",
                    request, status=404)
    if body.parent_topic_id:
        parent = (
            db.query(Topic)
            .filter(
                Topic.id == body.parent_topic_id,
                Topic.school_id == school_id,
                Topic.unit_id == body.unit_id,
            )
            .first()
        )
        if not parent:
            return _err("PARENT_TOPIC_NOT_FOUND",
                        "Parent topic must be in the same unit + school.",
                        request, status=400)
    dup = (
        db.query(Topic)
        .filter(
            Topic.school_id == school_id,
            Topic.unit_id == body.unit_id,
            Topic.code == body.code,
        )
        .first()
    )
    if dup:
        return _err("TOPIC_CODE_TAKEN",
                    "A topic with that code already exists in this unit.",
                    request, status=409)
    t = Topic(
        id=uuid.uuid4(),
        school_id=school_id,
        subject_id=u.subject_id,
        unit_id=body.unit_id,
        parent_topic_id=body.parent_topic_id,
        name=body.name,
        code=body.code,
        sequence_order=body.sequence_order,
        learning_outcomes=body.learning_outcomes,
        created_by=_actor(current_user),
    )
    db.add(t)
    db.flush()
    _audit(
        db, request,
        event_type="curriculum.topic.created",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "curriculum_topic", "id": str(t.id),
                "school_id": str(school_id),
                "subject_id": str(u.subject_id),
                "unit_id": str(body.unit_id)},
        details={"has_parent": bool(body.parent_topic_id),
                 "has_national_ref": False},
    )
    db.commit()
    return _ok(_ser_topic(t), request, status=201)


@router.get("/curriculum/tree")
def curriculum_tree(
    request: Request,
    subject_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Full Subject → Units → Topics → Subtopics tree for one subject."""
    s = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.school_id == school_id)
        .first()
    )
    if not s:
        return _err("SUBJECT_NOT_FOUND",
                    "Subject not found in this school.",
                    request, status=404)
    units = (
        db.query(Unit)
        .filter(Unit.school_id == school_id, Unit.subject_id == subject_id,
                Unit.archived_at.is_(None))
        .order_by(Unit.sequence_order.asc(), Unit.code.asc())
        .all()
    )
    topics_by_unit: dict[str, list] = {}
    for t in (
        db.query(Topic)
        .filter(Topic.school_id == school_id, Topic.subject_id == subject_id,
                Topic.archived_at.is_(None))
        .order_by(Topic.sequence_order.asc(), Topic.code.asc())
        .all()
    ):
        topics_by_unit.setdefault(str(t.unit_id), []).append(_ser_topic(t))
    out_units = []
    for u in units:
        topics = topics_by_unit.get(str(u.id), [])
        # Build a parent → children index for one-deep sub-topics.
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
    return _ok({
        "subject": _ser_subject(s),
        "units": out_units,
    }, request)


@router.post("/curriculum/adopt-subject")
def adopt_subject(
    body: AdoptSubjectBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Clone a published NationalSubject + its units + topics into the
    caller's school. Idempotent on `(school_id, national_subject_id)`."""
    nat = (
        db.query(NationalSubject)
        .filter(NationalSubject.id == body.national_subject_id)
        .first()
    )
    if not nat:
        return _err("NATIONAL_SUBJECT_NOT_FOUND",
                    "National subject not found.",
                    request, status=404)
    if not nat.ministry_published_at:
        return _err("NATIONAL_SUBJECT_NOT_PUBLISHED",
                    "This national subject is not yet published.",
                    request, status=400)

    # Idempotency: existing local subject with this national_subject_id
    # short-circuits to a no-op + returns the existing rows.
    existing = (
        db.query(Subject)
        .filter(
            Subject.school_id == school_id,
            Subject.national_subject_id == str(nat.id),
        )
        .first()
    )
    if existing:
        return _ok({
            "subject": _ser_subject(existing),
            "units_cloned": 0,
            "topics_cloned": 0,
            "idempotent": True,
        }, request)

    # Create the local subject. Use override code/name if supplied;
    # otherwise default to the national row's.
    local_code = body.code or nat.code
    local_name = body.name or nat.name
    code_dup = (
        db.query(Subject)
        .filter(Subject.school_id == school_id, Subject.code == local_code)
        .first()
    )
    if code_dup:
        return _err(
            "SUBJECT_CODE_TAKEN",
            f"Local subject code '{local_code}' is in use. Supply a "
            f"`code` override.",
            request, status=409,
        )
    s = Subject(
        id=uuid.uuid4(),
        school_id=school_id,
        name=local_name,
        code=local_code,
        is_active=True,
        grade_levels=json.dumps(body.grade_levels) if body.grade_levels else None,
        national_subject_id=str(nat.id),
    )
    db.add(s)
    db.flush()

    # Clone units.
    nat_units = (
        db.query(NationalUnit)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalUnit.sequence_order.asc())
        .all()
    )
    units_by_national: dict[str, Unit] = {}
    for nu in nat_units:
        u = Unit(
            id=uuid.uuid4(),
            school_id=school_id,
            subject_id=s.id,
            name=nu.name,
            code=nu.code,
            sequence_order=int(nu.sequence_order or 0),
            grade_level=nu.grade_level,
            description=nu.description,
            national_unit_id=str(nu.id),
            created_by=_actor(current_user),
        )
        db.add(u)
        db.flush()
        units_by_national[str(nu.id)] = u

    # Clone topics.
    topics_by_national: dict[str, Topic] = {}
    nat_topic_rows = (
        db.query(NationalTopic, NationalUnit.id.label("nu_id"))
        .join(NationalUnit, NationalUnit.id == NationalTopic.national_unit_id)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalTopic.sequence_order.asc())
        .all()
    )
    # First pass: create rows without parent_topic_id (we don't yet
    # know the local parent's id). Second pass wires parents up.
    for row in nat_topic_rows:
        nt = row[0]
        local_unit = units_by_national.get(str(nt.national_unit_id))
        if not local_unit:
            continue
        t = Topic(
            id=uuid.uuid4(),
            school_id=school_id,
            subject_id=s.id,
            unit_id=local_unit.id,
            parent_topic_id=None,
            name=nt.name,
            code=nt.code,
            sequence_order=int(nt.sequence_order or 0),
            learning_outcomes=nt.learning_outcomes,
            national_topic_id=str(nt.id),
            created_by=_actor(current_user),
        )
        db.add(t)
        db.flush()
        topics_by_national[str(nt.id)] = t

    # Second pass — set parent_topic_id where the national row had one.
    for row in nat_topic_rows:
        nt = row[0]
        if not nt.parent_topic_id:
            continue
        local_topic = topics_by_national.get(str(nt.id))
        local_parent = topics_by_national.get(str(nt.parent_topic_id))
        if local_topic and local_parent:
            local_topic.parent_topic_id = local_parent.id

    units_cloned = len(units_by_national)
    topics_cloned = len(topics_by_national)
    _audit(
        db, request,
        event_type="curriculum.subject.adopted",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "subject", "id": str(s.id),
                "school_id": str(school_id),
                "national_subject_id": str(nat.id)},
        details={"units_cloned": units_cloned,
                 "topics_cloned": topics_cloned},
    )
    db.commit()
    return _ok({
        "subject": _ser_subject(s),
        "units_cloned": units_cloned,
        "topics_cloned": topics_cloned,
        "idempotent": False,
    }, request, status=201)


@router.get("/curriculum/subjects")
def list_subjects(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """List the caller's school subjects, including grade_levels +
    national_subject_id back-ref. Used by the teacher-web tree view."""
    rows = (
        db.query(Subject)
        .filter(Subject.school_id == school_id, Subject.is_active == True)  # noqa: E712
        .order_by(Subject.name.asc())
        .all()
    )
    return _ok([_ser_subject(s) for s in rows], request)
