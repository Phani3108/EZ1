"""provinces and districts reference tables + school geography FKs

Revision ID: 2026_05_19_002
Revises: 2026_05_19_001
Create Date: 2026-05-19

- Creates ``provinces`` and ``districts`` reference tables.
- Adds nullable ``province_code``, ``district_code``, ``school_type``,
  ``principal_name``, ``address``, ``phone``, ``email``, ``founded_year``
  columns on ``schools``.
- Seeds provinces/districts from ``eduzim_shared.reference.zimbabwe_geo``.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_002"
down_revision: Union[str, None] = "2026_05_19_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ─── provinces ────────────────────────────────────────────
    if not inspector.has_table("provinces"):
        op.create_table(
            "provinces",
            sa.Column("code", sa.String(length=8), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False, unique=True),
            sa.Column("region", sa.String(length=100), nullable=False),
            sa.Column("capital", sa.String(length=100), nullable=False),
            sa.Column("country", sa.String(length=5), nullable=False, server_default="ZW"),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    # ─── districts ────────────────────────────────────────────
    if not inspector.has_table("districts"):
        op.create_table(
            "districts",
            sa.Column("code", sa.String(length=16), primary_key=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("province_code", sa.String(length=8),
                      sa.ForeignKey("provinces.code", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("province_code", "name", name="uq_district_province_name"),
        )
        op.create_index("ix_districts_province_code", "districts", ["province_code"])

    # ─── schools: add columns if missing ──────────────────────
    school_cols = {c["name"] for c in inspector.get_columns("schools")} if inspector.has_table("schools") else set()
    add = lambda col: op.add_column("schools", col)
    if "province_code" not in school_cols:
        add(sa.Column("province_code", sa.String(length=8),
                      sa.ForeignKey("provinces.code", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_schools_province_code", "schools", ["province_code"])
    if "district_code" not in school_cols:
        add(sa.Column("district_code", sa.String(length=16),
                      sa.ForeignKey("districts.code", ondelete="SET NULL"), nullable=True))
        op.create_index("ix_schools_district_code", "schools", ["district_code"])
    if "school_type" not in school_cols:
        add(sa.Column("school_type", sa.String(length=20), nullable=True))
    if "principal_name" not in school_cols:
        add(sa.Column("principal_name", sa.String(length=255), nullable=True))
    if "address" not in school_cols:
        add(sa.Column("address", sa.Text(), nullable=True))
    if "phone" not in school_cols:
        add(sa.Column("phone", sa.String(length=50), nullable=True))
    if "email" not in school_cols:
        add(sa.Column("email", sa.String(length=255), nullable=True))
    if "founded_year" not in school_cols:
        add(sa.Column("founded_year", sa.Integer(), nullable=True))

    # ─── Seed reference data ──────────────────────────────────
    try:
        from eduzim_shared.reference.zimbabwe_geo import (
            ZIMBABWE_PROVINCES, ZIMBABWE_DISTRICTS,
        )
    except Exception:
        # Best-effort seed; migration succeeds even if shared pkg is unavailable
        return

    provinces_tbl = sa.table(
        "provinces",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("region", sa.String),
        sa.column("capital", sa.String),
        sa.column("country", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    districts_tbl = sa.table(
        "districts",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("province_code", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    from datetime import datetime, timezone
    _now = datetime.now(timezone.utc)

    existing_provinces = {row[0] for row in bind.execute(sa.text("SELECT code FROM provinces")).fetchall()}
    province_rows = [
        {"code": p.code, "name": p.name, "region": p.region, "capital": p.capital,
         "country": "ZW", "created_at": _now}
        for p in ZIMBABWE_PROVINCES if p.code not in existing_provinces
    ]
    if province_rows:
        op.bulk_insert(provinces_tbl, province_rows)

    existing_districts = {row[0] for row in bind.execute(sa.text("SELECT code FROM districts")).fetchall()}
    district_rows = [
        {"code": d.code, "name": d.name, "province_code": d.province_code, "created_at": _now}
        for d in ZIMBABWE_DISTRICTS if d.code not in existing_districts
    ]
    if district_rows:
        op.bulk_insert(districts_tbl, district_rows)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("schools"):
        school_cols = {c["name"] for c in inspector.get_columns("schools")}
        for col in ("province_code", "district_code", "school_type",
                    "principal_name", "address", "phone", "email", "founded_year"):
            if col in school_cols:
                try:
                    op.drop_index(f"ix_schools_{col}", table_name="schools")
                except Exception:
                    pass
                op.drop_column("schools", col)

    if inspector.has_table("districts"):
        op.drop_table("districts")
    if inspector.has_table("provinces"):
        op.drop_table("provinces")
