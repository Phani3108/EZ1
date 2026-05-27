"""Comment bank (Phase 11c / T-007).

School-configurable phrase library teachers pick from when entering
marks. The model is minimal: one row per phrase, optional category
(praise / improvement / concern), and an `archived_at` for soft-delete
so a school can retire a phrase without breaking historical references
in marks remarks.

Authorization (enforced at the route layer):
  * School admins manage the bank (create / update / archive).
  * Teachers can READ the bank to pick from it.
  * The bank itself is school-scoped; no cross-tenant sharing.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, Index, Integer
from app.database import Base


UUID_STR = String(36)


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class CommentBankPhrase(Base):
    __tablename__ = "comment_bank_phrases"
    __table_args__ = (
        Index("ix_commentbank_school", "school_id", "archived_at"),
        Index("ix_commentbank_category", "school_id", "category"),
    )

    id = Column(UUID_STR, primary_key=True, default=_new_uuid)
    school_id = Column(UUID_STR, nullable=False, index=True)
    # praise | improvement | concern | other — free-form so a school
    # can add their own (e.g. "behaviour", "effort") without a migration.
    category = Column(String(32), nullable=False, default="other")
    text = Column(Text, nullable=False)
    # Higher sort_order surfaces sooner in the picker.
    sort_order = Column(Integer, nullable=False, default=0)
    created_by = Column(UUID_STR, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
