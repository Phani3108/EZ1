"""Auth dependencies for the communications service.

PH3 / BUG-007: JWT-decoding removed. Identity is read from
gateway-injected headers via the shared `ActorContext` dependency;
direct calls without `X-Gateway-Token` are 401'd.

Back-compat: `get_current_user` and `get_school_id` keep the same
callable signatures the rest of the codebase relies on but delegate
to the shared module.
"""
from __future__ import annotations

import uuid

from fastapi import Depends

from eduzim_shared.auth import (
    ActorContext,
    get_actor_context,
    get_school_id_from_actor,
)


__all__ = [
    "ActorContext",
    "get_actor_context",
    "get_current_user",
    "get_school_id",
]


def get_current_user(actor: ActorContext = Depends(get_actor_context)) -> ActorContext:
    return actor


def get_school_id(school_id: uuid.UUID = Depends(get_school_id_from_actor)) -> uuid.UUID:
    return school_id
