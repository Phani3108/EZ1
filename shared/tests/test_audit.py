"""Tests for the shared audit-log helper (Phase 9 / INFRA-018 / Q-016)."""
import json
import uuid

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from eduzim_shared.audit import (
    AuditLogMixin,
    Event,
    record_audit_event,
)


# ─── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def base_and_model():
    """Build a fresh Base + AuditLog model using the shared mixin.

    Each test gets its own Base so SQLAlchemy doesn't complain about
    duplicate table registration across test parametrisations.
    """
    Base = declarative_base()

    class AuditLog(AuditLogMixin, Base):
        __tablename__ = "audit_log"

    return Base, AuditLog


@pytest.fixture
def session_and_model(base_and_model):
    Base, AuditLog = base_and_model
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    s = SessionLocal()
    try:
        yield s, AuditLog
    finally:
        s.close()
        eng.dispose()


# ─── Schema integrity ─────────────────────────────────────────────


class TestSchema:

    def test_mixin_provides_canonical_columns(self):
        names = {c.name for c in AuditLogMixin.__table__.columns} \
            if hasattr(AuditLogMixin, "__table__") else {
                attr for attr in dir(AuditLogMixin)
                if not attr.startswith("_") and hasattr(getattr(AuditLogMixin, attr), "type")
            }
        # The mixin itself isn't a mapped class (no __tablename__) so it
        # has no __table__; we introspect via the attribute name check
        # above. Either way, every canonical column must be present.
        expected = {"id", "occurred_at", "actor_user_id", "actor_role",
                    "school_id", "event_type", "target", "details",
                    "ip_address", "user_agent", "request_id"}
        # Best check: assert the mixin class has all these as Column attributes.
        for name in expected:
            assert hasattr(AuditLogMixin, name), f"mixin missing {name!r}"

    def test_model_can_be_built(self, base_and_model):
        Base, AuditLog = base_and_model
        # If the column spread was broken, this would have raised on
        # Base subclass creation.
        assert AuditLog.__tablename__ == "audit_log"

    def test_table_creates_on_sqlite(self, base_and_model):
        Base, _ = base_and_model
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                            poolclass=StaticPool)
        Base.metadata.create_all(bind=eng)
        inspector = inspect(eng)
        cols = {c["name"] for c in inspector.get_columns("audit_log")}
        assert {"id", "school_id", "event_type", "occurred_at"} <= cols


# ─── record_audit_event ────────────────────────────────────────────


class TestWrite:

    def test_writes_one_row(self, session_and_model):
        session, AuditLog = session_and_model
        school = uuid.uuid4()
        actor = uuid.uuid4()
        record_audit_event(
            session, AuditLog,
            event_type=Event.STUDENT_CREATED,
            school_id=school,
            actor_user_id=actor,
            actor_role="Admin",
            target={"resource": "student", "id": "stu-001"},
            details={"reason": "bulk_import"},
            ip_address="203.0.113.42",
            request_id="req-test-1",
        )
        session.commit()

        rows = session.query(AuditLog).all()
        assert len(rows) == 1
        r = rows[0]
        assert str(r.school_id) == str(school)
        assert str(r.actor_user_id) == str(actor)
        assert r.actor_role == "Admin"
        assert r.event_type == "student.created"
        assert json.loads(r.target) == {"resource": "student", "id": "stu-001"}
        assert json.loads(r.details) == {"reason": "bulk_import"}
        assert r.ip_address == "203.0.113.42"
        assert r.request_id == "req-test-1"

    def test_target_and_details_optional(self, session_and_model):
        session, AuditLog = session_and_model
        record_audit_event(
            session, AuditLog,
            event_type=Event.LOGIN_SUCCESS,
            school_id=uuid.uuid4(),
        )
        session.commit()
        rows = session.query(AuditLog).all()
        assert len(rows) == 1
        assert rows[0].target is None
        assert rows[0].details is None

    def test_user_agent_truncated_to_255(self, session_and_model):
        session, AuditLog = session_and_model
        ua = "X" * 500
        record_audit_event(
            session, AuditLog,
            event_type=Event.LOGIN_SUCCESS,
            school_id=uuid.uuid4(),
            user_agent=ua,
        )
        session.commit()
        assert len(session.query(AuditLog).first().user_agent) == 255

    def test_never_raises_on_db_error(self, session_and_model):
        """Audit failure must not abort the caller's work."""
        session, AuditLog = session_and_model
        # Pass a bogus class to force a constructor crash.
        class _NotAModel:
            def __init__(self, **kw):
                raise RuntimeError("simulated DB failure")
        # Must NOT raise.
        record_audit_event(
            session, _NotAModel,
            event_type=Event.STUDENT_CREATED,
            school_id=uuid.uuid4(),
        )
        # The session should still be usable (we didn't poison it).
        # Verify by writing a real row through the real model:
        record_audit_event(
            session, AuditLog,
            event_type=Event.LOGIN_SUCCESS,
            school_id=uuid.uuid4(),
        )
        session.commit()
        assert session.query(AuditLog).count() == 1

    def test_id_is_unique_per_call(self, session_and_model):
        session, AuditLog = session_and_model
        school = uuid.uuid4()
        for _ in range(5):
            record_audit_event(
                session, AuditLog,
                event_type=Event.STUDENT_CREATED,
                school_id=school,
            )
        session.commit()
        ids = {str(r.id) for r in session.query(AuditLog).all()}
        assert len(ids) == 5


class TestEventConstants:
    """Spot-check that the canonical names exist and are stable."""

    def test_has_auth_events(self):
        assert Event.LOGIN_SUCCESS == "auth.login.success"
        assert Event.LOGIN_FAILED == "auth.login.failed"

    def test_has_student_events(self):
        assert Event.STUDENT_CREATED == "student.created"
        assert Event.STUDENT_UPDATED == "student.updated"
        assert Event.STUDENT_DELETED == "student.deleted"

    def test_has_data_export_events(self):
        assert Event.DATA_EXPORT_SCHOOL == "data.export.school"
        assert Event.DATA_EXPORT_PARENT == "data.export.parent"

    def test_has_tenancy_events(self):
        assert Event.TENANCY_PROMOTION_STARTED == "tenancy.promotion.started"
        assert Event.TENANCY_PROMOTION_COMPLETED == "tenancy.promotion.completed"

    def test_events_are_frozen(self):
        # Dataclass(frozen=True) — assignment fails.
        with pytest.raises((AttributeError, Exception)):
            Event.LOGIN_SUCCESS = "spoofed"  # type: ignore[misc]
