"""Tests for shared gateway-headers-only auth (PH3 / BUG-007 closer)."""
import os
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from eduzim_shared.auth import (
    ActorContext,
    get_actor_context,
    get_school_id_from_actor,
)


GATEWAY_TOKEN = "test-internal-token-XXX"


@pytest.fixture(autouse=True)
def _set_internal_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", GATEWAY_TOKEN)


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/whoami")
    def whoami(actor: ActorContext = Depends(get_actor_context)):
        return {
            "user_id": str(actor.user_id),
            "school_id": str(actor.school_id),
            "roles": list(actor.roles),
            "permissions": list(actor.permissions),
        }

    @app.get("/school")
    def school(school_id: uuid.UUID = Depends(get_school_id_from_actor)):
        return {"school_id": str(school_id)}

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _ok_headers(user_id=None, school_id=None, roles=None, perms=None, token=GATEWAY_TOKEN):
    headers = {}
    if token is not None:
        headers["X-Gateway-Token"] = token
    if user_id is not False:
        headers["X-User-Id"] = str(user_id or uuid.uuid4())
    if school_id is not False:
        headers["X-School-Id"] = str(school_id or uuid.uuid4())
    if roles is not None:
        headers["X-User-Roles"] = roles
    if perms is not None:
        headers["X-Permissions"] = perms
    return headers


class TestActorContextDataclass:

    def test_has_role_and_permission_lookups(self):
        actor = ActorContext(
            user_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            roles=("Teacher", "Parent"),
            permissions=("attendance:write", "fees:read"),
        )
        assert actor.has_role("Teacher")
        assert not actor.has_role("Admin")
        assert actor.has_permission("fees:read")
        assert not actor.has_permission("fees:write")

    def test_get_shim_emulates_old_dict_payload(self):
        u = uuid.uuid4()
        s = uuid.uuid4()
        actor = ActorContext(user_id=u, school_id=s, roles=("Admin",))
        # Back-compat: callers still using `payload.get("school_id")` etc.
        assert actor.get("school_id") == str(s)
        assert actor.get("user_id") == str(u)
        assert actor.get("sub") == str(u)
        assert actor.get("type") == "access"
        assert actor.get("role") == "Admin"
        assert actor.get("missing_key", "fallback") == "fallback"


class TestGatewayTokenGuard:
    """The X-Gateway-Token header is the critical bypass-protection
    boundary. Without it, anyone who reaches the service container
    directly could forge an X-User-Id and impersonate a user."""

    def test_missing_gateway_token_is_401(self, client):
        h = _ok_headers(token=None)
        r = client.get("/whoami", headers=h)
        assert r.status_code == 401
        assert "Direct service access denied" in r.json()["detail"]

    def test_wrong_gateway_token_is_401(self, client):
        h = _ok_headers(token="not-the-real-token")
        r = client.get("/whoami", headers=h)
        assert r.status_code == 401

    def test_unset_internal_token_is_500(self, client, monkeypatch):
        # Service mis-configured (no INTERNAL_SERVICE_TOKEN set) → refuse
        # to authorize ANYTHING. Fail closed.
        monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)
        h = _ok_headers()
        r = client.get("/whoami", headers=h)
        assert r.status_code == 500


class TestRequiredIdentityHeaders:

    def test_missing_user_id_is_401(self, client):
        h = _ok_headers(user_id=False)
        r = client.get("/whoami", headers=h)
        assert r.status_code == 401
        assert "X-User-Id" in r.json()["detail"]

    def test_missing_school_id_is_401(self, client):
        h = _ok_headers(school_id=False)
        r = client.get("/whoami", headers=h)
        assert r.status_code == 401
        assert "X-School-Id" in r.json()["detail"]

    def test_malformed_user_id_is_400(self, client):
        h = _ok_headers()
        h["X-User-Id"] = "not-a-uuid"
        r = client.get("/whoami", headers=h)
        assert r.status_code == 400

    def test_malformed_school_id_is_400(self, client):
        h = _ok_headers()
        h["X-School-Id"] = "not-a-uuid"
        r = client.get("/whoami", headers=h)
        assert r.status_code == 400


class TestHappyPath:

    def test_minimal_headers(self, client):
        u, s = uuid.uuid4(), uuid.uuid4()
        h = _ok_headers(user_id=u, school_id=s)
        r = client.get("/whoami", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == str(u)
        assert body["school_id"] == str(s)
        assert body["roles"] == []
        assert body["permissions"] == []

    def test_with_roles_and_permissions(self, client):
        u, s = uuid.uuid4(), uuid.uuid4()
        h = _ok_headers(
            user_id=u, school_id=s,
            roles="Teacher,Parent",
            perms="attendance:write,fees:read",
        )
        r = client.get("/whoami", headers=h)
        body = r.json()
        assert body["roles"] == ["Teacher", "Parent"]
        assert body["permissions"] == ["attendance:write", "fees:read"]

    def test_get_school_id_dependency(self, client):
        u, s = uuid.uuid4(), uuid.uuid4()
        r = client.get("/school", headers=_ok_headers(user_id=u, school_id=s))
        assert r.status_code == 200
        assert r.json()["school_id"] == str(s)

    def test_csv_handles_extra_whitespace(self, client):
        h = _ok_headers(roles=" Teacher , Admin ", perms="x:y, a:b ")
        r = client.get("/whoami", headers=h)
        body = r.json()
        assert body["roles"] == ["Teacher", "Admin"]
        assert body["permissions"] == ["x:y", "a:b"]
