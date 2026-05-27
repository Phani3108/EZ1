"""school_payment_config (Phase 12b)

Revision ID: 2026_05_19_006
Revises: 2026_05_19_005
Create Date: 2026-05-26

Per-school payment provider config. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_19_006"
down_revision: Union[str, None] = "2026_05_19_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has("school_payment_config"):
        return
    op.create_table(
        "school_payment_config",
        sa.Column("school_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_name", sa.String(32), nullable=False,
                  server_default="paynow"),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    if _has("school_payment_config"):
        op.drop_table("school_payment_config")
