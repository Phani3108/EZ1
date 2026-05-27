"""In-process authorization functions (PH2-5 interface stubs).

Per ADR 006 addendum §2 "The seams": these functions replace the current
cross-service HTTP authz calls (`/internal/teachers/authorize`,
`/internal/teachers/authorize-student`, `/internal/parents/authorize`) once
the school + student + assessment schemas live inside academics_db.

For PH2-5 the functions are stubs that raise `NotImplementedError`. PH2-8
implements `is_teacher_authorized_for_class` (when attendance moves in).
PH2-9 implements `is_teacher_authorized_for_student` and
`is_parent_authorized_for_student` (when assessment moves in).

Callers (route layer) MUST pass an `ActorContext` derived from gateway
headers (Phase 3 will formalise that pattern). These functions are not
callable from anywhere in the codebase that doesn't already have a verified
actor context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class ActorContext:
    """Identity context derived from the gateway-injected headers.

    PH2-5 placeholder; Phase 3 will replace per-service JWT decode with this.
    """
    user_id: uuid.UUID
    school_id: uuid.UUID
    role: str
    permissions: frozenset[str] = frozenset()


def is_teacher_authorized_for_class(
    teacher_user_id: uuid.UUID,
    class_id: uuid.UUID,
    school_id: uuid.UUID,
    db_session,
) -> bool:
    """PH2-8 implementation: return True if the teacher is assigned to the
    class within the school.

    Direct DB query against `class_teacher_assignments` (now co-located in
    academics_db after PH2-6). Replaces the previous HTTP hop into
    `school-service /internal/teachers/authorize` and the Phase-1
    AuthorizationServiceUnavailable handshake — in-process queries cannot
    suffer transient network failure.

    The signature is raw IDs for now (not `ActorContext`). PH3 will collapse
    every authz call site onto `ActorContext` extracted from gateway headers;
    at that point this function and `is_teacher_role` move to a uniform shape.

    Returns
    -------
    bool
        True if a `ClassTeacherAssignment` row exists matching all three IDs.
        False otherwise (genuine denial — teacher not assigned).

    Raises
    ------
    sqlalchemy.exc.SQLAlchemyError
        On a real DB-level failure. Callers should let it propagate; the
        attendance route layer wraps DB errors into 503 with Retry-After
        (mirroring the Phase-1 fail-closed-but-honest pattern for the old
        HTTP variant).
    """
    # Lazy import keeps the module dependency graph clean and avoids a
    # circular import when authorization.py is loaded before models.
    from app.models.school import ClassTeacherAssignment
    row = db_session.query(ClassTeacherAssignment).filter(
        ClassTeacherAssignment.teacher_user_id == teacher_user_id,
        ClassTeacherAssignment.class_id == class_id,
        ClassTeacherAssignment.school_id == school_id,
    ).first()
    return row is not None


def is_teacher_authorized_for_student(
    teacher_user_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db_session,
) -> bool:
    """PH2-9 implementation: return True if the teacher teaches *some* class
    the student is currently enrolled in (within the same school).

    Joins `class_teacher_assignments` ⋈ `enrollments` on `class_id` +
    `school_id`. Replaces the HTTP hop into
    `school-service /internal/teachers/authorize-student`.

    Returns True if any matching row exists. Returns False otherwise
    (genuine denial — teacher isn't assigned to any class the student is in).

    Raises
    ------
    sqlalchemy.exc.SQLAlchemyError
        On a real DB-level failure. Callers should let it propagate so the
        route layer can fail-closed-honestly (Phase 1 BUG-001 spirit).
    """
    from app.models.school import ClassTeacherAssignment
    from app.models.student import Enrollment
    row = (
        db_session.query(ClassTeacherAssignment.id)
        .join(
            Enrollment,
            (Enrollment.class_id == ClassTeacherAssignment.class_id)
            & (Enrollment.school_id == ClassTeacherAssignment.school_id),
        )
        .filter(
            ClassTeacherAssignment.teacher_user_id == teacher_user_id,
            ClassTeacherAssignment.school_id == school_id,
            Enrollment.student_id == student_id,
            Enrollment.school_id == school_id,
        )
        .first()
    )
    return row is not None


def is_parent_authorized_for_student(
    parent_user_id: uuid.UUID,
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db_session,
) -> bool:
    """PH2-9 implementation: return True if the parent's user account is
    linked to the student via `student_parents` (within the same school).

    The link chain: gateway-supplied `parent_user_id` → `parents.user_id`
    → `parents.id` → `student_parents.parent_id` → `student_parents.student_id`.

    Replaces the HTTP hop into `student-service /internal/parents/authorize`.

    Returns True iff a matching link row exists with the right school_id.

    Raises
    ------
    sqlalchemy.exc.SQLAlchemyError
        On a real DB-level failure (caller fail-closed-honestly per BUG-001).
    """
    from app.models.student import Parent, StudentParent
    row = (
        db_session.query(StudentParent.id)
        .join(Parent, Parent.id == StudentParent.parent_id)
        .filter(
            Parent.user_id == parent_user_id,
            Parent.school_id == school_id,
            StudentParent.student_id == student_id,
            StudentParent.school_id == school_id,
        )
        .first()
    )
    return row is not None
