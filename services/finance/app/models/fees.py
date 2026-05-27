"""
Fees Service ORM Models
========================
FeeStructure, FeeItem, Invoice, Payment

Key constraints:
- (student_id, fee_structure_id) unique for Invoice
- Payment is append-only
- Invoice status enum: PENDING, PARTIAL, PAID, OVERDUE
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, ForeignKey,
    UniqueConstraint, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    term_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    items = relationship("FeeItem", back_populates="fee_structure", cascade="all, delete-orphan")


class FeeItem(Base):
    __tablename__ = "fee_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fee_structure_id = Column(UUID(as_uuid=True), ForeignKey("fee_structures.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    label = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    fee_structure = relationship("FeeStructure", back_populates="items")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("student_id", "fee_structure_id", name="uq_invoice_student_structure"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    fee_structure_id = Column(UUID(as_uuid=True), ForeignKey("fee_structures.id"),
                              nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=True, unique=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    fee_structure = relationship("FeeStructure")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=True, unique=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    method = Column(String(50), nullable=False, default="CASH")
    reference = Column(String(255), nullable=True)
    paid_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("Invoice", back_populates="payments")


class PaymentTransaction(Base):
    """
    Tracks a single Paynow (or other gateway) attempt against an invoice.

    Lifecycle:
      INITIATED → SENT      — gateway accepted the request, user redirected
                 → FAILED   — gateway rejected (config/network/validation)
      SENT      → PAID      — webhook confirmed payment (Payment row created)
                 → CANCELLED, FAILED, EXPIRED — terminal failure states

    The `reference` column is the unique merchant reference we send to Paynow
    (`EDU-<inv8>-<rand6>`). Webhooks come back keyed on that reference, which
    is how we look the transaction up. `paynow_reference` is the gateway's
    own ID, returned in the webhook + poll response.
    """
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"),
                        nullable=True, index=True)

    provider = Column(String(50), nullable=False, default="PAYNOW")
    method = Column(String(50), nullable=False)  # ECOCASH | ONEMONEY | TELECASH | MUKURU | BANK
    reference = Column(String(64), nullable=False, unique=True, index=True)
    paynow_reference = Column(String(255), nullable=True, index=True)
    poll_url = Column(String(512), nullable=True)
    instructions = Column(String(512), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    phone = Column(String(20), nullable=True)

    # INITIATED | SENT | PAID | CANCELLED | FAILED | EXPIRED
    status = Column(String(20), nullable=False, default="INITIATED", index=True)
    last_error = Column(String(512), nullable=True)

    # Idempotency: if the gateway retries the webhook for the same payment,
    # we recognise it via the (reference, paynow_reference, amount) tuple
    # and skip the second insert. Stored explicitly for auditability.
    idempotency_key = Column(String(255), nullable=True, unique=True)

    initiated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("Invoice")
    payment = relationship("Payment")
