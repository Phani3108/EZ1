"""Phase 15a — Invite dispatch + outbox read endpoints (Communications).

  * `POST /invitations/dispatch`        — admin-web calls this after
                                          identity created the
                                          Invitation row. Picks a
                                          channel, renders the body,
                                          persists to InviteOutbox.
  * `GET  /invite-outbox`               — admin-web reads back the
                                          state of past dispatches
                                          (status, manual_code, etc.).
  * `POST /invite-outbox/{id}/resend`   — re-queue a manual_pending
                                          or failed row.
  * `POST /invite-outbox/{id}/mark-sent` — used by the outbox worker
                                          after the provider call
                                          succeeds. Internal.

Audit:
  * `invitation.dispatched` — target = {invitation_id, school_id,
    channel}. Details = {provider_name}. NO email, NO phone, NO body.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.invite_outbox import InviteOutbox
from app.models.audit import AuditLog
from app.services.invite_dispatcher import dispatch as _dispatch
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err, _ok, make_audit_helper,
)


router = APIRouter(tags=["Invite Dispatch"])

_audit = make_audit_helper(AuditLog)





def _actor(current_user) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(current_user["sub"]))
    except Exception:
        return None



class DispatchRequest(BaseModel):
    invitation_id: str = Field(..., max_length=36)
    school_name: str = Field(..., max_length=255)
    role: str = Field(..., max_length=32)
    full_name: str = Field(..., max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=32)
    manual_code: str = Field(..., min_length=6, max_length=6)
    invite_url: str = Field(..., max_length=500)


@router.post("/comm/invitations/dispatch")
def dispatch_invitation(
    body: DispatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Pick a channel + render + persist to InviteOutbox."""
    res = _dispatch(
        db,
        invitation_id=body.invitation_id,
        school_id=school_id,
        school_name=body.school_name,
        role=body.role,
        full_name=body.full_name,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        manual_code=body.manual_code,
        invite_url=body.invite_url,
    )
    _audit(
        db, request,
        event_type="invitation.dispatched",
        school_id=school_id,
        actor=_actor(current_user),
        target={"resource": "invitation", "id": body.invitation_id,
                "school_id": str(school_id), "channel": res.channel},
        details={"provider_name": res.provider_name or "manual",
                 "status": res.status},
    )
    db.commit()
    return _ok({
        "invite_outbox_id": res.invite_outbox_id,
        "channel": res.channel,
        "provider_name": res.provider_name,
        "status": res.status,
        "body_excerpt": res.body_excerpt,
    }, request, status=201)


@router.get("/comm/invite-outbox")
def list_invite_outbox(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Browse dispatched invites. Tenant-scoped. Returns the full
    body for the admin's UI — this is intentional so admins can
    re-read what they sent."""
    q = db.query(InviteOutbox).filter(InviteOutbox.school_id == school_id)
    if status:
        q = q.filter(InviteOutbox.status == status)
    rows = q.order_by(InviteOutbox.created_at.desc()).limit(500).all()
    return _ok([{
        "id": str(r.id),
        "invitation_id": r.invitation_id,
        "channel": r.channel,
        "provider_name": r.provider_name,
        "recipient_email": r.recipient_email,
        "recipient_phone": r.recipient_phone,
        "subject": r.subject,
        "body": r.body,
        "manual_code": r.manual_code,
        "invite_url": r.invite_url,
        "status": r.status,
        "retry_count": int(r.retry_count or 0),
        "last_attempt_at": r.last_attempt_at.isoformat() if r.last_attempt_at else None,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows], request)


@router.post("/comm/invite-outbox/{outbox_id}/mark-sent")
def mark_sent(
    outbox_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Outbox worker calls this after the provider confirms send."""
    r = (
        db.query(InviteOutbox)
        .filter(InviteOutbox.id == outbox_id,
                InviteOutbox.school_id == school_id)
        .first()
    )
    if not r:
        return _err("NOT_FOUND", "Outbox row not found.", request, status=404)
    r.status = "sent"
    r.last_attempt_at = datetime.now(timezone.utc)
    db.commit()
    return _ok({"id": str(r.id), "status": r.status}, request)


@router.post("/comm/invite-outbox/{outbox_id}/resend")
def resend(
    outbox_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Re-queue a manual_pending or failed row."""
    r = (
        db.query(InviteOutbox)
        .filter(InviteOutbox.id == outbox_id,
                InviteOutbox.school_id == school_id)
        .first()
    )
    if not r:
        return _err("NOT_FOUND", "Outbox row not found.", request, status=404)
    if r.status == "sent":
        return _err("ALREADY_SENT", "Already sent.", request, status=409)
    r.status = "queued" if r.channel != "manual" else "manual_pending"
    r.retry_count = int(r.retry_count or 0) + 1
    db.commit()
    return _ok({"id": str(r.id), "status": r.status,
                "retry_count": r.retry_count}, request)
