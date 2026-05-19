"""
Deep diagnostics probe for communication-service
=================================================
Called by the api-gateway diagnostics router via:
  POST /internal/diagnostics/probe

Channels we check:
  • Database connectivity
  • Outbox lag (oldest PENDING age + FAILED count in the last 24h)
  • SMS — Africa's Talking config + endpoint reachability
  • Email — SMTP config + TCP reachability (no actual mail sent)
  • Push — Firebase Cloud Messaging config + endpoint reachability
  • WhatsApp — Meta Cloud API config + endpoint reachability

Everything is read-only/idempotent. No real messages are sent.
"""
from __future__ import annotations

import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal


router = APIRouter(prefix="/internal/diagnostics", tags=["Diagnostics (internal)"])
settings = get_settings()


def _meta(request: Request) -> dict:
    rid = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return {"request_id": rid, "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── Database ───

def _check_db() -> dict:
    started = time.time()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "id": "database",
            "label": "Database connection",
            "status": "ok",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Connected to Postgres and ran a test query.",
        }
    except Exception as e:
        return {
            "id": "database",
            "label": "Database connection",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Couldn't reach the database. Check Postgres is running and credentials are correct.",
            "error": str(e)[:300],
        }


# ─── Outbox lag ───

def _check_outbox_lag() -> dict:
    """
    Look for stuck pending entries and recent failures.

    Signals the admin can act on:
      • oldest PENDING age in minutes  → worker stalled?
      • FAILED count in last 24h       → provider degraded?
    """
    started = time.time()
    try:
        from sqlalchemy import func
        from app.models.communication import NotificationOutbox

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with SessionLocal() as db:
            oldest_pending = (
                db.query(func.min(NotificationOutbox.created_at))
                .filter(NotificationOutbox.status == "PENDING")
                .scalar()
            )
            pending_count = (
                db.query(func.count(NotificationOutbox.id))
                .filter(NotificationOutbox.status == "PENDING")
                .scalar()
                or 0
            )
            failed_24h = (
                db.query(func.count(NotificationOutbox.id))
                .filter(
                    NotificationOutbox.status == "FAILED",
                    NotificationOutbox.created_at > cutoff,
                )
                .scalar()
                or 0
            )

        latency_ms = round((time.time() - started) * 1000, 1)

        if oldest_pending is not None:
            # SQLite returns naive datetimes; treat as UTC.
            if oldest_pending.tzinfo is None:
                oldest_pending = oldest_pending.replace(tzinfo=timezone.utc)
            oldest_min = max(
                0.0,
                (datetime.now(timezone.utc) - oldest_pending).total_seconds() / 60.0,
            )
        else:
            oldest_min = 0.0

        if oldest_min >= settings.OUTBOX_LAG_DOWN_MINUTES:
            status = "down"
            detail = (
                f"The notification worker hasn't sent the oldest pending message in "
                f"{int(oldest_min)} minutes. It may be stopped or crashing."
            )
        elif oldest_min >= settings.OUTBOX_LAG_DEGRADED_MINUTES:
            status = "degraded"
            detail = (
                f"Some messages have been waiting {int(oldest_min)} minutes. "
                "Worker is slow but moving."
            )
        elif pending_count == 0:
            status = "ok"
            detail = "No pending messages — the outbox is fully drained."
        else:
            status = "ok"
            detail = f"{pending_count} pending message(s); oldest is {int(oldest_min)} minute(s) old."

        return {
            "id": "outbox_lag",
            "label": "Outbox delivery lag",
            "status": status,
            "latency_ms": latency_ms,
            "detail": detail,
            "pending_count": int(pending_count),
            "oldest_pending_minutes": round(oldest_min, 1),
            "failed_last_24h": int(failed_24h),
        }
    except Exception as e:
        return {
            "id": "outbox_lag",
            "label": "Outbox delivery lag",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Couldn't read the outbox table. Database may be unhealthy.",
            "error": str(e)[:300],
        }


# ─── Generic reachability helpers ───

