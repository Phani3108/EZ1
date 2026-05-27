"""
Invoice + payment-receipt PDF tests.

These exercise both the renderer (returns valid PDF bytes) and the routes
(`/fees/invoices/{id}/pdf`, `/fees/payments/{id}/receipt`) end-to-end through
``TestClient``.

The dev-mode payment flow already covers a richer integration; here we focus
narrowly on the new endpoints.
"""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_fees_pdf.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database as app_db
from app.database import Base
from app.models.fees import FeeStructure, FeeItem, Invoice, Payment  # noqa
from app.services.fees_service import FeesService
from app.services.pdf_renderer import build_invoice_pdf, build_receipt_pdf

DB_URL = "sqlite:///./test_fees_pdf.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def _setup_db(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(app_db, "SessionLocal", TestSession)
    monkeypatch.setattr(app_db, "engine", engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(monkeypatch):
    # Bypass auth/header deps — return fixed school + user.
    from app.main import app
    from app import dependencies as deps

    def _school():
        return SCHOOL

    def _user():
        return {"sub": str(uuid.uuid4()), "email": "admin@example.com"}

    app.dependency_overrides[deps.get_school_id] = _school
    app.dependency_overrides[deps.get_current_user] = _user
    yield TestClient(app)
    app.dependency_overrides.clear()


SCHOOL = uuid.uuid4()


def _seed_invoice_with_payment(db, paid: Decimal = Decimal("400")):
    svc = FeesService(db)
    fs = svc.create_fee_structure(
        school_id=SCHOOL,
        academic_year_id=uuid.uuid4(),
        name="Term 1 2026",
        items=[
            {"label": "Tuition", "amount": 800, "currency": "USD"},
            {"label": "Books", "amount": 150, "currency": "USD"},
        ],
    )
    inv = svc.create_invoice(
        school_id=SCHOOL,
        student_id=uuid.uuid4(),
        fee_structure_id=uuid.UUID(fs["id"]),
        due_date=date.today() + timedelta(days=14),
    )
    pay = svc.record_payment(
        school_id=SCHOOL, invoice_id=uuid.UUID(inv["id"]),
        amount=paid, method="ECOCASH", reference="EDU-TEST",
        idempotency_key=f"pdf-test-{uuid.uuid4()}",
    )
    return inv, pay


# ────────────── Renderer ──────────────

class TestRenderer:
    def test_invoice_pdf_returns_valid_bytes(self):
        invoice = {
            "id": str(uuid.uuid4()), "school_id": str(SCHOOL),
            "student_id": str(uuid.uuid4()),
            "fee_structure_id": str(uuid.uuid4()),
            "total_amount": 950.0, "paid_amount": 200.0, "balance": 750.0,
            "currency": "USD", "due_date": "2026-06-01", "status": "PARTIAL",
            "created_at": "2026-05-19T08:00:00+00:00",
        }
        pdf = build_invoice_pdf(invoice=invoice,
                                 line_items=[{"label": "Tuition", "amount": 800},
                                             {"label": "Books", "amount": 150}])
        assert pdf.startswith(b"%PDF-1.4")
        assert pdf.endswith(b"%%EOF")
        assert b"Tuition" in pdf
        assert b"USD 950.00" in pdf

    def test_receipt_pdf_returns_valid_bytes(self):
        payment = {
            "id": str(uuid.uuid4()), "school_id": str(SCHOOL),
            "invoice_id": str(uuid.uuid4()),
            "amount": 400.0, "currency": "USD",
            "method": "ECOCASH", "reference": "EDU-XYZ",
            "paid_at": "2026-05-19T09:00:00+00:00",
            "created_at": "2026-05-19T09:00:00+00:00",
        }
        invoice = {
            "id": payment["invoice_id"], "student_id": str(uuid.uuid4()),
            "total_amount": 950.0, "paid_amount": 400.0, "balance": 550.0,
            "currency": "USD",
        }
        pdf = build_receipt_pdf(payment=payment, invoice=invoice)
        assert pdf.startswith(b"%PDF-1.4")
        assert pdf.endswith(b"%%EOF")
        assert b"ECOCASH" in pdf
        assert b"USD 400.00" in pdf

    def test_invoice_pdf_escapes_parens(self):
        invoice = {
            "id": "abc", "school_id": str(SCHOOL),
            "student_id": "stu", "fee_structure_id": "fs",
            "total_amount": 100.0, "paid_amount": 0.0, "balance": 100.0,
            "currency": "USD", "due_date": "2026-06-01", "status": "PENDING",
        }
        pdf = build_invoice_pdf(
            invoice=invoice,
            line_items=[{"label": "Tuition (Term 1)", "amount": 100}],
        )
        # `(` is escaped as `\(` inside PDF literal strings.
        assert b"Tuition \\(Term 1\\)" in pdf


# ────────────── Routes ──────────────

class TestPdfRoutes:
    def test_invoice_pdf_endpoint(self, client, db):
        inv, _ = _seed_invoice_with_payment(db)
        r = client.get(f"/api/v1/fees/invoices/{inv['id']}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-1.4")
        assert "inline" in r.headers["content-disposition"]

    def test_invoice_pdf_404_for_missing(self, client):
        r = client.get(f"/api/v1/fees/invoices/{uuid.uuid4()}/pdf")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"

    def test_receipt_pdf_endpoint(self, client, db):
        _inv, pay = _seed_invoice_with_payment(db)
        payment_id = pay["payment"]["id"]
        r = client.get(f"/api/v1/fees/payments/{payment_id}/receipt")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-1.4")
        assert b"ECOCASH" in r.content

    def test_receipt_pdf_404_for_missing(self, client):
        r = client.get(f"/api/v1/fees/payments/{uuid.uuid4()}/receipt")
        assert r.status_code == 404
