"""Phase 15a — Invitations table + User invite-lifecycle columns

Revision ID: 003_invitations
Revises: 002_user_preferences
Create Date: 2026-05-27

Idempotent. Touches:
  * `users`: makes password_hash nullable, adds phone, invited_at,
    activated_at.
  * `invitations`: new table for pre-staged users + activation tokens.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "003_invitations"
down_revision: Union[str, None] = "002_user_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # ── users: relax password_hash + add lifecycle columns ──────────
    # alter_column is no-op on SQLite (column-redefine is a table rebuild
    # there) but the test fixtures spin up tables via Base.metadata so
    # this migration only runs in real Postgres deployments.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)

    if not _has_column("users", "phone"):
        op.add_column("users", sa.Column("phone", sa.String(32), nullable=True))
        op.create_index("ix_users_phone", "users", ["phone"])
    if not _has_column("users", "invited_at"):
        op.add_column("users", sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("users", "activated_at"):
        op.add_column("users", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))

    # ── invitations table ─────────────────────────────────────────────
    if not _has_table("invitations"):
        op.create_table(
            "invitations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("token_hash", sa.String(255), nullable=False),
            sa.Column("manual_code", sa.String(6), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("target_resource_id", sa.String(36), nullable=True),
            sa.Column("target_resource_type", sa.String(32), nullable=True),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("contact_phone", sa.String(32), nullable=True),
            sa.Column("channel_attempted", sa.String(16), nullable=True),
            sa.Column("channel_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "school_id", "role", "contact_email", "contact_phone",
                name="uq_invitations_school_role_contact",
            ),
        )
        op.create_index("ix_invitations_school_role", "invitations", ["school_id", "role"])
        op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"])
        op.create_index("ix_invitations_manual_code", "invitations", ["manual_code"])
        op.create_index("ix_invitations_user_id", "invitations", ["user_id"])


def downgrade() -> None:
    if _has_table("invitations"):
        op.drop_table("invitations")
    bind = op.get_bind()
    if _has_column("users", "activated_at"):
        op.drop_column("users", "activated_at")
    if _has_column("users", "invited_at"):
        op.drop_column("users", "invited_at")
    if _has_column("users", "phone"):
        if bind.dialect.name != "sqlite":
            op.drop_index("ix_users_phone", table_name="users")
        op.drop_column("users", "phone")
    if bind.dialect.name != "sqlite":
        op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
