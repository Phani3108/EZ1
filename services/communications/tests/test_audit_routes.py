"""Integration tests for communications audit-log endpoint + write-side wiring.

Same shape as the academics + finance audit tests. Focused on the two
wire points: announcement create + announcement delete.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_audit.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import communication as _c  # noqa
    from app.models import idempotency as _i  # noqa
    from app.models import whatsapp as _w  # noqa
    from app.models import audit as _au  # noqa

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


def _admin_headers(school_id, user_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id or uuid.uuid4()),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage,comm:write",
    }


class TestList:

    def test_school_isolation(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        from app.models.audit import AuditLog
        from datetime import datetime, timezone
        s = SessionLocal()
        try:
            for _ in range(2):
                s.add(AuditLog(
                    id=uuid.uuid4(),
                    occurred_at=datetime.now(timezone.utc),
                    school_id=SCHOOL_A,
                    event_type="announcement.created",
                ))
            for _ in range(3):
                s.add(AuditLog(
                    id=uuid.uuid4(),
                    occurred_at=datetime.now(timezone.utc),
                    school_id=SCHOOL_B,
                    event_type="announcement.created",
                ))
            s.commit()
        finally:
            s.close()

        r_a = client.get("/api/v1/comm/audit-log", headers=_admin_headers(SCHOOL_A))
        r_b = client.get("/api/v1/comm/audit-log", headers=_admin_headers(SCHOOL_B))
        assert r_a.json()["meta"]["total"] == 2
        assert r_b.json()["meta"]["total"] == 3


class TestWriteSideWiring:

    def test_announcement_create_audited(self, client):
        r = client.post(
            "/api/v1/comm/announcements",
            headers=_admin_headers(SCHOOL_A),
            json={
                "title": "PTA Meeting",
                "body": "Please attend the PTA meeting on Friday at 14:00.",
                "audience": {"type": "ALL"},
                "channels": ["IN_APP"],
            },
        )
        assert r.status_code == 200, r.text
        ann_id = r.json()["data"]["announcement"]["id"]

        audit_r = client.get(
            "/api/v1/comm/audit-log?event_type=announcement.created",
            headers=_admin_headers(SCHOOL_A),
        )
        rows = audit_r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["target"]["id"] == ann_id
        # Title is in details (admin-controlled, short)
        assert rows[0]["details"]["title"] == "PTA Meeting"
        # BODY must NOT be in the audit (free-text, could contain PII)
        assert "Please attend" not in json.dumps(rows[0]["details"])
        assert "body" not in rows[0]["details"]
