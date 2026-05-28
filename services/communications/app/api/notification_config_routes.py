"""Per-school notification provider config + provider-aware dispatch (Phase 12c)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.notification_config import SchoolNotificationConfig
from app.models.audit import AuditLog
from app.providers import (
    PROVIDER_REGISTRY,
    SUPPORTED_CHANNELS,
    get_provider_for_school_channel,
    NotificationProviderError,
)
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)


router = APIRouter(tags=["Notification Config"])



def _ser_config(c: SchoolNotificationConfig) -> dict:
    try:
        cfg = json.loads(c.config_json) if c.config_json else None
    except (TypeError, ValueError):
        cfg = None
    return {
        "id": str(c.id),
        "school_id": str(c.school_id),
        "channel": c.channel,
        "provider_name": c.provider_name,
        "config": cfg,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


class NotificationConfigPut(BaseModel):
    channel: str = Field(..., max_length=16)
    provider_name: str = Field(..., max_length=32)
    config: Optional[dict] = None


@router.get("/comm/notification-config")
def get_notification_config(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Return one row per channel for this school. Missing rows are
    surfaced as defaults so the admin UI can render every channel."""
    rows = (
        db.query(SchoolNotificationConfig)
        .filter(SchoolNotificationConfig.school_id == school_id)
        .all()
    )
    by_channel = {r.channel: _ser_config(r) for r in rows}
    from app.providers.registry import DEFAULT_PROVIDER_NAMES
    out = []
    for ch in SUPPORTED_CHANNELS:
        if ch in by_channel:
            out.append(by_channel[ch])
        else:
            out.append({
                "id": None, "school_id": str(school_id), "channel": ch,
                "provider_name": DEFAULT_PROVIDER_NAMES[ch],
                "config": None, "updated_at": None, "is_default": True,
            })
    available = sorted({n for _ch, n in PROVIDER_REGISTRY.keys()})
    return {
        "data": {
            "channels": out,
            "available_providers_by_channel": {
                ch: sorted(
                    n for (c, n) in PROVIDER_REGISTRY.keys() if c == ch
                )
                for ch in SUPPORTED_CHANNELS
            },
            "all_providers": available,
        },
        "meta": _meta(request),
    }


@router.put("/comm/notification-config")
def put_notification_config(
    payload: NotificationConfigPut,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.channel not in SUPPORTED_CHANNELS:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "UNKNOWN_CHANNEL",
                "message": (
                    f"channel must be one of: {list(SUPPORTED_CHANNELS)}"
                ),
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )
    if (payload.channel, payload.provider_name) not in PROVIDER_REGISTRY:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "UNKNOWN_PROVIDER",
                "message": (
                    f"provider {payload.provider_name} doesn't serve "
                    f"channel {payload.channel}. Available for this "
                    "channel: " + ", ".join(
                        sorted(
                            n for (c, n) in PROVIDER_REGISTRY.keys()
                            if c == payload.channel
                        )
                    )
                ),
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )

    actor = uuid.UUID(str(current_user["sub"]))
    row = (
        db.query(SchoolNotificationConfig)
        .filter(
            SchoolNotificationConfig.school_id == school_id,
            SchoolNotificationConfig.channel == payload.channel,
        )
        .first()
    )
    if row is None:
        row = SchoolNotificationConfig(
            school_id=school_id,
            channel=payload.channel,
            provider_name=payload.provider_name,
            config_json=json.dumps(payload.config) if payload.config else None,
            updated_by_user_id=actor,
        )
        db.add(row)
    else:
        row.provider_name = payload.provider_name
        row.config_json = json.dumps(payload.config) if payload.config else None
        row.updated_by_user_id = actor
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="notification_config.updated",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "school_notification_config", "id": str(row.id),
                "channel": payload.channel},
        # The config json may carry secrets (api keys); only the
        # provider name is logged.
        details={"provider_name": payload.provider_name},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_config(row), "meta": _meta(request)}


# ─── Provider-aware dispatch ──────────────────────────────────────


class DispatchRequest(BaseModel):
    channel: str = Field(..., max_length=16)
    recipient: str = Field(..., max_length=255)
    subject: Optional[str] = Field(default=None, max_length=255)
    body: str = Field(..., min_length=1, max_length=4000)
    meta: Optional[dict] = None


@router.post("/comm/notify/dispatch")
def dispatch_notification(
    payload: DispatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Internal-/admin-only dispatch endpoint. Picks the school's
    configured provider for the channel and hands off to it.

    Production callers should usually go through the
    NotificationOutbox / dispatcher worker, not this endpoint
    directly — but this is the test-bed for the provider abstraction
    and a useful operational override.
    """
    if payload.channel not in SUPPORTED_CHANNELS:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "UNKNOWN_CHANNEL",
                "message": f"channel must be one of: {list(SUPPORTED_CHANNELS)}",
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )

    provider = get_provider_for_school_channel(db, school_id, payload.channel)
    try:
        result = provider.send(
            recipient=payload.recipient,
            subject=payload.subject,
            body=payload.body,
            meta=payload.meta,
        )
    except NotificationProviderError as e:
        return JSONResponse(
            status_code=502,
            content={"error": {
                "code": "PROVIDER_ERROR",
                "message": str(e),
                "details": {"provider": provider.name, "channel": payload.channel},
                "request_id": _meta(request)["request_id"],
            }},
        )

    actor = uuid.UUID(str(current_user["sub"]))
    record_audit_event(
        db, AuditLog, event_type="notification.dispatched",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "notification", "channel": payload.channel,
                "provider": provider.name,
                "provider_message_id": result.provider_message_id},
        # We log channel + provider + status; we do NOT log recipient
        # (could be PII) or body. Length is fine as a signal.
        details={"status": result.status, "length": len(payload.body)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {
        "data": {
            "provider": provider.name,
            "channel": payload.channel,
            "status": result.status,
            "provider_message_id": result.provider_message_id,
        },
        "meta": _meta(request),
    }
