"""
EduZim Base App Factory
========================
Creates a pre-configured FastAPI app with standard middleware and handlers.

Usage:
    from eduzim_shared.app_factory import create_app

    app = create_app(
        title="EduZim School Service",
        service_name="school-service",
        version="1.0.0",
    )
"""

from fastapi import FastAPI
from eduzim_shared.logging import setup_logging
from eduzim_shared.errors import register_exception_handlers
from eduzim_shared.middleware import RequestIdMiddleware


def create_app(
    title: str,
    service_name: str,
    version: str = "1.0.0",
    description: str = "",
    debug: bool = False,
) -> FastAPI:
    """
    Create a FastAPI app with EduZim standard configuration.

    Includes:
    - Structured JSON logging
    - X-Request-Id middleware
    - Standardized error handlers
    - Health check endpoint
    - OpenAPI docs at /docs
    """
    # Setup logging first
    setup_logging(service_name=service_name, json_output=not debug)

    app = FastAPI(
        title=title,
        description=description or f"EduZim {title}",
        version=version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add middleware
    app.add_middleware(RequestIdMiddleware)

    # Register error handlers
    register_exception_handlers(app, service_name=service_name)

    # Health endpoint
    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "healthy", "service": service_name, "version": version}

    @app.get("/", tags=["Health"])
    def root():
        return {"service": service_name, "status": "running", "version": version}

    return app