async def _http_head(url: str, timeout: float = 4.0) -> tuple[bool, int | None, str | None]:
    """Returns (reachable, status, error). Any HTTP reply counts as reachable."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=2.5),
            follow_redirects=False,
        ) as client:
            resp = await client.head(url)
        return True, resp.status_code, None
    except httpx.ConnectError as e:
        return False, None, f"Cannot connect: {e}"
    except httpx.TimeoutException:
        return False, None, "Timed out."
    except Exception as e:  # pragma: no cover
        return False, None, f"Unexpected error: {e}"


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str | None]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except OSError as e:
        return False, str(e)[:200]


# ─── SMS — Africa's Talking ───

AT_PROBE_URL = "https://api.africastalking.com/version1/messaging"


def _check_sms_config() -> dict:
    if not settings.AFRICASTALKING_API_KEY:
        return {
            "id": "sms_config",
            "label": "SMS provider configured",
            "status": "not_configured",
            "detail": "Africa's Talking API key is not set. SMS messages will not be sent.",
            "missing": ["AFRICASTALKING_API_KEY"],
        }
    return {
        "id": "sms_config",
        "label": "SMS provider configured",
        "status": "ok",
        "detail": f"Africa's Talking is set up as user '{settings.AFRICASTALKING_USERNAME}' "
                  f"with sender ID '{settings.AFRICASTALKING_SENDER}'.",
        "username": settings.AFRICASTALKING_USERNAME,
        "sender": settings.AFRICASTALKING_SENDER,
    }


async def _check_sms_reachable() -> dict:
    if not settings.AFRICASTALKING_API_KEY:
        return {
            "id": "sms_reachable",
            "label": "SMS provider reachable",
            "status": "not_configured",
            "detail": "Skipped — Africa's Talking is not configured.",
        }
    started = time.time()
    reachable, status_code, err = await _http_head(AT_PROBE_URL)
    latency_ms = round((time.time() - started) * 1000, 1)
    if reachable:
        return {
            "id": "sms_reachable",
            "label": "SMS provider reachable",
            "status": "ok",
            "latency_ms": latency_ms,
            "detail": f"Reached Africa's Talking (HTTP {status_code}).",
            "http_status": status_code,
        }
    return {
        "id": "sms_reachable",
        "label": "SMS provider reachable",
        "status": "down",
        "latency_ms": latency_ms,
        "detail": "Couldn't reach Africa's Talking. Check the server's internet connection.",
        "error": err,
    }


# ─── Email — SMTP ───

def _check_email_config() -> dict:
    if not settings.SMTP_HOST:
        return {
            "id": "email_config",
            "label": "Email (SMTP) configured",
            "status": "not_configured",
            "detail": "SMTP host is not set. Email notifications will not be sent.",
            "missing": ["SMTP_HOST"],
        }
    return {
        "id": "email_config",
        "label": "Email (SMTP) configured",
        "status": "ok",
        "detail": f"SMTP set to {settings.SMTP_HOST}:{settings.SMTP_PORT}, "
                  f"from {settings.SMTP_FROM}.",
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_from": settings.SMTP_FROM,
        "auth": bool(settings.SMTP_USER),
    }


def _check_email_reachable() -> dict:
    """TCP-only — never sends a real email."""
    if not settings.SMTP_HOST:
        return {
            "id": "email_reachable",
            "label": "Email (SMTP) reachable",
            "status": "not_configured",
            "detail": "Skipped — SMTP is not configured.",
        }
    started = time.time()
    reachable, err = _tcp_reachable(settings.SMTP_HOST, settings.SMTP_PORT)
    latency_ms = round((time.time() - started) * 1000, 1)
    if reachable:
        return {
            "id": "email_reachable",
            "label": "Email (SMTP) reachable",
            "status": "ok",
            "latency_ms": latency_ms,
            "detail": f"Opened TCP connection to {settings.SMTP_HOST}:{settings.SMTP_PORT}.",
        }
    return {
        "id": "email_reachable",
        "label": "Email (SMTP) reachable",
        "status": "down",
        "latency_ms": latency_ms,
        "detail": (
            f"Couldn't connect to {settings.SMTP_HOST}:{settings.SMTP_PORT}. "
            "Check the host/port and the server's outbound firewall."
        ),
        "error": err,
    }


# ─── Push — FCM ───

FCM_PROBE_URL = "https://fcm.googleapis.com/fcm/send"


def _check_push_config() -> dict:
    if not settings.FCM_SERVER_KEY:
        return {
            "id": "push_config",
            "label": "Push (FCM) configured",
            "status": "not_configured",
            "detail": "Firebase Cloud Messaging key is not set. Push notifications will not be sent.",
            "missing": ["FCM_SERVER_KEY"],
        }
    return {
        "id": "push_config",
        "label": "Push (FCM) configured",
        "status": "ok",
        "detail": "Firebase Cloud Messaging key is set.",
        "key_preview": settings.FCM_SERVER_KEY[:6] + "…",
    }


async def _check_push_reachable() -> dict:
    if not settings.FCM_SERVER_KEY:
        return {
            "id": "push_reachable",
            "label": "Push (FCM) reachable",
            "status": "not_configured",
            "detail": "Skipped — FCM is not configured.",
        }
    started = time.time()
    reachable, status_code, err = await _http_head(FCM_PROBE_URL)
    latency_ms = round((time.time() - started) * 1000, 1)
    if reachable:
        return {
            "id": "push_reachable",
            "label": "Push (FCM) reachable",
            "status": "ok",
            "latency_ms": latency_ms,
            "detail": f"Reached fcm.googleapis.com (HTTP {status_code}).",
            "http_status": status_code,
        }
    return {
        "id": "push_reachable",
        "label": "Push (FCM) reachable",
        "status": "down",
        "latency_ms": latency_ms,
        "detail": "Couldn't reach fcm.googleapis.com.",
        "error": err,
    }


# ─── WhatsApp — Meta Cloud API ───

def _check_whatsapp_config() -> dict:
    missing = []
    if not settings.WHATSAPP_ACCESS_TOKEN:
        missing.append("WHATSAPP_ACCESS_TOKEN")
    if not settings.WHATSAPP_PHONE_NUMBER_ID:
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if missing:
        return {
            "id": "whatsapp_config",
            "label": "WhatsApp Business configured",
            "status": "not_configured",
            "detail": "WhatsApp Business API is not connected yet. Parents won't receive WhatsApp messages.",
            "missing": missing,
        }
    return {
        "id": "whatsapp_config",
        "label": "WhatsApp Business configured",
        "status": "ok",
        "detail": "WhatsApp Business credentials are set.",
        "phone_number_id_preview": settings.WHATSAPP_PHONE_NUMBER_ID[:6] + "…",
    }


async def _check_whatsapp_reachable() -> dict:
    if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
        return {
            "id": "whatsapp_reachable",
            "label": "WhatsApp API reachable",
            "status": "not_configured",
            "detail": "Skipped — WhatsApp is not configured.",
        }
    started = time.time()
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.5),
        ) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
        latency_ms = round((time.time() - started) * 1000, 1)
        if resp.status_code == 200:
            return {
                "id": "whatsapp_reachable",
                "label": "WhatsApp API reachable",
                "status": "ok",
                "latency_ms": latency_ms,
                "detail": "Connected to the WhatsApp Business API and verified the access token.",
                "http_status": 200,
            }
        # 401/403 means token is bad, even though we reached Meta
        if resp.status_code in (401, 403):
            return {
                "id": "whatsapp_reachable",
                "label": "WhatsApp API reachable",
                "status": "down",
                "latency_ms": latency_ms,
                "detail": "Meta rejected the access token. Generate a new one in WhatsApp Business Manager.",
                "http_status": resp.status_code,
            }
        return {
            "id": "whatsapp_reachable",
            "label": "WhatsApp API reachable",
            "status": "degraded",
            "latency_ms": latency_ms,
            "detail": f"Unexpected response from Meta (HTTP {resp.status_code}).",
            "http_status": resp.status_code,
        }
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {
            "id": "whatsapp_reachable",
            "label": "WhatsApp API reachable",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Couldn't reach graph.facebook.com.",
            "error": str(e)[:300],
        }
    except Exception as e:  # pragma: no cover
        return {
            "id": "whatsapp_reachable",
            "label": "WhatsApp API reachable",
            "status": "down",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "detail": "Unexpected error contacting WhatsApp API.",
            "error": str(e)[:300],
        }


# ─── Roll-up ───

def _roll_up(checks: list[dict[str, Any]]) -> tuple[str, str]:
    statuses = [c.get("status") for c in checks]
    if "down" in statuses:
        return "down", "One or more channels are unhealthy. See details below."
    if "degraded" in statuses:
        return "degraded", "Messaging is working but slow on at least one channel."
    if any(s == "ok" for s in statuses) and "not_configured" in statuses:
        return "ok", "Messaging is healthy. Some channels are not configured yet."
    if all(s == "not_configured" for s in statuses if s):
        return "not_configured", "No delivery channels are configured."
    return "ok", "All channels passed."


@router.post("/probe")
async def probe(request: Request):
    checks: list[dict[str, Any]] = []
    checks.append(_check_db())
    checks.append(_check_outbox_lag())

    # SMS
    checks.append(_check_sms_config())
    checks.append(await _check_sms_reachable())

    # Email
    checks.append(_check_email_config())
    checks.append(_check_email_reachable())

    # Push
    checks.append(_check_push_config())
    checks.append(await _check_push_reachable())

    # WhatsApp
    checks.append(_check_whatsapp_config())
    checks.append(await _check_whatsapp_reachable())

    status, message = _roll_up(checks)
    return {
        "data": {"status": status, "message": message, "checks": checks},
        "meta": _meta(request),
    }
