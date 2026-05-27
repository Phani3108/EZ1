"""Phase 13c tests: expenses, vendors, capital, assets, library, visitors."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_ops.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()


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


class TestExpenses:
    def test_record_then_list_with_total(self, client):
        for amt in (5000, 3000, 2000):
            client.post(
                "/api/v1/expenses", headers=_admin_headers(),
                json={"category": "utilities",
                      "description": "Electricity",
                      "amount_cents": amt,
                      "incurred_on": date.today().isoformat()},
            )
        l = client.get("/api/v1/expenses", headers=_admin_headers())
        assert l.json()["data"]["total_cents"] == 10000
        assert len(l.json()["data"]["items"]) == 3


class TestVendorPayments:
    def test_record(self, client):
        r = client.post(
            "/api/v1/vendor-payments", headers=_admin_headers(),
            json={"vendor_name": "Acme Stationers",
                  "amount_cents": 45000,
                  "paid_on": date.today().isoformat(),
                  "method": "bank_transfer"},
        )
        assert r.status_code == 200, r.text


class TestCapitalProjects:
    def test_create_then_update_status(self, client):
        c = client.post(
            "/api/v1/capital-projects", headers=_admin_headers(),
            json={"name": "Lab block",
                  "budget_cents": 1500000,
                  "starts_on": date.today().isoformat()},
        )
        pid = c.json()["data"]["id"]
        u = client.put(
            f"/api/v1/capital-projects/{pid}",
            headers=_admin_headers(),
            json={"status": "in_progress",
                  "spent_cents": 250000},
        )
        assert u.json()["data"]["status"] == "in_progress"
        assert u.json()["data"]["spent_cents"] == 250000


class TestAssets:
    def test_create_then_assign_then_return(self, client):
        c = client.post(
            "/api/v1/assets", headers=_admin_headers(),
            json={"asset_tag": "LAB-0001",
                  "category": "lab_equipment",
                  "name": "Microscope Mk2"},
        )
        aid = c.json()["data"]["id"]
        TARGET = uuid.uuid4()
        a = client.post(
            f"/api/v1/assets/{aid}/movements",
            headers=_admin_headers(),
            json={"action": "assigned",
                  "target_user_id": str(TARGET)},
        )
        assert a.json()["data"]["asset"]["status"] == "assigned"
        assert a.json()["data"]["asset"]["assigned_to_user_id"] == str(TARGET)
        r = client.post(
            f"/api/v1/assets/{aid}/movements",
            headers=_admin_headers(),
            json={"action": "returned"},
        )
        assert r.json()["data"]["asset"]["status"] == "in_stock"


class TestLibrary:
    def test_book_loan_lifecycle(self, client):
        b = client.post(
            "/api/v1/library/books", headers=_admin_headers(),
            json={"title": "Sadza for Beginners",
                  "author": "T. Mukoma",
                  "total_copies": 2},
        )
        bid = b.json()["data"]["id"]
        BORROWER = uuid.uuid4()
        # First loan — one copy out
        l1 = client.post(
            "/api/v1/library/loans", headers=_admin_headers(),
            json={"book_id": bid,
                  "borrower_user_id": str(BORROWER),
                  "due_on": (date.today() + timedelta(days=14)).isoformat()},
        )
        assert l1.status_code == 200
        # Second loan — one copy out
        l2 = client.post(
            "/api/v1/library/loans", headers=_admin_headers(),
            json={"book_id": bid,
                  "borrower_user_id": str(uuid.uuid4()),
                  "due_on": (date.today() + timedelta(days=14)).isoformat()},
        )
        assert l2.status_code == 200
        # Third loan — no copies left
        l3 = client.post(
            "/api/v1/library/loans", headers=_admin_headers(),
            json={"book_id": bid,
                  "borrower_user_id": str(uuid.uuid4()),
                  "due_on": date.today().isoformat()},
        )
        assert l3.status_code == 409
        # Return the first loan
        lid = l1.json()["data"]["id"]
        rr = client.post(f"/api/v1/library/loans/{lid}/return",
                         headers=_admin_headers())
        assert rr.status_code == 200
        assert rr.json()["data"]["status"] == "returned"


class TestVisitors:
    def test_sign_in_then_sign_out(self, client):
        s = client.post(
            "/api/v1/visitors", headers=_admin_headers(),
            json={"full_name": "John Inspector",
                  "visitor_type": "inspector",
                  "purpose": "Routine site visit"},
        )
        vid = s.json()["data"]["id"]
        active = client.get(
            "/api/v1/visitors?active_only=true", headers=_admin_headers(),
        )
        assert len(active.json()["data"]) == 1
        o = client.post(f"/api/v1/visitors/{vid}/sign-out",
                        headers=_admin_headers())
        assert o.json()["data"]["signed_out_at"] is not None
        active2 = client.get(
            "/api/v1/visitors?active_only=true", headers=_admin_headers(),
        )
        assert len(active2.json()["data"]) == 0

    def test_audit_omits_visitor_name(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/visitors", headers=_admin_headers(),
            json={"full_name": "TOPSECRETNAME",
                  "phone": "+263770ABC",
                  "purpose": "ProcurementMtg"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "visitor.signed_in").all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOPSECRETNAME" not in blob
            assert "263770ABC" not in blob
        finally:
            s.close()
