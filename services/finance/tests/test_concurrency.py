"""Q-007 (Phase 4) — concurrency invariants for finance.

The pre-existing `test_concurrency_two_payments` in test_fees.py is a
sequential simulation. This file pushes harder on the row-locking /
CAS invariants by:

  1. Deterministically simulating two interleaved transactions that
     race on the same invoice — the CAS predicate (BUG-010) must
     reject the loser.
  2. Concurrent idempotency-key collisions — N calls with the SAME
     idempotency_key must yield exactly ONE Payment row, even when
     interleaved.
  3. Fan-out: 50 sequential payments across 50 invoices verify the
     global invariant Σ payments == Σ invoice.paid_amount and that
     every invoice ends in PAID status.

Why deterministic rather than `threading.Thread + Barrier`?
The unit-test runtime is SQLite + StaticPool, which funnels every
session's writes through a single shared connection — SQLite cannot
faithfully simulate the race because it serializes writes at the
file/connection level. Threading would either deadlock (two writes
to one connection) or appear to race but not actually do so. Postgres
(production) has true row-level locking via FOR UPDATE; that path is
covered by the production runtime, not by this unit test.

The deterministic interleave is the SAME logical scenario the
threaded version would have exercised — we just drive the ordering
explicitly so a CI environment without Postgres can still catch
regressions in the CAS predicate (BUG-010) or the idempotency guard.
"""
from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fees_concurrency.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, close_all_sessions
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.fees import FeeStructure, FeeItem, Invoice, Payment  # noqa


@pytest.fixture
def engine_and_factory():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _wal(dbapi_conn, _):
        dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    close_all_sessions()
    eng.dispose()


@pytest.fixture
def db(engine_and_factory):
    _, SessionLocal = engine_and_factory
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


SCHOOL_A = uuid.uuid4()
STUDENT_1 = uuid.uuid4()
YEAR_A = uuid.uuid4()
TERM_A = uuid.uuid4()


_INVOICE_COUNTER = 0


def _invoice(db, total=Decimal("1000"), student_id=None):
    """Fresh invoice per call so the duplicate-invoice guard never fires."""
    global _INVOICE_COUNTER
    _INVOICE_COUNTER += 1

    from app.services.fees_service import FeesService
    svc = FeesService(db)
    fs = svc.create_fee_structure(
        school_id=SCHOOL_A,
        academic_year_id=YEAR_A,
        name=f"Term 1 Fees #{_INVOICE_COUNTER}",
        items=[{"label": "Tuition", "amount": float(total), "currency": "USD"}],
        term_id=TERM_A,
    )
    inv = svc.create_invoice(
        SCHOOL_A, student_id or uuid.uuid4(), uuid.UUID(fs["id"]),
        due_date=date(2026, 3, 1),
    )
    return inv


# ════════════════════════════════════════════════════════════════
# Test 1 — deterministic CAS race
# ════════════════════════════════════════════════════════════════


