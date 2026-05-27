"""
EduZim Kafka Producer
=====================
Wrapper around confluent-kafka Producer with JSON serialization,
delivery callbacks, and structured logging.

Usage:
    from eduzim_shared.kafka.producer import EduZimProducer
    from eduzim_shared.kafka.config import KafkaConfig, Topics

    producer = EduZimProducer(KafkaConfig(bootstrap_servers="kafka:9092"))
    producer.publish(
        topic=Topics.USER_CREATED,
        key=str(user.id),
        value={"user_id": str(user.id), "school_id": str(user.school_id)},
        headers={"source": "auth-service"},
    )
    producer.flush()
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from confluent_kafka import Producer, KafkaError

from eduzim_shared.kafka.config import KafkaConfig

logger = logging.getLogger(__name__)

# INFRA-022 (Phase 5): every producer created in this process registers
# itself here so the shared app_factory lifespan can flush them on shutdown.
# WeakValueDictionary would be ideal but consumers usually keep producers
# as module-level singletons, so a regular dict is fine.
_registered_producers: "dict[str, EduZimProducer]" = {}


class EduZimProducer:
    """Production-grade Kafka producer with JSON serialization."""

    def __init__(self, config: KafkaConfig, label: Optional[str] = None):
        self._config = config
        self._label = label or f"producer-{id(self):x}"
        self._producer = Producer(config.producer_config())
        _registered_producers[self._label] = self
        logger.info(
            "Kafka producer initialized",
            extra={
                "bootstrap_servers": config.bootstrap_servers,
                "label": self._label,
            },
        )

    def publish(
        self,
        topic: str,
        value: dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish a message to a Kafka topic.

        Args:
            topic: Target topic name
            value: Message payload (will be JSON-serialized)
            key: Optional partition key (typically entity ID)
            headers: Optional message headers
        """
        # Enrich the event envelope
        envelope = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "data": value,
        }

        serialized_value = json.dumps(envelope, default=str).encode("utf-8")
        serialized_key = key.encode("utf-8") if key else None

        # Convert headers to confluent-kafka format
        kafka_headers = None
        if headers:
            kafka_headers = [(k, v.encode("utf-8")) for k, v in headers.items()]

        try:
            self._producer.produce(
                topic=topic,
                key=serialized_key,
                value=serialized_value,
                headers=kafka_headers,
                callback=self._delivery_callback,
            )
            # Trigger any queued delivery callbacks
            self._producer.poll(0)

            logger.info(
                f"Event published to {topic}",
                extra={
                    "topic": topic,
                    "event_id": envelope["event_id"],
                    "key": key,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to publish to {topic}: {e}",
                extra={"topic": topic, "key": key},
                exc_info=True,
            )
            raise

    def flush(self, timeout: float = 10.0) -> int:
        """
        Wait for all messages to be delivered.

        Args:
            timeout: Max seconds to wait

        Returns:
            Number of messages still in queue (0 = all delivered)
        """
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning(f"Kafka flush: {remaining} messages still in queue")
        return remaining

    def close(self) -> None:
        """Flush and close the producer."""
        self.flush()
        logger.info("Kafka producer closed")

    @staticmethod
    def _delivery_callback(err, msg):
        """Callback invoked per message delivery."""
        if err is not None:
            logger.error(
                f"Kafka delivery failed: {err}",
                extra={
                    "topic": msg.topic(),
                    "partition": msg.partition(),
                },
            )
        else:
            logger.debug(
                f"Delivered to {msg.topic()}[{msg.partition()}] @ offset {msg.offset()}",
            )
