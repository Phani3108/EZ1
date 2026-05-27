"""special — boarding + multi-campus (Phase 13e)

Revision ID: 2026_05_19_019
Revises: 2026_05_19_018
Create Date: 2026-05-27

Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_019"
down_revision: Union[str, None] = "2026_05_19_018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("boarding_rooms"):
        op.create_table(
            "boarding_rooms",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("room_code", sa.String(32), nullable=False),
            sa.Column("campus", sa.String(64), nullable=True),
            sa.Column("occupancy_kind", sa.String(16), nullable=False, server_default="mixed"),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "room_code",
                                name="uq_boarding_room_code"),
        )
        op.create_index("ix_boarding_room_school", "boarding_rooms",
                        ["school_id"])

    if not _has("boarding_assignments"):
        op.create_table(
            "boarding_assignments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("room_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("bed_label", sa.String(16), nullable=True),
            sa.Column("starts_on", sa.Date(), nullable=False),
            sa.Column("ended_on", sa.Date(), nullable=True),
            sa.Column("assigned_by_user_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_boarding_assignment_room", "boarding_assignments",
                        ["room_id"])
        op.create_index("ix_boarding_assignment_student", "boarding_assignments",
                        ["student_id"])
        op.create_index("ix_boarding_assignment_active", "boarding_assignments",
                        ["school_id", "ended_on"])

    if not _has("campuses"):
        op.create_table(
            "campuses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("campus_type", sa.String(16), nullable=False, server_default="combined"),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("province_code", sa.String(8), nullable=True),
            sa.Column("district_code", sa.String(16), nullable=True),
            sa.Column("lat", sa.String(16), nullable=True),
            sa.Column("lng", sa.String(16), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("school_id", "code", name="uq_campus_code"),
        )
        op.create_index("ix_campus_school", "campuses", ["school_id"])


def downgrade() -> None:
    for t in ("campuses", "boarding_assignments", "boarding_rooms"):
        if _has(t):
            op.drop_table(t)
