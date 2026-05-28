"""Forgot-password & self-service password reset."""
import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, PasswordResetToken
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)
from app.utils.security import hash_password
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Password Reset"])



class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Request a password reset token. Always returns 200 (no email oracle)."""
    user = db.query(User).filter(User.email == data.email, User.is_active == True).first()

    if user:
        # Invalidate any existing tokens
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
        ).update({"used": True})

        # Generate token
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires,
        )
        db.add(prt)
        db.commit()

        # In production, send email via SMTP/SendGrid.
        # For now, log the token (viewable via service logs).
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            "password_reset_token_generated",
            extra={
                "user_id": str(user.id),
                "email": data.email,
                "token": raw_token,
                "reset_url": f"{settings.FRONTEND_URL}/reset-password?token={raw_token}",
            },
        )

    # Always return success to prevent email enumeration
    return {
        "data": {"message": "If the email exists, a reset link has been sent."},
        "meta": _meta(request),
    }


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Reset password using a valid token."""
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()

    prt = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False,
    ).first()

    if not prt:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired reset token",
                              "details": {}, "request_id": _meta(request)["request_id"]}},
        )

    if prt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "TOKEN_EXPIRED", "message": "Reset token has expired",
                              "details": {}, "request_id": _meta(request)["request_id"]}},
        )

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "USER_NOT_FOUND", "message": "User not found",
                              "details": {}, "request_id": _meta(request)["request_id"]}},
        )

    user.password_hash = hash_password(data.new_password)
    prt.used = True
    db.commit()

    return {"data": {"message": "Password has been reset successfully."}, "meta": _meta(request)}
