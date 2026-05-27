"""OpenTelemetry tracing for EduZim services (INFRA-008, Phase 6).

Wires distributed tracing across services. The trace propagates from
the gateway through each downstream service via W3C Trace Context
headers (`traceparent`, `tracestate`) — already injected by the
gateway's existing `X-Request-Id` middleware boundary.

Backend: OTLP over gRPC to Tempo (lighter than Jaeger; can re-emit to
Jaeger format if needed). Configured via env:

    OTEL_EXPORTER_OTLP_ENDPOINT     e.g. http://tempo:4317 (default)
    OTEL_TRACES_SAMPLER             default `parentbased_traceidratio`
    OTEL_TRACES_SAMPLER_ARG         sample rate, default 0.1 (10%)
    EDUZIM_TRACING_ENABLED          true|false (default false)

When EDUZIM_TRACING_ENABLED=false, `install(...)` is a no-op — no
imports of the opentelemetry SDK, no overhead. Production deployments
flip the env var.

Per-service instrumentation:
  * FastAPI — auto-instruments every route handler.
  * HTTPX   — auto-instruments outbound calls (academics → finance, etc.).
  * SQLAlchemy — auto-instruments DB queries.
  * Logging — adds trace_id / span_id to every log record.

Sentry coordinates: ADR 007 sets `send_default_pii=False`. The same
default holds for traces — span attributes must not include PII
(student names, parent phones). The auto-instrumentation respects this
because FastAPI's default span attributes are method / path / status
only, none of which carry PII unless we explicitly add it.
"""
from __future__ import annotations

import logging
import os
from typing import Optional


_logger = logging.getLogger(__name__)
_INSTALLED = False  # idempotency guard


def is_enabled() -> bool:
    return os.environ.get("EDUZIM_TRACING_ENABLED", "false").lower() == "true"


def install(
    *,
    service_name: str,
    app=None,
    sqlalchemy_engine=None,
) -> None:
    """Install OpenTelemetry instrumentation for this process.

    Parameters
    ----------
    service_name : str
        Used as the `service.name` resource attribute — Tempo / Jaeger
        groups spans by it.
    app : FastAPI, optional
        If provided, auto-instruments every route.
    sqlalchemy_engine : Engine, optional
        If provided, auto-instruments DB queries on this engine.

    Idempotent. Calling twice with the same service_name is a no-op.

    No-op when EDUZIM_TRACING_ENABLED is unset / false.
    """
    global _INSTALLED
    if not is_enabled():
        _logger.debug("tracing disabled (EDUZIM_TRACING_ENABLED != true)")
        return
    if _INSTALLED:
        _logger.debug("tracing already installed; skip")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        _logger.warning(
            "tracing.install: opentelemetry packages not installed (%s); skip",
            e,
        )
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")

    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.environ.get("SERVICE_VERSION", "unknown"),
        "deployment.environment": os.environ.get("ENVIRONMENT", "dev"),
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _logger.info(
        "tracing.install: service=%s endpoint=%s",
        service_name, endpoint,
    )

    # Instrument FastAPI, HTTPX, SQLAlchemy when their packages are
    # importable. Each is best-effort — if a service doesn't use one,
    # the import simply fails and we skip.
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except ImportError:
            _logger.debug("FastAPI instrumentor not installed")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        _logger.debug("HTTPX instrumentor not installed")

    if sqlalchemy_engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument(engine=sqlalchemy_engine)
        except ImportError:
            _logger.debug("SQLAlchemy instrumentor not installed")

    # Logging integration — adds trace_id / span_id to every log record
    # via the LoggingInstrumentor. The shared JSON formatter (see
    # eduzim_shared.logging) picks these up automatically.
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=False)
    except ImportError:
        _logger.debug("Logging instrumentor not installed")

    _INSTALLED = True


def shutdown() -> None:
    """Flush any in-flight spans. Called from app_factory's lifespan."""
    if not _INSTALLED:
        return
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception as e:  # pragma: no cover — defensive shutdown
        _logger.warning("tracing.shutdown failed: %s", e)
