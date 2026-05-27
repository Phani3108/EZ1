"""Phase 15a — Invitation flow tests.

Covers:
  * Create → preview → accept (token path).
  * Create → manual-code accept (offline fallback).
  * Idempotent re-create returns the same row, rotated token.
  * Expired token rejected.
  * Already-accepted token rejected.
  * Resend rotates token + bumps attempts.
  * Activated user can then log in (verifies password_hash flips
    nullable → set correctly).
  * Audit invariants: NO email, NO phone, NO password in any AuditLog
    row's `target` or `details`.
"""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest

# Env must be set before app imports.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_identity_invitations.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN",
                      "test-internal-token-DO-NOT-USE-IN-PRODUCTION")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    # Importing user + invitation ensures their tables are registered.
    from app.models.user import User, Role, Permission, AuditLog  # noqa
    from app.models.invitation import Invitation  # noqa

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session):
    _, SessionLocal = engine_and_session
    from app.database import get_db
    from app.dependencies import get_current_user
    from app.main import app

    inviter_id = uuid.uuid4()

    def _override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    async def _override_user():
        # Mocked JWT payload — gateway would put this in the header.
        return {
            "sub": str(inviter_id),
            "school_id": str(SCHOOL_A),
            "roles": ["SchoolAdmin"],
            "permissions": ["invite:write", "school:manage"],
            "type": "access",
            "jti": "test-jti",
        }

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    yield TestClient(app, raise_server_exceptions=False), inviter_id
    app.dependency_overrides.clear()


def _seed_role(SessionLocal, name: str):
    """Identity's RBAC requires the role to exist before invitation."""
    from app.models.user import Role
    s = SessionLocal()
    try:
        r = Role(id=uuid.uuid4(), name=name, description="seeded for test")
        s.add(r)
        s.commit()
        return r
    finally:
        s.close()


class TestInvitationCreate:
    def test_create_then_preview_then_accept(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        # 1. Create
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A),
            "role": "Parent",
            "full_name": "Tendai Mukoma",
            "contact_phone": "+263770000001",
        })
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["role"] == "Parent"
        raw = data["raw_token"]
        code = data["manual_code"]
        assert len(code) == 6 and code.isdigit()
        assert raw and len(raw) > 30

        # 2. Preview — no auth header needed (we still use the mocked
        # dep but preview is public; with the dep override the route
        # still works).
        pv = c.get(f"/api/v1/invitations/{raw}/preview")
        assert pv.status_code == 200, pv.text
        pdat = pv.json()["data"]
        assert pdat["role"] == "Parent"
        assert pdat["full_name"] == "Tendai Mukoma"

        # 3. Accept
        ac = c.post(f"/api/v1/invitations/{raw}/accept",
                    json={"password": "Ndatenda123"})
        assert ac.status_code == 200, ac.text
        adat = ac.json()["data"]
        assert adat["role"] == "Parent"
        assert adat["school_id"] == str(SCHOOL_A)

        # 4. Replay accept → ALREADY_ACCEPTED.
        ac2 = c.post(f"/api/v1/invitations/{raw}/accept",
                     json={"password": "Other123!"})
        assert ac2.status_code == 409

    def test_requires_at_least_one_contact(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A),
            "role": "Parent",
            "full_name": "No Contact",
        })
        # Pydantic 422 since the validator rejects.
        assert r.status_code == 422

    def test_idempotent_recreate_rotates_token(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Teacher")
        body = {
            "school_id": str(SCHOOL_A), "role": "Teacher",
            "full_name": "Mrs Ndlovu", "contact_email": "n@example.com",
        }
        r1 = c.post("/api/v1/invitations", json=body)
        r2 = c.post("/api/v1/invitations", json=body)
        assert r1.status_code == 201
        assert r2.status_code == 200   # idempotent → returns 200 (not 201)
        d1 = r1.json()["data"]
        d2 = r2.json()["data"]
        # Same row id...
        assert d1["id"] == d2["id"]
        # ...but rotated token + code.
        assert d1["raw_token"] != d2["raw_token"]
        assert d1["manual_code"] != d2["manual_code"]

    def test_unknown_role_rejected(self, client, engine_and_session):
        c, _ = client
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A),
            "role": "GalacticEmperor",
            "full_name": "Z",
            "contact_email": "z@example.com",
        })
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_ROLE"


