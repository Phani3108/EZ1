"""Phase 16a-4 — Bulk CSV import for curriculum tests."""
from __future__ import annotations

import io
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_bulk_curriculum.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
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


def _admin_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage",
    }


def _ops_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(HOD_OPS),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "EduZimOps",
        "X-Permissions": "school:create,ministry:read",
    }


def _csv(rows: list[dict]) -> bytes:
    import csv
    out = io.StringIO()
    if not rows:
        return b""
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode("utf-8")


def _seed_subject(client, code="MATH"):
    return client.post(
        "/api/v1/curriculum/subjects",
        headers=_admin_headers(),
        json={"name": "Mathematics", "code": code},
    ).json()["data"]


class TestSchoolBulkCurriculum:
    def test_units_and_topics_upsert(self, client):
        _seed_subject(client, "MATH")
        csv_bytes = _csv([
            {"subject_code": "MATH", "unit_code": "U-ALG",
             "unit_name": "Algebra", "unit_sequence": "1",
             "unit_grade_level": "Form 3", "topic_code": "T-QUAD",
             "topic_name": "Quadratics", "topic_sequence": "1",
             "learning_outcomes": "Solve quadratic equations.",
             "parent_topic_code": ""},
            {"subject_code": "MATH", "unit_code": "U-ALG",
             "unit_name": "Algebra", "unit_sequence": "1",
             "unit_grade_level": "Form 3", "topic_code": "T-QUAD-DISC",
             "topic_name": "Discriminant", "topic_sequence": "2",
             "learning_outcomes": "", "parent_topic_code": "T-QUAD"},
            {"subject_code": "MATH", "unit_code": "U-GEO",
             "unit_name": "Geometry", "unit_sequence": "2",
             "unit_grade_level": "Form 3", "topic_code": "T-CIRC",
             "topic_name": "Circles", "topic_sequence": "1",
             "learning_outcomes": "", "parent_topic_code": ""},
        ])
        r = client.post(
            "/api/v1/bulk/curriculum",
            headers=_admin_headers(),
            files={"file": ("c.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["units_created"] == 2
        assert d["topics_created"] == 3
        # Re-running with the same CSV is a no-op (idempotent on
        # (school_id, subject_id, code) for both units + topics).
        r2 = client.post(
            "/api/v1/bulk/curriculum",
            headers=_admin_headers(),
            files={"file": ("c.csv", csv_bytes, "text/csv")},
        )
        d2 = r2.json()["data"]
        assert d2["units_created"] == 0
        assert d2["topics_created"] == 0
        # Tree shows the right structure.
        s = client.get("/api/v1/curriculum/subjects", headers=_admin_headers()).json()["data"][0]
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={s['id']}",
            headers=_admin_headers(),
        ).json()["data"]
        assert len(tree["units"]) == 2

    def test_unknown_subject_code_skipped(self, client):
        csv_bytes = _csv([
            {"subject_code": "GHOST", "unit_code": "U-X",
             "unit_name": "X", "unit_sequence": "1",
             "unit_grade_level": "", "topic_code": "",
             "topic_name": "", "topic_sequence": "",
             "learning_outcomes": "", "parent_topic_code": ""},
        ])
        r = client.post(
            "/api/v1/bulk/curriculum",
            headers=_admin_headers(),
            files={"file": ("c.csv", csv_bytes, "text/csv")},
        )
        d = r.json()["data"]
        assert d["units_created"] == 0
        assert d["skipped"] == 1
        assert "unknown subject_code" in d["errors"][0]["error"]

    def test_dry_run_does_not_persist(self, client):
        _seed_subject(client, "MATH")
        csv_bytes = _csv([
            {"subject_code": "MATH", "unit_code": "U-DRY",
             "unit_name": "Dry", "unit_sequence": "1",
             "unit_grade_level": "", "topic_code": "T-X",
             "topic_name": "Topic", "topic_sequence": "1",
             "learning_outcomes": "", "parent_topic_code": ""},
        ])
        r = client.post(
            "/api/v1/bulk/curriculum?dry_run=true",
            headers=_admin_headers(),
            files={"file": ("c.csv", csv_bytes, "text/csv")},
        )
        d = r.json()["data"]
        assert d["units_created"] == 1
        assert d["topics_created"] == 1
        # Nothing persisted.
        s = client.get("/api/v1/curriculum/subjects", headers=_admin_headers()).json()["data"][0]
        tree = client.get(
            f"/api/v1/curriculum/tree?subject_id={s['id']}",
            headers=_admin_headers(),
        ).json()["data"]
        assert tree["units"] == []


class TestNationalBulkCurriculum:
    def test_auto_create_national_subject_and_tree(self, client):
        csv_bytes = _csv([
            {"subject_code": "ZIM-MATH-FRM1",
             "subject_name": "Form 1 Maths",
             "unit_code": "U-NUM", "unit_name": "Numbers",
             "unit_sequence": "1", "unit_grade_level": "Form 1",
             "topic_code": "T-INT", "topic_name": "Integers",
             "topic_sequence": "1",
             "learning_outcomes": "Add and subtract integers.",
             "parent_topic_code": ""},
            {"subject_code": "ZIM-MATH-FRM1",
             "subject_name": "Form 1 Maths",
             "unit_code": "U-ALG", "unit_name": "Algebra",
             "unit_sequence": "2", "unit_grade_level": "Form 1",
             "topic_code": "T-LIN", "topic_name": "Linear Equations",
             "topic_sequence": "1", "learning_outcomes": "",
             "parent_topic_code": ""},
        ])
        r = client.post(
            "/api/v1/ministry/bulk/national-curriculum",
            headers=_ops_headers(),
            files={"file": ("nc.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["subjects_created"] == 1
        assert d["units_created"] == 2
        assert d["topics_created"] == 2

    def test_idempotent_rerun(self, client):
        csv_bytes = _csv([
            {"subject_code": "ZIM-X", "subject_name": "X",
             "unit_code": "U", "unit_name": "Unit",
             "unit_sequence": "1", "unit_grade_level": "",
             "topic_code": "T", "topic_name": "Topic",
             "topic_sequence": "1", "learning_outcomes": "",
             "parent_topic_code": ""},
        ])
        client.post("/api/v1/ministry/bulk/national-curriculum",
                    headers=_ops_headers(),
                    files={"file": ("nc.csv", csv_bytes, "text/csv")})
        r = client.post("/api/v1/ministry/bulk/national-curriculum",
                        headers=_ops_headers(),
                        files={"file": ("nc.csv", csv_bytes, "text/csv")})
        d = r.json()["data"]
        assert d["subjects_created"] == 0
        assert d["units_created"] == 0
        assert d["topics_created"] == 0


class TestTemplatesDownload:
    def test_curriculum_template_present(self, client):
        r = client.get("/api/v1/templates", headers=_admin_headers())
        entities = {e["entity"] for e in r.json()["data"]}
        assert "curriculum" in entities
        assert "national-curriculum" in entities

    def test_curriculum_csv_download(self, client):
        r = client.get("/api/v1/templates/curriculum.csv",
                       headers=_admin_headers())
        assert r.status_code == 200
        text = r.text
        assert "subject_code,unit_code,unit_name" in text
        # Example row references "Quadratics" as the topic.
        assert "T-QUAD" in text
