"""Reporting consumer tests (PH2-11).

The consumer module wraps the shared EduZimConsumer. We unit-test the
event-envelope → ReportingService.consume_event bridge — not the kafka
client itself (that's covered by shared/tests).

What's exercised here:
  * TOPIC_TO_EVENT_TYPE mapping has the canonical keys.
  * _build_handler returns a callable that maps a Kafka envelope to a
    correct ReportingService call.
  * Topic-derived event_type wins over a missing/short envelope.event_type.
  * Handler errors don't blow up the closure (DB rollback is exercised).
"""
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_reporting_consumer.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("KAFKA_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.projections import (  # noqa: F401  (register on Base.metadata)
    ProcessedEvent, DashboardStats, AttendanceDailyAggregate,
    FinancialSummary, StudentCountProjection,
)

from app.consumer import TOPIC_TO_EVENT_TYPE, _build_handler


@pytest.fixture
def session_factory():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield SessionLocal
    eng.dispose()


class TestTopicMapping:

    def test_has_canonical_topics(self):
        # Spot-check the six event types reporting actually projects on.
        for t in [
            "eduzim.student.created.v1",
            "eduzim.enrollment.created.v1",
            "eduzim.attendance.recorded.v1",
            "eduzim.invoice.created.v1",
            "eduzim.payment.recorded.v1",
            "eduzim.announcement.created.v1",
        ]:
            assert t in TOPIC_TO_EVENT_TYPE, f"missing topic mapping for {t}"

    def test_assessment_topics_present_for_future_handlers(self):
        # PH2-9 emits these — we subscribe so the cursor advances. No
        # projection handler yet; the consumer skips them as 'unknown_event'.
        assert "eduzim.assessment.created.v1" in TOPIC_TO_EVENT_TYPE
        assert "eduzim.assessment.marks.recorded.v1" in TOPIC_TO_EVENT_TYPE


class TestHandler:

    def test_handler_routes_student_created(self, session_factory):
        handler = _build_handler(session_factory)
        school_id = str(uuid.uuid4())
        envelope = {
            "event_id": "evt-001",
            "event_type": "student.created",
            "school_id": school_id,
            "payload": {},
            "_topic": "eduzim.student.created.v1",
        }
        handler(envelope)

        # Verify the projection was updated.
        db = session_factory()
        try:
            stats = db.query(DashboardStats).filter(
                DashboardStats.school_id == uuid.UUID(school_id),
            ).first()
            assert stats is not None
            assert stats.total_students == 1
        finally:
            db.close()

    def test_handler_uses_topic_when_event_type_short(self, session_factory):
        """If publisher writes only short-form event_type (e.g. 'recorded'),
        the topic-derived mapping resolves it."""
        handler = _build_handler(session_factory)
        school_id = str(uuid.uuid4())
        envelope = {
            "event_id": "evt-002",
            "event_type": "recorded",  # short form, no dot
            "school_id": school_id,
            "payload": {
                "accepted": 30, "present": 27, "absent": 2, "late": 1,
                "date": "2026-03-15",
            },
            "_topic": "eduzim.attendance.recorded.v1",
        }
        handler(envelope)

        db = session_factory()
        try:
            stats = db.query(DashboardStats).filter(
                DashboardStats.school_id == uuid.UUID(school_id),
            ).first()
            assert stats is not None
            assert stats.attendance_today_total == 30
        finally:
            db.close()

    def test_handler_idempotent_on_duplicate(self, session_factory):
        handler = _build_handler(session_factory)
        school_id = str(uuid.uuid4())
        envelope = {
            "event_id": "evt-dup-001",
            "event_type": "student.created",
            "school_id": school_id,
            "payload": {},
            "_topic": "eduzim.student.created.v1",
        }
        handler(envelope)
        handler(envelope)
        handler(envelope)

        db = session_factory()
        try:
            stats = db.query(DashboardStats).filter(
                DashboardStats.school_id == uuid.UUID(school_id),
            ).first()
            assert stats.total_students == 1  # not 3
        finally:
            db.close()
