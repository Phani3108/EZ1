"""Auth dependencies for the academics service.

PH3 / BUG-007: JWT-decoding removed. The gateway is the only JWT verifier;
academics trusts gateway-injected headers (`X-Gateway-Token`, `X-User-Id`,
`X-School-Id`, `X-User-Roles`, `X-Permissions`) read via the shared
`get_actor_context` dependency. Direct calls without a matching
`X-Gateway-Token` are 401'd by the shared module.

History:
  PH2-7 added `get_token` (originally from student-service) so the student
  routes could pass the raw token to the in-process school client (the
  client ignores it now, but the signature stayed for protocol compat).
  PH2-8 added `is_teacher_role` and a new in-process
  `verify_teacher_class_authorization` that replaced attendance-service's
  former HTTP hop into school-service.
  PH3 (this rewrite) — removed `jose.jwt.decode`; identity now comes from
  headers. The PH2-9 fail-closed `AuthorizationServiceUnavailable` flow
  is preserved unchanged.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from eduzim_shared.auth import (
    ActorContext,
    get_actor_context,
    get_school_id_from_actor,
)


logger = logging.getLogger(__name__)


__all__ = [
    "ActorContext",
    "AuthorizationServiceUnavailable",
    "get_actor_context",
    "get_current_user",
    "get_school_id",
    "get_token",
    "is_teacher_role",
    "is_parent_role",
    "require_permission",
    "verify_teacher_class_authorization",
    "verify_parent_student_authorization",
    "verify_teacher_student_authorization",
]


class AuthorizationServiceUnavailable(Exception):
    """Raised when we cannot determine teacher/parent authorization.

    PH2-8: in-process replacement makes the original failure modes
    (network timeout, 5xx from school-service, malformed JSON) impossible;
    only a real DB error can now raise this. The exception type is kept so
    the route layer's existing 503-with-Retry-After handler continues to
    work unmodified.
    """


def get_current_user(actor: ActorContext = Depends(get_actor_context)) -> ActorContext:
    """Back-compat shim.

    Returns an `ActorContext`. Callers that still do `.get(key)` or
    `payload["sub"]` continue to work because `ActorContext` implements
    the dict-like protocol for the old token-payload keys.
    """
    return actor


def get_school_id(school_id: uuid.UUID = Depends(get_school_id_from_actor)) -> uuid.UUID:
    return school_id


def get_token() -> str:
    """Return an empty string.

    PH2-7 introduced this dependency to forward the raw token to the
    in-process school client. The client ignored it then, and PH3 removed
    the token-passing concept entirely (services no longer read JWTs).
    The signature stays so callers that still `Depends(get_token)`
    continue to type-check; they always get an empty string now.
    """
    return ""


def require_permission(required: str):
    """RBAC-style helper.

    PH3: the gateway enforces RBAC (see services/api-gateway/app/routes.py
    RBAC_MAP). This is now a thin pass-through that doesn't re-check; it
    stays callable so existing routes don't need a sweep.
    """
    async def checker(actor: ActorContext = Depends(get_actor_context)) -> ActorContext:
        return actor
    return checker


def is_teacher_role(current_user) -> bool:
    """Check if the current user has a Teacher role.

    Accepts either an `ActorContext` or the legacy dict shape.
    """
    if isinstance(current_user, ActorContext):
        return current_user.has_role("Teacher")
    roles = current_user.get("roles", []) if hasattr(current_user, "get") else []
    return "Teacher" in roles


def is_parent_role(current_user) -> bool:
    if isinstance(current_user, ActorContext):
        return current_user.has_role("Parent")
    roles = current_user.get("roles", []) if hasattr(current_user, "get") else []
    return "Parent" in roles


async def verify_teacher_class_authorization(
    teacher_user_id: uuid.UUID,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    db: Session,
) -> bool:
    """Verify a teacher is assigned to a class within their school.

    PH2-8: in-process replacement for the pre-consolidation HTTP call into
    `school-service /internal/teachers/authorize`. Queries
    `class_teacher_assignments` directly via the existing request DB
    session.

    The async signature is preserved so the attendance route layer's
    `await verify_teacher_class_authorization(...)` call continues to work
    without modification (the function is sync internally now; FastAPI
    handles awaiting a coroutine that returns a plain value).

    Raises
    ------
    AuthorizationServiceUnavailable
        On real DB-level failure (rare; previously raised on transient
        network errors that no longer apply post-merge). The attendance
        route layer wraps this into 503 with Retry-After.
    """
    from app.services.authorization import is_teacher_authorized_for_class
    try:
        return is_teacher_authorized_for_class(
            teacher_user_id=teacher_user_id,
            class_id=class_id,
            school_id=school_id,
            db_session=db,
        )
    except SQLAlchemyError as e:
        logger.error(
            "Teacher authorization DB query failed: teacher=%s class=%s school=%s err=%s",
            teacher_user_id, class_id, school_id, e,
        )
        raise AuthorizationServiceUnavailable(
            f"DB error during authorization check: {e}"
        ) from e


async def verify_parent_student_authorization(
    parent_user_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: Session,
) -> bool:
    """PH2-9: in-process replacement for the pre-consolidation HTTP call into
    `student-service /internal/parents/authorize`.

    Returns True if the parent's user account is linked to the student
    (via `student_parents`) within the same school. False otherwise.

    Raises
    ------
    AuthorizationServiceUnavailable
        On a real DB-level failure — same fail-closed-honestly contract as
        `verify_teacher_class_authorization`.
    """
    from app.services.authorization import is_parent_authorized_for_student
    try:
        return is_parent_authorized_for_student(
            parent_user_id=parent_user_id,
            student_id=student_id,
            school_id=school_id,
            db_session=db,
        )
    except SQLAlchemyError as e:
        logger.error(
            "Parent-student authorization DB query failed: parent=%s student=%s school=%s err=%s",
            parent_user_id, student_id, school_id, e,
        )
        raise AuthorizationServiceUnavailable(
            f"DB error during authorization check: {e}"
        ) from e


async def verify_teacher_student_authorization(
    teacher_user_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: Session,
) -> bool:
    """PH2-9: in-process replacement for the pre-consolidation HTTP call into
    `school-service /internal/teachers/authorize-student`.

    Returns True iff the teacher teaches a class the student is enrolled in.
    False otherwise. Raises AuthorizationServiceUnavailable on DB error.
    """
    from app.services.authorization import is_teacher_authorized_for_student
    try:
        return is_teacher_authorized_for_student(
            teacher_user_id=teacher_user_id,
            student_id=student_id,
            school_id=school_id,
            db_session=db,
        )
    except SQLAlchemyError as e:
        logger.error(
            "Teacher-student authorization DB query failed: teacher=%s student=%s school=%s err=%s",
            teacher_user_id, student_id, school_id, e,
        )
        raise AuthorizationServiceUnavailable(
            f"DB error during authorization check: {e}"
        ) from e
