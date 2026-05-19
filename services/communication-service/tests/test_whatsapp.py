"""
WhatsApp provider + webhook tests.

Covers:
  * `MetaWhatsAppProvider.send_text` against a mocked Meta endpoint (success,
    network error, 4xx body parsing).
  * Outbox delivery using the WhatsApp channel creates a `WhatsAppMessage`
    and propagates the wamid.
  * Webhook GET verification handshake (token match + mismatch).
  * Webhook POST delivery callback flips outbox to SENT/FAILED and is
    idempotent on repeat callbacks with the same status.
"""
import os
import uuid

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_whatsapp.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "verify-me")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database as app_db
from app.database import Base
from app.main import app
from app.config import get_settings
from app.api import whatsapp_webhook as wh_module
from app.models.communication import Announcement, NotificationOutbox
from app.models.whatsapp import WhatsAppMessage
from app.services.communication_service import CommunicationService
from app.services.whatsapp_provider import (
    MetaWhatsAppProvider,
    MockWhatsAppProvider,
    classify_status,
)

# Force the verify token onto the cached settings instance regardless of when
# `app.config` was first imported by sibling test modules.
get_settings().WHATSAPP_VERIFY_TOKEN = "verify-me"
wh_module.settings = get_settings()

DB_URL = "sqlite:///./test_whatsapp.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def _setup_db(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(app_db, "SessionLocal", TestSession)
    monkeypatch.setattr(app_db, "engine", engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    return TestClient(app)


# ─────────────────── classify_status ───────────────────

class TestClassifyStatus:
    @pytest.mark.parametrize(
        "raw,expected",
        [("sent", "SENT"), ("delivered", "SENT"), ("read", "SENT"),
         ("failed", "FAILED"), ("undelivered", "FAILED"),
         ("queued", "PENDING"), ("", "PENDING"), (None, "PENDING")],
    )
    def test_classify(self, raw, expected):
        assert classify_status(raw) == expected


# ─────────────────── MetaWhatsAppProvider ─────────────────

def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "messaging_product": "whatsapp",
        "messages": [{"id": "wamid.HBgL263777"}],
        "contacts": [{"wa_id": "263777111222"}],
    })


def _err_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={
        "error": {"code": 131056, "message": "Recipient not on WhatsApp"}
    })


def _network_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("simulated", request=request)


class TestMetaWhatsAppProvider:
    def test_configured_flag(self):
        p = MetaWhatsAppProvider(phone_number_id="123", access_token="tok",
                                  transport=httpx.MockTransport(_ok_handler))
        assert p.configured is True

    def test_not_configured(self):
        p = MetaWhatsAppProvider(phone_number_id="", access_token="")
        assert p.configured is False

    def test_send_text_success(self):
        p = MetaWhatsAppProvider(phone_number_id="123", access_token="tok",
                                  transport=httpx.MockTransport(_ok_handler))
        ok, payload = p.send_text("263777111222", "Hello")
        assert ok is True
        assert payload["messages"][0]["id"].startswith("wamid")

    def test_send_text_api_error(self):
        p = MetaWhatsAppProvider(phone_number_id="123", access_token="tok",
                                  transport=httpx.MockTransport(_err_handler))
        ok, payload = p.send_text("263777111222", "Hello")
        assert ok is False
        assert payload["error"]["code"] == 131056

    def test_send_text_network_error(self):
        p = MetaWhatsAppProvider(phone_number_id="123", access_token="tok",
                                  transport=httpx.MockTransport(_network_handler))
        ok, payload = p.send_text("263777111222", "Hello")
        assert ok is False
        assert "network" in payload["error"]["message"]

    def test_send_template_payload_shape(self):
        captured = {}

        def handler(req: httpx.Request) -> httpx.Response:
            import json
            captured["body"] = json.loads(req.content.decode())
            return _ok_handler(req)

        p = MetaWhatsAppProvider(phone_number_id="123", access_token="tok",
                                  transport=httpx.MockTransport(handler))
        ok, _ = p.send_template("263777111222", "fees_due",
                                language="en",
                                components=[{"type": "body",
                                             "parameters": [{"type": "text", "text": "$50"}]}])
        assert ok is True
        body = captured["body"]
        assert body["type"] == "template"
        assert body["template"]["name"] == "fees_due"
        assert body["template"]["language"]["code"] == "en"
        assert body["template"]["components"][0]["parameters"][0]["text"] == "$50"


# ─────────────────── Delivery engine ─────────────────

