"""tenancy tier (PH8-1 / DEC-009)

Revision ID: 2026_05_19_006
Revises: 2026_05_19_005
Create Date: 2026-05-26

Adds three columns to `schools`:
  * `tenancy_tier`           — `shared` | `dedicated` | `district`. Default `shared`.
                                Existing rows get `shared` via server_default.
  * `district_routing_code`  — Optional. Nonnull only when tenancy_tier=='district'.
  * `maintenance_mode`       — Boolean. True while a promotion job is mid-flight.

Idempotent — safe to run against fresh or migrated databases.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_006"
down_revision: Union[str, None] = "2026_05_19_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    """Returns True if the column already exists. Lets us re-run safely."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    # tenancy_tier
    if not _has_column("schools", "tenancy_tier"):
        op.add_column(
            "schools",
            sa.Column(
                "tenancy_tier",
                sa.String(20),
                nullable=False,
                server_default="shared",
            ),
        )
        op.create_index(
            "ix_schools_tenancy_tier", "schools", ["tenancy_tier"],
        )

    # district_routing_code
    if not _has_column("schools", "district_routing_code"):
        op.add_column(
            "schools",
            sa.Column("district_routing_code", sa.String(16), nullable=True),
        )

    # maintenance_mode
    if not _has_column("schools", "maintenance_mode"):
        op.add_column(
            "schools",
            sa.Column(
                "maintenance_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    # We deliberately don't drop the columns on downgrade. Any school
    # promoted to `dedicated` has its data on the dedicated DB; dropping
    # the column on shared would orphan that mapping. Operationally,
    # rolling back this migration is the wrong move once tier promotions
    # have happened — call the support runbook instead.
    pass
