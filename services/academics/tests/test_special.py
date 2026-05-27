"""Phase 13e tests: boarding rooms + assignments + multi-campus."""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_special.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()
STUDENT_A = uuid.uuid4()
STUDENT_B = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa
    from app.models import audit as _au  # noqa
    from app.models import comment_bank as _cb  # noqa
    from app.models import planning as _p  # noqa
    from app.models import student_life as _sl  # noqa
    from app.models import org as _o  # noqa
    from app.models import parent_life as _pl  # noqa
    from app.models import staff as _st2  # noqa
    from app.models import compliance as _co  # noqa
    from app.models import ops as _op  # noqa
    from app.models import community as _cm  # noqa
    from app.models import special as _sp  # noqa

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    yield eng, SessionLocal
    eng.dispose()


@pytest.fixture
def client(engine_and_session):
    _, SessionLocal = engine_and_session
    from app.database import get_db
    from app.main import app

    def _override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _admin_headers():
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(ADMIN_A), "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Admin", "X-Permissions": "school:manage",
    }


class TestBoarding:
    def test_room_then_assign_with_capacity(self, client):
        r = client.post(
            "/api/v1/boarding/rooms", headers=_admin_headers(),
            json={"room_code": "B-101",
                  "occupancy_kind": "boys",
                  "capacity": 2},
        )
        rid = r.json()["data"]["id"]
        # 1st assignment fits
        a1 = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": rid,
                  "student_id": str(STUDENT_A),
                  "starts_on": date.today().isoformat(),
                  "bed_label": "Bed 1"},
        )
        assert a1.status_code == 200
        # 2nd assignment fits
        a2 = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": rid,
                  "student_id": str(STUDENT_B),
                  "starts_on": date.today().isoformat(),
                  "bed_label": "Bed 2"},
        )
        assert a2.status_code == 200
        # 3rd is rejected (capacity)
        a3 = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": rid,
                  "student_id": str(uuid.uuid4()),
                  "starts_on": date.today().isoformat()},
        )
        assert a3.status_code == 409
        assert a3.json()["error"]["code"] == "ROOM_FULL"

    def test_student_cant_double_assign(self, client):
        r = client.post(
            "/api/v1/boarding/rooms", headers=_admin_headers(),
            json={"room_code": "B-200",
                  "occupancy_kind": "girls",
                  "capacity": 5},
        ).json()["data"]
        client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": r["id"],
                  "student_id": str(STUDENT_A),
                  "starts_on": date.today().isoformat()},
        )
        # 2nd assignment for same student → reject
        a2 = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": r["id"],
                  "student_id": str(STUDENT_A),
                  "starts_on": date.today().isoformat()},
        )
        assert a2.status_code == 409
        assert a2.json()["error"]["code"] == "ALREADY_ASSIGNED"

    def test_end_assignment_frees_capacity(self, client):
        r = client.post(
            "/api/v1/boarding/rooms", headers=_admin_headers(),
            json={"room_code": "B-300",
                  "occupancy_kind": "boys",
                  "capacity": 1},
        ).json()["data"]
        a = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": r["id"],
                  "student_id": str(STUDENT_A),
                  "starts_on": date.today().isoformat()},
        ).json()["data"]
        client.post(
            f"/api/v1/boarding/assignments/{a['id']}/end",
            headers=_admin_headers(),
            json={"ended_on": (date.today() + timedelta(days=30)).isoformat()},
        )
        # New student can now take the freed slot
        b = client.post(
            "/api/v1/boarding/assignments", headers=_admin_headers(),
            json={"room_id": r["id"],
                  "student_id": str(STUDENT_B),
                  "starts_on": date.today().isoformat()},
        )
        assert b.status_code == 200


class TestCampus:
    def test_primary_flips(self, client):
        c1 = client.post(
            "/api/v1/campuses", headers=_admin_headers(),
            json={"code": "MAIN", "name": "Main Campus",
                  "campus_type": "combined",
                  "is_primary": True},
        )
        c2 = client.post(
            "/api/v1/campuses", headers=_admin_headers(),
            json={"code": "ANNEX", "name": "Annex Campus",
                  "campus_type": "annex",
                  "is_primary": True},
        )
        assert c1.status_code == 200
        assert c2.status_code == 200
        l = client.get("/api/v1/campuses", headers=_admin_headers())
        primaries = [c for c in l.json()["data"] if c["is_primary"]]
        # Creating ANNEX as primary should have cleared MAIN's flag
        assert len(primaries) == 1
        assert primaries[0]["code"] == "ANNEX"

    def test_invalid_campus_type_rejected(self, client):
        r = client.post(
            "/api/v1/campuses", headers=_admin_headers(),
            json={"code": "X", "name": "X",
                  "campus_type": "playground"},
        )
        assert r.status_code == 400
