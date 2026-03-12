"""
EduZim Kafka Configuration
===========================
Centralized Kafka topic and configuration management.
All topics use versioned naming: eduzim.<domain>.<entity>.<action>.v<N>
"""

from dataclasses import dataclass
from typing import Optional


class Topics:
    """All EduZim Kafka topics — Phase 1 versioned."""

    # Auth events
    USER_CREATED = "eduzim.auth.user.created.v1"

    # School events
    SCHOOL_CREATED = "eduzim.school.school.created.v1"
    ACADEMIC_YEAR_CREATED = "eduzim.school.academic_year.created.v1"
    TERM_CREATED = "eduzim.school.term.created.v1"
    CLASS_CREATED = "eduzim.school.class.created.v1"
    SUBJECT_CREATED = "eduzim.school.subject.created.v1"
    CLASS_TEACHER_ASSIGNED = "eduzim.school.class_teacher.assigned.v1"

    # Student events
    STUDENT_CREATED = "eduzim.student.student.created.v1"
    ENROLLMENT_CREATED = "eduzim.student.enrollment.created.v1"

    # Attendance events
    ATTENDANCE_RECORDED = "eduzim.attendance.recorded.v1"

    # Fees events
    INVOICE_CREATED = "eduzim.fees.invoice.created.v1"
    PAYMENT_RECORDED = "eduzim.fees.payment.recorded.v1"

    # Communication events
    ANNOUNCEMENT_CREATED = "eduzim.comm.announcement.created.v1"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Return all defined topic names."""
        return [
            value for key, value in vars(cls).items()
            if not key.startswith("_") and isinstance(value, str) and key != "all_topics"
        ]


@dataclass
class KafkaConfig:
    """Kafka connection configuration."""
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "eduzim"
    group_id: Optional[str] = None

    # Producer settings
    acks: str = "all"
    retries: int = 3
    retry_backoff_ms: int = 500
    max_in_flight_requests: int = 1

    # Consumer settings
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False
    session_timeout_ms: int = 30000
    max_poll_interval_ms: int = 300000

    def producer_config(self) -> dict:
        """Generate confluent-kafka producer configuration."""
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "acks": self.acks,
            "retries": self.retries,
            "retry.backoff.ms": self.retry_backoff_ms,
            "max.in.flight.requests.per.connection": self.max_in_flight_requests,
            "enable.idempotence": True,
        }

    def consumer_config(self) -> dict:
        """Generate confluent-kafka consumer configuration."""
        return {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id or f"{self.client_id}-consumer",
            "auto.offset.reset": self.auto_offset_reset,
            "enable.auto.commit": self.enable_auto_commit,
            "session.timeout.ms": self.session_timeout_ms,
            "max.poll.interval.ms": self.max_poll_interval_ms,
        }
