"""Permission identifiers — Phase 20b.

A typo in a permission string is one of the worst-shaped bugs the
codebase can produce:

* The gateway compares the request's required permission against the
  user's `X-Permissions` CSV.
* `"school:mange"` (typo for `school:manage`) is a string that is in
  no user's permission list. The result is a confident `403` for
  every caller — including the legitimate SchoolAdmin. No syntax
  error, no test failure, no log line. Just a feature that silently
  stops working.

The fix is to type-narrow permissions to a known set. This module
ships an `Enum` of every permission EduZim uses, plus an `all_known()`
helper for tests / startup-time validation.

Why `StrEnum`?
--------------

`StrEnum` (Python 3.11+) values are real strings, so all existing
comparisons like `if perm in user_perms` keep working when callers
pass `Perm.SCHOOL_MANAGE` instead of `"school:manage"`. The gateway
already CSV-compares strings; the enum value IS the string.

Why a flat enum and not a hierarchy?
------------------------------------

EduZim permissions are not nested (we don't grant `school:*` style
roles — RBAC is at the role layer). A flat enum maps 1:1 to what's
on the wire.

Add a new permission — checklist
--------------------------------

1. Add the enum member here.
2. Wire it into the seed in `scripts/seed-baseline.sh`.
3. Grant it to whichever role(s) need it via the standard
   `role_permissions` rows.
4. Reference `Perm.YOUR_NEW_PERM` in route handlers / gateway RBAC.

Do NOT add a permission and then write `"your:new_perm"` in code —
that defeats the purpose of this module.
"""
from __future__ import annotations

from enum import Enum


class Perm(str, Enum):
    """Every EduZim permission string. Value is the wire string."""

    # ─── School / academic management ──────────────────────────────
    SCHOOL_CREATE = "school:create"        # Provisioner / EduZimOps
    SCHOOL_MANAGE = "school:manage"        # SchoolAdmin
    # ─── People ────────────────────────────────────────────────────
    STUDENT_READ = "student:read"
    STUDENT_WRITE = "student:write"
    STUDENT_DRAFT = "student:draft"        # Teacher draft submission
    TEACHER_READ = "teacher:read"
    # ─── Attendance ────────────────────────────────────────────────
    ATTENDANCE_READ = "attendance:read"
    ATTENDANCE_WRITE = "attendance:write"
    # ─── Assessment ────────────────────────────────────────────────
    ASSESSMENT_READ = "assessment:read"
    ASSESSMENT_WRITE = "assessment:write"
    # ─── Question bank (Phase 16c) ─────────────────────────────────
    QUESTION_DRAFT = "question:draft"      # Teacher draft submission
    # ─── Fees / payments ───────────────────────────────────────────
    FEES_READ = "fees:read"
    FEES_WRITE = "fees:write"
    # ─── Communications ────────────────────────────────────────────
    COMM_READ = "comm:read"
    COMM_WRITE = "comm:write"
    INVITE_WRITE = "invite:write"          # Phase 15 dispatcher
    # ─── Reporting ─────────────────────────────────────────────────
    REPORT_READ = "report:read"
    REPORT_ADMIN = "report:admin"
    # ─── Ministry (Phase 14) ───────────────────────────────────────
    MINISTRY_READ = "ministry:read"

    def __str__(self) -> str:  # noqa: D401
        """Return the wire string so `f"{Perm.X}"` doesn't print `Perm.X`."""
        return self.value


# Sentinel value used by the gateway when an endpoint requires merely
# an authenticated user (no specific permission). Kept as a plain
# string because the gateway RBAC table mixes None / "authenticated" /
# real permission strings — promoting it to an Enum member would
# create a "is it a permission or not?" branching mess.
PERM_AUTHENTICATED = "authenticated"


def all_known() -> frozenset[str]:
    """Return every permission string this codebase knows about.

    Useful at startup to validate that seed scripts and the gateway
    RBAC table only reference known strings. A drift here is the
    actionable signal for "someone added a permission and forgot to
    update the enum."
    """
    return frozenset(m.value for m in Perm)


__all__ = ["Perm", "PERM_AUTHENTICATED", "all_known"]
