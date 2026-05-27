"""Finance / inventory / operations models — Phase 13c.

  * A-008 — `Expense`, `VendorPayment`, `CapitalProject`. The full
    fees/invoices ledger lives in services/finance/; this is the
    OPERATIONS finance: non-tuition outflows (utilities, repairs,
    grants, capital builds).
  * A-009 — `Asset`, `AssetMovement` — inventory with movement
    log (assigned-to / returned / disposed).
  * A-011 — `LibraryBook`, `BookLoan` — library catalog + check-out.
  * A-014 — `Visitor` — sign-in log (visitor management).

The actual fee + payment ledger remains in `services/finance/`.
A-008 lives here in academics because school-operational finance
(expenses, vendors, capital projects) sits next to the rest of the
school's domain.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Date, Integer, Boolean, Text,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── A-008 — Expenses + vendors + capital projects ────────────────


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expense_school_date", "school_id", "incurred_on"),
        Index("ix_expense_school_category", "school_id", "category"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    # utilities | repairs | supplies | salaries_topup | transport |
    # food | events | other
    category = Column(String(32), nullable=False, default="other")
    description = Column(String(500), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    incurred_on = Column(Date, nullable=False)
    # Optional vendor name for downstream rollups.
    vendor_name = Column(String(255), nullable=True)
    # Optional attachment id (receipt scan).
    attachment_id = Column(UUID_STR, nullable=True)
    recorded_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class VendorPayment(Base):
    __tablename__ = "vendor_payments"
    __table_args__ = (
        Index("ix_vendor_pay_school", "school_id", "paid_on"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    vendor_name = Column(String(255), nullable=False)
    invoice_reference = Column(String(120), nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    paid_on = Column(Date, nullable=False)
    # cash | bank_transfer | ecocash | check | other
    method = Column(String(32), nullable=False, default="bank_transfer")
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CapitalProject(Base):
    __tablename__ = "capital_projects"
    __table_args__ = (
        Index("ix_capital_school_status", "school_id", "status"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    budget_cents = Column(Integer, nullable=False)
    spent_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    # planning | in_progress | completed | cancelled
    status = Column(String(16), nullable=False, default="planning")
    starts_on = Column(Date, nullable=True)
    target_completion = Column(Date, nullable=True)
    completed_on = Column(Date, nullable=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-009 — Asset management ─────────────────────────────────────


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("school_id", "asset_tag",
                         name="uq_asset_tag"),
        Index("ix_asset_school_category", "school_id", "category"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    asset_tag = Column(String(64), nullable=False)
    # furniture | electronics | textbook | lab_equipment | sports |
    # transport | other
    category = Column(String(32), nullable=False, default="other")
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    serial_number = Column(String(128), nullable=True)
    purchase_date = Column(Date, nullable=True)
    purchase_cost_cents = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    # in_stock | assigned | maintenance | disposed | lost
    status = Column(String(16), nullable=False, default="in_stock")
    assigned_to_user_id = Column(UUID_STR, nullable=True)
    assigned_to_location = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow, onupdate=_utcnow, nullable=False,
    )


class AssetMovement(Base):
    """Append-only log of every assign / return / dispose action
    on an Asset."""
    __tablename__ = "asset_movements"
    __table_args__ = (
        Index("ix_movement_asset", "asset_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    asset_id = Column(UUID_STR, nullable=False)
    # assigned | returned | maintenance | disposed | lost | found
    action = Column(String(16), nullable=False)
    actor_user_id = Column(UUID_STR, nullable=False)
    target_user_id = Column(UUID_STR, nullable=True)
    target_location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-011 — Library ──────────────────────────────────────────────


class LibraryBook(Base):
    __tablename__ = "library_books"
    __table_args__ = (
        Index("ix_book_school", "school_id"),
        Index("ix_book_isbn", "school_id", "isbn"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    author = Column(String(255), nullable=True)
    isbn = Column(String(20), nullable=True)
    category = Column(String(64), nullable=True)
    total_copies = Column(Integer, nullable=False, default=1)
    available_copies = Column(Integer, nullable=False, default=1)
    shelf_location = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class BookLoan(Base):
    __tablename__ = "book_loans"
    __table_args__ = (
        Index("ix_loan_book", "book_id"),
        Index("ix_loan_borrower", "borrower_user_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    book_id = Column(UUID_STR, nullable=False)
    borrower_user_id = Column(UUID_STR, nullable=False)
    issued_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    due_on = Column(Date, nullable=False)
    returned_at = Column(DateTime(timezone=True), nullable=True)
    # Status derived from returned_at + due_on at read time; we don't
    # store it to avoid the consistency burden.


# ─── A-014 — Visitor management ───────────────────────────────────


class Visitor(Base):
    __tablename__ = "visitors"
    __table_args__ = (
        Index("ix_visitor_school_date", "school_id", "signed_in_at"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    # parent | vendor | inspector | guest | contractor | other
    visitor_type = Column(String(16), nullable=False, default="guest")
    purpose = Column(String(255), nullable=False)
    visiting_user_id = Column(UUID_STR, nullable=True)  # who they're seeing
    visitor_badge_number = Column(String(32), nullable=True)
    signed_in_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    signed_out_at = Column(DateTime(timezone=True), nullable=True)
    signed_in_by_user_id = Column(UUID_STR, nullable=False)
