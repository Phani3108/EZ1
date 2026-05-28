"""Phase 17a — thin client wrapper around the communications-service
attachment endpoints. Phase 19b makes failure visible.

Used by the template-instantiation flow to clone every attachment that
the template owns into a fresh row for the new instance. The HTTP call
is "best-effort" — if communications is unreachable (dev, tests, or a
transient failure), the instantiation still succeeds and the audit row
records both `attachments_cloned: 0` AND the failure reason so a HoD
isn't left with a green checkmark on a half-published template.

Tests typically set `EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1` to short-
circuit the call without hitting the network.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# Phase 19b — warn-once when the test escape is set in a real process.
# A developer who sets this in their local .env to speed up dev would
# otherwise see template instantiation report 0 cloned attachments
# silently. One log line at startup is enough.
_DISABLED_LOGGED = False


@dataclass(frozen=True)
class CloneResult:
    """Phase 19b — richer return for attachment-clone calls.

    - `cloned_count` matches the old int return.
    - `error_kind` is one of:
        * None              — call succeeded.
        * "disabled_env"    — short-circuited by EDUZIM_DISABLE_CROSS_SERVICE_HTTP.
        * "http_status"     — communications responded 4xx/5xx.
        * "transport"       — connection error / timeout / DNS.
        * "parse"           — response wasn't a valid JSON envelope.
    - `error_detail` is a 1-line string for the audit row's `details`
      blob. We log it at WARNING regardless; this just lets the caller
      mirror it into the audit trail so operators can spot patterns
      without grepping logs.

    Truthy iff cloned_count > 0, so old `if clone_attachments_for_owner(...)`
    patterns keep working.
    """
    cloned_count: int
    error_kind: Optional[str] = None
    error_detail: Optional[str] = None

    def __bool__(self) -> bool:
        return self.cloned_count > 0

    def __int__(self) -> int:
        return self.cloned_count


def clone_attachments_for_owner(
    *,
    school_id: uuid.UUID,
    source_owner_kind: str,
    source_owner_id: str,
    new_owner_kind: str,
    new_owner_id: str,
    actor_user_id: str,
    timeout: float = 5.0,
) -> CloneResult:
    """Call communications' POST /comm/attachments/clone-bulk.

    Returns a `CloneResult` that the caller folds into the audit row.
    The function NEVER raises — template instantiation is more
    important than file fidelity. The visible-failure pattern is:

      result = clone_attachments_for_owner(...)
      _audit(... details={
          "attachments_cloned": result.cloned_count,
          "attachment_clone_error": result.error_kind,   # null on success
      })

    A non-null `error_kind` in the audit log is a signal for the
    reporting consumer to flag the template (Phase 19+) and surface a
    "some attachments did not copy" banner to the HoD.

    Tests: set `EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1` to short-circuit
    without hitting the network; the result will carry
    `error_kind="disabled_env"` so the test envelope can assert it.
    """
    global _DISABLED_LOGGED
    if os.environ.get("EDUZIM_DISABLE_CROSS_SERVICE_HTTP", "0") == "1":
        if not _DISABLED_LOGGED:
            logger.info(
                "attachment_client short-circuited by "
                "EDUZIM_DISABLE_CROSS_SERVICE_HTTP=1; "
                "template instantiations will report 0 cloned attachments"
            )
            _DISABLED_LOGGED = True
        return CloneResult(cloned_count=0, error_kind="disabled_env")

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
            detail = f"status={r.status_code} body={r.text[:200]}"
            logger.warning("attachment_clone_failed %s", detail)
            return CloneResult(
                cloned_count=0,
                error_kind="http_status",
                error_detail=detail,
            )
        data = r.json().get("data") or {}
        return CloneResult(cloned_count=int(data.get("cloned_count") or 0))
    except httpx.HTTPError as e:
        detail = f"{type(e).__name__}: {e}"
        logger.warning("attachment_clone_failed transport %s", detail)
        return CloneResult(
            cloned_count=0,
            error_kind="transport",
            error_detail=detail,
        )
    except (ValueError, KeyError) as e:
        detail = f"{type(e).__name__}: {e}"
        logger.warning("attachment_clone_failed parse %s", detail)
        return CloneResult(
            cloned_count=0,
            error_kind="parse",
            error_detail=detail,
        )
