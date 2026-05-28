"""Phase 16d — HomeworkTemplate + LessonPlanTemplate endpoints.

Endpoints (mirrored for each template type):
  * `POST   /homework-templates`              — create a template.
  * `GET    /homework-templates`              — list (filter by subject,
                                                 published-only).
  * `GET    /homework-templates/{id}`         — single template.
  * `POST   /homework-templates/{id}/publish-school-wide`
                                              — HoD/SchoolAdmin.
  * `POST   /homework-templates/{id}/unpublish`
  * `POST   /homework-templates/{id}/instantiate`
                                              — body `{class_id,
                                                 due_date?}` clones
                                                 into a real Homework.
                                                 Attachment cloning
                                                 (Phase 16e) wires in
                                                 once attachment MIME
                                                 polish lands.
  * `POST   /homework/{id}/sync-from-template`
                                              — refresh title /
                                                 description from the
                                                 source template.

Same endpoint shape exists for LessonPlanTemplate.

Audit invariants (ADR 018):
  * `template.created`              — target = {school_id, template_id,
                                       template_type}. details = {has_subject}.
                                       No title/body text.
  * `template.published_school_wide` — target = {school_id, template_id}.
  * `template.instantiated`         — target = {school_id, template_id,
                                       instance_id}. details =
                                       {class_id, attachments_cloned}.
  * `template.synced_from_source`   — target = {school_id, instance_id,
                                       source_template_id}.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.content_templates import (
    HomeworkTemplate, LessonPlanTemplate,
)
from app.models.student_life import Homework
from app.models.planning import LessonPlan
from app.models.audit import AuditLog
from app.services.attachment_client import clone_attachments_for_owner
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Content Templates"])


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


def _actor(current_user) -> str:
    return str(current_user["sub"])


def _has_perm(current_user, perm: str) -> bool:
    """Phase 19a — defence-in-depth perm check.

    Gateway forwards a validated `X-Permissions` header; the shared
    `ActorContext` dataclass exposes `has_permission(perm)`. We re-assert
    inside HoD-only handlers so opening the gateway prefix for teacher
    instantiate doesn't accidentally also open publish-school-wide.

    Accepts either the dataclass or the legacy dict shape — both are
    in use across the codebase.
    """
    has_method = getattr(current_user, "has_permission", None)
    if callable(has_method):
        return bool(has_method(perm))
    perms = current_user.get("permissions") if hasattr(current_user, "get") else None
    return bool(perms) and perm in perms


def _audit(db: Session, request: Request, *,
           event_type: str, school_id: str, actor: str,
           target: dict, details: Optional[dict] = None):
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    try:
        record_audit_event(
            db, AuditLog,
            event_type=event_type,
            school_id=uuid.UUID(school_id),
            actor_user_id=uuid.UUID(actor),
            target=target,
            details=details or {},
            request_id=request_id,
        )
    except Exception:
        pass


# ─── Serialisers ──────────────────────────────────────────────────


def _ser_hw_template(t: HomeworkTemplate) -> dict:
    return {
        "id": t.id,
        "school_id": t.school_id,
        "subject_id": t.subject_id,
        "title": t.title,
        "description": t.description,
        "default_due_days": int(t.default_due_days) if t.default_due_days else None,
        "topic_ids": json.loads(t.topic_ids) if t.topic_ids else [],
        "grade_levels": json.loads(t.grade_levels) if t.grade_levels else [],
        "is_published_school_wide": bool(t.is_published_school_wide),
        "source_template_id": t.source_template_id,
        "maintained_by_user_id": t.maintained_by_user_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _ser_lp_template(t: LessonPlanTemplate) -> dict:
    return {
        "id": t.id,
        "school_id": t.school_id,
        "subject_id": t.subject_id,
        "title": t.title,
        "objectives": t.objectives,
        "activities": t.activities,
        "resources": t.resources,
        "suggested_period_number": (
            int(t.suggested_period_number) if t.suggested_period_number else None
        ),
        "topic_ids": json.loads(t.topic_ids) if t.topic_ids else [],
        "grade_levels": json.loads(t.grade_levels) if t.grade_levels else [],
        "is_published_school_wide": bool(t.is_published_school_wide),
        "source_template_id": t.source_template_id,
        "maintained_by_user_id": t.maintained_by_user_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ─── Schemas ──────────────────────────────────────────────────────


class HomeworkTemplateCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field(..., min_length=1)
    subject_id: Optional[uuid.UUID] = None
    default_due_days: Optional[int] = Field(default=None, ge=0, le=365)
    topic_ids: List[uuid.UUID] = Field(default_factory=list)
    grade_levels: List[str] = Field(default_factory=list)
    source_template_id: Optional[uuid.UUID] = None


class HomeworkInstantiate(BaseModel):
    class_id: uuid.UUID
    due_date: Optional[date] = None


class LessonPlanTemplateCreate(BaseModel):
    title: str = Field(..., max_length=200)
    objectives: Optional[str] = None
    activities: Optional[str] = None
    resources: Optional[str] = None
    subject_id: Optional[uuid.UUID] = None
    suggested_period_number: Optional[int] = Field(default=None, ge=0, le=20)
    topic_ids: List[uuid.UUID] = Field(default_factory=list)
    grade_levels: List[str] = Field(default_factory=list)
    source_template_id: Optional[uuid.UUID] = None


class LessonPlanInstantiate(BaseModel):
    class_id: uuid.UUID
    scheduled_date: Optional[date] = None
    scheduled_period_number: Optional[int] = Field(default=None, ge=0, le=20)


# ─── HomeworkTemplate endpoints ───────────────────────────────────


@router.post("/homework-templates")
def create_hw_template(
    body: HomeworkTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    t = HomeworkTemplate(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        subject_id=str(body.subject_id) if body.subject_id else None,
        title=body.title,
        description=body.description,
        default_due_days=body.default_due_days,
        topic_ids=json.dumps([str(t) for t in body.topic_ids]) if body.topic_ids else None,
        grade_levels=json.dumps(body.grade_levels) if body.grade_levels else None,
        source_template_id=str(body.source_template_id) if body.source_template_id else None,
        maintained_by_user_id=_actor(current_user),
    )
    db.add(t)
    db.flush()
    _audit(
        db, request,
        event_type="template.created",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "homework_template", "id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "homework",
                 "has_subject": body.subject_id is not None},
    )
    db.commit()
    return _ok(_ser_hw_template(t), request, status=201)


@router.get("/homework-templates")
def list_hw_templates(
    request: Request,
    subject_id: Optional[uuid.UUID] = Query(None),
    published_only: bool = Query(False),
    mine_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(HomeworkTemplate).filter(
        HomeworkTemplate.school_id == str(school_id),
        HomeworkTemplate.archived_at.is_(None),
    )
    if subject_id:
        q = q.filter(HomeworkTemplate.subject_id == str(subject_id))
    if published_only:
        q = q.filter(HomeworkTemplate.is_published_school_wide == True)  # noqa: E712
    if mine_only:
        q = q.filter(HomeworkTemplate.maintained_by_user_id == _actor(current_user))
    rows = q.order_by(HomeworkTemplate.updated_at.desc()).limit(500).all()
    return _ok([_ser_hw_template(r) for r in rows], request)


@router.post("/homework-templates/{template_id}/publish-school-wide")
def publish_hw_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """HoD / SchoolAdmin only.

    Phase 19a: gateway prefix is `authenticated` (so teachers can hit
    sibling endpoints like /instantiate); this handler enforces the
    HoD/SchoolAdmin scope in-process via `school:manage`. Returns
    403 INSUFFICIENT_PERMISSION when a plain teacher hits it directly.
    """
    if not _has_perm(current_user, "school:manage"):
        return _err(
            "INSUFFICIENT_PERMISSION",
            "Only HoD or SchoolAdmin can publish a template school-wide.",
            request, status=403,
        )
    t = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.id == str(template_id),
                HomeworkTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND", "Template not found.", request, status=404)
    if t.is_published_school_wide:
        return _err("ALREADY_PUBLISHED",
                    "Template is already published school-wide.",
                    request, status=409)
    t.is_published_school_wide = True
    _audit(
        db, request,
        event_type="template.published_school_wide",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "homework_template", "id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "homework"},
    )
    db.commit()
    return _ok(_ser_hw_template(t), request)


@router.post("/homework-templates/{template_id}/unpublish")
def unpublish_hw_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if not _has_perm(current_user, "school:manage"):
        return _err(
            "INSUFFICIENT_PERMISSION",
            "Only HoD or SchoolAdmin can unpublish a school-wide template.",
            request, status=403,
        )
    t = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.id == str(template_id),
                HomeworkTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND", "Template not found.", request, status=404)
    t.is_published_school_wide = False
    _audit(
        db, request,
        event_type="template.unpublished_school_wide",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "homework_template", "id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "homework"},
    )
    db.commit()
    return _ok(_ser_hw_template(t), request)


@router.post("/homework-templates/{template_id}/instantiate")
def instantiate_hw_template(
    template_id: uuid.UUID,
    body: HomeworkInstantiate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Clone the template into a real Homework row for the named class."""
    t = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.id == str(template_id),
                HomeworkTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND", "Template not found.", request, status=404)

    # Derive due_date — explicit body wins; else template's
    # default_due_days from today; else today + 7d as a safe fallback.
    if body.due_date:
        due_date = body.due_date
    elif t.default_due_days is not None:
        due_date = date.today() + timedelta(days=int(t.default_due_days))
    else:
        due_date = date.today() + timedelta(days=7)

    hw = Homework(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        class_id=str(body.class_id),
        subject_id=t.subject_id,
        title=t.title,
        description=t.description,
        due_date=due_date,
        topic_ids=t.topic_ids,
        template_source_id=t.id,
        assigned_by=_actor(current_user),
    )
    db.add(hw)
    db.flush()
    # Phase 17a — clone every attachment the template owns into the
    # new instance. Best-effort cross-service call to communications;
    # failures degrade to attachments_cloned=0 (instance still created).
    # Phase 19b — the result now carries an error_kind so the audit row
    # records WHY zero attachments came through (test env, comms down,
    # bad JSON, etc.). Operators / the reporting consumer can grep for
    # `attachment_clone_error` to find affected templates.
    clone_result = clone_attachments_for_owner(
        school_id=school_id,
        source_owner_kind="homework_template",
        source_owner_id=t.id,
        new_owner_kind="homework",
        new_owner_id=hw.id,
        actor_user_id=_actor(current_user),
    )
    _audit(
        db, request,
        event_type="template.instantiated",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "homework", "id": hw.id,
                "template_id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "homework",
                 "class_id": str(body.class_id),
                 "attachments_cloned": clone_result.cloned_count,
                 "attachment_clone_error": clone_result.error_kind},
    )
    db.commit()
    return _ok({
        "instance_id": hw.id,
        "template_id": t.id,
        "due_date": due_date.isoformat(),
        "class_id": str(body.class_id),
        "attachments_cloned": clone_result.cloned_count,
        "attachment_clone_error": clone_result.error_kind,
    }, request, status=201)


