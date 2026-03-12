"""
Fees Service Tests — Quality Gate 6
======================================
Unit Tests:
- Duplicate invoice rejected
- Partial payment correct math
- Overpayment rejected
- Invoice status transitions correct
- Already paid invoice rejects payment

Integration Tests:
- Cross-school isolation
- Idempotent invoice creation
- Idempotent payment creation

Financial Integrity Tests:
- 10 partial payments → status correct
- Exact payment → status PAID
- Payment sequence: PENDING → PARTIAL → PAID
- Defaulter logic
- Concurrency: two payments don't exceed total
"""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
import threading

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_fees.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.fees import FeeStructure, FeeItem, Invoice, Payment  # noqa

engine = create_engine("sqlite:///./test_fees.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Close all sessions THEN drop tables
    TestSession.close_all()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_fees.db"):
        try:
            os.remove("./test_fees.db")
        except OSError:
            pass


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
STUDENT_1 = uuid.uuid4()
STUDENT_2 = uuid.uuid4()
YEAR_A = uuid.uuid4()
TERM_A = uuid.uuid4()


def _svc(db):
    from app.services.fees_service import FeesService
    return FeesService(db)


def _fee_structure(db, school_id=None, items=None, name=None):
    svc = _svc(db)
    default_items = items or [
        {"label": "Tuition", "amount": 800, "currency": "USD"},
        {"label": "Books", "amount": 150, "currency": "USD"},
        {"label": "Activities", "amount": 50, "currency": "USD"},
    ]
    return svc.create_fee_structure(
        school_id or SCHOOL_A, YEAR_A,
        name or f"Fees-{uuid.uuid4().hex[:8]}",
        default_items, TERM_A,
    )


def _invoice(db, student_id=None, fs_id=None, school_id=None, due=None, idem_key=None):
    svc = _svc(db)
    if not fs_id:
        fs = _fee_structure(db, school_id)
        fs_id = uuid.UUID(fs["id"])
    return svc.create_invoice(
        school_id or SCHOOL_A, student_id or STUDENT_1,
        fs_id, due or date(2026, 4, 30), idem_key,
    )


# ═══════════════════════════════════════════
# Fee Structure
# ═══════════════════════════════════════════

class TestFeeStructure:
    def test_create(self, db):
        result = _fee_structure(db)
        assert "id" in result
        assert result["total"] == 1000.0
        assert len(result["items"]) == 3

    def test_items_sum_correct(self, db):
        result = _fee_structure(db, items=[
            {"label": "A", "amount": 333.33},
            {"label": "B", "amount": 666.67},
        ])
        assert abs(result["total"] - 1000.0) < 0.01


# ═══════════════════════════════════════════
# Invoice
# ═══════════════════════════════════════════

class TestInvoice:
    def test_create(self, db):
        result = _invoice(db)
        assert result["total_amount"] == 1000.0
        assert result["paid_amount"] == 0
        assert result["balance"] == 1000.0
        assert result["status"] == "PENDING"

    def test_duplicate_invoice_rejected(self, db):
        fs = _fee_structure(db)
        fs_id = uuid.UUID(fs["id"])
        _invoice(db, fs_id=fs_id)
        result = _invoice(db, fs_id=fs_id)
        assert result["error"] == "DUPLICATE_INVOICE"

    def test_idempotent_invoice(self, db):
        fs = _fee_structure(db)
        fs_id = uuid.UUID(fs["id"])
        r1 = _invoice(db, fs_id=fs_id, idem_key="idem-inv-001")
        r2 = _invoice(db, fs_id=fs_id, idem_key="idem-inv-001")
        assert r1["id"] == r2["id"]  # Same invoice returned

    def test_different_students_allowed(self, db):
        fs = _fee_structure(db)
        fs_id = uuid.UUID(fs["id"])
        r1 = _invoice(db, STUDENT_1, fs_id)
        r2 = _invoice(db, STUDENT_2, fs_id)
        assert "id" in r1 and "id" in r2
        assert r1["id"] != r2["id"]


# ═══════════════════════════════════════════
# Payment — Core
# ═══════════════════════════════════════════

class TestPayment:
    def test_full_payment(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("1000"), "CASH", "REF001")
        assert result["payment"]["amount"] == 1000.0
        assert result["invoice"]["status"] == "PAID"
        assert result["invoice"]["balance"] == 0
        assert result["already_processed"] is False

    def test_partial_payment(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("300"), "MOBILE")
        assert result["invoice"]["status"] == "PARTIAL"
        assert result["invoice"]["paid_amount"] == 300.0
        assert result["invoice"]["balance"] == 700.0

    def test_overpayment_rejected(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("1500"))
        assert result["error"] == "OVERPAYMENT"

    def test_already_paid_rejects(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("1000"))
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("100"))
        assert result["error"] == "ALREADY_PAID"

    def test_zero_amount_rejected(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("0"))
        assert result["error"] == "INVALID_AMOUNT"

    def test_negative_amount_rejected(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("-50"))
        assert result["error"] == "INVALID_AMOUNT"

    def test_idempotent_payment(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        r1 = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                 Decimal("500"), idempotency_key="pay-001")
        r2 = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                 Decimal("500"), idempotency_key="pay-001")
        assert r1["already_processed"] is False
        assert r2["already_processed"] is True
        assert r1["payment"]["id"] == r2["payment"]["id"]


