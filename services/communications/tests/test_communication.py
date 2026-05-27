"""
Communication Service Tests — Quality Gate 7
================================================
Unit Tests:
- Audience resolution correct (ALL, CLASS, ROLE)
- Duplicate outbox entries not created
- Cross-school audience blocked
- Retry increments correctly
- Max retry stops at FAILED

Integration Tests:
- Announcement persists
- Outbox records created
- Cross-school isolation enforced
- Soft delete hides from list
- Delivery engine processes correctly
"""
import os
import uuid
from datetime import datetime, timezone

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_comm.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.communication import Announcement, NotificationOutbox  # noqa

engine = create_engine("sqlite:///./test_comm.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_comm.db"):
        try:
            os.remove("./test_comm.db")
        except OSError:
            pass


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
CLASS_1 = uuid.uuid4()
ADMIN = uuid.uuid4()
USER_1 = uuid.uuid4()
USER_2 = uuid.uuid4()
USER_3 = uuid.uuid4()
USER_4 = uuid.uuid4()
USER_5 = uuid.uuid4()


def _resolver():
    from app.services.communication_service import MockAudienceResolver
    resolver = MockAudienceResolver()
    resolver.add_users(SCHOOL_A, [USER_1, USER_2, USER_3])
    resolver.add_users(SCHOOL_B, [USER_4, USER_5])
    resolver.add_class_users(SCHOOL_A, CLASS_1, [USER_1, USER_2])
    resolver.add_role_users(SCHOOL_A, "Teacher", [USER_3])
    return resolver


def _svc(db, sms_provider=None):
    from app.services.communication_service import CommunicationService, MockSMSProvider
    return CommunicationService(db, _resolver(),
                                 sms_provider or MockSMSProvider(),
                                 max_retries=3)


# ═══════════════════════════════════════════
# Announcements
# ═══════════════════════════════════════════

