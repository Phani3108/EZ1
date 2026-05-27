"""Per-school payment + notification provider config (Phase 12b/c)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SchoolPaymentConfig(Base):
    """One row per school. Picks which `PaymentProvider` handles the
    parent payment flow. Defaults to "paynow" when no row exists."""
    __tablename__ = "school_payment_config"

    school_id = Column(UUID(as_uuid=True), primary_key=True)
    # See providers/registry.py PROVIDER_REGISTRY keys.
    provider_name = Column(String(32), nullable=False, default="paynow")
    # Provider-specific opaque config (e.g. paynow merchant id).
    # JSON-text rather than JSONB for portability.
    config_json = Column(Text, nullable=True)
    updated_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=_utcnow, onupdate=_utcnow,
    )
