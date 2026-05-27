"""Ministry (MoPSE) cross-school finance aggregation — Phase 14 / M-003.

DEC-013 + ADR 020: Ministry is viewer + auditor only. Every route here
is GET. The route-layer asserts the `Ministry` role explicitly as
defence-in-depth on top of the gateway's `ministry:read` RBAC.

Boundary note: Province / District metadata lives in academics, not
finance. This service returns per-school rollups; the admin-web client
joins with `/api/v1/ministry/geography` (academics) to produce
district/province/national charts. That keeps the service boundary
clean — no cross-service HTTP on every Ministry page load.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.fees import Invoice
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
from eduzim_shared.auth import ActorContext


router = APIRouter(tags=["Ministry — Finance"])


CROSS_SCHOOL_SENTINEL = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _meta(request: Request) -> dict:
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


def _err(code: str, msg: str, request: Request, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"error": {
            "code": code, "message": msg, "details": {},
            "request_id": _meta(request)["request_id"],
        }},
    )


def _ok(data, request: Request):
    return {"data": data, "meta": _meta(request)}


def _require_ministry(current_user, request: Request):
    has_role = False
    if isinstance(current_user, ActorContext):
        has_role = current_user.has_role("Ministry")
    elif hasattr(current_user, "get"):
        roles = current_user.get("roles", []) or []
        has_role = "Ministry" in roles
    if not has_role:
        return _err("FORBIDDEN",
                    "Ministry role required for cross-school aggregation.",
                    request, status_code=403)
    return None


def _actor_id(current_user) -> Optional[uuid.UUID]:
    if isinstance(current_user, ActorContext):
        return current_user.user_id
    try:
        return uuid.UUID(str(current_user["sub"]))
    except Exception:
        return None


def _audit(db: Session, current_user, event_type: str, scope: str, count: int):
    """Per ADR 018: details carry NO amounts here — even though this is
    a money-domain endpoint. The Ministry rollup is NOT an individual
    money move; it is a count of how many invoice rows were aggregated.
    Money-move events that DO log amounts are individual payment writes
    (already covered by finance's existing audit wiring)."""
    actor = _actor_id(current_user)
    try:
        record_audit_event(
            db, AuditLog,
            event_type=event_type,
            actor_user_id=actor,
            school_id=CROSS_SCHOOL_SENTINEL,
            target=scope,
            details={"endpoint": event_type, "rows": int(count)},
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _d(value) -> float:
    """Cast Decimal | None → float for JSON serialisation."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


# ─── M-003 — Per-school fee rollup ─────────────────────────────────


@router.get("/ministry/fees")
def ministry_fees(
    request: Request,
    school_id: Optional[uuid.UUID] = Query(
        None,
        description="Optional filter to a single school. Omit for all schools.",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Per-school fee rollup: invoiced, paid, outstanding, collection-rate.

    Returns one row per school. The admin-web Ministry dashboard joins
    this against `/api/v1/ministry/geography` (academics) for
    district/province/national charts.

    Each row:
      * school_id           — UUID
      * invoices            — count
      * total_invoiced      — sum of total_amount across all invoices
      * total_paid          — sum of paid_amount across all invoices
      * outstanding         — invoiced - paid (clamped to ≥ 0)
      * collection_rate     — paid / invoiced, rounded to 4dp, null if invoiced=0
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e

    q = db.query(
        Invoice.school_id.label("school_id"),
        func.count(Invoice.id).label("invoice_n"),
        func.coalesce(func.sum(Invoice.total_amount), 0).label("invoiced"),
        func.coalesce(func.sum(Invoice.paid_amount), 0).label("paid"),
    ).group_by(Invoice.school_id)

    if school_id is not None:
        q = q.filter(Invoice.school_id == school_id)

    rows = q.all()
    out = []
    for r in rows:
        invoiced = _d(r.invoiced)
        paid = _d(r.paid)
        outstanding = max(0.0, invoiced - paid)
        rate = (
            round(paid / invoiced, 4)
            if invoiced > 0 else None
        )
        out.append({
            "school_id": str(r.school_id),
            "invoices": int(r.invoice_n or 0),
            "total_invoiced": invoiced,
            "total_paid": paid,
            "outstanding": outstanding,
            "collection_rate": rate,
        })

    _audit(db, current_user, "ministry.fees.read",
           f"school:{school_id or '*'}", len(out))
    return _ok(out, request)


# ─── M-003 — Defaulter snapshot (counts only, no PII) ──────────────


@router.get("/ministry/fees/defaulters")
def ministry_defaulters(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Per-school count of currently-overdue or partial invoices.

    PII invariant: NO student names, NO parent contacts, NO row IDs.
    Just `{school_id, overdue_invoices, partial_invoices,
    overdue_amount, partial_amount}` per school.
    """
    if (e := _require_ministry(current_user, request)) is not None:
        return e

    rows = (
        db.query(
            Invoice.school_id.label("school_id"),
            Invoice.status.label("status"),
            func.count(Invoice.id).label("n"),
            func.coalesce(
                func.sum(Invoice.total_amount - Invoice.paid_amount), 0,
            ).label("amount_owed"),
        )
        .filter(Invoice.status.in_(("OVERDUE", "PARTIAL")))
        .group_by(Invoice.school_id, Invoice.status)
        .all()
    )

    # Reshape: one row per school, with both statuses as columns.
    by_school: dict[str, dict] = {}
    for r in rows:
        sid = str(r.school_id)
        sl = by_school.setdefault(sid, {
            "school_id": sid,
            "overdue_invoices": 0,
            "partial_invoices": 0,
            "overdue_amount": 0.0,
            "partial_amount": 0.0,
        })
        if r.status == "OVERDUE":
            sl["overdue_invoices"] = int(r.n or 0)
            sl["overdue_amount"] = _d(r.amount_owed)
        elif r.status == "PARTIAL":
            sl["partial_invoices"] = int(r.n or 0)
            sl["partial_amount"] = _d(r.amount_owed)

    out = sorted(by_school.values(), key=lambda r: r["school_id"])
    _audit(db, current_user, "ministry.defaulters.read", "national", len(out))
    return _ok(out, request)
