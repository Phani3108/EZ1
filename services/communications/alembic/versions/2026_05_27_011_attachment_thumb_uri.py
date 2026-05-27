"""attachment.thumb_uri (Phase 17b)

Revision ID: 2026_05_27_011
Revises: 2026_05_27_010
Create Date: 2026-05-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_27_011"
down_revision: Union[str, None] = "2026_05_27_010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in [c["name"] for c in sa.inspect(bind).get_columns(table)]


def upgrade() -> None:
    if not _has_col("attachments", "thumb_uri"):
        op.add_column(
            "attachments", sa.Column("thumb_uri", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _has_col("attachments", "thumb_uri"):
        op.drop_column("attachments", "thumb_uri")
