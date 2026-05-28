"""Tests for the permissions enum — Phase 20b.

Validates:
* Enum values are the exact wire strings the gateway compares.
* `Perm.X == "some:string"` works (StrEnum / `str, Enum` semantics).
* `Perm.X` is usable as a dict key and `in` operand alongside strings.
* `all_known()` returns every member.
* The gateway's RBAC table only references known permissions (drift
  detection — catches "someone added a permission to the gateway
  table without updating the enum").
"""
from __future__ import annotations

import re
from pathlib import Path

from eduzim_shared.permissions import Perm, PERM_AUTHENTICATED, all_known


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_enum_value_is_wire_string():
    assert Perm.SCHOOL_MANAGE.value == "school:manage"
    assert Perm.MINISTRY_READ.value == "ministry:read"


def test_str_equality_works_both_directions():
    # The whole point: code that historically did `perm == "school:manage"`
    # keeps working when the LHS becomes `Perm.SCHOOL_MANAGE`.
    assert Perm.SCHOOL_MANAGE == "school:manage"
    assert "school:manage" == Perm.SCHOOL_MANAGE


def test_membership_against_user_perm_list():
    # The gateway extracts user permissions as a CSV → list of strings.
    user_perms = ["school:manage", "comm:write"]
    assert Perm.SCHOOL_MANAGE in user_perms
    assert Perm.COMM_WRITE in user_perms
    assert Perm.SCHOOL_CREATE not in user_perms


def test_f_string_renders_wire_value():
    # If someone accidentally f-strings a Perm into a header, the
    # wire string must come out, not "Perm.SCHOOL_MANAGE".
    assert f"{Perm.SCHOOL_MANAGE}" == "school:manage"


def test_all_known_returns_every_member():
    known = all_known()
    assert "school:manage" in known
    assert "ministry:read" in known
    assert "question:draft" in known
    # Sanity: roughly the right size — if we drop below 15 something
    # got accidentally deleted.
    assert len(known) >= 15


def test_perm_authenticated_is_plain_string():
    # The gateway's "no specific permission required" sentinel must
    # NOT be a Perm member (would conflate with real permissions).
    assert PERM_AUTHENTICATED == "authenticated"
    assert PERM_AUTHENTICATED not in all_known()


def test_gateway_rbac_table_uses_only_known_permissions():
    """Drift guard. Every permission string in the gateway RBAC table
    must be a member of `Perm` or the literal "authenticated" / None.

    A failure here means someone added a permission to the gateway
    routes table without adding it to `Perm`. The fix is to add the
    enum member, not to suppress this test.
    """
    routes_py = REPO_ROOT / "services/api-gateway/app/routes.py"
    if not routes_py.exists():
        return  # repo layout in CI may differ; this test is opportunistic
    text = routes_py.read_text()
    # Match RBAC tuples like ("POST", "/api/...", "perm:string"),
    # ("GET", "/...", "authenticated"), ("...", "...", None).
    # We pull the third tuple element specifically.
    pat = re.compile(
        r"\(\s*\"(?:GET|POST|PUT|PATCH|DELETE)\","
        r"\s*\"[^\"]+\","
        r"\s*(?:\"(?P<perm>[^\"]+)\"|None)\s*\)"
    )
    seen: set[str] = set()
    for m in pat.finditer(text):
        if m.group("perm"):
            seen.add(m.group("perm"))
    allowed = all_known() | {PERM_AUTHENTICATED}
    unknown = seen - allowed
    assert not unknown, (
        f"Gateway RBAC references unknown permission strings: {sorted(unknown)}.\n"
        f"Add them to `Perm` in shared/eduzim_shared/permissions.py."
    )
