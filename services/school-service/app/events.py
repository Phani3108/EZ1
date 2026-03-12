"""Kafka event publishing for school-service."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)
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
        _producer = EduZimProducer(KafkaConfig(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id="school-service",
        ))
        return _producer
    except Exception as e:
        logger.warning(f"Kafka not available: {e}")
        return None


def publish_event(topic: str, key: str, payload: dict,
                  school_id: str, actor_user_id: str) -> None:
    producer = _get_producer()
    if not producer:
        logger.info(f"Kafka disabled, skipping {topic}")
        return
    from datetime import datetime, timezone
    event = {
        "event_type": topic.split(".")[-2],
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "actor_user_id": actor_user_id,
        "payload": payload,
    }
    producer.publish(topic=topic, key=key, value=event, headers={"source": "school-service"})
