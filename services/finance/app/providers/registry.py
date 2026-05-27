"""PaymentProvider registry.

Resolves a school's configured provider from `school_payment_config`
(see model). When the school hasn't picked one, the system default is
"paynow" for compatibility with the existing flow.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

from app.providers.payment_provider import PaymentProvider
from app.providers.paynow import PaynowProvider
from app.providers.manual import ManualHandoverProvider


# Provider name → instance. The registry is small and immutable —
# adding a provider means importing it and registering at module
# load.
PROVIDER_REGISTRY: dict[str, PaymentProvider] = {
    "paynow": PaynowProvider(),
    "manual": ManualHandoverProvider(),
}


DEFAULT_PROVIDER_NAME = "paynow"


def get_provider_for_school(
    db: "Session", school_id: uuid.UUID,
) -> PaymentProvider:
    """Return the PaymentProvider configured for `school_id`. Falls
    back to the system default when the school has no preference."""
    from app.models.payment_config import SchoolPaymentConfig
    row = (
        db.query(SchoolPaymentConfig)
        .filter(SchoolPaymentConfig.school_id == school_id)
        .first()
    )
    name = (row.provider_name if row else DEFAULT_PROVIDER_NAME).lower()
    return PROVIDER_REGISTRY.get(name) or PROVIDER_REGISTRY[DEFAULT_PROVIDER_NAME]