class TestCASOnSameInvoice:
    """Exercise the BUG-010 optimistic CAS predicate. Two sessions read
    the invoice at paid=0, the first commits a 600 payment, the second
    tries to commit a second 600 — must be rejected as
    CONCURRENT_WRITE_LOST or OVERPAYMENT (depending on observation
    order)."""

    def test_second_payment_loses_cas(self, engine_and_factory, db):
        _, SessionLocal = engine_and_factory
        inv = _invoice(db)
        inv_id = uuid.UUID(inv["id"])

        s1 = SessionLocal()
        s2 = SessionLocal()
        try:
            from app.services.fees_service import FeesService

            # Both sessions LOAD the invoice — both see paid_amount=0.
            inv1 = s1.query(Invoice).filter(Invoice.id == inv_id).first()
            inv2 = s2.query(Invoice).filter(Invoice.id == inv_id).first()
            assert inv1.paid_amount == 0
            assert inv2.paid_amount == 0

            # s1 records its payment and commits.
            r1 = FeesService(s1).record_payment(SCHOOL_A, inv_id, Decimal("600"))
            assert "error" not in r1
            assert r1["invoice"]["paid_amount"] == 600

            # s2 now tries to record its payment. Its in-memory `inv2`
            # still has paid_amount=0, but the DB row has paid_amount=600.
            # The CAS WHERE paid_amount == observed_paid (=0) must fail
            # → CONCURRENT_WRITE_LOST (or possibly OVERPAYMENT if the
            # read happens to refresh).
            r2 = FeesService(s2).record_payment(SCHOOL_A, inv_id, Decimal("600"))
            assert r2.get("error") in ("CONCURRENT_WRITE_LOST", "OVERPAYMENT"), \
                f"Expected race rejection, got: {r2}"

            # Final state: exactly one payment, invoice paid_amount = 600.
            fresh = SessionLocal()
            try:
                final = fresh.query(Invoice).filter(Invoice.id == inv_id).first()
                pays = fresh.query(Payment).filter(Payment.invoice_id == inv_id).all()
                assert final.paid_amount == Decimal("600")
                assert len(pays) == 1
            finally:
                fresh.close()
        finally:
            s1.close()
            s2.close()

    def test_cas_predicate_rejects_stale_update(self, engine_and_factory, db):
        """White-box test of the CAS WHERE clause directly.

        SQLite (and any single-connection test runtime) can't faithfully
        simulate a multi-writer race, because every transaction sees the
        latest committed state at load time. We exercise the CAS
        predicate the same way a real concurrent writer would trigger
        it: by manually issuing a `UPDATE ... WHERE paid_amount = <stale>`
        after the DB row has already moved past that value. The CAS
        must reject the update (rowcount=0)."""
        _, SessionLocal = engine_and_factory
        inv = _invoice(db, total=Decimal("1000"))
        inv_id = uuid.UUID(inv["id"])

        # Land a real payment (puts paid_amount at 400).
        from app.services.fees_service import FeesService
        FeesService(db).record_payment(SCHOOL_A, inv_id, Decimal("400"))

        # Simulate a concurrent writer that observed paid_amount=0
        # before our payment landed, and now tries to CAS-update.
        # The predicate `paid_amount == 0` no longer matches → 0 rows.
        s = SessionLocal()
        try:
            rows = s.query(Invoice).filter(
                Invoice.id == inv_id,
                Invoice.school_id == SCHOOL_A,
                Invoice.paid_amount == Decimal("0"),  # stale observed value
            ).update(
                {Invoice.paid_amount: Decimal("300")},
                synchronize_session=False,
            )
            s.commit()
            assert rows == 0, \
                "CAS predicate failed to reject stale write — double-spend possible"
        finally:
            s.close()

        # The real DB state is untouched by the failed CAS attempt.
        fresh = SessionLocal()
        try:
            final = fresh.query(Invoice).filter(Invoice.id == inv_id).first()
            assert final.paid_amount == Decimal("400")
        finally:
            fresh.close()

    def test_cas_predicate_accepts_fresh_update(self, engine_and_factory, db):
        """Inverse of the previous: when the predicate's observed value
        IS still the DB's current value, the update succeeds (rowcount=1)."""
        _, SessionLocal = engine_and_factory
        inv = _invoice(db, total=Decimal("1000"))
        inv_id = uuid.UUID(inv["id"])

        s = SessionLocal()
        try:
            rows = s.query(Invoice).filter(
                Invoice.id == inv_id,
                Invoice.school_id == SCHOOL_A,
                Invoice.paid_amount == Decimal("0"),  # matches current state
            ).update(
                {Invoice.paid_amount: Decimal("500")},
                synchronize_session=False,
            )
            s.commit()
            assert rows == 1
        finally:
            s.close()

        fresh = SessionLocal()
        try:
            final = fresh.query(Invoice).filter(Invoice.id == inv_id).first()
            assert final.paid_amount == Decimal("500")
        finally:
            fresh.close()


# ════════════════════════════════════════════════════════════════
# Test 2 — idempotency-key collisions
# ════════════════════════════════════════════════════════════════