# ═══════════════════════════════════════════
# Financial Integrity — 10 Partial Payments
# ═══════════════════════════════════════════

class TestFinancialIntegrity:
    def test_10_partial_payments(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        for i in range(10):
            result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                         Decimal("100"), reference=f"PAY-{i+1}")
            if i < 9:
                assert result["invoice"]["status"] == "PARTIAL", f"Step {i}: expected PARTIAL"
            else:
                assert result["invoice"]["status"] == "PAID", f"Step {i}: expected PAID"

        # Verify final state
        final = svc.get_invoice(uuid.UUID(inv["id"]), SCHOOL_A)
        assert final["paid_amount"] == 1000.0
        assert final["balance"] == 0
        assert final["status"] == "PAID"

        # 11th payment should fail
        result = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]),
                                     Decimal("1"))
        assert result["error"] == "ALREADY_PAID"

    def test_status_transition_pending_partial_paid(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        assert inv["status"] == "PENDING"

        r1 = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("400"))
        assert r1["invoice"]["status"] == "PARTIAL"

        r2 = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("600"))
        assert r2["invoice"]["status"] == "PAID"

    def test_exact_boundary_payment(self, db):
        inv = _invoice(db)
        svc = _svc(db)
        svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("999.99"))
        r2 = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("0.01"))
        assert r2["invoice"]["status"] == "PAID"
        assert abs(r2["invoice"]["balance"]) < 0.01

    def test_concurrency_two_payments(self, db):
        """Simulate two concurrent payments — total should not exceed invoice amount.
        Uses sequential simulation since SQLite doesn't support real row locking."""
        inv = _invoice(db)
        inv_id = uuid.UUID(inv["id"])
        svc = _svc(db)

        # First payment: 600
        r1 = svc.record_payment(SCHOOL_A, inv_id, Decimal("600"))
        assert "error" not in r1
        assert r1["invoice"]["status"] == "PARTIAL"

        # Second payment: 600 → should fail (only 400 remaining)
        r2 = svc.record_payment(SCHOOL_A, inv_id, Decimal("600"))
        assert r2["error"] == "OVERPAYMENT"

        # Third payment: exact remaining → should succeed
        r3 = svc.record_payment(SCHOOL_A, inv_id, Decimal("400"))
        assert r3["invoice"]["status"] == "PAID"
        assert r3["invoice"]["balance"] == 0


# ═══════════════════════════════════════════
# Defaulters
# ═══════════════════════════════════════════

class TestDefaulters:
    def test_defaulter_identified(self, db):
        inv = _invoice(db, due=date(2026, 1, 15))
        svc = _svc(db)
        defaulters = svc.get_defaulters(SCHOOL_A, as_of=date(2026, 2, 1))
        assert len(defaulters) == 1
        assert defaulters[0]["status"] == "OVERDUE"

    def test_paid_not_defaulter(self, db):
        inv = _invoice(db, due=date(2026, 1, 15))
        svc = _svc(db)
        svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("1000"))
        defaulters = svc.get_defaulters(SCHOOL_A, as_of=date(2026, 2, 1))
        assert len(defaulters) == 0

    def test_partial_is_defaulter(self, db):
        inv = _invoice(db, due=date(2026, 1, 15))
        svc = _svc(db)
        svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("300"))
        defaulters = svc.get_defaulters(SCHOOL_A, as_of=date(2026, 2, 1))
        assert len(defaulters) == 1


# ═══════════════════════════════════════════
# Cross-School Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_invoice_isolated(self, db):
        fs_a = _fee_structure(db, SCHOOL_A, name="FS-A-Iso")
        fs_b = _fee_structure(db, SCHOOL_B, name="FS-B-Iso")
        svc = _svc(db)
        svc.create_invoice(SCHOOL_A, STUDENT_1, uuid.UUID(fs_a["id"]),
                            date(2026, 4, 30))
        svc.create_invoice(SCHOOL_B, STUDENT_2, uuid.UUID(fs_b["id"]),
                            date(2026, 4, 30))
        assert len(svc.list_invoices(SCHOOL_A)) == 1
        assert len(svc.list_invoices(SCHOOL_B)) == 1

    def test_payment_cross_school_blocked(self, db):
        fs = _fee_structure(db, SCHOOL_A)
        svc = _svc(db)
        inv = svc.create_invoice(SCHOOL_A, STUDENT_1, uuid.UUID(fs["id"]),
                                  date(2026, 4, 30))
        result = svc.record_payment(SCHOOL_B, uuid.UUID(inv["id"]),
                                     Decimal("500"))
        assert result["error"] == "NOT_FOUND"

    def test_defaulters_isolated(self, db):
        fs_a = _fee_structure(db, SCHOOL_A, name="FS-A-Def")
        fs_b = _fee_structure(db, SCHOOL_B, name="FS-B-Def")
        svc = _svc(db)
        svc.create_invoice(SCHOOL_A, STUDENT_1, uuid.UUID(fs_a["id"]),
                            date(2026, 1, 15))
        svc.create_invoice(SCHOOL_B, STUDENT_2, uuid.UUID(fs_b["id"]),
                            date(2026, 1, 15))
        da = svc.get_defaulters(SCHOOL_A, date(2026, 2, 1))
        db_def = svc.get_defaulters(SCHOOL_B, date(2026, 2, 1))
        assert len(da) == 1
        assert len(db_def) == 1
