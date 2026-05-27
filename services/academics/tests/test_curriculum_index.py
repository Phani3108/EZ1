"""Phase 16b — Topic↔Resource cross-index tests."""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date, datetime, timezone

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_curriculum_index.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    import app.models  # noqa
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


def _admin_headers(school_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


def _seed_subject_unit_topic(client, SessionLocal):
    """Create a subject + unit + topic via the API and return their IDs."""
    s = client.post(
        "/api/v1/curriculum/subjects",
        headers=_admin_headers(),
        json={"name": "Maths", "code": "MATH"},
    ).json()["data"]
    u = client.post(
        "/api/v1/curriculum/units",
        headers=_admin_headers(),
        json={"subject_id": s["id"], "name": "Algebra", "code": "U-ALG"},
    ).json()["data"]
    t = client.post(
        "/api/v1/curriculum/topics",
        headers=_admin_headers(),
        json={"unit_id": u["id"], "name": "Quadratics", "code": "T-QUAD"},
    ).json()["data"]
    return s["id"], u["id"], t["id"]


def _seed_lesson_plan(SessionLocal, school_id: uuid.UUID, subject_id: str,
                      class_id: uuid.UUID, title="Lesson 1") -> str:
    """Insert a LessonPlan row directly. Existing create endpoint is
    intentionally not exercised here — we test the tag endpoint
    against a pre-existing row."""
    from app.models.planning import LessonPlan
    s = SessionLocal()
    try:
        lp = LessonPlan(
            id=str(uuid.uuid4()),
            school_id=str(school_id),
            title=title,
            subject_id=subject_id,
            class_id=str(class_id),
            created_by=str(uuid.uuid4()),
        )
        s.add(lp)
        s.commit()
        return str(lp.id)
    finally:
        s.close()


def _seed_homework(SessionLocal, school_id: uuid.UUID, subject_id: str,
                   class_id: uuid.UUID, title="HW 1") -> str:
    from app.models.student_life import Homework
    s = SessionLocal()
    try:
        hw = Homework(
            id=str(uuid.uuid4()),
            school_id=str(school_id),
            class_id=str(class_id),
            subject_id=subject_id,
            title=title,
            description="Body",
            due_date=date.today(),
            assigned_by=str(uuid.uuid4()),
        )
        s.add(hw)
        s.commit()
        return str(hw.id)
    finally:
        s.close()


def _seed_assessment(SessionLocal, school_id: uuid.UUID, subject_id: str,
                     class_id: uuid.UUID, name="Test 1") -> str:
    from app.models.assessment import Assessment
    s = SessionLocal()
    try:
        a = Assessment(
            id=str(uuid.uuid4()),
            school_id=str(school_id),
            academic_year_id=str(uuid.uuid4()),
            term_id=str(uuid.uuid4()),
            class_id=str(class_id),
            subject_id=subject_id,
            name=name,
            assessment_type="TEST",
            date=date.today(),
            max_marks=100,
            created_by=str(uuid.uuid4()),
        )
        s.add(a)
        s.commit()
        return str(a.id)
    finally:
        s.close()


class TestTagAndFetch:
    def test_tag_homework_and_query_topic_resources(self, client, engine_and_session):
        _, SL = engine_and_session
        subj_id, _u_id, topic_id = _seed_subject_unit_topic(client, SL)
        hw_id = _seed_homework(SL, SCHOOL_A, subj_id, uuid.uuid4())

        # Tag.
        r = client.post(
            "/api/v1/curriculum/tag",
            headers=_admin_headers(),
            json={"resource_type": "homework",
                  "resource_id": hw_id,
                  "topic_ids": [topic_id]},
        )
        assert r.status_code == 200, r.text

        # Fetch — homework is in the resource list.
        r2 = client.get(
            f"/api/v1/curriculum/topics/{topic_id}/resources",
            headers=_admin_headers(),
        )
        data = r2.json()["data"]
        assert len(data["homeworks"]) == 1
        assert data["homeworks"][0]["id"] == hw_id
        assert data["counts"]["homeworks"] == 1

    def test_tag_multiple_resource_types(self, client, engine_and_session):
        _, SL = engine_and_session
        subj_id, _u_id, topic_id = _seed_subject_unit_topic(client, SL)
        lp_id = _seed_lesson_plan(SL, SCHOOL_A, subj_id, uuid.uuid4())
        hw_id = _seed_homework(SL, SCHOOL_A, subj_id, uuid.uuid4())
        asmt_id = _seed_assessment(SL, SCHOOL_A, subj_id, uuid.uuid4())

        for rtype, rid in (
            ("lesson_plan", lp_id),
            ("homework", hw_id),
            ("assessment", asmt_id),
        ):
            r = client.post(
                "/api/v1/curriculum/tag",
                headers=_admin_headers(),
                json={"resource_type": rtype,
                      "resource_id": rid,
                      "topic_ids": [topic_id]},
            )
            assert r.status_code == 200, r.text

        r2 = client.get(
            f"/api/v1/curriculum/topics/{topic_id}/resources",
            headers=_admin_headers(),
        )
        data = r2.json()["data"]
        assert data["counts"] == {
            "lesson_plans": 1, "homeworks": 1,
            "assessments": 1, "formative_assessments": 0,
        }

    def test_tag_rejects_topic_from_other_school(self, client, engine_and_session):
        _, SL = engine_and_session
        # Topic created in school A.
        _, _, topic_id = _seed_subject_unit_topic(client, SL)
        # Homework created in school B.
        # Need a separate subject in school B.
        s_b = client.post(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(school_id=SCHOOL_B),
            json={"name": "M", "code": "MATH"},
        ).json()["data"]
        hw_id = _seed_homework(SL, SCHOOL_B, s_b["id"], uuid.uuid4())
        # School B admin tries to tag with school A's topic — rejected.
        r = client.post(
            "/api/v1/curriculum/tag",
            headers=_admin_headers(school_id=SCHOOL_B),
            json={"resource_type": "homework",
                  "resource_id": hw_id,
                  "topic_ids": [topic_id]},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_TOPICS"

    def test_tag_unknown_resource_rejected(self, client):
        r = client.post(
            "/api/v1/curriculum/tag",
            headers=_admin_headers(),
            json={"resource_type": "homework",
                  "resource_id": str(uuid.uuid4()),
                  "topic_ids": []},
        )
        assert r.status_code == 404


class TestCoverage:
    def test_coverage_per_topic_counts(self, client, engine_and_session):
        _, SL = engine_and_session
        subj_id, _u_id, topic_id = _seed_subject_unit_topic(client, SL)
        # Second topic, no tagged resources — should show 0 across the board.
        u_id = client.post(
            "/api/v1/curriculum/units",
            headers=_admin_headers(),
            json={"subject_id": subj_id, "name": "Geometry", "code": "U-GEO"},
        ).json()["data"]["id"]
        empty_topic_id = client.post(
            "/api/v1/curriculum/topics",
            headers=_admin_headers(),
            json={"unit_id": u_id, "name": "Circles", "code": "T-CIRC"},
        ).json()["data"]["id"]

        # Tag two homeworks against the first topic.
        for _ in range(2):
            hw_id = _seed_homework(SL, SCHOOL_A, subj_id, uuid.uuid4())
            client.post(
                "/api/v1/curriculum/tag",
                headers=_admin_headers(),
                json={"resource_type": "homework",
                      "resource_id": hw_id,
                      "topic_ids": [topic_id]},
            )

        r = client.get(
            f"/api/v1/curriculum/coverage?subject_id={subj_id}",
            headers=_admin_headers(),
        )
        data = r.json()["data"]
        assert len(data["topics"]) == 2
        by_id = {t["topic_id"]: t for t in data["topics"]}
        assert by_id[topic_id]["homeworks"] == 2
        assert by_id[topic_id]["total"] == 2
        assert by_id[empty_topic_id]["total"] == 0
        assert data["uncovered_count"] == 1
