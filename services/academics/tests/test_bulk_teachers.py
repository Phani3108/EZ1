"""Phase 15a — Bulk teacher import + parent invite queueing tests."""
from __future__ import annotations

import io
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_bulk_teachers.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
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


def _admin_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,student:write,student:read,invite:write",
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


class TestBulkTeachers:
    def test_happy_path_queues_invites(self, client, engine_and_session):
        csv_bytes = _csv([
            {"first_name": "Tichaona", "last_name": "Moyo",
             "email": "tm@example.com", "phone": "+263770000001",
             "class_codes": "F1A,F1B"},
            {"first_name": "Rumbi", "last_name": "Sibanda",
             "email": "rs@example.com", "phone": "+263770000002",
             "class_codes": "F2A"},
        ])
        r = client.post(
            "/api/v1/bulk/teachers",
            headers=_admin_headers(),
            files={"file": ("teachers.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["total"] == 2
        assert data["queued"] == 2
        # List the queue.
        l = client.get("/api/v1/bulk/invite-requests?role=Teacher",
                       headers=_admin_headers())
        rows = l.json()["data"]
        assert len(rows) == 2
        emails = {row["contact_email"] for row in rows}
        assert emails == {"tm@example.com", "rs@example.com"}
        for row in rows:
            assert row["role"] == "Teacher"
            assert row["request_status"] == "pending"
            assert row["extra"] in ("F1A,F1B", "F2A")

    def test_missing_email_rejected(self, client):
        csv_bytes = _csv([
            {"first_name": "X", "last_name": "Y", "email": "",
             "phone": "+263770000001", "class_codes": ""},
        ])
        r = client.post(
            "/api/v1/bulk/teachers",
            headers=_admin_headers(),
            files={"file": ("teachers.csv", csv_bytes, "text/csv")},
        )
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["queued"] == 0
        assert data["skipped"] == 1

    def test_dry_run_does_not_persist(self, client):
        csv_bytes = _csv([
            {"first_name": "Test", "last_name": "Drier",
             "email": "dry@example.com", "phone": "", "class_codes": ""},
        ])
        r = client.post(
            "/api/v1/bulk/teachers?dry_run=true",
            headers=_admin_headers(),
            files={"file": ("teachers.csv", csv_bytes, "text/csv")},
        )
        assert r.json()["data"]["queued"] == 1
        # Nothing persisted.
        l = client.get("/api/v1/bulk/invite-requests", headers=_admin_headers())
        assert l.json()["data"] == []

    def test_idempotent_skip_on_duplicate_email(self, client):
        csv_bytes = _csv([
            {"first_name": "Dup", "last_name": "One",
             "email": "dup@example.com", "phone": "", "class_codes": ""},
        ])
        client.post("/api/v1/bulk/teachers",
                    headers=_admin_headers(),
                    files={"file": ("t.csv", csv_bytes, "text/csv")})
        r = client.post("/api/v1/bulk/teachers",
                        headers=_admin_headers(),
                        files={"file": ("t.csv", csv_bytes, "text/csv")})
        # Second run skips because the pending row already exists.
        data = r.json()["data"]
        assert data["queued"] == 0
        assert data["skipped"] == 1


class TestParentInviteQueuedOnStudentImport:
    def test_parent_contact_creates_invite_request(self, client):
        # Use the existing /students/import endpoint with parent fields.
        import csv as _csv_mod
        out = io.StringIO()
        w = _csv_mod.DictWriter(out, fieldnames=[
            "first_name", "last_name", "student_code",
            "parent_first_name", "parent_last_name",
            "parent_phone", "parent_email",
        ])
        w.writeheader()
        w.writerow({
            "first_name": "Tendai", "last_name": "Mukoma",
            "student_code": "S-IT-1",
            "parent_first_name": "Mai", "parent_last_name": "Mukoma",
            "parent_phone": "+263770111000",
            "parent_email": "mai@example.com",
        })
        csv_bytes = out.getvalue().encode("utf-8")
        r = client.post(
            "/api/v1/students/import",
            headers=_admin_headers(),
            files={"file": ("students.csv", csv_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.text
        # Now an InviteRequest with role=Parent should exist.
        l = client.get("/api/v1/bulk/invite-requests?role=Parent",
                       headers=_admin_headers())
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["role"] == "Parent"
        assert rows[0]["contact_phone"] == "+263770111000"
        assert rows[0]["contact_email"] == "mai@example.com"
        assert rows[0]["target_resource_type"] == "student"


class TestMarkDispatched:
    def test_mark_dispatched_persists(self, client, engine_and_session):
        csv_bytes = _csv([
            {"first_name": "Mark", "last_name": "Disp",
             "email": "md@example.com", "phone": "", "class_codes": ""},
        ])
        client.post("/api/v1/bulk/teachers",
                    headers=_admin_headers(),
                    files={"file": ("t.csv", csv_bytes, "text/csv")})
        l = client.get("/api/v1/bulk/invite-requests",
                       headers=_admin_headers())
        rid = l.json()["data"][0]["id"]
        fake_inv = str(uuid.uuid4())
        r = client.post(
            f"/api/v1/bulk/invite-requests/{rid}/mark-dispatched"
            f"?identity_invitation_id={fake_inv}",
            headers=_admin_headers(),
        )
        assert r.status_code == 200, r.text
        # No longer in the pending list.
        l2 = client.get("/api/v1/bulk/invite-requests?status=pending",
                        headers=_admin_headers())
        assert l2.json()["data"] == []
        l3 = client.get("/api/v1/bulk/invite-requests?status=dispatched",
                        headers=_admin_headers())
        d = l3.json()["data"]
        assert len(d) == 1
        assert d[0]["identity_invitation_id"] == fake_inv
