"""Phase 9 — audit_log table (INFRA-018 / Q-016)

Revision ID: 004_audit_log
Revises: 003_invitations
Create Date: 2026-06-03

The ``AuditLog`` model (app/models/user.py) and ``record_audit_event``
(app/services/audit.py) shipped, and the /login path writes an
``auth.login.{success,failed}`` row on every attempt — but no migration
ever created the backing table. Result: EVERY login 500s with
``relation "audit_log" does not exist``. This migration lands the table.

Idempotent: guards on table/index existence so re-runs are safe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "004_audit_log"
down_revision: Union[str, None] = "003_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(36)

    if not _has_table("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_user_id", uuid_type, nullable=True),
            sa.Column("actor_role", sa.String(32), nullable=True),
            sa.Column("school_id", uuid_type, nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("target", sa.Text(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(255), nullable=True),
            sa.Column("request_id", sa.String(64), nullable=True),
            sa.UniqueConstraint("id", name="uq_audit_log_id"),
        )

    for col, ix in [
        ("occurred_at", "ix_audit_log_occurred_at"),
        ("actor_user_id", "ix_audit_log_actor_user_id"),
        ("school_id", "ix_audit_log_school_id"),
        ("event_type", "ix_audit_log_event_type"),
        ("request_id", "ix_audit_log_request_id"),
    ]:
        if not _has_index("audit_log", ix):
            op.create_index(ix, "audit_log", [col])


def downgrade() -> None:
    if _has_table("audit_log"):
        op.drop_table("audit_log")
