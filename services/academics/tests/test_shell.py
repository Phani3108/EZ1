"""academics service — smoke tests.

PH2-5 introduced this file as a /health + authz-stub check on an empty shell.
PH2-6 kept the smoke tests; the "shell phase" assertion moved off /health
onto /health/phase. PH2-8 implemented `is_teacher_authorized_for_class`.
PH2-9 implemented the remaining two: `is_teacher_authorized_for_student`
and `is_parent_authorized_for_student`. **No authz function in academics
still raises `NotImplementedError`.** Behavioural correctness for each one
is covered by `TestPH28TeacherAuthInProcess` (PH2-8, in test_attendance.py)
and `TestPH29StudentScopedAuth` (PH2-9, in test_authz_in_process.py).
"""
import os

# Required env: config.py declares JWT_SECRET_KEY / INTERNAL_SERVICE_TOKEN
# without defaults; tests/__init__.py also calls setdefault, but be explicit
# here so this file works when run in isolation.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION-32chars-min-len-XXXX",
)
os.environ.setdefault(
    "INTERNAL_SERVICE_TOKEN",
    "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
)
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_smoke.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "academics"


def test_health_phase_reports_current_phase():
    resp = client.get("/health/phase")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "academics"
    # Phase string changes per merge step; just assert it's there.
    assert "phase" in data
    assert "PH2" in data["phase"]


def test_no_authorization_function_still_stubs():
    """PH2-9: every authz function in `services/authorization.py` is now
    implemented. If anyone re-introduces a NotImplementedError stub for
    one of these in a future refactor, this test catches it.
    """
    from app.services import authorization as az
    import inspect
    import uuid

    # Each callable in the module that's a public function (no underscore prefix)
    # and accepts a db_session-like parameter should not raise NotImplementedError
    # when called with sentinel uuids + a no-op `db_session=None` if it's
    # implementation-free. We assert by source-inspection instead — the body of
    # each public function MUST NOT contain `raise NotImplementedError`.
    expected = {
        "is_teacher_authorized_for_class",
        "is_teacher_authorized_for_student",
        "is_parent_authorized_for_student",
    }
    for name in expected:
        fn = getattr(az, name)
        src = inspect.getsource(fn)
        assert "raise NotImplementedError" not in src, (
            f"{name} regressed to a stub; PH2-8/PH2-9 implementations were lost"
        )
