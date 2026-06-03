"""Add grade_level to classes

Revision ID: 2026_06_03_025
Revises: 2026_05_28_024
Create Date: 2026-06-03

The admin-web "New Class" form has always collected a grade level, but the
`classes` table had no column to store it, so the value was accepted by the
API and silently dropped — the Classes table's "Grade Level" column rendered
blank for every row. This adds the backing column (nullable, so existing rows
stay valid).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026_06_03_025"
down_revision: Union[str, None] = "2026_05_28_024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _has_column("classes", "grade_level"):
        op.add_column("classes", sa.Column("grade_level", sa.Integer(), nullable=True))


def downgrade() -> None:
    if _has_column("classes", "grade_level"):
        op.drop_column("classes", "grade_level")
