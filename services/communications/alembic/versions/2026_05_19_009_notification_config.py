"""school_notification_config (Phase 12c)

Revision ID: 2026_05_19_009
Revises: 2026_05_19_008
Create Date: 2026-05-27

Per-school per-channel notification provider config. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_19_009"
down_revision: Union[str, None] = "2026_05_19_008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has("school_notification_config"):
        return
    op.create_table(
        "school_notification_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("provider_name", sa.String(32), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "channel",
                            name="uq_school_notification_channel"),
    )
    op.create_index(
        "ix_school_notification_config_school",
        "school_notification_config", ["school_id"],
    )


def downgrade() -> None:
    if _has("school_notification_config"):
        op.drop_table("school_notification_config")
