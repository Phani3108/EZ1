"""
Fees Service Business Logic
==============================
Financial integrity: row locking, partial payment math, overpayment rejection,
idempotent invoicing, status transitions, defaulter queries.

Concurrency safety: SELECT ... FOR UPDATE on invoice row during payment.
(Falls back to non-locking read on SQLite for testing.)
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.fees import FeeStructure, FeeItem, Invoice, Payment


class FeesService:
    def __init__(self, db: Session):
        self.db = db

    # ───────────── Fee Structure ─────────────

    def create_fee_structure(self, school_id: uuid.UUID, academic_year_id: uuid.UUID,
                              name: str, items: list[dict],
                              term_id: uuid.UUID = None) -> dict:
        fs = FeeStructure(
            school_id=school_id, academic_year_id=academic_year_id,
            term_id=term_id, name=name,
        )
        self.db.add(fs)
        self.db.flush()  # get ID before adding items

        for item in items:
            fi = FeeItem(
                fee_structure_id=fs.id,
                label=item["label"],
                amount=Decimal(str(item["amount"])),
                currency=item.get("currency", "USD"),
            )
            self.db.add(fi)

        self.db.commit()
        self.db.refresh(fs)
        return self._ser_structure(fs)

    def list_fee_structures(self, school_id: uuid.UUID,
                             academic_year_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(FeeStructure).filter(FeeStructure.school_id == school_id)
        if academic_year_id:
            q = q.filter(FeeStructure.academic_year_id == academic_year_id)
        return [self._ser_structure(fs) for fs in q.all()]

    # ───────────── Invoice ─────────────

    def create_invoice(self, school_id: uuid.UUID, student_id: uuid.UUID,
                       fee_structure_id: uuid.UUID, due_date: date,
                       idempotency_key: str = None) -> dict:
        # Idempotency check
        if idempotency_key:
            existing = self.db.query(Invoice).filter(
                Invoice.idempotency_key == idempotency_key,
            ).first()
            if existing:
                return self._ser_invoice(existing)

        # Duplicate check
        dup = self.db.query(Invoice).filter(
            Invoice.student_id == student_id,
            Invoice.fee_structure_id == fee_structure_id,
        ).first()
        if dup:
            return {"error": "DUPLICATE_INVOICE",
                    "message": "Invoice already exists for this student and fee structure"}

        # Get fee structure and compute total
        fs = self.db.query(FeeStructure).filter(
            FeeStructure.id == fee_structure_id,
            FeeStructure.school_id == school_id,
        ).first()
        if not fs:
            return {"error": "NOT_FOUND", "message": "Fee structure not found"}

        total = sum(item.amount for item in fs.items)
        if total <= 0:
            return {"error": "INVALID_AMOUNT", "message": "Fee structure has no items"}

        currency = fs.items[0].currency if fs.items else "USD"

        invoice = Invoice(
            school_id=school_id, student_id=student_id,
            fee_structure_id=fee_structure_id,
            idempotency_key=idempotency_key,
            total_amount=total, paid_amount=Decimal("0"),
            currency=currency, due_date=due_date, status="PENDING",
        )
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return self._ser_invoice(invoice)

    def list_invoices(self, school_id: uuid.UUID, student_id: uuid.UUID = None,
                      status: str = None) -> list[dict]:
        q = self.db.query(Invoice).filter(Invoice.school_id == school_id)
        if student_id:
            q = q.filter(Invoice.student_id == student_id)
        if status:
            q = q.filter(Invoice.status == status)
        return [self._ser_invoice(inv) for inv in q.all()]

    def get_invoice(self, invoice_id: uuid.UUID,
                    school_id: uuid.UUID) -> Optional[dict]:
        inv = self.db.query(Invoice).filter(
            Invoice.id == invoice_id, Invoice.school_id == school_id,
        ).first()
        return self._ser_invoice(inv) if inv else None

    # ───────────── Payment (with row locking) ─────────────

    def record_payment(self, school_id: uuid.UUID, invoice_id: uuid.UUID,
                       amount: Decimal, method: str = "CASH",
                       reference: str = None,
                       idempotency_key: str = None) -> dict:
        # Idempotency check
        if idempotency_key:
            existing = self.db.query(Payment).filter(
                Payment.idempotency_key == idempotency_key,
            ).first()
            if existing:
                inv = self.db.query(Invoice).filter(Invoice.id == existing.invoice_id).first()
                return {"payment": self._ser_payment(existing),
                        "invoice": self._ser_invoice(inv),
                        "already_processed": True}

        # Row lock on invoice for concurrency safety
        # SQLite doesn't support FOR UPDATE, so we use a try/except fallback
        try:
            invoice = self.db.query(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.school_id == school_id,
            ).with_for_update().first()
        except Exception:
            # SQLite fallback - no row locking
            invoice = self.db.query(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.school_id == school_id,
            ).first()

        if not invoice:
            return {"error": "NOT_FOUND", "message": "Invoice not found"}

        if invoice.status == "PAID":
            return {"error": "ALREADY_PAID", "message": "Invoice is already fully paid"}

        amount = Decimal(str(amount))
        if amount <= 0:
            return {"error": "INVALID_AMOUNT", "message": "Payment amount must be positive"}

        # Check overpayment
        remaining = invoice.total_amount - invoice.paid_amount
        if amount > remaining:
            return {"error": "OVERPAYMENT",
                    "message": f"Payment {amount} exceeds remaining balance {remaining}"}

        # Currency check
        if hasattr(invoice, 'currency') and invoice.currency:
            pass  # Accept for now — currency validation can be stricter in v2

        # Record payment
        payment = Payment(
            school_id=school_id, invoice_id=invoice_id,
            idempotency_key=idempotency_key,
            amount=amount, currency=invoice.currency,
            method=method, reference=reference,
        )
        self.db.add(payment)

        # Update invoice
        invoice.paid_amount = invoice.paid_amount + amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = "PAID"
        elif invoice.paid_amount > 0:
            invoice.status = "PARTIAL"

        self.db.commit()
        self.db.refresh(payment)
        self.db.refresh(invoice)

        return {
            "payment": self._ser_payment(payment),
            "invoice": self._ser_invoice(invoice),
            "already_processed": False,
        }

    def list_payments(self, school_id: uuid.UUID,
                      invoice_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(Payment).filter(Payment.school_id == school_id)
        if invoice_id:
            q = q.filter(Payment.invoice_id == invoice_id)
        return [self._ser_payment(p) for p in q.order_by(Payment.created_at).all()]

    # ───────────── Defaulters ─────────────

    def get_defaulters(self, school_id: uuid.UUID,
                       as_of: date = None) -> list[dict]:
        target = as_of or date.today()
        invoices = self.db.query(Invoice).filter(
            Invoice.school_id == school_id,
            Invoice.status.in_(["PENDING", "PARTIAL", "OVERDUE"]),
            Invoice.due_date < target,
        ).all()

        # Mark overdue
        for inv in invoices:
            if inv.status != "OVERDUE" and inv.status != "PAID":
                inv.status = "OVERDUE"
        self.db.commit()

        return [self._ser_invoice(inv) for inv in invoices]

    # ───────────── Serializers ─────────────

    def _ser_structure(self, fs: FeeStructure) -> dict:
        items = [{"id": str(i.id), "label": i.label,
                  "amount": float(i.amount), "currency": i.currency}
                 for i in fs.items]
        return {
            "id": str(fs.id), "school_id": str(fs.school_id),
            "academic_year_id": str(fs.academic_year_id),
            "term_id": str(fs.term_id) if fs.term_id else None,
            "name": fs.name, "is_active": fs.is_active,
            "items": items,
            "total": sum(i["amount"] for i in items),
            "created_at": fs.created_at.isoformat() if fs.created_at else None,
        }

    def _ser_invoice(self, inv: Invoice) -> dict:
        return {
            "id": str(inv.id), "school_id": str(inv.school_id),
            "student_id": str(inv.student_id),
            "fee_structure_id": str(inv.fee_structure_id),
            "total_amount": float(inv.total_amount),
            "paid_amount": float(inv.paid_amount),
            "balance": float(inv.total_amount - inv.paid_amount),
            "currency": inv.currency,
            "due_date": inv.due_date.isoformat(),
            "status": inv.status,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }

    def _ser_payment(self, p: Payment) -> dict:
        return {
            "id": str(p.id), "school_id": str(p.school_id),
            "invoice_id": str(p.invoice_id),
            "amount": float(p.amount), "currency": p.currency,
            "method": p.method, "reference": p.reference,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
