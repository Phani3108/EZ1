"""Idempotency key model for the fees-service.

Bridges the shared `create_idempotency_key_model` factory to our SQLAlchemy
declarative Base so request-level Idempotency-Key headers can dedupe
mutating calls (e.g. POST /fees/payments/initiate).
"""

from app.database import Base
from eduzim_shared.idempotency import create_idempotency_key_model

IdempotencyKey = create_idempotency_key_model(Base)
