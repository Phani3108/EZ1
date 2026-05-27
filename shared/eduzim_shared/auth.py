"""Gateway-headers-only auth (PH3 / closes BUG-007).

Downstream services (academics, finance, communications) no longer parse
JWTs. The gateway validates the token once and injects identity headers
on every forwarded request:

    X-User-Id          UUID of the authenticated user
    X-School-Id        UUID of the user's school (tenant scope)
    X-User-Roles       CSV of role names ("Teacher,Parent")
    X-Permissions      CSV of permission strings ("attendance:write,...")
    X-Gateway-Token    shared secret proving the request came from the gateway

This module exposes the FastAPI dependency `get_actor_context` (and a
matching `ActorContext` dataclass). Services should import the dependency
and stop calling `jose.jwt.decode` themselves.

Security model:
  * `X-Gateway-Token` MUST match the service's `INTERNAL_SERVICE_TOKEN`.
    Without that match, requests are rejected 401 — even if the other
    headers are well-formed. This prevents bypass by hitting the service
    container directly.
  * The gateway's own `INTERNAL_SERVICE_TOKEN` must equal what each
    downstream service has in its env. Bootstrap script (BUG-004 follow-up)
    issues one shared token across the deployment.
  * `INTERNAL_SERVICE_TOKEN` is the same secret the existing /internal/*
    endpoints already required — we're just extending its scope from
    "service-to-service internal RPC" to "every downstream request from
    the gateway". The dual-purpose use is intentional and documented in
    the runbook.

This dependency is intentionally tolerant of MISSING optional headers
(roles / permissions) since not every flow needs them — but `X-User-Id`,
`X-School-Id`, and `X-Gateway-Token` are required. Missing required
header → 401.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, Header, HTTPException


@dataclass(frozen=True)
class ActorContext:
    """Resolved identity for the current request, sourced from gateway headers."""
    user_id: uuid.UUID
    school_id: uuid.UUID
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)

    def has_role(self, name: str) -> bool:
        return name in self.roles

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions

    # Back-compat shim — many existing dependencies pass a `dict` around
    # (the old `get_current_user` return value). New code should use the
    # dataclass attributes; the following dict-like protocol (`get`,
    # `__getitem__`, `__contains__`) keeps drop-in callers working during
    # the transition.
    def _as_dict(self) -> dict:
        return {
            "sub": str(self.user_id),
            "user_id": str(self.user_id),
            "school_id": str(self.school_id),
            "roles": list(self.roles),
            "permissions": list(self.permissions),
            # the old token payload had a single "role" too — use the
            # first one when emulating that shape
            "role": self.roles[0] if self.roles else None,
            "type": "access",
        }

    def get(self, key: str, default=None):
        return self._as_dict().get(key, default)

    def __getitem__(self, key: str):
        return self._as_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self._as_dict()


def _split_csv(value: Optional[str]) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _service_internal_token() -> str:
    """Read INTERNAL_SERVICE_TOKEN from env at call time.

    We read fresh each call rather than caching, so tests that monkeypatch
    `os.environ` between cases see the new value immediately. The cost is
    negligible (one dict lookup per request).
    """
    return os.environ.get("INTERNAL_SERVICE_TOKEN", "")


def get_actor_context(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_school_id: Optional[str] = Header(None, alias="X-School-Id"),
    x_user_roles: Optional[str] = Header(None, alias="X-User-Roles"),
    x_permissions: Optional[str] = Header(None, alias="X-Permissions"),
    x_gateway_token: Optional[str] = Header(None, alias="X-Gateway-Token"),
) -> ActorContext:
    """FastAPI dependency yielding an ActorContext from gateway headers.

    Raises 401 if:
      - X-Gateway-Token is missing or wrong (the request didn't come from
        the gateway, or the secrets are mis-configured).
      - X-User-Id or X-School-Id is missing/malformed.

    Does NOT touch any JWT. The gateway is the only JWT verifier.
    """
    expected_token = _service_internal_token()
    if not expected_token:
        # Misconfigured service — refuse to authorize anyone rather than
        # default-allow. (BUG-004's "fail-closed" spirit applied to the
        # downstream side.)
        raise HTTPException(status_code=500, detail="INTERNAL_SERVICE_TOKEN not set")

    if not x_gateway_token or x_gateway_token != expected_token:
        # Important: don't echo expected token in the response. Generic 401.
        raise HTTPException(status_code=401, detail="Direct service access denied")

    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header missing")
    if not x_school_id:
        raise HTTPException(status_code=401, detail="X-School-Id header missing")

    try:
        user_id = uuid.UUID(x_user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="X-User-Id must be a UUID")
    try:
        school_id = uuid.UUID(x_school_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="X-School-Id must be a UUID")

    return ActorContext(
        user_id=user_id,
        school_id=school_id,
        roles=_split_csv(x_user_roles),
        permissions=_split_csv(x_permissions),
    )


def get_school_id_from_actor(
    actor: ActorContext = Depends(get_actor_context),
) -> uuid.UUID:
    """Convenience dependency for routes that only need school_id.

    Equivalent to the per-service `get_school_id` that used to wrap
    `get_current_user`. New routes should prefer depending on
    `ActorContext` directly and using `.school_id`.
    """
    return actor.school_id


def has_role(actor: ActorContext, role: str) -> bool:
    """Module-level helper mirroring is_teacher_role / is_parent_role
    semantics — but driven off the gateway-injected roles list."""
    return role in actor.roles
