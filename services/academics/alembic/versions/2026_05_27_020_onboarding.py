"""Phase 15 — Onboarding: drafts + School.is_live + first-time tracking

Revision ID: 2026_05_27_020
Revises: 2026_05_19_019
Create Date: 2026-05-27

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_27_020"
down_revision: Union[str, None] = "2026_05_19_019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return col in cols


def upgrade() -> None:
    if not _has("student_drafts"):
        op.create_table(
            "student_drafts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_code", sa.String(50), nullable=True),
            sa.Column("first_name", sa.String(255), nullable=False),
            sa.Column("last_name", sa.String(255), nullable=False),
            sa.Column("dob", sa.Date(), nullable=True),
            sa.Column("gender", sa.String(10), nullable=True),
            sa.Column("admission_date", sa.Date(), nullable=True),
            sa.Column("class_id", sa.String(36), nullable=True),
            sa.Column("parent_first_name", sa.String(255), nullable=True),
            sa.Column("parent_last_name", sa.String(255), nullable=True),
            sa.Column("parent_phone", sa.String(32), nullable=True),
            sa.Column("parent_email", sa.String(255), nullable=True),
            sa.Column("parent_relationship_type", sa.String(20), nullable=True),
            sa.Column("submitted_by_user_id", sa.String(36), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("review_status", sa.String(16), nullable=False,
                      server_default="pending"),
            sa.Column("reviewed_by_user_id", sa.String(36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.String(200), nullable=True),
            sa.Column("approved_student_id", sa.String(36), nullable=True),
        )
        op.create_index("ix_student_drafts_school_status", "student_drafts",
                        ["school_id", "review_status"])
        op.create_index("ix_student_drafts_submitted_by", "student_drafts",
                        ["submitted_by_user_id"])

    if not _has("invite_requests"):
        op.create_table(
            "invite_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("contact_phone", sa.String(32), nullable=True),
            sa.Column("target_resource_id", sa.String(36), nullable=True),
            sa.Column("target_resource_type", sa.String(32), nullable=True),
            sa.Column("extra", sa.String(500), nullable=True),
            sa.Column("request_status", sa.String(16), nullable=False,
                      server_default="pending"),
            sa.Column("identity_invitation_id", sa.String(36), nullable=True),
            sa.Column("last_error", sa.String(500), nullable=True),
            sa.Column("requested_by_user_id", sa.String(36), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_invite_requests_school_status",
                        "invite_requests", ["school_id", "request_status"])
        op.create_index("ix_invite_requests_role",
                        "invite_requests", ["role"])

    if not _has("parent_drafts"):
        op.create_table(
            "parent_drafts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("first_name", sa.String(255), nullable=False),
            sa.Column("last_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(32), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("relationship_type", sa.String(20), nullable=False,
                      server_default="GUARDIAN"),
            sa.Column("student_id", sa.String(36), nullable=True),
            sa.Column("submitted_by_user_id", sa.String(36), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("review_status", sa.String(16), nullable=False,
                      server_default="pending"),
            sa.Column("reviewed_by_user_id", sa.String(36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.String(200), nullable=True),
            sa.Column("approved_parent_id", sa.String(36), nullable=True),
        )
        op.create_index("ix_parent_drafts_school_status", "parent_drafts",
                        ["school_id", "review_status"])

    # Phase 15 / Go-Live gate on the School row. Default false so all
    # existing tenants are flipped manually by the admin via the
    # setup wizard. PostgreSQL: alter_column; SQLite: ignored.
    if not _has_col("schools", "is_live"):
        op.add_column("schools", sa.Column(
            "is_live", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ))
    if not _has_col("schools", "went_live_at"):
        op.add_column("schools", sa.Column(
            "went_live_at", sa.DateTime(timezone=True), nullable=True,
        ))


def downgrade() -> None:
    for t in ("invite_requests", "parent_drafts", "student_drafts"):
        if _has(t):
            op.drop_table(t)
    if _has_col("schools", "went_live_at"):
        op.drop_column("schools", "went_live_at")
    if _has_col("schools", "is_live"):
        op.drop_column("schools", "is_live")
