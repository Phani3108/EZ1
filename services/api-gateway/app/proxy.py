"""
Gateway Proxy — Downstream Request Forwarding
================================================
- Forwards with timeout
- Propagates X-Request-Id, X-User-Id, X-School-Id, X-User-Roles,
  X-Permissions, X-User-Role (legacy), X-Gateway-Token
  (PH3 / BUG-007: downstream services trust these headers and DO NOT
   re-parse the JWT. X-Gateway-Token is the integrity guard — services
   reject any request whose token doesn't match their INTERNAL_SERVICE_TOKEN.)
- GET retries with backoff (safe idempotent methods)
- Per-service circuit breaker (fail-fast)
- Normalizes errors from downstream
- Logs request/response with structured fields
"""
import asyncio
import os
import time
import logging
from enum import Enum
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ───────────── Circuit Breaker ─────────────

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-service circuit breaker to fail fast on unhealthy downstreams."""

    def __init__(
        self,
        failure_threshold: int = None,
        recovery_timeout: float = None,
        success_threshold: int = None,
    ):
        self.failure_threshold = failure_threshold or settings.CB_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout or settings.CB_RECOVERY_TIMEOUT
        self.success_threshold = success_threshold or settings.CB_SUCCESS_THRESHOLD

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPENED after {self._failure_count} failures")


class GatewayProxy:
    """Proxy requests to downstream services with timeout, retry, and circuit breaker."""

    def __init__(self, timeout: float = None, connect_timeout: float = None):
        self.timeout = timeout or settings.DOWNSTREAM_TIMEOUT
        self.connect_timeout = connect_timeout or settings.DOWNSTREAM_CONNECT_TIMEOUT
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    def _get_cb(self, service_name: str) -> CircuitBreaker:
        if service_name not in self._circuit_breakers:
            self._circuit_breakers[service_name] = CircuitBreaker()
        return self._circuit_breakers[service_name]

    async def forward(
        self,
        method: str,
        url: str,
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        request_id: str = None,
        service_name: str = "unknown",
        tenant: dict = None,
    ) -> dict:
        """Forward request to downstream service. Returns result dict."""

        # Circuit breaker check
        cb = self._get_cb(service_name)
        if not cb.allow_request():
            logger.warning(f"circuit_breaker_open", extra={"service": service_name})
            return {
                "status_code": 503,
                "body": None,
                "latency_ms": 0,
                "error": "SERVICE_UNAVAILABLE",
            }

        # Build forwarding headers — inject tenant context
        fwd_headers = {
            "Content-Type": "application/json",
            "X-Request-Id": request_id or "",
        }
        if headers:
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth:
                # Authorization is forwarded only for /api/v1/auth/* routes
                # (identity service is the only one that reads it). Other
                # services SHOULD ignore it now — PH3 / BUG-007 stripped
                # their JWT-decoding code. Keeping the forward is a
                # transitional convenience for refresh-token paths.
                fwd_headers["Authorization"] = auth

        # PH3 / BUG-007: inject identity headers from the JWT — NEVER from
        # the client. The downstream services trust these headers as the
        # sole source of identity and reject any direct call that doesn't
        # carry a matching X-Gateway-Token.
        if tenant:
            if tenant.get("school_id"):
                fwd_headers["X-School-Id"] = str(tenant["school_id"])
            if tenant.get("user_id"):
                fwd_headers["X-User-Id"] = str(tenant["user_id"])
            if tenant.get("role"):
                # Kept for back-compat with any code that still reads
                # the single-role header. New code uses X-User-Roles.
                fwd_headers["X-User-Role"] = tenant["role"]
            roles = tenant.get("roles") or []
            if roles:
                fwd_headers["X-User-Roles"] = ",".join(str(r) for r in roles)
            perms = tenant.get("permissions") or []
            if perms:
                fwd_headers["X-Permissions"] = ",".join(str(p) for p in perms)

        # X-Gateway-Token: the shared secret proving this request came
        # from the gateway. Sourced from env at request time so the
        # bootstrap script can rotate it without a gateway restart. If
        # unset, the header is omitted and downstream services 401 the
        # request — which is the correct fail-closed behaviour for a
        # mis-configured deployment.
        gateway_token = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
        if gateway_token:
            fwd_headers["X-Gateway-Token"] = gateway_token

        # Determine if retry-safe (GET only)
        max_attempts = settings.RETRY_MAX_ATTEMPTS if method == "GET" else 1

        last_error = None
        for attempt in range(1, max_attempts + 1):
            result = await self._do_request(
                method, url, fwd_headers, body, params,
                request_id, service_name, attempt,
            )

            if result.get("error") and attempt < max_attempts:
                # Retry only on timeout/connect errors, not 4xx/5xx responses
                if result["status_code"] in (502, 504):
                    last_error = result
                    await asyncio.sleep(settings.RETRY_BACKOFF * attempt)
                    logger.info(f"retrying GET",
                                extra={"service": service_name, "attempt": attempt + 1, "url": url})
                    continue

            # Record circuit breaker outcome
            if result.get("error") and result["status_code"] in (502, 504):
                cb.record_failure()
            elif not result.get("error"):
                cb.record_success()

            return result

        # All retries exhausted
        cb.record_failure()
        return last_error or result

    async def _do_request(
        self,
        method: str,
        url: str,
        headers: dict,
        body: dict,
        params: dict,
        request_id: str,
        service_name: str,
        attempt: int,
    ) -> dict:
        """Single request attempt to downstream."""
        start = time.time()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=self.connect_timeout),
            ) as client:
                response = await client.request(
                    method=method, url=url,
                    headers=headers,
                    json=body if method in ("POST", "PUT", "PATCH") else None,
                    params=params if method == "GET" else None,
                )

            latency_ms = (time.time() - start) * 1000
            logger.info("downstream_call",
                        extra={
                            "request_id": request_id,
                            "service": service_name,
                            "method": method, "url": url,
                            "status": response.status_code,
                            "latency_ms": f"{latency_ms:.1f}",
                            "attempt": attempt,
                        })

            try:
                resp_body = response.json()
            except Exception:
                resp_body = {"raw": response.text}

            return {
                "status_code": response.status_code,
                "body": resp_body,
                "latency_ms": latency_ms,
            }

        except httpx.TimeoutException:
            latency_ms = (time.time() - start) * 1000
            logger.error("downstream_timeout",
                         extra={"service": service_name, "url": url,
                                "latency_ms": f"{latency_ms:.1f}", "attempt": attempt})
            return {
                "status_code": 504,
                "body": None,
                "latency_ms": latency_ms,
                "error": "GATEWAY_TIMEOUT",
            }

        except httpx.ConnectError:
            latency_ms = (time.time() - start) * 1000
            logger.error("downstream_connect_error",
                         extra={"service": service_name, "url": url, "attempt": attempt})
            return {
                "status_code": 502,
                "body": None,
                "latency_ms": latency_ms,
                "error": "BAD_GATEWAY",
            }

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            logger.error(f"downstream_error: {e}",
                         extra={"service": service_name, "url": url, "attempt": attempt})
            return {
                "status_code": 502,
                "body": None,
                "latency_ms": latency_ms,
                "error": "BAD_GATEWAY",
            }

    async def check_health(self, url: str, service_name: str) -> dict:
        """Check downstream /health endpoint for readiness."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(3.0, connect=2.0),
            ) as client:
                resp = await client.get(f"{url}/health")
                return {
                    "status": "healthy" if resp.status_code == 200 else "unhealthy",
                    "status_code": resp.status_code,
                }
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}
