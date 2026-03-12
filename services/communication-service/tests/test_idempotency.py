"""
Communication Service Idempotency Tests — Quality Gate 10B-4
===============================================================
Tests for X-Request-Id based idempotency on the announcements endpoint.
Verifies that duplicate announcement creations from offline sync are de-duplicated.
"""
import os
import uuid

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_comm_idempotency.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.communication import Announcement, NotificationOutbox  # noqa
from app.models.idempotency import IdempotencyKey  # noqa: register model

engine = create_engine(
    "sqlite:///./test_comm_idempotency.db",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    TestSession.close_all()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_comm_idempotency.db"):
        try:
            os.remove("./test_comm_idempotency.db")
        except OSError:
            pass


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


# ───── Constants ─────

SCHOOL_A = uuid.uuid4()
TEACHER_1 = uuid.uuid4()
CLASS_A = uuid.uuid4()


# ───── Helpers ─────

from fastapi.testclient import TestClient
from jose import jwt as jose_jwt


def _make_token(user_id=None, school_id=None, roles=None):
    payload = {
        "sub": str(user_id or TEACHER_1),
        "school_id": str(school_id or SCHOOL_A),
        "roles": roles or ["Teacher"],
        "type": "access",
    }
    return jose_jwt.encode(payload, "test-secret", algorithm="HS256")


def _teacher_headers(request_id=None):
    h = {"Authorization": f"Bearer {_make_token()}"}
    if request_id:
        h["X-Request-Id"] = request_id
    return h


def _announcement_body(title="PTA Meeting", audience_type="ALL"):
    body = {
        "title": title,
        "body": "Please take note of the following important information.",
        "audience": {"type": audience_type},
        "channels": ["IN_APP"],
    }
    if audience_type == "CLASS":
        body["audience"]["class_id"] = str(CLASS_A)
    return body


@pytest.fixture
def client(db):
    from app.main import app
    from app.database import get_db

    def _override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════
#   IDEMPOTENCY TESTS
# ═══════════════════════════════════════════


class TestAnnouncementIdempotency:
    """Tests for X-Request-Id based idempotency on announcements endpoint."""

    def test_first_request_creates_announcement(self, client, db):
        """First request with X-Request-Id should create the announcement."""
        request_id = str(uuid.uuid4())
        resp = client.post(
            "/api/v1/comm/announcements",
            json=_announcement_body("First Notice"),
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data.get("already_processed") is None or data.get("already_processed") is not True
        assert data["announcement"]["title"] == "First Notice"

    def test_duplicate_request_returns_already_processed(self, client, db):
        """Sending same X-Request-Id twice should return already_processed on second call."""
        request_id = str(uuid.uuid4())
        body = _announcement_body("Duplicate Test")

        resp1 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["already_processed"] is True

    def test_different_request_ids_create_separate_announcements(self, client, db):
        """Different X-Request-Id values should create separate announcements."""
        body = _announcement_body("Multiple Notices")

        resp1 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=str(uuid.uuid4())),
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=str(uuid.uuid4())),
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"].get("already_processed") is not True

    def test_no_request_id_skips_idempotency(self, client, db):
        """Without X-Request-Id header, every request creates a new announcement."""
        body = _announcement_body("No Idempotency")

        resp1 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(),
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(),
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"].get("already_processed") is not True

    def test_idempotency_key_stored_in_db(self, client, db):
        """After first request, the idempotency key should exist in the database."""
        request_id = str(uuid.uuid4())
        client.post(
            "/api/v1/comm/announcements",
            json=_announcement_body(),
            headers=_teacher_headers(request_id=request_id),
        )

        from eduzim_shared.idempotency import DbIdempotencyStore
        store = DbIdempotencyStore(db, IdempotencyKey)
        assert store.is_duplicate(f"announcement:{request_id}") is True

    def test_triple_replay_safe(self, client, db):
        """3x same X-Request-Id should all be safe (first creates, rest return cached)."""
        request_id = str(uuid.uuid4())
        body = _announcement_body("Triple Test")
        headers = _teacher_headers(request_id=request_id)

        resp1 = client.post("/api/v1/comm/announcements", json=body, headers=headers)
        resp2 = client.post("/api/v1/comm/announcements", json=body, headers=headers)
        resp3 = client.post("/api/v1/comm/announcements", json=body, headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200

        assert resp2.json()["data"]["already_processed"] is True
        assert resp3.json()["data"]["already_processed"] is True

    def test_cached_response_preserves_announcement_data(self, client, db):
        """The cached response should preserve the original announcement data."""
        request_id = str(uuid.uuid4())
        body = _announcement_body("Cache Check")

        resp1 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=request_id),
        )
        original_title = resp1.json()["data"]["announcement"]["title"]

        resp2 = client.post(
            "/api/v1/comm/announcements",
            json=body,
            headers=_teacher_headers(request_id=request_id),
        )
        cached_title = resp2.json()["data"]["announcement"]["title"]
        assert cached_title == original_title
