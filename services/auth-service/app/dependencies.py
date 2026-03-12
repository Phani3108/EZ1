import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import TokenBlacklist
from app.utils.security import decode_token

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """Extract and validate JWT from Authorization header."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    # Check blacklist
    jti = payload.get("jti")
    if db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first():
        raise HTTPException(status_code=401, detail="Token has been revoked")

    return payload


def require_permission(required: str):
    """Dependency factory: check user has a specific permission via roles."""
    async def checker(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> dict:
        from app.services.auth_service import AuthService
        svc = AuthService(db)
        user_id = uuid.UUID(current_user["sub"])
        me = svc.get_me(user_id)
        if not me or required not in me.get("permissions", []):
            raise HTTPException(status_code=403, detail=f"Permission required: {required}")
        return current_user
    return checker


def get_school_id(current_user: dict = Depends(get_current_user)) -> uuid.UUID:
    """Extract school_id from token — never from client."""
    school_id = current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="school_id missing from token")
    return uuid.UUID(school_id)
