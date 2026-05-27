"""attendance period support (Phase 11a / T-002)

Revision ID: 2026_05_19_008
Revises: 2026_05_19_007
Create Date: 2026-05-26

Adds `period_number INTEGER NOT NULL DEFAULT 0` to `attendance_records`
and replaces the `(school_id, student_id, date)` unique constraint with
a period-aware `(school_id, student_id, date, period_number)` one.

Sentinel convention:
  * `period_number = 0` → daily / homeroom / all-day mark. This is the
    legacy mode every existing row gets backfilled into and what primary
    schools (single homeroom per day) keep using.
  * `period_number ≥ 1` → a specific period in the school's schedule.
    Secondary schools take attendance per period; each (student, date,
    period) is its own row.

Why a sentinel instead of NULL: with NULL, the unique constraint becomes
`(school_id, student_id, date, period_number)` where two rows with NULL
period_number for the same student/date would BOTH be allowed (NULL ≠
NULL in SQL unique-constraint semantics). The whole point of the
constraint is preventing duplicate marks — keep it strict by using a
non-null sentinel.

Why integer and not a `periods` table FK: Option D in the Phase 11a
design debate — the metadata-bearing `periods` table comes with T-010
(calendar / lesson plans, Phase 11d) where it has real consumers. Until
then, `period_number` carries enough information for the UX (a teacher
selecting "Period 3" maps cleanly to integer 3), and the promotion path
to a UUID FK is documented in the task entry.

Idempotent — safe to re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_008"
down_revision: Union[str, None] = "2026_05_19_007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_constraint(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for c in inspector.get_unique_constraints(table):
        if c.get("name") == name:
            return True
    return False


def upgrade() -> None:
    # SQLite (test environment) cannot ALTER TABLE to drop constraints,
    # so we use a batch migration which rebuilds the table transparently.
    # Postgres takes the direct path. Both arrive at the same end state.
    if not _has_column("attendance_records", "period_number"):
        with op.batch_alter_table("attendance_records") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "period_number",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )

    # Swap the unique constraint. Old one (if present) was on three columns;
    # new one is on four. We do this in a separate batch op so SQLite reseats
    # the schema after the column add.
    if _has_constraint("attendance_records", "uq_attendance_student_date"):
        with op.batch_alter_table("attendance_records") as batch_op:
            batch_op.drop_constraint(
                "uq_attendance_student_date", type_="unique",
            )

    if not _has_constraint(
        "attendance_records", "uq_attendance_student_date_period",
    ):
        with op.batch_alter_table("attendance_records") as batch_op:
            batch_op.create_unique_constraint(
                "uq_attendance_student_date_period",
                ["school_id", "student_id", "date", "period_number"],
            )


def downgrade() -> None:
    # We don't drop period_number in downgrade — production rows may
    # carry non-zero period_numbers that the daily-only schema can't
    # represent. The unique constraint can be reverted, but the column
    # stays. An operator who really needs to revert all the way must do
    # so manually after confirming no non-zero rows exist.
    if _has_constraint(
        "attendance_records", "uq_attendance_student_date_period",
    ):
        with op.batch_alter_table("attendance_records") as batch_op:
            batch_op.drop_constraint(
                "uq_attendance_student_date_period", type_="unique",
            )
    if not _has_constraint("attendance_records", "uq_attendance_student_date"):
        with op.batch_alter_table("attendance_records") as batch_op:
            batch_op.create_unique_constraint(
                "uq_attendance_student_date",
                ["school_id", "student_id", "date"],
            )
