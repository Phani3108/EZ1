import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """SHA-256 hash of a refresh token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(
    user_id: str,
    school_id: str,
    roles: list,
    permissions: Optional[List[str]] = None,
) -> tuple:
    """Create an access token. Returns (token, jti, expire)."""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "school_id": school_id,
        "roles": roles,
        "permissions": permissions or [],
        "jti": jti,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire


def create_refresh_token(
    user_id: str,
    school_id: str,
    roles: list,
    permissions: Optional[List[str]] = None,
) -> tuple:
    """Create a refresh token. Returns (token, jti, expire)."""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "school_id": school_id,
        "roles": roles,
        "permissions": permissions or [],
        "jti": jti,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire


def decode_token(token: str) -> dict:
    """Decode and validate JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
