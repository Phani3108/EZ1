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

from app import models as _models  # noqa: F401  ensures Base.metadata sees every table
from app.api.routes import router
from app.api.payments import router as payments_router
from app.api.diagnostics import router as diagnostics_router
# Phase 9 follow-up — admin browse endpoint for the per-service audit log.
from app.api.audit_routes import router as audit_router
# Phase 12b — provider-aware payment config + initiate + manual confirm.
from app.api.payment_config_routes import router as payment_config_router
# Phase 14 / M-003 — Ministry cross-school fees aggregation (read-only).
from app.api.ministry_routes import router as ministry_router
app.include_router(router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(payment_config_router, prefix="/api/v1")
app.include_router(ministry_router, prefix="/api/v1")
# NOTE: diagnostics is mounted WITHOUT the /api/v1 prefix because the gateway
# blocks any external `/internal/*` traffic. Only the gateway can call it.
app.include_router(diagnostics_router)
