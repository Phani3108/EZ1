"""Phase 18b — Ministry-distributed template endpoints.

Two surfaces:

  * Ministry-side write API (gated `school:create` at the gateway):
      POST /ministry/national-templates/homework
      PUT  /ministry/national-templates/homework/{id}
      POST /ministry/national-templates/homework/{id}/publish
      POST /ministry/national-templates/homework/{id}/archive
      GET  /ministry/national-templates/homework
      (same shape for /ministry/national-templates/lesson-plan)

  * School-side browse + adopt API (gated `school:manage`):
      GET  /national-templates/homework            — published & not archived
      POST /national-templates/homework/{id}/adopt — clone into school's
            local HomeworkTemplate. Idempotent by (school_id,
            source_national_template_id).

Adopt resolves subject_code → school's local Subject (must already be
adopted) and topic_codes → school's local Topic IDs (best-effort —
unresolved codes are dropped from the local copy's `topic_ids` list
and reported back so the HoD can patch them).

v1 does NOT carry attachments cross-school. National templates are
text-only; HoDs add their own attachments to the adopted local copy.

Audit invariants per ADR 024:
  * Cross-school events use the sentinel UUID
    `eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee` (per ADR 020).
  * `national_template.created` — target=`{template_id, kind}`,
        details=`{subject_code, topic_codes_count, has_grade_levels}`.
        NO title. NO body.
  * `national_template.published` / `.archived` —
        target=`{template_id, kind}`, details=`{}`.
  * `national_template.adopted` —
        target=`{school_id, national_template_id, local_template_id, kind}`,
        details=`{topics_resolved, topics_unresolved}`. NO names.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.school import Subject
from app.models.curriculum import Topic
from app.models.content_templates import (
    HomeworkTemplate, LessonPlanTemplate,
)
from app.models.national_templates import (
    NationalHomeworkTemplate, NationalLessonPlanTemplate,
)
from app.models.audit import AuditLog
# Phase 20a — shared route helpers (replaces ~50 lines of per-file
# copy-paste). See `shared/eduzim_shared/routes.py`.
from eduzim_shared.routes import (
    _meta, _err, _ok, CROSS_SCHOOL_SENTINEL, make_audit_helper,
)


router = APIRouter(tags=["National Templates (Ministry)"])

_audit = make_audit_helper(AuditLog)


def _actor(current_user) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))


def _json_array(s: Optional[str]) -> list:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _ser_homework(t: NationalHomeworkTemplate) -> dict:
    return {
        "id": str(t.id),
        "code": t.code,
        "title": t.title,
        "description": t.description,
        "subject_code": t.subject_code,
        "topic_codes": _json_array(t.topic_codes),
        "grade_levels": _json_array(t.grade_levels),
        "default_due_days": t.default_due_days,
        "published_at": (
            t.published_at.isoformat() if t.published_at else None
        ),
        "archived_at": (
            t.archived_at.isoformat() if t.archived_at else None
        ),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _ser_lesson(t: NationalLessonPlanTemplate) -> dict:
    return {
        "id": str(t.id),
        "code": t.code,
        "title": t.title,
        "objectives": t.objectives,
        "activities": t.activities,
        "resources": t.resources,
        "subject_code": t.subject_code,
        "topic_codes": _json_array(t.topic_codes),
        "grade_levels": _json_array(t.grade_levels),
        "suggested_period_number": t.suggested_period_number,
        "published_at": (
            t.published_at.isoformat() if t.published_at else None
        ),
        "archived_at": (
            t.archived_at.isoformat() if t.archived_at else None
        ),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ─── Ministry-side write API ────────────────────────────────────────


class NationalHomeworkCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    subject_code: Optional[str] = None
    topic_codes: Optional[List[str]] = None
    grade_levels: Optional[List[str]] = None
    default_due_days: Optional[int] = None


class NationalLessonPlanCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    objectives: Optional[str] = None
    activities: Optional[str] = None
    resources: Optional[str] = None
    subject_code: Optional[str] = None
    topic_codes: Optional[List[str]] = None
    grade_levels: Optional[List[str]] = None
    suggested_period_number: Optional[int] = None


@router.post("/ministry/national-templates/homework")
def create_national_homework_template(
    body: NationalHomeworkCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    existing = (
        db.query(NationalHomeworkTemplate)
        .filter(NationalHomeworkTemplate.code == body.code)
        .first()
    )
    if existing:
        return _err("DUPLICATE_CODE", "A template with this code already exists.",
                    request, status=409)
    t = NationalHomeworkTemplate(
        code=body.code, title=body.title, description=body.description,
        subject_code=body.subject_code,
        topic_codes=json.dumps(body.topic_codes or []),
        grade_levels=json.dumps(body.grade_levels or []),
        default_due_days=body.default_due_days,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(t)
    db.flush()
    _audit(
        db, request,
        event_type="national_template.created",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
        target={"resource": "national_homework_template",
                "id": str(t.id), "kind": "homework"},
        details={
            "subject_code": body.subject_code,
            "topic_codes_count": len(body.topic_codes or []),
            "has_grade_levels": bool(body.grade_levels),
        },
    )
    db.commit()
    db.refresh(t)
    return _ok(_ser_homework(t), request, status=201)


@router.post("/ministry/national-templates/lesson-plan")
def create_national_lesson_plan_template(
    body: NationalLessonPlanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    existing = (
        db.query(NationalLessonPlanTemplate)
        .filter(NationalLessonPlanTemplate.code == body.code)
        .first()
    )
    if existing:
        return _err("DUPLICATE_CODE", "A template with this code already exists.",
                    request, status=409)
    t = NationalLessonPlanTemplate(
        code=body.code, title=body.title,
        objectives=body.objectives, activities=body.activities,
        resources=body.resources,
        subject_code=body.subject_code,
        topic_codes=json.dumps(body.topic_codes or []),
        grade_levels=json.dumps(body.grade_levels or []),
        suggested_period_number=body.suggested_period_number,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(t)
    db.flush()
    _audit(
        db, request,
        event_type="national_template.created",
        school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
        target={"resource": "national_lesson_plan_template",
                "id": str(t.id), "kind": "lesson_plan"},
        details={
            "subject_code": body.subject_code,
            "topic_codes_count": len(body.topic_codes or []),
            "has_grade_levels": bool(body.grade_levels),
        },
    )
    db.commit()
    db.refresh(t)
    return _ok(_ser_lesson(t), request, status=201)


@router.post("/ministry/national-templates/homework/{template_id}/publish")
def publish_homework_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = (
        db.query(NationalHomeworkTemplate)
        .filter(NationalHomeworkTemplate.id == str(template_id))
        .first()
    )
    if not t:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if t.archived_at:
        return _err("ARCHIVED", "Cannot publish an archived template.",
                    request, status=400)
    if t.published_at is None:
        t.published_at = datetime.now(timezone.utc)
        _audit(
            db, request,
            event_type="national_template.published",
            school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
            target={"resource": "national_homework_template",
                    "id": str(t.id), "kind": "homework"},
            details={},
        )
    db.commit()
    db.refresh(t)
    return _ok(_ser_homework(t), request)


@router.post("/ministry/national-templates/lesson-plan/{template_id}/publish")
def publish_lesson_plan_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = (
        db.query(NationalLessonPlanTemplate)
        .filter(NationalLessonPlanTemplate.id == str(template_id))
        .first()
    )
    if not t:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if t.archived_at:
        return _err("ARCHIVED", "Cannot publish an archived template.",
                    request, status=400)
    if t.published_at is None:
        t.published_at = datetime.now(timezone.utc)
        _audit(
            db, request,
            event_type="national_template.published",
            school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
            target={"resource": "national_lesson_plan_template",
                    "id": str(t.id), "kind": "lesson_plan"},
            details={},
        )
    db.commit()
    db.refresh(t)
    return _ok(_ser_lesson(t), request)


@router.post("/ministry/national-templates/homework/{template_id}/archive")
def archive_homework_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = (
        db.query(NationalHomeworkTemplate)
        .filter(NationalHomeworkTemplate.id == str(template_id))
        .first()
    )
    if not t:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if t.archived_at is None:
        t.archived_at = datetime.now(timezone.utc)
        _audit(
            db, request,
            event_type="national_template.archived",
            school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
            target={"resource": "national_homework_template",
                    "id": str(t.id), "kind": "homework"},
            details={},
        )
    db.commit()
    db.refresh(t)
    return _ok(_ser_homework(t), request)


@router.post("/ministry/national-templates/lesson-plan/{template_id}/archive")
def archive_lesson_plan_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    t = (
        db.query(NationalLessonPlanTemplate)
        .filter(NationalLessonPlanTemplate.id == str(template_id))
        .first()
    )
    if not t:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if t.archived_at is None:
        t.archived_at = datetime.now(timezone.utc)
        _audit(
            db, request,
            event_type="national_template.archived",
            school_id=CROSS_SCHOOL_SENTINEL, actor=_actor(current_user),
            target={"resource": "national_lesson_plan_template",
                    "id": str(t.id), "kind": "lesson_plan"},
            details={},
        )
    db.commit()
    db.refresh(t)
    return _ok(_ser_lesson(t), request)


@router.get("/ministry/national-templates/homework")
def list_national_homework_templates_ministry(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    include_archived: bool = Query(False),
):
    """Ministry-side list — includes drafts + (optionally) archived."""
    q = db.query(NationalHomeworkTemplate)
    if not include_archived:
        q = q.filter(NationalHomeworkTemplate.archived_at.is_(None))
    rows = q.order_by(NationalHomeworkTemplate.created_at.desc()).all()
    return _ok([_ser_homework(r) for r in rows], request)


@router.get("/ministry/national-templates/lesson-plan")
def list_national_lesson_plan_templates_ministry(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    include_archived: bool = Query(False),
):
    q = db.query(NationalLessonPlanTemplate)
    if not include_archived:
        q = q.filter(NationalLessonPlanTemplate.archived_at.is_(None))
    rows = q.order_by(NationalLessonPlanTemplate.created_at.desc()).all()
    return _ok([_ser_lesson(r) for r in rows], request)


# ─── School-side browse + adopt API ─────────────────────────────────


@router.get("/national-templates/homework")
def browse_homework_templates_for_school(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """School-side browse — published & not archived only."""
    rows = (
        db.query(NationalHomeworkTemplate)
        .filter(NationalHomeworkTemplate.published_at.isnot(None))
        .filter(NationalHomeworkTemplate.archived_at.is_(None))
        .order_by(NationalHomeworkTemplate.published_at.desc())
        .all()
    )
    # Enrich each with the school's adoption state (already adopted?).
    serialized = []
    for r in rows:
        local = (
            db.query(HomeworkTemplate)
            .filter(HomeworkTemplate.school_id == str(school_id))
            .filter(HomeworkTemplate.source_national_template_id == str(r.id))
            .first()
        )
        d = _ser_homework(r)
        d["adopted_local_template_id"] = str(local.id) if local else None
        serialized.append(d)
    return _ok(serialized, request)


@router.get("/national-templates/lesson-plan")
def browse_lesson_plan_templates_for_school(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(NationalLessonPlanTemplate)
        .filter(NationalLessonPlanTemplate.published_at.isnot(None))
        .filter(NationalLessonPlanTemplate.archived_at.is_(None))
        .order_by(NationalLessonPlanTemplate.published_at.desc())
        .all()
    )
    serialized = []
    for r in rows:
        local = (
            db.query(LessonPlanTemplate)
            .filter(LessonPlanTemplate.school_id == str(school_id))
            .filter(LessonPlanTemplate.source_national_template_id == str(r.id))
            .first()
        )
        d = _ser_lesson(r)
        d["adopted_local_template_id"] = str(local.id) if local else None
        serialized.append(d)
    return _ok(serialized, request)


def _resolve_subject_for_school(
    db: Session, school_id: uuid.UUID, subject_code: Optional[str],
) -> Optional[Subject]:
    if not subject_code:
        return None
    return (
        db.query(Subject)
        .filter(Subject.school_id == school_id, Subject.code == subject_code)
        .first()
    )


def _resolve_topics_for_school(
    db: Session, school_id: uuid.UUID, subject_id: Optional[uuid.UUID],
    topic_codes: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve a list of national topic codes → school-local Topic IDs.

    Returns (resolved_ids_as_strings, unresolved_codes). Subject scope
    is optional — when subject_id is set we filter topics under it; else
    we accept any topic with the matching code across this school.
    """
    if not topic_codes:
        return [], []
    # Phase 19d — dedupe codes preserving order. Without this, a Ministry
    # author who lists the same topic code twice would end up with the
    # corresponding local Topic ID duplicated in the adopted template's
    # `topic_ids` JSON, polluting the Topic→Resource cross-index.
    topic_codes = list(dict.fromkeys(topic_codes))
    q = db.query(Topic).filter(Topic.school_id == school_id)
    if subject_id is not None:
        q = q.filter(Topic.subject_id == subject_id)
    local_topics = q.filter(Topic.code.in_(topic_codes)).all()
    found_by_code = {t.code: str(t.id) for t in local_topics}
    resolved = [found_by_code[c] for c in topic_codes if c in found_by_code]
    unresolved = [c for c in topic_codes if c not in found_by_code]
    return resolved, unresolved


