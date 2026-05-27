"""student.user_id link (Phase 12a / PH12-1)

Revision ID: 2026_05_19_013
Revises: 2026_05_19_012
Create Date: 2026-05-26

Adds `user_id` to `students` so a student can be linked to an Identity
User row for login. Null when the student hasn't been provisioned a
digital account. Unique because one User maps to one Student.

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_19_013"
down_revision: Union[str, None] = "2026_05_19_012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("students", "user_id"):
        with op.batch_alter_table("students") as batch_op:
            batch_op.add_column(
                sa.Column("user_id", UUID(as_uuid=True), nullable=True),
            )
            batch_op.create_unique_constraint(
                "uq_student_user_id", ["user_id"],
            )
        op.create_index(
            "ix_students_user_id", "students", ["user_id"],
        )


def downgrade() -> None:
    # Don't drop on routine downgrade — the column may carry live
    # user-account links. Drop manually after a documented audit.
    pass
