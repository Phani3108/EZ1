"""PH3 / BUG-007: prove direct calls (no gateway headers) are rejected.

Academics is the largest surface — many routes are guarded by RBAC at
the gateway, but the underlying dependency in
`app/dependencies.py:get_current_user` is what we're validating here:
that the new shared `get_actor_context` is wired up and refuses requests
without `X-Gateway-Token`.

We hit a representative read endpoint per domain (school, student,
attendance, reports) so a regression in one router's dependency wiring
gets caught.
"""
import os
import uuid

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_headers.db")
os.environ.setdefault("REPORTING_DATABASE_URL", "sqlite:///./test_academics_reporting.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def db_tables():
    """In-memory academics DB + projection DB. Lets the happy-path test
    reach the route layer without an OperationalError."""
    from app.database import Base, get_db
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models.projections import ProjectionBase
    import app.reporting_db as rdb
    from app.main import app

    a_eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    r_eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=a_eng)
    ProjectionBase.metadata.create_all(bind=r_eng)

    ASession = sessionmaker(autocommit=False, autoflush=False, bind=a_eng)
    RSession = sessionmaker(autocommit=False, autoflush=False, bind=r_eng)
    rdb._engine = r_eng
    rdb._ReportingSession = RSession

    def _override_a():
        s = ASession()
        try:
            yield s
        finally:
            s.close()

    def _override_r():
        s = RSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_a
    app.dependency_overrides[rdb.get_reporting_db] = _override_r
    yield
    app.dependency_overrides.clear()
    a_eng.dispose()
    r_eng.dispose()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def gateway_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN", "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(uuid.uuid4()),
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": "Admin",
    }


# A read endpoint per major router family — each known to exist with
# minimal request-shape requirements so a 401 vs non-401 status is the
# only signal we're checking.
TARGETS = [
    "/api/v1/schools/current",
    "/api/v1/students",
    "/api/v1/attendance/daily",
    "/api/v1/reports/dashboard",
]


@pytest.mark.parametrize("target", TARGETS)
class TestDirectAccessRejected:

    def test_no_headers_at_all(self, client, target):
        r = client.get(target)
        assert r.status_code == 401, f"{target} returned {r.status_code}"

    def test_missing_gateway_token(self, client, gateway_headers, target):
        headers = {k: v for k, v in gateway_headers.items() if k != "X-Gateway-Token"}
        r = client.get(target, headers=headers)
        assert r.status_code == 401, f"{target} returned {r.status_code}"

    def test_wrong_gateway_token(self, client, gateway_headers, target):
        headers = {**gateway_headers, "X-Gateway-Token": "not-the-real-token"}
        r = client.get(target, headers=headers)
        assert r.status_code == 401, f"{target} returned {r.status_code}"


@pytest.mark.parametrize("target", TARGETS)
def test_valid_gateway_call_does_not_401(client, gateway_headers, target):
    r = client.get(target, headers=gateway_headers)
    # The route may legitimately return 200, 400, 404, 422 depending on
    # query/params. The only status we MUST NOT see is 401 — that would
    # mean auth blocked a valid gateway-routed request.
    assert r.status_code != 401, f"{target} unexpectedly 401'd with valid headers"
