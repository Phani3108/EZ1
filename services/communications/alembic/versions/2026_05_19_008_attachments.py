"""attachments table (Phase 11b / T-008)

Revision ID: 2026_05_19_008
Revises: 2026_05_19_007
Create Date: 2026-05-26

Polymorphic `attachments` table for files attached to announcements,
messages, incidents, and marks. The owner reference is stored as
(owner_kind, owner_id) — no FK because the owner table varies. Service
layers enforce existence.

Idempotent — safe to re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "2026_05_19_008"
down_revision: Union[str, None] = "2026_05_19_007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("attachments"):
        return
    op.create_table(
        "attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_kind", sa.String(32), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("uploaded_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_attachment_owner", "attachments",
                    ["school_id", "owner_kind", "owner_id"])
    op.create_index("ix_attachment_school", "attachments", ["school_id"])


def downgrade() -> None:
    # Attachments contain user-generated content under retention policy.
    # Don't drop on routine downgrade.
    pass
