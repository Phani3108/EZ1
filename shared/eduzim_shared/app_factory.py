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

INFRA-022 (Phase 5): the factory now installs a startup/shutdown lifespan
that flushes the Kafka producer (if the service registered one) and waits a
short grace period for in-flight requests to drain. Services can hook
extra cleanup via the ``shutdown_hooks`` parameter.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, List, Optional

from fastapi import FastAPI
from eduzim_shared.logging import setup_logging
from eduzim_shared.errors import register_exception_handlers
from eduzim_shared.middleware import RequestIdMiddleware


def _maybe_init_sentry(service_name: str, version: str) -> None:
    """INFRA-010 (Phase 6): wire Sentry error tracking when SENTRY_DSN is set.

    Off by default (empty DSN). Production deploys set SENTRY_DSN via the
    secrets manager. Tests never set it so this is a no-op in CI.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN set but sentry-sdk not installed; skipping init"
        )
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "dev"),
        release=f"{service_name}@{version}",
        send_default_pii=False,  # per ADR 007 — minimal PII
    )
    logging.getLogger(__name__).info(
        "Sentry initialized for %s @ %s", service_name, version,
    )


ShutdownHook = Callable[[], "Awaitable[None] | None"]

_logger = logging.getLogger(__name__)


async def _run_hook(hook: ShutdownHook, name: str) -> None:
    try:
        result = hook()
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:  # pragma: no cover — defensive shutdown
        _logger.error("Shutdown hook %s failed: %s", name, e)


def _flush_kafka_singleton() -> None:
    """Attempt to flush a process-wide Kafka producer if one was created.

    Services that use ``eduzim_shared.kafka.producer.EduZimProducer`` can
    register their producer with this module so the lifespan can flush it
    on SIGTERM. If no producer is registered (or Kafka isn't enabled), this
    is a no-op.
    """
    try:
        from eduzim_shared.kafka.producer import _registered_producers
    except Exception:
        return
    for label, prod in list(_registered_producers.items()):
        try:
            remaining = prod.flush(timeout=5.0)
            _logger.info("Flushed Kafka producer %s (queue_remaining=%s)",
                         label, remaining)
        except Exception as e:
            _logger.error("Kafka flush failed for %s: %s", label, e)


def create_app(
    title: str,
    service_name: str,
    version: str = "1.0.0",
    description: str = "",
    debug: bool = False,
    shutdown_hooks: Optional[List[ShutdownHook]] = None,
    shutdown_grace_seconds: float = 3.0,
    enable_metrics: bool = True,
    enable_tracing: bool = True,
) -> FastAPI:
    """
    Create a FastAPI app with EduZim standard configuration.

    Includes:
    - Structured JSON logging
    - X-Request-Id middleware
    - Standardized error handlers
    - Health check endpoint
    - OpenAPI docs at /docs
    - INFRA-022: graceful shutdown lifespan
    - INFRA-007 (Phase 6): /metrics endpoint with Prometheus exposition
    - INFRA-008 (Phase 6): OpenTelemetry tracing (no-op without env)

    Parameters
    ----------
    shutdown_hooks : list of callables (sync or async), optional
        Run during shutdown BEFORE the Kafka flush + grace sleep. Each
        hook is awaited if it returns a coroutine. Exceptions are logged
        but do not abort shutdown.
    shutdown_grace_seconds : float
        How long to sleep AFTER hooks/Kafka flush to let in-flight HTTP
        requests finish. Tuned for typical request lifetimes (< 3s); bump
        for services with long-tail endpoints.
    enable_metrics : bool
        Install Prometheus /metrics. Default True. Set False for one-off
        services that should not be scraped (e.g. the reporting consumer
        shell that only exposes /health).
    enable_tracing : bool
        Wire OpenTelemetry tracing if EDUZIM_TRACING_ENABLED=true at
        runtime. Default True — the runtime env decides; this flag is
        for tests that need to opt out entirely.
    """
    # Setup logging first
    setup_logging(service_name=service_name, json_output=not debug)

    # INFRA-010 (Phase 6): Sentry — no-op if SENTRY_DSN unset.
    _maybe_init_sentry(service_name=service_name, version=version)

    hooks: List[ShutdownHook] = list(shutdown_hooks or [])

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _logger.info("Service %s starting up (version=%s)", service_name, version)
        try:
            yield
        finally:
            _logger.info("Service %s shutting down — running %d hooks",
                         service_name, len(hooks))
            for i, hook in enumerate(hooks):
                await _run_hook(hook, name=f"{service_name}-hook-{i}")
            _flush_kafka_singleton()
            # Flush tracing spans before the grace sleep so they make it
            # to the collector even on a hard SIGKILL after grace.
            if enable_tracing:
                try:
                    from eduzim_shared import tracing as _tracing
                    _tracing.shutdown()
                except ImportError:
                    pass
            if shutdown_grace_seconds > 0:
                _logger.info("Draining in-flight requests for %.1fs",
                             shutdown_grace_seconds)
                await asyncio.sleep(shutdown_grace_seconds)
            _logger.info("Service %s shutdown complete", service_name)

    app = FastAPI(
        title=title,
        description=description or f"EduZim {title}",
        version=version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(RequestIdMiddleware)

    # Register error handlers
    register_exception_handlers(app, service_name=service_name)

    # INFRA-007 (Phase 6): Prometheus /metrics. Mounted BEFORE the
    # route definitions below so the metrics middleware sees them all.
    if enable_metrics:
        try:
            from eduzim_shared import metrics as _metrics
            _metrics.install(app, service_name=service_name)
        except ImportError as e:
            _logger.warning("metrics install skipped: %s", e)

    # INFRA-008 (Phase 6): OpenTelemetry tracing. No-op unless
    # EDUZIM_TRACING_ENABLED=true at runtime.
    if enable_tracing:
        try:
            from eduzim_shared import tracing as _tracing
            _tracing.install(service_name=service_name, app=app)
        except ImportError as e:
            _logger.warning("tracing install skipped: %s", e)

    # Health endpoint
    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "healthy", "service": service_name, "version": version}

    @app.get("/", tags=["Health"])
    def root():
        return {"service": service_name, "status": "running", "version": version}

    return app
