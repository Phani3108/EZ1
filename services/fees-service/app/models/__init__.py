"""Aggregate ORM imports so Base.metadata sees every table."""

from app.models import fees as _fees  # noqa: F401
from app.models.idempotency import IdempotencyKey  # noqa: F401
