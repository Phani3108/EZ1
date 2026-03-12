"""
EduZim Kafka Consumer
=====================
Wrapper around confluent-kafka Consumer with JSON deserialization,
idempotent processing, retry strategy, and manual offset commit.

Usage:
    from eduzim_shared.kafka.consumer import EduZimConsumer
    from eduzim_shared.kafka.config import KafkaConfig, Topics

    def handle_user_created(event: dict):
        print(f"User created: {event['data']['user_id']}")

    consumer = EduZimConsumer(
        config=KafkaConfig(
            bootstrap_servers="kafka:9092",
            group_id="reporting-service",
        ),
    )
    consumer.subscribe([Topics.USER_CREATED])
    consumer.start(handler=handle_user_created)
"""

import json
import logging
import signal
import time
from typing import Callable, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from eduzim_shared.kafka.config import KafkaConfig

logger = logging.getLogger(__name__)


class EduZimConsumer:
    """
    Production-grade Kafka consumer with:
    - JSON deserialization
    - Manual offset commit (at-least-once delivery)
    - Idempotent processing support (via event_id tracking)
    - Configurable retry strategy
    - Graceful shutdown
    """

    def __init__(
        self,
        config: KafkaConfig,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ):
        self._config = config
        self._consumer = Consumer(config.consumer_config())
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds
        self._running = False
        self._processed_event_ids: set[str] = set()
        self._max_idempotency_cache = 10000

        logger.info(
            "Kafka consumer initialized",
            extra={
                "bootstrap_servers": config.bootstrap_servers,
                "group_id": config.group_id,
            },
        )

    def subscribe(self, topics: list[str]) -> None:
        """Subscribe to one or more topics."""
        self._consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")

    def start(
        self,
        handler: Callable[[dict], None],
        poll_timeout: float = 1.0,
        idempotent: bool = True,
    ) -> None:
        """
        Start consuming messages in a blocking loop.

        Args:
            handler: Callback function receiving deserialized event dicts
            poll_timeout: Seconds to wait per poll
            idempotent: Skip already-processed event_ids (in-memory cache)
        """
        self._running = True

        # Graceful shutdown on SIGINT/SIGTERM
        def shutdown(signum, frame):
            logger.info("Shutdown signal received")
            self._running = False

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        logger.info("Consumer loop started")

        try:
            while self._running:
                msg = self._consumer.poll(timeout=poll_timeout)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            f"End of partition: {msg.topic()}[{msg.partition()}]"
                        )
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue

                # Deserialize
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize message: {e}")
                    self._consumer.commit(msg)
                    continue

                event_id = event.get("event_id", "")

                # Idempotency check
                if idempotent and event_id in self._processed_event_ids:
                    logger.debug(f"Skipping duplicate event: {event_id}")
                    self._consumer.commit(msg)
                    continue

                # Process with retry
                success = self._process_with_retry(handler, event, event_id)

                if success:
                    # Track for idempotency
                    if idempotent:
                        self._processed_event_ids.add(event_id)
                        # Evict oldest entries if cache is too large
                        if len(self._processed_event_ids) > self._max_idempotency_cache:
                            self._processed_event_ids.clear()

                    # Commit offset (at-least-once)
                    self._consumer.commit(msg)
                else:
                    logger.error(
                        f"Event processing failed after {self._max_retries} retries",
                        extra={"event_id": event_id, "topic": msg.topic()},
                    )
                    # Commit anyway to avoid infinite loop on poison messages
                    self._consumer.commit(msg)

        except KafkaException as e:
            logger.error(f"Kafka exception: {e}", exc_info=True)
        finally:
            self.close()

    def _process_with_retry(
        self,
        handler: Callable[[dict], None],
        event: dict,
        event_id: str,
    ) -> bool:
        """Process an event with retry logic."""
        for attempt in range(1, self._max_retries + 1):
            try:
                handler(event)
                return True
            except Exception as e:
                logger.warning(
                    f"Handler failed (attempt {attempt}/{self._max_retries}): {e}",
                    extra={"event_id": event_id, "attempt": attempt},
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff * attempt)
        return False

    def close(self) -> None:
        """Close the consumer connection."""
        self._running = False
        self._consumer.close()
        logger.info("Kafka consumer closed")
