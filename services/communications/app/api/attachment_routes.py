"""Attachment upload / list / download API (Phase 11b / T-008).

Endpoints:
  POST   /comm/attachments               — multipart upload
  GET    /comm/attachments?owner_kind=&owner_id=  — list for an owner
  GET    /comm/attachments/{id}/download — read bytes
  DELETE /comm/attachments/{id}          — soft delete (owner-actor only)

Owner-kind / owner-id pairs are validated by the route layer for the
two owners that Phase 11b actually creates (announcement, message).
Future owners (incident, mark) will add their own checks here as the
respective phases land.

Audit: every upload and every delete writes an `attachment.uploaded` /
`attachment.deleted` row. `details` carries mime_type + size_bytes (a
size signal is useful for "show me unusually large attachments today"
queries) but NEVER the file contents.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, Query,
)
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.attachment import Attachment, ALLOWED_MIME_TYPES, MAX_UPLOAD_BYTES
from app.models.communication import Announcement
from app.models.messaging import Message
from app.services.storage import get_storage
from eduzim_shared.audit import record_audit_event
from app.models.audit import AuditLog


router = APIRouter(tags=["Attachments"])


VALID_OWNER_KINDS = {
    # Phases 11–13 owners.
    "announcement", "message", "incident", "mark",
    # Phase 11e — homework (the polymorphic doc-string mentioned it
    # but the allowlist hadn't caught up).
    "homework",
    # Phase 16 — academic-content owners. Lesson plans + their
    # templates, homework templates, assessments (for exam-paper
    # PDFs), questions, topics (e.g., a scanned ZIMSEC page attached
    # to a topic for reference).
    "lesson_plan", "lesson_plan_template", "homework_template",
    "assessment", "question", "topic", "national_topic",
}


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _verify_owner_exists(
    db: Session, *,
    owner_kind: str, owner_id: uuid.UUID, school_id: uuid.UUID,
) -> bool:
    """Check that the (owner_kind, owner_id) resource exists in this school.

    For owner kinds that don't have a backing table yet (incident,
    mark — owned by Phases 11e and 11c), we accept the upload but
    return False from this check so the audit row records the kind
    explicitly. Once those tables exist, this function gains a real
    check for them.
    """
    if owner_kind == "announcement":
        row = (
            db.query(Announcement)
            .filter(Announcement.id == owner_id, Announcement.school_id == school_id)
            .first()
        )
        return row is not None
    if owner_kind == "message":
        row = (
            db.query(Message)
            .filter(Message.id == owner_id, Message.school_id == school_id)
            .first()
        )
        return row is not None
    # incident / mark — accept; the owning phase will add a real check.
    return True


def _serialize(a: Attachment) -> dict:
    return {
        "id": str(a.id),
        "owner_kind": a.owner_kind,
        "owner_id": str(a.owner_id),
        "file_name": a.file_name,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "uploaded_by_user_id": str(a.uploaded_by_user_id),
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "deleted_at": a.deleted_at.isoformat() if a.deleted_at else None,
    }


@router.post("/comm/attachments")
async def upload_attachment(
    request: Request,
    owner_kind: str = Form(...),
    owner_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if owner_kind not in VALID_OWNER_KINDS:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INVALID_OWNER_KIND",
                "message": (
                    f"owner_kind must be one of: {sorted(VALID_OWNER_KINDS)}"
                ),
                "details": {"owner_kind": owner_kind},
                "request_id": _meta(request)["request_id"],
            }},
        )

    if not _verify_owner_exists(
        db, owner_kind=owner_kind, owner_id=owner_id, school_id=school_id,
    ):
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "OWNER_NOT_FOUND",
                "message": f"{owner_kind}/{owner_id} not found in this school.",
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": {
                "code": "FILE_TOO_LARGE",
                "message": (
                    f"File exceeds the {MAX_UPLOAD_BYTES} byte limit."
                ),
                "details": {"size_bytes": len(raw),
                            "limit_bytes": MAX_UPLOAD_BYTES},
                "request_id": _meta(request)["request_id"],
            }},
        )
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MIME_TYPES:
        return JSONResponse(
            status_code=415,
            content={"error": {
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": (
                    f"mime type '{mime}' is not in the allow-list. "
                    f"Allowed: {sorted(ALLOWED_MIME_TYPES)}"
                ),
                "details": {},
                "request_id": _meta(request)["request_id"],
            }},
        )

    storage = get_storage()
    storage_uri = storage.save(
        raw,
        school_id=school_id,
        mime_type=mime,
        suggested_name=file.filename or "file",
    )

    actor_user_id = uuid.UUID(str(current_user["sub"]))
    a = Attachment(
        school_id=school_id,
        owner_kind=owner_kind,
        owner_id=owner_id,
        file_name=(file.filename or "file")[:255],
        mime_type=mime,
        size_bytes=len(raw),
        storage_uri=storage_uri,
        uploaded_by_user_id=actor_user_id,
    )
    db.add(a)
    db.flush()

    record_audit_event(
        db, AuditLog,
        event_type="attachment.uploaded",
        school_id=school_id,
        actor_user_id=actor_user_id,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "attachment", "id": str(a.id),
                "owner_kind": owner_kind, "owner_id": str(owner_id)},
        # Size + mime are admin-debuggable metadata; the file name is
        # NOT logged because users frequently name files with PII
        # ("alice-report-card.pdf").
        details={"mime_type": mime, "size_bytes": len(raw)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _serialize(a), "meta": _meta(request)}


@router.get("/comm/attachments")
def list_attachments(
    request: Request,
    owner_kind: str = Query(...),
    owner_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if owner_kind not in VALID_OWNER_KINDS:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INVALID_OWNER_KIND",
                "message": (
                    f"owner_kind must be one of: {sorted(VALID_OWNER_KINDS)}"
                ),
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    rows = (
        db.query(Attachment)
        .filter(
            Attachment.school_id == school_id,
            Attachment.owner_kind == owner_kind,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.created_at.asc())
        .all()
    )
    return {"data": [_serialize(a) for a in rows], "meta": _meta(request)}


@router.get("/comm/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    a = (
        db.query(Attachment)
        .filter(
            Attachment.id == attachment_id,
            Attachment.school_id == school_id,
            Attachment.deleted_at.is_(None),
        )
        .first()
    )
    if a is None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Attachment not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    storage = get_storage()
    try:
        data = storage.open(a.storage_uri)
    except FileNotFoundError:
        return JSONResponse(
            status_code=410,
            content={"error": {
                "code": "GONE",
                "message": "Attachment metadata exists but the file has been deleted from storage.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    return Response(
        content=data,
        media_type=a.mime_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{a.file_name}"'
            ),
            "X-Attachment-Id": str(a.id),
        },
    )


@router.delete("/comm/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Soft-delete an attachment. The uploader OR a school admin can
    do this. Bytes are removed from storage; the metadata row stays
    with `deleted_at` set so the audit trail is intact."""
    a = (
        db.query(Attachment)
        .filter(
            Attachment.id == attachment_id,
            Attachment.school_id == school_id,
        )
        .first()
    )
    if a is None or a.deleted_at is not None:
        return JSONResponse(
            status_code=404,
            content={"error": {
                "code": "NOT_FOUND", "message": "Attachment not found.",
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )
    actor_user_id = uuid.UUID(str(current_user["sub"]))
    roles = current_user.get("roles") or []
    is_admin = any(
        (r.lower() if isinstance(r, str) else "") in ("admin", "principal")
        for r in (roles if isinstance(roles, list) else [roles])
    )
    if a.uploaded_by_user_id != actor_user_id and not is_admin:
        return JSONResponse(
            status_code=403,
            content={"error": {
                "code": "FORBIDDEN",
                "message": (
                    "Only the uploader or a school admin can delete an "
                    "attachment."
                ),
                "details": {}, "request_id": _meta(request)["request_id"],
            }},
        )

    storage = get_storage()
    storage.delete(a.storage_uri)
    a.deleted_at = datetime.now(timezone.utc)

    record_audit_event(
        db, AuditLog,
        event_type="attachment.deleted",
        school_id=school_id,
        actor_user_id=actor_user_id,
        actor_role=(roles[0] if roles else None),
        target={"resource": "attachment", "id": str(a.id),
                "owner_kind": a.owner_kind, "owner_id": str(a.owner_id)},
        details={"mime_type": a.mime_type, "size_bytes": a.size_bytes},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _serialize(a), "meta": _meta(request)}
