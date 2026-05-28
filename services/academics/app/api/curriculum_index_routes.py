"""Phase 16b — Topic↔Resource cross-index endpoints.

Every academic-content row (LessonPlan, Homework, Assessment,
FormativeAssessment, and the Phase-16c Question) carries a `topic_ids`
JSON-text column listing the Topic IDs it covers. These endpoints
answer the inverse query:

  * `GET /curriculum/topics/{topic_id}/resources`
    Returns `{lesson_plans, homeworks, assessments,
    formative_assessments, questions}` for the caller's school, each
    filtered to rows that mention `topic_id` in their `topic_ids`
    array.

  * `GET /curriculum/coverage?subject_id=X`
    Per-topic counts: how many LessonPlans, Homework, Assessments,
    FormativeAssessments tag each topic. Used by the HoD coverage
    view to find topics with zero teacher attention.

Implementation notes
--------------------
* `topic_ids` is stored as JSON-text for SQLite + Postgres portability.
* On Postgres we'd ideally use a JSONB column with a GIN index for
  fast `?` membership queries; on SQLite we fall back to a `LIKE`
  substring match. Both code paths use the same `_filter_by_topic`
  helper which does `JSON.contains` via LIKE — exact string match on
  `"<uuid>"` substring inside the stored JSON text. Good enough for
  v16; if performance becomes an issue, Phase 17 switches to JSONB.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Literal

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.curriculum import Topic, Unit
from app.models.school import Subject
from app.models.planning import LessonPlan, FormativeAssessment
from app.models.student_life import Homework
from app.models.assessment import Assessment
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err, _ok,
)


router = APIRouter(tags=["Curriculum Index"])





def _topic_substring(topic_id: str) -> str:
    """Build the substring we expect to find in the JSON-text column.
    JSON arrays of strings serialise the UUID as `"<uuid>"` — we match
    on that exact quoted form so a topic_id is never confused with a
    substring of another id."""
    return f'"{topic_id}"'


# ─── Endpoint ─────────────────────────────────────────────────────


@router.get("/curriculum/topics/{topic_id}/resources")
def topic_resources(
    topic_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
    limit: int = Query(50, ge=1, le=200),
):
    """Return every resource that tags `topic_id` in this school."""
    # Confirm the topic exists in this school (defence-in-depth — even
    # though the cross-tenant LIKE-substring search wouldn't surface
    # other schools' rows anyway).
    t = (
        db.query(Topic)
        .filter(Topic.id == topic_id, Topic.school_id == school_id)
        .first()
    )
    if not t:
        return _err("TOPIC_NOT_FOUND", "Topic not found.", request, status=404)

    needle = _topic_substring(str(topic_id))
    # All four content tables store school_id as String(36) (UUID_STR);
    # coerce once so the comparison is unambiguous on SQLite + Postgres.
    sid = str(school_id)

    lesson_plans = (
        db.query(LessonPlan)
        .filter(
            LessonPlan.school_id == sid,
            LessonPlan.topic_ids.like(f"%{needle}%"),
            LessonPlan.archived_at.is_(None),
        )
        .order_by(LessonPlan.created_at.desc())
        .limit(limit)
        .all()
    )
    homeworks = (
        db.query(Homework)
        .filter(
            Homework.school_id == sid,
            Homework.topic_ids.like(f"%{needle}%"),
            Homework.archived_at.is_(None),
        )
        .order_by(Homework.created_at.desc())
        .limit(limit)
        .all()
    )
    assessments = (
        db.query(Assessment)
        .filter(
            Assessment.school_id == sid,
            Assessment.topic_ids.like(f"%{needle}%"),
            Assessment.deleted_at.is_(None),
        )
        .order_by(Assessment.created_at.desc())
        .limit(limit)
        .all()
    )
    formatives = (
        db.query(FormativeAssessment)
        .filter(
            FormativeAssessment.school_id == sid,
            FormativeAssessment.topic_ids.like(f"%{needle}%"),
        )
        .order_by(FormativeAssessment.created_at.desc())
        .limit(limit)
        .all()
    )

    return _ok({
        "topic": {
            "id": str(t.id),
            "name": t.name,
            "code": t.code,
            "subject_id": str(t.subject_id),
            "unit_id": str(t.unit_id),
        },
        "lesson_plans": [
            {"id": str(r.id), "title": r.title,
             "class_id": str(r.class_id) if r.class_id else None,
             "scheduled_date": r.scheduled_date.isoformat() if r.scheduled_date else None}
            for r in lesson_plans
        ],
        "homeworks": [
            {"id": str(r.id), "title": r.title,
             "class_id": str(r.class_id) if r.class_id else None,
             "due_date": r.due_date.isoformat() if r.due_date else None}
            for r in homeworks
        ],
        "assessments": [
            {"id": str(r.id), "name": r.name,
             "assessment_type": r.assessment_type,
             "class_id": str(r.class_id) if r.class_id else None,
             "date": r.date.isoformat() if r.date else None}
            for r in assessments
        ],
        "formative_assessments": [
            {"id": str(r.id), "title": r.title,
             "formative_kind": r.formative_kind,
             "class_id": str(r.class_id) if r.class_id else None}
            for r in formatives
        ],
        "counts": {
            "lesson_plans": len(lesson_plans),
            "homeworks": len(homeworks),
            "assessments": len(assessments),
            "formative_assessments": len(formatives),
        },
    }, request)


@router.get("/curriculum/coverage")
def curriculum_coverage(
    request: Request,
    subject_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Per-topic resource counts for one subject. Used by the HoD
    coverage view to spot under-tagged areas of the curriculum."""
    subj = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.school_id == school_id)
        .first()
    )
    if not subj:
        return _err("SUBJECT_NOT_FOUND",
                    "Subject not found in this school.",
                    request, status=404)

    topics = (
        db.query(Topic)
        .filter(
            Topic.school_id == school_id,
            Topic.subject_id == subject_id,
            Topic.archived_at.is_(None),
        )
        .order_by(Topic.sequence_order.asc(), Topic.code.asc())
        .all()
    )

    # For each topic compute the four counts via the LIKE substring.
    # On a real Postgres with JSONB we'd batch this with one query
    # using `?|` — for v16's SQLite-compatible path we iterate.
    sid = str(school_id)
    out = []
    for t in topics:
        needle = _topic_substring(str(t.id))
        lp = (
            db.query(LessonPlan)
            .filter(
                LessonPlan.school_id == sid,
                LessonPlan.topic_ids.like(f"%{needle}%"),
                LessonPlan.archived_at.is_(None),
            ).count()
        )
        hw = (
            db.query(Homework)
            .filter(
                Homework.school_id == sid,
                Homework.topic_ids.like(f"%{needle}%"),
                Homework.archived_at.is_(None),
            ).count()
        )
        asmt = (
            db.query(Assessment)
            .filter(
                Assessment.school_id == sid,
                Assessment.topic_ids.like(f"%{needle}%"),
                Assessment.deleted_at.is_(None),
            ).count()
        )
        fm = (
            db.query(FormativeAssessment)
            .filter(
                FormativeAssessment.school_id == sid,
                FormativeAssessment.topic_ids.like(f"%{needle}%"),
            ).count()
        )
        out.append({
            "topic_id": str(t.id),
            "topic_name": t.name,
            "topic_code": t.code,
            "unit_id": str(t.unit_id),
            "lesson_plans": int(lp),
            "homeworks": int(hw),
            "assessments": int(asmt),
            "formative_assessments": int(fm),
            "total": int(lp + hw + asmt + fm),
        })

    return _ok({
        "subject_id": str(subject_id),
        "topics": out,
        "uncovered_count": sum(1 for r in out if r["total"] == 0),
    }, request)


