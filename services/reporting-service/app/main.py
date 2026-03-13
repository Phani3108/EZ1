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
from app.api.exports import router as exports_router
app.include_router(router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
