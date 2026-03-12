"""
Assessment Service Idempotency Tests — Quality Gate 10B-4
==========================================================
Tests for X-Request-Id based idempotency on the bulk marks endpoint.
Verifies that duplicate sync requests from offline-capable clients
are safely de-duplicated.
"""
import os
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_assessment_idempotency.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.assessment import Assessment, Mark  # noqa: register models
from app.models.idempotency import IdempotencyKey  # noqa: register model

engine = create_engine(
    "sqlite:///./test_assessment_idempotency.db",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    TestSession.close_all()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_assessment_idempotency.db"):
        try:
            os.remove("./test_assessment_idempotency.db")
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
STUDENT_1 = uuid.uuid4()
STUDENT_2 = uuid.uuid4()
STUDENT_3 = uuid.uuid4()
YEAR_A = uuid.uuid4()
TERM_A = uuid.uuid4()
CLASS_A = uuid.uuid4()
SUBJECT_MATH = uuid.uuid4()


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


def _teacher_headers(user_id=None, school_id=None, request_id=None):
    h = {"Authorization": f"Bearer {_make_token(user_id, school_id, ['Teacher'])}"}
    if request_id:
        h["X-Request-Id"] = request_id
    return h


def _admin_headers(user_id=None, school_id=None, request_id=None):
    h = {"Authorization": f"Bearer {_make_token(user_id, school_id, ['Admin'])}"}
    if request_id:
        h["X-Request-Id"] = request_id
    return h


def _create_assessment(db, name="Mid-term Math", school_id=None):
    from app.services.assessment_service import AssessmentService
    svc = AssessmentService(db)
    return svc.create_assessment(
        school_id=school_id or SCHOOL_A,
        academic_year_id=YEAR_A,
        term_id=TERM_A,
        class_id=CLASS_A,
        subject_id=SUBJECT_MATH,
        name=name,
        assessment_type="TEST",
        date=date(2026, 3, 15),
        max_marks=Decimal("100"),
        created_by=TEACHER_1,
    )


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


class TestBulkMarksIdempotency:
    """Tests for X-Request-Id based idempotency on bulk marks endpoint."""

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_first_request_processes_normally(self, mock_auth, client, db):
        """First request with X-Request-Id should process marks normally."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]
        request_id = str(uuid.uuid4())

        resp = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json={"marks": [
                {"student_id": str(STUDENT_1), "marks": 85, "is_absent": False, "remarks": "Good"},
                {"student_id": str(STUDENT_2), "marks": 72, "is_absent": False, "remarks": "Fair"},
            ]},
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data.get("already_processed") is None or data.get("already_processed") is not True
        assert data["accepted"] == 2

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_duplicate_request_returns_already_processed(self, mock_auth, client, db):
        """Sending the same X-Request-Id twice should return already_processed=True."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]
        request_id = str(uuid.uuid4())

        marks_body = {"marks": [
            {"student_id": str(STUDENT_1), "marks": 90, "is_absent": False, "remarks": "Excellent"},
        ]}

        # First request — should succeed
        resp1 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp1.status_code == 200
        assert resp1.json()["data"]["accepted"] == 1

        # Second request — same X-Request-Id → already_processed
        resp2 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["already_processed"] is True

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_different_request_ids_process_independently(self, mock_auth, client, db):
        """Different X-Request-Id values should be treated as separate requests."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]

        marks_body = {"marks": [
            {"student_id": str(STUDENT_1), "marks": 80, "is_absent": False},
        ]}

        resp1 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(request_id=str(uuid.uuid4())),
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(request_id=str(uuid.uuid4())),
        )
        assert resp2.status_code == 200
        # Both processed (same marks → upsert, but different idempotency keys)
        assert resp2.json()["data"].get("already_processed") is not True

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_no_request_id_skips_idempotency(self, mock_auth, client, db):
        """Without X-Request-Id header, idempotency check is skipped."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]

        marks_body = {"marks": [
            {"student_id": str(STUDENT_1), "marks": 75, "is_absent": False},
        ]}

        # First request without X-Request-Id
        resp1 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(),
        )
        assert resp1.status_code == 200

        # Second request without X-Request-Id — processes normally (no dedup)
        resp2 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json=marks_body,
            headers=_teacher_headers(),
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"].get("already_processed") is not True

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_idempotency_key_persisted_in_db(self, mock_auth, client, db):
        """After first request, idempotency key should be stored in the database."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]
        request_id = str(uuid.uuid4())

        client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json={"marks": [{"student_id": str(STUDENT_1), "marks": 70, "is_absent": False}]},
            headers=_teacher_headers(request_id=request_id),
        )

        # Check DB directly
        from eduzim_shared.idempotency import DbIdempotencyStore
        store = DbIdempotencyStore(db, IdempotencyKey)
        assert store.is_duplicate(f"marks-bulk:{request_id}") is True

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_cached_response_matches_original(self, mock_auth, client, db):
        """The cached response from idempotency replay should match the original response data."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]
        request_id = str(uuid.uuid4())

        resp1 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json={"marks": [
                {"student_id": str(STUDENT_1), "marks": 88, "is_absent": False},
                {"student_id": str(STUDENT_2), "marks": 65, "is_absent": False},
            ]},
            headers=_teacher_headers(request_id=request_id),
        )
        assert resp1.status_code == 200
        original_accepted = resp1.json()["data"]["accepted"]

        # Replay
        resp2 = client.post(
            f"/api/v1/assessments/{assessment_id}/marks/bulk",
            json={"marks": [
                {"student_id": str(STUDENT_1), "marks": 88, "is_absent": False},
                {"student_id": str(STUDENT_2), "marks": 65, "is_absent": False},
            ]},
            headers=_teacher_headers(request_id=request_id),
        )
        data2 = resp2.json()["data"]
        assert data2["already_processed"] is True
        assert data2["accepted"] == original_accepted

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_triple_replay_still_idempotent(self, mock_auth, client, db):
        """Sending 3x with same X-Request-Id should all be safe."""
        mock_auth.return_value = True
        assessment = _create_assessment(db)
        assessment_id = assessment["id"]
        request_id = str(uuid.uuid4())
        marks_body = {"marks": [{"student_id": str(STUDENT_1), "marks": 50, "is_absent": False}]}
        headers = _teacher_headers(request_id=request_id)

        resp1 = client.post(f"/api/v1/assessments/{assessment_id}/marks/bulk", json=marks_body, headers=headers)
        resp2 = client.post(f"/api/v1/assessments/{assessment_id}/marks/bulk", json=marks_body, headers=headers)
        resp3 = client.post(f"/api/v1/assessments/{assessment_id}/marks/bulk", json=marks_body, headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200

        # Only first should process, 2nd and 3rd are idempotent
        assert resp2.json()["data"]["already_processed"] is True
        assert resp3.json()["data"]["already_processed"] is True
