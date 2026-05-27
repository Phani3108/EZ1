"""
Diagnostics probe tests for communication-service.

We focus on the parts the admin needs to trust:
  • Roll-up logic (down > degraded > not_configured > ok)
  • Outbox lag check observes real rows
  • SMS / Email / Push / WhatsApp config checks distinguish
    'configured' vs 'not configured' without secrets leaking.

Network calls are not exercised — that's reachability checks and they
already short-circuit when keys are missing.
"""
import os
import uuid

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_comm_diag.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.database as db_mod
from app.models.communication import NotificationOutbox  # noqa: register


engine = create_engine(
    "sqlite:///./test_comm_diag.db",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, _rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    # Point diagnostics' SessionLocal at our test engine.
    monkeypatch.setattr(db_mod, "SessionLocal", TestSession)
    import app.api.diagnostics as diag_mod
    monkeypatch.setattr(diag_mod, "SessionLocal", TestSession)

    Base.metadata.create_all(bind=engine)
    yield
    from sqlalchemy.orm import close_all_sessions
    close_all_sessions()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        path = f"./test_comm_diag.db{suffix}"
        try:
            os.remove(path)
        except OSError:
            pass


# ─── Roll-up ───

def test_rollup_down_beats_everything():
    from app.api.diagnostics import _roll_up
    status, _ = _roll_up([
        {"status": "ok"}, {"status": "degraded"},
        {"status": "down"}, {"status": "not_configured"},
    ])
    assert status == "down"


def test_rollup_degraded_beats_not_configured():
    from app.api.diagnostics import _roll_up
    status, _ = _roll_up([
        {"status": "ok"}, {"status": "degraded"},
        {"status": "not_configured"},
    ])
    assert status == "degraded"


def test_rollup_ok_with_some_not_configured():
    from app.api.diagnostics import _roll_up
    status, msg = _roll_up([
        {"status": "ok"}, {"status": "ok"},
        {"status": "not_configured"},
    ])
    assert status == "ok"
    assert "not configured" in msg.lower()


def test_rollup_all_not_configured():
    from app.api.diagnostics import _roll_up
    status, _ = _roll_up([
        {"status": "not_configured"}, {"status": "not_configured"},
    ])
    assert status == "not_configured"


# ─── DB check ───

def test_db_check_passes_against_test_engine():
    from app.api.diagnostics import _check_db
    result = _check_db()
    assert result["id"] == "database"
    assert result["status"] == "ok"
    assert "Connected" in result["detail"]


# ─── Outbox lag check ───

def test_outbox_lag_empty_outbox_is_ok():
    from app.api.diagnostics import _check_outbox_lag
    result = _check_outbox_lag()
    assert result["status"] == "ok"
    assert result["pending_count"] == 0
    assert result["failed_last_24h"] == 0


def test_outbox_lag_with_pending_rows_reports_count():
    from app.api.diagnostics import _check_outbox_lag
    school_id = uuid.uuid4()
    ann_id = uuid.uuid4()
    # Need an announcement row first since FK references it.
    from app.models.communication import Announcement
    db = TestSession()
    try:
        db.add(Announcement(
            id=ann_id, school_id=school_id, title="T", body="B",
            audience_type="ALL", created_by=uuid.uuid4(),
        ))
        for _ in range(3):
            db.add(NotificationOutbox(
                id=uuid.uuid4(), school_id=school_id,
                announcement_id=ann_id, user_id=uuid.uuid4(),
                channel="SMS", status="PENDING",
            ))
        db.add(NotificationOutbox(
            id=uuid.uuid4(), school_id=school_id,
            announcement_id=ann_id, user_id=uuid.uuid4(),
            channel="SMS", status="FAILED",
        ))
        db.commit()
    finally:
        db.close()

    result = _check_outbox_lag()
    assert result["pending_count"] == 3
    assert result["failed_last_24h"] == 1


# ─── Provider config checks ───

def test_sms_config_not_set_returns_not_configured(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "AFRICASTALKING_API_KEY", "")
    result = diag._check_sms_config()
    assert result["status"] == "not_configured"
    assert "AFRICASTALKING_API_KEY" in result["missing"]


def test_sms_config_set_returns_ok_without_leaking_key(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "AFRICASTALKING_API_KEY", "atsk_supersecret_dont_leak")
    monkeypatch.setattr(diag.settings, "AFRICASTALKING_USERNAME", "eduzim_prod")
    result = diag._check_sms_config()
    assert result["status"] == "ok"
    assert "atsk_supersecret_dont_leak" not in str(result)


def test_email_config_not_set(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "SMTP_HOST", "")
    result = diag._check_email_config()
    assert result["status"] == "not_configured"


def test_email_config_set(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(diag.settings, "SMTP_PORT", 587)
    result = diag._check_email_config()
    assert result["status"] == "ok"
    assert result["smtp_host"] == "smtp.example.com"


def test_push_config_not_set(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "FCM_SERVER_KEY", "")
    result = diag._check_push_config()
    assert result["status"] == "not_configured"


def test_push_config_set_returns_only_preview(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "FCM_SERVER_KEY", "AAAA_secret_should_not_appear")
    result = diag._check_push_config()
    assert result["status"] == "ok"
    assert "secret_should_not_appear" not in str(result)
    assert "key_preview" in result


def test_whatsapp_config_missing_token(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "WHATSAPP_ACCESS_TOKEN", "")
    monkeypatch.setattr(diag.settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    result = diag._check_whatsapp_config()
    assert result["status"] == "not_configured"
    assert "WHATSAPP_ACCESS_TOKEN" in result["missing"]


def test_whatsapp_config_set(monkeypatch):
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "WHATSAPP_ACCESS_TOKEN", "EAAGmysecrettoken")
    monkeypatch.setattr(diag.settings, "WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    result = diag._check_whatsapp_config()
    assert result["status"] == "ok"
    assert "EAAGmysecrettoken" not in str(result)


def test_paynow_hash_check_skipped_concept_applies_here(monkeypatch):
    """Sanity: when keys missing, reachability checks short-circuit not_configured."""
    import asyncio
    from app.api import diagnostics as diag
    monkeypatch.setattr(diag.settings, "AFRICASTALKING_API_KEY", "")
    monkeypatch.setattr(diag.settings, "FCM_SERVER_KEY", "")
    monkeypatch.setattr(diag.settings, "WHATSAPP_ACCESS_TOKEN", "")
    monkeypatch.setattr(diag.settings, "WHATSAPP_PHONE_NUMBER_ID", "")

    assert asyncio.run(diag._check_sms_reachable())["status"] == "not_configured"
    assert asyncio.run(diag._check_push_reachable())["status"] == "not_configured"
    assert asyncio.run(diag._check_whatsapp_reachable())["status"] == "not_configured"
