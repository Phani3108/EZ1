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
# Phase 20a — shared route helpers.
from eduzim_shared.routes import _meta, _err, _ok, make_audit_helper


router = APIRouter(tags=["Curriculum"])

_audit = make_audit_helper(AuditLog)


def _actor(current_user) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


# ─── Helpers ──────────────────────────────────────────────────────


def _ser_subject(s: Subject, *, national_version: Optional[int] = None) -> dict:
    grade_levels: List[str] = []
    if s.grade_levels:
        try:
            grade_levels = json.loads(s.grade_levels)
        except Exception:
            grade_levels = []
    out = {
        "id": str(s.id),
        "school_id": str(s.school_id),
        "name": s.name,
        "code": s.code,
        "is_active": bool(s.is_active),
        "grade_levels": grade_levels,
        "national_subject_id": s.national_subject_id,
        # Phase 17d — adoption + version metadata. `is_stale` is true
        # iff the school adopted this subject but the Ministry has
        # since published a newer version.
        "adopted_national_version": (
            int(s.adopted_national_version)
            if s.adopted_national_version is not None else None
        ),
        "national_current_version": national_version,
        "is_stale": (
            s.national_subject_id is not None
            and national_version is not None
            and s.adopted_national_version is not None
            and national_version > s.adopted_national_version
        ),
    }
    return out


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
        # Phase 17d — track which national-curriculum version we
        # cloned. Surfaces as `is_stale` on subject listing once the
        # Ministry publishes a newer version.
        adopted_national_version=int(nat.version or 1),
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
    national_subject_id back-ref + `is_stale` indicator when the
    Ministry has published a newer version of a national subject
    this school adopted (Phase 17d)."""
    rows = (
        db.query(Subject)
        .filter(Subject.school_id == school_id, Subject.is_active == True)  # noqa: E712
        .order_by(Subject.name.asc())
        .all()
    )
    # Batch-load national versions for adopted subjects.
    # Subject.national_subject_id is String(36); NationalSubject.id is
    # a UUID column — the cross-type IN join is unreliable on SQLite,
    # so iterate-and-match in Python.
    nat_ids_str = [r.national_subject_id for r in rows if r.national_subject_id]
    nat_version_by_id: dict[str, int] = {}
    if nat_ids_str:
        try:
            nat_rows = db.query(NationalSubject).all()
            nat_version_by_id = {
                str(n.id): int(n.version or 1)
                for n in nat_rows
                if str(n.id) in set(nat_ids_str)
            }
        except Exception:
            nat_version_by_id = {}
    return _ok([
        _ser_subject(
            s,
            national_version=nat_version_by_id.get(s.national_subject_id),
        )
        for s in rows
    ], request)


class UpgradeSubjectBody(BaseModel):
    """Phase 17d — re-clone units/topics from a newer NationalSubject
    version while preserving school-local additions.

    Semantics:
      - For every NationalUnit/NationalTopic on the current version,
        upsert the corresponding school-local Unit/Topic by
        `national_*_id`. Updates name + sequence + learning_outcomes
        + grade_level if they changed.
      - For new National rows (added in the new version), create new
        local rows.
      - For local Unit/Topic rows where `national_*_id IS NULL`
        (custom additions), preserve them untouched.
      - For local rows whose national counterpart was removed in v2,
        we KEEP the local row (don't auto-delete content the school
        may rely on). The HoD can manually archive these.
    """
    school_subject_id: uuid.UUID


def _resolve_upgrade_targets(
    db: Session, school_id: uuid.UUID, school_subject_id: uuid.UUID
):
    """Phase 18a — shared resolver used by both preview + commit.

    Returns `(Subject, NationalSubject, from_version, to_version)` on
    success or `(None, code, message, status)` on error so the caller
    can early-return.
    """
    s = (
        db.query(Subject)
        .filter(Subject.id == school_subject_id,
                Subject.school_id == school_id)
        .first()
    )
    if not s:
        return None, "SUBJECT_NOT_FOUND", "Subject not found.", 404
    if not s.national_subject_id:
        return None, "SUBJECT_NOT_ADOPTED", (
            "Only nationally-adopted subjects can be upgraded."
        ), 400
    try:
        nat_lookup_id = uuid.UUID(s.national_subject_id)
        nat = (
            db.query(NationalSubject)
            .filter(NationalSubject.id == nat_lookup_id)
            .first()
        )
    except (ValueError, TypeError):
        nat = None
    if not nat:
        return None, "NATIONAL_SUBJECT_NOT_FOUND", (
            "Source national subject no longer exists."
        ), 404
    if not nat.ministry_published_at:
        return None, "NATIONAL_SUBJECT_NOT_PUBLISHED", (
            "The source national subject is unpublished."
        ), 400
    from_version = int(s.adopted_national_version or 0)
    to_version = int(nat.version or 1)
    return (s, nat, from_version, to_version)


@router.get("/curriculum/upgrade-subject/preview")
def preview_upgrade_subject(
    request: Request,
    school_subject_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Phase 18a — read-only "what will change?" view of a curriculum
    upgrade. Returns the same shape as `upgrade-subject` plus per-row
    diff lists so the HoD can review before committing.

    The endpoint NEVER mutates. Safe to call repeatedly; the audit row
    is logged with counts only — no syllabus content reaches details.
    """
    resolved = _resolve_upgrade_targets(db, school_id, school_subject_id)
    if resolved[0] is None:
        _, code, msg, status = resolved
        return _err(code, msg, request, status=status)
    s, nat, from_version, to_version = resolved

    if from_version >= to_version:
        _audit(
            db, request,
            event_type="curriculum.subject.upgrade_previewed",
            school_id=school_id,
            actor=_actor(current_user),
            target={"resource": "subject", "id": str(s.id),
                    "school_id": str(school_id),
                    "national_subject_id": str(nat.id)},
            details={
                "from_version": from_version,
                "to_version": to_version,
                "no_op": True,
            },
        )
        db.commit()
        return _ok({
            "subject_id": str(s.id),
            "from_version": from_version,
            "to_version": to_version,
            "no_op": True,
            "units_to_add": [],
            "units_to_update": [],
            "topics_to_add": [],
            "topics_to_update": [],
            "local_custom_units_preserved_count": 0,
            "local_custom_topics_preserved_count": 0,
            "local_nationally_orphaned_units_count": 0,
            "local_nationally_orphaned_topics_count": 0,
        }, request)

    # Build local maps for upsert lookups.
    local_units = (
        db.query(Unit)
        .filter(Unit.school_id == school_id, Unit.subject_id == s.id)
        .all()
    )
    local_unit_by_natid: dict[str, Unit] = {
        u.national_unit_id: u for u in local_units if u.national_unit_id
    }
    local_custom_units = [u for u in local_units if not u.national_unit_id]

    local_topics = (
        db.query(Topic)
        .filter(Topic.school_id == school_id, Topic.subject_id == s.id)
        .all()
    )
    local_topic_by_natid: dict[str, Topic] = {
        t.national_topic_id: t for t in local_topics if t.national_topic_id
    }
    local_custom_topics = [t for t in local_topics if not t.national_topic_id]

    nat_units = (
        db.query(NationalUnit)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalUnit.sequence_order.asc())
        .all()
    )

    units_to_add: list[dict] = []
    units_to_update: list[dict] = []
    seen_local_unit_ids: set = set()

    for nu in nat_units:
        existing = local_unit_by_natid.get(str(nu.id))
        if existing:
            seen_local_unit_ids.add(existing.id)
            changes: list[str] = []
            if existing.name != nu.name:
                changes.append("name")
            if existing.sequence_order != int(nu.sequence_order or 0):
                changes.append("sequence_order")
            if existing.grade_level != nu.grade_level:
                changes.append("grade_level")
            if existing.description != nu.description:
                changes.append("description")
            if changes:
                units_to_update.append({
                    "local_unit_id": str(existing.id),
                    "national_unit_id": str(nu.id),
                    "code": nu.code,
                    "changed_fields": changes,
                })
        else:
            units_to_add.append({
                "national_unit_id": str(nu.id),
                "code": nu.code,
                "name": nu.name,
                "grade_level": nu.grade_level,
                "sequence_order": int(nu.sequence_order or 0),
            })

    # Local national-linked units whose national counterpart no longer
    # exists (preserved by the upgrade, but worth flagging to HoD).
    nat_unit_ids = {str(nu.id) for nu in nat_units}
    local_orphaned_units = [
        u for u in local_units
        if u.national_unit_id and u.national_unit_id not in nat_unit_ids
    ]

    nat_topic_rows = (
        db.query(NationalTopic)
        .join(NationalUnit, NationalUnit.id == NationalTopic.national_unit_id)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalTopic.sequence_order.asc())
        .all()
    )

    topics_to_add: list[dict] = []
    topics_to_update: list[dict] = []
    nat_topic_ids = {str(nt.id) for nt in nat_topic_rows}

    for nt in nat_topic_rows:
        existing = local_topic_by_natid.get(str(nt.id))
        if existing:
            changes: list[str] = []
            if existing.name != nt.name:
                changes.append("name")
            if existing.sequence_order != int(nt.sequence_order or 0):
                changes.append("sequence_order")
            if existing.learning_outcomes != nt.learning_outcomes:
                changes.append("learning_outcomes")
            # Unit re-parent detection: requires looking at the
            # corresponding national_unit_id local unit, which may be
            # a new unit-to-add. Skip the rare reparent case in
            # preview — `upgrade` itself handles it.
            if changes:
                topics_to_update.append({
                    "local_topic_id": str(existing.id),
                    "national_topic_id": str(nt.id),
                    "code": nt.code,
                    "changed_fields": changes,
                })
        else:
            topics_to_add.append({
                "national_topic_id": str(nt.id),
                "code": nt.code,
                "name": nt.name,
                "sequence_order": int(nt.sequence_order or 0),
            })

    local_orphaned_topics = [
        t for t in local_topics
        if t.national_topic_id and t.national_topic_id not in nat_topic_ids
    ]

    _audit(
        db, request,
        event_type="curriculum.subject.upgrade_previewed",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "subject", "id": str(s.id),
                "school_id": str(school_id),
                "national_subject_id": str(nat.id)},
        details={
            "from_version": from_version,
            "to_version": to_version,
            "units_to_add_count": len(units_to_add),
            "units_to_update_count": len(units_to_update),
            "topics_to_add_count": len(topics_to_add),
            "topics_to_update_count": len(topics_to_update),
            "local_custom_units_preserved_count": len(local_custom_units),
            "local_custom_topics_preserved_count": len(local_custom_topics),
        },
    )
    db.commit()
    return _ok({
        "subject_id": str(s.id),
        "from_version": from_version,
        "to_version": to_version,
        "no_op": False,
        "units_to_add": units_to_add,
        "units_to_update": units_to_update,
        "topics_to_add": topics_to_add,
        "topics_to_update": topics_to_update,
        "local_custom_units_preserved_count": len(local_custom_units),
        "local_custom_topics_preserved_count": len(local_custom_topics),
        "local_nationally_orphaned_units_count": len(local_orphaned_units),
        "local_nationally_orphaned_topics_count": len(local_orphaned_topics),
    }, request)


