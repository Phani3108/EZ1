"""Phase 12a / PH12-1 — Student↔User linkage tests."""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_user_link.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
STUDENT_USER_A = uuid.uuid4()
STUDENT_USER_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa
    from app.models import audit as _au  # noqa
    from app.models import comment_bank as _cb  # noqa
    from app.models import planning as _p  # noqa
    from app.models import student_life as _sl  # noqa
    from app.models import org as _o  # noqa

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
    from app.main import app

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _admin_headers(user_id=ADMIN_A, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "student:write",
    }


def _student_headers(user_id, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Student",
        "X-Permissions": "authenticated",
    }


def _create_student(client) -> str:
    r = client.post(
        "/api/v1/students",
        headers=_admin_headers(),
        json={
            "student_code": "S001",
            "first_name": "Alice",
            "last_name": "Smith",
            "dob": "2012-05-15",
            "gender": "FEMALE",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


class TestLink:
    def test_link_admin_assigns_user(self, client):
        sid = _create_student(client)
        r = client.post(
            f"/api/v1/students/{sid}/link-user",
            headers=_admin_headers(),
            json={"user_id": str(STUDENT_USER_A)},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["user_id"] == str(STUDENT_USER_A)

    def test_relink_different_user_rejected(self, client):
        sid = _create_student(client)
        client.post(
            f"/api/v1/students/{sid}/link-user",
            headers=_admin_headers(),
            json={"user_id": str(STUDENT_USER_A)},
        )
        # Same user re-link is fine (idempotent).
        r2 = client.post(
            f"/api/v1/students/{sid}/link-user",
            headers=_admin_headers(),
            json={"user_id": str(STUDENT_USER_A)},
        )
        assert r2.status_code == 200
        # Different user is rejected.
        r3 = client.post(
            f"/api/v1/students/{sid}/link-user",
            headers=_admin_headers(),
            json={"user_id": str(STUDENT_USER_B)},
        )
        assert r3.status_code == 409
        assert r3.json()["error"]["code"] == "ALREADY_LINKED"


class TestStudentSelfService:
    def test_me_resolves_via_link(self, client):
        sid = _create_student(client)
        client.post(
            f"/api/v1/students/{sid}/link-user",
            headers=_admin_headers(),
            json={"user_id": str(STUDENT_USER_A)},
        )
        # Student logs in with their own user_id → /students/me
        r = client.get(
            "/api/v1/students/me",
            headers=_student_headers(STUDENT_USER_A),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["id"] == sid
        assert r.json()["data"]["first_name"] == "Alice"

    def test_me_404_when_unlinked(self, client):
        # A user with no Student.user_id linkage → 404
        r = client.get(
            "/api/v1/students/me",
            headers=_student_headers(uuid.uuid4()),
        )
        assert r.status_code == 404
