"""comment bank (Phase 11c / T-007)

Revision ID: 2026_05_19_009
Revises: 2026_05_19_008
Create Date: 2026-05-26

Adds `comment_bank_phrases` — school-scoped phrase library for marks
remarks. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_009"
down_revision: Union[str, None] = "2026_05_19_008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("comment_bank_phrases"):
        return
    op.create_table(
        "comment_bank_phrases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(32), nullable=False,
                  server_default="other"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_commentbank_school", "comment_bank_phrases",
        ["school_id", "archived_at"],
    )
    op.create_index(
        "ix_commentbank_category", "comment_bank_phrases",
        ["school_id", "category"],
    )


def downgrade() -> None:
    if _has_table("comment_bank_phrases"):
        op.drop_index("ix_commentbank_category", "comment_bank_phrases")
        op.drop_index("ix_commentbank_school", "comment_bank_phrases")
        op.drop_table("comment_bank_phrases")
