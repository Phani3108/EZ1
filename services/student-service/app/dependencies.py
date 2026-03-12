"""JWT dependencies for student-service."""
import uuid
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()
security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")
    return payload


def get_school_id(current_user: dict = Depends(get_current_user)) -> uuid.UUID:
    sid = current_user.get("school_id")
    if not sid:
        raise HTTPException(status_code=400, detail="school_id missing from token")
    return uuid.UUID(sid)


def get_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> str:
    return credentials.credentials