@router.post("/homework/{homework_id}/sync-from-template")
def sync_hw_from_template(
    homework_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    hw = (
        db.query(Homework)
        .filter(Homework.id == str(homework_id),
                Homework.school_id == str(school_id))
        .first()
    )
    if not hw:
        return _err("HOMEWORK_NOT_FOUND", "Homework not found.", request, status=404)
    if not hw.template_source_id:
        return _err("NO_TEMPLATE_SOURCE",
                    "This homework was not instantiated from a template.",
                    request, status=400)
    t = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.id == hw.template_source_id,
                HomeworkTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND",
                    "Source template was deleted; cannot sync.",
                    request, status=404)
    hw.title = t.title
    hw.description = t.description
    hw.topic_ids = t.topic_ids
    _audit(
        db, request,
        event_type="template.synced_from_source",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "homework", "id": hw.id,
                "school_id": str(school_id),
                "source_template_id": t.id},
        details={"template_type": "homework"},
    )
    db.commit()
    return _ok({
        "instance_id": hw.id,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }, request)


# ─── LessonPlanTemplate endpoints ─────────────────────────────────


@router.post("/lesson-plan-templates")
def create_lp_template(
    body: LessonPlanTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    t = LessonPlanTemplate(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        subject_id=str(body.subject_id) if body.subject_id else None,
        title=body.title,
        objectives=body.objectives,
        activities=body.activities,
        resources=body.resources,
        suggested_period_number=body.suggested_period_number,
        topic_ids=json.dumps([str(t) for t in body.topic_ids]) if body.topic_ids else None,
        grade_levels=json.dumps(body.grade_levels) if body.grade_levels else None,
        source_template_id=str(body.source_template_id) if body.source_template_id else None,
        maintained_by_user_id=_actor(current_user),
    )
    db.add(t)
    db.flush()
    _audit(
        db, request,
        event_type="template.created",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "lesson_plan_template", "id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "lesson_plan",
                 "has_subject": body.subject_id is not None},
    )
    db.commit()
    return _ok(_ser_lp_template(t), request, status=201)


