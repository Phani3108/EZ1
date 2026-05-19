"""
Communication Service Business Logic
=======================================
- Audience resolution (ALL/CLASS/ROLE)
- Outbox creation (no duplicates)
- Delivery engine (poll PENDING, attempt, retry, mark FAILED at max)
- Mock SMS provider
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

from sqlalchemy.orm import Session

from app.models.communication import Announcement, NotificationOutbox


# ───────────── Audience Resolver Protocol ─────────────

class AudienceResolver(Protocol):
    """Resolves audience to list of user_ids. Injectable for testing."""
    def resolve(self, school_id: uuid.UUID, audience_type: str,
                class_id: uuid.UUID = None, role: str = None) -> list[uuid.UUID]: ...


class MockAudienceResolver:
    """Pre-loaded audience for testing and Phase 1."""
    def __init__(self):
        self._users: dict[str, list[uuid.UUID]] = {}  # keyed by school_id

    def add_users(self, school_id: uuid.UUID, users: list[uuid.UUID]):
        self._users[str(school_id)] = users

    def add_class_users(self, school_id: uuid.UUID, class_id: uuid.UUID,
                        users: list[uuid.UUID]):
        self._users[f"{school_id}:class:{class_id}"] = users

    def add_role_users(self, school_id: uuid.UUID, role: str,
                       users: list[uuid.UUID]):
        self._users[f"{school_id}:role:{role}"] = users

    def resolve(self, school_id: uuid.UUID, audience_type: str,
                class_id: uuid.UUID = None, role: str = None) -> list[uuid.UUID]:
        if audience_type == "ALL":
            return self._users.get(str(school_id), [])
        elif audience_type == "CLASS" and class_id:
            return self._users.get(f"{school_id}:class:{class_id}", [])
        elif audience_type == "ROLE" and role:
            return self._users.get(f"{school_id}:role:{role}", [])
        return []


# ───────────── SMS Provider Protocol ─────────────

class SMSProvider(Protocol):
    def send(self, phone: str, message: str) -> bool: ...


class MockSMSProvider:
    """Mock SMS provider — always succeeds (configurable for failure testing)."""
    def __init__(self, fail_for: set = None):
        self.sent: list[dict] = []
        self.fail_for = fail_for or set()  # set of user_ids to fail for

    def send(self, user_id: str, message: str) -> bool:
        if user_id in self.fail_for:
            return False
        self.sent.append({"user_id": user_id, "message": message})
        return True


# ───────────── Communication Service ─────────────

class CommunicationService:
    def __init__(self, db: Session, audience_resolver: AudienceResolver = None,
                 sms_provider: SMSProvider = None, max_retries: int = 3,
                 whatsapp_provider=None, user_phone_resolver=None):
        self.db = db
        self.audience_resolver = audience_resolver or MockAudienceResolver()
        self.sms_provider = sms_provider or MockSMSProvider()
        self.max_retries = max_retries
        # Lazy import — keeps the module import-cycle free.
        if whatsapp_provider is None:
            from app.services.whatsapp_provider import get_provider as _wa
            self.whatsapp_provider = _wa()
        else:
            self.whatsapp_provider = whatsapp_provider
        # `user_phone_resolver(user_id) -> phone:str|None` — in production wired
        # to student-service; tests inject a dict-backed callable.
        self.user_phone_resolver = user_phone_resolver or (lambda _uid: None)

    # ───────────── Announcements ─────────────

    def create_announcement(self, school_id: uuid.UUID, title: str, body: str,
                             audience_type: str, channels: list[str],
                             created_by: uuid.UUID,
                             class_id: uuid.UUID = None,
                             role: str = None) -> dict:
        # Validate audience params
        if audience_type == "CLASS" and not class_id:
            return {"error": "INVALID_AUDIENCE", "message": "class_id required for CLASS audience"}
        if audience_type == "ROLE" and not role:
            return {"error": "INVALID_AUDIENCE", "message": "role required for ROLE audience"}
        if audience_type == "ALL" and class_id:
            return {"error": "INVALID_AUDIENCE", "message": "class_id not allowed for ALL audience"}

        # Step 1: Persist announcement BEFORE delivery
        announcement = Announcement(
            school_id=school_id, title=title, body=body,
            audience_type=audience_type,
            audience_class_id=class_id,
            audience_role=role,
            created_by=created_by,
        )
        self.db.add(announcement)
        self.db.flush()

        # Step 2: Resolve audience
        user_ids = self.audience_resolver.resolve(school_id, audience_type, class_id, role)

        # Step 3: Create outbox entries (no duplicates via unique constraint)
        outbox_count = 0
        for uid in user_ids:
            for channel in channels:
                existing = self.db.query(NotificationOutbox).filter(
                    NotificationOutbox.announcement_id == announcement.id,
                    NotificationOutbox.user_id == uid,
                    NotificationOutbox.channel == channel,
                ).first()
                if not existing:
                    entry = NotificationOutbox(
                        school_id=school_id, announcement_id=announcement.id,
                        user_id=uid, channel=channel, status="PENDING",
                    )
                    self.db.add(entry)
                    outbox_count += 1

        self.db.commit()
        self.db.refresh(announcement)

        return {
            "announcement": self._ser_announcement(announcement),
            "outbox_created": outbox_count,
            "recipient_count": len(user_ids),
            "channels": channels,
        }

    def list_announcements(self, school_id: uuid.UUID, page: int = 1,
                            page_size: int = 50) -> tuple[list[dict], int]:
        q = self.db.query(Announcement).filter(
            Announcement.school_id == school_id,
            Announcement.deleted_at == None,
        )
        total = q.count()
        anns = q.order_by(Announcement.created_at.desc()).offset(
            (page - 1) * page_size).limit(page_size).all()
        return [self._ser_announcement(a) for a in anns], total

    def get_feed_for_student(self, school_id: uuid.UUID,
                              student_id: uuid.UUID,
                              class_id: uuid.UUID = None,
                              page: int = 1,
                              page_size: int = 20) -> tuple[list[dict], int]:
        """Return announcements relevant to a parent viewing a specific child.

        Includes:
        - ALL audience announcements
        - CLASS audience matching the child's class_id
        - ROLE audience targeting 'Parent'
        """
        from sqlalchemy import or_

        filters = [
            Announcement.school_id == school_id,
            Announcement.deleted_at == None,
        ]

        audience_conditions = [
            Announcement.audience_type == "ALL",
            Announcement.audience_type == "ROLE",
        ]
        if class_id:
            audience_conditions.append(
                (Announcement.audience_type == "CLASS") &
                (Announcement.audience_class_id == class_id)
            )

        q = self.db.query(Announcement).filter(
            *filters, or_(*audience_conditions)
        )
        total = q.count()
        anns = q.order_by(Announcement.created_at.desc()).offset(
            (page - 1) * page_size).limit(page_size).all()
        return [self._ser_announcement(a) for a in anns], total

    def soft_delete_announcement(self, ann_id: uuid.UUID,
                                  school_id: uuid.UUID) -> Optional[dict]:
        ann = self.db.query(Announcement).filter(
            Announcement.id == ann_id, Announcement.school_id == school_id,
            Announcement.deleted_at == None,
        ).first()
        if not ann:
            return None
        ann.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(ann)
        return self._ser_announcement(ann)

    # ───────────── Outbox ─────────────

    def get_outbox(self, school_id: uuid.UUID, status: str = None,
                   announcement_id: uuid.UUID = None,
                   limit: int = 100, offset: int = 0) -> list[dict]:
        # Hard-cap to protect against runaway tenants.
        limit = max(1, min(int(limit or 100), 500))
        offset = max(0, int(offset or 0))
        q = self.db.query(NotificationOutbox).filter(
            NotificationOutbox.school_id == school_id,
        )
        if status:
            q = q.filter(NotificationOutbox.status == status)
        if announcement_id:
            q = q.filter(NotificationOutbox.announcement_id == announcement_id)
        rows = (
            q.order_by(NotificationOutbox.created_at)
             .offset(offset)
             .limit(limit)
             .all()
        )
        return [self._ser_outbox(o) for o in rows]

    # ───────────── Delivery Engine ─────────────

    def process_pending(self, school_id: uuid.UUID = None) -> dict:
        """Poll PENDING outbox entries and attempt delivery."""
        q = self.db.query(NotificationOutbox).filter(
            NotificationOutbox.status == "PENDING",
        )
        if school_id:
            q = q.filter(NotificationOutbox.school_id == school_id)

        entries = q.all()
        sent = 0
        failed = 0
        retried = 0

        for entry in entries:
            success = self._attempt_delivery(entry)
            entry.last_attempt_at = datetime.now(timezone.utc)

            if success:
                entry.status = "SENT"
                sent += 1
            else:
                entry.retry_count += 1
                if entry.retry_count >= self.max_retries:
                    entry.status = "FAILED"
                    entry.error_message = f"Max retries ({self.max_retries}) exceeded"
                    failed += 1
                else:
                    retried += 1

        self.db.commit()
        return {"sent": sent, "failed": failed, "retried": retried, "total": len(entries)}

    def _attempt_delivery(self, entry: NotificationOutbox) -> bool:
        """Attempt delivery via the appropriate channel."""
        if entry.channel == "IN_APP":
            return True  # In-app is always "delivered" (read from outbox)
        elif entry.channel == "SMS":
            announcement = self.db.query(Announcement).filter(
                Announcement.id == entry.announcement_id,
            ).first()
            msg = f"{announcement.title}: {announcement.body}" if announcement else ""
            return self.sms_provider.send(str(entry.user_id), msg)
        elif entry.channel == "WHATSAPP":
            return self._send_whatsapp(entry)
        return False

    def _send_whatsapp(self, entry: NotificationOutbox) -> bool:
        """Hand a WhatsApp outbox entry to the provider and record the wamid."""
        from app.models.whatsapp import WhatsAppMessage

        announcement = self.db.query(Announcement).filter(
            Announcement.id == entry.announcement_id,
        ).first()
        if not announcement:
            entry.error_message = "Announcement not found for outbox entry"
            return False

        phone = self.user_phone_resolver(str(entry.user_id))
        if not phone:
            entry.error_message = "Recipient has no WhatsApp number on file"
            return False

        body = f"*{announcement.title}*\n\n{announcement.body}"
        ok, payload = self.whatsapp_provider.send_text(phone, body)

        wamid = None
        if ok:
            try:
                wamid = payload["messages"][0]["id"]
            except (KeyError, IndexError, TypeError):
                wamid = None

        # Always create an audit row so retries don't fork into ghosts.
        wa = WhatsAppMessage(
            school_id=entry.school_id,
            outbox_id=entry.id,
            to_phone=phone,
            provider_message_id=wamid,
            body_preview=body[:500],
        )
        if not ok:
            err = (payload or {}).get("error", {}) if isinstance(payload, dict) else {}
            wa.error_code = str(err.get("code", "send_failed"))[:64]
            wa.error_message = str(err.get("message", "WhatsApp send failed"))[:1000]
            entry.error_message = wa.error_message
        self.db.add(wa)
        return ok

    # ───────────── Serializers ─────────────

    def _ser_announcement(self, a: Announcement) -> dict:
        return {
            "id": str(a.id), "school_id": str(a.school_id),
            "title": a.title, "body": a.body,
            "audience_type": a.audience_type,
            "audience_class_id": str(a.audience_class_id) if a.audience_class_id else None,
            "audience_role": a.audience_role,
            "created_by": str(a.created_by),
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "deleted_at": a.deleted_at.isoformat() if a.deleted_at else None,
        }

    def _ser_outbox(self, o: NotificationOutbox) -> dict:
        return {
            "id": str(o.id), "school_id": str(o.school_id),
            "announcement_id": str(o.announcement_id),
            "user_id": str(o.user_id),
            "channel": o.channel, "status": o.status,
            "retry_count": o.retry_count,
            "last_attempt_at": o.last_attempt_at.isoformat() if o.last_attempt_at else None,
            "error_message": o.error_message,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
