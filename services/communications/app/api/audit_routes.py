"""Audit log browse endpoint (Phase 9 / INFRA-018).

`GET /api/v1/audit-log` — paginated, school-scoped, admin-only.
Returns recent audit rows. Supports optional filters: `event_type`,
`actor_user_id`, `from_date`, `to_date`.

The endpoint deliberately does NOT support free-text search of
`target` / `details` JSON — those are intentionally opaque, and a
full-text index over them invites the kind of casual browsing that
runs against the privacy-minimisation goal (ADR 007). If an
administrator needs deeper forensics, they query the DB directly
with a documented purpose.

RBAC: gateway enforces `school:manage` on the path. Each request is
also school-scoped by `school_id` so a misrouted token can't see
another school's audit log.

Pagination uses a simple offset+limit. For Phase 9 + the audit
volumes we expect (~1000 events/day per active school), this is
fine. Keyset pagination is a follow-up once row counts demand it.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.audit import AuditLog
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)


router = APIRouter(tags=["Audit"])



@router.get("/comm/audit-log")
def list_audit_log(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(
        None,
        description="Filter by exact event_type (e.g. 'student.created'). "
                    "See eduzim_shared.audit.Event for the canonical list.",
    ),
    actor_user_id: Optional[uuid.UUID] = Query(
        None,
        description="Filter to events performed by this user.",
    ),
    from_date: Optional[date] = Query(
        None,
        description="ISO date; only events at or after this date.",
    ),
    to_date: Optional[date] = Query(
        None,
        description="ISO date; only events on or before this date.",
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Paginated audit log browse — scoped strictly to the caller's school."""
    q = db.query(AuditLog).filter(AuditLog.school_id == school_id)
    if event_type:
        q = q.filter(AuditLog.event_type == event_type)
    if actor_user_id:
        q = q.filter(AuditLog.actor_user_id == actor_user_id)
    if from_date:
        q = q.filter(AuditLog.occurred_at >= datetime.combine(
            from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        q = q.filter(AuditLog.occurred_at <= datetime.combine(
            to_date, datetime.max.time(), tzinfo=timezone.utc))

    total = q.count()
    rows = (
        q.order_by(desc(AuditLog.occurred_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = [_serialize(r) for r in rows]
    meta = _meta(request)
    meta.update({
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": (page * page_size) < total,
    })
    return {"data": data, "meta": meta}


def _serialize(r: AuditLog) -> dict:
    """Audit row → wire dict. The JSON-encoded `target` / `details`
    columns are parsed back into objects for the wire payload (the
    DB-side JSON-text is just for portability)."""
    def _parse_json(s):
        if not s:
            return None
        try:
            return json.loads(s)
        except (TypeError, ValueError):
            return s   # surface as-is if it isn't valid JSON
    return {
        "id": str(r.id),
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
        "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
        "actor_role": r.actor_role,
        "school_id": str(r.school_id),
        "event_type": r.event_type,
        "target": _parse_json(r.target),
        "details": _parse_json(r.details),
        "ip_address": r.ip_address,
        "user_agent": r.user_agent,
        "request_id": r.request_id,
    }
