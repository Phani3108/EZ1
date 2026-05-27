import base64
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import bcrypt
from jose import jwt, JWTError

from app.config import get_settings

settings = get_settings()


# ─── Password hashing ────────────────────────────────────────────────
#
# We use bcrypt directly (the ``bcrypt`` Python package). passlib 1.7.4
# is incompatible with bcrypt >= 4.x and refuses inputs > 72 bytes.
#
# To preserve full entropy for long passphrases we pre-hash with SHA-256
# and base64-encode the digest before passing to bcrypt. This is the
# same construction used by Django's ``bcrypt_sha256`` and many other
# frameworks: it sidesteps bcrypt's 72-byte limit without truncating.
# Stored hashes are prefixed with ``$bcrypt-sha256$`` so the scheme is
# identifiable on inspection.

_BCRYPT_ROUNDS = 12
_SCHEME_PREFIX = "$bcrypt-sha256$"


def _prepare(password: str) -> bytes:
    """Return a 44-byte base64 SHA-256 digest of the password."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)  # 44 bytes, well under bcrypt's 72-byte cap


def hash_password(password: str) -> str:
    """Return a salted bcrypt-sha256 hash of ``password``."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(_prepare(password), salt).decode("ascii")
    return _SCHEME_PREFIX + hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash created by :func:`hash_password`.

    Also accepts legacy plain bcrypt hashes (``$2b$``…) for backwards
    compatibility with any users seeded before the bcrypt-sha256 switch.
    """
    if not hashed_password:
        return False
    try:
        if hashed_password.startswith(_SCHEME_PREFIX):
            stored = hashed_password[len(_SCHEME_PREFIX):].encode("ascii")
            return bcrypt.checkpw(_prepare(plain_password), stored)
        # Legacy: plain bcrypt, truncates to 72 bytes per bcrypt's contract.
        if hashed_password.startswith("$2"):
            return bcrypt.checkpw(
                plain_password.encode("utf-8")[:72],
                hashed_password.encode("ascii"),
            )
    except (ValueError, TypeError):
        return False
    return False


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
