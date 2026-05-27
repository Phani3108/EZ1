"""Add user_preferences table

Revision ID: 002_user_preferences
Revises: 001_initial
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "002_user_preferences"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("theme_pref", sa.String(16), nullable=False, server_default="focus"),
        sa.Column("text_size", sa.String(4), nullable=False, server_default="md"),
        sa.Column("high_contrast", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_aloud_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reduced_motion", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("language IN ('en', 'sn', 'nd')", name="ck_user_pref_language"),
        sa.CheckConstraint(
            "theme_pref IN ('joyful', 'focus', 'sovereign')",
            name="ck_user_pref_theme",
        ),
        sa.CheckConstraint(
            "text_size IN ('sm', 'md', 'lg', 'xl')",
            name="ck_user_pref_text_size",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
