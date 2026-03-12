"""JWT dependencies + teacher authorization for attendance-service."""
import uuid
import httpx
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


def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> str:
    """Return the raw Bearer token string."""
    return credentials.credentials


def get_school_id(current_user: dict = Depends(get_current_user)) -> uuid.UUID:
    sid = current_user.get("school_id")
    if not sid:
        raise HTTPException(status_code=400, detail="school_id missing from token")
    return uuid.UUID(sid)


def is_teacher_role(current_user: dict) -> bool:
    """Check if the current user has a Teacher role."""
    roles = current_user.get("roles", [])
    return "Teacher" in roles


async def verify_teacher_class_authorization(
    teacher_user_id: uuid.UUID,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
) -> bool:
    """Call school-service internal endpoint to verify teacher-class assignment."""
    url = f"{settings.SCHOOL_SERVICE_URL}/internal/teachers/authorize"
    params = {
        "teacher_user_id": str(teacher_user_id),
        "class_id": str(class_id),
        "school_id": str(school_id),
    }
    headers = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("authorized", False)
    except Exception:
        pass
    return False
