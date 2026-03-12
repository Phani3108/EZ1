import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RefreshRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", str(uuid.uuid4()))
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and receive access + refresh tokens."""
    svc = AuthService(db)
    result = svc.login(
        data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    if result is None:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password",
                              "details": {}, "request_id": _meta(request)["request_id"]}}
        )

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
