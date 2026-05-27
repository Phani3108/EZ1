"""Comment bank tests (Phase 11c / T-007)."""
from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_commentbank.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()
TEACHER_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa
    from app.models import audit as _au  # noqa
    from app.models import comment_bank as _cb  # noqa

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


def _admin_headers(user_id=ADMIN_A, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage",
    }


def _teacher_headers(user_id=TEACHER_A, school_id=SCHOOL_A):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Teacher",
        "X-Permissions": "authenticated",
    }


class TestCommentBankCRUD:
    def test_create_then_list(self, client):
        r = client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(),
            json={"category": "praise", "text": "Excellent work!", "sort_order": 5},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["text"] == "Excellent work!"

        l = client.get(
            "/api/v1/comment-bank",
            headers=_teacher_headers(),
        )
        assert l.status_code == 200
        rows = l.json()["data"]
        assert len(rows) == 1
        assert rows[0]["category"] == "praise"

    def test_update_changes_text(self, client):
        cr = client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(),
            json={"text": "Good", "category": "praise"},
        )
        pid = cr.json()["data"]["id"]
        u = client.put(
            f"/api/v1/comment-bank/{pid}",
            headers=_admin_headers(),
            json={"text": "Great"},
        )
        assert u.status_code == 200
        assert u.json()["data"]["text"] == "Great"

    def test_archive_hides_from_default_list(self, client):
        cr = client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(),
            json={"text": "Improve", "category": "improvement"},
        )
        pid = cr.json()["data"]["id"]
        d = client.delete(
            f"/api/v1/comment-bank/{pid}",
            headers=_admin_headers(),
        )
        assert d.status_code == 200
        assert d.json()["data"]["archived_at"] is not None

        # Default list excludes archived
        l = client.get("/api/v1/comment-bank", headers=_teacher_headers())
        assert l.json()["data"] == []
        # include_archived shows it
        la = client.get(
            "/api/v1/comment-bank?include_archived=true",
            headers=_teacher_headers(),
        )
        assert len(la.json()["data"]) == 1

    def test_invalid_category_rejected(self, client):
        r = client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(),
            json={"text": "x", "category": "evil"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_CATEGORY"

    def test_cross_tenant_isolation(self, client):
        client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(school_id=SCHOOL_A),
            json={"text": "A phrase"},
        )
        client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(user_id=uuid.uuid4(), school_id=SCHOOL_B),
            json={"text": "B phrase"},
        )

        a_rows = client.get(
            "/api/v1/comment-bank",
            headers=_admin_headers(school_id=SCHOOL_A),
        ).json()["data"]
        b_rows = client.get(
            "/api/v1/comment-bank",
            headers=_admin_headers(user_id=uuid.uuid4(), school_id=SCHOOL_B),
        ).json()["data"]
        assert len(a_rows) == 1 and a_rows[0]["text"] == "A phrase"
        assert len(b_rows) == 1 and b_rows[0]["text"] == "B phrase"


class TestCommentBankAudit:
    def test_create_writes_audit_without_phrase_text(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.post(
            "/api/v1/comment-bank",
            headers=_admin_headers(),
            json={"text": "TOP-SECRET phrase ABC123", "category": "praise"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "comment_bank.phrase.created")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOP-SECRET phrase ABC123" not in blob
        finally:
            s.close()
