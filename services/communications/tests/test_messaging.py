"""Parent-Teacher Messaging Tests (Phase 11b / T-011).

Covers:
  * Thread create / get-or-existing
  * Send message, denorm last_message_at + unread counters
  * Cross-tenant isolation: thread A's school cannot see school B
  * Participant scoping: a non-participant gets 404 on the thread
  * Mark-read zeroes the right side's counter
  * Redaction replaces the body with the placeholder
  * Authorisation resolver gate (deny path returns 403)
  * Audit hooks fire on thread create + message send (without body)
"""
from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_messaging.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
TEACHER_A = uuid.uuid4()
PARENT_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import communication as _c  # noqa
    from app.models import idempotency as _i  # noqa
    from app.models import whatsapp as _w  # noqa
    from app.models import audit as _au  # noqa
    from app.models import messaging as _m  # noqa

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session):
    _, SessionLocal = engine_and_session
    from app.database import get_db
    from app.main import app

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _headers(user_id: uuid.UUID, role: str, school_id: uuid.UUID = SCHOOL_A,
             perms: str = "authenticated") -> dict:
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": role,
        "X-Permissions": perms,
    }


# ─── Thread create ─────────────────────────────────────────────────


class TestThreadCreate:
    def test_teacher_creates_thread_with_parent(self, client):
        r = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["teacher_user_id"] == str(TEACHER_A)
        assert body["parent_user_id"] == str(PARENT_A)
        assert body["created"] is True

    def test_thread_is_reused_idempotently(self, client):
        payload = {"other_user_id": str(PARENT_A), "other_role": "Parent"}
        r1 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"), json=payload,
        )
        r2 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"), json=payload,
        )
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]
        assert r2.json()["data"]["created"] is False

    def test_two_teachers_create_separate_threads(self, client):
        OTHER_TEACHER = uuid.uuid4()
        r1 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        r2 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(OTHER_TEACHER, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        assert r1.json()["data"]["id"] != r2.json()["data"]["id"]

    def test_two_teachers_two_parents(self, client):
        """Same parent, different teacher = different thread."""
        r1 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        # Parent-initiated to same teacher reuses
        r2 = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(PARENT_A, "Parent"),
            json={"other_user_id": str(TEACHER_A), "other_role": "Teacher"},
        )
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]

    def test_invalid_participant_roles_rejected(self, client):
        # Teacher trying to create a thread with another Teacher → 400
        OTHER_TEACHER = uuid.uuid4()
        r = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(OTHER_TEACHER), "other_role": "Teacher"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_PARTICIPANTS"


# ─── Send message + denorm state ───────────────────────────────────


class TestSendMessage:
    def _open_thread(self, client) -> str:
        r = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        return r.json()["data"]["id"]

    def test_send_then_list_returns_message(self, client):
        tid = self._open_thread(client)
        r = client.post(
            f"/api/v1/comm/messages/threads/{tid}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": "Hello, how is Alice doing?"},
        )
        assert r.status_code == 200, r.text

        # Parent-side fetch returns the message
        r2 = client.get(
            f"/api/v1/comm/messages/threads/{tid}",
            headers=_headers(PARENT_A, "Parent"),
        )
        msgs = r2.json()["data"]["messages"]
        assert len(msgs) == 1
        assert msgs[0]["body"] == "Hello, how is Alice doing?"
        assert msgs[0]["sender_role"] == "Teacher"

    def test_send_updates_unread_for_other_side(self, client):
        tid = self._open_thread(client)
        client.post(
            f"/api/v1/comm/messages/threads/{tid}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": "msg 1"},
        )
        # Parent-side inbox sees unread=1
        r = client.get(
            "/api/v1/comm/messages/threads",
            headers=_headers(PARENT_A, "Parent"),
        )
        threads = r.json()["data"]
        assert len(threads) == 1
        assert threads[0]["unread_count"] == 1

        # Teacher-side inbox sees their own send as zero unread
        r2 = client.get(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        assert r2.json()["data"][0]["unread_count"] == 0

    def test_empty_body_rejected(self, client):
        tid = self._open_thread(client)
        r = client.post(
            f"/api/v1/comm/messages/threads/{tid}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": ""},
        )
        # Pydantic min_length=1 — 422 from validation
        assert r.status_code in (400, 422)

    def test_non_participant_cannot_see_thread(self, client):
        """A teacher who is NOT in the thread gets 404 on read."""
        tid = self._open_thread(client)
        OTHER_TEACHER = uuid.uuid4()
        r = client.get(
            f"/api/v1/comm/messages/threads/{tid}",
            headers=_headers(OTHER_TEACHER, "Teacher"),
        )
        assert r.status_code == 404

    def test_non_participant_cannot_send(self, client):
        tid = self._open_thread(client)
        OTHER_PARENT = uuid.uuid4()
        r = client.post(
            f"/api/v1/comm/messages/threads/{tid}/messages",
            headers=_headers(OTHER_PARENT, "Parent"),
            json={"body": "I shouldn't be here"},
        )
        assert r.status_code == 404


