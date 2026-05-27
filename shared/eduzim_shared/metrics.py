"""Per-service Prometheus metrics (INFRA-007 follow-up, Phase 6).

Adds a `/metrics` endpoint to every FastAPI app built via the shared
`app_factory.create_app()`. The endpoint serves Prometheus exposition
format with three standard signals per service:

  * `eduzim_http_requests_total{service, route, method, status}` (counter)
  * `eduzim_http_request_duration_seconds{service, route, method}` (histogram)
  * `eduzim_http_in_flight_requests{service}` (gauge)

The gateway keeps its own `gateway_*` metrics (defined inline in
middleware/stack.py). This module is for the four downstream services
+ the reporting consumer.

Implementation chooses `prometheus_client` (the official client) over
`prometheus-fastapi-instrumentator` (popular wrapper) because:
  * One fewer dep to vet.
  * Explicit middleware is easier to reason about than auto-magic.
  * `prometheus_client` is already in our dep chain transitively.

Cardinality control: `route` is the URL TEMPLATE (e.g. `/students/{id}`),
not the raw path. FastAPI exposes this via `request.scope['route'].path`
when routing matched. Unmatched paths are bucketed as `unmatched` to
prevent cardinality blow-up from random 404 probes.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import Response


# We DON'T initialise a default registry at import time — each FastAPI
# app gets its own to avoid cross-test bleed. The factory builds the
# metrics + middleware + endpoint as a unit.


def install(
    app: FastAPI,
    *,
    service_name: str,
    endpoint: str = "/metrics",
    histogram_buckets: tuple[float, ...] | None = None,
) -> None:
    """Install metrics middleware + /metrics endpoint on the given app.

    Parameters
    ----------
    app : FastAPI
        Target app (typically the one returned by `create_app`).
    service_name : str
        Label value applied to every metric. Lets a single Prometheus
        scrape across multiple services group cleanly.
    endpoint : str
        Path to mount the exposition format on. Default `/metrics`.
    histogram_buckets : tuple of floats, optional
        Latency bucket boundaries in SECONDS (Prometheus convention).
        Default targets the SLO buckets we care about: 5ms→10s.
    """
    from prometheus_client import (
        CollectorRegistry, Counter, Gauge, Histogram, generate_latest,
        CONTENT_TYPE_LATEST,
    )

    buckets = histogram_buckets or (
        0.005, 0.010, 0.025, 0.050, 0.100, 0.250,
        0.500, 1.0, 2.5, 5.0, 10.0,
    )

    registry = CollectorRegistry()

    requests_total = Counter(
        "eduzim_http_requests_total",
        "Total HTTP requests by service, route, method, status",
        ["service", "route", "method", "status"],
        registry=registry,
    )
    request_duration = Histogram(
        "eduzim_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["service", "route", "method"],
        buckets=buckets,
        registry=registry,
    )
    in_flight = Gauge(
        "eduzim_http_in_flight_requests",
        "HTTP requests currently being processed",
        ["service"],
        registry=registry,
    )

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next: Callable):
        # Skip the metrics endpoint itself to avoid recursive timing /
        # cardinality blow-up from Prometheus's own scrapes.
        if request.url.path == endpoint:
            return await call_next(request)

        in_flight.labels(service=service_name).inc()
        start = time.perf_counter()
        status = "500"  # default — overwritten on success
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = _route_template(request)
            method = request.method
            requests_total.labels(
                service=service_name, route=route, method=method, status=status,
            ).inc()
            request_duration.labels(
                service=service_name, route=route, method=method,
            ).observe(elapsed)
            in_flight.labels(service=service_name).dec()

    @app.get(endpoint, include_in_schema=False)
    def metrics_endpoint():
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )


def _route_template(request: Request) -> str:
    """Return the matched route TEMPLATE (`/students/{id}`) or `unmatched`.

    Using the template prevents cardinality blow-up from per-resource
    metrics that would otherwise emit one time series per UUID seen.
    """
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    # No route matched (404 / 405 / pre-routing error) — bucket together.
    return "unmatched"
