"""
EduZim API Gateway — Main Application
========================================
Full middleware pipeline:
  request_id → auth → rbac → tenant → rate_limit → proxy → error_normalize → metrics

Cookie-based refresh tokens:
  POST /api/v1/auth/login   → strips refresh_token from body, sets httpOnly cookie
  POST /api/v1/auth/refresh → reads cookie, injects into body before forwarding
  POST /api/v1/auth/logout  → clears the cookie

Endpoints:
  /health          — gateway health
  /ready           — downstream readiness (cached)
  /system/status   — service versions and circuit breaker state
  /metrics         — Prometheus metrics
  /api/v1/**       — proxied to downstream services
"""
import json as _json
import time
import uuid
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import get_settings
from app.routes import resolve_service, SERVICE_ROUTES
from app.middleware.stack import (
    extract_request_id, validate_jwt, check_rbac, extract_tenant,
    RateLimiter, get_rate_limit_key, normalize_error, MetricsCollector,
)
from app.proxy import GatewayProxy

logger = logging.getLogger(__name__)
settings = get_settings()

# Cookie settings for refresh-token
RT_COOKIE_NAME = "eduzim_rt"
RT_COOKIE_PATH = "/api/v1/auth"
RT_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days
RT_COOKIE_SAMESITE = "lax"

app = FastAPI(title=settings.APP_NAME, docs_url=None, redoc_url=None)

# CORS — allow frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
rate_limiter = RateLimiter()
metrics = MetricsCollector()
proxy = GatewayProxy()

# Readiness cache
_readiness_cache: dict = {}
_readiness_cache_time: float = 0


# ───────────── Health / Ready / Status / Metrics ─────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME, "version": "1.0.0"}


@app.get("/ready")
async def readiness():
    """Check downstream services with cached health probes."""
    global _readiness_cache, _readiness_cache_time

    now = time.time()
    if now - _readiness_cache_time < settings.READINESS_CACHE_TTL and _readiness_cache:
        return _readiness_cache

    # Collect unique services
    services = {}
    for prefix, (url_key, svc_name) in SERVICE_ROUTES.items():
        url = getattr(settings, url_key, None)
        if url and svc_name not in services:
            services[svc_name] = url

    results = {}
    for name, url in services.items():
        health_result = await proxy.check_health(url, name)
        results[name] = health_result.get("status", "unknown")

    all_healthy = all(s == "healthy" for s in results.values())
    response = {
        "status": "ready" if all_healthy else "degraded",
        "services": results,
    }

    _readiness_cache = response
    _readiness_cache_time = now
    return response


@app.get("/system/status")
async def system_status():
    """Admin view of services with circuit breaker states."""
    services = {}
    for prefix, (url_key, svc_name) in SERVICE_ROUTES.items():
        url = getattr(settings, url_key, None)
        if url and svc_name not in services:
            cb = proxy._circuit_breakers.get(svc_name)
            services[svc_name] = {
                "url": url,
                "circuit_breaker": cb.state.value if cb else "closed",
            }

    return {
        "gateway": {"version": "1.0.0", "service": settings.SERVICE_NAME},
        "services": services,
    }


@app.get("/metrics")
async def prometheus_metrics():
    return PlainTextResponse(content=metrics.to_prometheus(),
                             media_type="text/plain; charset=utf-8")


# ───────────── Gateway-local routes (must be registered BEFORE the catch-all) ─────────────
from app.api.diagnostics import router as diagnostics_router

app.include_router(diagnostics_router, prefix="/api/v1")


# ───────────── Gateway Catch-All ─────────────

