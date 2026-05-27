"""Phase 17d — curriculum versioning

Revision ID: 2026_05_27_022
Revises: 2026_05_27_021
Create Date: 2026-05-27

Adds:
  * `national_subjects.version` (int, default 1).
  * `subjects.adopted_national_version` (int, nullable).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_27_022"
down_revision: Union[str, None] = "2026_05_27_021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in [c["name"] for c in sa.inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_col("national_subjects", "version"):
        op.add_column(
            "national_subjects",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_col("subjects", "adopted_national_version"):
        op.add_column(
            "subjects",
            sa.Column("adopted_national_version", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if _has_col("subjects", "adopted_national_version"):
        op.drop_column("subjects", "adopted_national_version")
    if _has_col("national_subjects", "version"):
        op.drop_column("national_subjects", "version")
