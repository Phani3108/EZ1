"""community batch — policy docs, sponsors, alumni (Phase 13d)

Revision ID: 2026_05_19_018
Revises: 2026_05_19_017
Create Date: 2026-05-27

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_018"
down_revision: Union[str, None] = "2026_05_19_017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("policy_documents"):
        op.create_table(
            "policy_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("category", sa.String(32), nullable=False, server_default="other"),
            sa.Column("attachment_id", sa.String(36), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("visible_to_parents", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "code", "version",
                                name="uq_policy_code_version"),
        )
        op.create_index("ix_policy_school", "policy_documents", ["school_id"])

    if not _has("sponsors"):
        op.create_table(
            "sponsors",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("sponsor_type", sa.String(16), nullable=False, server_default="other"),
            sa.Column("contact_name", sa.String(255), nullable=True),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("contact_phone", sa.String(20), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "name", name="uq_sponsor_name"),
        )

    if not _has("sponsorships"):
        op.create_table(
            "sponsorships",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("sponsor_id", sa.String(36), nullable=False),
            sa.Column("purpose", sa.String(32), nullable=False, server_default="other"),
            sa.Column("committed_cents", sa.Integer(), nullable=False),
            sa.Column("received_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("starts_on", sa.Date(), nullable=True),
            sa.Column("ends_on", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sponsorship_school_status", "sponsorships",
                        ["school_id", "status"])
        op.create_index("ix_sponsorship_sponsor", "sponsorships", ["sponsor_id"])

    if not _has("alumni"):
        op.create_table(
            "alumni",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("graduation_year", sa.Integer(), nullable=False),
            sa.Column("final_class_label", sa.String(80), nullable=True),
            sa.Column("current_email", sa.String(255), nullable=True),
            sa.Column("current_phone", sa.String(20), nullable=True),
            sa.Column("current_occupation", sa.String(255), nullable=True),
            sa.Column("current_university", sa.String(255), nullable=True),
            sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "student_id", name="uq_alumnus_student"),
        )
        op.create_index("ix_alumni_school", "alumni", ["school_id"])


def downgrade() -> None:
    for t in ("alumni", "sponsorships", "sponsors", "policy_documents"):
        if _has(t):
            op.drop_table(t)
