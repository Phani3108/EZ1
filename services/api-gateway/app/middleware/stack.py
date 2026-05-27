"""
Gateway Middleware Stack
=========================
1. request_id — generates/propagates X-Request-Id
2. auth — JWT validation, extracts user context
3. rbac — checks permission against RBAC map
4. tenant — enforces school_id from token only (prevents spoofing)
5. rate_limit — Redis token bucket per user/device
6. error_normalizer — standardizes downstream error responses
7. metrics — Prometheus counters and histograms
"""
import time
import uuid
import logging
from datetime import datetime, timezone

from jose import jwt, JWTError
from app.config import get_settings
from app.routes import get_required_permission

logger = logging.getLogger(__name__)
settings = get_settings()


# ───────────── 1. Request ID ─────────────

def extract_request_id(headers: dict) -> str:
    """Extract or generate X-Request-Id."""
    return headers.get("x-request-id") or headers.get("X-Request-Id") or str(uuid.uuid4())


# ───────────── 2. Auth (JWT) ─────────────

def validate_jwt(auth_header: str) -> dict | None:
    """Validate a JWT Bearer token.

    Returns the decoded payload on success, or ``None`` on any failure:
      * missing/blank Authorization header
      * not a ``Bearer`` scheme or empty token
      * signature/expiry/algorithm errors
      * token ``type`` other than ``access``

    NOTE — there is NO dev-mode bypass. Every request hitting the gateway
    must carry a valid access token. For local development, issue a real
    token via ``POST /api/v1/auth/login`` against the auth-service (or use
    ``scripts/dev-seed.sh`` to seed credentials).
    """
    if not auth_header or not isinstance(auth_header, str):
        return None
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e, extra={"token_preview": token[:10]})
        return None
    except Exception as e:  # pragma: no cover — defensive
        logger.error("Unexpected JWT error: %s", e)
        return None

    if payload.get("type") != "access":
        logger.warning("JWT type mismatch: %s (expected 'access')", payload.get("type"))
        return None
    return payload


# ───────────── 3. RBAC ─────────────

def check_rbac(user_payload: dict, method: str, path: str) -> tuple:
    """Check RBAC permission. Returns (allowed: bool, reason: str)."""
    required = get_required_permission(method, path)

    if required is None:
        return True, None  # Public endpoint

    if user_payload is None:
        return False, "Authentication required"

    if required == "authenticated":
        return True, None  # Just needs a valid token

    # Check user permissions (from token claims)
    user_permissions = set(user_payload.get("permissions", []))
    user_role = user_payload.get("role", "")

    # Admin has all permissions
    if user_role == "admin":
        return True, None

    if required in user_permissions:
        return True, None

    return False, f"Permission '{required}' required"


# ───────────── 4. Tenant Enforcement ─────────────

def extract_tenant(user_payload: dict) -> dict:
    """Extract tenant context from JWT. NEVER from request params.

    PH3 / BUG-007: the returned dict gains `roles` (list) and
    `permissions` (list) — downstream services now read identity entirely
    from gateway-injected headers (eduzim_shared.auth.ActorContext), so
    they need the full role + permission set, not just a single role
    string.

    `role` is kept for back-compat with the existing X-User-Role header.
    """
    if not user_payload:
        return {}
    # JWTs may carry either `roles` (PH3 canonical, list of strings) or
    # the legacy `role` (single string). Normalise to a list so the
    # gateway forwards a consistent X-User-Roles header.
    roles_field = user_payload.get("roles")
    if isinstance(roles_field, list):
        roles = [str(r) for r in roles_field if r]
    elif user_payload.get("role"):
        roles = [str(user_payload["role"])]
    else:
        roles = []

    perms_field = user_payload.get("permissions") or []
    if isinstance(perms_field, list):
        permissions = [str(p) for p in perms_field if p]
    else:
        permissions = []

    return {
        "school_id": user_payload.get("school_id"),
        "user_id": user_payload.get("sub"),
        "role": user_payload.get("role") or (roles[0] if roles else None),
        "roles": roles,
        "permissions": permissions,
    }


# ───────────── 5. Rate Limiter ─────────────
#
# BUG-006 (Phase 1) — Redis-backed token bucket. The previous implementation
# kept an in-memory dict as a fallback when no Redis client was supplied; that
# state was lost on every gateway restart, so a process bounce opened a
# wide-open brute-force window for the duration of the next request burst.
# This implementation requires Redis. Tests pass a FakeRedis instance with
# the same `pipeline().incr().expire().execute()` shape we actually use.

class RateLimiter:
    """Token bucket rate limiter backed by Redis.

    Construction REQUIRES a redis_client (or a compatible fake). Callers must
    arrange for a Redis client to exist before constructing — the gateway
    main.py wires this from ``settings.REDIS_URL`` when ``REDIS_ENABLED`` is
    true. Tests inject a FakeRedis. There is no in-memory fallback.
    """

    def __init__(self, redis_client):
        if redis_client is None:
            raise ValueError(
                "RateLimiter requires a redis_client (BUG-006: in-memory "
                "fallback removed). Pass a real Redis client or a test fake "
                "supporting .pipeline().incr().expire().execute()."
            )
        self.redis = redis_client

    def check(self, key: str, limit: int, window: int) -> tuple:
        """Returns (allowed: bool, remaining: int, reset_at: int)."""
        now = int(time.time())
        window_start = now - (now % window)
        bucket_key = f"rl:{key}:{window_start}"

        pipe = self.redis.pipeline()
        pipe.incr(bucket_key)
        pipe.expire(bucket_key, window + 10)
        results = pipe.execute()

        count = results[0]
        remaining = max(0, limit - count)
        reset_at = window_start + window
        return count <= limit, remaining, reset_at


