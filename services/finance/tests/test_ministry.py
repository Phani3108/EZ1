"""Phase 14 / M-003 — Ministry fees aggregation tests.

Same invariants as academics ministry tests:
  * Non-Ministry role gets 403 even with permission string set.
  * Aggregations span schools (cross-tenant).
  * Audit row contains NO PII (no school names — only the school's
    UUID, plus counts).
  * No POST/PUT/DELETE verbs under /ministry.
"""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_finance_ministry.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
SCHOOL_C = uuid.uuid4()
MINISTRY_ACTOR = uuid.uuid4()


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


def _headers(role: str, perms: str = "ministry:read"):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(MINISTRY_ACTOR),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": role,
        "X-Permissions": perms,
    }


def _seed_invoices(SessionLocal):
    from app.models.fees import FeeStructure, FeeItem, Invoice

    s = SessionLocal()
    try:
        # Fee structure (one is enough — invoices carry school_id directly).
        fs = FeeStructure(
            id=uuid.uuid4(), school_id=SCHOOL_A,
            academic_year_id=uuid.uuid4(),
            term_id=uuid.uuid4(),
            name="Term 1 Fees", is_active=True,
        )
        s.add(fs)
        s.flush()

        # School A: 2 invoices. Total = 1000. Paid = 600.
        s.add(Invoice(id=uuid.uuid4(), school_id=SCHOOL_A,
                      student_id=uuid.uuid4(), fee_structure_id=fs.id,
                      total_amount=Decimal("500.00"),
                      paid_amount=Decimal("500.00"),
                      currency="USD",
                      due_date=date.today(),
                      status="PAID"))
        s.add(Invoice(id=uuid.uuid4(), school_id=SCHOOL_A,
                      student_id=uuid.uuid4(), fee_structure_id=fs.id,
                      total_amount=Decimal("500.00"),
                      paid_amount=Decimal("100.00"),
                      currency="USD",
                      due_date=date.today() - timedelta(days=5),
                      status="PARTIAL"))
        # School B: 1 invoice. Total = 200. Paid = 0. Overdue.
        s.add(Invoice(id=uuid.uuid4(), school_id=SCHOOL_B,
                      student_id=uuid.uuid4(), fee_structure_id=fs.id,
                      total_amount=Decimal("200.00"),
                      paid_amount=Decimal("0.00"),
                      currency="USD",
                      due_date=date.today() - timedelta(days=30),
                      status="OVERDUE"))
        # School C: 1 invoice, fully paid.
        s.add(Invoice(id=uuid.uuid4(), school_id=SCHOOL_C,
                      student_id=uuid.uuid4(), fee_structure_id=fs.id,
                      total_amount=Decimal("300.00"),
                      paid_amount=Decimal("300.00"),
                      currency="USD",
                      due_date=date.today(),
                      status="PAID"))
        s.commit()
    finally:
        s.close()


class TestMinistryFeesAuth:
    def test_non_ministry_role_forbidden(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        r = client.get(
            "/api/v1/ministry/fees",
            headers=_headers("Admin", perms="ministry:read,fees:write"),
        )
        assert r.status_code == 403

    def test_no_write_verbs(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        r = client.post(
            "/api/v1/ministry/fees", headers=_headers("Ministry"), json={},
        )
        assert r.status_code in (404, 405)


class TestMinistryFeesRollup:
    def test_per_school_rollup(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        r = client.get(
            "/api/v1/ministry/fees", headers=_headers("Ministry"),
        )
        assert r.status_code == 200, r.text
        rows = {row["school_id"]: row for row in r.json()["data"]}
        a = rows[str(SCHOOL_A)]
        assert a["invoices"] == 2
        assert a["total_invoiced"] == 1000.0
        assert a["total_paid"] == 600.0
        assert a["outstanding"] == 400.0
        assert a["collection_rate"] == 0.6
        b = rows[str(SCHOOL_B)]
        assert b["collection_rate"] == 0.0
        assert b["outstanding"] == 200.0
        c = rows[str(SCHOOL_C)]
        assert c["collection_rate"] == 1.0
        assert c["outstanding"] == 0.0

    def test_filter_by_school(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        r = client.get(
            f"/api/v1/ministry/fees?school_id={SCHOOL_A}",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["school_id"] == str(SCHOOL_A)


class TestMinistryDefaulters:
    def test_overdue_and_partial_split(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        r = client.get(
            "/api/v1/ministry/fees/defaulters",
            headers=_headers("Ministry"),
        )
        rows = {row["school_id"]: row for row in r.json()["data"]}
        a = rows[str(SCHOOL_A)]
        assert a["partial_invoices"] == 1
        assert a["partial_amount"] == 400.0   # 500 - 100
        b = rows[str(SCHOOL_B)]
        assert b["overdue_invoices"] == 1
        assert b["overdue_amount"] == 200.0
        # School C had no overdue/partial — should not appear.
        assert str(SCHOOL_C) not in rows


class TestMinistryFeesAudit:
    def test_audit_no_amounts_or_school_names(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_invoices(SL)
        client.get("/api/v1/ministry/fees", headers=_headers("Ministry"))
        client.get("/api/v1/ministry/fees/defaulters",
                   headers=_headers("Ministry"))

        from app.models.audit import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type.like("ministry.%"))
                .all()
            )
            assert len(rows) >= 2
            for row in rows:
                blob = _json.dumps({"target": row.target,
                                    "details": row.details or {}})
                # Amounts must NOT appear in the audit row for these
                # rollup endpoints (per ADR 018 — they are not a
                # money-move event; details = endpoint+rowcount only).
                assert "500" not in blob
                assert "200" not in blob
                assert "1000" not in blob
                assert "300" not in blob
                # No school UUIDs leaked into details:
                assert str(SCHOOL_A) not in blob
                assert str(SCHOOL_B) not in blob
                assert str(SCHOOL_C) not in blob
                # Required keys present:
                d = row.details
                if isinstance(d, str):
                    d = _json.loads(d)
                assert "endpoint" in d
                assert "rows" in d
        finally:
            s.close()
