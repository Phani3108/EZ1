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

# Make sure the WhatsApp model is registered with Base before any
# `create_all` (used by tests and dev bootstraps) sweeps the metadata.
from app.models import whatsapp as _whatsapp_models  # noqa: F401
