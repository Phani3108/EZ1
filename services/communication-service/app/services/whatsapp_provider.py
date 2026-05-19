"""
Meta WhatsApp Business Cloud API provider.

Implements two flows:

1. **Outbound send** — `MetaWhatsAppProvider.send_text` and `send_template`
   POST to ``https://graph.facebook.com/v19.0/{phone_number_id}/messages`` and
   return ``(ok: bool, payload: dict)`` where ``payload`` contains the
   provider's ``messages[0].id`` (the *wamid*) on success, or an error body.

2. **Delivery callback handling** — when Meta POSTs back to the webhook with
   ``statuses[*]`` rows, we update the matching ``WhatsAppMessage`` and
   propagate the terminal status (delivered/read/failed) onto the originating
   ``NotificationOutbox`` row.  Each wamid is processed once thanks to the
   ``WhatsAppMessage.provider_message_id`` unique index plus the
   ``WhatsAppMessage.last_callback_status`` short-circuit.

The provider is intentionally injectable: ``MockWhatsAppProvider`` is used in
tests and in dev-mode so the rest of the service can rely on the same
contract regardless of whether credentials are configured.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

META_GRAPH_BASE = "https://graph.facebook.com/v19.0"


class WhatsAppProvider(Protocol):
    """Outbound WhatsApp client contract."""

    def send_text(self, phone: str, body: str) -> tuple[bool, dict]: ...

    def send_template(
        self, phone: str, template_name: str,
        language: str = "en", components: Optional[list[dict]] = None,
    ) -> tuple[bool, dict]: ...


# ─────────────────────────── Mock (dev / tests) ────────────────────────────

class MockWhatsAppProvider:
    """In-memory provider — records every call, never touches the network."""

    def __init__(self, fail_for: Optional[set[str]] = None):
        self.sent: list[dict] = []
        self.fail_for = fail_for or set()

    def _record(self, kind: str, phone: str, payload: dict) -> tuple[bool, dict]:
        if phone in self.fail_for:
            self.sent.append({"kind": kind, "phone": phone, "ok": False, **payload})
            return False, {"error": {"message": "mock-forced-failure"}}
        wamid = f"wamid.MOCK.{uuid.uuid4().hex[:12].upper()}"
        self.sent.append({"kind": kind, "phone": phone, "ok": True, "wamid": wamid, **payload})
        return True, {"messages": [{"id": wamid}], "contacts": [{"wa_id": phone}]}

    def send_text(self, phone: str, body: str) -> tuple[bool, dict]:
        return self._record("text", phone, {"body": body})

    def send_template(self, phone: str, template_name: str,
                      language: str = "en",
                      components: Optional[list[dict]] = None) -> tuple[bool, dict]:
        return self._record("template", phone, {
            "template": template_name, "language": language,
            "components": components or [],
        })


# ─────────────────────────── Meta Cloud client ─────────────────────────────

class MetaWhatsAppProvider:
    """Real Meta WhatsApp Business Cloud API client (httpx, sync)."""

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout_s: float = 15.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.timeout_s = timeout_s
        self._transport = transport  # tests inject a MockTransport here

    @property
    def configured(self) -> bool:
        return bool(self.phone_number_id and self.access_token)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=META_GRAPH_BASE,
            timeout=self.timeout_s,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )

    def _post(self, body: dict) -> tuple[bool, dict]:
        url = f"/{self.phone_number_id}/messages"
        try:
            with self._client() as client:
                resp = client.post(url, json=body)
        except httpx.HTTPError as exc:
            logger.warning("WhatsApp network error: %s", exc)
            return False, {"error": {"message": f"network: {exc}"}}

        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:500]}

        if resp.status_code >= 400:
            logger.warning("WhatsApp API %s: %s", resp.status_code, payload)
            return False, payload
        return True, payload

    def send_text(self, phone: str, body: str) -> tuple[bool, dict]:
        return self._post({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": body[:4096]},
        })

    def send_template(self, phone: str, template_name: str,
                      language: str = "en",
                      components: Optional[list[dict]] = None) -> tuple[bool, dict]:
        return self._post({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components or [],
            },
        })


# ─────────────── Helpers for the route layer ────────────────

# Map Meta statuses to our outbox vocabulary.
_DELIVERED_STATES = {"sent", "delivered", "read"}
_FAILED_STATES = {"failed", "undelivered"}


def classify_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s in _DELIVERED_STATES:
        return "SENT"
    if s in _FAILED_STATES:
        return "FAILED"
    return "PENDING"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_provider(transport: Optional[httpx.BaseTransport] = None) -> WhatsAppProvider:
    """Factory — real provider iff configured, otherwise the mock."""
    real = MetaWhatsAppProvider(transport=transport)
    if real.configured:
        return real
    return MockWhatsAppProvider()
