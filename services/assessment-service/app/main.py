"""
EduZim Assessment Service — Main Application
"""
from fastapi import FastAPI

try:
    from eduzim_shared.app_factory import create_app
except ImportError:
    create_app = None

from app.config import get_settings

settings = get_settings()


def build_app() -> FastAPI:
    if create_app:
        application = create_app(
            title=settings.APP_NAME,
            service_name=settings.SERVICE_NAME,
        )
    else:
        application = FastAPI(title=settings.APP_NAME)

        @application.get("/health")
        def health():
            return {"status": "healthy", "service": settings.SERVICE_NAME}

    from app.api.routes import router
    application.include_router(router, prefix="/api/v1")
    return application


app = build_app()