@router.get("/lesson-plan-templates")
def list_lp_templates(
    request: Request,
    subject_id: Optional[uuid.UUID] = Query(None),
    published_only: bool = Query(False),
    mine_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(LessonPlanTemplate).filter(
        LessonPlanTemplate.school_id == str(school_id),
        LessonPlanTemplate.archived_at.is_(None),
    )
    if subject_id:
        q = q.filter(LessonPlanTemplate.subject_id == str(subject_id))
    if published_only:
        q = q.filter(LessonPlanTemplate.is_published_school_wide == True)  # noqa: E712
    if mine_only:
        q = q.filter(LessonPlanTemplate.maintained_by_user_id == _actor(current_user))
    rows = q.order_by(LessonPlanTemplate.updated_at.desc()).limit(500).all()
    return _ok([_ser_lp_template(r) for r in rows], request)


@router.post("/lesson-plan-templates/{template_id}/publish-school-wide")
def publish_lp_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    # Phase 19a — HoD/SchoolAdmin gate, see publish_hw_template above.
    if not _has_perm(current_user, "school:manage"):
        return _err(
            "INSUFFICIENT_PERMISSION",
            "Only HoD or SchoolAdmin can publish a template school-wide.",
            request, status=403,
        )
    t = (
        db.query(LessonPlanTemplate)
        .filter(LessonPlanTemplate.id == str(template_id),
                LessonPlanTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND", "Template not found.", request, status=404)
    if t.is_published_school_wide:
        return _err("ALREADY_PUBLISHED",
                    "Template is already published school-wide.",
                    request, status=409)
    t.is_published_school_wide = True
    _audit(
        db, request,
        event_type="template.published_school_wide",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "lesson_plan_template", "id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "lesson_plan"},
    )
    db.commit()
    return _ok(_ser_lp_template(t), request)


@router.post("/lesson-plan-templates/{template_id}/instantiate")
def instantiate_lp_template(
    template_id: uuid.UUID,
    body: LessonPlanInstantiate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    t = (
        db.query(LessonPlanTemplate)
        .filter(LessonPlanTemplate.id == str(template_id),
                LessonPlanTemplate.school_id == str(school_id))
        .first()
    )
    if not t:
        return _err("TEMPLATE_NOT_FOUND", "Template not found.", request, status=404)

    lp = LessonPlan(
        id=str(uuid.uuid4()),
        school_id=str(school_id),
        title=t.title,
        subject_id=t.subject_id,
        class_id=str(body.class_id),
        # LessonPlan has a pre-existing `template_id` reference column
        # from Phase 11d — use it to track the source.
        template_id=t.id,
        objectives=t.objectives,
        activities=t.activities,
        resources=t.resources,
        scheduled_date=body.scheduled_date,
        scheduled_period_number=(
            body.scheduled_period_number
            if body.scheduled_period_number is not None
            else t.suggested_period_number
        ),
        topic_ids=t.topic_ids,
        created_by=_actor(current_user),
    )
    db.add(lp)
    db.flush()
    # Phase 19b — visible-failure pattern; see homework instantiate above.
    clone_result = clone_attachments_for_owner(
        school_id=school_id,
        source_owner_kind="lesson_plan_template",
        source_owner_id=t.id,
        new_owner_kind="lesson_plan",
        new_owner_id=lp.id,
        actor_user_id=_actor(current_user),
    )
    _audit(
        db, request,
        event_type="template.instantiated",
        school_id=str(school_id),
        actor=_actor(current_user),
        target={"resource": "lesson_plan", "id": lp.id,
                "template_id": t.id,
                "school_id": str(school_id)},
        details={"template_type": "lesson_plan",
                 "class_id": str(body.class_id),
                 "attachments_cloned": clone_result.cloned_count,
                 "attachment_clone_error": clone_result.error_kind},
    )
    db.commit()
    return _ok({
        "instance_id": lp.id,
        "template_id": t.id,
        "class_id": str(body.class_id),
        "attachments_cloned": clone_result.cloned_count,
        "attachment_clone_error": clone_result.error_kind,
    }, request, status=201)
