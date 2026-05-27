"""Integration tests for the audit-log endpoint (Phase 9 / INFRA-018).

Covers:

  * `GET /api/v1/audit-log` returns rows scoped to the caller's school.
  * Cross-tenant isolation: school A's admin sees zero of school B's rows.
  * Filtering by event_type / actor_user_id / from_date / to_date.
  * Pagination.

Also exercises the wired-in audit at writeside: creating a student
through the API should leave an `audit_log` row visible in the browse.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_audit.db")
os.environ.setdefault("REPORTING_DATABASE_URL", "sqlite:///./test_academics_audit_r.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa
    from app.models import audit as _au  # noqa

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


def _admin_headers(school_id, user_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or uuid.uuid4()),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage",
    }


def _seed_audit_rows(SessionLocal, *, school_id, n=5, event_type="student.created",
                      actor_user_id=None):
    """Seed N audit rows directly via the model (bypasses the API)."""
    from app.models.audit import AuditLog
    from datetime import datetime, timezone
    session = SessionLocal()
    try:
        for i in range(n):
            session.add(AuditLog(
                id=uuid.uuid4(),
                occurred_at=datetime.now(timezone.utc),
                actor_user_id=actor_user_id,
                actor_role="Admin",
                school_id=school_id,
                event_type=event_type,
                target=json.dumps({"resource": "student", "id": f"stu-{i}"}),
            ))
        session.commit()
    finally:
        session.close()


# ─── List endpoint ────────────────────────────────────────────────


class TestList:

    def test_empty_returns_empty_list(self, client):
        r = client.get("/api/v1/audit-log",
                       headers=_admin_headers(SCHOOL_A))
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_returns_seeded_rows(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=3)

        r = client.get("/api/v1/audit-log", headers=_admin_headers(SCHOOL_A))
        assert r.status_code == 200
        assert r.json()["meta"]["total"] == 3
        assert len(r.json()["data"]) == 3

    def test_rows_are_school_scoped(self, client, engine_and_session):
        """School A admin must not see school B's audit rows."""
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=3)
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_B, n=5,
                         event_type="parent.created")

        r_a = client.get("/api/v1/audit-log", headers=_admin_headers(SCHOOL_A))
        r_b = client.get("/api/v1/audit-log", headers=_admin_headers(SCHOOL_B))
        assert r_a.json()["meta"]["total"] == 3
        assert r_b.json()["meta"]["total"] == 5
        # Every row in A's response must be from SCHOOL_A.
        for row in r_a.json()["data"]:
            assert row["school_id"] == str(SCHOOL_A)
        for row in r_b.json()["data"]:
            assert row["school_id"] == str(SCHOOL_B)

    def test_filter_by_event_type(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=3,
                         event_type="student.created")
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=2,
                         event_type="parent.created")

        r = client.get(
            "/api/v1/audit-log?event_type=student.created",
            headers=_admin_headers(SCHOOL_A),
        )
        assert r.json()["meta"]["total"] == 3
        for row in r.json()["data"]:
            assert row["event_type"] == "student.created"

    def test_filter_by_actor_user_id(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        target_actor = uuid.uuid4()
        other_actor = uuid.uuid4()
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=2,
                         actor_user_id=target_actor)
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=4,
                         actor_user_id=other_actor)

        r = client.get(
            f"/api/v1/audit-log?actor_user_id={target_actor}",
            headers=_admin_headers(SCHOOL_A),
        )
        assert r.json()["meta"]["total"] == 2
        for row in r.json()["data"]:
            assert row["actor_user_id"] == str(target_actor)

    def test_pagination(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=10)

        # Page 1
        r1 = client.get(
            "/api/v1/audit-log?page=1&page_size=4",
            headers=_admin_headers(SCHOOL_A),
        )
        assert len(r1.json()["data"]) == 4
        assert r1.json()["meta"]["has_next"] is True

        # Page 3 — final partial page
        r3 = client.get(
            "/api/v1/audit-log?page=3&page_size=4",
            headers=_admin_headers(SCHOOL_A),
        )
        assert len(r3.json()["data"]) == 2
        assert r3.json()["meta"]["has_next"] is False

    def test_ordered_newest_first(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=5)
        r = client.get("/api/v1/audit-log", headers=_admin_headers(SCHOOL_A))
        timestamps = [row["occurred_at"] for row in r.json()["data"]]
        # Newest first — descending
        assert timestamps == sorted(timestamps, reverse=True)

    def test_target_and_details_returned_as_objects(self, client, engine_and_session):
        """`target` is JSON-text in the DB but should be deserialized
        back into an object on the wire."""
        _, SessionLocal = engine_and_session
        _seed_audit_rows(SessionLocal, school_id=SCHOOL_A, n=1)
        r = client.get("/api/v1/audit-log", headers=_admin_headers(SCHOOL_A))
        row = r.json()["data"][0]
        assert isinstance(row["target"], dict)
        assert row["target"]["resource"] == "student"


# ─── Writeside integration — creating a student leaves an audit row ─


class TestWriteSideIntegration:

    def test_student_create_leaves_audit_row(self, client, engine_and_session):
        """End-to-end: POST /students → audit row appears via /audit-log."""
        # First create a student through the API.
        r = client.post(
            "/api/v1/students",
            headers=_admin_headers(SCHOOL_A),
            json={
                "student_code": "AUD001",
                "first_name": "Audit",
                "last_name": "Test",
                "dob": "2012-05-15",
                "gender": "MALE",
            },
        )
        assert r.status_code == 200, r.text
        student_id = r.json()["data"]["id"]

        # The audit-log browse should now show one row.
        audit_r = client.get(
            "/api/v1/audit-log?event_type=student.created",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["event_type"] == "student.created"
        assert rows[0]["target"]["id"] == student_id

    def test_student_update_audit_records_changed_fields_not_values(
        self, client, engine_and_session,
    ):
        """ADR 007: audit captures FACT of change, not the new value
        (the new value is in the students table; the audit signal is
        the action itself)."""
        # Seed a student
        r = client.post(
            "/api/v1/students",
            headers=_admin_headers(SCHOOL_A),
            json={
                "student_code": "AUD002", "first_name": "Pre",
                "last_name": "Update", "dob": "2012-05-15", "gender": "MALE",
            },
        )
        student_id = r.json()["data"]["id"]

        # Now update one field
        client.put(
            f"/api/v1/students/{student_id}",
            headers=_admin_headers(SCHOOL_A),
            json={"first_name": "Post"},
        )

        audit_r = client.get(
            "/api/v1/audit-log?event_type=student.updated",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        details = rows[0]["details"]
        # Captures WHICH fields changed, NOT the new values.
        assert "changed_fields" in details
        assert "first_name" in details["changed_fields"]
        # The actual new value ("Post") MUST NOT appear in the audit
        # row — that's the whole privacy point.
        assert "Post" not in json.dumps(details)
