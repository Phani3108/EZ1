"""parent-life tables (Phase 12d/e/f)

Revision ID: 2026_05_19_014
Revises: 2026_05_19_013
Create Date: 2026-05-27

Batch of small tables for the lower-priority parent-side surface:
events, perf opt-out, conference slots/bookings, permission slips,
grievances, transport, meal credit, donations, newsletter posts,
gallery photo entries, sibling discount rule. Idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_05_19_014"
down_revision: Union[str, None] = "2026_05_19_013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:  # noqa: C901 - one-shot batch migration
    if not _has("school_events"):
        op.create_table(
            "school_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("kind", sa.String(32), nullable=False, server_default="other"),
            sa.Column("visible_to_parents", sa.Boolean(), nullable=False,
                      server_default=sa.text("1")),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_school_event_date", "school_events",
                        ["school_id", "start_at"])

    if not _has("school_performance_opt_out"):
        op.create_table(
            "school_performance_opt_out",
            sa.Column("school_id", sa.String(36), primary_key=True),
            sa.Column("opted_out_by", sa.String(36), nullable=False),
            sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
        )

    if not _has("conference_slots"):
        op.create_table(
            "conference_slots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("teacher_user_id", sa.String(36), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False,
                      server_default="15"),
            sa.Column("is_booked", sa.Boolean(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_conf_slot_teacher", "conference_slots",
                        ["school_id", "teacher_user_id"])
        op.create_index("ix_conf_slot_date", "conference_slots",
                        ["school_id", "starts_at"])

    if not _has("conference_bookings"):
        op.create_table(
            "conference_bookings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("slot_id", sa.String(36),
                      sa.ForeignKey("conference_slots.id", ondelete="CASCADE"),
                      nullable=False, unique=True),
            sa.Column("parent_user_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has("permission_slips"):
        op.create_table(
            "permission_slips",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("class_id", sa.String(36), nullable=True),
            sa.Column("deadline", sa.Date(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_perm_slip_class", "permission_slips",
                        ["school_id", "class_id"])

    if not _has("permission_slip_responses"):
        op.create_table(
            "permission_slip_responses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("slip_id", sa.String(36),
                      sa.ForeignKey("permission_slips.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("parent_user_id", sa.String(36), nullable=False),
            sa.Column("decision", sa.String(16), nullable=False),
            sa.Column("signed_full_name", sa.String(255), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("slip_id", "student_id",
                                name="uq_perm_slip_response_student"),
        )

    if not _has("grievances"):
        op.create_table(
            "grievances",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("parent_user_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=True),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_grievance_school_status", "grievances",
                        ["school_id", "status"])

    if not _has("transport_buses"):
        op.create_table(
            "transport_buses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("label", sa.String(120), nullable=False),
            sa.Column("plate_number", sa.String(32), nullable=True),
            sa.Column("route_description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has("transport_pings"):
        op.create_table(
            "transport_pings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("bus_id", sa.String(36),
                      sa.ForeignKey("transport_buses.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("lat", sa.Numeric(9, 6), nullable=True),
            sa.Column("lng", sa.Numeric(9, 6), nullable=True),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_bus_ping_bus_at", "transport_pings",
                        ["bus_id", "occurred_at"])

    if not _has("meal_credit_accounts"):
        op.create_table(
            "meal_credit_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False, unique=True),
            sa.Column("balance_cents", sa.Integer(), nullable=False,
                      server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has("donations"):
        op.create_table(
            "donations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("donor_user_id", sa.String(36), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False,
                      server_default="USD"),
            sa.Column("purpose", sa.String(200), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_donation_school", "donations",
                        ["school_id", "created_at"])

    if not _has("newsletter_posts"):
        op.create_table(
            "newsletter_posts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("author_user_id", sa.String(36), nullable=False),
        )

    if not _has("gallery_photos"):
        op.create_table(
            "gallery_photos",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("school_id", sa.String(36), nullable=False),
            sa.Column("attachment_id", sa.String(36), nullable=False),
            sa.Column("caption", sa.String(500), nullable=True),
            sa.Column("visibility", sa.String(64), nullable=False,
                      server_default="all_parents"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("published_by", sa.String(36), nullable=False),
        )

    if not _has("sibling_discount_rules"):
        op.create_table(
            "sibling_discount_rules",
            sa.Column("school_id", sa.String(36), primary_key=True),
            sa.Column("rule_json", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("1")),
            sa.Column("updated_by", sa.String(36), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    for t in (
        "sibling_discount_rules", "gallery_photos", "newsletter_posts",
        "donations", "meal_credit_accounts", "transport_pings",
        "transport_buses", "grievances", "permission_slip_responses",
        "permission_slips", "conference_bookings", "conference_slots",
        "school_performance_opt_out", "school_events",
    ):
        if _has(t):
            op.drop_table(t)
