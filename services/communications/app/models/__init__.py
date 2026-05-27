"""Communication service ORM models — re-exported so `Base.metadata`
includes every table before bootstrappers/tests call `create_all`."""
from app.models.communication import Announcement, NotificationOutbox  # noqa: F401
from app.models.idempotency import IdempotencyKey  # noqa: F401
from app.models.whatsapp import WhatsAppMessage  # noqa: F401
from app.models.messaging import MessageThread, Message  # noqa: F401
from app.models.attachment import Attachment  # noqa: F401
from app.models.notification_config import SchoolNotificationConfig  # noqa: F401
