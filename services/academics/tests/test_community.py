"""Phase 13d tests: policies, sponsors/sponsorships, alumni."""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_community.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
PARENT_A = uuid.uuid4()
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
    from app.models import student_life as _sl  # noqa
    from app.models import org as _o  # noqa
    from app.models import parent_life as _pl  # noqa
    from app.models import staff as _st2  # noqa
    from app.models import compliance as _co  # noqa
    from app.models import ops as _op  # noqa
    from app.models import community as _cm  # noqa

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
        "X-User-Id": str(ADMIN_A), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Admin", "X-Permissions": "school:manage",
    }


def _parent_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(PARENT_A), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Parent", "X-Permissions": "authenticated",
    }


class TestPolicies:
    def test_publish_versions_supersede(self, client):
        v1 = client.post(
            "/api/v1/policies", headers=_admin_headers(),
            json={"code": "UNIFORM",
                  "title": "Uniform Policy v1",
                  "category": "uniform",
                  "version": 1,
                  "effective_from": date.today().isoformat()},
        )
        assert v1.status_code == 200, v1.text
        v2 = client.post(
            "/api/v1/policies", headers=_admin_headers(),
            json={"code": "UNIFORM",
                  "title": "Uniform Policy v2",
                  "category": "uniform",
                  "version": 2,
                  "effective_from": date.today().isoformat()},
        )
        assert v2.status_code == 200
        # Parent sees current only (visible + not superseded)
        l = client.get("/api/v1/policies", headers=_parent_headers())
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["version"] == 2
        # Admin sees both
        la = client.get("/api/v1/policies", headers=_admin_headers())
        assert len(la.json()["data"]) == 2

    def test_invisible_policy_hidden_from_parents(self, client):
        client.post(
            "/api/v1/policies", headers=_admin_headers(),
            json={"code": "INTERNAL-001",
                  "title": "Internal Disciplinary",
                  "category": "discipline",
                  "effective_from": date.today().isoformat(),
                  "visible_to_parents": False},
        )
        l = client.get("/api/v1/policies", headers=_parent_headers())
        assert l.json()["data"] == []
        la = client.get("/api/v1/policies", headers=_admin_headers())
        assert len(la.json()["data"]) == 1


class TestSponsors:
    def test_create_sponsor_then_sponsorship(self, client):
        s = client.post(
            "/api/v1/sponsors", headers=_admin_headers(),
            json={"name": "Old Mutual Foundation",
                  "sponsor_type": "corporate",
                  "contact_email": "csr@oldmutual.example"},
        )
        sid = s.json()["data"]["id"]
        sp = client.post(
            "/api/v1/sponsorships", headers=_admin_headers(),
            json={"sponsor_id": sid,
                  "purpose": "bursary",
                  "committed_cents": 500000,
                  "starts_on": date.today().isoformat()},
        )
        assert sp.status_code == 200
        pid = sp.json()["data"]["id"]
        u = client.put(
            f"/api/v1/sponsorships/{pid}",
            headers=_admin_headers(),
            json={"received_cents": 250000, "status": "active"},
        )
        assert u.json()["data"]["status"] == "active"
        assert u.json()["data"]["received_cents"] == 250000


class TestAlumni:
    def test_record_then_update(self, client):
        a = client.post(
            "/api/v1/alumni", headers=_admin_headers(),
            json={"student_id": str(STUDENT_A),
                  "full_name": "Tatenda Moyo",
                  "graduation_year": 2024,
                  "final_class_label": "Form 6 Sciences"},
        )
        aid = a.json()["data"]["id"]
        u = client.put(
            f"/api/v1/alumni/{aid}", headers=_admin_headers(),
            json={"current_occupation": "University of Cape Town student",
                  "current_university": "UCT"},
        )
        assert u.status_code == 200
        assert u.json()["data"]["current_university"] == "UCT"
        assert u.json()["data"]["last_contacted_at"] is not None

    def test_audit_omits_name_and_email(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/alumni", headers=_admin_headers(),
            json={"student_id": str(STUDENT_A),
                  "full_name": "TOPSECRETALUM",
                  "graduation_year": 2024,
                  "current_email": "secret@x.com"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "alumnus.recorded").all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOPSECRETALUM" not in blob
            assert "secret@x.com" not in blob
        finally:
            s.close()
