"""Phase 12b — PaymentProvider abstraction tests.

Covers:
  * Provider registry resolves known names; defaults to paynow.
  * Manual provider produces a MAN-* reference + instructions.
  * Per-school config endpoint round-trips; unknown provider rejected.
  * Provider-aware initiate uses school's configured provider.
  * Manual confirm marks the txn PAID + audits without leaking notes.
"""
from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_finance_provider.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
PARENT_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import fees as _f  # noqa
    from app.models import audit as _au  # noqa
    from app.models import payment_config as _pc  # noqa

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


def _admin_headers(user_id=ADMIN_A, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage",
    }


def _parent_headers(user_id=PARENT_A, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Parent",
        "X-Permissions": "authenticated",
    }


def _seed_invoice(SessionLocal) -> uuid.UUID:
    from app.models.fees import Invoice
    from decimal import Decimal
    from datetime import date, timedelta
    s = SessionLocal()
    try:
        i = Invoice(
            school_id=SCHOOL_A,
            student_id=uuid.uuid4(),
            fee_structure_id=uuid.uuid4(),
            total_amount=Decimal("100"),
            paid_amount=Decimal("0"),
            due_date=date.today() + timedelta(days=30),
            status="PENDING",
        )
        s.add(i)
        s.commit()
        return i.id
    finally:
        s.close()


# ─── Provider registry / Manual provider ──────────────────────────


class TestProviderRegistry:
    def test_default_is_paynow(self, engine_and_session):
        _, SessionLocal = engine_and_session
        from app.providers import get_provider_for_school
        s = SessionLocal()
        try:
            p = get_provider_for_school(s, SCHOOL_A)
            assert p.name == "paynow"
        finally:
            s.close()

    def test_manual_provider_returns_reference_and_instructions(self):
        from app.providers import ManualHandoverProvider
        from decimal import Decimal
        p = ManualHandoverProvider()
        result = p.initiate(
            invoice_id=uuid.uuid4(), amount=Decimal("50"),
            school_id=SCHOOL_A, payer_user_id=PARENT_A,
        )
        assert result.reference.startswith("MAN-")
        assert result.redirect_url is None
        assert result.status == "PENDING"
        assert "instructions" in result.raw_response


# ─── Per-school config endpoint ───────────────────────────────────


class TestPaymentConfig:
    def test_default_config_is_paynow(self, client):
        r = client.get(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["provider_name"] == "paynow"
        assert body["is_default"] is True
        assert "manual" in body["available_providers"]

    def test_switch_to_manual(self, client):
        r = client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "manual"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["provider_name"] == "manual"

        # GET reflects the new choice
        g = client.get(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
        )
        assert g.json()["data"]["provider_name"] == "manual"
        assert g.json()["data"]["is_default"] is False

    def test_unknown_provider_rejected(self, client):
        r = client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "scammer-coin"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_PROVIDER"


# ─── Provider-aware initiate ──────────────────────────────────────


class TestInitiate:
    def _switch_to_manual(self, client):
        client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "manual"},
        )

    def test_initiate_manual_returns_man_reference(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        self._switch_to_manual(client)
        inv_id = _seed_invoice(SessionLocal)
        r = client.post(
            "/api/v1/fees/payments/checkout",
            headers=_parent_headers(),
            json={"invoice_id": str(inv_id), "amount": "100"},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["provider"] == "manual"
        assert body["reference"].startswith("MAN-")
        assert body["redirect_url"] is None
        assert "instructions" in body and body["instructions"]

    def test_initiate_paynow_default_surfaces_provider_error(
        self, client, engine_and_session,
    ):
        # When the deployment hasn't configured Paynow keys, the
        # provider raises and the route surfaces 502.
        _, SessionLocal = engine_and_session
        inv_id = _seed_invoice(SessionLocal)
        r = client.post(
            "/api/v1/fees/payments/checkout",
            headers=_parent_headers(),
            json={"invoice_id": str(inv_id), "amount": "100"},
        )
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "PROVIDER_ERROR"


# ─── Manual confirm ───────────────────────────────────────────────


class TestManualConfirm:
    def test_confirm_marks_paid(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "manual"},
        )
        inv_id = _seed_invoice(SessionLocal)
        r = client.post(
            "/api/v1/fees/payments/checkout",
            headers=_parent_headers(),
            json={"invoice_id": str(inv_id), "amount": "100"},
        )
        ref = r.json()["data"]["reference"]

        c = client.post(
            "/api/v1/fees/payments/manual/confirm",
            headers=_admin_headers(),
            json={"reference": ref, "note": "Cash received in office"},
        )
        assert c.status_code == 200, c.text
        assert c.json()["data"]["status"] == "PAID"

    def test_confirm_unknown_reference_404(self, client):
        client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "manual"},
        )
        r = client.post(
            "/api/v1/fees/payments/manual/confirm",
            headers=_admin_headers(),
            json={"reference": "MAN-ZZZZZZZZZZZZ"},
        )
        assert r.status_code == 404

    def test_confirm_audit_does_not_log_note(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.put(
            "/api/v1/fees/payment-config",
            headers=_admin_headers(),
            json={"provider_name": "manual"},
        )
        inv_id = _seed_invoice(SessionLocal)
        ref = client.post(
            "/api/v1/fees/payments/checkout",
            headers=_parent_headers(),
            json={"invoice_id": str(inv_id), "amount": "100"},
        ).json()["data"]["reference"]
        client.post(
            "/api/v1/fees/payments/manual/confirm",
            headers=_admin_headers(),
            json={"reference": ref,
                  "note": "TOP SECRET PAYER NARRATIVE XYZ"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "payment.manual.confirmed")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOP SECRET PAYER NARRATIVE XYZ" not in blob
        finally:
            s.close()
