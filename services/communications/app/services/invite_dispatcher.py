"""Phase 15a — InviteDispatcher.

Given an Invitation (created by identity service), this service:

  1. Resolves the preferred delivery channel for the school from
     `SchoolNotificationConfig` (Phase 12c). Priority order:
     SMS → WhatsApp → Email → Manual.
  2. Renders the body via `templates.invite.render`.
  3. Writes a row to `InviteOutbox` for delivery (the outbox worker
     reads it and sends via the configured provider).
  4. When channel = manual (no config), the outbox row lands in
     `manual_pending` status with the 6-digit code populated; the
     admin reads it out over the phone.

This module is stateless and importable; the route layer calls
`dispatch(...)` after creating the invitation. The dispatcher does
NOT call the provider in-process — it persists, and a separate worker
(already wired for announcements) delivers. Phase 15a wires only the
persistence step; provider-side delivery integration tests come in
Phase 15e closeout.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification_config import SchoolNotificationConfig
from app.models.invite_outbox import InviteOutbox
from app.templates.invite import render as render_template

logger = logging.getLogger(__name__)


# Priority order. The first channel that:
#   (a) has a configured provider for the school, AND
#   (b) has matching recipient contact info on the invitation row
# wins. Falls through to "manual" when nothing fits.
CHANNEL_PRIORITY = ("sms", "whatsapp", "email", "manual")


@dataclass
class DispatchResult:
    invite_outbox_id: str
    channel: str
    provider_name: Optional[str]
    status: str
    body_excerpt: str


def _has_provider(db: Session, school_id: uuid.UUID, channel: str) -> Optional[SchoolNotificationConfig]:
    return (
        db.query(SchoolNotificationConfig)
        .filter(
            SchoolNotificationConfig.school_id == school_id,
            SchoolNotificationConfig.channel == channel,
        )
        .first()
    )


def _channel_matches_contact(channel: str, *, email: Optional[str], phone: Optional[str]) -> bool:
    if channel in ("sms", "whatsapp"):
        return bool(phone)
    if channel == "email":
        return bool(email)
    return True   # manual always matches


def _pick_channel(
    db: Session, school_id: uuid.UUID,
    *, email: Optional[str], phone: Optional[str],
) -> tuple[str, Optional[SchoolNotificationConfig]]:
    """Returns (channel, config_row). config_row is None for manual."""
    for ch in CHANNEL_PRIORITY:
        if ch == "manual":
            return ch, None
        if not _channel_matches_contact(ch, email=email, phone=phone):
            continue
        cfg = _has_provider(db, school_id, ch)
        if cfg:
            return ch, cfg
    return "manual", None


def dispatch(
    db: Session,
    *,
    invitation_id: str,
    school_id: uuid.UUID,
    school_name: str,
    role: str,
    full_name: str,
    contact_email: Optional[str],
    contact_phone: Optional[str],
    manual_code: str,
    invite_url: str,
) -> DispatchResult:
    """Pick a channel + persist an InviteOutbox row. Returns the
    DispatchResult (channel + status + body excerpt) for the caller's
    UI."""
    channel, cfg = _pick_channel(
        db, school_id, email=contact_email, phone=contact_phone,
    )
    rendered = render_template(
        role=role, channel=channel,
        ctx={
            "school_name": school_name,
            "full_name": full_name,
            "invite_url": invite_url,
            "manual_code": manual_code,
        },
    )
    status = "manual_pending" if channel == "manual" else "queued"

    row = InviteOutbox(
        id=uuid.uuid4(),
        school_id=school_id,
        invitation_id=str(invitation_id),
        channel=channel,
        provider_name=(cfg.provider_name if cfg else None),
        recipient_email=contact_email,
        recipient_phone=contact_phone,
        subject=rendered.subject,
        body=rendered.body,
        manual_code=manual_code,
        invite_url=invite_url,
        status=status,
    )
    db.add(row)
    db.commit()
    return DispatchResult(
        invite_outbox_id=str(row.id),
        channel=channel,
        provider_name=(cfg.provider_name if cfg else None),
        status=status,
        body_excerpt=(rendered.body[:120] if rendered.body else ""),
    )
