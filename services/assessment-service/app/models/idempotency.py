"""
Idempotency Key model — assessment-service.
Prevents duplicate bulk marks submissions via X-Request-Id or sync_batch_id.
"""
from eduzim_shared.idempotency import create_idempotency_key_model
from app.database import Base

IdempotencyKey = create_idempotency_key_model(Base)
