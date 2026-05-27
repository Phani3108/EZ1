"""Phase 12c — notification provider abstraction.

Same shape as the finance PaymentProvider abstraction (DEC-004
revised): we don't run our own SMS gateway / push fleet / email
deliverability stack. Schools (or the platform default) pick a
provider per channel, and the application code talks to a uniform
`NotificationProvider` interface.

Four channels:
  - SMS  → AfricasTalking (default), ManualHandover
  - Push → FCM             (default), ManualHandover
  - Email → SendGrid        (default), ManualHandover
  - WhatsApp → Meta Cloud   (default), ManualHandover

ManualHandover means: we log the intent (an outbox row), the school's
admin team sends the message externally, and the row gets marked
delivered once they confirm. Useful for first-month-of-pilot schools
who haven't activated a paid SMS/email plan yet.
"""
from app.providers.notification_provider import (  # noqa: F401
    NotificationProvider,
    NotificationResult,
    NotificationStatus,
    NotificationProviderError,
)
from app.providers.registry import (  # noqa: F401
    get_provider_for_school_channel,
    PROVIDER_REGISTRY,
    SUPPORTED_CHANNELS,
)
