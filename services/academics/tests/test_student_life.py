"""Phase 11e tests: incidents (T-004), substitute grants (T-006), homework (T-003)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_student_life.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
TEACHER_B = uuid.uuid4()
STUDENT_A = uuid.uuid4()
CLASS_A = uuid.uuid4()


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


def _headers(user_id, role, perms="authenticated"):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": role,
        "X-Permissions": perms,
    }


# ─── T-004 incidents ───────────────────────────────────────────────


class TestIncidents:
    def test_create_then_list(self, client):
        r = client.post(
            "/api/v1/incidents",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A),
                  "class_id": str(CLASS_A),
                  "summary": "Disrupted class",
                  "severity": "moderate",
                  "category": "disruption"},
        )
        assert r.status_code == 200, r.text
        l = client.get(
            f"/api/v1/incidents?student_id={STUDENT_A}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert l.status_code == 200
        assert len(l.json()["data"]) == 1

    def test_invalid_severity_rejected(self, client):
        r = client.post(
            "/api/v1/incidents",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A),
                  "summary": "x",
                  "severity": "apocalyptic"},
        )
        assert r.status_code == 400

    def test_update_marks_notified_and_resolved(self, client):
        cr = client.post(
            "/api/v1/incidents",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A),
                  "summary": "Cheating"},
        )
        iid = cr.json()["data"]["id"]
        now = datetime.now(timezone.utc).isoformat()
        u = client.put(
            f"/api/v1/incidents/{iid}",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"parent_notified_at": now,
                  "resolved_at": now,
                  "severity": "serious"},
        )
        assert u.status_code == 200
        assert u.json()["data"]["severity"] == "serious"
        assert u.json()["data"]["parent_notified_at"] is not None

    def test_audit_omits_summary_text(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/incidents",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A),
                  "summary": "SECRET DETAILS DO NOT LOG ME"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "incident.created")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "SECRET DETAILS DO NOT LOG ME" not in blob
        finally:
            s.close()


# ─── T-006 substitute grants ──────────────────────────────────────


class TestSubstituteGrants:
    def test_admin_grants_then_list_active(self, client):
        now = datetime.now(timezone.utc)
        g = client.post(
            "/api/v1/substitute-grants",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={
                "absent_teacher_user_id": str(TEACHER_A),
                "grantee_user_id": str(TEACHER_B),
                "starts_at": now.isoformat(),
                "ends_at": (now + timedelta(hours=8)).isoformat(),
                "reason": "Sick leave",
            },
        )
        assert g.status_code == 200, g.text
        l = client.get(
            f"/api/v1/substitute-grants?grantee_user_id={TEACHER_B}",
            headers=_headers(TEACHER_B, "Teacher"),
        )
        assert len(l.json()["data"]) == 1

    def test_invalid_window_rejected(self, client):
        now = datetime.now(timezone.utc)
        r = client.post(
            "/api/v1/substitute-grants",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={
                "absent_teacher_user_id": str(TEACHER_A),
                "grantee_user_id": str(TEACHER_B),
                "starts_at": now.isoformat(),
                "ends_at": (now - timedelta(hours=1)).isoformat(),
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_WINDOW"

    def test_self_grant_rejected(self, client):
        now = datetime.now(timezone.utc)
        r = client.post(
            "/api/v1/substitute-grants",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={
                "absent_teacher_user_id": str(TEACHER_A),
                "grantee_user_id": str(TEACHER_A),
                "starts_at": now.isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "SELF_GRANT"

    def test_revoke_excludes_from_active_list(self, client):
        now = datetime.now(timezone.utc)
        g = client.post(
            "/api/v1/substitute-grants",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={
                "absent_teacher_user_id": str(TEACHER_A),
                "grantee_user_id": str(TEACHER_B),
                "starts_at": now.isoformat(),
                "ends_at": (now + timedelta(hours=8)).isoformat(),
            },
        )
        gid = g.json()["data"]["id"]
        r = client.post(
            f"/api/v1/substitute-grants/{gid}/revoke",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
        )
        assert r.status_code == 200
        assert r.json()["data"]["revoked_at"] is not None

        l = client.get(
            f"/api/v1/substitute-grants?grantee_user_id={TEACHER_B}&active_only=true",
            headers=_headers(TEACHER_B, "Teacher"),
        )
        assert l.json()["data"] == []


# ─── T-003 homework ───────────────────────────────────────────────


class TestHomework:
    def test_assign_then_list(self, client):
        from datetime import date
        a = client.post(
            "/api/v1/homework",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"class_id": str(CLASS_A),
                  "title": "Read chapter 3",
                  "description": "Pages 50-65",
                  "due_date": date.today().isoformat()},
        )
        assert a.status_code == 200, a.text
        l = client.get(
            f"/api/v1/homework?class_id={CLASS_A}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert len(l.json()["data"]) == 1

    def test_submit_then_grade(self, client):
        from datetime import date
        a = client.post(
            "/api/v1/homework",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"class_id": str(CLASS_A),
                  "title": "T", "description": "D",
                  "due_date": date.today().isoformat()},
        )
        hid = a.json()["data"]["id"]
        s = client.post(
            f"/api/v1/homework/{hid}/submissions",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A),
                  "body": "My answer"},
        )
        sid = s.json()["data"]["id"]
        g = client.put(
            f"/api/v1/homework/submissions/{sid}/grade",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"grade_marks": "8/10",
                  "grade_remarks": "Solid effort"},
        )
        assert g.status_code == 200
        assert g.json()["data"]["grade_marks"] == "8/10"

    def test_submission_is_upserted(self, client):
        from datetime import date
        a = client.post(
            "/api/v1/homework",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"class_id": str(CLASS_A),
                  "title": "T", "description": "D",
                  "due_date": date.today().isoformat()},
        )
        hid = a.json()["data"]["id"]
        client.post(
            f"/api/v1/homework/{hid}/submissions",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A), "body": "v1"},
        )
        client.post(
            f"/api/v1/homework/{hid}/submissions",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"student_id": str(STUDENT_A), "body": "v2"},
        )
        l = client.get(
            f"/api/v1/homework/{hid}/submissions",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["body"] == "v2"
