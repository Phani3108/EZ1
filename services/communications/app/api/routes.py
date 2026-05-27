"""Communication Service API Routes."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.communication_service import CommunicationService
from app.events import publish_event
from eduzim_shared.idempotency import DbIdempotencyStore
from app.models.idempotency import IdempotencyKey

# Phase 9 follow-up — write-side audit calls for announcements.
from eduzim_shared.audit import Event as AuditEvent, record_audit_event
from app.models.audit import AuditLog

router = APIRouter(tags=["Communication"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4())) if hasattr(request, "state") else str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code, msg, request):
    return {"error": {"code": code, "message": msg, "details": {}, "request_id": _meta(request)["request_id"]}}


# ───── Schemas ─────

class AudienceSchema(BaseModel):
    # RULE-4 (Phase 11b) added the TEACHER_CLASSES audience type so the
    # simplified teacher form can send "all parents of all my classes"
    # without a picker. Resolution happens in the audience resolver —
    # for tests this is mocked; production wires to the academics
    # service's class-roster lookup.
    type: str = Field(..., pattern="^(ALL|CLASS|ROLE|TEACHER_CLASSES)$")
    class_id: Optional[uuid.UUID] = None
    role: Optional[str] = None

class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=500)
    body: str
    audience: AudienceSchema
    channels: List[str]  # ["IN_APP", "SMS"]


# ───── Announcements ─────

@router.post("/comm/announcements")
def create_announcement(data: AnnouncementCreate, request: Request,
                        db: Session = Depends(get_db),
                        current_user: dict = Depends(get_current_user),
                        school_id: uuid.UUID = Depends(get_school_id)):
    # ── Idempotency check via X-Request-Id header ──
    request_id = request.headers.get("X-Request-Id")
    if request_id:
        idem_store = DbIdempotencyStore(db, IdempotencyKey)
        idem_key = f"announcement:{request_id}"
        if idem_store.is_duplicate(idem_key):
            cached = idem_store.get_cached_response(idem_key)
            if cached:
                cached["already_processed"] = True
                return {"data": cached, "meta": _meta(request)}
            return {
                "data": {"already_processed": True},
                "meta": _meta(request),
            }

    svc = CommunicationService(db)
    actor_user_id = uuid.UUID(current_user["sub"])
    result = svc.create_announcement(
        school_id, data.title, data.body,
        data.audience.type, data.channels,
        actor_user_id,
        data.audience.class_id, data.audience.role,
        actor_user_id=actor_user_id,
    )
    if "error" in result:
        return _err(result["error"], result["message"], request), 422

    # ── Record idempotency key ──
    if request_id:
        idem_store = DbIdempotencyStore(db, IdempotencyKey)
        idem_key = f"announcement:{request_id}"
        idem_store.mark_processed(idem_key, result)

    publish_event("eduzim.comm.announcement.created.v1",
                  result["announcement"]["id"],
                  {
                      "announcement_id": result["announcement"]["id"],
                      "audience_type": data.audience.type,
                      "channels": data.channels,
                      "recipient_count": result["recipient_count"],
                  },
                  str(school_id), current_user["sub"])
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.ANNOUNCEMENT_CREATED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "announcement",
                "id": result["announcement"]["id"]},
        details={
            # PII-minimisation: never log the announcement BODY
            # (free-text — could contain anything). Title is short
            # admin-controlled metadata; including it helps the audit
            # trail without exposing user-generated content.
            "title": data.title,
            "audience_type": data.audience.type,
            "channel_count": len(data.channels),
            "recipient_count": result["recipient_count"],
        },
        request_id=request_id,
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.get("/comm/feed")
def get_feed(request: Request,
             student_id: uuid.UUID = Query(...),
             class_id: uuid.UUID = Query(None),
             page: int = Query(1, ge=1),
             page_size: int = Query(20, ge=1, le=100),
             db: Session = Depends(get_db),
             current_user: dict = Depends(get_current_user),
             school_id: uuid.UUID = Depends(get_school_id)):
    """Parent-facing feed: announcements relevant to a specific child."""
    svc = CommunicationService(db)
    anns, total = svc.get_feed_for_student(school_id, student_id, class_id,
                                            page, page_size)
    meta = _meta(request)
    meta.update({"page": page, "page_size": page_size, "total": total})
    return {"data": anns, "meta": meta}


@router.get("/comm/announcements")
def list_announcements(request: Request, page: int = Query(1, ge=1),
                       page_size: int = Query(50, ge=1, le=100),
                       db: Session = Depends(get_db),
                       school_id: uuid.UUID = Depends(get_school_id)):
    svc = CommunicationService(db)
    anns, total = svc.list_announcements(school_id, page, page_size)
    meta = _meta(request)
    meta.update({"page": page, "page_size": page_size, "total": total})
    return {"data": anns, "meta": meta}


@router.delete("/comm/announcements/{ann_id}")
def delete_announcement(ann_id: uuid.UUID, request: Request,
                        db: Session = Depends(get_db),
                        current_user: dict = Depends(get_current_user),
                        school_id: uuid.UUID = Depends(get_school_id)):
    svc = CommunicationService(db)
    result = svc.soft_delete_announcement(ann_id, school_id)
    if not result:
        return _err("NOT_FOUND", "Announcement not found", request), 404
    record_audit_event(
        db, AuditLog,
        event_type=AuditEvent.ANNOUNCEMENT_DELETED,
        school_id=school_id,
        actor_user_id=uuid.UUID(current_user["sub"]) if current_user.get("sub") else None,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "announcement", "id": str(ann_id)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


# ───── Outbox ─────

@router.get("/comm/outbox")
def get_outbox(request: Request, status: str = Query(None),
               announcement_id: uuid.UUID = Query(None),
               limit: int = Query(100, ge=1, le=500),
               offset: int = Query(0, ge=0),
               db: Session = Depends(get_db),
               school_id: uuid.UUID = Depends(get_school_id)):
    svc = CommunicationService(db)
    return {"data": svc.get_outbox(school_id, status, announcement_id, limit, offset),
            "meta": _meta(request)}


@router.get("/comm/outbox/stats")
def outbox_stats(request: Request,
                 db: Session = Depends(get_db),
                 school_id: uuid.UUID = Depends(get_school_id)):
    """
    Roll-up of the school's outbox so admin Notification Center can
    show a single dashboard line ("3 failed, 12 pending, 4,210 delivered").
    """
    from sqlalchemy import func
    from app.models.communication import NotificationOutbox

    rows = (
        db.query(NotificationOutbox.status, NotificationOutbox.channel,
                 func.count(NotificationOutbox.id))
        .filter(NotificationOutbox.school_id == school_id)
        .group_by(NotificationOutbox.status, NotificationOutbox.channel)
        .all()
    )
    totals: dict[str, int] = {}
    by_channel: dict[str, dict[str, int]] = {}
    for status, channel, count in rows:
        totals[status] = totals.get(status, 0) + int(count)
        by_channel.setdefault(channel, {})[status] = int(count)

    return {
        "data": {
            "totals": totals,
            "by_channel": by_channel,
        },
        "meta": _meta(request),
    }


@router.post("/comm/outbox/{entry_id}/retry")
def retry_outbox_entry(entry_id: uuid.UUID, request: Request,
                       db: Session = Depends(get_db),
                       school_id: uuid.UUID = Depends(get_school_id)):
    """
    Reset a FAILED outbox row back to PENDING so the worker picks it up
    again on its next sweep. Admin-curated retry.
    """
    from app.models.communication import NotificationOutbox

    entry = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.id == entry_id,
            NotificationOutbox.school_id == school_id,
        )
        .first()
    )
    if not entry:
        return _err("NOT_FOUND", "Outbox entry not found.", request), 404
    if entry.status not in ("FAILED",):
        return _err(
            "INVALID_STATE",
            f"Only FAILED entries can be retried (current status: {entry.status}).",
            request,
        ), 422

    entry.status = "PENDING"
    entry.retry_count = 0
    entry.error_message = None
    db.commit()
    return {
        "data": {"id": str(entry.id), "status": entry.status, "retried": True},
        "meta": _meta(request),
    }
