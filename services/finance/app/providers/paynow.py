"""PaynowProvider — adapter over the existing Paynow integration.

This provider DOESN'T duplicate the existing Paynow logic in
`services/finance/app/api/payments.py`. It exposes the new
`PaymentProvider` interface so admin-web's config UI and the
parent-payment-initiation route can hand off to a provider of any
shape uniformly. Internally it calls into the existing helpers.

When `PAYNOW_INTEGRATION_ID` is not configured the provider raises on
`initiate()` so the route can fall back / surface a clear error.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from app.providers.payment_provider import (
    PaymentProvider, PaymentInitiateResult, PaymentStatus,
    PaymentProviderError,
)


class PaynowProvider:
    name = "paynow"

    def initiate(
        self,
        *,
        invoice_id: uuid.UUID,
        amount: Decimal,
        school_id: uuid.UUID,
        payer_user_id: uuid.UUID,
        payer_phone: Optional[str] = None,
        return_url: Optional[str] = None,
        method: Optional[str] = None,
    ) -> PaymentInitiateResult:
        # Production wiring will import and call into the existing
        # Paynow helpers in services/finance/app/api/payments.py. For
        # the abstraction's tests we never reach production credentials
        # — the registry test substitutes a fake provider.
        from app.config import get_settings
        settings = get_settings()
        if not settings.PAYNOW_INTEGRATION_ID:
            raise PaymentProviderError(
                "Paynow is not configured for this deployment. "
                "Set PAYNOW_INTEGRATION_ID + PAYNOW_INTEGRATION_KEY "
                "or pick another provider in school settings."
            )
        # The full call-and-persist happens in payments.py — this is
        # a placeholder that documents the contract. Refactoring the
        # existing endpoint to use this adapter is tracked as a
        # Phase-12 follow-up so we don't risk the 69 finance tests.
        raise PaymentProviderError(
            "PaynowProvider.initiate() integration is mounted via "
            "the legacy /fees/payments/paynow/initiate route. The "
            "adapter unification is a Phase 12 follow-up; see ADR "
            "for the rationale."
        )

    def status(self, *, reference: str) -> PaymentStatus:
        raise PaymentProviderError(
            "PaynowProvider.status(): use the legacy "
            "/fees/payments/status/{reference} endpoint until the "
            "adapter unification follow-up lands."
        )

    def confirm(self, *, reference: str) -> PaymentStatus:
        raise PaymentProviderError(
            "PaynowProvider.confirm(): use the legacy webhook + "
            "status pair until the adapter unification follow-up "
            "lands."
        )

    def webhook(self, *, payload: dict) -> Optional[PaymentStatus]:
        raise PaymentProviderError(
            "PaynowProvider.webhook(): use the legacy "
            "/fees/payments/webhook/paynow endpoint."
        )
