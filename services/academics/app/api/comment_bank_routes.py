"""Comment Bank API (Phase 11c / T-007).

  GET    /comment-bank             — list (any authenticated user — used by marks entry)
  POST   /comment-bank             — create (school admin)
  PUT    /comment-bank/{id}        — update text/category/sort_order (school admin)
  DELETE /comment-bank/{id}        — archive (soft) — school admin
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.comment_bank import CommentBankPhrase
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event


router = APIRouter(tags=["Comment Bank"])


CATEGORIES = {"praise", "improvement", "concern", "behaviour", "effort", "other"}


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _serialize(p: CommentBankPhrase) -> dict:
    return {
        "id": p.id,
        "category": p.category,
        "text": p.text,
        "sort_order": p.sort_order,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "archived_at": p.archived_at.isoformat() if p.archived_at else None,
    }


class PhraseCreate(BaseModel):
    category: str = Field(default="other", max_length=32)
    text: str = Field(..., min_length=1, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=1000)


class PhraseUpdate(BaseModel):
    category: Optional[str] = Field(default=None, max_length=32)
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    sort_order: Optional[int] = Field(default=None, ge=0, le=1000)


@router.get("/comment-bank")
def list_phrases(
    request: Request,
    category: Optional[str] = Query(None, max_length=32),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(CommentBankPhrase).filter(
        CommentBankPhrase.school_id == str(school_id),
    )
    if not include_archived:
        q = q.filter(CommentBankPhrase.archived_at.is_(None))
    if category:
        q = q.filter(CommentBankPhrase.category == category)
    rows = q.order_by(
        CommentBankPhrase.sort_order.desc(),
        CommentBankPhrase.created_at.asc(),
    ).all()
    return {"data": [_serialize(r) for r in rows], "meta": _meta(request)}


@router.post("/comment-bank")
def create_phrase(
    payload: PhraseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.category not in CATEGORIES:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INVALID_CATEGORY",
                "message": f"category must be one of: {sorted(CATEGORIES)}",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    actor = uuid.UUID(str(current_user["sub"]))
    p = CommentBankPhrase(
        school_id=str(school_id),
        category=payload.category,
        text=payload.text.strip(),
        sort_order=payload.sort_order,
        created_by=str(actor),
    )
    db.add(p)
    db.flush()
    record_audit_event(
        db, AuditLog,
        event_type="comment_bank.phrase.created",
        school_id=school_id,
        actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "comment_bank_phrase", "id": p.id},
        # Length only, not the phrase text — phrases can carry teacher
        # commentary patterns that we don't want to dump into audit
        # browsing tools.
        details={"category": payload.category, "length": len(payload.text)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _serialize(p), "meta": _meta(request)}


@router.put("/comment-bank/{phrase_id}")
def update_phrase(
    phrase_id: uuid.UUID,
    payload: PhraseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = (
        db.query(CommentBankPhrase)
        .filter(
            CommentBankPhrase.id == str(phrase_id),
            CommentBankPhrase.school_id == str(school_id),
        )
        .first()
    )
    if p is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Phrase not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    if payload.category is not None:
        if payload.category not in CATEGORIES:
            return JSONResponse(
                status_code=400,
                content={"error": {
                    "code": "INVALID_CATEGORY",
                    "message": f"category must be one of: {sorted(CATEGORIES)}",
                    "details": {}, "request_id": _meta(request)["request_id"],
                }},
            )
        p.category = payload.category
    if payload.text is not None:
        p.text = payload.text.strip()
    if payload.sort_order is not None:
        p.sort_order = payload.sort_order
    db.flush()
    record_audit_event(
        db, AuditLog,
        event_type="comment_bank.phrase.updated",
        school_id=school_id,
        actor_user_id=uuid.UUID(str(current_user["sub"])),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "comment_bank_phrase", "id": p.id},
        details={"changed_fields": [
            k for k in ("category", "text", "sort_order")
            if getattr(payload, k) is not None
        ]},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _serialize(p), "meta": _meta(request)}


@router.delete("/comment-bank/{phrase_id}")
def archive_phrase(
    phrase_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    p = (
        db.query(CommentBankPhrase)
        .filter(
            CommentBankPhrase.id == str(phrase_id),
            CommentBankPhrase.school_id == str(school_id),
        )
        .first()
    )
    if p is None or p.archived_at is not None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Phrase not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    p.archived_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db, AuditLog,
        event_type="comment_bank.phrase.archived",
        school_id=school_id,
        actor_user_id=uuid.UUID(str(current_user["sub"])),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "comment_bank_phrase", "id": p.id},
        details={},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _serialize(p), "meta": _meta(request)}