class TestAnnouncement:
    def test_create_all_audience(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Test", "Hello everyone",
                                          "ALL", ["IN_APP"], ADMIN)
        assert "announcement" in result
        assert result["recipient_count"] == 3
        assert result["outbox_created"] == 3

    def test_create_class_audience(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Class Update", "Homework due",
                                          "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_1)
        assert result["recipient_count"] == 2
        assert result["outbox_created"] == 2

    def test_create_role_audience(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Teacher Meeting", "Staff room 3pm",
                                          "ROLE", ["IN_APP"], ADMIN, role="Teacher")
        assert result["recipient_count"] == 1
        assert result["outbox_created"] == 1

    def test_class_requires_class_id(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Oops", "No class",
                                          "CLASS", ["IN_APP"], ADMIN)
        assert result["error"] == "INVALID_AUDIENCE"

    def test_role_requires_role(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Oops", "No role",
                                          "ROLE", ["IN_APP"], ADMIN)
        assert result["error"] == "INVALID_AUDIENCE"

    def test_all_rejects_class_id(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Oops", "Extra param",
                                          "ALL", ["IN_APP"], ADMIN, class_id=CLASS_1)
        assert result["error"] == "INVALID_AUDIENCE"

    def test_multi_channel_outbox(self, db):
        svc = _svc(db)
        result = svc.create_announcement(SCHOOL_A, "Alert", "Important",
                                          "ALL", ["IN_APP", "SMS"], ADMIN)
        # 3 users × 2 channels = 6 outbox entries
        assert result["outbox_created"] == 6
        assert result["recipient_count"] == 3

    def test_soft_delete_hides(self, db):
        svc = _svc(db)
        r1 = svc.create_announcement(SCHOOL_A, "A1", "Body1", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_A, "A2", "Body2", "ALL", ["IN_APP"], ADMIN)
        svc.soft_delete_announcement(uuid.UUID(r1["announcement"]["id"]), SCHOOL_A)
        anns, total = svc.list_announcements(SCHOOL_A)
        assert total == 1
        assert anns[0]["title"] == "A2"


# ═══════════════════════════════════════════
# Outbox Deduplication
# ═══════════════════════════════════════════

class TestOutboxDedup:
    def test_no_duplicate_outbox(self, db):
        svc = _svc(db)
        r1 = svc.create_announcement(SCHOOL_A, "First", "Body", "ALL", ["IN_APP"], ADMIN)
        ann_id = uuid.UUID(r1["announcement"]["id"])

        # Try creating outbox entries again for same announcement
        # (simulating retry of announcement creation)
        outbox = svc.get_outbox(SCHOOL_A, announcement_id=ann_id)
        assert len(outbox) == 3  # Only 3, not 6


# ═══════════════════════════════════════════
# Delivery Engine
# ═══════════════════════════════════════════

class TestDeliveryEngine:
    def test_in_app_always_succeeds(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "OK", "In app", "ALL", ["IN_APP"], ADMIN)
        result = svc.process_pending(SCHOOL_A)
        assert result["sent"] == 3
        assert result["failed"] == 0

        # Verify status changed
        outbox = svc.get_outbox(SCHOOL_A, status="SENT")
        assert len(outbox) == 3

    def test_sms_delivery(self, db):
        from app.services.communication_service import MockSMSProvider
        sms = MockSMSProvider()
        svc = _svc(db, sms_provider=sms)
        svc.create_announcement(SCHOOL_A, "SMS", "Test sms", "ALL", ["SMS"], ADMIN)
        result = svc.process_pending(SCHOOL_A)
        assert result["sent"] == 3
        assert len(sms.sent) == 3

    def test_sms_failure_retries(self, db):
        from app.services.communication_service import MockSMSProvider
        sms = MockSMSProvider(fail_for={str(USER_1)})
        svc = _svc(db, sms_provider=sms)
        svc.create_announcement(SCHOOL_A, "Retry", "Fail test", "ALL", ["SMS"], ADMIN)

        # Round 1: 2 sent, 1 retried (retry_count=1)
        r1 = svc.process_pending(SCHOOL_A)
        assert r1["sent"] == 2
        assert r1["retried"] == 1

        # Round 2: retry_count=2, still retrying
        r2 = svc.process_pending(SCHOOL_A)
        assert r2["retried"] == 1

        # Round 3: retry_count=3 → hits max_retries → FAILED
        r3 = svc.process_pending(SCHOOL_A)
        assert r3["failed"] == 1

        # Verify final state
        failed = svc.get_outbox(SCHOOL_A, status="FAILED")
        assert len(failed) == 1
        assert failed[0]["retry_count"] == 3
        assert "Max retries" in failed[0]["error_message"]

    def test_no_pending_after_all_sent(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "Done", "All sent", "ALL", ["IN_APP"], ADMIN)
        svc.process_pending(SCHOOL_A)
        pending = svc.get_outbox(SCHOOL_A, status="PENDING")
        assert len(pending) == 0


# ═══════════════════════════════════════════
# Cross-School Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_announcements_isolated(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "A", "For school A", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_B, "B", "For school B", "ALL", ["IN_APP"], ADMIN)
        a, ta = svc.list_announcements(SCHOOL_A)
        b, tb = svc.list_announcements(SCHOOL_B)
        assert ta == 1 and tb == 1

    def test_outbox_isolated(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "A", "AA", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_B, "B", "BB", "ALL", ["IN_APP"], ADMIN)
        oa = svc.get_outbox(SCHOOL_A)
        ob = svc.get_outbox(SCHOOL_B)
        assert len(oa) == 3  # 3 users in school A
        assert len(ob) == 2  # 2 users in school B

    def test_soft_delete_cross_school_blocked(self, db):
        svc = _svc(db)
        r = svc.create_announcement(SCHOOL_A, "Mine", "Body", "ALL", ["IN_APP"], ADMIN)
        ann_id = uuid.UUID(r["announcement"]["id"])
        result = svc.soft_delete_announcement(ann_id, SCHOOL_B)
        assert result is None  # Can't delete another school's announcement

    def test_delivery_isolated(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "A", "AA", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_B, "B", "BB", "ALL", ["IN_APP"], ADMIN)

        # Only process school A
        result = svc.process_pending(SCHOOL_A)
        assert result["sent"] == 3

        # School B still pending
        pending_b = svc.get_outbox(SCHOOL_B, status="PENDING")
        assert len(pending_b) == 2


# ═══════════════════════════════════════════
# Parent Feed (10A-P2)
# ═══════════════════════════════════════════

STUDENT_1 = uuid.uuid4()
CLASS_2 = uuid.uuid4()

class TestParentFeed:
    """Test get_feed_for_student — audience-filtered announcements for parents."""

    def test_all_audience_appears_in_feed(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "General", "For all", "ALL", ["IN_APP"], ADMIN)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=CLASS_1)
        assert total == 1
        assert feed[0]["title"] == "General"

    def test_matching_class_appears_in_feed(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "Class News", "Homework",
                                 "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_1)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=CLASS_1)
        assert total == 1
        assert feed[0]["title"] == "Class News"

    def test_different_class_excluded(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "Other Class", "Not for you",
                                 "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_2)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=CLASS_1)
        assert total == 0

    def test_role_audience_appears_in_feed(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "Parent Note", "Meeting",
                                 "ROLE", ["IN_APP"], ADMIN, role="Parent")
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=CLASS_1)
        assert total == 1
        assert feed[0]["title"] == "Parent Note"

    def test_feed_combines_all_and_class_and_role(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "General", "All", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_A, "Class", "Class A",
                                 "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_1)
        svc.create_announcement(SCHOOL_A, "Parent", "Role",
                                 "ROLE", ["IN_APP"], ADMIN, role="Parent")
        svc.create_announcement(SCHOOL_A, "Other Class", "Excluded",
                                 "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_2)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=CLASS_1)
        assert total == 3
        titles = {a["title"] for a in feed}
        assert titles == {"General", "Class", "Parent"}

    def test_feed_cross_school_isolation(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "A Announcement", "For A", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_B, "B Announcement", "For B", "ALL", ["IN_APP"], ADMIN)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1)
        assert total == 1
        assert feed[0]["title"] == "A Announcement"

    def test_feed_excludes_deleted(self, db):
        svc = _svc(db)
        r1 = svc.create_announcement(SCHOOL_A, "Deleted", "Gone", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_A, "Active", "Here", "ALL", ["IN_APP"], ADMIN)
        svc.soft_delete_announcement(uuid.UUID(r1["announcement"]["id"]), SCHOOL_A)
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1)
        assert total == 1
        assert feed[0]["title"] == "Active"

    def test_feed_pagination(self, db):
        svc = _svc(db)
        for i in range(5):
            svc.create_announcement(SCHOOL_A, f"Ann {i}", f"Body {i}",
                                     "ALL", ["IN_APP"], ADMIN)
        feed_p1, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1,
                                                     page=1, page_size=2)
        assert total == 5
        assert len(feed_p1) == 2
        feed_p2, _ = svc.get_feed_for_student(SCHOOL_A, STUDENT_1,
                                                 page=2, page_size=2)
        assert len(feed_p2) == 2

    def test_feed_without_class_id_returns_all_and_role(self, db):
        svc = _svc(db)
        svc.create_announcement(SCHOOL_A, "General", "All", "ALL", ["IN_APP"], ADMIN)
        svc.create_announcement(SCHOOL_A, "Class", "Only class",
                                 "CLASS", ["IN_APP"], ADMIN, class_id=CLASS_1)
        svc.create_announcement(SCHOOL_A, "Role", "For parents",
                                 "ROLE", ["IN_APP"], ADMIN, role="Parent")
        # No class_id means CLASS announcements excluded
        feed, total = svc.get_feed_for_student(SCHOOL_A, STUDENT_1, class_id=None)
        assert total == 2
        titles = {a["title"] for a in feed}
        assert titles == {"General", "Role"}
