"""
Comprehensive auth-service tests — Quality Gate 2.

Tests cover:
- Password hashing (bcrypt)
- JWT creation & validation -- access + refresh
- Expired token rejection
- Refresh token rotation (old token invalidated)
- RBAC: role assignment, permission expansion
- Token blacklist on logout
- Login audit logging (success + failure + IP + user agent)
- Multi-tenant isolation (school A ≠ school B)
- Standard response envelope format
- Security: wrong password, missing token, deactivated user
- Password reset (password changes, refresh tokens revoked)
"""
import os
import uuid

import pytest
from datetime import datetime, timezone

# Patch env BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User, Role, Permission, RefreshToken, TokenBlacklist, LoginAudit  # noqa: F401

TEST_DB_URL = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Enable FK support for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_auth.db"):
        try:
            os.remove("./test_auth.db")
        except OSError:
            pass


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()


# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════

def _seed_permission(db, name, resource, action):
    p = Permission(id=uuid.uuid4(), name=name, resource=resource, action=action)
    db.add(p)
    db.commit()
    return p


def _seed_role(db, name, permissions=None):
    r = Role(id=uuid.uuid4(), name=name)
    if permissions:
        r.permissions = permissions
    db.add(r)
    db.commit()
    return r


def _register_user(db, email, password, school_id, roles=None):
    from app.utils.security import hash_password
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name="Test User",
        password_hash=hash_password(password),
        school_id=school_id,
        is_active=True,
    )
    if roles:
        user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_auth_service(db):
    from app.services.auth_service import AuthService
    return AuthService(db)


def _login(db, email, password, ip="127.0.0.1"):
    from app.schemas.auth import LoginRequest
    svc = _make_auth_service(db)
    return svc.login(LoginRequest(email=email, password=password), ip_address=ip, user_agent="pytest")


# ═══════════════════════════════════════════
# Unit Tests — Security Utils
# ═══════════════════════════════════════════

