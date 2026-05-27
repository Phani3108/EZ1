"""Phase 12c — NotificationProvider abstraction tests."""
from __future__ import annotations

import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_notif.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import communication as _c  # noqa
    from app.models import idempotency as _i  # noqa
    from app.models import whatsapp as _w  # noqa
    from app.models import audit as _au  # noqa
    from app.models import messaging as _m  # noqa
    from app.models import attachment as _a  # noqa
    from app.models import notification_config as _nc  # noqa

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


# ─── Registry + Manual providers ──────────────────────────────────


class TestRegistry:
    def test_default_resolution_per_channel(self, engine_and_session):
        _, SessionLocal = engine_and_session
        from app.providers import get_provider_for_school_channel
        s = SessionLocal()
        try:
            for ch, default_name in [
                ("sms", "africastalking"), ("push", "fcm"),
                ("email", "sendgrid"), ("whatsapp", "meta_cloud"),
            ]:
                p = get_provider_for_school_channel(s, SCHOOL_A, ch)
                assert p.name == default_name
                assert p.channel == ch
        finally:
            s.close()

    def test_manual_providers_return_pending(self):
        from app.providers import PROVIDER_REGISTRY
        for ch in ("sms", "push", "email", "whatsapp"):
            p = PROVIDER_REGISTRY[(ch, "manual")]
            r = p.send(recipient="+1234567890",
                       subject="hi", body="test")
            assert r.status == "MANUAL_PENDING"
            assert r.provider_message_id is None


# ─── Config endpoint ─────────────────────────────────────────────


class TestConfig:
    def test_get_returns_defaults_for_all_channels(self, client):
        r = client.get(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        body = r.json()["data"]
        channels = {c["channel"]: c for c in body["channels"]}
        assert set(channels.keys()) == {"sms", "push", "email", "whatsapp"}
        assert all(c["is_default"] is True for c in body["channels"])

    def test_put_switches_one_channel(self, client):
        r = client.put(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
            json={"channel": "sms", "provider_name": "manual"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["provider_name"] == "manual"

        # GET shows manual for sms; defaults for others
        g = client.get(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
        )
        chs = {c["channel"]: c for c in g.json()["data"]["channels"]}
        assert chs["sms"]["provider_name"] == "manual"
        assert chs["push"]["provider_name"] == "fcm"

    def test_unknown_channel_rejected(self, client):
        r = client.put(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
            json={"channel": "carrier-pigeon", "provider_name": "manual"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_CHANNEL"

    def test_unknown_provider_for_channel_rejected(self, client):
        # `fcm` doesn't serve sms — should reject.
        r = client.put(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
            json={"channel": "sms", "provider_name": "fcm"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "UNKNOWN_PROVIDER"


# ─── Dispatch ─────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_via_manual_returns_pending(self, client):
        client.put(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
            json={"channel": "sms", "provider_name": "manual"},
        )
        r = client.post(
            "/api/v1/comm/notify/dispatch",
            headers=_admin_headers(),
            json={"channel": "sms",
                  "recipient": "+263770000000",
                  "body": "Test message"},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["channel"] == "sms"
        assert body["provider"] == "manual"
        assert body["status"] == "MANUAL_PENDING"

    def test_dispatch_default_provider_surfaces_provider_error(self, client):
        # No keys configured → real provider raises → 502.
        r = client.post(
            "/api/v1/comm/notify/dispatch",
            headers=_admin_headers(),
            json={"channel": "sms",
                  "recipient": "+1",
                  "body": "Hi"},
        )
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "PROVIDER_ERROR"

    def test_dispatch_audit_does_not_log_recipient_or_body(
        self, client, engine_and_session,
    ):
        _, SessionLocal = engine_and_session
        client.put(
            "/api/v1/comm/notification-config",
            headers=_admin_headers(),
            json={"channel": "sms", "provider_name": "manual"},
        )
        client.post(
            "/api/v1/comm/notify/dispatch",
            headers=_admin_headers(),
            json={"channel": "sms",
                  "recipient": "+263770SENSITIVE",
                  "body": "TOP SECRET BODY"},
        )
        from app.models.audit import AuditLog
        import json as _json
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "notification.dispatched")
                .all()
            )
            assert len(rows) == 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details})
            assert "TOP SECRET BODY" not in blob
            assert "263770SENSITIVE" not in blob
        finally:
            s.close()
