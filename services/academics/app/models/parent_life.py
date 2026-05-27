"""Parent-life models — Phase 12d/e/f + opt-out flag for 12g.

A pragmatic single module covering the lower-priority parent-side
surfaces. Each table is intentionally minimal; the full UX polish is
left to whatever consumer ends up loving the feature most.

Phase 12d:
  * `SchoolEvent` (P-010) — admin-published events parents see in
    their calendar (sports day, exams, holidays).
  * `SchoolPerformanceOptOut` (P-009) — per-school flag that disables
    "your child vs class average" comparisons. Comparison itself is
    computed on the fly; opt-out is a single row per school.

Phase 12e:
  * `ConferenceSlot` + `ConferenceBooking` (P-005) — parent-teacher
    conference scheduling.
  * `PermissionSlip` + `PermissionSlipResponse` (P-006) — digital
    permission slips with parental e-signature acknowledgement.
  * `Grievance` (P-007) — parent grievance submission (admin queue).
  * `TransportBus` + `TransportPing` (P-012) — minimal bus route +
    last-known-ping visibility. The driver app is Phase 13.

Phase 12f:
  * `MealCreditAccount` (P-013) — cafeteria credit balance.
  * `Donation` (P-014) — parent donation log.
  * `NewsletterPost` (P-015) — school-published newsletter feed.
  * `GalleryPhoto` (P-016) — curated photo references (storage URI
    via the polymorphic Attachment).
  * `SiblingDiscountRule` (P-017) — per-school discount config.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Text, Date, Integer, Numeric, Boolean,
    ForeignKey, Index, UniqueConstraint,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── 12d engagement ────────────────────────────────────────────────


class SchoolEvent(Base):
    __tablename__ = "school_events"
    __table_args__ = (
        Index("ix_school_event_date", "school_id", "start_at"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=True)
    # "exam" | "sports" | "holiday" | "meeting" | "other"
    kind = Column(String(32), nullable=False, default="other")
    visible_to_parents = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class SchoolPerformanceOptOut(Base):
    """A row here means the school has DISABLED parent-facing
    comparisons. Absence = comparisons enabled (the default per
    DEC-007 / privacy-by-default)."""
    __tablename__ = "school_performance_opt_out"
    school_id = Column(UUID_STR, primary_key=True)
    opted_out_by = Column(UUID_STR, nullable=False)
    opted_out_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    reason = Column(String(500), nullable=True)


# ─── 12e logistics ────────────────────────────────────────────────


class ConferenceSlot(Base):
    """A teacher's bookable slot for a parent-teacher conference."""
    __tablename__ = "conference_slots"
    __table_args__ = (
        Index("ix_conf_slot_teacher", "school_id", "teacher_user_id"),
        Index("ix_conf_slot_date", "school_id", "starts_at"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    teacher_user_id = Column(UUID_STR, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=15)
    is_booked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ConferenceBooking(Base):
    __tablename__ = "conference_bookings"
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    slot_id = Column(
        UUID_STR,
        ForeignKey("conference_slots.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    parent_user_id = Column(UUID_STR, nullable=False)
    student_id = Column(UUID_STR, nullable=False)
    notes = Column(Text, nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class PermissionSlip(Base):
    """Admin-published permission slip (field trip etc.)."""
    __tablename__ = "permission_slips"
    __table_args__ = (
        Index("ix_perm_slip_class", "school_id", "class_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    class_id = Column(UUID_STR, nullable=True)  # null = whole school
    deadline = Column(Date, nullable=True)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class PermissionSlipResponse(Base):
    """One row per (slip, student). The parent's "e-signature" is a
    confirmation of identity (their authenticated session) + their
    typed full_name. Not a cryptographic signature — that's a Phase
    13 follow-up if the school's legal counsel requires it."""
    __tablename__ = "permission_slip_responses"
    __table_args__ = (
        UniqueConstraint(
            "slip_id", "student_id",
            name="uq_perm_slip_response_student",
        ),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    slip_id = Column(
        UUID_STR,
        ForeignKey("permission_slips.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id = Column(UUID_STR, nullable=False)
    parent_user_id = Column(UUID_STR, nullable=False)
    # "approved" | "declined"
    decision = Column(String(16), nullable=False)
    signed_full_name = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Grievance(Base):
    """Parent grievance / concern submission."""
    __tablename__ = "grievances"
    __table_args__ = (
        Index("ix_grievance_school_status", "school_id", "status"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    parent_user_id = Column(UUID_STR, nullable=False)
    student_id = Column(UUID_STR, nullable=True)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    # "open" | "in_review" | "resolved" | "dismissed"
    status = Column(String(16), nullable=False, default="open")
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id = Column(UUID_STR, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class TransportBus(Base):
    """Minimal bus route + assigned vehicle."""
    __tablename__ = "transport_buses"
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    label = Column(String(120), nullable=False)
    plate_number = Column(String(32), nullable=True)
    route_description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class TransportPing(Base):
    """Last-known location + status ping from the bus. The driver
    app (Phase 13) writes these; parents read via the most-recent
    row per bus."""
    __tablename__ = "transport_pings"
    __table_args__ = (
        Index("ix_bus_ping_bus_at", "bus_id", "occurred_at"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    bus_id = Column(
        UUID_STR,
        ForeignKey("transport_buses.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "departed" | "en_route" | "arrived" | "delayed"
    status = Column(String(16), nullable=False)
    lat = Column(Numeric(9, 6), nullable=True)
    lng = Column(Numeric(9, 6), nullable=True)
    note = Column(String(500), nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── 12f lifestyle ─────────────────────────────────────────────────


class MealCreditAccount(Base):
    """One row per student. Topped up by parent payments (or admin
    adjustments). Cafeteria scanner debits via the admin-web POS in
    Phase 13; for now we just track the balance."""
    __tablename__ = "meal_credit_accounts"
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    student_id = Column(UUID_STR, nullable=False, unique=True)
    balance_cents = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow,
        onupdate=_utcnow, nullable=False,
    )


class Donation(Base):
    """Parent donation log. Separate from fee payments so we don't
    pollute the invoice ledger."""
    __tablename__ = "donations"
    __table_args__ = (
        Index("ix_donation_school", "school_id", "created_at"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    donor_user_id = Column(UUID_STR, nullable=True)  # null = anonymous
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    purpose = Column(String(200), nullable=True)  # "library", "sports", etc.
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class NewsletterPost(Base):
    """School-published newsletter / blog post. Visible to parents."""
    __tablename__ = "newsletter_posts"
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    author_user_id = Column(UUID_STR, nullable=False)


class GalleryPhoto(Base):
    """Curated photo entry. The actual bytes live in the
    polymorphic Attachment table (owner_kind="gallery_photo"). This
    row carries the caption + visibility metadata."""
    __tablename__ = "gallery_photos"
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    attachment_id = Column(UUID_STR, nullable=False)
    caption = Column(String(500), nullable=True)
    # "all_parents" | "class:<id>" — simple visibility scope.
    visibility = Column(String(64), nullable=False, default="all_parents")
    published_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    published_by = Column(UUID_STR, nullable=False)


class SiblingDiscountRule(Base):
    """Per-school sibling discount rule. The actual discount is
    applied during fee structure assignment in Phase 13's admin-web
    flow; this row is the policy record."""
    __tablename__ = "sibling_discount_rules"
    school_id = Column(UUID_STR, primary_key=True)
    # E.g., second child: 10%, third: 20%, fourth: 30%.
    rule_json = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_by = Column(UUID_STR, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow,
        onupdate=_utcnow, nullable=False,
    )
