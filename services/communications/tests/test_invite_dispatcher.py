"""Phase 15a — InviteDispatcher tests."""
from __future__ import annotations

import json as _json
import os
import uuid

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_invites.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import (  # noqa
        communication, audit, messaging, attachment,
        notification_config, invite_outbox, whatsapp,
    )

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


def _admin_headers(school_id=None):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(school_id or SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,invite:write,comm:write,comm:read",
    }


def _seed_provider(SessionLocal, school_id, channel, provider_name):
    from app.models.notification_config import SchoolNotificationConfig
    s = SessionLocal()
    try:
        s.add(SchoolNotificationConfig(
            id=uuid.uuid4(), school_id=school_id, channel=channel,
            provider_name=provider_name, updated_by_user_id=uuid.uuid4(),
        ))
        s.commit()
    finally:
        s.close()


def _dispatch_body(*, invitation_id=None, role="Parent",
                   contact_email=None, contact_phone="+263770000001"):
    return {
        "invitation_id": invitation_id or str(uuid.uuid4()),
        "school_name": "Harare Central",
        "role": role,
        "full_name": "Tendai Mukoma",
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "manual_code": "847301",
        "invite_url": "https://eduzim.zw/invite/abc123",
    }


class TestChannelPriority:
    def test_picks_sms_when_phone_and_sms_provider_present(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "sms", "africastalking")
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(contact_phone="+263770111222"),
        )
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["channel"] == "sms"
        assert d["provider_name"] == "africastalking"
        assert d["status"] == "queued"

    def test_falls_back_to_whatsapp_when_no_sms(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "whatsapp", "meta_cloud")
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(contact_phone="+263770111222"),
        )
        d = r.json()["data"]
        assert d["channel"] == "whatsapp"
        assert d["provider_name"] == "meta_cloud"

    def test_falls_back_to_email_when_no_sms_or_whatsapp(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "email", "sendgrid")
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(contact_phone=None,
                                contact_email="test@example.com"),
        )
        d = r.json()["data"]
        assert d["channel"] == "email"
        assert d["provider_name"] == "sendgrid"

    def test_manual_fallback_when_no_provider(self, client, engine_and_session):
        # No provider configured at all.
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(contact_phone="+263770ABC"),
        )
        d = r.json()["data"]
        assert d["channel"] == "manual"
        assert d["status"] == "manual_pending"
        assert d["provider_name"] is None

    def test_manual_fallback_when_contact_doesnt_match_channel(self, client, engine_and_session):
        """Configure SMS but provide only email. SMS skipped → email
        skipped (no provider) → manual."""
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "sms", "africastalking")
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(contact_phone=None,
                                contact_email="only-email@example.com"),
        )
        d = r.json()["data"]
        assert d["channel"] == "manual"


class TestBodyRendering:
    def test_sms_body_under_160_chars(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "sms", "africastalking")
        client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(role="Parent"),
        )
        l = client.get("/api/v1/comm/invite-outbox", headers=_admin_headers())
        rows = l.json()["data"]
        assert len(rows) == 1
        assert len(rows[0]["body"]) <= 160
        assert "EduZim" in rows[0]["body"]
        assert "847301" in rows[0]["body"]

    def test_email_subject_present(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "email", "sendgrid")
        client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(role="Teacher", contact_phone=None,
                                contact_email="t@example.com"),
        )
        l = client.get("/api/v1/comm/invite-outbox", headers=_admin_headers())
        row = l.json()["data"][0]
        assert row["subject"]
        assert "EduZim" in row["subject"] or "EduZim" in row["body"]
        assert "Harare Central" in row["body"]


class TestOutboxLifecycle:
    def test_mark_sent_then_resend(self, client, engine_and_session):
        _, SL = engine_and_session
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(),
        )
        outbox_id = r.json()["data"]["invite_outbox_id"]
        # Mark sent.
        ms = client.post(
            f"/api/v1/comm/invite-outbox/{outbox_id}/mark-sent",
            headers=_admin_headers(),
        )
        assert ms.json()["data"]["status"] == "sent"
        # Resend should reject — already sent.
        rs = client.post(
            f"/api/v1/comm/invite-outbox/{outbox_id}/resend",
            headers=_admin_headers(),
        )
        assert rs.status_code == 409

    def test_resend_manual_pending(self, client, engine_and_session):
        r = client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json=_dispatch_body(),  # manual fallback
        )
        outbox_id = r.json()["data"]["invite_outbox_id"]
        rs = client.post(
            f"/api/v1/comm/invite-outbox/{outbox_id}/resend",
            headers=_admin_headers(),
        )
        d = rs.json()["data"]
        assert d["status"] == "manual_pending"
        assert d["retry_count"] == 1


class TestTenantIsolation:
    def test_outbox_filtered_by_school(self, client, engine_and_session):
        client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(school_id=SCHOOL_A),
            json=_dispatch_body(),
        )
        client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(school_id=SCHOOL_B),
            json=_dispatch_body(),
        )
        l_a = client.get("/api/v1/comm/invite-outbox",
                         headers=_admin_headers(school_id=SCHOOL_A))
        l_b = client.get("/api/v1/comm/invite-outbox",
                         headers=_admin_headers(school_id=SCHOOL_B))
        assert len(l_a.json()["data"]) == 1
        assert len(l_b.json()["data"]) == 1


class TestAuditNoPII:
    def test_dispatch_audit_omits_recipient_and_body(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_provider(SL, SCHOOL_A, "sms", "africastalking")
        client.post(
            "/api/v1/comm/invitations/dispatch",
            headers=_admin_headers(),
            json={
                "invitation_id": str(uuid.uuid4()),
                "school_name": "Harare Central",
                "role": "Parent",
                "full_name": "VERYSECRETNAME",
                "contact_email": None,
                "contact_phone": "+26377SECRETPHONE",
                "manual_code": "999999",
                "invite_url": "https://eduzim.zw/invite/xxx",
            },
        )

        from app.models.audit import AuditLog
        s = SL()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type == "invitation.dispatched")
                .all()
            )
            assert len(rows) >= 1
            blob = _json.dumps({"target": rows[0].target,
                                "details": rows[0].details or "{}"})
            assert "VERYSECRETNAME" not in blob
            assert "SECRETPHONE" not in blob
            # The audit DOES record provider + channel — those are
            # not PII.
            assert "africastalking" in blob
            assert "sms" in blob
        finally:
            s.close()
