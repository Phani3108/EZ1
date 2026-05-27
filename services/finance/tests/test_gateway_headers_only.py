"""PH3 / BUG-007: prove direct calls (no gateway headers) are rejected.

The finance service no longer decodes JWTs — it trusts gateway-injected
headers. This file verifies the integrity boundary:

  * No X-Gateway-Token          → 401
  * Wrong X-Gateway-Token       → 401
  * Valid token + headers       → request reaches the route

We only assert on the AUTH OUTCOME (401 vs 200/4xx-from-handler). Body
shape, validation errors, and DB state are covered by the existing
test_fees / test_paynow files.
"""
import os
import uuid

import pytest


# Shared package envs must be set BEFORE app.config is imported. The
# tests/__init__.py already does this — we re-assert here for clarity.
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION-32chars-min-len-XXXX")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token-DO-NOT-USE-IN-PRODUCTION")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_finance_headers.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def db_tables():
    """Create the finance tables in an in-memory SQLite so the happy-path
    test can actually reach the route layer (otherwise the OperationalError
    obscures whether auth succeeded)."""
    from app.database import Base, get_db
    from app.models.fees import FeeStructure, FeeItem, Invoice, Payment  # noqa
    from app.main import app

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()
    eng.dispose()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def gateway_headers():
    return {
        "X-Gateway-Token": os.environ["INTERNAL_SERVICE_TOKEN"],
        "X-User-Id": str(uuid.uuid4()),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "Admin",
        "X-Permissions": "fees:read,fees:write",
    }


# Pick an endpoint that's guarded by auth. /api/v1/fees/invoices is the
# read path most exercised; if it works as expected, the dependency is
# wired correctly.
TARGET = "/api/v1/fees/invoices"


class TestDirectAccessRejected:

    def test_no_headers_at_all(self, client):
        r = client.get(TARGET)
        assert r.status_code == 401

    def test_missing_gateway_token(self, client, gateway_headers):
        headers = {k: v for k, v in gateway_headers.items() if k != "X-Gateway-Token"}
        r = client.get(TARGET, headers=headers)
        assert r.status_code == 401
        assert "Direct service access denied" in r.json().get("detail", "")

    def test_wrong_gateway_token(self, client, gateway_headers):
        headers = {**gateway_headers, "X-Gateway-Token": "this-is-not-the-real-token"}
        r = client.get(TARGET, headers=headers)
        assert r.status_code == 401

    def test_missing_user_id(self, client, gateway_headers):
        headers = {k: v for k, v in gateway_headers.items() if k != "X-User-Id"}
        r = client.get(TARGET, headers=headers)
        assert r.status_code == 401

    def test_missing_school_id(self, client, gateway_headers):
        headers = {k: v for k, v in gateway_headers.items() if k != "X-School-Id"}
        r = client.get(TARGET, headers=headers)
        assert r.status_code == 401


class TestValidGatewayCallReachesRoute:

    def test_valid_headers_dont_401(self, client, gateway_headers):
        r = client.get(TARGET, headers=gateway_headers)
        # The route may legitimately return 200 (empty list), 400, or 422
        # depending on query params. The ONLY status we're asserting NOT
        # to see is 401 — that would mean auth blocked the request.
        assert r.status_code != 401