def _make_announcement(db, school_id: uuid.UUID) -> Announcement:
    ann = Announcement(
        school_id=school_id, title="Term Starts Monday",
        body="School resumes 09:00.", audience_type="ALL",
        created_by=uuid.uuid4(),
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


class TestWhatsAppDelivery:
    def test_outbox_send_creates_whatsapp_row(self, db):
        school_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ann = _make_announcement(db, school_id)

        outbox = NotificationOutbox(
            school_id=school_id, announcement_id=ann.id,
            user_id=user_id, channel="WHATSAPP", status="PENDING",
        )
        db.add(outbox)
        db.commit()

        provider = MockWhatsAppProvider()
        svc = CommunicationService(
            db,
            whatsapp_provider=provider,
            user_phone_resolver=lambda _uid: "263777111222",
        )
        result = svc.process_pending(school_id=school_id)
        assert result["sent"] == 1
        assert provider.sent[0]["phone"] == "263777111222"

        wa = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.school_id == school_id,
        ).one()
        assert wa.provider_message_id is not None
        assert wa.provider_message_id.startswith("wamid")

    def test_outbox_send_missing_phone_marks_failed(self, db):
        school_id = uuid.uuid4()
        ann = _make_announcement(db, school_id)
        outbox = NotificationOutbox(
            school_id=school_id, announcement_id=ann.id,
            user_id=uuid.uuid4(), channel="WHATSAPP", status="PENDING",
        )
        db.add(outbox)
        db.commit()

        svc = CommunicationService(
            db,
            whatsapp_provider=MockWhatsAppProvider(),
            user_phone_resolver=lambda _uid: None,
            max_retries=1,
        )
        svc.process_pending(school_id=school_id)

        outbox_after = db.query(NotificationOutbox).filter(
            NotificationOutbox.id == outbox.id,
        ).one()
        assert outbox_after.status == "FAILED"
        # error_message is overwritten with "Max retries" once max is hit,
        # so we only assert the terminal state here.


# ─────────────────── Webhook routes ─────────────────

class TestWhatsAppVerification:
    def test_verify_token_match(self, client):
        r = client.get(
            "/api/v1/comm/webhooks/whatsapp",
            params={"hub.mode": "subscribe",
                    "hub.verify_token": "verify-me",
                    "hub.challenge": "12345"},
        )
        assert r.status_code == 200
        assert r.text == "12345"

    def test_verify_token_mismatch(self, client):
        r = client.get(
            "/api/v1/comm/webhooks/whatsapp",
            params={"hub.mode": "subscribe",
                    "hub.verify_token": "wrong",
                    "hub.challenge": "12345"},
        )
        assert r.status_code == 403


class TestWhatsAppCallback:
    def _seed_message(self, db, wamid: str = "wamid.TEST.ABC123"):
        school_id = uuid.uuid4()
        ann = _make_announcement(db, school_id)
        outbox = NotificationOutbox(
            school_id=school_id, announcement_id=ann.id,
            user_id=uuid.uuid4(), channel="WHATSAPP", status="PENDING",
        )
        db.add(outbox)
        db.flush()
        wa = WhatsAppMessage(
            school_id=school_id, outbox_id=outbox.id,
            to_phone="263777111222", provider_message_id=wamid,
            body_preview="Hello",
        )
        db.add(wa)
        db.commit()
        return outbox, wa

    def _callback(self, wamid: str, status: str = "delivered") -> dict:
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": wamid,
                            "status": status,
                            "recipient_id": "263777111222",
                        }],
                    },
                }],
            }],
        }

    def test_delivered_callback_marks_outbox_sent(self, client, db):
        outbox, wa = self._seed_message(db)
        r = client.post("/api/v1/comm/webhooks/whatsapp",
                        json=self._callback(wa.provider_message_id, "delivered"))
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["statuses_processed"] == 1

        db.expire_all()
        outbox_after = db.query(NotificationOutbox).filter(
            NotificationOutbox.id == outbox.id,
        ).one()
        assert outbox_after.status == "SENT"

    def test_failed_callback_marks_outbox_failed(self, client, db):
        outbox, wa = self._seed_message(db, "wamid.FAIL.ZZZ")
        payload = self._callback(wa.provider_message_id, "failed")
        payload["entry"][0]["changes"][0]["value"]["statuses"][0]["errors"] = [
            {"code": 131056, "title": "Recipient not on WhatsApp"},
        ]
        r = client.post("/api/v1/comm/webhooks/whatsapp", json=payload)
        assert r.status_code == 200

        db.expire_all()
        outbox_after = db.query(NotificationOutbox).filter(
            NotificationOutbox.id == outbox.id,
        ).one()
        assert outbox_after.status == "FAILED"
        assert "Recipient not on WhatsApp" in (outbox_after.error_message or "")

    def test_duplicate_callback_is_idempotent(self, client, db):
        outbox, wa = self._seed_message(db, "wamid.DUP.123")
        payload = self._callback(wa.provider_message_id, "delivered")

        r1 = client.post("/api/v1/comm/webhooks/whatsapp", json=payload)
        r2 = client.post("/api/v1/comm/webhooks/whatsapp", json=payload)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["data"]["statuses_processed"] == 1
        assert r2.json()["data"]["duplicates_skipped"] == 1

    def test_unknown_wamid_is_acked(self, client):
        r = client.post(
            "/api/v1/comm/webhooks/whatsapp",
            json=self._callback("wamid.NEVERSEEN", "delivered"),
        )
        assert r.status_code == 200
        assert r.json()["data"]["statuses_processed"] == 0

    def test_invalid_payload_returns_400(self, client):
        r = client.post(
            "/api/v1/comm/webhooks/whatsapp",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 400