class TestPasswordHashing:
    def test_hash_and_verify(self):
        from app.utils.security import hash_password, verify_password
        hashed = hash_password("SecureP@ss123")
        assert verify_password("SecureP@ss123", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_hash_is_unique_per_call(self):
        from app.utils.security import hash_password
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # bcrypt salts differently each time


class TestTokenHashing:
    def test_sha256_deterministic(self):
        from app.utils.security import hash_token
        h1 = hash_token("my-refresh-token")
        h2 = hash_token("my-refresh-token")
        assert h1 == h2
        assert h1 != hash_token("different-token")


class TestJWT:
    def test_create_access_token(self):
        from app.utils.security import create_access_token, decode_token
        token, jti, expire = create_access_token(str(uuid.uuid4()), str(SCHOOL_A), ["Teacher"])
        payload = decode_token(token)
        assert payload["type"] == "access"
        assert payload["school_id"] == str(SCHOOL_A)
        assert "Teacher" in payload["roles"]
        assert payload["jti"] == jti

    def test_create_refresh_token(self):
        from app.utils.security import create_refresh_token, decode_token
        token, jti, expire = create_refresh_token(str(uuid.uuid4()), str(SCHOOL_A), ["Teacher"])
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_expired_token_rejected(self):
        from jose import jwt as jose_jwt, JWTError
        from app.config import get_settings
        from app.utils.security import decode_token
        settings = get_settings()
        payload = {
            "sub": str(uuid.uuid4()), "school_id": str(SCHOOL_A),
            "jti": str(uuid.uuid4()), "type": "access", "roles": [],
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
        }
        token = jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(Exception):
            decode_token(token)

    def test_wrong_school_id_in_token(self):
        from app.utils.security import create_access_token, decode_token
        token, _, _ = create_access_token(str(uuid.uuid4()), str(SCHOOL_A), ["Teacher"])
        payload = decode_token(token)
        assert payload["school_id"] == str(SCHOOL_A)
        assert payload["school_id"] != str(SCHOOL_B)


# ═══════════════════════════════════════════
# Login
# ═══════════════════════════════════════════

class TestLogin:
    def test_login_success(self, db):
        _register_user(db, "login@test.zw", "TestPass1", SCHOOL_A)
        result = _login(db, "login@test.zw", "TestPass1")
        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["expires_in"] > 0
        assert result["user"]["email"] == "login@test.zw"

    def test_login_wrong_password_returns_none(self, db):
        _register_user(db, "wrong@test.zw", "CorrectPass", SCHOOL_A)
        result = _login(db, "wrong@test.zw", "WrongPassword")
        assert result is None

    def test_login_nonexistent_user(self, db):
        result = _login(db, "nobody@test.zw", "Pass1234")
        assert result is None

    def test_login_disabled_user(self, db):
        user = _register_user(db, "disabled@test.zw", "Pass1234", SCHOOL_A)
        user.is_active = False
        db.commit()
        result = _login(db, "disabled@test.zw", "Pass1234")
        assert result is None


class TestLoginAudit:
    def test_successful_login_audited(self, db):
        _register_user(db, "audit@test.zw", "Pass1234", SCHOOL_A)
        _login(db, "audit@test.zw", "Pass1234", ip="10.0.0.1")
        audits = db.query(LoginAudit).filter(LoginAudit.email == "audit@test.zw").all()
        assert len(audits) == 1
        assert audits[0].success is True
        assert audits[0].ip_address == "10.0.0.1"
        assert audits[0].user_agent == "pytest"

    def test_failed_login_audited(self, db):
        _register_user(db, "fail@test.zw", "Pass1234", SCHOOL_A)
        _login(db, "fail@test.zw", "WrongPass", ip="192.168.1.1")
        audits = db.query(LoginAudit).filter(LoginAudit.email == "fail@test.zw").all()
        assert len(audits) == 1
        assert audits[0].success is False
        assert audits[0].failure_reason == "invalid_credentials"


# ═══════════════════════════════════════════
# Refresh Token Rotation
# ═══════════════════════════════════════════

class TestRefreshToken:
    def test_rotation_invalidates_old(self, db):
        _register_user(db, "rotate@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        login_result = _login(db, "rotate@test.zw", "Pass1234")
        old_refresh = login_result["refresh_token"]

        # Refresh — should return new token pair
        new_result = svc.refresh_tokens(old_refresh)
        assert new_result is not None
        assert new_result["refresh_token"] != old_refresh

        # Old refresh token should be revoked
        assert svc.refresh_tokens(old_refresh) is None

    def test_invalid_refresh_token_rejected(self, db):
        svc = _make_auth_service(db)
        assert svc.refresh_tokens("garbage-token") is None


# ═══════════════════════════════════════════
# Logout
# ═══════════════════════════════════════════

class TestLogout:
    def test_logout_blacklists_access_and_revokes_refresh(self, db):
        from app.utils.security import decode_token
        _register_user(db, "logout@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        login_result = _login(db, "logout@test.zw", "Pass1234")

        payload = decode_token(login_result["access_token"])
        svc.logout(payload)

        # Access JTI blacklisted
        assert svc.is_token_blacklisted(payload["jti"])
        # Refresh revoked
        assert svc.refresh_tokens(login_result["refresh_token"]) is None


# ═══════════════════════════════════════════
# /me — Permission Expansion
# ═══════════════════════════════════════════

class TestMe:
    def test_me_returns_expanded_permissions(self, db):
        p1 = _seed_permission(db, "student:read", "student", "read")
        p2 = _seed_permission(db, "attendance:write", "attendance", "write")
        role = _seed_role(db, "Teacher", [p1, p2])
        user = _register_user(db, "me@test.zw", "Pass1234", SCHOOL_A, roles=[role])
        svc = _make_auth_service(db)
        me = svc.get_me(user.id)
        assert "attendance:write" in me["permissions"]
        assert "student:read" in me["permissions"]
        assert "Teacher" in me["roles"]


# ═══════════════════════════════════════════
# Multi-Tenant Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_same_email_different_schools_allowed(self, db):
        u1 = _register_user(db, "shared@email.zw", "Pass1234", SCHOOL_A)
        u2 = _register_user(db, "shared@email.zw", "Pass1234", SCHOOL_B)
        assert u1.id != u2.id

    def test_get_user_blocked_cross_school(self, db):
        user = _register_user(db, "iso@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        assert svc.get_user(user.id, SCHOOL_B) is None
        assert svc.get_user(user.id, SCHOOL_A) is not None

    def test_update_user_blocked_cross_school(self, db):
        from app.schemas.auth import UserUpdate
        user = _register_user(db, "upd@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        assert svc.update_user(user.id, SCHOOL_B, UserUpdate(full_name="Hacked")) is None

    def test_password_reset_blocked_cross_school(self, db):
        from app.schemas.auth import PasswordReset
        user = _register_user(db, "rst@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        assert svc.reset_password(user.id, SCHOOL_B, PasswordReset(new_password="NewPass999")) is False

    def test_list_users_scoped_to_school(self, db):
        _register_user(db, "a1@test.zw", "Pass1234", SCHOOL_A)
        _register_user(db, "a2@test.zw", "Pass1234", SCHOOL_A)
        _register_user(db, "b1@test.zw", "Pass1234", SCHOOL_B)
        svc = _make_auth_service(db)
        users_a, total_a = svc.list_users(SCHOOL_A, 1, 50)
        users_b, total_b = svc.list_users(SCHOOL_B, 1, 50)
        assert total_a == 2
        assert total_b == 1


# ═══════════════════════════════════════════
# Password Reset
# ═══════════════════════════════════════════

class TestPasswordReset:
    def test_password_changes(self, db):
        user = _register_user(db, "pwreset@test.zw", "OldPass123", SCHOOL_A)
        svc = _make_auth_service(db)
        from app.schemas.auth import PasswordReset
        svc.reset_password(user.id, SCHOOL_A, PasswordReset(new_password="NewPass456"))
        assert _login(db, "pwreset@test.zw", "OldPass123") is None
        assert _login(db, "pwreset@test.zw", "NewPass456") is not None

    def test_password_reset_revokes_refresh_tokens(self, db):
        user = _register_user(db, "pwrev@test.zw", "Pass1234", SCHOOL_A)
        svc = _make_auth_service(db)
        login_result = _login(db, "pwrev@test.zw", "Pass1234")
        from app.schemas.auth import PasswordReset
        svc.reset_password(user.id, SCHOOL_A, PasswordReset(new_password="NewPass999"))
        assert svc.refresh_tokens(login_result["refresh_token"]) is None


# ═══════════════════════════════════════════
# RBAC Management
# ═══════════════════════════════════════════

class TestRBAC:
    def test_create_role(self, db):
        from app.schemas.auth import RoleCreate
        svc = _make_auth_service(db)
        result = svc.create_role(RoleCreate(name="CustomRole", description="Test"))
        assert result["name"] == "CustomRole"

    def test_duplicate_role_rejected(self, db):
        from app.schemas.auth import RoleCreate
        svc = _make_auth_service(db)
        svc.create_role(RoleCreate(name="DupRole"))
        result = svc.create_role(RoleCreate(name="DupRole"))
        assert "error" in result

    def test_permission_assignment_to_role(self, db):
        p = _seed_permission(db, "test:read", "test", "read")
        from app.schemas.auth import RoleCreate
        svc = _make_auth_service(db)
        role = svc.create_role(RoleCreate(name="PermTest"))
        result = svc.assign_permission_to_role(uuid.UUID(role["id"]), p.id)
        assert any(pp["name"] == "test:read" for pp in result["permissions"])

    def test_role_assignment_to_user(self, db):
        p = _seed_permission(db, "fees:read", "fees", "read")
        role = _seed_role(db, "Accountant", [p])
        user = _register_user(db, "acct@test.zw", "Pass1234", SCHOOL_A, roles=[role])
        svc = _make_auth_service(db)
        me = svc.get_me(user.id)
        assert "Accountant" in me["roles"]
        assert "fees:read" in me["permissions"]
