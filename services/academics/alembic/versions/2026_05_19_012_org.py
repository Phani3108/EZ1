"""org tables + co-teacher relaxation (Phase 11f)

Revision ID: 2026_05_19_012
Revises: 2026_05_19_011
Create Date: 2026-05-26

  * Relax class_teacher_assignments unique constraint to enable
    co-teacher mode (T-016): now keyed by (school, class, year,
    teacher) instead of (school, class, year).
  * Add HoD assignments (T-017), CPD records (T-018), self-evaluation
    forms (T-019).

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_012"
down_revision: Union[str, None] = "2026_05_19_011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_constraint(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(c.get("name") == name
               for c in inspector.get_unique_constraints(table))


def upgrade() -> None:
    # T-016: class_teacher_assignments constraint swap
    if _has_constraint("class_teacher_assignments", "uq_class_teacher_year"):
        with op.batch_alter_table("class_teacher_assignments") as batch_op:
            batch_op.drop_constraint("uq_class_teacher_year", type_="unique")
    if not _has_constraint(
        "class_teacher_assignments", "uq_class_teacher_year_teacher",
    ):
        with op.batch_alter_table("class_teacher_assignments") as batch_op:
            batch_op.create_unique_constraint(
                "uq_class_teacher_year_teacher",
                ["school_id", "class_id", "academic_year_id", "teacher_user_id"],
            )

    # T-017
    if not _has_table("hod_assignments"):
        op.create_table(
            "hod_assignments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("subject_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("granted_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("school_id", "subject_id", "user_id",
                                name="uq_hod_subject_user"),
        )
        op.create_index("ix_hod_school_subject", "hod_assignments",
                        ["school_id", "subject_id"])
        op.create_index("ix_hod_school_user", "hod_assignments",
                        ["school_id", "user_id"])

    # T-018
    if not _has_table("cpd_records"):
        op.create_table(
            "cpd_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("academic_year_id", sa.String(36), nullable=True),
            sa.Column("category", sa.String(32), nullable=False,
                      server_default="other"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("provider", sa.String(200), nullable=True),
            sa.Column("completed_on", sa.Date(), nullable=False),
            sa.Column("hours", sa.Numeric(5, 2), nullable=False,
                      server_default="0"),
            sa.Column("certificate_uri", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_cpd_school_user", "cpd_records",
                        ["school_id", "user_id"])
        op.create_index("ix_cpd_school_year", "cpd_records",
                        ["school_id", "academic_year_id"])

    # T-019
    if not _has_table("self_evaluation_forms"):
        op.create_table(
            "self_evaluation_forms",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("term_id", sa.String(36), nullable=False),
            sa.Column("responses_json", sa.Text(), nullable=False),
            sa.Column("overall_reflection", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "user_id", "term_id",
                                name="uq_self_eval_user_term"),
        )
        op.create_index("ix_self_eval_school_term", "self_evaluation_forms",
                        ["school_id", "term_id"])


def downgrade() -> None:
    for t in ("self_evaluation_forms", "cpd_records", "hod_assignments"):
        if _has_table(t):
            op.drop_table(t)
    if _has_constraint(
        "class_teacher_assignments", "uq_class_teacher_year_teacher",
    ):
        with op.batch_alter_table("class_teacher_assignments") as batch_op:
            batch_op.drop_constraint(
                "uq_class_teacher_year_teacher", type_="unique",
            )
    if not _has_constraint("class_teacher_assignments", "uq_class_teacher_year"):
        with op.batch_alter_table("class_teacher_assignments") as batch_op:
            batch_op.create_unique_constraint(
                "uq_class_teacher_year",
                ["school_id", "class_id", "academic_year_id"],
            )
