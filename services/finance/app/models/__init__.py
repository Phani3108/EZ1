"""Aggregate ORM imports so Base.metadata sees every table."""

from app.models import fees as _fees  # noqa: F401
from app.models.idempotency import IdempotencyKey  # noqa: F401
# Phase 9 follow-up — audit table.
from app.models.audit import AuditLog  # noqa: F401
# Phase 12b — per-school payment provider config.
from app.models.payment_config import SchoolPaymentConfig  # noqa: F401
