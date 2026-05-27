"""initial schema (bootstrap from SQLAlchemy metadata)

Revision ID: 2026_05_19_007
Revises:
Create Date: 2026-05-19

This migration bootstraps the schema from the current SQLAlchemy models for
services that previously relied on Base.metadata.create_all() at boot. It is
idempotent (checkfirst=True) so it is safe to apply against:
  * fresh databases  -> creates all tables
  * existing dev/test databases -> no-op for tables that already exist

Future schema changes should be authored as proper alembic revisions using
`alembic revision --autogenerate -m "description"`.
"""
from typing import Sequence, Union

from alembic import op

from app.database import Base
from app.models import assessment, idempotency  # noqa: F401  (ensures tables register on Base.metadata)


revision: str = "2026_05_19_005"
down_revision: Union[str, None] = "2026_05_19_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
