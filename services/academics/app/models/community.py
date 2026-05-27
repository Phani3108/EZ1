"""Community models — Phase 13d.

  * A-017 — `PolicyDocument` — admin-published policy / handbook
    references. Attachment-backed (T-008).
  * A-019 — `Sponsor`, `Sponsorship` — corporate / NGO sponsors and
    their funding commitments. Parent-side `Donation` (Phase 12f)
    handles individual contributions.
  * A-020 — `Alumnus` — graduate / former-student tracking.

A-015 (events) + A-016 (newsletter) reuse `SchoolEvent` and
`NewsletterPost` from Phase 12d/f.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, Date, Integer, Boolean, Text,
    UniqueConstraint, Index,
)
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ─── A-017 — Policy documents ─────────────────────────────────────


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint("school_id", "code", "version",
                         name="uq_policy_code_version"),
        Index("ix_policy_school", "school_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    code = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    # "uniform" | "discipline" | "academic" | "fees" | "child_protection" |
    # "data_privacy" | "other"
    category = Column(String(32), nullable=False, default="other")
    # The actual document attachment via T-008.
    attachment_id = Column(UUID_STR, nullable=True)
    # Versioning — bumping creates a new row with the same code.
    version = Column(Integer, nullable=False, default=1)
    effective_from = Column(Date, nullable=False)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    visible_to_parents = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-019 — Sponsors + sponsorships ──────────────────────────────


class Sponsor(Base):
    __tablename__ = "sponsors"
    __table_args__ = (
        UniqueConstraint("school_id", "name",
                         name="uq_sponsor_name"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # corporate | individual | ngo | government | other
    sponsor_type = Column(String(16), nullable=False, default="other")
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Sponsorship(Base):
    """A funding commitment from a Sponsor to the school. The actual
    money-in is still tracked via Donation rows (Phase 12f) — this
    table is the CONTRACT layer."""
    __tablename__ = "sponsorships"
    __table_args__ = (
        Index("ix_sponsorship_school_status", "school_id", "status"),
        Index("ix_sponsorship_sponsor", "sponsor_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    sponsor_id = Column(UUID_STR, nullable=False)
    # bursary | infrastructure | equipment | sports | program | other
    purpose = Column(String(32), nullable=False, default="other")
    committed_cents = Column(Integer, nullable=False)
    received_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    # pending | active | completed | terminated
    status = Column(String(16), nullable=False, default="pending")
    starts_on = Column(Date, nullable=True)
    ends_on = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ─── A-020 — Alumni ───────────────────────────────────────────────


class Alumnus(Base):
    __tablename__ = "alumni"
    __table_args__ = (
        UniqueConstraint("school_id", "student_id",
                         name="uq_alumnus_student"),
        Index("ix_alumni_school", "school_id"),
    )
    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    # Original Student row (the graduating record).
    student_id = Column(UUID_STR, nullable=False)
    full_name = Column(String(255), nullable=False)
    graduation_year = Column(Integer, nullable=False)
    final_class_label = Column(String(80), nullable=True)
    # Current contact + status snapshots. Updated as alumni get back
    # in touch.
    current_email = Column(String(255), nullable=True)
    current_phone = Column(String(20), nullable=True)
    current_occupation = Column(String(255), nullable=True)
    current_university = Column(String(255), nullable=True)
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow, onupdate=_utcnow, nullable=False,
    )
