"""ManualHandoverProvider — off-platform payment recording.

For schools without an electronic-gateway relationship. The parent
pays in cash, EcoCash direct, bank transfer, etc., outside our
platform. The school records the reference on our side and marks
the invoice paid.

  `initiate()` — returns a unique reference + instructions text.
    No redirect (the parent does the payment off-platform).
  `confirm(reference)` — finalises ONLY when an admin POSTs to the
    confirmation endpoint. Without that, the txn stays PENDING.
  `webhook()` — no-op (manual flow has no webhook).
  `status()` — reads back the latest PaymentTransaction row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.providers.payment_provider import (
    PaymentProvider, PaymentInitiateResult, PaymentStatus,
    PaymentProviderError,
)


class ManualHandoverProvider:
    name = "manual"

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
        # Reference shape: `MAN-<short uuid>` — easy to write on a
        # bank-deposit slip / EcoCash reference field.
        ref = f"MAN-{uuid.uuid4().hex[:10].upper()}"
        return PaymentInitiateResult(
            reference=ref,
            redirect_url=None,
            status="PENDING",
            raw_response={
                "instructions": (
                    "Pay the indicated amount via your school's "
                    "off-platform channel (cash / EcoCash direct / "
                    "bank transfer). Include this reference. The "
                    "school office will mark the invoice paid once "
                    "the funds clear."
                ),
                "reference": ref,
                "amount": str(amount),
                "invoice_id": str(invoice_id),
                "initiated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def status(self, *, reference: str) -> PaymentStatus:
        # Manual provider has no external state to query. Callers
        # should read the PaymentTransaction row directly.
        return PaymentStatus(
            reference=reference, status="PENDING",
            paid_amount=None, raw_response={},
        )

    def confirm(self, *, reference: str) -> PaymentStatus:
        # The actual marking-paid happens in the admin endpoint that
        # records the payment; this method is a no-op so the
        # interface stays satisfied.
        return PaymentStatus(
            reference=reference, status="PAID",
            paid_amount=None, raw_response={"confirmed_manually": True},
        )

    def webhook(self, *, payload: dict) -> Optional[PaymentStatus]:
        # No webhook for manual flows.
        return None
