"""Phase 11f tests: HoD (T-017), CPD (T-018), self-eval (T-019), co-teacher (T-016)."""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_org.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
TEACHER_B = uuid.uuid4()
SUBJECT_A = uuid.uuid4()
TERM_A = uuid.uuid4()
YEAR_A = uuid.uuid4()
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


# ─── T-017 HoD ─────────────────────────────────────────────────────


class TestHoD:
    def test_grant_then_list(self, client):
        g = client.post(
            "/api/v1/hod-assignments",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"subject_id": str(SUBJECT_A), "user_id": str(TEACHER_A)},
        )
        assert g.status_code == 200, g.text
        l = client.get(
            f"/api/v1/hod-assignments?user_id={TEACHER_A}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert len(l.json()["data"]) == 1

    def test_grant_is_idempotent(self, client):
        g1 = client.post(
            "/api/v1/hod-assignments",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"subject_id": str(SUBJECT_A), "user_id": str(TEACHER_A)},
        )
        g2 = client.post(
            "/api/v1/hod-assignments",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"subject_id": str(SUBJECT_A), "user_id": str(TEACHER_A)},
        )
        assert g1.json()["data"]["id"] == g2.json()["data"]["id"]

    def test_revoke_then_re_grant_reactivates(self, client):
        g = client.post(
            "/api/v1/hod-assignments",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"subject_id": str(SUBJECT_A), "user_id": str(TEACHER_A)},
        )
        aid = g.json()["data"]["id"]
        client.delete(
            f"/api/v1/hod-assignments/{aid}",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
        )
        # Re-grant same tuple → same row reactivated.
        g2 = client.post(
            "/api/v1/hod-assignments",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"subject_id": str(SUBJECT_A), "user_id": str(TEACHER_A)},
        )
        assert g2.json()["data"]["id"] == aid
        assert g2.json()["data"]["revoked_at"] is None


# ─── T-018 CPD ─────────────────────────────────────────────────────


class TestCpd:
    def test_record_then_list(self, client):
        r = client.post(
            "/api/v1/cpd",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"category": "workshop",
                  "title": "Active learning techniques",
                  "completed_on": date.today().isoformat(),
                  "hours": 8},
        )
        assert r.status_code == 200, r.text
        l = client.get(
            "/api/v1/cpd",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["hours"] == 8.0

    def test_only_caller_records_listed_by_default(self, client):
        client.post(
            "/api/v1/cpd",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"title": "A", "completed_on": date.today().isoformat()},
        )
        client.post(
            "/api/v1/cpd",
            headers=_headers(TEACHER_B, "Teacher"),
            json={"title": "B", "completed_on": date.today().isoformat()},
        )
        # Teacher A only sees A's record.
        ra = client.get("/api/v1/cpd", headers=_headers(TEACHER_A, "Teacher"))
        titles = [x["title"] for x in ra.json()["data"]]
        assert titles == ["A"]

    def test_invalid_category_rejected(self, client):
        r = client.post(
            "/api/v1/cpd",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"category": "evil",
                  "title": "Bad", "completed_on": date.today().isoformat()},
        )
        assert r.status_code == 400


# ─── T-019 Self-evaluation ─────────────────────────────────────────


class TestSelfEval:
    def test_submit_then_list(self, client):
        r = client.post(
            "/api/v1/self-evaluations",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"term_id": str(TERM_A),
                  "responses": {"q1": 5, "q2": "Clear improvement"},
                  "overall_reflection": "Good term overall."},
        )
        assert r.status_code == 200, r.text
        l = client.get(
            f"/api/v1/self-evaluations?term_id={TERM_A}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["responses"]["q1"] == 5

    def test_submit_is_upsert(self, client):
        client.post(
            "/api/v1/self-evaluations",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"term_id": str(TERM_A),
                  "responses": {"q1": 1}},
        )
        client.post(
            "/api/v1/self-evaluations",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"term_id": str(TERM_A),
                  "responses": {"q1": 9}},
        )
        l = client.get(
            f"/api/v1/self-evaluations?term_id={TERM_A}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["responses"]["q1"] == 9

    def test_audit_does_not_log_response_values(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/self-evaluations",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"term_id": str(TERM_A),
                  "responses": {"sensitive_topic": "TOP SECRET ANSWER"}},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "self_eval.submitted")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOP SECRET ANSWER" not in blob
            # Question keys ARE logged (they're a structural signal).
            assert "sensitive_topic" in blob
        finally:
            s.close()


# ─── T-016 Co-teacher ──────────────────────────────────────────────


class TestCoTeacher:
    def test_assign_two_teachers_to_same_class(self, client):
        g1 = client.post(
            "/api/v1/class-teachers/co",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"class_id": str(CLASS_A),
                  "academic_year_id": str(YEAR_A),
                  "teacher_user_id": str(TEACHER_A)},
        )
        g2 = client.post(
            "/api/v1/class-teachers/co",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"class_id": str(CLASS_A),
                  "academic_year_id": str(YEAR_A),
                  "teacher_user_id": str(TEACHER_B)},
        )
        # Both should land — pre-Phase-11f the unique constraint
        # would have rejected the second.
        assert g1.status_code == 200
        assert g2.status_code == 200
        assert g1.json()["data"]["id"] != g2.json()["data"]["id"]

    def test_assign_same_teacher_twice_is_idempotent(self, client):
        g1 = client.post(
            "/api/v1/class-teachers/co",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"class_id": str(CLASS_A),
                  "academic_year_id": str(YEAR_A),
                  "teacher_user_id": str(TEACHER_A)},
        )
        g2 = client.post(
            "/api/v1/class-teachers/co",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
            json={"class_id": str(CLASS_A),
                  "academic_year_id": str(YEAR_A),
                  "teacher_user_id": str(TEACHER_A)},
        )
        assert g1.json()["data"]["id"] == g2.json()["data"]["id"]
        assert g2.json()["data"]["already_assigned"] is True
