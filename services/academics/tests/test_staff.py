"""Phase 13a tests: staff + HR + admissions + transfers."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_staff.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
STAFF_USER_A = uuid.uuid4()
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


def _staff_headers(user_id=STAFF_USER_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Teacher", "X-Permissions": "authenticated",
    }


# ─── A-001 staff ──────────────────────────────────────────────────


class TestStaff:
    def test_create_then_list(self, client):
        r = client.post(
            "/api/v1/staff", headers=_admin_headers(),
            json={"role_category": "accountant",
                  "staff_code": "ACC001",
                  "first_name": "Tendai", "last_name": "Moyo"},
        )
        assert r.status_code == 200, r.text
        l = client.get("/api/v1/staff", headers=_admin_headers())
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["role_category"] == "accountant"

    def test_terminate_marks_inactive(self, client):
        cr = client.post(
            "/api/v1/staff", headers=_admin_headers(),
            json={"role_category": "driver",
                  "staff_code": "DRV001",
                  "first_name": "Farai", "last_name": "Ncube"},
        )
        sid = cr.json()["data"]["id"]
        client.post(f"/api/v1/staff/{sid}/terminate", headers=_admin_headers())
        l = client.get(
            "/api/v1/staff?active_only=true", headers=_admin_headers(),
        )
        assert len(l.json()["data"]) == 0
        l2 = client.get(
            "/api/v1/staff?active_only=false", headers=_admin_headers(),
        )
        assert len(l2.json()["data"]) == 1
        assert l2.json()["data"][0]["is_active"] is False

    def test_audit_does_not_log_names(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/staff", headers=_admin_headers(),
            json={"role_category": "nurse",
                  "staff_code": "NUR001",
                  "first_name": "TOPSECRETNAME",
                  "last_name": "DONOTLOG",
                  "phone": "+263770001",
                  "email": "secret@example.com"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "staff.created").all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOPSECRETNAME" not in blob
            assert "DONOTLOG" not in blob
            assert "secret@example.com" not in blob
        finally:
            s.close()


# ─── A-002 leave ──────────────────────────────────────────────────


class TestLeave:
    def test_request_then_approve(self, client):
        today = date.today()
        r = client.post(
            "/api/v1/leave-requests", headers=_staff_headers(),
            json={"leave_type": "annual",
                  "starts_on": (today + timedelta(days=10)).isoformat(),
                  "ends_on": (today + timedelta(days=15)).isoformat(),
                  "reason": "Family wedding"},
        )
        assert r.status_code == 200, r.text
        lid = r.json()["data"]["id"]
        d = client.put(
            f"/api/v1/leave-requests/{lid}/decide",
            headers=_admin_headers(),
            json={"status": "approved"},
        )
        assert d.status_code == 200
        assert d.json()["data"]["status"] == "approved"

    def test_invalid_window_rejected(self, client):
        today = date.today()
        r = client.post(
            "/api/v1/leave-requests", headers=_staff_headers(),
            json={"leave_type": "annual",
                  "starts_on": (today + timedelta(days=15)).isoformat(),
                  "ends_on": (today + timedelta(days=10)).isoformat()},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_WINDOW"

    def test_staff_sees_only_own(self, client):
        today = date.today()
        client.post(
            "/api/v1/leave-requests", headers=_staff_headers(),
            json={"starts_on": today.isoformat(),
                  "ends_on": today.isoformat()},
        )
        OTHER = uuid.uuid4()
        client.post(
            "/api/v1/leave-requests", headers=_staff_headers(user_id=OTHER),
            json={"starts_on": today.isoformat(),
                  "ends_on": today.isoformat()},
        )
        mine = client.get("/api/v1/leave-requests", headers=_staff_headers())
        assert len(mine.json()["data"]) == 1
        all_admin = client.get(
            "/api/v1/leave-requests", headers=_admin_headers(),
        )
        assert len(all_admin.json()["data"]) == 2


# ─── A-002 salary slips ──────────────────────────────────────────


class TestSalary:
    def test_issue_slip_computes_net(self, client):
        r = client.post(
            "/api/v1/salary-slips", headers=_admin_headers(),
            json={"user_id": str(STAFF_USER_A),
                  "period_year": 2026, "period_month": 5,
                  "gross_cents": 50000, "deductions_cents": 5000},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["net_cents"] == 45000

    def test_staff_sees_own_only(self, client):
        client.post(
            "/api/v1/salary-slips", headers=_admin_headers(),
            json={"user_id": str(STAFF_USER_A),
                  "period_year": 2026, "period_month": 5,
                  "gross_cents": 10000},
        )
        client.post(
            "/api/v1/salary-slips", headers=_admin_headers(),
            json={"user_id": str(uuid.uuid4()),
                  "period_year": 2026, "period_month": 5,
                  "gross_cents": 10000},
        )
        mine = client.get("/api/v1/salary-slips",
                          headers=_staff_headers(user_id=STAFF_USER_A))
        assert len(mine.json()["data"]) == 1

    def test_unique_per_period(self, client):
        client.post(
            "/api/v1/salary-slips", headers=_admin_headers(),
            json={"user_id": str(STAFF_USER_A),
                  "period_year": 2026, "period_month": 6,
                  "gross_cents": 10000},
        )
        # Second slip same period — should 500 (uniq violation surfaces
        # as a server-side error). Acceptable; we just confirm one row
        # remains via list.
        client.post(
            "/api/v1/salary-slips", headers=_admin_headers(),
            json={"user_id": str(STAFF_USER_A),
                  "period_year": 2026, "period_month": 6,
                  "gross_cents": 99999},
        )
        all_user = client.get(
            "/api/v1/salary-slips",
            headers=_staff_headers(user_id=STAFF_USER_A),
        )
        # June row exists exactly once
        june = [s for s in all_user.json()["data"] if s["period_month"] == 6]
        assert len(june) == 1


# ─── A-003 admissions ────────────────────────────────────────────


class TestAdmissions:
    def test_submit_then_accept_then_enrol(self, client):
        s = client.post(
            "/api/v1/admissions", headers=_admin_headers(),
            json={
                "applicant_first_name": "Chiedza",
                "applicant_last_name": "Mhlanga",
                "guardian_first_name": "Rumbi",
                "guardian_last_name": "Mhlanga",
                "guardian_phone": "+263770111",
            },
        )
        aid = s.json()["data"]["id"]
        a = client.put(
            f"/api/v1/admissions/{aid}/decide",
            headers=_admin_headers(),
            json={"status": "accepted",
                  "decision_notes": "Strong placement test."},
        )
        assert a.status_code == 200
        assert a.json()["data"]["status"] == "accepted"
        # Enrol step needs a student_id
        e = client.put(
            f"/api/v1/admissions/{aid}/decide",
            headers=_admin_headers(),
            json={"status": "enrolled",
                  "student_id": str(STUDENT_A)},
        )
        assert e.status_code == 200
        assert e.json()["data"]["status"] == "enrolled"
        assert e.json()["data"]["student_id"] == str(STUDENT_A)

    def test_enrol_without_student_id_rejected(self, client):
        s = client.post(
            "/api/v1/admissions", headers=_admin_headers(),
            json={"applicant_first_name": "Alice",
                  "applicant_last_name": "X",
                  "guardian_first_name": "B",
                  "guardian_last_name": "X",
                  "guardian_phone": "+263770000"},
        )
        aid = s.json()["data"]["id"]
        r = client.put(
            f"/api/v1/admissions/{aid}/decide",
            headers=_admin_headers(),
            json={"status": "enrolled"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "STUDENT_ID_REQUIRED"


# ─── A-004 transfers ─────────────────────────────────────────────


class TestTransfers:
    def test_outbound_record(self, client):
        r = client.post(
            "/api/v1/transfers", headers=_admin_headers(),
            json={
                "student_id": str(STUDENT_A),
                "direction": "outbound",
                "counterparty_school_name": "Springs College",
                "effective_date": date.today().isoformat(),
                "reason": "Family relocating",
            },
        )
        assert r.status_code == 200, r.text
        l = client.get(
            f"/api/v1/transfers?student_id={STUDENT_A}",
            headers=_admin_headers(),
        )
        assert len(l.json()["data"]) == 1
        assert l.json()["data"][0]["direction"] == "outbound"
