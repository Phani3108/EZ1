"""Planning tests (Phase 11d): periods, lesson plans, formatives, seat plans."""
from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_planning.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
CLASS_A = uuid.uuid4()
SUBJECT_A = uuid.uuid4()
ASSESS_A = uuid.uuid4()
STUDENT_A = uuid.uuid4()


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


def _admin_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage",
    }


def _teacher_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(TEACHER_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Teacher",
        "X-Permissions": "authenticated",
    }


# ─── T-010 periods ─────────────────────────────────────────────────


class TestPeriods:
    def test_create_then_list(self, client):
        r = client.post(
            "/api/v1/periods",
            headers=_admin_headers(),
            json={
                "period_number": 1, "name": "Period 1",
                "start_time": "08:00:00", "end_time": "08:45:00",
            },
        )
        assert r.status_code == 200, r.text
        l = client.get("/api/v1/periods", headers=_teacher_headers())
        assert l.status_code == 200
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["period_number"] == 1


# ─── T-005 lesson plans ────────────────────────────────────────────


class TestLessonPlans:
    def test_create_template_and_instance(self, client):
        # Template (no class_id)
        t = client.post(
            "/api/v1/lesson-plans",
            headers=_teacher_headers(),
            json={"title": "Algebra basics template",
                  "objectives": "Cover quadratics"},
        )
        assert t.status_code == 200
        tid = t.json()["data"]["id"]
        assert t.json()["data"]["is_template"] is True

        # Instance pointing back to template
        i = client.post(
            "/api/v1/lesson-plans",
            headers=_teacher_headers(),
            json={"title": "Algebra Mon",
                  "class_id": str(CLASS_A),
                  "template_id": tid,
                  "scheduled_period_number": 2},
        )
        assert i.status_code == 200
        assert i.json()["data"]["is_template"] is False
        assert i.json()["data"]["template_id"] == tid

    def test_templates_only_filter(self, client):
        client.post(
            "/api/v1/lesson-plans",
            headers=_teacher_headers(),
            json={"title": "Template"},
        )
        client.post(
            "/api/v1/lesson-plans",
            headers=_teacher_headers(),
            json={"title": "Instance", "class_id": str(CLASS_A)},
        )
        r = client.get(
            "/api/v1/lesson-plans?templates_only=true",
            headers=_teacher_headers(),
        )
        rows = r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["is_template"] is True

    def test_update_changes_fields(self, client):
        cr = client.post(
            "/api/v1/lesson-plans",
            headers=_teacher_headers(),
            json={"title": "Original"},
        )
        lid = cr.json()["data"]["id"]
        u = client.put(
            f"/api/v1/lesson-plans/{lid}",
            headers=_teacher_headers(),
            json={"title": "Revised", "objectives": "New goal"},
        )
        assert u.status_code == 200
        assert u.json()["data"]["title"] == "Revised"
        assert u.json()["data"]["objectives"] == "New goal"


# ─── T-013 formative assessments ───────────────────────────────────


class TestFormative:
    def test_create_and_respond(self, client):
        cr = client.post(
            "/api/v1/formative-assessments",
            headers=_teacher_headers(),
            json={
                "class_id": str(CLASS_A),
                "title": "Did you understand?",
                "formative_kind": "exit_ticket",
                "prompt": "What was confusing today?",
            },
        )
        assert cr.status_code == 200, cr.text
        fid = cr.json()["data"]["id"]

        rr = client.post(
            f"/api/v1/formative-assessments/{fid}/responses",
            headers=_teacher_headers(),
            json={"student_id": str(STUDENT_A),
                  "response_text": "The proof step"},
        )
        assert rr.status_code == 200

        # List shows response_count = 1
        l = client.get(
            f"/api/v1/formative-assessments?class_id={CLASS_A}",
            headers=_teacher_headers(),
        )
        assert l.json()["data"][0]["response_count"] == 1

    def test_student_response_upsert(self, client):
        cr = client.post(
            "/api/v1/formative-assessments",
            headers=_teacher_headers(),
            json={"class_id": str(CLASS_A), "title": "P",
                  "formative_kind": "poll", "prompt": "Q?",
                  "payload": {"options": ["A", "B"]}},
        )
        fid = cr.json()["data"]["id"]
        # Same student responds twice — should upsert, not duplicate
        client.post(
            f"/api/v1/formative-assessments/{fid}/responses",
            headers=_teacher_headers(),
            json={"student_id": str(STUDENT_A), "response_text": "A"},
        )
        client.post(
            f"/api/v1/formative-assessments/{fid}/responses",
            headers=_teacher_headers(),
            json={"student_id": str(STUDENT_A), "response_text": "B"},
        )
        l = client.get(
            f"/api/v1/formative-assessments?class_id={CLASS_A}",
            headers=_teacher_headers(),
        )
        assert l.json()["data"][0]["response_count"] == 1

    def test_invalid_kind_rejected(self, client):
        # FastAPI's Pydantic regex catches this at validation → 422.
        r = client.post(
            "/api/v1/formative-assessments",
            headers=_teacher_headers(),
            json={"class_id": str(CLASS_A), "title": "X",
                  "formative_kind": "bogus", "prompt": "Q"},
        )
        assert r.status_code in (400, 422)


# ─── T-012 exam seat plans ─────────────────────────────────────────


class TestSeatPlans:
    def test_create_and_list(self, client):
        cr = client.post(
            "/api/v1/exam-seat-plans",
            headers=_admin_headers(),
            json={
                "assessment_id": str(ASSESS_A),
                "room": "Hall A",
                "layout": [
                    [str(STUDENT_A), None],
                    [None, None],
                ],
                "notes": "Front row reserved for late arrivals",
            },
        )
        assert cr.status_code == 200, cr.text
        body = cr.json()["data"]
        assert body["room"] == "Hall A"
        assert body["layout"][0][0] == str(STUDENT_A)

        l = client.get(
            f"/api/v1/exam-seat-plans?assessment_id={ASSESS_A}",
            headers=_teacher_headers(),
        )
        assert l.json()["data"][0]["room"] == "Hall A"
