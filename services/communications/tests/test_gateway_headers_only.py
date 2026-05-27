"""PH3 / BUG-007: prove direct calls (no gateway headers) are rejected.

Mirror of the finance integrity test, scoped to a communications
endpoint. Asserts only the auth outcome.
"""
import os
import uuid

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION-32chars-min-len-XXXX")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token-DO-NOT-USE-IN-PRODUCTION")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_comms_headers.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def db_tables():
    """Spin a fresh in-memory DB so the happy-path test can reach routes."""
    from app.database import Base, get_db
    # Touch model modules so Base.metadata sees them.
    from app.models import communication as _c  # noqa
    from app.models import idempotency as _i  # noqa
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
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def gateway_headers():
    return {
        "X-Gateway-Token": os.environ["INTERNAL_SERVICE_TOKEN"],
        "X-User-Id": str(uuid.uuid4()),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "Admin",
    }


TARGET = "/api/v1/comm/announcements"


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
        headers = {**gateway_headers, "X-Gateway-Token": "not-the-real-token"}
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
        assert r.status_code != 401
