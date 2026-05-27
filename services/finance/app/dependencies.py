"""Auth dependencies for the finance service.

PH3 / BUG-007: the JWT-decoding `get_current_user` is gone. Identity
is read from gateway-injected headers via the shared `ActorContext`
dependency. Direct calls without a matching `X-Gateway-Token` are
rejected 401 by `get_actor_context` itself.

Back-compat: `get_current_user` and `get_school_id` keep the same call
signatures the rest of the codebase relies on — but their
implementations now delegate to the shared module. New code should
depend on `ActorContext` directly.
"""
from __future__ import annotations

import uuid

from fastapi import Depends

from eduzim_shared.auth import (
    ActorContext,
    get_actor_context,
    get_school_id_from_actor,
)


# Re-export so existing imports `from app.dependencies import get_actor_context` work.
__all__ = [
    "ActorContext",
    "get_actor_context",
    "get_current_user",
    "get_school_id",
]


def get_current_user(actor: ActorContext = Depends(get_actor_context)) -> ActorContext:
    """Back-compat shim — returns an ActorContext that exposes a `.get(key)`
    method so callers still doing `current_user.get("school_id")` work
    unchanged."""
    return actor


def get_school_id(school_id: uuid.UUID = Depends(get_school_id_from_actor)) -> uuid.UUID:
    return school_id