@router.post("/national-templates/homework/{template_id}/adopt")
def adopt_homework_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Clone a Ministry homework template into this school's local
    library. Idempotent by (school_id, source_national_template_id) —
    re-adopting returns the existing local row."""
    nat = (
        db.query(NationalHomeworkTemplate)
        .filter(NationalHomeworkTemplate.id == str(template_id))
        .first()
    )
    if not nat:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if not nat.published_at or nat.archived_at is not None:
        return _err(
            "NOT_ADOPTABLE",
            "This template is not currently published.",
            request, status=400,
        )

    existing = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.school_id == str(school_id))
        .filter(HomeworkTemplate.source_national_template_id == str(nat.id))
        .first()
    )
    if existing:
        return _ok({
            "local_template_id": str(existing.id),
            "national_template_id": str(nat.id),
            "idempotent": True,
            "topics_resolved": 0,
            "topics_unresolved": 0,
        }, request)

    subject = _resolve_subject_for_school(db, school_id, nat.subject_code)
    nat_topic_codes = _json_array(nat.topic_codes)
    resolved_ids, unresolved_codes = _resolve_topics_for_school(
        db, school_id, subject.id if subject else None, nat_topic_codes,
    )

    local = HomeworkTemplate(
        school_id=str(school_id),
        subject_id=str(subject.id) if subject else None,
        title=nat.title,
        description=nat.description,
        default_due_days=nat.default_due_days,
        topic_ids=json.dumps(resolved_ids),
        grade_levels=nat.grade_levels,  # already JSON-text
        is_published_school_wide=False,
        maintained_by_user_id=str(_actor(current_user)),
        source_national_template_id=str(nat.id),
    )
    db.add(local)
    try:
        db.flush()
    except IntegrityError:
        # Phase 19b race fix: a concurrent adopt call from the same
        # school just inserted the row first. Roll back, fetch it,
        # return it as idempotent. Migration 2026_05_28_024 adds the
        # UniqueConstraint that drives this.
        db.rollback()
        existing = (
            db.query(HomeworkTemplate)
            .filter(HomeworkTemplate.school_id == str(school_id))
            .filter(HomeworkTemplate.source_national_template_id == str(nat.id))
            .first()
        )
        if existing:
            return _ok({
                "local_template_id": str(existing.id),
                "national_template_id": str(nat.id),
                "idempotent": True,
                "topics_resolved": 0,
                "topics_unresolved": 0,
            }, request)
        raise

    _audit(
        db, request,
        event_type="national_template.adopted",
        school_id=school_id, actor=_actor(current_user),
        target={"resource": "homework_template",
                "id": str(local.id),
                "school_id": str(school_id),
                "national_template_id": str(nat.id),
                "kind": "homework"},
        details={
            "topics_resolved": len(resolved_ids),
            "topics_unresolved": len(unresolved_codes),
            "subject_resolved": subject is not None,
        },
    )
    db.commit()
    return _ok({
        "local_template_id": str(local.id),
        "national_template_id": str(nat.id),
        "idempotent": False,
        "topics_resolved": len(resolved_ids),
        "topics_unresolved": len(unresolved_codes),
        "unresolved_topic_codes": unresolved_codes,
        "subject_resolved": subject is not None,
    }, request, status=201)


@router.post("/national-templates/lesson-plan/{template_id}/adopt")
def adopt_lesson_plan_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    nat = (
        db.query(NationalLessonPlanTemplate)
        .filter(NationalLessonPlanTemplate.id == str(template_id))
        .first()
    )
    if not nat:
        return _err("NOT_FOUND", "Template not found.", request, status=404)
    if not nat.published_at or nat.archived_at is not None:
        return _err(
            "NOT_ADOPTABLE",
            "This template is not currently published.",
            request, status=400,
        )

    existing = (
        db.query(LessonPlanTemplate)
        .filter(LessonPlanTemplate.school_id == str(school_id))
        .filter(LessonPlanTemplate.source_national_template_id == str(nat.id))
        .first()
    )
    if existing:
        return _ok({
            "local_template_id": str(existing.id),
            "national_template_id": str(nat.id),
            "idempotent": True,
            "topics_resolved": 0,
            "topics_unresolved": 0,
        }, request)

    subject = _resolve_subject_for_school(db, school_id, nat.subject_code)
    nat_topic_codes = _json_array(nat.topic_codes)
    resolved_ids, unresolved_codes = _resolve_topics_for_school(
        db, school_id, subject.id if subject else None, nat_topic_codes,
    )

    local = LessonPlanTemplate(
        school_id=str(school_id),
        subject_id=str(subject.id) if subject else None,
        title=nat.title,
        objectives=nat.objectives,
        activities=nat.activities,
        resources=nat.resources,
        suggested_period_number=nat.suggested_period_number,
        topic_ids=json.dumps(resolved_ids),
        grade_levels=nat.grade_levels,
        is_published_school_wide=False,
        maintained_by_user_id=str(_actor(current_user)),
        source_national_template_id=str(nat.id),
    )
    db.add(local)
    try:
        db.flush()
    except IntegrityError:
        # Phase 19b — see adopt_homework_template above.
        db.rollback()
        existing = (
            db.query(LessonPlanTemplate)
            .filter(LessonPlanTemplate.school_id == str(school_id))
            .filter(LessonPlanTemplate.source_national_template_id == str(nat.id))
            .first()
        )
        if existing:
            return _ok({
                "local_template_id": str(existing.id),
                "national_template_id": str(nat.id),
                "idempotent": True,
                "topics_resolved": 0,
                "topics_unresolved": 0,
            }, request)
        raise

    _audit(
        db, request,
        event_type="national_template.adopted",
        school_id=school_id, actor=_actor(current_user),
        target={"resource": "lesson_plan_template",
                "id": str(local.id),
                "school_id": str(school_id),
                "national_template_id": str(nat.id),
                "kind": "lesson_plan"},
        details={
            "topics_resolved": len(resolved_ids),
            "topics_unresolved": len(unresolved_codes),
            "subject_resolved": subject is not None,
        },
    )
    db.commit()
    return _ok({
        "local_template_id": str(local.id),
        "national_template_id": str(nat.id),
        "idempotent": False,
        "topics_resolved": len(resolved_ids),
        "topics_unresolved": len(unresolved_codes),
        "unresolved_topic_codes": unresolved_codes,
        "subject_resolved": subject is not None,
    }, request, status=201)
