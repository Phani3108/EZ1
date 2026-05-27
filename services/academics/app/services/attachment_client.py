"""Phase 17a — thin client wrapper around the communications-service
attachment endpoints.

Used by the template-instantiation flow to clone every attachment
that the template owns into a fresh row for the new instance. The
HTTP call is "best-effort" — if communications is unreachable (dev,
tests, or a transient failure), the instantiation still succeeds and
the audit row records `attachments_cloned: 0`.

Tests typically monkey-patch `clone_attachments_for_owner` to a stub
so SQLite tests don't hit the network.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def clone_attachments_for_owner(
    *,
    school_id: uuid.UUID,
    source_owner_kind: str,
    source_owner_id: str,
    new_owner_kind: str,
    new_owner_id: str,
    actor_user_id: str,
    timeout: float = 5.0,
) -> int:
    """Call communications' POST /comm/attachments/clone-bulk.

    Returns the count of cloned attachments. Returns 0 if the call
    fails (communications down / DNS error / timeout). Errors are
    logged but never re-raised — template instantiation is more
    important than file fidelity.

    Tests: set EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1 to short-circuit
    this function to 0 without attempting the call.
    """
    if os.environ.get("EDUZIM_DISABLE_CROSS_SERVICE_HTTP", "0") == "1":
        return 0

    settings = get_settings()
    url = f"{settings.COMMUNICATIONS_SERVICE_URL}/api/v1/comm/attachments/clone-bulk"
    headers = {
        "X-Gateway-Token": settings.INTERNAL_SERVICE_TOKEN,
        "X-User-Id": actor_user_id,
        "X-School-Id": str(school_id),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,comm:write",
    }
    payload = {
        "source_owner_kind": source_owner_kind,
        "source_owner_id": source_owner_id,
        "new_owner_kind": new_owner_kind,
        "new_owner_id": new_owner_id,
    }
    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code >= 400:
            logger.warning(
                "attachment_clone_failed status=%s body=%s",
                r.status_code, r.text[:200],
            )
            return 0
        data = r.json().get("data") or {}
        return int(data.get("cloned_count") or 0)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("attachment_clone_failed err=%s", e)
        return 0
