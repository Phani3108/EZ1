"""Kafka event publishing for attendance-service — per BATCH, not per record."""
import logging
from datetime import datetime, timezone

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
            client_id="attendance-service",
        ))
        return _producer
    except Exception as e:
        logger.warning(f"Kafka not available: {e}")
        return None


def publish_batch_event(school_id: str, batch_result: dict,
                        actor_user_id: str, date_range: dict = None) -> None:
    producer = _get_producer()
    if not producer:
        logger.info("Kafka disabled, skipping attendance batch event")
        return
    event = {
        "event_type": "recorded",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "actor_user_id": actor_user_id,
        "payload": {
            "batch_id": batch_result.get("batch_id"),
            "total_events": batch_result.get("total"),
            "accepted": batch_result.get("accepted"),
            "updated": batch_result.get("updated"),
            "date_range": date_range or {},
        },
    }
    producer.publish(
        topic="eduzim.attendance.recorded.v1",
        key=school_id,
        value=event,
        headers={"source": "attendance-service"},
    )
