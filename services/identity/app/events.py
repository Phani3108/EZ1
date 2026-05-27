"""Kafka event publishing for auth-service."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-initialized producer
_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.KAFKA_ENABLED:
            return None
        from eduzim_shared.kafka.producer import EduZimProducer
        from eduzim_shared.kafka.config import KafkaConfig
        config = KafkaConfig(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id="auth-service",
        )
        _producer = EduZimProducer(config)
        return _producer
    except Exception as e:
        logger.warning(f"Kafka producer not available: {e}")
        return None


def publish_user_created(
    user_id: str,
    school_id: str,
    email: str,
    full_name: str,
    roles: list[str],
    actor_user_id: Optional[str] = None,
) -> None:
    """Publish UserCreated event to Kafka."""
    producer = _get_producer()
    if not producer:
        logger.info("Kafka disabled, skipping user.created event")
        return

    from datetime import datetime, timezone

    event = {
        "event_id": None,  # Producer wrapper generates this
        "event_type": "user.created",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "actor_user_id": actor_user_id or user_id,
        "payload": {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "roles": roles,
        },
    }

    producer.publish(
        topic="eduzim.auth.user.created.v1",
        key=user_id,
        value=event,
        headers={"source": "auth-service"},
    )
    logger.info(f"Published user.created event for {user_id}")
