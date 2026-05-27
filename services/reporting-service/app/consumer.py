"""Reporting Service — Kafka consumer (PH2-11 entry point).

The reporting-service container has no HTTP surface anymore. It runs ONE
long-running process: this consumer loop. Each domain event is fetched
from Kafka, deserialized, mapped to `ReportingService.consume_event`,
which writes / updates the projection rows in `reporting_db`.

Topics subscribed (matches the union of all academics + finance +
communications publishers):

  * eduzim.student.created.v1            → student.created
  * eduzim.enrollment.created.v1         → enrollment.created
  * eduzim.attendance.recorded.v1        → attendance.recorded
  * eduzim.invoice.created.v1            → invoice.created
  * eduzim.payment.recorded.v1           → payment.recorded
  * eduzim.announcement.created.v1       → announcement.created
  * eduzim.assessment.created.v1         → assessment.created (PH2-9, ignored
                                            by current projections — kept on
                                            the subscription list so adding a
                                            handler later is one-liner)
  * eduzim.assessment.marks.recorded.v1  → marks.recorded (same as above)

The Kafka event envelope (per publisher conventions) is:
    {"event_id": <uuid>, "event_type": <type>, "event_version": 1,
     "occurred_at": <iso>, "school_id": <uuid>, "actor_user_id": <uuid>,
     "payload": {...}}

`ReportingService.consume_event` expects (event_type, school_id, payload)
flat-ish; the bridge below maps the topic→event_type.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

# Make the shared package importable when run inside the container.
sys.path.insert(0, "/shared")
sys.path.insert(0, "../../shared")

logger = logging.getLogger(__name__)


# Topic suffix → projection event_type the ReportingService handler dispatches on.
TOPIC_TO_EVENT_TYPE = {
    "eduzim.student.created.v1": "student.created",
    "eduzim.enrollment.created.v1": "enrollment.created",
    "eduzim.attendance.recorded.v1": "attendance.recorded",
    "eduzim.invoice.created.v1": "invoice.created",
    "eduzim.payment.recorded.v1": "payment.recorded",
    "eduzim.announcement.created.v1": "announcement.created",
    # PH2-9 — new academics emits. No projection handler yet; consuming them
    # marks them processed so we don't see lag, and gives us a place to
    # hook future "marks recorded today" tiles.
    "eduzim.assessment.created.v1": "assessment.created",
    "eduzim.assessment.marks.recorded.v1": "marks.recorded",
}


def _build_handler(SessionLocal):
    """Closure capturing the DB session factory. Each event opens a fresh session."""
    from app.services.reporting_service import ReportingService

    def handler(envelope: dict) -> None:
        # The envelope carries the event_type already (publisher writes the
        # short form into the message), but topic-derived mapping is more
        # robust if a publisher ever drops the field.
        topic = envelope.get("_topic", "")
        event_type = TOPIC_TO_EVENT_TYPE.get(topic, envelope.get("event_type", ""))

        # Some envelopes use the short type ("recorded") + topic context
        # rather than the dotted ("attendance.recorded") form. Normalise.
        if "." not in event_type and topic:
            mapped = TOPIC_TO_EVENT_TYPE.get(topic)
            if mapped:
                event_type = mapped

        # Build the dict shape ReportingService expects.
        event_dict = {
            "event_id": envelope.get("event_id"),
            "event_type": event_type,
            "school_id": envelope.get("school_id"),
            "payload": envelope.get("payload", {}),
        }

        # Open a per-event session — keeps each commit independent and
        # makes connection pool churn predictable under load.
        db = SessionLocal()
        try:
            svc = ReportingService(db)
            result = svc.consume_event(event_dict)
            if result.get("status") == "processed":
                logger.info(
                    "reporting.consumed",
                    extra={"event_id": event_dict["event_id"], "event_type": event_type},
                )
            elif result.get("status") != "duplicate":
                logger.warning(
                    "reporting.unconsumed",
                    extra={"result": result, "event_type": event_type},
                )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return handler


class _TopicAwareConsumer:
    """Thin wrapper that injects the source topic into each event envelope.

    The shared EduZimConsumer is generic — it deserializes JSON and dispatches.
    Our handler needs to know which topic the message came from so it can
    pick the right projection branch when the publisher's `event_type` is
    ambiguous (some short-form publishers emit just "recorded"). This wrapper
    monkey-patches the deserialized event with the topic before handing it
    off to the real handler.
    """

    def __init__(self, config, max_retries: int = 3):
        from eduzim_shared.kafka.consumer import EduZimConsumer
        self._inner = EduZimConsumer(config=config, max_retries=max_retries)

    def subscribe(self, topics):
        self._inner.subscribe(topics)

    def start(self, handler, **kwargs):
        # Wrap the user handler so it sees the topic.
        # The shared consumer calls handler(deserialized_dict) — we extend it
        # to (deserialized_dict + topic injected).
        import json
        from confluent_kafka import KafkaError

        running_flag = {"running": True}
        import signal as _signal

        def _shutdown(*_):
            running_flag["running"] = False
        _signal.signal(_signal.SIGINT, _shutdown)
        _signal.signal(_signal.SIGTERM, _shutdown)

        c = self._inner._consumer  # use the underlying confluent consumer
        try:
            while running_flag["running"]:
                msg = c.poll(timeout=kwargs.get("poll_timeout", 1.0))
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("consumer.error", extra={"err": str(msg.error())})
                    continue
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error("consumer.deserialize_failed", extra={"err": str(e)})
                    c.commit(msg)
                    continue

                event["_topic"] = msg.topic()

                try:
                    handler(event)
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "consumer.handler_error",
                        extra={"err": str(e), "topic": msg.topic()},
                    )
                    # Still commit so a poison message doesn't wedge the
                    # partition forever. The ReportingService.idempotency
                    # check will skip it on next replay.
                c.commit(msg)
        finally:
            c.close()


def run(bootstrap_servers: Optional[str] = None, group_id: str = "reporting-service") -> None:
    """Long-running consumer loop. Blocks until SIGINT/SIGTERM."""
    from app.config import get_settings
    from app.database import SessionLocal

    settings = get_settings()
    bootstrap = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS

    if not settings.KAFKA_ENABLED:
        logger.warning(
            "reporting.consumer.kafka_disabled — nothing to do; exiting cleanly"
        )
        return

    from eduzim_shared.kafka.config import KafkaConfig

    consumer = _TopicAwareConsumer(
        config=KafkaConfig(
            bootstrap_servers=bootstrap,
            group_id=group_id,
        ),
    )

    topics = list(TOPIC_TO_EVENT_TYPE.keys())
    consumer.subscribe(topics)

    handler = _build_handler(SessionLocal)
    logger.info("reporting.consumer.starting", extra={"topics": topics, "group_id": group_id})
    consumer.start(handler)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run()