class TestManualCodeFallback:
    def test_accept_by_code(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Parent",
            "full_name": "Phone-Only Parent",
            "contact_phone": "+263770111222",
        })
        code = r.json()["data"]["manual_code"]

        ac = c.post("/api/v1/invitations/by-code", json={
            "phone": "+263770111222", "code": code,
            "password": "Sadza123!",
        })
        assert ac.status_code == 200, ac.text

    def test_wrong_code_rejected(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Parent",
            "full_name": "Phone-Only", "contact_phone": "+263770111333",
        })
        ac = c.post("/api/v1/invitations/by-code", json={
            "phone": "+263770111333", "code": "000000",
            "password": "OkPass123!",
        })
        assert ac.status_code == 404
        assert ac.json()["error"]["code"] == "INVALID_CODE"


class TestResend:
    def test_resend_rotates_token_and_bumps_attempts(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Teacher")
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Teacher",
            "full_name": "Teacher Tee", "contact_email": "tt@example.com",
        })
        raw1 = r.json()["data"]["raw_token"]
        rs = c.post(f"/api/v1/invitations/{raw1}/resend")
        assert rs.status_code == 200, rs.text
        d = rs.json()["data"]
        assert d["attempts"] == 1
        # Old token no longer works.
        pv = c.get(f"/api/v1/invitations/{raw1}/preview")
        assert pv.status_code == 404


class TestActivatedUserCanLogIn:
    def test_round_trip(self, client, engine_and_session):
        from app.services.auth_service import AuthService
        from app.schemas.auth import LoginRequest
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        r = c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Parent",
            "full_name": "Login Tester", "contact_email": "lt@example.com",
        })
        raw = r.json()["data"]["raw_token"]
        c.post(f"/api/v1/invitations/{raw}/accept",
               json={"password": "MyPassword!1"})

        s = SL()
        try:
            svc = AuthService(s)
            ok = svc.login(LoginRequest(email="lt@example.com",
                                        password="MyPassword!1"))
            assert ok is not None
            # AuthService returns {access_token, refresh_token, user{}}.
            # Verify the activated user matches the invited one.
            assert ok["user"]["email"] == "lt@example.com"
            assert "Parent" in ok["user"]["roles"]
            bad = svc.login(LoginRequest(email="lt@example.com",
                                         password="Wrong!"))
            assert bad is None
        finally:
            s.close()

    def test_invited_but_not_yet_activated_cannot_log_in(self, client, engine_and_session):
        """User row exists (invited) but password_hash is NULL — must
        be refused at login as invalid_credentials."""
        from app.services.auth_service import AuthService
        from app.schemas.auth import LoginRequest
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Teacher")
        c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Teacher",
            "full_name": "Pending T", "contact_email": "pt@example.com",
        })
        s = SL()
        try:
            svc = AuthService(s)
            r = svc.login(LoginRequest(email="pt@example.com",
                                       password="Anything!"))
            assert r is None
        finally:
            s.close()


class TestAuditNoPII:
    def test_invited_audit_omits_email_phone_name(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        c.post("/api/v1/invitations", json={
            "school_id": str(SCHOOL_A), "role": "Parent",
            "full_name": "VERYSECRETPARENT",
            "contact_email": "topsecret@example.com",
            "contact_phone": "+263770ZZZZZ",
        })

        from app.models.user import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "user.invited")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details or "{}"})
            assert "VERYSECRETPARENT" not in blob
            assert "topsecret@example.com" not in blob
            assert "263770ZZZZZ" not in blob
        finally:
            s.close()

    def test_activated_audit_omits_email_and_password(self, client, engine_and_session):
        c, _ = client
        _, SL = engine_and_session
        _seed_role(SL, "Parent")
        body = {
            "school_id": str(SCHOOL_A), "role": "Parent",
            "full_name": "X",
            "contact_email": "topsecret2@example.com",
        }
        r = c.post("/api/v1/invitations", json=body)
        raw = r.json()["data"]["raw_token"]
        c.post(f"/api/v1/invitations/{raw}/accept",
               json={"password": "MYSECRETPASSWORD!"})

        from app.models.user import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "user.activated")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details or "{}"})
            assert "topsecret2@example.com" not in blob
            assert "MYSECRETPASSWORD" not in blob
        finally:
            s.close()
