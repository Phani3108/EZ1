"""Phase 19b — uniqueness on (school_id, source_national_template_id).

Revision ID: 2026_05_28_024
Revises: 2026_05_27_023
Create Date: 2026-05-28

Closes audit finding H1: cross-school template adopt had a check-then-
insert race. Without a DB-level uniqueness constraint, a double-click on
the "Adopt" button created two local clones in `homework_templates` /
`lesson_plan_templates`. With this constraint in place, the second
insert raises `IntegrityError` and the handler can return the existing
row (idempotency).

The constraint is partial in spirit — it only matters for rows where
`source_national_template_id` is non-null (i.e. rows that came from the
Ministry catalog). Vanilla per-school templates without a national
source-id all hold NULL and SQLite/Postgres treat multiple NULLs as
distinct, so the constraint does not block normal template creation.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_28_024"
down_revision: Union[str, None] = "2026_05_27_023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_uq(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == name for c in insp.get_unique_constraints(table))


def upgrade() -> None:
    if not _has_uq("homework_templates", "uq_homework_template_school_source_natl"):
        with op.batch_alter_table("homework_templates") as b:
            b.create_unique_constraint(
                "uq_homework_template_school_source_natl",
                ["school_id", "source_national_template_id"],
            )
    if not _has_uq("lesson_plan_templates", "uq_lesson_plan_template_school_source_natl"):
        with op.batch_alter_table("lesson_plan_templates") as b:
            b.create_unique_constraint(
                "uq_lesson_plan_template_school_source_natl",
                ["school_id", "source_national_template_id"],
            )


def downgrade() -> None:
    if _has_uq("lesson_plan_templates", "uq_lesson_plan_template_school_source_natl"):
        with op.batch_alter_table("lesson_plan_templates") as b:
            b.drop_constraint(
                "uq_lesson_plan_template_school_source_natl",
                type_="unique",
            )
    if _has_uq("homework_templates", "uq_homework_template_school_source_natl"):
        with op.batch_alter_table("homework_templates") as b:
            b.drop_constraint(
                "uq_homework_template_school_source_natl",
                type_="unique",
            )
