"""Shared route helpers — Phase 20a.

Every FastAPI routes file in EduZim used to define its own copies of
the same four helpers:

    def _meta(request) -> dict:
        ...

    def _err(code, msg, request, status=400) -> JSONResponse:
        ...

    def _ok(data, request, status=200) -> JSONResponse:
        ...

    def _audit(db, request, *, event_type, school_id, actor, target,
               details=None):
        ...

…plus the constant:

    CROSS_SCHOOL_SENTINEL = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

These were copy-pasted across ~25 routes files (academics + finance +
communications + identity), totalling ~2,000 lines of identical code.
The drift was the obvious failure mode — if one service tightened its
audit on a cross-cutting concern (per ADR 018), the others stayed
loose.

This module centralizes them. Each routes file now imports the helpers
and creates a per-service `_audit` closure with its local `AuditLog`
model. The call-site signature is unchanged so the migration is one
import + one factory call per file.

Usage
-----

    from eduzim_shared.routes import (
        _meta, _err, _ok, CROSS_SCHOOL_SENTINEL, make_audit_helper,
    )
    from app.models.audit import AuditLog

    _audit = make_audit_helper(AuditLog)

    @router.post("/foo")
    def foo(request: Request, db: Session = Depends(get_db)):
        ...
        _audit(db, request,
               event_type="foo.created",
               school_id=school_id, actor=actor_id,
               target={"id": str(foo_id)},
               details={"count": n})
        return _ok({"id": str(foo_id)}, request, status=201)

Why a factory for `_audit`?
---------------------------

`AuditLog` is a per-service SQLAlchemy model (each service has its own
audit table). The factory lets us close over the model without
threading it through every call site.

Why not adopt `eduzim_shared.response.success_response` / etc.?
----------------------------------------------------------------

That module already exists but uses different function names
(`success_response`, `error_response`, etc.). Migrating call sites to
those would touch every route handler ~3x. Instead this module keeps
the existing terse `_ok`/`_err`/`_meta` names that already match the
codebase conventions, so the migration is a one-line import per file.
The two modules complement each other — `response.py` is for new
services that want the verbose names; this module is for the existing
fleet.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from eduzim_shared.audit import record_audit_event


# ─── ADR 020 cross-school sentinel ─────────────────────────────────
#
# Used for audit rows that legitimately span tenants — Ministry actions,
# cross-school operations, failed logins where the user's school isn't
# known yet. Defined once here so a typo can't desync services.

CROSS_SCHOOL_SENTINEL: uuid.UUID = uuid.UUID(
    "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
)


# ─── Response envelope helpers ──────────────────────────────────────


def _meta(request: Request) -> dict:
    """Standard envelope `meta` block — request_id + ISO-8601 timestamp.

    The request_id comes from middleware (`request.state.request_id`)
    when present; falls back to a fresh UUID4 so the audit chain still
    works in tests that don't run the full middleware stack.
    """
    rid = (
        getattr(request.state, "request_id", str(uuid.uuid4()))
        if hasattr(request, "state")
        else str(uuid.uuid4())
    )
    return {
        "request_id": rid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _err(
    code: str, msg: str, request: Request,
    status: int = 400,
    details: Optional[dict] = None,
    *,
    status_code: Optional[int] = None,
) -> JSONResponse:
    """Standard error envelope.

    Matches the shape returned by every routes file today: a
    `{"error": {"code", "message", "details", "request_id"}}` blob
    with the HTTP status. `details` defaults to `{}` so audit-friendly
    error responses don't carry surprise fields.

    Accepts both `status=` (curriculum/national_templates/onboarding
    convention) and the keyword-only `status_code=`
    (staff/ministry/communications convention) so the Phase 20a
    migration is purely a search-and-replace on the import line.
    """
    final_status = status_code if status_code is not None else status
    return JSONResponse(
        status_code=final_status,
        content={
            "error": {
                "code": code,
                "message": msg,
                "details": details or {},
                "request_id": _meta(request)["request_id"],
            },
        },
    )


def _ok(
    data: Any, request: Request, status: int = 200,
) -> JSONResponse:
    """Standard success envelope: `{"data": ..., "meta": {...}}`."""
    return JSONResponse(
        status_code=status,
        content={"data": data, "meta": _meta(request)},
    )


# ─── Audit helper factory ───────────────────────────────────────────


AuditFn = Callable[..., None]


def make_audit_helper(AuditLogModel: type) -> AuditFn:
    """Build a per-service `_audit(db, request, ...)` closure.

    The closure preserves the existing call-site signature so route
    handlers don't need any code changes beyond replacing the local
    `def _audit` with a `_audit = make_audit_helper(AuditLog)` line at
    the top of the module.

    The closure swallows audit-write failures by design (audit must
    never break the request) but logs them. Adding the row to the
    session here without committing matches the existing pattern: the
    handler does `db.commit()` after its main work, which flushes both
    the business mutation AND the audit row in one transaction. If the
    handler is a read-only path that doesn't commit, the helper falls
    back to its own `db.commit()` — this matches the way Ministry/
    Phase 17 read endpoints write audit events explicitly.

    Parameters
    ----------
    AuditLogModel : SQLAlchemy model class
        Each service has its own audit table; pass the local model.
        The closure uses it via `eduzim_shared.audit.record_audit_event`,
        which is already model-agnostic.
    """
    def _audit(
        db: Session,
        request: Request,
        *,
        event_type: str,
        school_id: Any,  # uuid.UUID or str — coerced to UUID below
        actor: Any,      # uuid.UUID or str or None
        target: dict,
        details: Optional[dict] = None,
        actor_role: Optional[str] = None,
    ) -> None:
        # ADR 020 sentinel and the AuditLog `school_id` column are
        # both `UUID(as_uuid=True)`. SQLAlchemy's bind layer calls
        # `value.hex` on UUID values — so a str leaks through to the
        # flush stage and raises `AttributeError: 'str' object has no
        # attribute 'hex'`. Pre-coerce here so call sites can pass
        # either form (the convention varies — academics generally
        # passes uuid.UUID, communications passes str).
        school_uuid: Optional[uuid.UUID]
        if school_id is None:
            school_uuid = None
        elif isinstance(school_id, uuid.UUID):
            school_uuid = school_id
        else:
            try:
                school_uuid = uuid.UUID(str(school_id))
            except (TypeError, ValueError):
                school_uuid = None
        actor_uuid: Optional[uuid.UUID]
        if actor is None:
            actor_uuid = None
        elif isinstance(actor, uuid.UUID):
            actor_uuid = actor
        else:
            try:
                actor_uuid = uuid.UUID(str(actor))
            except (TypeError, ValueError):
                actor_uuid = None
        request_id = (
            getattr(request.state, "request_id", None)
            if hasattr(request, "state")
            else None
        )
        try:
            record_audit_event(
                db, AuditLogModel,
                event_type=event_type,
                school_id=school_uuid,
                actor_user_id=actor_uuid,
                actor_role=actor_role,
                target=target,
                details=details or {},
                request_id=request_id,
            )
        except Exception:
            # Audit failures must never break the request. The shared
            # helper logs internally; we keep the closure quiet so
            # call sites stay readable.
            try:
                db.rollback()
            except Exception:
                pass

    return _audit


__all__ = [
    "CROSS_SCHOOL_SENTINEL",
    "_meta",
    "_err",
    "_ok",
    "make_audit_helper",
    "AuditFn",
]
