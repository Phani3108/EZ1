"""Phase 18b — Ministry-distributed (cross-school) templates.

Revision ID: 2026_05_27_023
Revises: 2026_05_27_022
Create Date: 2026-05-27

Adds:
  * `national_homework_templates`
  * `national_lesson_plan_templates`
  * `homework_templates.source_national_template_id` (nullable UUID_STR)
  * `lesson_plan_templates.source_national_template_id` (nullable UUID_STR)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_27_023"
down_revision: Union[str, None] = "2026_05_27_022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    if table not in sa.inspect(bind).get_table_names():
        return False
    return col in [c["name"] for c in sa.inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_table("national_homework_templates"):
        op.create_table(
            "national_homework_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("subject_code", sa.String(64), nullable=True),
            sa.Column("topic_codes", sa.Text(), nullable=True),
            sa.Column("grade_levels", sa.Text(), nullable=True),
            sa.Column("default_due_days", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "code", name="uq_national_homework_template_code",
            ),
        )
        op.create_index(
            "ix_national_homework_templates_published",
            "national_homework_templates", ["published_at"],
        )

    if not _has_table("national_lesson_plan_templates"):
        op.create_table(
            "national_lesson_plan_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("objectives", sa.Text(), nullable=True),
            sa.Column("activities", sa.Text(), nullable=True),
            sa.Column("resources", sa.Text(), nullable=True),
            sa.Column("suggested_period_number", sa.Integer(), nullable=True),
            sa.Column("subject_code", sa.String(64), nullable=True),
            sa.Column("topic_codes", sa.Text(), nullable=True),
            sa.Column("grade_levels", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "code", name="uq_national_lesson_plan_template_code",
            ),
        )
        op.create_index(
            "ix_national_lesson_plan_templates_published",
            "national_lesson_plan_templates", ["published_at"],
        )

    if not _has_col("homework_templates", "source_national_template_id"):
        op.add_column(
            "homework_templates",
            sa.Column(
                "source_national_template_id", sa.String(36), nullable=True,
            ),
        )
        op.create_index(
            "ix_homework_templates_source_national",
            "homework_templates", ["source_national_template_id"],
        )

    if not _has_col("lesson_plan_templates", "source_national_template_id"):
        op.add_column(
            "lesson_plan_templates",
            sa.Column(
                "source_national_template_id", sa.String(36), nullable=True,
            ),
        )
        op.create_index(
            "ix_lesson_plan_templates_source_national",
            "lesson_plan_templates", ["source_national_template_id"],
        )


def downgrade() -> None:
    if _has_col("lesson_plan_templates", "source_national_template_id"):
        op.drop_index(
            "ix_lesson_plan_templates_source_national",
            table_name="lesson_plan_templates",
        )
        op.drop_column(
            "lesson_plan_templates", "source_national_template_id",
        )
    if _has_col("homework_templates", "source_national_template_id"):
        op.drop_index(
            "ix_homework_templates_source_national",
            table_name="homework_templates",
        )
        op.drop_column(
            "homework_templates", "source_national_template_id",
        )
    if _has_table("national_lesson_plan_templates"):
        op.drop_index(
            "ix_national_lesson_plan_templates_published",
            table_name="national_lesson_plan_templates",
        )
        op.drop_table("national_lesson_plan_templates")
    if _has_table("national_homework_templates"):
        op.drop_index(
            "ix_national_homework_templates_published",
            table_name="national_homework_templates",
        )
        op.drop_table("national_homework_templates")
