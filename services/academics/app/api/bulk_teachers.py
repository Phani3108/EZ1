"""Phase 15a — Bulk teacher import.

CSV columns:
  * `first_name`, `last_name`  — required
  * `email`                    — required (the identity-side primary key)
  * `phone`                    — optional
  * `class_codes`              — optional, comma-separated list of
                                 class codes from the school's
                                 academic year. e.g., "F1A,F1B".

On accept:
  * One `InviteRequest` is queued per row with `role=Teacher` and
    `extra` populated with the class_codes csv. Admin-web's dispatcher
    later turns each row into an identity `Invitation` + a real
    `ClassTeacherAssignment` once the teacher activates.

We deliberately do NOT create `ClassTeacherAssignment` rows here —
they need a valid `teacher_user_id`, which only exists after identity
creates the User. The class-assignment step happens at dispatch time.

Dry-run mode validates row shapes + returns the would-be queue
contents without writing.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.onboarding import InviteRequest


router = APIRouter(tags=["Bulk Operations"])


REQUIRED = {"first_name", "last_name", "email"}
OPTIONAL = {"phone", "class_codes"}
MAX_ROWS = 1000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code: str, msg: str, request: Request, status: int = 400, details: dict | None = None):
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code, "message": msg, "details": details or {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _validate_row(row: dict, row_num: int) -> list[dict]:
    errors = []
    for col in REQUIRED:
        if not (row.get(col, "") or "").strip():
            errors.append({"row": row_num, "field": col, "error": f"{col} is required"})
    e = (row.get("email", "") or "").strip()
    if e and not EMAIL_PATTERN.match(e):
        errors.append({"row": row_num, "field": "email", "error": "invalid email"})
    p = (row.get("phone", "") or "").strip()
    if p and not PHONE_PATTERN.match(p.replace(" ", "")):
        errors.append({"row": row_num, "field": "phone", "error": "invalid phone"})
    return errors


@router.post("/bulk/teachers")
async def import_teachers_csv(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only; do not queue invites"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Bulk-queue teacher invites from a CSV file."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return _err("INVALID_FILE", "File must be a .csv", request)

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _err("ENCODING_ERROR", "File must be UTF-8 encoded", request)

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED - headers
    if missing:
        return _err(
            "MISSING_COLUMNS",
            f"Missing required columns: {', '.join(sorted(missing))}",
            request,
            details={"missing": sorted(missing), "found": sorted(headers)},
        )

    actor = uuid.UUID(str(current_user["sub"]))
    results = {"total": 0, "queued": 0, "skipped": 0, "errors": []}

    for row_num, row in enumerate(reader, start=2):
        if row_num > MAX_ROWS + 1:
            results["errors"].append(
                {"row": row_num, "error": f"Maximum {MAX_ROWS} rows exceeded"}
            )
            break
        results["total"] += 1
        row_errors = _validate_row(row, row_num)
        if row_errors:
            results["errors"].extend(row_errors)
            results["skipped"] += 1
            continue
        if dry_run:
            results["queued"] += 1
            continue

        email = row["email"].strip()
        phone = (row.get("phone") or "").strip()
        class_codes = (row.get("class_codes") or "").strip()
        full_name = f"{row['first_name'].strip()} {row['last_name'].strip()}".strip()

        # Idempotency: if there's already a pending InviteRequest for this
        # (school, role, email) tuple, skip the row (don't double-queue).
        dup = (
            db.query(InviteRequest)
            .filter(
                InviteRequest.school_id == school_id,
                InviteRequest.role == "Teacher",
                InviteRequest.contact_email == email,
                InviteRequest.request_status == "pending",
            )
            .first()
        )
        if dup:
            results["skipped"] += 1
            continue

        ir = InviteRequest(
            id=uuid.uuid4(),
            school_id=school_id,
            role="Teacher",
            full_name=full_name,
            contact_email=email,
            contact_phone=phone or None,
            target_resource_id=None,
            target_resource_type=None,
            extra=class_codes or None,
            requested_by_user_id=actor,
        )
        db.add(ir)
        results["queued"] += 1

    db.commit()
    meta = _meta(request)
    meta["dry_run"] = dry_run
    return {"data": results, "meta": meta}


@router.get("/bulk/invite-requests")
def list_invite_requests(
    request: Request,
    role: Optional[str] = Query(None),
    status: Optional[str] = Query("pending"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Browse the queue. Tenant-scoped."""
    q = db.query(InviteRequest).filter(InviteRequest.school_id == school_id)
    if role:
        q = q.filter(InviteRequest.role == role)
    if status:
        q = q.filter(InviteRequest.request_status == status)
    rows = q.order_by(InviteRequest.requested_at.desc()).limit(500).all()
    return {
        "data": [{
            "id": str(r.id),
            "school_id": str(r.school_id),
            "role": r.role,
            "full_name": r.full_name,
            "contact_email": r.contact_email,
            "contact_phone": r.contact_phone,
            "target_resource_id": r.target_resource_id,
            "target_resource_type": r.target_resource_type,
            "extra": r.extra,
            "request_status": r.request_status,
            "identity_invitation_id": r.identity_invitation_id,
            "last_error": r.last_error,
            "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            "dispatched_at": r.dispatched_at.isoformat() if r.dispatched_at else None,
        } for r in rows],
        "meta": _meta(request),
    }


@router.post("/bulk/invite-requests/{request_id}/mark-dispatched")
def mark_dispatched(
    request_id: uuid.UUID,
    request: Request,
    identity_invitation_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    """Admin-web calls this after successfully posting the row to
    identity's POST /api/v1/invitations. Marks the queue row
    dispatched + stores the identity-side invitation ID for tracking."""
    ir = (
        db.query(InviteRequest)
        .filter(InviteRequest.id == request_id,
                InviteRequest.school_id == school_id)
        .first()
    )
    if not ir:
        return _err("NOT_FOUND", "Invite request not found.", request, status=404)
    ir.request_status = "dispatched"
    ir.identity_invitation_id = identity_invitation_id
    ir.dispatched_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "data": {"id": str(ir.id), "request_status": "dispatched"},
        "meta": _meta(request),
    }
