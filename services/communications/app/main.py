from app.config import get_settings
settings = get_settings()

import sys
sys.path.insert(0, "../../shared")

try:
    from eduzim_shared.app_factory import create_app
    app = create_app(title=settings.APP_NAME, service_name=settings.SERVICE_NAME, debug=settings.DEBUG)
except ImportError:
    from fastapi import FastAPI
    app = FastAPI(title=settings.APP_NAME)
    @app.get("/health")
    def health():
        return {"status": "healthy", "service": settings.SERVICE_NAME}

from app.api.routes import router
app.include_router(router, prefix="/api/v1")

from app.api.diagnostics import router as diagnostics_router
app.include_router(diagnostics_router)

from app.api.whatsapp_webhook import router as whatsapp_router
app.include_router(whatsapp_router, prefix="/api/v1")

# Phase 9 follow-up — admin audit-log browse endpoint.
from app.api.audit_routes import router as audit_router
app.include_router(audit_router, prefix="/api/v1")

# Phase 11b / T-011 — parent-teacher messaging.
from app.api.messaging_routes import router as messaging_router
app.include_router(messaging_router, prefix="/api/v1")

# Phase 11b / T-008 — file attachments.
from app.api.attachment_routes import router as attachment_router
app.include_router(attachment_router, prefix="/api/v1")

# Phase 12c — notification provider config + provider-aware dispatch.
from app.api.notification_config_routes import router as notification_config_router
app.include_router(notification_config_router, prefix="/api/v1")

# Make sure the WhatsApp model is registered with Base before any
# `create_all` (used by tests and dev bootstraps) sweeps the metadata.
from app.models import whatsapp as _whatsapp_models  # noqa: F401
# Phase 9 follow-up — audit table.
from app.models import audit as _audit_models  # noqa: F401
# Phase 11b — messaging tables.
from app.models import messaging as _messaging_models  # noqa: F401
# Phase 11b — attachments table.
from app.models import attachment as _attachment_models  # noqa: F401
# Phase 12c — notification provider config table.
from app.models import notification_config as _notification_config_models  # noqa: F401