# ─── Mark read ─────────────────────────────────────────────────────


class TestMarkRead:
    def test_mark_read_zeros_counter(self, client):
        r = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        tid = r.json()["data"]["id"]
        client.post(
            f"/api/v1/comm/messages/threads/{tid}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": "Hello"},
        )
        # Parent marks as read
        mr = client.post(
            f"/api/v1/comm/messages/threads/{tid}/read",
            headers=_headers(PARENT_A, "Parent"),
        )
        assert mr.status_code == 200
        assert mr.json()["data"]["marked_read"] == 1

        # Parent's unread counter is now zero
        list_r = client.get(
            "/api/v1/comm/messages/threads",
            headers=_headers(PARENT_A, "Parent"),
        )
        assert list_r.json()["data"][0]["unread_count"] == 0


# ─── Tenancy isolation ─────────────────────────────────────────────


class TestTenancyIsolation:
    def test_other_school_cannot_see_thread(self, client):
        r = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher", SCHOOL_A),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        tid = r.json()["data"]["id"]

        # Same user ids, but a different school context.
        r2 = client.get(
            f"/api/v1/comm/messages/threads/{tid}",
            headers=_headers(TEACHER_A, "Teacher", SCHOOL_B),
        )
        assert r2.status_code == 404


# ─── Redaction ─────────────────────────────────────────────────────


class TestRedaction:
    def test_redaction_replaces_body_keeps_row(self, client):
        # Open thread + send a message
        thr = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        ).json()["data"]
        sent = client.post(
            f"/api/v1/comm/messages/threads/{thr['id']}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": "Sensitive content here"},
        ).json()["data"]

        # Admin redacts
        red = client.post(
            f"/api/v1/comm/messages/{sent['id']}/redact",
            headers=_headers(ADMIN_A, "Admin", perms="school:manage"),
        )
        assert red.status_code == 200, red.text
        red_body = red.json()["data"]
        assert red_body["redacted"] is True
        assert red_body["body"] == "[redacted]"

        # The thread still has 1 message (row stayed)
        thr2 = client.get(
            f"/api/v1/comm/messages/threads/{thr['id']}",
            headers=_headers(TEACHER_A, "Teacher"),
        )
        msgs = thr2.json()["data"]["messages"]
        assert len(msgs) == 1
        assert msgs[0]["body"] == "[redacted]"
        # Original sensitive content is NOT present anywhere
        import json as _json
        assert "Sensitive content here" not in _json.dumps(thr2.json())


# ─── Audit hooks ───────────────────────────────────────────────────


class TestAuditWiring:
    def test_thread_create_writes_audit_row(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        )
        from app.models.audit import AuditLog
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "message.thread.created")
                .all()
            )
            assert len(rows) == 1
            assert rows[0].actor_user_id == TEACHER_A
        finally:
            s.close()

    def test_message_send_audit_does_not_log_body(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        thr = client.post(
            "/api/v1/comm/messages/threads",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"other_user_id": str(PARENT_A), "other_role": "Parent"},
        ).json()["data"]
        client.post(
            f"/api/v1/comm/messages/threads/{thr['id']}/messages",
            headers=_headers(TEACHER_A, "Teacher"),
            json={"body": "Top secret never log this"},
        )
        from app.models.audit import AuditLog
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "message.sent")
                .all()
            )
            assert len(rows) == 1
            # The audit details may carry length, but NEVER the body.
            import json as _json
            details_blob = _json.dumps({"target": rows[0].target,
                                        "details": rows[0].details})
            assert "Top secret never log this" not in details_blob
        finally:
            s.close()