@router.post("/curriculum/upgrade-subject")
def upgrade_subject(
    body: UpgradeSubjectBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Pull the latest NationalSubject version into this school's
    local Unit/Topic tree. Idempotent — running with no version delta
    is a no-op that just returns counts."""
    s = (
        db.query(Subject)
        .filter(Subject.id == body.school_subject_id,
                Subject.school_id == school_id)
        .first()
    )
    if not s:
        return _err("SUBJECT_NOT_FOUND", "Subject not found.", request, status=404)
    if not s.national_subject_id:
        return _err(
            "SUBJECT_NOT_ADOPTED",
            "Only nationally-adopted subjects can be upgraded.",
            request, status=400,
        )
    # Subject.national_subject_id is String(36); NationalSubject.id is
    # a UUID column. Iterate-and-match in Python to avoid the cross-
    # type IN comparison that SQLite handles unreliably.
    try:
        nat_lookup_id = uuid.UUID(s.national_subject_id)
        nat = (
            db.query(NationalSubject)
            .filter(NationalSubject.id == nat_lookup_id)
            .first()
        )
    except (ValueError, TypeError):
        nat = None
    if not nat:
        return _err(
            "NATIONAL_SUBJECT_NOT_FOUND",
            "Source national subject no longer exists.",
            request, status=404,
        )
    if not nat.ministry_published_at:
        return _err(
            "NATIONAL_SUBJECT_NOT_PUBLISHED",
            "The source national subject is unpublished.",
            request, status=400,
        )

    from_version = int(s.adopted_national_version or 0)
    to_version = int(nat.version or 1)
    if from_version >= to_version:
        return _ok({
            "subject_id": str(s.id),
            "from_version": from_version,
            "to_version": to_version,
            "units_added": 0, "units_updated": 0,
            "topics_added": 0, "topics_updated": 0,
            "no_op": True,
        }, request)

    # Build national-id → local-row maps for upsert lookups.
    local_units = (
        db.query(Unit)
        .filter(Unit.school_id == school_id, Unit.subject_id == s.id)
        .all()
    )
    local_unit_by_natid: dict[str, Unit] = {
        u.national_unit_id: u for u in local_units if u.national_unit_id
    }
    local_topics = (
        db.query(Topic)
        .filter(Topic.school_id == school_id, Topic.subject_id == s.id)
        .all()
    )
    local_topic_by_natid: dict[str, Topic] = {
        t.national_topic_id: t for t in local_topics if t.national_topic_id
    }

    units_added = 0
    units_updated = 0
    topics_added = 0
    topics_updated = 0

    nat_units = (
        db.query(NationalUnit)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalUnit.sequence_order.asc())
        .all()
    )
    nat_unit_to_local: dict[str, Unit] = {}
    for nu in nat_units:
        existing = local_unit_by_natid.get(str(nu.id))
        if existing:
            changed = (
                existing.name != nu.name
                or existing.sequence_order != int(nu.sequence_order or 0)
                or existing.grade_level != nu.grade_level
                or existing.description != nu.description
            )
            if changed:
                existing.name = nu.name
                existing.sequence_order = int(nu.sequence_order or 0)
                existing.grade_level = nu.grade_level
                existing.description = nu.description
                units_updated += 1
            nat_unit_to_local[str(nu.id)] = existing
        else:
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
            units_added += 1
            nat_unit_to_local[str(nu.id)] = u

    # Topics. Two passes — first upsert, then re-wire parents.
    nat_topic_rows = (
        db.query(NationalTopic)
        .join(NationalUnit, NationalUnit.id == NationalTopic.national_unit_id)
        .filter(NationalUnit.national_subject_id == nat.id)
        .order_by(NationalTopic.sequence_order.asc())
        .all()
    )
    for nt in nat_topic_rows:
        local_unit = nat_unit_to_local.get(str(nt.national_unit_id))
        if not local_unit:
            continue
        existing = local_topic_by_natid.get(str(nt.id))
        if existing:
            changed = (
                existing.name != nt.name
                or existing.sequence_order != int(nt.sequence_order or 0)
                or existing.learning_outcomes != nt.learning_outcomes
                or existing.unit_id != local_unit.id   # rare: topic moved units
            )
            if changed:
                existing.name = nt.name
                existing.sequence_order = int(nt.sequence_order or 0)
                existing.learning_outcomes = nt.learning_outcomes
                existing.unit_id = local_unit.id
                topics_updated += 1
        else:
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
            local_topic_by_natid[str(nt.id)] = t
            topics_added += 1

    # Re-wire parent_topic_id pointers.
    for nt in nat_topic_rows:
        local_topic = local_topic_by_natid.get(str(nt.id))
        if not local_topic:
            continue
        if nt.parent_topic_id:
            local_parent = local_topic_by_natid.get(str(nt.parent_topic_id))
            new_parent_id = local_parent.id if local_parent else None
        else:
            new_parent_id = None
        if local_topic.parent_topic_id != new_parent_id:
            local_topic.parent_topic_id = new_parent_id

    s.adopted_national_version = to_version
    _audit(
        db, request,
        event_type="curriculum.subject.upgraded",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "subject", "id": str(s.id),
                "school_id": str(school_id),
                "national_subject_id": str(nat.id)},
        details={
            "from_version": from_version,
            "to_version": to_version,
            "units_added": units_added,
            "units_updated": units_updated,
            "topics_added": topics_added,
            "topics_updated": topics_updated,
        },
    )
    db.commit()
    return _ok({
        "subject_id": str(s.id),
        "from_version": from_version,
        "to_version": to_version,
        "units_added": units_added,
        "units_updated": units_updated,
        "topics_added": topics_added,
        "topics_updated": topics_updated,
        "no_op": False,
    }, request)
