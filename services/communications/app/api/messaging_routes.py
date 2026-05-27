"""Parent-Teacher Messaging API (Phase 11b / T-011).

Endpoints:
  GET    /comm/messages/threads               — list threads for caller
  POST   /comm/messages/threads               — create / get-existing thread
  GET    /comm/messages/threads/{id}          — thread + messages
  POST   /comm/messages/threads/{id}/messages — send a message
  POST   /comm/messages/threads/{id}/read     — mark all unread as read
  POST   /comm/messages/{id}/redact           — admin-only soft-delete

Audit hooks land here (route layer) rather than in the service so we
capture request context (request_id, ip, user_agent). The `details`
payload carries event-meta only — never the message body itself.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.services.messaging_service import (
    MessagingService, ParticipantAuthorizationError,
    serialize_thread, serialize_message,
)
from app.models.messaging import MessageThread, Message
from eduzim_shared.audit import record_audit_event
from app.models.audit import AuditLog


router = APIRouter(tags=["Messaging"])


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _sender_role_from_user(current_user: dict) -> str:
    """Roles header is comma-separated. We pick the first matching
    Teacher/Parent role. Defaults to "Teacher" because the route is
    teacher-side; the parent-web side passes "Parent" explicitly."""
    roles = current_user.get("roles") or []
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(",")]
    for r in roles:
        if r.lower() == "parent":
            return "Parent"
        if r.lower() == "teacher":
            return "Teacher"
    return "Teacher"


# ─── Schemas ───────────────────────────────────────────────────────


class ThreadCreate(BaseModel):
    """The caller provides the OTHER participant; the caller's own id
    comes from the JWT. The service figures out which side is the
    teacher and which is the parent based on the caller's roles."""
    other_user_id: uuid.UUID
    # The caller's role on the thread — Teacher creates a thread WITH a
    # parent, Parent creates a thread WITH a teacher. The service will
    # invert as needed.
    other_role: str = Field(..., pattern="^(Teacher|Parent)$")


class MessageSend(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


# ─── Routes ────────────────────────────────────────────────────────


@router.get("/comm/messages/threads")
def list_threads(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    svc = MessagingService(db)
    user_id = uuid.UUID(str(current_user["sub"]))
    threads = svc.list_threads_for_user(school_id=school_id, user_id=user_id)
    data = [serialize_thread(t, viewer_user_id=user_id) for t in threads]
    return {"data": data, "meta": _meta(request)}


@router.post("/comm/messages/threads")
def create_thread(
    payload: ThreadCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    user_id = uuid.UUID(str(current_user["sub"]))
    my_role = _sender_role_from_user(current_user)

    # Figure out which side is teacher and which is parent.
    if my_role == "Teacher" and payload.other_role == "Parent":
        teacher_id, parent_id = user_id, payload.other_user_id
    elif my_role == "Parent" and payload.other_role == "Teacher":
        teacher_id, parent_id = payload.other_user_id, user_id
    else:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INVALID_PARTICIPANTS",
                "message": (
                    "A thread requires one Teacher and one Parent — got "
                    f"{my_role} initiating to {payload.other_role}."
                ),
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )

    svc = MessagingService(db)
    try:
        thread, created = svc.get_or_create_thread(
            school_id=school_id,
            teacher_user_id=teacher_id,
            parent_user_id=parent_id,
            creator_user_id=user_id,
        )
    except ParticipantAuthorizationError as e:
        return JSONResponse(
            status_code=403,
            content={"error": {
                "code": "FORBIDDEN_PAIR", "message": str(e),
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )

    if created:
        record_audit_event(
            db, AuditLog,
            event_type="message.thread.created",
            school_id=school_id,
            actor_user_id=user_id,
            actor_role=my_role,
            target={"resource": "message_thread", "id": str(thread.id)},
            # Privacy: who-met-whom is itself sensitive. We do NOT
            # log the participant ids in `details`; they're already on
            # the row that `target.id` references. This keeps the audit
            # log usable for "show me thread creations today" reports
            # without becoming a parent-teacher graph dump.
            details={"created": True},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            request_id=getattr(request.state, "request_id", None),
        )
        db.commit()
    return {
        "data": {
            **serialize_thread(thread, viewer_user_id=user_id),
            "created": created,
        },
        "meta": _meta(request),
    }


@router.get("/comm/messages/threads/{thread_id}")
def get_thread(
    thread_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    user_id = uuid.UUID(str(current_user["sub"]))
    svc = MessagingService(db)
    thread = svc.get_thread_for_user(
        thread_id=thread_id, school_id=school_id, user_id=user_id,
    )
    if thread is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Thread not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    msgs = svc.list_messages(thread=thread)
    return {
        "data": {
            "thread": serialize_thread(thread, viewer_user_id=user_id),
            "messages": [serialize_message(m) for m in msgs],
        },
        "meta": _meta(request),
    }


@router.post("/comm/messages/threads/{thread_id}/messages")
def send_message(
    thread_id: uuid.UUID,
    payload: MessageSend,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    user_id = uuid.UUID(str(current_user["sub"]))
    role = _sender_role_from_user(current_user)
    svc = MessagingService(db)
    thread = svc.get_thread_for_user(
        thread_id=thread_id, school_id=school_id, user_id=user_id,
    )
    if thread is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Thread not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    try:
        msg = svc.send_message(
            thread=thread,
            sender_user_id=user_id,
            sender_role=role,
            body=payload.body,
        )
    except ParticipantAuthorizationError as e:
        return JSONResponse(
            status_code=403,
            content={"error": {
                "code": "FORBIDDEN", "message": str(e),
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )

    record_audit_event(
        db, AuditLog,
        event_type="message.sent",
        school_id=school_id,
        actor_user_id=user_id,
        actor_role=role,
        target={"resource": "message", "id": str(msg.id),
                "thread_id": str(thread.id)},
        # NB: body length is logged, body content is NOT. Per ADR 018,
        # the audit row carries the FACT and a length signal for
        # filtering ("show me overly-long messages today"), nothing
        # more.
        details={"length": len(payload.body)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": serialize_message(msg), "meta": _meta(request)}


@router.post("/comm/messages/threads/{thread_id}/read")
def mark_thread_read(
    thread_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    user_id = uuid.UUID(str(current_user["sub"]))
    svc = MessagingService(db)
    thread = svc.get_thread_for_user(
        thread_id=thread_id, school_id=school_id, user_id=user_id,
    )
    if thread is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Thread not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    updated = svc.mark_thread_read(thread=thread, reader_user_id=user_id)
    db.commit()
    return {
        "data": {"marked_read": updated},
        "meta": _meta(request),
    }


@router.post("/comm/messages/{message_id}/redact")
def redact_message(
    message_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Soft-delete a message. Admin-only at the gateway RBAC level.
    The route enforces a second check by school scope."""
    user_id = uuid.UUID(str(current_user["sub"]))
    msg = (
        db.query(Message)
        .filter(Message.id == message_id, Message.school_id == school_id)
        .first()
    )
    if msg is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Message not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    svc = MessagingService(db)
    redacted = svc.redact_message(message=msg, actor_user_id=user_id)
    record_audit_event(
        db, AuditLog,
        event_type="message.redacted",
        school_id=school_id,
        actor_user_id=user_id,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "message", "id": str(redacted.id),
                "thread_id": str(redacted.thread_id)},
        details={"original_length": None},  # don't leak the length either
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": serialize_message(redacted), "meta": _meta(request)}
