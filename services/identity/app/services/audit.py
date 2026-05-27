"""Audit log helper (Phase 9 — Q-016 / INFRA-018).

Lightweight write API for the `audit_log` table. Callers wire this into
sensitive-action paths (login, role grant, secret rotation, etc.).

The full integration — auditing every PII write across every service —
is the bigger Phase 9 lift and is intentionally NOT done in this commit.
This module ships the substrate so the integration is a small per-call
change later.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.user import AuditLog

logger = logging.getLogger(__name__)


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    school_id: uuid.UUID,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_role: Optional[str] = None,
    target: Optional[dict] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Write one audit row. Never raises into the caller.

    If the database write fails (e.g., during shutdown) we log loudly so
    ops can see the gap but we don't abort the caller's main work — an
    audit log that can crash a login flow is a worse outcome than a
    missing audit row.
    """
    try:
        row = AuditLog(
            id=uuid.uuid4(),
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            school_id=school_id,
            event_type=event_type,
            target=json.dumps(target) if target is not None else None,
            details=json.dumps(details) if details is not None else None,
            ip_address=ip_address,
            user_agent=(user_agent[:255] if user_agent else None),
            request_id=request_id,
        )
        db.add(row)
        db.flush()  # ensure constraint failures surface here
    except Exception as e:
        logger.error(
            "Audit write failed (event=%s school=%s actor=%s): %s",
            event_type, school_id, actor_user_id, e,
        )
