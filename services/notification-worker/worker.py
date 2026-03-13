"""
EduZim Notification Worker
===========================
Processes the communication-service outbox table and delivers notifications
via SMS (Africa's Talking), email (SMTP), and push (Firebase Cloud Messaging).

Runs as a standalone service polling the outbox every 5 seconds.
"""
import os
import time
import json
import uuid
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("notification-worker")

# ─── Config ───

COMMS_DB_URL = os.getenv("COMMS_DATABASE_URL", "postgresql://eduzim:eduzim_secret@localhost:5432/comms_db")
AUTH_DB_URL = os.getenv("AUTH_DATABASE_URL", "postgresql://eduzim:eduzim_secret@localhost:5432/auth_db")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# SMS - Africa's Talking
AT_API_KEY = os.getenv("AFRICASTALKING_API_KEY", "")
AT_USERNAME = os.getenv("AFRICASTALKING_USERNAME", "sandbox")
AT_SENDER = os.getenv("AFRICASTALKING_SENDER", "EduZim")

# Email - SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@eduzim.co.zw")

# Push - Firebase Cloud Messaging
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    comms_engine = create_engine(COMMS_DB_URL, pool_pre_ping=True, pool_size=5)
    auth_engine = create_engine(AUTH_DB_URL, pool_pre_ping=True, pool_size=2)
    CommsSession = sessionmaker(bind=comms_engine)
    AuthSession = sessionmaker(bind=auth_engine)
except ImportError:
    logger.error("SQLAlchemy not installed. pip install sqlalchemy psycopg2-binary")
    raise


# ─── Delivery Channels ───

def send_sms(phone: str, message: str) -> tuple[bool, str]:
    """Send SMS via Africa's Talking API."""
    if not AT_API_KEY:
        logger.warning("SMS skipped: AFRICASTALKING_API_KEY not set")
        return False, "SMS not configured"

    try:
        resp = requests.post(
            "https://api.africastalking.com/version1/messaging",
            headers={
                "apiKey": AT_API_KEY,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "username": AT_USERNAME,
                "to": phone,
                "message": message,
                "from": AT_SENDER,
            },
            timeout=10,
        )
        if resp.status_code == 201:
            return True, ""
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)[:200]


def send_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Send email via SMTP."""
    if not SMTP_HOST:
        logger.warning("Email skipped: SMTP_HOST not set")
        return False, "SMTP not configured"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(f"<html><body><p>{body}</p></body></html>", "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)[:200]


def send_push(device_token: str, title: str, body: str) -> tuple[bool, str]:
    """Send push notification via Firebase Cloud Messaging."""
    if not FCM_SERVER_KEY:
        logger.warning("Push skipped: FCM_SERVER_KEY not set")
        return False, "FCM not configured"

    try:
        resp = requests.post(
            "https://fcm.googleapis.com/fcm/send",
            headers={
                "Authorization": f"key={FCM_SERVER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "to": device_token,
                "notification": {"title": title, "body": body},
                "data": {"type": "announcement"},
            },
            timeout=10,
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("success", 0) > 0:
                return True, ""
            return False, f"FCM failure: {result.get('results', [])}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:200]


# ─── User Resolution ───

def get_user_contact(auth_session, user_id: str) -> dict:
    """Resolve user_id to email and phone from the auth database."""
    result = auth_session.execute(
        text("SELECT email, full_name FROM users WHERE id = :uid AND is_active = true"),
        {"uid": user_id},
    ).fetchone()
    if result:
        return {"email": result[0], "name": result[1]}
    return {}


def get_announcement(comms_session, announcement_id: str) -> dict:
    """Get announcement title and body."""
    result = comms_session.execute(
        text("SELECT title, body FROM announcements WHERE id = :aid"),
        {"aid": announcement_id},
    ).fetchone()
    if result:
        return {"title": result[0], "body": result[1]}
    return {}


# ─── Main Loop ───

def process_batch():
    """Pick up pending outbox entries and deliver them."""
    comms_db = CommsSession()
    auth_db = AuthSession()

    try:
        # Fetch pending entries (oldest first, with retry limit)
        rows = comms_db.execute(
            text("""
                SELECT id, announcement_id, user_id, channel, retry_count
                FROM notification_outbox
                WHERE status = 'PENDING' AND retry_count < :max_retries
                ORDER BY created_at ASC
                LIMIT :batch_size
            """),
            {"max_retries": MAX_RETRIES, "batch_size": BATCH_SIZE},
        ).fetchall()

        if not rows:
            return 0

        delivered = 0
        for row in rows:
            entry_id, announcement_id, user_id, channel, retry_count = row

            announcement = get_announcement(comms_db, str(announcement_id))
            if not announcement:
                _mark_failed(comms_db, entry_id, "Announcement not found")
                continue

            contact = get_user_contact(auth_db, str(user_id))
            if not contact:
                _mark_failed(comms_db, entry_id, "User not found or inactive")
                continue

            success = False
            error_msg = ""

            if channel == "SMS":
                # Need phone number - for now use email as fallback
                success, error_msg = False, "Phone lookup not yet implemented"
            elif channel == "EMAIL":
                success, error_msg = send_email(
                    contact["email"],
                    f"EduZim: {announcement['title']}",
                    announcement["body"],
                )
            elif channel == "PUSH":
                success, error_msg = False, "Push token lookup not yet implemented"
            elif channel == "IN_APP":
                # In-app notifications are read directly from the feed endpoint
                success = True
                error_msg = ""
            else:
                error_msg = f"Unknown channel: {channel}"

            if success:
                _mark_delivered(comms_db, entry_id)
                delivered += 1
            else:
                _mark_retry(comms_db, entry_id, retry_count + 1, error_msg)

        comms_db.commit()
        return delivered

    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        comms_db.rollback()
        return 0
    finally:
        comms_db.close()
        auth_db.close()


def _mark_delivered(db, entry_id):
    db.execute(
        text("""
            UPDATE notification_outbox
            SET status = 'DELIVERED', last_attempt_at = :now
            WHERE id = :id
        """),
        {"id": entry_id, "now": datetime.now(timezone.utc)},
    )


def _mark_retry(db, entry_id, new_count, error_msg):
    status = "FAILED" if new_count >= MAX_RETRIES else "PENDING"
    db.execute(
        text("""
            UPDATE notification_outbox
            SET status = :status, retry_count = :count,
                last_attempt_at = :now, error_message = :err
            WHERE id = :id
        """),
        {"id": entry_id, "status": status, "count": new_count,
         "now": datetime.now(timezone.utc), "err": error_msg},
    )


def _mark_failed(db, entry_id, error_msg):
    db.execute(
        text("""
            UPDATE notification_outbox
            SET status = 'FAILED', last_attempt_at = :now, error_message = :err
            WHERE id = :id
        """),
        {"id": entry_id, "now": datetime.now(timezone.utc), "err": error_msg},
    )


def main():
    logger.info("EduZim Notification Worker started")
    logger.info(f"Poll interval: {POLL_INTERVAL}s, Batch size: {BATCH_SIZE}, Max retries: {MAX_RETRIES}")
    logger.info(f"SMS: {'configured' if AT_API_KEY else 'not configured'}")
    logger.info(f"Email: {'configured' if SMTP_HOST else 'not configured'}")
    logger.info(f"Push: {'configured' if FCM_SERVER_KEY else 'not configured'}")

    while True:
        try:
            delivered = process_batch()
            if delivered > 0:
                logger.info(f"Delivered {delivered} notifications")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
