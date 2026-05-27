"""Idempotency key model for the Communication Service."""
from app.database import Base
from eduzim_shared.idempotency import create_idempotency_key_model

IdempotencyKey = create_idempotency_key_model(Base)
