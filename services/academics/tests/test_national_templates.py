"""Phase 18b — cross-school Ministry-distributed template tests.

Covers:
  * Ministry create + publish + archive lifecycle.
  * School-side browse (published-only filter, adopted_local_template_id
    enrichment).
  * Adopt path (idempotency, subject + topic resolution, unresolved
    codes reported).
  * Audit invariants — no template title, no body, no topic names.
  * Tenant scope — school A's adopted copy is invisible to school B.
"""
from __future__ import annotations

import json as _json
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_natpl.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
ADMIN_B = uuid.uuid4()
OPS = uuid.uuid4()


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


def _admin_headers(school_id, user_id):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


def _ops_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(OPS),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "EduZimOps",
        "X-Permissions": "school:create",
    }


def _adopt_subject(client, code: str, name: str, headers):
    """Helper — Ministry creates a national subject, publishes it,
    then school adopts. Returns the local school-side Subject id."""
    nat = client.post(
        "/api/v1/ministry/national-curriculum/subjects",
        headers=_ops_headers(),
        json={"code": code, "name": name},
    ).json()["data"]
    u1 = client.post(
        "/api/v1/ministry/national-curriculum/units",
        headers=_ops_headers(),
        json={"national_subject_id": nat["id"], "name": "Unit 1",
              "code": "U-1", "sequence_order": 1, "grade_level": "Form 1"},
    ).json()["data"]
    client.post(
        "/api/v1/ministry/national-curriculum/topics",
        headers=_ops_headers(),
        json={"national_unit_id": u1["id"], "name": "Topic 1",
              "code": "T-1", "sequence_order": 1},
    )
    client.post(
        "/api/v1/ministry/national-curriculum/topics",
        headers=_ops_headers(),
        json={"national_unit_id": u1["id"], "name": "Topic 2",
              "code": "T-2", "sequence_order": 2},
    )
    client.post(
        f"/api/v1/ministry/national-curriculum/subjects/{nat['id']}/publish",
        headers=_ops_headers(),
    )
    client.post(
        "/api/v1/curriculum/adopt-subject",
        headers=headers,
        json={"national_subject_id": nat["id"]},
    )


class TestNationalHomeworkLifecycle:
    def test_create_publish_archive(self, client):
        r = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-001", "title": "Algebra warm-up",
                  "description": "Solve 5 quadratics.",
                  "subject_code": "MATH-F1",
                  "topic_codes": ["T-1", "T-2"],
                  "grade_levels": ["Form 1"],
                  "default_due_days": 7},
        )
        assert r.status_code == 201, r.text
        tid = r.json()["data"]["id"]
        assert r.json()["data"]["published_at"] is None

        pub = client.post(
            f"/api/v1/ministry/national-templates/homework/{tid}/publish",
            headers=_ops_headers(),
        )
        assert pub.json()["data"]["published_at"] is not None

        # Listing shows it.
        lst = client.get(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
        ).json()["data"]
        assert any(t["id"] == tid for t in lst)

        # Archive prevents further publish, but list keeps the row when
        # include_archived=true.
        arch = client.post(
            f"/api/v1/ministry/national-templates/homework/{tid}/archive",
            headers=_ops_headers(),
        )
        assert arch.json()["data"]["archived_at"] is not None

        active = client.get(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
        ).json()["data"]
        assert all(t["id"] != tid for t in active)

    def test_duplicate_code_rejected(self, client):
        client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-DUP", "title": "x", "description": "x"},
        )
        r2 = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-DUP", "title": "y", "description": "y"},
        )
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_CODE"


