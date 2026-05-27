"""staff + HR + admissions + transfers (Phase 13a)

Revision ID: 2026_05_19_015
Revises: 2026_05_19_014
Create Date: 2026-05-27

7-table batch for the principal's operational surface. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_015"
down_revision: Union[str, None] = "2026_05_19_014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("non_teaching_staff"):
        op.create_table(
            "non_teaching_staff",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("role_category", sa.String(32), nullable=False, server_default="other"),
            sa.Column("staff_code", sa.String(50), nullable=False),
            sa.Column("first_name", sa.String(255), nullable=False),
            sa.Column("last_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("user_id", sa.String(36), nullable=True, unique=True),
            sa.Column("hired_on", sa.Date(), nullable=True),
            sa.Column("terminated_on", sa.Date(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "staff_code", name="uq_non_teaching_staff_code"),
        )
        op.create_index("ix_nts_school_role", "non_teaching_staff",
                        ["school_id", "role_category"])

    if not _has("leave_requests"):
        op.create_table(
            "leave_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("leave_type", sa.String(32), nullable=False, server_default="annual"),
            sa.Column("starts_on", sa.Date(), nullable=False),
            sa.Column("ends_on", sa.Date(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column("decided_by_user_id", sa.String(36), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("decision_notes", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_leave_school_user", "leave_requests",
                        ["school_id", "user_id"])
        op.create_index("ix_leave_school_status", "leave_requests",
                        ["school_id", "status"])

    if not _has("employment_contracts"):
        op.create_table(
            "employment_contracts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("role_title", sa.String(120), nullable=False),
            sa.Column("salary_band", sa.String(32), nullable=True),
            sa.Column("starts_on", sa.Date(), nullable=False),
            sa.Column("ends_on", sa.Date(), nullable=True),
            sa.Column("attachment_id", sa.String(36), nullable=True),
            sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("termination_reason", sa.String(500), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_contract_school_user", "employment_contracts",
                        ["school_id", "user_id"])

    if not _has("salary_slips"):
        op.create_table(
            "salary_slips",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("period_year", sa.Integer(), nullable=False),
            sa.Column("period_month", sa.Integer(), nullable=False),
            sa.Column("gross_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("deductions_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("net_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("attachment_id", sa.String(36), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "school_id", "user_id", "period_year", "period_month",
                name="uq_salary_slip_period",
            ),
        )
        op.create_index("ix_salary_school_user", "salary_slips",
                        ["school_id", "user_id"])

    if not _has("performance_reviews"):
        op.create_table(
            "performance_reviews",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("reviewer_user_id", sa.String(36), nullable=False),
            sa.Column("period_label", sa.String(80), nullable=False),
            sa.Column("overall_rating", sa.String(32), nullable=False),
            sa.Column("criteria_json", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_perf_school_user", "performance_reviews",
                        ["school_id", "user_id"])

    if not _has("admission_applications"):
        op.create_table(
            "admission_applications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("applicant_first_name", sa.String(255), nullable=False),
            sa.Column("applicant_last_name", sa.String(255), nullable=False),
            sa.Column("applicant_dob", sa.Date(), nullable=True),
            sa.Column("applicant_gender", sa.String(10), nullable=True),
            sa.Column("guardian_first_name", sa.String(255), nullable=False),
            sa.Column("guardian_last_name", sa.String(255), nullable=False),
            sa.Column("guardian_phone", sa.String(20), nullable=False),
            sa.Column("guardian_email", sa.String(255), nullable=True),
            sa.Column("target_class_label", sa.String(80), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="submitted"),
            sa.Column("decided_by_user_id", sa.String(36), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("decision_notes", sa.String(500), nullable=True),
            sa.Column("student_id", sa.String(36), nullable=True, unique=True),
            sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_admission_school_status", "admission_applications",
                        ["school_id", "status"])

    if not _has("student_transfers"):
        op.create_table(
            "student_transfers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("direction", sa.String(8), nullable=False),
            sa.Column("counterparty_school_name", sa.String(255), nullable=True),
            sa.Column("counterparty_school_contact", sa.String(255), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("transcript_attachment_id", sa.String(36), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("initiated_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_transfer_school_direction", "student_transfers",
                        ["school_id", "direction"])
        op.create_index("ix_transfer_student", "student_transfers", ["student_id"])


def downgrade() -> None:
    for t in (
        "student_transfers", "admission_applications",
        "performance_reviews", "salary_slips",
        "employment_contracts", "leave_requests",
        "non_teaching_staff",
    ):
        if _has(t):
            op.drop_table(t)
