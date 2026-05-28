"""
WhatsApp Business Cloud API webhook routes.

* ``GET  /comm/webhooks/whatsapp`` — Meta verification handshake.
* ``POST /comm/webhooks/whatsapp`` — delivery callbacks (status updates) and
  inbound messages.  We treat the wamid as the natural idempotency key:
  the first callback wins, repeats short-circuit on
  ``WhatsAppMessage.last_callback_status``.

Inbound text messages currently log + ack — actual parent reply handling is
out of scope for Squad A; the contract here just keeps Meta from retrying.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.communication import NotificationOutbox
from app.models.whatsapp import WhatsAppMessage
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta,
)
from app.services.whatsapp_provider import classify_status, utc_now

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["WhatsApp Webhooks"])



# ──────────────────────── Verification (GET) ─────────────────────────
#
# Meta calls us with `hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`
# We echo `hub.challenge` iff the token matches our configured value.

@router.get("/comm/webhooks/whatsapp")
def whatsapp_verify(request: Request):
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge", "")

    expected = settings.WHATSAPP_VERIFY_TOKEN
    if mode == "subscribe" and expected and token == expected:
        return PlainTextResponse(challenge, status_code=200)
    return PlainTextResponse("forbidden", status_code=403)


# ───────────────────── Delivery callback (POST) ──────────────────────

@router.post("/comm/webhooks/whatsapp")
async def whatsapp_callback(request: Request, db: Session = Depends(get_db)):
    """Process Meta delivery + inbound notifications.

    Meta payload schema (abridged)::

        {
          "object": "whatsapp_business_account",
          "entry": [{
            "changes": [{
              "value": {
                "statuses": [{"id": "wamid…", "status": "delivered", ...}],
                "messages": [{"from": "263…", "text": {"body": "…"}}]
              }
            }]
          }]
        }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": {"code": "BAD_PAYLOAD", "message": "Invalid JSON",
                       "request_id": _meta(request)["request_id"]}},
            status_code=400,
        )

    statuses_seen = 0
    messages_seen = 0
    duplicates = 0

    for entry in body.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}

            for status in value.get("statuses", []) or []:
                wamid = status.get("id")
                new_status = status.get("status")
                if not wamid or not new_status:
                    continue

                wa = (
                    db.query(WhatsAppMessage)
                    .filter(WhatsAppMessage.provider_message_id == wamid)
                    .first()
                )
                if not wa:
                    # Unknown wamid — ack so Meta stops retrying but log.
                    logger.info("WhatsApp callback for unknown wamid=%s", wamid)
                    continue

                # Idempotency: same terminal status seen before → no-op.
                if wa.last_callback_status == new_status:
                    duplicates += 1
                    continue

                statuses_seen += 1

                wa.last_callback_status = new_status
                wa.last_callback_at = utc_now()
                err = status.get("errors")
                if err:
                    e0 = err[0] if isinstance(err, list) and err else {}
                    wa.error_code = str(e0.get("code", ""))[:64] or wa.error_code
                    wa.error_message = (
                        str(e0.get("title") or e0.get("message", ""))[:1000]
                        or wa.error_message
                    )

                # Propagate to the outbox row if linked.
                if wa.outbox_id:
                    outbox = db.query(NotificationOutbox).filter(
                        NotificationOutbox.id == wa.outbox_id,
                    ).first()
                    if outbox:
                        mapped = classify_status(new_status)
                        if mapped == "SENT":
                            outbox.status = "SENT"
                            outbox.error_message = None
                        elif mapped == "FAILED":
                            outbox.status = "FAILED"
                            outbox.error_message = (
                                wa.error_message or f"WhatsApp status={new_status}"
                            )
                        outbox.last_attempt_at = utc_now()

            for _msg in value.get("messages", []) or []:
                # Inbound parent replies — record metric only, no action yet.
                messages_seen += 1

    db.commit()
    return {
        "data": {
            "statuses_processed": statuses_seen,
            "duplicates_skipped": duplicates,
            "messages_received": messages_seen,
        },
        "meta": _meta(request),
    }
