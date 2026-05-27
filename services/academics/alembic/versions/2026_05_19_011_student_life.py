"""student-life tables (Phase 11e)

Revision ID: 2026_05_19_011
Revises: 2026_05_19_010
Create Date: 2026-05-26

behavior_incidents (T-004), substitute_grants (T-006),
homework + homework_submissions (T-003). Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_011"
down_revision: Union[str, None] = "2026_05_19_010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("behavior_incidents"):
        op.create_table(
            "behavior_incidents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("class_id", sa.String(36), nullable=True),
            sa.Column("reported_by", sa.String(36), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False,
                      server_default="minor"),
            sa.Column("category", sa.String(32), nullable=False,
                      server_default="other"),
            sa.Column("summary", sa.String(500), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_incident_school_student", "behavior_incidents",
                        ["school_id", "student_id"])
        op.create_index("ix_incident_school_date", "behavior_incidents",
                        ["school_id", "occurred_at"])

    if not _has("substitute_grants"):
        op.create_table(
            "substitute_grants",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("absent_teacher_user_id", sa.String(36), nullable=False),
            sa.Column("grantee_user_id", sa.String(36), nullable=False),
            sa.Column("class_ids_json", sa.Text(), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("granted_by_user_id", sa.String(36), nullable=False),
            sa.Column("reason", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_by_user_id", sa.String(36), nullable=True),
        )
        op.create_index("ix_substitute_active", "substitute_grants",
                        ["school_id", "ends_at", "revoked_at"])
        op.create_index("ix_substitute_grantee", "substitute_grants",
                        ["school_id", "grantee_user_id"])

    if not _has("homework"):
        op.create_table(
            "homework",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("class_id", sa.String(36), nullable=False),
            sa.Column("subject_id", sa.String(36), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("assigned_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_homework_school_class", "homework",
                        ["school_id", "class_id"])
        op.create_index("ix_homework_due", "homework",
                        ["school_id", "due_date"])

    if not _has("homework_submissions"):
        op.create_table(
            "homework_submissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("homework_id", sa.String(36),
                      sa.ForeignKey("homework.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("grade_marks", sa.String(20), nullable=True),
            sa.Column("grade_remarks", sa.String(500), nullable=True),
            sa.Column("graded_by", sa.String(36), nullable=True),
            sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint(
                "homework_id", "student_id",
                name="uq_homework_submission_student",
            ),
        )


def downgrade() -> None:
    for t in (
        "homework_submissions", "homework",
        "substitute_grants", "behavior_incidents",
    ):
        if _has(t):
            op.drop_table(t)
