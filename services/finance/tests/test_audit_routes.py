"""Integration tests for finance audit-log endpoint + write-side wiring.

Mirrors the academics audit-route tests. Covers:
  * `GET /api/v1/fees/audit-log` returns rows scoped to the caller's school.
  * Cross-tenant isolation.
  * Write-side wiring: POST /fees/structures, POST /fees/invoices,
    POST /fees/payments each leave an audit row.
  * PII-minimisation invariant: fee amounts are NOT logged in audit
    `details` for fee structures or invoices (only counts / IDs).
    Payment amounts ARE logged because they're the audit story for a
    money move (ADR 018 calls this out explicitly).
"""
from __future__ import annotations

import json
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_finance_audit.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import fees as _f  # noqa
    from app.models import audit as _au  # noqa

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


def _admin_headers(school_id, user_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or uuid.uuid4()),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage,fees:write",
    }


# ─── Browse endpoint ─────────────────────────────────────────────


class TestList:

    def test_empty_returns_empty_list(self, client):
        r = client.get("/api/v1/fees/audit-log",
                       headers=_admin_headers(SCHOOL_A))
        assert r.status_code == 200
        assert r.json()["data"] == []
        assert r.json()["meta"]["total"] == 0

    def test_school_isolation(self, client, engine_and_session):
        """Seed rows for both schools; A's admin must not see B's rows."""
        _, SessionLocal = engine_and_session
        from app.models.audit import AuditLog
        from datetime import datetime, timezone
        s = SessionLocal()
        try:
            for _ in range(3):
                s.add(AuditLog(
                    id=uuid.uuid4(),
                    occurred_at=datetime.now(timezone.utc),
                    school_id=SCHOOL_A,
                    event_type="fee_structure.created",
                ))
            for _ in range(5):
                s.add(AuditLog(
                    id=uuid.uuid4(),
                    occurred_at=datetime.now(timezone.utc),
                    school_id=SCHOOL_B,
                    event_type="invoice.created",
                ))
            s.commit()
        finally:
            s.close()

        r_a = client.get("/api/v1/fees/audit-log", headers=_admin_headers(SCHOOL_A))
        r_b = client.get("/api/v1/fees/audit-log", headers=_admin_headers(SCHOOL_B))
        assert r_a.json()["meta"]["total"] == 3
        assert r_b.json()["meta"]["total"] == 5
        for row in r_a.json()["data"]:
            assert row["school_id"] == str(SCHOOL_A)


# ─── Write-side wiring ────────────────────────────────────────────


class TestWriteSideWiring:

    def test_fee_structure_create_audited(self, client, engine_and_session):
        """POST /fees/structures → audit row with event=fee_structure.created."""
        r = client.post(
            "/api/v1/fees/structures",
            headers=_admin_headers(SCHOOL_A),
            json={
                "academic_year_id": str(uuid.uuid4()),
                "name": "Term 1 Fees",
                "items": [
                    {"label": "Tuition", "amount": 500.0, "currency": "USD"},
                    {"label": "Books",   "amount": 100.0, "currency": "USD"},
                ],
            },
        )
        assert r.status_code == 200, r.text
        fs_id = r.json()["data"]["id"]

        audit_r = client.get(
            "/api/v1/fees/audit-log?event_type=fee.structure.created",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["target"]["id"] == fs_id

    def test_fee_structure_audit_does_not_log_amounts(self, client):
        """PII-minimisation: the fee structure's monetary values must
        NOT appear in audit details — only structural metadata
        (name + item count)."""
        r = client.post(
            "/api/v1/fees/structures",
            headers=_admin_headers(SCHOOL_A),
            json={
                "academic_year_id": str(uuid.uuid4()),
                "name": "Term 1 Fees",
                "items": [
                    {"label": "Tuition", "amount": 12345.67, "currency": "USD"},
                ],
            },
        )
        assert r.status_code == 200

        audit_r = client.get(
            "/api/v1/fees/audit-log?event_type=fee.structure.created",
            headers=_admin_headers(SCHOOL_A),
        )
        details = audit_r.json()["data"][0]["details"]
        # Should have structural metadata
        assert details["item_count"] == 1
        assert details["name"] == "Term 1 Fees"
        # Should NOT contain the price
        assert "12345.67" not in json.dumps(details)
        assert "amount" not in details

    def test_invoice_create_audited(self, client, engine_and_session):
        # First create a structure
        r = client.post(
            "/api/v1/fees/structures",
            headers=_admin_headers(SCHOOL_A),
            json={
                "academic_year_id": str(uuid.uuid4()),
                "name": "Term 1 Fees",
                "items": [{"label": "Tuition", "amount": 500, "currency": "USD"}],
            },
        )
        fs_id = r.json()["data"]["id"]
        student_id = uuid.uuid4()

        r = client.post(
            "/api/v1/fees/invoices",
            headers=_admin_headers(SCHOOL_A),
            json={
                "student_id": str(student_id),
                "fee_structure_id": fs_id,
                "due_date": "2026-04-01",
            },
        )
        assert r.status_code == 200, r.text

        audit_r = client.get(
            "/api/v1/fees/audit-log?event_type=fee.invoice.created",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["target"]["student_id"] == str(student_id)
        # Amount is NOT in audit details (it's on the invoice row, ACL-scoped).
        details = rows[0]["details"]
        assert "500" not in json.dumps(details)
        assert details["due_date"] == "2026-04-01"

    def test_payment_audit_logs_amount_intentionally(self, client):
        """ADR 018 §3 exception: payment amount IS logged in audit
        details because the amount IS the audit story for a money move.
        Document the exception via test so a future PR that removes it
        as 'PII leak' gets a red flag."""
        # Create structure + invoice
        r = client.post(
            "/api/v1/fees/structures",
            headers=_admin_headers(SCHOOL_A),
            json={
                "academic_year_id": str(uuid.uuid4()),
                "name": "T1",
                "items": [{"label": "Tuition", "amount": 1000, "currency": "USD"}],
            },
        )
        fs_id = r.json()["data"]["id"]
        r = client.post(
            "/api/v1/fees/invoices",
            headers=_admin_headers(SCHOOL_A),
            json={
                "student_id": str(uuid.uuid4()),
                "fee_structure_id": fs_id,
                "due_date": "2026-04-01",
            },
        )
        invoice_id = r.json()["data"]["id"]

        # Record a payment
        r = client.post(
            "/api/v1/fees/payments",
            headers=_admin_headers(SCHOOL_A),
            json={
                "invoice_id": invoice_id,
                "amount": 250.0,
                "method": "CASH",
            },
        )
        assert r.status_code == 200, r.text

        audit_r = client.get(
            "/api/v1/fees/audit-log?event_type=fee.payment.recorded",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        details = rows[0]["details"]
        # Amount IS logged for payments (the exception in ADR 018).
        assert "250" in str(details.get("amount"))
        assert details["method"] == "CASH"
        # And we DID capture IP / user-agent on this one (security event).
        # TestClient sets these to defaults; the assertion is "they're not None"
        # rather than a specific value.
        assert rows[0]["ip_address"] is not None or rows[0]["user_agent"] is not None