def get_rate_limit_key(path: str, user_payload: dict, body: dict = None,
                       ip: str = None) -> tuple:
    """Determine the rate-limit key for this request.

    Composite strategy (per the Phase-1 decision):
      * Unauthenticated `/auth/login`, `/auth/forgot-password`, `/auth/refresh`
        → keyed by IP (`login:<ip>`). Prevents account-discovery + brute-force
        from a single source. Limit: LOGIN_RATE_LIMIT.
      * Authenticated attendance sync (`/attendance/sync`) → keyed by
        `school_id:device_id` (or `school_id:user_id` if no device). Limit:
        SYNC_RATE_LIMIT.
      * Other authenticated routes → keyed by `school_id:user_id`.
      * Other unauthenticated routes → keyed by IP (`anon:<ip>`). A school
        behind one NAT shares the bucket, which is OK for genuinely
        unauthenticated traffic (almost none after Phase 1).

    Returns (key, limit, window_seconds).
    """
    school_id = user_payload.get("school_id", "unknown") if user_payload else None
    user_id = user_payload.get("sub", "unknown") if user_payload else None
    ip_key = ip or "unknown-ip"

    # Login / refresh / forgot-password — keyed by IP (brute-force defence).
    # Stricter limit per LOGIN_RATE_LIMIT.
    if ("/auth/login" in path
            or "/auth/forgot-password" in path
            or "/auth/refresh" in path):
        return f"login:{ip_key}", settings.LOGIN_RATE_LIMIT, settings.RATE_LIMIT_WINDOW

    # Attendance sync — per-device (or per-user when device missing).
    if "/attendance/sync" in path and body:
        device_id = body.get("device_id") or user_id or "no-device"
        return (
            f"{school_id or 'anon'}:{device_id}",
            settings.SYNC_RATE_LIMIT,
            settings.RATE_LIMIT_WINDOW,
        )

    # Authenticated default — per (school, user).
    if user_payload:
        return (
            f"{school_id}:{user_id}",
            settings.DEFAULT_RATE_LIMIT,
            settings.RATE_LIMIT_WINDOW,
        )

    # Unauthenticated default — per IP.
    return f"anon:{ip_key}", settings.DEFAULT_RATE_LIMIT, settings.RATE_LIMIT_WINDOW


# ───────────── 6. Error Normalizer ─────────────

def normalize_error(status_code: int, detail: str = None,
                    request_id: str = None, downstream_service: str = None) -> dict:
    """Standardized error response."""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    return {
        "error": {
            "code": code_map.get(status_code, "UNKNOWN_ERROR"),
            "message": detail or f"HTTP {status_code}",
            "details": {"downstream_service": downstream_service} if downstream_service else {},
            "request_id": request_id or str(uuid.uuid4()),
        }
    }


# ───────────── 7. Metrics Collector ─────────────

class MetricsCollector:
    """Simple in-memory metrics for Prometheus scraping."""

    HISTOGRAM_BUCKETS = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

    def __init__(self):
        self.request_count: dict = {}       # {route:status → count}
        self.latency_sum: dict = {}         # {route → total_ms}
        self.latency_count: dict = {}       # {route → count}
        self.latency_buckets: dict = {}     # {route:le → count}
        self.downstream_errors: dict = {}   # {service → count}
        self.rate_limit_blocks: int = 0

    def record_request(self, route: str, status: int, latency_ms: float):
        key = f"{route}:{status}"
        self.request_count[key] = self.request_count.get(key, 0) + 1
        self.latency_sum[route] = self.latency_sum.get(route, 0) + latency_ms
        self.latency_count[route] = self.latency_count.get(route, 0) + 1
        for bucket in self.HISTOGRAM_BUCKETS:
            bk = f"{route}:{bucket}"
            if latency_ms <= bucket:
                self.latency_buckets[bk] = self.latency_buckets.get(bk, 0) + 1

    def record_downstream_error(self, service: str):
        self.downstream_errors[service] = self.downstream_errors.get(service, 0) + 1

    def record_rate_limit(self):
        self.rate_limit_blocks += 1

    def to_prometheus(self) -> str:
        lines = [
            "# HELP gateway_requests_total Total HTTP requests by route and status",
            "# TYPE gateway_requests_total counter",
        ]
        for key, count in sorted(self.request_count.items()):
            route, status = key.rsplit(":", 1)
            lines.append(f'gateway_requests_total{{route="{route}",status="{status}"}} {count}')

        lines.extend([
            "# HELP gateway_request_duration_ms Request duration histogram in ms",
            "# TYPE gateway_request_duration_ms histogram",
        ])
        routes_seen = set()
        for key in sorted(self.latency_buckets.keys()):
            route, le = key.rsplit(":", 1)
            routes_seen.add(route)
            lines.append(f'gateway_request_duration_ms_bucket{{route="{route}",le="{le}"}} {self.latency_buckets[key]}')
        for route in sorted(routes_seen):
            total = self.latency_sum.get(route, 0)
            count = self.latency_count.get(route, 0)
            lines.append(f'gateway_request_duration_ms_sum{{route="{route}"}} {total:.1f}')
            lines.append(f'gateway_request_duration_ms_count{{route="{route}"}} {count}')

        lines.extend([
            "# HELP gateway_downstream_errors_total Downstream service errors",
            "# TYPE gateway_downstream_errors_total counter",
        ])
        for svc, count in sorted(self.downstream_errors.items()):
            lines.append(f'gateway_downstream_errors_total{{service="{svc}"}} {count}')

        lines.extend([
            "# HELP gateway_rate_limit_blocks_total Rate limit blocks",
            "# TYPE gateway_rate_limit_blocks_total counter",
            f"gateway_rate_limit_blocks_total {self.rate_limit_blocks}",
        ])
        return "\n".join(lines) + "\n"
