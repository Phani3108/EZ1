"""compliance + health records (Phase 13b)

Revision ID: 2026_05_19_016
Revises: 2026_05_19_015
Create Date: 2026-05-27

Compliance report templates + submissions + student health records.
Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_016"
down_revision: Union[str, None] = "2026_05_19_015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("compliance_report_templates"):
        op.create_table(
            "compliance_report_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("cadence", sa.String(16), nullable=False, server_default="annual"),
            sa.Column("schema_json", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "code",
                                name="uq_compliance_template_code"),
        )

    if not _has("compliance_report_submissions"):
        op.create_table(
            "compliance_report_submissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("template_id", sa.String(36), nullable=False),
            sa.Column("period_label", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("attachment_id", sa.String(36), nullable=True),
            sa.Column("submitted_by_user_id", sa.String(36), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_notes", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "school_id", "template_id", "period_label",
                name="uq_compliance_submission_period",
            ),
        )
        op.create_index("ix_compliance_school_period",
                        "compliance_report_submissions",
                        ["school_id", "period_label"])

    if not _has("health_records"):
        op.create_table(
            "health_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("allergies", sa.Text(), nullable=True),
            sa.Column("chronic_conditions", sa.Text(), nullable=True),
            sa.Column("medications", sa.Text(), nullable=True),
            sa.Column("emergency_contact_name", sa.String(255), nullable=True),
            sa.Column("emergency_contact_relation", sa.String(64), nullable=True),
            sa.Column("emergency_contact_phone", sa.String(20), nullable=True),
            sa.Column("vaccinations_json", sa.Text(), nullable=True),
            sa.Column("blood_group", sa.String(8), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("updated_by_user_id", sa.String(36), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("student_id", name="uq_health_record_student"),
        )
        op.create_index("ix_health_school", "health_records", ["school_id"])


def downgrade() -> None:
    for t in (
        "health_records",
        "compliance_report_submissions",
        "compliance_report_templates",
    ):
        if _has(t):
            op.drop_table(t)
