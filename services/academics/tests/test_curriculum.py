"""Phase 16a — Curriculum + NationalCurriculum + adopt-subject tests."""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import datetime, timezone

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_curriculum.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
HOD_OPS = uuid.uuid4()


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


def _admin_headers(school_id=None, user_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


def _ops_headers():
    """Provisioner / EduZimOps — cross-tenant; X-School-Id ignored on
    Ministry-side writes but the gateway requires SOMETHING."""
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(HOD_OPS),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "EduZimOps",
        "X-Permissions": "school:create,invite:write,ministry:read",
    }


class TestSchoolLocalCurriculum:
    def test_create_subject_with_grade_levels(self, client):
        r = client.post(
            "/api/v1/curriculum/subjects",
            headers=_admin_headers(),
            json={"name": "Mathematics", "code": "MATH",
                  "grade_levels": ["Form 1", "Form 2", "Form 3"]},
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["code"] == "MATH"
        assert d["grade_levels"] == ["Form 1", "Form 2", "Form 3"]
        assert d["national_subject_id"] is None

    def test_duplicate_subject_code_rejected(self, client):
        client.post("/api/v1/curriculum/subjects",
                    headers=_admin_headers(),
                    json={"name": "X", "code": "DUP"})
        r = client.post("/api/v1/curriculum/subjects",
                        headers=_admin_headers(),
                        json={"name": "Y", "code": "DUP"})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "SUBJECT_CODE_TAKEN"

    def test_create_unit_then_topic_then_tree(self, client):
        s = client.post("/api/v1/curriculum/subjects",
                        headers=_admin_headers(),
                        json={"name": "Maths", "code": "MATH"}).json()["data"]
        u = client.post("/api/v1/curriculum/units",
                        headers=_admin_headers(),
                        json={"subject_id": s["id"],
                              "name": "Algebra", "code": "U-ALG",
                              "sequence_order": 1, "grade_level": "Form 3"})
        assert u.status_code == 201, u.text
        unit_id = u.json()["data"]["id"]
        t1 = client.post("/api/v1/curriculum/topics",
                         headers=_admin_headers(),
                         json={"unit_id": unit_id,
                               "name": "Quadratics", "code": "T-QUAD",
                               "sequence_order": 1})
        assert t1.status_code == 201
        topic1_id = t1.json()["data"]["id"]
        # Sub-topic nested under topic 1.
        t2 = client.post("/api/v1/curriculum/topics",
                         headers=_admin_headers(),
                         json={"unit_id": unit_id,
                               "name": "Discriminant",
                               "code": "T-QUAD-DISC",
                               "sequence_order": 1,
                               "parent_topic_id": topic1_id})
        assert t2.status_code == 201

        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={s['id']}",
            headers=_admin_headers(),
        )
        data = tree.json()["data"]
        assert len(data["units"]) == 1
        root_topics = data["units"][0]["topics"]
        assert len(root_topics) == 1
        assert root_topics[0]["code"] == "T-QUAD"
        assert len(root_topics[0]["subtopics"]) == 1
        assert root_topics[0]["subtopics"][0]["code"] == "T-QUAD-DISC"

    def test_unit_under_other_schools_subject_rejected(self, client):
        # Admin A creates a subject in school A.
        s = client.post("/api/v1/curriculum/subjects",
                        headers=_admin_headers(school_id=SCHOOL_A),
                        json={"name": "Maths", "code": "MATH"}).json()["data"]
        # Admin B tries to create a unit in school B referencing that subject.
        r = client.post("/api/v1/curriculum/units",
                        headers=_admin_headers(school_id=SCHOOL_B),
                        json={"subject_id": s["id"],
                              "name": "Algebra", "code": "U-ALG"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "SUBJECT_NOT_FOUND"

    def test_duplicate_unit_code_in_same_subject_rejected(self, client):
        s = client.post("/api/v1/curriculum/subjects",
                        headers=_admin_headers(),
                        json={"name": "M", "code": "M1"}).json()["data"]
        client.post("/api/v1/curriculum/units",
                    headers=_admin_headers(),
                    json={"subject_id": s["id"], "name": "U", "code": "DUP"})
        r = client.post("/api/v1/curriculum/units",
                        headers=_admin_headers(),
                        json={"subject_id": s["id"], "name": "V", "code": "DUP"})
        assert r.status_code == 409


class TestNationalCurriculum:
    def test_create_then_publish(self, client):
        # Provisioner creates a national subject.
        c = client.post("/api/v1/ministry/national-curriculum/subjects",
                        headers=_ops_headers(),
                        json={"code": "ZIM-MATH", "name": "Mathematics"})
        assert c.status_code == 201, c.text
        sid = c.json()["data"]["id"]
        # Not yet published — schools cannot adopt.
        ad = client.post("/api/v1/curriculum/adopt-subject",
                         headers=_admin_headers(),
                         json={"national_subject_id": sid})
        assert ad.status_code == 400
        assert ad.json()["error"]["code"] == "NATIONAL_SUBJECT_NOT_PUBLISHED"
        # Publish.
        p = client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{sid}/publish",
            headers=_ops_headers(),
        )
        assert p.status_code == 200
        assert p.json()["data"]["ministry_published_at"] is not None
        # Listing now shows it (default published_only=True).
        l = client.get("/api/v1/ministry/national-curriculum/subjects",
                       headers=_admin_headers())
        codes = {x["code"] for x in l.json()["data"]}
        assert "ZIM-MATH" in codes


class TestAdoptSubject:
    def _seed_national(self, client):
        c = client.post("/api/v1/ministry/national-curriculum/subjects",
                        headers=_ops_headers(),
                        json={"code": "ZIM-FRM1-MATH", "name": "Form 1 Maths"})
        sid = c.json()["data"]["id"]
        # 2 units, 3 topics total.
        u1 = client.post("/api/v1/ministry/national-curriculum/units",
                         headers=_ops_headers(),
                         json={"national_subject_id": sid,
                               "name": "Numbers", "code": "U-NUM",
                               "sequence_order": 1, "grade_level": "Form 1"})
        u1_id = u1.json()["data"]["id"]
        u2 = client.post("/api/v1/ministry/national-curriculum/units",
                         headers=_ops_headers(),
                         json={"national_subject_id": sid,
                               "name": "Algebra", "code": "U-ALG",
                               "sequence_order": 2, "grade_level": "Form 1"})
        u2_id = u2.json()["data"]["id"]
        client.post("/api/v1/ministry/national-curriculum/topics",
                    headers=_ops_headers(),
                    json={"national_unit_id": u1_id,
                          "name": "Integers", "code": "T-INT",
                          "sequence_order": 1})
        client.post("/api/v1/ministry/national-curriculum/topics",
                    headers=_ops_headers(),
                    json={"national_unit_id": u2_id,
                          "name": "Linear Equations", "code": "T-LIN",
                          "sequence_order": 1})
        client.post("/api/v1/ministry/national-curriculum/topics",
                    headers=_ops_headers(),
                    json={"national_unit_id": u2_id,
                          "name": "Inequalities", "code": "T-INEQ",
                          "sequence_order": 2})
        # Publish.
        client.post(
            f"/api/v1/ministry/national-curriculum/subjects/{sid}/publish",
            headers=_ops_headers(),
        )
        return sid

    def test_adopt_clones_full_tree(self, client):
        sid = self._seed_national(client)
        r = client.post("/api/v1/curriculum/adopt-subject",
                        headers=_admin_headers(),
                        json={"national_subject_id": sid,
                              "grade_levels": ["Form 1"]})
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["units_cloned"] == 2
        assert d["topics_cloned"] == 3
        assert d["idempotent"] is False
        local_subject_id = d["subject"]["id"]
        assert d["subject"]["national_subject_id"] == sid
        # Tree on the school side mirrors the national tree.
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={local_subject_id}",
            headers=_admin_headers(),
        )
        units = tree.json()["data"]["units"]
        assert len(units) == 2
        algebra = next(u for u in units if u["code"] == "U-ALG")
        assert len(algebra["topics"]) == 2

    def test_adopt_is_idempotent(self, client):
        sid = self._seed_national(client)
        first = client.post("/api/v1/curriculum/adopt-subject",
                            headers=_admin_headers(),
                            json={"national_subject_id": sid})
        second = client.post("/api/v1/curriculum/adopt-subject",
                             headers=_admin_headers(),
                             json={"national_subject_id": sid})
        assert second.status_code == 200
        d = second.json()["data"]
        assert d["idempotent"] is True
        assert d["units_cloned"] == 0
        assert d["topics_cloned"] == 0
        # Same local subject id.
        assert d["subject"]["id"] == first.json()["data"]["subject"]["id"]

    def test_adopt_tenant_isolated(self, client):
        sid = self._seed_national(client)
        # Both schools adopt → each gets its own local subject row.
        a = client.post("/api/v1/curriculum/adopt-subject",
                        headers=_admin_headers(school_id=SCHOOL_A),
                        json={"national_subject_id": sid})
        b = client.post("/api/v1/curriculum/adopt-subject",
                        headers=_admin_headers(school_id=SCHOOL_B),
                        json={"national_subject_id": sid})
        assert a.status_code == 201
        assert b.status_code == 201
        assert a.json()["data"]["subject"]["id"] != b.json()["data"]["subject"]["id"]

    def test_audit_no_names_only_counts(self, client, engine_and_session):
        _, SL = engine_and_session
        sid = self._seed_national(client)
        client.post("/api/v1/curriculum/adopt-subject",
                    headers=_admin_headers(),
                    json={"national_subject_id": sid})
        from app.models.audit import AuditLog
        s = SL()
        try:
            row = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "curriculum.subject.adopted")
                .first()
            )
            assert row is not None
            blob = _json.dumps({"target": row.target,
                                "details": row.details or "{}"})
            # No subject / unit / topic names in details.
            assert "Form 1 Maths" not in blob
            assert "Numbers" not in blob
            assert "Algebra" not in blob
            assert "Inequalities" not in blob
            # Counts ARE present.
            assert "units_cloned" in blob
            assert "topics_cloned" in blob
        finally:
            s.close()
