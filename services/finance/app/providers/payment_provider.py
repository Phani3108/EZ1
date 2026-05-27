"""PaymentProvider protocol (Phase 12b)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol


@dataclass(frozen=True)
class PaymentInitiateResult:
    """Result of `initiate()`. The `redirect_url` is what the parent's
    app navigates them to for hosted checkout flows (Paynow); for
    out-of-band flows (Manual) the field is None."""
    reference: str
    redirect_url: Optional[str]
    raw_response: dict
    # The wire-shape status — provider implementations normalise to
    # one of: "INITIATED", "PENDING", "PAID", "FAILED", "EXPIRED".
    status: str


@dataclass(frozen=True)
class PaymentStatus:
    reference: str
    status: str
    paid_amount: Optional[Decimal]
    raw_response: dict


class PaymentProviderError(Exception):
    """Raised on integration failures. Routes translate to 502 / 503."""


class PaymentProvider(Protocol):
    """Lifecycle of a payment:

      1. `initiate(invoice_id, amount, ...)` →
         persists a PaymentTransaction (provider impl is responsible
         for that); returns enough info for the caller to either
         redirect the user (Paynow) or display instructions (Manual).
      2. Async webhook (`webhook(payload)`) OR polled status
         (`status(reference)`) confirms the result.
      3. `confirm(reference)` is the route the caller uses on a
         success-redirect to finalise the invoice.
    """
    name: str

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
    ) -> PaymentInitiateResult: ...

    def status(self, *, reference: str) -> PaymentStatus: ...

    def confirm(self, *, reference: str) -> PaymentStatus: ...

    def webhook(self, *, payload: dict) -> Optional[PaymentStatus]: ...