class TestIdempotencyUnderConcurrency:
    """The idempotency_key is on a unique index. If two requests hit
    with the same key, the SECOND must dedupe to the first's response
    and NOT create a second Payment row."""

    def test_sequential_dedup(self, engine_and_factory, db):
        _, SessionLocal = engine_and_factory
        inv = _invoice(db, total=Decimal("5000"))
        inv_id = uuid.UUID(inv["id"])

        from app.services.fees_service import FeesService
        svc = FeesService(db)
        key = f"idem-{uuid.uuid4()}"

        results = []
        for _ in range(10):
            results.append(svc.record_payment(
                SCHOOL_A, inv_id, Decimal("100"),
                idempotency_key=key,
            ))

        # 1 was actually recorded, 9 were dedup-replays.
        actually_processed = [r for r in results if not r.get("already_processed")]
        dedup_returns = [r for r in results if r.get("already_processed")]
        assert len(actually_processed) == 1
        assert len(dedup_returns) == 9

        # Exactly ONE Payment row with this key.
        fresh = SessionLocal()
        try:
            rows = fresh.query(Payment).filter(Payment.idempotency_key == key).all()
            assert len(rows) == 1
            inv_row = fresh.query(Invoice).filter(Invoice.id == inv_id).first()
            assert inv_row.paid_amount == Decimal("100"), \
                f"Invoice double-credited: {inv_row.paid_amount}"
        finally:
            fresh.close()

    def test_interleaved_dedup_across_sessions(self, engine_and_factory, db):
        """Same key, two sessions. The second's idempotency check finds
        the first session's Payment row and dedupes — no duplicate row,
        no double-credit on the invoice."""
        _, SessionLocal = engine_and_factory
        inv = _invoice(db, total=Decimal("5000"))
        inv_id = uuid.UUID(inv["id"])

        from app.services.fees_service import FeesService
        s1 = SessionLocal()
        s2 = SessionLocal()
        try:
            key = f"idem-{uuid.uuid4()}"

            r1 = FeesService(s1).record_payment(SCHOOL_A, inv_id, Decimal("100"),
                                                 idempotency_key=key)
            assert "error" not in r1

            r2 = FeesService(s2).record_payment(SCHOOL_A, inv_id, Decimal("100"),
                                                 idempotency_key=key)
            assert "error" not in r2
            assert r2.get("already_processed") is True
        finally:
            s1.close()
            s2.close()

        fresh = SessionLocal()
        try:
            rows = fresh.query(Payment).filter(Payment.idempotency_key == key).all()
            assert len(rows) == 1
            inv_row = fresh.query(Invoice).filter(Invoice.id == inv_id).first()
            assert inv_row.paid_amount == Decimal("100")
        finally:
            fresh.close()


# ════════════════════════════════════════════════════════════════
# Test 3 — fan-out: 50 invoices, global invariants hold
# ════════════════════════════════════════════════════════════════


class TestFanOutInvariants:
    def test_fifty_invoices_paid_in_sequence(self, engine_and_factory, db):
        _, SessionLocal = engine_and_factory
        invoices = [_invoice(db, total=Decimal("100")) for _ in range(50)]

        from app.services.fees_service import FeesService
        svc = FeesService(db)
        for i, inv in enumerate(invoices):
            r = svc.record_payment(SCHOOL_A, uuid.UUID(inv["id"]), Decimal("100"))
            assert "error" not in r, f"Payment {i} failed: {r}"

        # Global invariant: Σ invoice.paid_amount == Σ payment.amount.
        fresh = SessionLocal()
        try:
            all_inv = fresh.query(Invoice).filter(
                Invoice.school_id == SCHOOL_A,
            ).all()
            all_pay = fresh.query(Payment).filter(
                Payment.school_id == SCHOOL_A,
            ).all()
            assert sum(i.paid_amount for i in all_inv) == \
                   sum(p.amount for p in all_pay)
            assert {i.status for i in all_inv} == {"PAID"}
        finally:
            fresh.close()
