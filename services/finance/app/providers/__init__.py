"""Phase 12b — payment provider abstraction (PaymentProvider).

Per DEC-004 (revised): we don't build card processing in-house.
Schools pick a provider (Paynow today; future: Stripe, Flutterwave,
ManualHandover). Each provider implements the same interface.

  `PaymentProvider.initiate(invoice_id, amount)` — start a payment
  `PaymentProvider.confirm(reference)`           — finalise a payment
  `PaymentProvider.webhook(payload)`             — handle async result
  `PaymentProvider.status(reference)`            — query latest state

Provider selection is per-school, stored in `school_payment_config`
(see model). Default is "paynow" for compatibility with the existing
flow; "manual" is the off-platform alternative documented for schools
that don't have an electronic gateway relationship.
"""
from app.providers.payment_provider import (  # noqa: F401
    PaymentProvider,
    PaymentInitiateResult,
    PaymentStatus,
    PaymentProviderError,
)
from app.providers.paynow import PaynowProvider  # noqa: F401
from app.providers.manual import ManualHandoverProvider  # noqa: F401
from app.providers.registry import (  # noqa: F401
    get_provider_for_school,
    PROVIDER_REGISTRY,
)