# ─── Tagging endpoint ─────────────────────────────────────────────


class TagBody(BaseModel):
    resource_type: Literal[
        "lesson_plan", "homework", "assessment", "formative_assessment",
    ]
    resource_id: uuid.UUID
    topic_ids: List[uuid.UUID] = Field(default_factory=list, max_length=20)


RESOURCE_MODEL = {
    "lesson_plan": LessonPlan,
    "homework": Homework,
    "assessment": Assessment,
    "formative_assessment": FormativeAssessment,
}


@router.post("/curriculum/tag")
def tag_resource(
    body: TagBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Set the `topic_ids` field on a resource (replaces the whole list).

    This is the simplest way to attach a resource to topics without
    threading a new field through every existing create-schema. Each
    individual create endpoint can call this internally too.
    """
    Model = RESOURCE_MODEL[body.resource_type]
    # All four content models use UUID_STR (String(36)) for both `id`
    # and `school_id`, so compare via plain str() coercion.
    row = (
        db.query(Model)
        .filter(Model.id == str(body.resource_id),
                Model.school_id == str(school_id))
        .first()
    )
    if not row:
        return _err(
            "RESOURCE_NOT_FOUND",
            f"{body.resource_type} not found in this school.",
            request, status=404,
        )
    # Validate every topic_id is in this school.
    if body.topic_ids:
        topic_count = (
            db.query(Topic)
            .filter(
                Topic.school_id == school_id,
                Topic.id.in_(body.topic_ids),
            ).count()
        )
        if topic_count != len(set(body.topic_ids)):
            return _err(
                "INVALID_TOPICS",
                "One or more topic_ids do not belong to this school.",
                request, status=400,
            )
    row.topic_ids = json.dumps([str(t) for t in body.topic_ids]) if body.topic_ids else None
    db.commit()
    return _ok({
        "resource_type": body.resource_type,
        "resource_id": str(body.resource_id),
        "topic_ids": [str(t) for t in body.topic_ids],
    }, request)
