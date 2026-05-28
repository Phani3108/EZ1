import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, CROSS_SCHOOL_SENTINEL,
)
from app.schemas.auth import LoginRequest, RefreshRequest
from app.services.auth_service import AuthService
# Phase 9 follow-up — security-event audit (login success / failure / logout).
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Phase 19d — ADR-020 alignment.
# All other services use this cross-school sentinel for audit rows that
# legitimately span tenants (Ministry actions, failed logins, etc.).
# Identity was the lone holdout on `00000000-…-0`; STATUS.md §6 even
# documented the divergence approvingly. This commit closes it so the
# audit table has one consistent sentinel value.
_CROSS_SCHOOL_SENTINEL = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _audit_school_id(school_id_str: str | None) -> uuid.UUID:
    """Coerce an audit row's school_id. Identity's school_id may be
    None for failed-login attempts where we don't know the user yet —
    in that case we use the cross-school sentinel UUID (per ADR 020)
    so the column constraint is satisfied and audit retention still
    works."""
    if not school_id_str:
        return _CROSS_SCHOOL_SENTINEL
    try:
        return uuid.UUID(str(school_id_str))
    except (TypeError, ValueError):
        return _CROSS_SCHOOL_SENTINEL



@router.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and receive access + refresh tokens."""
    svc = AuthService(db)
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    request_id = getattr(request.state, "request_id", None)
    result = svc.login(
        data,
        ip_address=ip,
        user_agent=user_agent,
    )
    if result is None:
        # Phase 9 follow-up: failed login is a security-relevant event.
        # PII-minimisation: do NOT log the attempted password. The email
        # IS logged (we already know it was supplied; it's the brute-force
        # signal we care about). school_id is unknown on failure → sentinel.
        record_audit_event(
            db,
            event_type="auth.login.failed",
            school_id=_audit_school_id(None),
            actor_user_id=None,
            target={"resource": "auth", "email": data.email},
            details={"reason": "invalid_credentials"},
            ip_address=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        db.commit()
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password",
                              "details": {}, "request_id": _meta(request)["request_id"]}}
        )

    # Success — log the auth.login.success event.
    try:
        actor_user_id = uuid.UUID(str(result.get("user_id"))) if result.get("user_id") else None
    except (TypeError, ValueError):
        actor_user_id = None
    record_audit_event(
        db,
        event_type="auth.login.success",
        school_id=_audit_school_id(result.get("school_id")),
        actor_user_id=actor_user_id,
        actor_role=(result.get("roles") or [None])[0],
        target={"resource": "auth", "user_id": str(actor_user_id) if actor_user_id else None},
        ip_address=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    db.commit()
    return {"data": result, "meta": _meta(request)}


@router.post("/refresh")
def refresh(data: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Exchange refresh token for new token pair."""
    svc = AuthService(db)
    result = svc.refresh_tokens(data.refresh_token)
    if result is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired refresh token",
                              "details": {}, "request_id": _meta(request)["request_id"]}}
        )

    return {"data": result, "meta": _meta(request)}


@router.post("/logout")
def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout — blacklist access token and revoke refresh tokens."""
    svc = AuthService(db)
    svc.logout(current_user)
    # Phase 9 follow-up — audit the logout. Useful for "when did the
    # user end their session" forensics during incidents.
    try:
        actor_user_id = uuid.UUID(str(current_user.get("sub")))
    except (TypeError, ValueError):
        actor_user_id = None
    record_audit_event(
        db,
        event_type="auth.logout",
        school_id=_audit_school_id(current_user.get("school_id")),
        actor_user_id=actor_user_id,
        actor_role=(current_user.get("roles") or [None])[0],
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": {"message": "Successfully logged out"}, "meta": _meta(request)}


@router.get("/me")
def get_me(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user profile with expanded permissions."""
    svc = AuthService(db)
    result = svc.get_me(uuid.UUID(current_user["sub"]))
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "User not found",
                              "details": {}, "request_id": _meta(request)["request_id"]}}
        )

    return {"data": result, "meta": _meta(request)}
