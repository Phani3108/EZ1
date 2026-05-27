from app.config import get_settings

settings = get_settings()

# Fail closed if dev JWT secret is used outside DEBUG.
_DEV_JWT_SECRET = "dev-jwt-secret-change-in-production"
if not settings.DEBUG and settings.JWT_SECRET_KEY == _DEV_JWT_SECRET:
    raise RuntimeError(
        "Refusing to start: JWT_SECRET_KEY is set to the well-known development value "
        "while DEBUG=False. Set a strong JWT_SECRET_KEY environment variable."
    )

# Use shared app factory
import sys
sys.path.insert(0, "../../shared")

try:
    from eduzim_shared.app_factory import create_app
    app = create_app(
        title=settings.APP_NAME,
        service_name=settings.SERVICE_NAME,
        description=(
            "EduZim Auth Service — JWT authentication with access/refresh tokens, "
            "multi-tenant user management (school_id scoped), RBAC with roles and "
            "permissions, login audit logging, and Kafka event publishing."
        ),
        debug=settings.DEBUG,
    )
except ImportError:
    # Fallback if shared lib not installed
    from fastapi import FastAPI
    app = FastAPI(title=settings.APP_NAME, docs_url="/docs", redoc_url="/redoc")

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "healthy", "service": settings.SERVICE_NAME}

    @app.get("/", tags=["Health"])
    def root():
        return {"service": settings.SERVICE_NAME, "status": "running", "version": "1.0.0"}

# Register routes
from app.api.auth import router as auth_router
from app.api.rbac import router as rbac_router
from app.api.forgot_password import router as forgot_router
from app.api.preferences import router as preferences_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(rbac_router, prefix="/api/v1")
app.include_router(forgot_router, prefix="/api/v1")
app.include_router(preferences_router, prefix="/api/v1")
