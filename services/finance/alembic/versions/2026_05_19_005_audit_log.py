"""audit log table (Phase 9 follow-up — finance)

Revision ID: 2026_05_19_005
Revises: 2026_05_19_004
Create Date: 2026-05-26

Creates the `audit_log` table using the shared mixin definition.
Idempotent — re-running is safe (the `_has_table` guard skips if the
table already exists in the bound DB).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database import Base
from app.models import audit  # noqa: F401  (registers on Base.metadata)


revision: str = "2026_05_19_005"
down_revision: Union[str, None] = "2026_05_19_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("audit_log"):
        return
    # Base.metadata picks up the table from the audit import above.
    audit_log = Base.metadata.tables["audit_log"]
    audit_log.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Audit data is retention-controlled by `scripts/audit-log-retention.py`,
    # not by alembic downgrade. Dropping on rollback would lose
    # subpoena-relevant rows.
    pass