@app.api_route("/api/v1/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway_proxy(request: Request, full_path: str):
    start = time.time()
    path = f"/api/v1/{full_path}"
    method = request.method

    # Block internal service-to-service paths from external access
    if "/internal/" in path:
        return JSONResponse(
            status_code=404,
            content=normalize_error(404, "Route not found", str(uuid.uuid4())),
        )

    # 1. Request ID
    request_id = extract_request_id(dict(request.headers))

    # 1b. Save-Data — propagate downstream so services can return slim payloads.
    # Header is a low-cost UX signal: when the client opts in (or the OS reports
    # a metered connection) we want every microservice in the chain to know.
    save_data = request.headers.get("save-data", "").strip().lower() == "on"

    # 2. Auth
    auth_header = request.headers.get("authorization", "")
    user_payload = validate_jwt(auth_header)

    # 3. RBAC
    allowed, reason = check_rbac(user_payload, method, path)
    if not allowed:
        status = 401 if "Authentication" in (reason or "") else 403
        metrics.record_request(path, status, (time.time() - start) * 1000)
        return JSONResponse(
            status_code=status,
            content=normalize_error(status, reason, request_id),
            headers={"X-Request-Id": request_id},
        )

    # 4. Tenant context
    tenant = extract_tenant(user_payload)

    # 5. Rate limiting
    body = None
    if method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = {}

    # --- Cookie-based refresh: inject refresh_token from cookie on refresh ---
    is_refresh = path == "/api/v1/auth/refresh" and method == "POST"
    if is_refresh:
        rt_cookie = request.cookies.get(RT_COOKIE_NAME)
        if rt_cookie:
            if body is None:
                body = {}
            body["refresh_token"] = rt_cookie

    rl_key, rl_limit, rl_window = get_rate_limit_key(path, user_payload, body)
    rl_allowed, rl_remaining, rl_reset = rate_limiter.check(rl_key, rl_limit, rl_window)

    if not rl_allowed:
        metrics.record_rate_limit()
        metrics.record_request(path, 429, (time.time() - start) * 1000)
        retry_after = max(1, rl_reset - int(time.time()))
        resp = normalize_error(429, f"Rate limit exceeded. Retry after {retry_after}s",
                               request_id)
        resp["error"]["details"]["limit"] = rl_limit
        resp["error"]["details"]["window_seconds"] = rl_window
        resp["error"]["details"]["retry_after"] = retry_after
        return JSONResponse(status_code=429, content=resp,
                            headers={"Retry-After": str(retry_after),
                                     "X-RateLimit-Remaining": "0",
                                     "X-Request-Id": request_id})

    # 6. Resolve downstream
    url_key, service_name = resolve_service(path)
    if not url_key:
        metrics.record_request(path, 404, (time.time() - start) * 1000)
        return JSONResponse(status_code=404,
                            content=normalize_error(404, "Route not found", request_id),
                            headers={"X-Request-Id": request_id})

    base_url = getattr(settings, url_key, None)
    if not base_url:
        metrics.record_request(path, 503, (time.time() - start) * 1000)
        return JSONResponse(status_code=503,
                            content=normalize_error(503, f"Service {service_name} not configured",
                                                     request_id, service_name),
                            headers={"X-Request-Id": request_id})

    downstream_url = f"{base_url}{path}"

    # 7. Forward (with tenant context injection, retry for GET, circuit breaker)
    result = await proxy.forward(
        method=method, url=downstream_url,
        headers=dict(request.headers), body=body,
        params=dict(request.query_params),
        request_id=request_id, service_name=service_name,
        tenant=tenant,
    )

    latency_ms = (time.time() - start) * 1000
    status_code = result["status_code"]

    # 8. Error normalization for downstream failures
    if result.get("error"):
        metrics.record_downstream_error(service_name)
        metrics.record_request(path, status_code, latency_ms)
        return JSONResponse(
            status_code=status_code,
            content=normalize_error(status_code, result.get("error"), request_id, service_name),
            headers={"X-Request-Id": request_id},
        )

    # 9. Metrics
    metrics.record_request(path, status_code, latency_ms)

    # 10. Structured log
    logger.info("gateway_request", extra={
        "request_id": request_id,
        "school_id": tenant.get("school_id"),
        "user_id": tenant.get("user_id"),
        "path": path, "method": method,
        "status": status_code,
        "latency_ms": f"{latency_ms:.1f}",
        "downstream_service": service_name,
    })

    # Forward response with headers
    resp_headers = {
        "X-Request-Id": request_id,
        "X-RateLimit-Remaining": str(rl_remaining),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cache-Control": "no-store",
        # Save-Data: caches must vary on this header so a low-bandwidth response
        # is never served to a regular client (and vice-versa).
        "Vary": "Save-Data, Accept-Encoding, Accept-Language",
    }
    if save_data:
        resp_headers["X-Save-Data"] = "on"

    if settings.ENFORCE_HTTPS:
        resp_headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains"

    response_body = result["body"]

    # --- Cookie-based refresh token handling ---
    is_login = path == "/api/v1/auth/login" and method == "POST"
    is_logout = path == "/api/v1/auth/logout" and method == "POST"

    response = JSONResponse(
        status_code=status_code,
        content=response_body,
        headers=resp_headers,
    )

    if is_login and status_code < 400 and isinstance(response_body, dict):
        data = response_body.get("data", response_body)
        rt = data.pop("refresh_token", None) if isinstance(data, dict) else None
        if rt:
            response = JSONResponse(
                status_code=status_code,
                content=response_body,
                headers=resp_headers,
            )
            response.set_cookie(
                key=RT_COOKIE_NAME,
                value=rt,
                max_age=RT_COOKIE_MAX_AGE,
                path=RT_COOKIE_PATH,
                httponly=True,
                samesite=RT_COOKIE_SAMESITE,
                secure=False,  # set True in production behind TLS
            )

    if is_refresh and status_code < 400 and isinstance(response_body, dict):
        data = response_body.get("data", response_body)
        rt = data.pop("refresh_token", None) if isinstance(data, dict) else None
        if rt:
            response = JSONResponse(
                status_code=status_code,
                content=response_body,
                headers=resp_headers,
            )
            response.set_cookie(
                key=RT_COOKIE_NAME,
                value=rt,
                max_age=RT_COOKIE_MAX_AGE,
                path=RT_COOKIE_PATH,
                httponly=True,
                samesite=RT_COOKIE_SAMESITE,
                secure=False,
            )

    if is_logout:
        response.delete_cookie(key=RT_COOKIE_NAME, path=RT_COOKIE_PATH)

    return response