class TestSchoolBrowse:
    def test_browse_shows_only_published_unarchived(self, client):
        # Two templates: one published, one draft.
        pub_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-PUB", "title": "x", "description": "x"},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{pub_id}/publish",
            headers=_ops_headers(),
        )
        client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-DRAFT", "title": "x", "description": "x"},
        )
        rows = client.get(
            "/api/v1/national-templates/homework",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        codes = {r["code"] for r in rows}
        assert "HW-PUB" in codes
        assert "HW-DRAFT" not in codes


class TestAdopt:
    def test_adopt_clones_template_and_resolves_topics(self, client, engine_and_session):
        _, SL = engine_and_session
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))

        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-X", "title": "Algebra warm-up",
                  "description": "Solve five quadratics.",
                  "subject_code": "MATH-F1",
                  "topic_codes": ["T-1", "T-2", "T-MISSING"],
                  "grade_levels": ["Form 1"],
                  "default_due_days": 7},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{nat_id}/publish",
            headers=_ops_headers(),
        )

        r = client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["idempotent"] is False
        assert d["topics_resolved"] == 2
        assert d["topics_unresolved"] == 1
        assert "T-MISSING" in d["unresolved_topic_codes"]
        assert d["subject_resolved"] is True
        local_id = d["local_template_id"]

        # The local template now shows up in the school's HomeworkTemplate
        # listing.
        listed = client.get(
            "/api/v1/homework-templates",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        assert any(t["id"] == local_id for t in listed)

    def test_adopt_is_idempotent(self, client):
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))
        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-Y", "title": "x", "description": "x",
                  "subject_code": "MATH-F1", "topic_codes": ["T-1"]},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{nat_id}/publish",
            headers=_ops_headers(),
        )

        r1 = client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        r2 = client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        assert r1["local_template_id"] == r2["local_template_id"]
        assert r2["idempotent"] is True

    def test_adopt_rejects_unpublished(self, client):
        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-NOPUB", "title": "x", "description": "x"},
        ).json()["data"]["id"]
        r = client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NOT_ADOPTABLE"

    def test_browse_enriches_with_adopted_local_id(self, client):
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))
        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-E", "title": "x", "description": "x",
                  "subject_code": "MATH-F1"},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{nat_id}/publish",
            headers=_ops_headers(),
        )

        # Before adopt — adopted_local_template_id is null.
        before = client.get(
            "/api/v1/national-templates/homework",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        row = next(r for r in before if r["id"] == nat_id)
        assert row["adopted_local_template_id"] is None

        adopted = client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        after = client.get(
            "/api/v1/national-templates/homework",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        row = next(r for r in after if r["id"] == nat_id)
        assert row["adopted_local_template_id"] == adopted["local_template_id"]


class TestTenantIsolation:
    def test_school_a_adoption_is_invisible_to_school_b(self, client):
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))
        _adopt_subject(client, "ENG-F1", "Form 1 English",
                       _admin_headers(SCHOOL_B, ADMIN_B))
        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-T", "title": "x", "description": "x"},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{nat_id}/publish",
            headers=_ops_headers(),
        )
        client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        )

        # School A sees adopted_local_template_id set.
        a_rows = client.get(
            "/api/v1/national-templates/homework",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        ).json()["data"]
        a_row = next(r for r in a_rows if r["id"] == nat_id)
        assert a_row["adopted_local_template_id"] is not None

        # School B sees the same national template but with no adopt.
        b_rows = client.get(
            "/api/v1/national-templates/homework",
            headers=_admin_headers(SCHOOL_B, ADMIN_B),
        ).json()["data"]
        b_row = next(r for r in b_rows if r["id"] == nat_id)
        assert b_row["adopted_local_template_id"] is None


class TestLessonPlanLifecycle:
    """Same shape as homework — one round-trip test confirms the
    lesson-plan-side endpoints work in parallel."""

    def test_create_publish_adopt(self, client):
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))
        nat_id = client.post(
            "/api/v1/ministry/national-templates/lesson-plan",
            headers=_ops_headers(),
            json={"code": "LP-001", "title": "Quadratics intro",
                  "objectives": "Define a quadratic.",
                  "subject_code": "MATH-F1",
                  "topic_codes": ["T-1"]},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/lesson-plan/{nat_id}/publish",
            headers=_ops_headers(),
        )
        r = client.post(
            f"/api/v1/national-templates/lesson-plan/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        )
        assert r.status_code == 201
        d = r.json()["data"]
        assert d["topics_resolved"] == 1


class TestAudit:
    def test_audit_carries_no_titles_or_bodies(self, client, engine_and_session):
        _, SL = engine_and_session
        _adopt_subject(client, "MATH-F1", "Form 1 Maths",
                       _admin_headers(SCHOOL_A, ADMIN_A))
        nat_id = client.post(
            "/api/v1/ministry/national-templates/homework",
            headers=_ops_headers(),
            json={"code": "HW-AUD", "title": "Secret Title",
                  "description": "Body should NOT appear in audit.",
                  "subject_code": "MATH-F1",
                  "topic_codes": ["T-1"]},
        ).json()["data"]["id"]
        client.post(
            f"/api/v1/ministry/national-templates/homework/{nat_id}/publish",
            headers=_ops_headers(),
        )
        client.post(
            f"/api/v1/national-templates/homework/{nat_id}/adopt",
            headers=_admin_headers(SCHOOL_A, ADMIN_A),
        )
        from app.models.audit import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type.in_([
                    "national_template.created",
                    "national_template.published",
                    "national_template.adopted",
                ]))
                .all()
            )
            assert len(rows) >= 3
            for r in rows:
                blob = _json.dumps({"target": r.target,
                                    "details": r.details or "{}"})
                assert "Secret Title" not in blob
                assert "Body should NOT appear" not in blob
        finally:
            s.close()
