"""Kafka event publishing for academics service.

PH2-6 note: same publisher as the original school-service, with the
client_id and source header changed to `academics`. During PH2-6 → PH2-9
both services exist, but only the one the gateway routes traffic to
actually emits — so no duplicate Kafka writes.
"""
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
        _producer = EduZimProducer(
            KafkaConfig(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                client_id="academics",
            ),
            label="academics",  # distinct flush-registry entry from school-service's
        )
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
    producer.publish(topic=topic, key=key, value=event, headers={"source": "academics"})


# PH2-8 — attendance-specific batch publisher. Same Kafka producer; different
# event shape (one event per sync batch, not per attendance row). Topic stays
# `eduzim.attendance.recorded.v1` so the reporting consumer doesn't need to
# change.
def publish_batch_event(school_id: str, batch_result: dict,
                        actor_user_id: str, date_range: dict = None) -> None:
    producer = _get_producer()
    if not producer:
        logger.info("Kafka disabled, skipping attendance batch event")
        return
    from datetime import datetime, timezone
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
        headers={"source": "academics"},
    )


# PH2-9 — assessment events. The pre-consolidation assessment-service did
# NOT publish Kafka events; reporting therefore missed assessments and
# marks. With assessment now in academics, these emits go through the
# unified academics producer.

def publish_assessment_created_event(
    school_id: str,
    actor_user_id: str,
    assessment: dict,
) -> None:
    producer = _get_producer()
    if not producer:
        logger.info("Kafka disabled, skipping assessment.created event")
        return
    from datetime import datetime, timezone
    event = {
        "event_type": "created",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "actor_user_id": actor_user_id,
        # Minimal payload: identifiers + the joinable shape downstream
        # consumers (reporting projection) need. Avoid pushing the entire
        # row — events live on the wire forever; mind the size.
        "payload": {
            "assessment_id": assessment.get("id"),
            "class_id": assessment.get("class_id"),
            "subject_id": assessment.get("subject_id"),
            "term_id": assessment.get("term_id"),
            "academic_year_id": assessment.get("academic_year_id"),
            "assessment_type": assessment.get("assessment_type"),
            "max_marks": str(assessment.get("max_marks"))
                if assessment.get("max_marks") is not None else None,
            "date": str(assessment.get("date"))
                if assessment.get("date") is not None else None,
        },
    }
    producer.publish(
        topic="eduzim.assessment.created.v1",
        key=school_id,
        value=event,
        headers={"source": "academics"},
    )


def publish_marks_recorded_event(
    school_id: str,
    actor_user_id: str,
    assessment_id: str,
    result: dict,
) -> None:
    """One Kafka event per bulk-marks submission (NOT per row).

    `result` is the return value of AssessmentService.bulk_upsert_marks —
    contains accepted/updated/errors counters. We forward those so the
    reporting projection can update its "marks recorded today" tile without
    re-querying.
    """
    producer = _get_producer()
    if not producer:
        logger.info("Kafka disabled, skipping marks.recorded event")
        return
    from datetime import datetime, timezone
    event = {
        "event_type": "recorded",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "school_id": school_id,
        "actor_user_id": actor_user_id,
        "payload": {
            "assessment_id": assessment_id,
            "accepted": result.get("accepted", 0),
            "updated": result.get("updated", 0),
            "errors_count": len(result.get("errors", []) or []),
        },
    }
    producer.publish(
        topic="eduzim.assessment.marks.recorded.v1",
        key=school_id,
        value=event,
        headers={"source": "academics"},
    )
