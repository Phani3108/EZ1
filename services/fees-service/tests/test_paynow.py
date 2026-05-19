"""
Paynow integration tests
=========================
Pure-unit coverage of the Paynow client + webhook handler logic that doesn't
require live calls to paynow.co.zw. We focus on:

  * Hash determinism (signing the same payload twice yields the same hash)
  * Hash round-trip (sign → verify)
  * Hash tampering rejected (changing any value invalidates)
  * Status classifier maps Paynow strings to our internal state
  * `record_payment` idempotency for repeated webhooks
"""
import os
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fees_paynow.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("PAYNOW_INTEGRATION_ID", "1234")
os.environ.setdefault("PAYNOW_INTEGRATION_KEY", "0123456789abcdef0123456789abcdef")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.fees import Invoice, Payment, PaymentTransaction  # noqa: F401
from app.services.fees_service import FeesService

# Force reload so the env vars above are picked up by the cached client
from app.api import payments as payments_module
from app.api.payments import PaynowClient, _classify_paynow_status


engine = create_engine(
    "sqlite:///./test_fees_paynow.db",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from sqlalchemy import event


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, _rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    from sqlalchemy.orm import close_all_sessions
    close_all_sessions()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        path = f"./test_fees_paynow.db{suffix}"
        try:
            os.remove(path)
        except OSError:
            pass


# ───────────── Hash ─────────────

def _client() -> PaynowClient:
    c = PaynowClient()
    c.integration_id = "1234"
    c.integration_key = "0123456789abcdef0123456789abcdef"
    return c


def test_hash_is_deterministic():
    c = _client()
    payload = {"id": c.integration_id, "reference": "EDU-X", "amount": "10.00",
               "status": "Message"}
    assert c.generate_hash(payload) == c.generate_hash(payload)


def test_hash_roundtrip_verifies():
    c = _client()
    payload = {"id": c.integration_id, "reference": "EDU-X", "amount": "10.00",
               "status": "Message"}
    payload["hash"] = c.generate_hash(payload)
    assert c.verify_hash(payload) is True


def test_hash_tamper_rejected():
    c = _client()
    payload = {"id": c.integration_id, "reference": "EDU-X", "amount": "10.00",
               "status": "Message"}
    payload["hash"] = c.generate_hash(payload)
    payload["amount"] = "9999.00"  # tamper after signing
    assert c.verify_hash(payload) is False


def test_hash_missing_rejected():
    c = _client()
    assert c.verify_hash({"id": c.integration_id, "reference": "EDU-X"}) is False


def test_hash_changes_with_key():
    a = _client()
    b = _client()
    b.integration_key = "ffffffffffffffffffffffffffffffff"
    payload = {"id": a.integration_id, "reference": "EDU-X", "amount": "10.00"}
    assert a.generate_hash(payload) != b.generate_hash(payload)


# ───────────── Status classifier ─────────────

@pytest.mark.parametrize("raw,expected", [
    ("Paid", "PAID"),
    ("paid", "PAID"),
    ("Awaiting Delivery", "PAID"),
    ("Delivered", "PAID"),
    ("Cancelled", "CANCELLED"),
    ("Failed", "FAILED"),
    ("Disputed", "FAILED"),
    ("Refunded", "FAILED"),
    ("Sent", "SENT"),
    ("", "SENT"),
    ("Some new status Paynow added", "SENT"),
])
def test_classify_paynow_status(raw, expected):
    assert _classify_paynow_status(raw) == expected


# ───────────── record_payment idempotency (the webhook contract) ─────────────

def _make_invoice(db, school_id, total=Decimal("100.00")):
    from app.models.fees import FeeStructure, FeeItem
    import uuid
    from datetime import date
    fs = FeeStructure(
        id=uuid.uuid4(), school_id=school_id,
        academic_year_id=uuid.uuid4(), name="Term 1 fees",
    )
    db.add(fs)
    db.flush()
    db.add(FeeItem(fee_structure_id=fs.id, label="Tuition", amount=total, currency="USD"))
    inv = Invoice(
        id=uuid.uuid4(), school_id=school_id, student_id=uuid.uuid4(),
        fee_structure_id=fs.id,
        total_amount=total, paid_amount=Decimal("0"),
        currency="USD", due_date=date.today(),
        status="PENDING",
    )
    db.add(inv)
    db.commit()
    return inv


def test_webhook_idempotency_same_key_records_once():
    """
    Simulate Paynow firing the same webhook twice with the same
    (reference, paynow_reference). The second call must NOT create a
    second Payment row or double-count the paid_amount.
    """
    import uuid
    db = TestSession()
    school_id = uuid.uuid4()
    inv = _make_invoice(db, school_id, total=Decimal("100.00"))

    svc = FeesService(db)
    idem = "paynow:EDU-ABC-001:PNW-99"

    r1 = svc.record_payment(school_id, inv.id, Decimal("100.00"),
                            method="ECOCASH", reference="PNW-99",
                            idempotency_key=idem)
    r2 = svc.record_payment(school_id, inv.id, Decimal("100.00"),
                            method="ECOCASH", reference="PNW-99",
                            idempotency_key=idem)

    assert "error" not in r1
    assert r2["already_processed"] is True
    payments = db.query(Payment).filter(Payment.invoice_id == inv.id).all()
    assert len(payments) == 1
    db.refresh(inv)
    assert inv.status == "PAID"
    assert inv.paid_amount == Decimal("100.00")
    db.close()


# ───────────── /fees/payments/initiate header-idempotency ─────────────

def test_initiate_payment_idempotent_replay():
    """Same Idempotency-Key header → one PaymentTransaction, cached payload."""
    import uuid
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app import dependencies as deps

    db = TestSession()
    school_id = uuid.uuid4()
    inv = _make_invoice(db, school_id, total=Decimal("100.00"))
    inv_id = inv.id
    db.close()

    def _db_override():
        d = TestSession()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[deps.get_school_id] = lambda: school_id
    app.dependency_overrides[deps.get_current_user] = lambda: {"sub": str(uuid.uuid4()), "email": "p@x.com"}

    # Force demo mode (no real Paynow call) by clearing creds on the client.
    payments_module.paynow_client.integration_id = ""
    payments_module.paynow_client.integration_key = ""

    client = TestClient(app)
    body = {
        "invoice_id": str(inv_id),
        "amount": 50.0,
        "method": "ECOCASH",
        "phone": "+263772123456",
    }
    headers = {"Idempotency-Key": "abc-123"}

    r1 = client.post("/api/v1/fees/payments/initiate", json=body, headers=headers)
    r2 = client.post("/api/v1/fees/payments/initiate", json=body, headers=headers)

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    p1, p2 = r1.json(), r2.json()
    assert p2["meta"].get("idempotent_replay") is True
    assert p1["data"]["transaction_ref"] == p2["data"]["transaction_ref"]

    # Exactly one PaymentTransaction row created.
    db = TestSession()
    txns = db.query(PaymentTransaction).filter(PaymentTransaction.invoice_id == inv_id).all()
    assert len(txns) == 1
    db.close()

    app.dependency_overrides.clear()
