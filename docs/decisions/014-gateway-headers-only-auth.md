# ADR 014 — Gateway-headers-only authentication for downstream services

**Status**: Accepted (PH3, closed 2026-05-26)
**Closes**: BUG-007 (JWT re-parsed in every downstream service)

## Context

Pre-Phase-3, every downstream service (academics, finance, communications,
reporting-service) re-parsed the JWT in its own `dependencies.py`:

```python
from jose import jwt, JWTError

async def get_current_user(credentials = Depends(security_scheme)):
    payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, ...)
    ...
```

This duplication defeated the gateway: a request that bypassed the gateway
(e.g. by reaching the service container directly on the docker network)
would still be accepted as long as the caller produced a JWT signed with
the shared secret. The gateway's RBAC, rate-limit, circuit-breaker, and
audit-log layers were trivially bypassable.

Across 4 surviving services that's ~80 lines of duplicated JWT-parsing
code, four chances for the `type: "access"` check to drift, and four
copies of the secret on disk.

## Decision

**Downstream services do not parse JWTs.** They trust gateway-injected
HTTP headers and a shared service-to-service token:

| Header | Set by | Used for |
|---|---|---|
| `X-Gateway-Token` | gateway | integrity boundary — services 401 if it doesn't match `INTERNAL_SERVICE_TOKEN` |
| `X-User-Id` | gateway | actor identity (UUID) |
| `X-School-Id` | gateway | tenant scope (UUID) |
| `X-User-Roles` | gateway | CSV of role names, e.g. `Teacher,Parent` |
| `X-Permissions` | gateway | CSV of permission strings, e.g. `attendance:write,fees:read` |
| `X-User-Role` | gateway (legacy) | single-role string, kept for old code paths |

The gateway validates the JWT exactly once in `validate_jwt` middleware,
extracts identity via `extract_tenant`, and injects all six headers on
every forwarded request. The shared `eduzim_shared.auth.get_actor_context`
FastAPI dependency reads them and returns a frozen `ActorContext`
dataclass.

## Integrity boundary

The `X-Gateway-Token` check is the single most important security
property of this design. Without it, anyone with docker-network access
could forge `X-User-Id` and impersonate any user. The token is the same
`INTERNAL_SERVICE_TOKEN` previously used for `/internal/*` endpoints —
PH3 extends its scope to every downstream request, not just the legacy
RPC routes. Bootstrap script (BUG-004 follow-up) issues one shared
token across the whole deployment.

The dependency fails closed on three conditions:

1. `INTERNAL_SERVICE_TOKEN` is unset on the service container → 500
   (refuse to authorize anyone — the service is misconfigured).
2. `X-Gateway-Token` is missing or wrong → 401 ("Direct service access denied").
3. `X-User-Id` or `X-School-Id` is missing or malformed → 401.

## Alternatives considered

* **mTLS between gateway and downstream services.** Stronger primitive
  (no shared secret on disk in N places), but requires cert-manager + a
  rotation runbook + container-startup ordering for cert distribution.
  Scheduled for Phase 5 (INFRA-019); PH3 lays the application-layer
  foundation that mTLS will reinforce.
* **Signed JWT cookies for service-to-service.** Same drift risk as the
  status quo — each service would still have to validate signatures.
* **OIDC / Keycloak.** Overkill for 4 internal services. Reasonable to
  revisit once we expose third-party API access.
* **Status quo + JWT in identity only, hand-rolled HMAC elsewhere.**
  Still N decoders.

## Consequences

* Each service's `dependencies.py` now has 0 lines of JWT decoding
  (only `get_current_user`/`get_school_id` shims that delegate to
  shared). Total reduction: ~80 LoC + 4 secret copies.
* Tests inject headers instead of forging tokens. Each service has a
  `tests/test_gateway_headers_only.py` (5 negative + 1 happy-path test
  per service) that proves the integrity boundary holds.
* Each downstream container must now have `INTERNAL_SERVICE_TOKEN`
  set, otherwise it 500s on every request. The compose files enforce
  this with `${INTERNAL_SERVICE_TOKEN:?...missing}`.
* Gateway must inject `X-Gateway-Token` on every forwarded request.
  Sourced from env at request time (no caching) so rotation doesn't
  require a gateway restart.
* RBAC continues to be enforced at the gateway. The `require_permission`
  dependency in each service is now a no-op pass-through; the gateway's
  `check_rbac` middleware is the only gatekeeper.

## Migration notes

* `services/reporting-service/app/dependencies.py` is stubbed to raise
  HTTP 410 if anyone invokes it. The container has no auth-guarded
  routes; the consumer process doesn't touch JWTs.
* `services/identity/app/utils/security.py` is the **only** remaining
  module that imports `jose`. It's the sole token issuer/verifier.
* Test helpers in each service moved from a `_make_token()` /
  `Authorization: Bearer …` pattern to a `_gateway_headers()` /
  direct-header pattern. Existing test bodies needed minimal changes
  thanks to the back-compat `ActorContext.get(...)` and `[]` shims.
