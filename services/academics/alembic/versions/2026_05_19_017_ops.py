"""ops batch — finance / inventory / library / visitors (Phase 13c)

Revision ID: 2026_05_19_017
Revises: 2026_05_19_016
Create Date: 2026-05-27

8-table batch. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_017"
down_revision: Union[str, None] = "2026_05_19_016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:  # noqa: C901
    if not _has("expenses"):
        op.create_table(
            "expenses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("category", sa.String(32), nullable=False, server_default="other"),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("incurred_on", sa.Date(), nullable=False),
            sa.Column("vendor_name", sa.String(255), nullable=True),
            sa.Column("attachment_id", sa.String(36), nullable=True),
            sa.Column("recorded_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_expense_school_date", "expenses", ["school_id", "incurred_on"])
        op.create_index("ix_expense_school_category", "expenses",
                        ["school_id", "category"])

    if not _has("vendor_payments"):
        op.create_table(
            "vendor_payments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("vendor_name", sa.String(255), nullable=False),
            sa.Column("invoice_reference", sa.String(120), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("paid_on", sa.Date(), nullable=False),
            sa.Column("method", sa.String(32), nullable=False, server_default="bank_transfer"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("recorded_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_vendor_pay_school", "vendor_payments",
                        ["school_id", "paid_on"])

    if not _has("capital_projects"):
        op.create_table(
            "capital_projects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("budget_cents", sa.Integer(), nullable=False),
            sa.Column("spent_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(16), nullable=False, server_default="planning"),
            sa.Column("starts_on", sa.Date(), nullable=True),
            sa.Column("target_completion", sa.Date(), nullable=True),
            sa.Column("completed_on", sa.Date(), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_capital_school_status", "capital_projects",
                        ["school_id", "status"])

    if not _has("assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("asset_tag", sa.String(64), nullable=False),
            sa.Column("category", sa.String(32), nullable=False, server_default="other"),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("serial_number", sa.String(128), nullable=True),
            sa.Column("purchase_date", sa.Date(), nullable=True),
            sa.Column("purchase_cost_cents", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(16), nullable=False, server_default="in_stock"),
            sa.Column("assigned_to_user_id", sa.String(36), nullable=True),
            sa.Column("assigned_to_location", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "asset_tag", name="uq_asset_tag"),
        )
        op.create_index("ix_asset_school_category", "assets",
                        ["school_id", "category"])

    if not _has("asset_movements"):
        op.create_table(
            "asset_movements",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("asset_id", sa.String(36), nullable=False),
            sa.Column("action", sa.String(16), nullable=False),
            sa.Column("actor_user_id", sa.String(36), nullable=False),
            sa.Column("target_user_id", sa.String(36), nullable=True),
            sa.Column("target_location", sa.String(255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_movement_asset", "asset_movements", ["asset_id"])

    if not _has("library_books"):
        op.create_table(
            "library_books",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("author", sa.String(255), nullable=True),
            sa.Column("isbn", sa.String(20), nullable=True),
            sa.Column("category", sa.String(64), nullable=True),
            sa.Column("total_copies", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("available_copies", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("shelf_location", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_book_school", "library_books", ["school_id"])
        op.create_index("ix_book_isbn", "library_books", ["school_id", "isbn"])

    if not _has("book_loans"):
        op.create_table(
            "book_loans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("book_id", sa.String(36), nullable=False),
            sa.Column("borrower_user_id", sa.String(36), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("due_on", sa.Date(), nullable=False),
            sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_loan_book", "book_loans", ["book_id"])
        op.create_index("ix_loan_borrower", "book_loans", ["borrower_user_id"])

    if not _has("visitors"):
        op.create_table(
            "visitors",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("visitor_type", sa.String(16), nullable=False, server_default="guest"),
            sa.Column("purpose", sa.String(255), nullable=False),
            sa.Column("visiting_user_id", sa.String(36), nullable=True),
            sa.Column("visitor_badge_number", sa.String(32), nullable=True),
            sa.Column("signed_in_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("signed_out_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signed_in_by_user_id", sa.String(36), nullable=False),
        )
        op.create_index("ix_visitor_school_date", "visitors",
                        ["school_id", "signed_in_at"])


def downgrade() -> None:
    for t in (
        "visitors", "book_loans", "library_books",
        "asset_movements", "assets",
        "capital_projects", "vendor_payments", "expenses",
    ):
        if _has(t):
            op.drop_table(t)
