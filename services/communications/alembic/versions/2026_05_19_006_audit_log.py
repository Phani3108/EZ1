"""audit log table (Phase 9 follow-up — communications)

Revision ID: 2026_05_19_006
Revises: 2026_05_19_005
Create Date: 2026-05-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database import Base
from app.models import audit  # noqa: F401  (registers on Base.metadata)


revision: str = "2026_05_19_006"
down_revision: Union[str, None] = "2026_05_19_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("audit_log"):
        return
    audit_log = Base.metadata.tables["audit_log"]
    audit_log.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    pass
