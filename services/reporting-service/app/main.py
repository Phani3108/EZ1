"""Reporting Service — PH2-11.

This module USED to be a FastAPI app with /api/v1/reports/* endpoints.
PH2-11 moved the read endpoints into the academics service and converted
the reporting-service container into a pure Kafka consumer. The container
CMD now runs `python -m app.consumer`, not uvicorn.

This stub stays in place so that anything still importing `app.main:app`
(local dev, lingering CI lines, the existing alembic env that pulls
`from app.main import app` in a few revisions) gets a minimal FastAPI
instance exposing only /health. It does NOT mount /api/v1/reports/*
anymore — those return 404 by design.

For the actual long-running process, see `app/consumer.py`. For the CLI
tools that replace POST /reports/consume and POST /reports/rebuild, see
`services/reporting-service/cli/`.
"""
from app.config import get_settings

settings = get_settings()

import sys

sys.path.insert(0, "../../shared")

try:
    from eduzim_shared.app_factory import create_app
    app = create_app(
        title=settings.APP_NAME,
        service_name=settings.SERVICE_NAME,
        debug=settings.DEBUG,
    )
except ImportError:
    from fastapi import FastAPI
    app = FastAPI(title=settings.APP_NAME)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "mode": "consumer-only-since-ph2-11",
    }


@app.get("/health/phase")
def health_phase():
    return {
        "service": settings.SERVICE_NAME,
        "version": "0.6.0-ph2-11",
        "phase": (
            "PH2-11 — HTTP routes retired. Reads now served by academics; "
            "this container runs the Kafka consumer at app.consumer.run()."
        ),
    }
