"""Phase 13b tests: compliance + rollups + health records."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_compliance.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
NURSE_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()
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
    from app.models import compliance as _c  # noqa

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


def _admin_headers(user_id=ADMIN_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Admin", "X-Permissions": "school:manage",
    }


def _nurse_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(NURSE_A), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Nurse", "X-Permissions": "school:manage",
    }


def _teacher_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(TEACHER_A), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Teacher", "X-Permissions": "school:manage",
    }


# ─── A-005 templates + submissions ────────────────────────────────


class TestComplianceTemplates:
    def test_create_then_list(self, client):
        r = client.post(
            "/api/v1/compliance/templates", headers=_admin_headers(),
            json={"code": "MoPSE-Q-001", "title": "Quarterly enrolment",
                  "cadence": "quarterly",
                  "schema": {"fields": ["male_count", "female_count"]}},
        )
        assert r.status_code == 200, r.text
        l = client.get("/api/v1/compliance/templates", headers=_admin_headers())
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["code"] == "MoPSE-Q-001"

    def test_invalid_cadence_rejected(self, client):
        r = client.post(
            "/api/v1/compliance/templates", headers=_admin_headers(),
            json={"code": "X", "title": "Bad", "cadence": "daily"},
        )
        assert r.status_code == 400


class TestComplianceSubmissions:
    def _seed_template(self, client) -> str:
        r = client.post(
            "/api/v1/compliance/templates", headers=_admin_headers(),
            json={"code": "T1", "title": "Trial template"},
        )
        return r.json()["data"]["id"]

    def test_draft_submit_accept_flow(self, client):
        tid = self._seed_template(client)
        s = client.post(
            "/api/v1/compliance/submissions", headers=_admin_headers(),
            json={"template_id": tid, "period_label": "2026-Q1",
                  "payload": {"male_count": 120, "female_count": 130}},
        )
        sid = s.json()["data"]["id"]
        assert s.json()["data"]["status"] == "draft"
        sub = client.put(
            f"/api/v1/compliance/submissions/{sid}/decide",
            headers=_admin_headers(),
            json={"status": "submitted"},
        )
        assert sub.json()["data"]["status"] == "submitted"
        acc = client.put(
            f"/api/v1/compliance/submissions/{sid}/decide",
            headers=_admin_headers(),
            json={"status": "accepted"},
        )
        assert acc.json()["data"]["status"] == "accepted"
        assert acc.json()["data"]["accepted_at"] is not None


# ─── A-006 disciplinary rollup ────────────────────────────────────


class TestDisciplineRollup:
    def test_rollup_after_incidents(self, client):
        # Seed two incidents directly via the route
        for _ in range(2):
            client.post(
                "/api/v1/incidents", headers=_admin_headers(),
                json={"student_id": str(uuid.uuid4()),
                      "summary": "X", "severity": "minor",
                      "category": "disruption"},
            )
        r = client.get("/api/v1/compliance/discipline-rollup",
                       headers=_admin_headers())
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["totals"]["incidents"] == 2
        assert body["totals"]["open"] == 2


# ─── A-007 health records ─────────────────────────────────────────


class TestHealthRecords:
    def test_nurse_upsert_then_read(self, client):
        u = client.put(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
            json={"allergies": "Peanuts; mild lactose intolerance",
                  "blood_group": "O+",
                  "emergency_contact_name": "Mai Chiedza",
                  "emergency_contact_phone": "+263770999"},
        )
        assert u.status_code == 200, u.text
        g = client.get(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
        )
        assert g.status_code == 200
        assert g.json()["data"]["blood_group"] == "O+"

    def test_teacher_role_forbidden(self, client):
        client.put(
            f"/api/v1/health-records/{STUDENT_A}", headers=_admin_headers(),
            json={"allergies": "shellfish"},
        )
        # Teacher role passes the gateway RBAC (we test the route-layer
        # second-check that gates to nurse / admin / principal). Even
        # though the gateway allows school:manage, the route forbids
        # Teacher role.
        r = client.get(
            f"/api/v1/health-records/{STUDENT_A}", headers=_teacher_headers(),
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "FORBIDDEN"

    def test_audit_does_not_log_body_on_read_or_write(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.put(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
            json={"allergies": "TOPSECRETALLERGY",
                  "medications": "TOPSECRETMED"},
        )
        client.get(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type.in_([
                    "health_record.created", "health_record.read",
                ]))
                .all()
            )
            assert len(rows) >= 2
            blob = _json.dumps([
                {"target": r.target, "details": r.details} for r in rows
            ])
            assert "TOPSECRETALLERGY" not in blob
            assert "TOPSECRETMED" not in blob
        finally:
            s.close()

    def test_update_logs_field_names_only(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.put(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
            json={"allergies": "initial"},
        )
        client.put(
            f"/api/v1/health-records/{STUDENT_A}", headers=_nurse_headers(),
            json={"allergies": "updated",
                  "blood_group": "A+"},
        )
        from app.models.audit import AuditLog
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "health_record.updated")
                .all()
            )
            assert len(rows) >= 1
            import json as _json
            details = _json.loads(rows[-1].details or "{}")
            assert "changed_fields" in details
            assert set(details["changed_fields"]) >= {"allergies", "blood_group"}
        finally:
            s.close()
