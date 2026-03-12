"""
EduZim Kafka Admin — Topic Auto-Creation
=========================================
Ensures all required Kafka topics exist on service startup.

Usage:
    from eduzim_shared.kafka.admin import ensure_topics
    from eduzim_shared.kafka.config import Topics

    ensure_topics(
        bootstrap_servers="kafka:9092",
        topics=Topics.all_topics(),
    )
"""

import logging
from typing import Optional

from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


def ensure_topics(
    bootstrap_servers: str,
    topics: list[str],
    num_partitions: int = 3,
    replication_factor: int = 1,
    timeout: float = 10.0,
) -> None:
    """
    Ensure all specified Kafka topics exist.
    Creates missing topics with the given configuration.

    Args:
        bootstrap_servers: Kafka broker addresses
        topics: List of topic names to ensure
        num_partitions: Number of partitions per topic
        replication_factor: Replication factor (1 for dev, 3 for prod)
        timeout: Admin operation timeout in seconds
    """
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    # Get existing topics
    metadata = admin.list_topics(timeout=timeout)
    existing_topics = set(metadata.topics.keys())

    # Find missing topics
    missing = [t for t in topics if t not in existing_topics]

    if not missing:
        logger.info(f"All {len(topics)} topics already exist")
        return

    # Create missing topics
    new_topics = [
        NewTopic(
            topic=topic,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
        )
        for topic in missing
    ]

    logger.info(f"Creating {len(missing)} missing topics: {missing}")

    futures = admin.create_topics(new_topics, operation_timeout=timeout)

    for topic, future in futures.items():
        try:
            future.result()
            logger.info(f"  ✅ Created topic: {topic}")
        except Exception as e:
            logger.error(f"  ❌ Failed to create topic {topic}: {e}")
            raise
