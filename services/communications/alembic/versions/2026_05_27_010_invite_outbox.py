"""invite_outbox (Phase 15)

Revision ID: 2026_05_27_010
Revises: 2026_05_19_009
Create Date: 2026-05-27

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_27_010"
down_revision: Union[str, None] = "2026_05_19_009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("invite_outbox"):
        op.create_table(
            "invite_outbox",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", UUID(as_uuid=True), nullable=False),
            sa.Column("invitation_id", sa.String(36), nullable=False),
            sa.Column("channel", sa.String(16), nullable=False),
            sa.Column("provider_name", sa.String(32), nullable=True),
            sa.Column("recipient_email", sa.String(255), nullable=True),
            sa.Column("recipient_phone", sa.String(32), nullable=True),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("manual_code", sa.String(6), nullable=True),
            sa.Column("invite_url", sa.String(500), nullable=True),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="queued"),
            sa.Column("retry_count", sa.Integer(), nullable=False,
                      server_default="0"),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_invite_outbox_school_status", "invite_outbox",
                        ["school_id", "status"])
        op.create_index("ix_invite_outbox_invitation", "invite_outbox",
                        ["invitation_id"])


def downgrade() -> None:
    if _has("invite_outbox"):
        op.drop_table("invite_outbox")
