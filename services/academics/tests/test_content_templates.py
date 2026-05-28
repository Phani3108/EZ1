"""Phase 16d — HomeworkTemplate + LessonPlanTemplate tests."""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_content_templates.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
# Phase 17a — template instantiation now calls communications to
# clone attachments. Short-circuit the cross-service call in tests so
# we don't depend on a running communications service.
os.environ["EDUZIM_DISABLE_CROSS_SERVICE_HTTP"] = "1"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
TEACHER_B = uuid.uuid4()


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


def _headers(role="Teacher", school_id=None, user_id=None, perms=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or TEACHER_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": role,
        "X-Permissions": perms or "school:manage",
    }


def _seed_subject(client):
    return client.post(
        "/api/v1/curriculum/subjects",
        headers=_headers(),
        json={"name": "Mathematics", "code": "MATH"},
    ).json()["data"]


class TestHomeworkTemplate:
    def test_create_and_list(self, client):
        s = _seed_subject(client)
        r = client.post(
            "/api/v1/homework-templates",
            headers=_headers(),
            json={
                "title": "Quadratics worksheet",
                "description": "Solve 10 quadratic equations by factorisation.",
                "subject_id": s["id"],
                "default_due_days": 7,
                "grade_levels": ["Form 3"],
            },
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["title"] == "Quadratics worksheet"
        assert d["default_due_days"] == 7
        assert d["is_published_school_wide"] is False
        # List shows the row.
        l = client.get("/api/v1/homework-templates", headers=_headers())
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == d["id"]

    def test_publish_school_wide_then_list_filter(self, client):
        s = _seed_subject(client)
        a = client.post(
            "/api/v1/homework-templates",
            headers=_headers(user_id=TEACHER_A),
            json={"title": "A", "description": "X", "subject_id": s["id"]},
        ).json()["data"]
        b = client.post(
            "/api/v1/homework-templates",
            headers=_headers(user_id=TEACHER_B),
            json={"title": "B", "description": "Y", "subject_id": s["id"]},
        ).json()["data"]
        # Publish only A.
        client.post(
            f"/api/v1/homework-templates/{a['id']}/publish-school-wide",
            headers=_headers(role="SchoolAdmin", user_id=ADMIN_A),
        )
        # published_only=true shows only A.
        l = client.get(
            "/api/v1/homework-templates?published_only=true",
            headers=_headers(),
        )
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == a["id"]
        # mine_only=true as teacher B shows only B.
        l = client.get(
            "/api/v1/homework-templates?mine_only=true",
            headers=_headers(user_id=TEACHER_B),
        )
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["id"] == b["id"]

    def test_instantiate_clones_into_homework(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        t = client.post(
            "/api/v1/homework-templates",
            headers=_headers(),
            json={
                "title": "Mid-term essay",
                "description": "Write 500 words on integers.",
                "subject_id": s["id"],
                "default_due_days": 14,
            },
        ).json()["data"]
        class_id = str(uuid.uuid4())
        inst = client.post(
            f"/api/v1/homework-templates/{t['id']}/instantiate",
            headers=_headers(),
            json={"class_id": class_id},
        )
        assert inst.status_code == 201, inst.text
        data = inst.json()["data"]
        # Verify Homework row exists with correct fields.
        from app.models.student_life import Homework
        ses = SL()
        try:
            hw = ses.query(Homework).filter(
                Homework.id == data["instance_id"]
            ).first()
            assert hw is not None
            assert hw.title == "Mid-term essay"
            assert hw.description.startswith("Write 500 words")
            assert hw.class_id == class_id
            assert hw.template_source_id == t["id"]
        finally:
            ses.close()

    def test_sync_from_template_updates_instance(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        t = client.post(
            "/api/v1/homework-templates",
            headers=_headers(),
            json={"title": "Original", "description": "Body v1",
                  "subject_id": s["id"]},
        ).json()["data"]
        class_id = str(uuid.uuid4())
        instance = client.post(
            f"/api/v1/homework-templates/{t['id']}/instantiate",
            headers=_headers(),
            json={"class_id": class_id},
        ).json()["data"]
        # Mutate the template via direct DB write (simulating a
        # maintainer edit).
        from app.models.content_templates import HomeworkTemplate
        from app.models.student_life import Homework
        ses = SL()
        try:
            row = ses.query(HomeworkTemplate).filter(
                HomeworkTemplate.id == t["id"]).first()
            row.title = "Updated"
            row.description = "Body v2"
            ses.commit()
        finally:
            ses.close()
        # Sync — instance reflects the new title.
        r = client.post(
            f"/api/v1/homework/{instance['instance_id']}/sync-from-template",
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
        ses = SL()
        try:
            hw = ses.query(Homework).filter(
                Homework.id == instance["instance_id"]).first()
            assert hw.title == "Updated"
            assert hw.description == "Body v2"
        finally:
            ses.close()

    def test_sync_rejected_when_no_template_source(self, client, engine_and_session):
        _, SL = engine_and_session
        # Create a homework directly (no template_source_id).
        from app.models.student_life import Homework
        ses = SL()
        try:
            hw = Homework(
                id=str(uuid.uuid4()),
                school_id=str(SCHOOL_A),
                class_id=str(uuid.uuid4()),
                title="Standalone",
                description="No template",
                due_date=date.today(),
                assigned_by=str(uuid.uuid4()),
            )
            ses.add(hw)
            ses.commit()
            hw_id = hw.id
        finally:
            ses.close()
        r = client.post(
            f"/api/v1/homework/{hw_id}/sync-from-template",
            headers=_headers(),
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_TEMPLATE_SOURCE"


class TestTeacherCanInstantiateButNotPublishSchoolWide:
    """Phase 19a — fixes Critical C2.

    Before: the gateway's broad `("POST", "/api/v1/homework-templates/",
    "school:manage")` blocked any teacher without school:manage from
    hitting `/{id}/instantiate` — the very flow built for them. After:
    the gateway prefix is `authenticated`; only `publish-school-wide`
    is gated, and that gate is now enforced server-side too."""

    def test_teacher_without_school_manage_can_instantiate(self, client):
        s = _seed_subject(client)
        # Admin creates + publishes a template (admin has school:manage).
        t = client.post(
            "/api/v1/homework-templates",
            headers=_headers(role="SchoolAdmin", user_id=ADMIN_A),
            json={"title": "Shared HW", "description": "Body",
                  "subject_id": s["id"]},
        ).json()["data"]
        # Teacher with NO school:manage perm should be able to instantiate.
        teacher_headers = _headers(
            role="Teacher", user_id=TEACHER_A,
            perms="attendance:write,assessment:write",  # no school:manage
        )
        r = client.post(
            f"/api/v1/homework-templates/{t['id']}/instantiate",
            headers=teacher_headers,
            json={"class_id": str(uuid.uuid4()), "due_date": "2026-09-01"},
        )
        assert r.status_code == 201, r.text

    def test_teacher_without_school_manage_cannot_publish_school_wide(self, client):
        s = _seed_subject(client)
        t = client.post(
            "/api/v1/homework-templates",
            headers=_headers(user_id=TEACHER_A),
            json={"title": "T's HW", "description": "Body",
                  "subject_id": s["id"]},
        ).json()["data"]
        teacher_headers = _headers(
            role="Teacher", user_id=TEACHER_A,
            perms="attendance:write,assessment:write",
        )
        r = client.post(
            f"/api/v1/homework-templates/{t['id']}/publish-school-wide",
            headers=teacher_headers,
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "INSUFFICIENT_PERMISSION"

    def test_lesson_plan_template_same_gate(self, client):
        s = _seed_subject(client)
        t = client.post(
            "/api/v1/lesson-plan-templates",
            headers=_headers(user_id=TEACHER_A),
            json={"title": "LP", "objectives": "x",
                  "subject_id": s["id"]},
        ).json()["data"]
        teacher_headers = _headers(
            role="Teacher", user_id=TEACHER_A,
            perms="attendance:write",
        )
        # Instantiate works.
        ok = client.post(
            f"/api/v1/lesson-plan-templates/{t['id']}/instantiate",
            headers=teacher_headers,
            json={"class_id": str(uuid.uuid4())},
        )
        assert ok.status_code == 201, ok.text
        # publish-school-wide blocked.
        blocked = client.post(
            f"/api/v1/lesson-plan-templates/{t['id']}/publish-school-wide",
            headers=teacher_headers,
        )
        assert blocked.status_code == 403


class TestTenantIsolation:
    def test_other_school_cannot_see_my_template(self, client):
        s = _seed_subject(client)
        client.post(
            "/api/v1/homework-templates",
            headers=_headers(school_id=SCHOOL_A),
            json={"title": "School A template", "description": "X",
                  "subject_id": s["id"]},
        )
        l = client.get(
            "/api/v1/homework-templates",
            headers=_headers(school_id=SCHOOL_B),
        )
        assert l.json()["data"] == []


class TestLessonPlanTemplate:
    def test_create_then_instantiate(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        t = client.post(
            "/api/v1/lesson-plan-templates",
            headers=_headers(),
            json={
                "title": "Intro to Quadratics",
                "objectives": "Recognise quadratic patterns.",
                "activities": "Discussion + 3 practice problems.",
                "resources": "Textbook chapter 4.",
                "subject_id": s["id"],
                "suggested_period_number": 1,
            },
        )
        assert t.status_code == 201, t.text
        tdata = t.json()["data"]

        class_id = str(uuid.uuid4())
        inst = client.post(
            f"/api/v1/lesson-plan-templates/{tdata['id']}/instantiate",
            headers=_headers(),
            json={"class_id": class_id, "scheduled_date": "2026-09-01"},
        )
        assert inst.status_code == 201, inst.text

        from app.models.planning import LessonPlan
        ses = SL()
        try:
            lp = ses.query(LessonPlan).filter(
                LessonPlan.id == inst.json()["data"]["instance_id"]
            ).first()
            assert lp is not None
            assert lp.title == "Intro to Quadratics"
            assert lp.objectives.startswith("Recognise")
            assert lp.template_id == tdata["id"]
            assert lp.scheduled_period_number == 1
        finally:
            ses.close()


class TestAuditNoPII:
    def test_template_created_audit_omits_body(self, client, engine_and_session):
        _, SL = engine_and_session
        s = _seed_subject(client)
        client.post(
            "/api/v1/homework-templates",
            headers=_headers(),
            json={
                "title": "SECRETTEMPLATETITLE_42",
                "description": "VERYSECRETBODYTEXT_99",
                "subject_id": s["id"],
            },
        )
        from app.models.audit import AuditLog
        ses = SL()
        try:
            row = (
                ses.query(AuditLog)
                .filter(AuditLog.event_type == "template.created")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            # Title + body NOT in details.
            assert "SECRETTEMPLATETITLE_42" not in blob
            assert "VERYSECRETBODYTEXT_99" not in blob
            # Type IS in details.
            assert "homework" in blob
        finally:
            ses.close()
