"""Tests for the PH8-4 per-school + parent self-service export endpoints.

These are integration tests against the FastAPI app — they spin a
real in-memory academics DB, seed two schools' worth of data, then
call the export endpoints and verify the returned ZIPs contain the
right CSVs scoped to the right tenant.

The KEY invariant being checked: school B's data MUST NOT appear in
school A's export, and parent X's export MUST NOT contain any
non-linked child.
"""
from __future__ import annotations

import csv
import io
import json
import os
import uuid
import zipfile
from datetime import date

import pytest

# Required env BEFORE app.config import. Use file-backed SQLite (not
# :memory:) because :memory: forces SingletonThreadPool which doesn't
# accept the pool_size args app.database uses.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_export_academics.db")
os.environ.setdefault("REPORTING_DATABASE_URL", "sqlite:///./test_export_reporting.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
PARENT_A_USER = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s  # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import assessment as _as  # noqa

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


@pytest.fixture
def seeded(engine_and_session):
    """Seed two schools with parallel data, and link a parent to one
    of School A's students."""
    _, SessionLocal = engine_and_session
    from app.models.school import School, Province
    from app.models.student import Student, Parent, StudentParent
    from app.models.attendance import AttendanceRecord

    session = SessionLocal()
    try:
        prov = Province(name="Harare", code="HRE", region="Northern",
                        capital="Harare")
        session.add(prov)
        session.flush()
        session.add_all([
            School(id=SCHOOL_A, name="School A", province_code=prov.code),
            School(id=SCHOOL_B, name="School B", province_code=prov.code),
        ])
        session.flush()

        # School A students
        a_kid_1 = Student(
            school_id=SCHOOL_A, student_code="A001",
            first_name="Anna", last_name="A",
            dob=date(2012, 5, 15), gender="FEMALE",
        )
        a_kid_2 = Student(
            school_id=SCHOOL_A, student_code="A002",
            first_name="Alex", last_name="A",
            dob=date(2012, 7, 1), gender="MALE",
        )
        # School B student
        b_kid = Student(
            school_id=SCHOOL_B, student_code="B001",
            first_name="Bob", last_name="B",
            dob=date(2013, 1, 1), gender="MALE",
        )
        session.add_all([a_kid_1, a_kid_2, b_kid])
        session.flush()

        # Parent linked only to a_kid_1
        parent_a = Parent(
            school_id=SCHOOL_A, user_id=PARENT_A_USER,
            first_name="Pam", last_name="A",
            phone="+263771111111", relationship_type="MOTHER",
        )
        session.add(parent_a)
        session.flush()
        session.add(StudentParent(
            school_id=SCHOOL_A,
            student_id=a_kid_1.id, parent_id=parent_a.id,
            is_primary=True,
        ))

        # Some attendance for both schools
        class_a = uuid.uuid4()
        class_b = uuid.uuid4()
        session.add_all([
            AttendanceRecord(school_id=SCHOOL_A, student_id=a_kid_1.id,
                             class_id=class_a, date=date(2026, 3, 1), status="P"),
            AttendanceRecord(school_id=SCHOOL_A, student_id=a_kid_2.id,
                             class_id=class_a, date=date(2026, 3, 1), status="A"),
            AttendanceRecord(school_id=SCHOOL_B, student_id=b_kid.id,
                             class_id=class_b, date=date(2026, 3, 1), status="P"),
        ])
        session.commit()

        return {
            "a_kid_1_id": a_kid_1.id,
            "a_kid_2_id": a_kid_2.id,
            "b_kid_id": b_kid.id,
            "parent_a_id": parent_a.id,
        }
    finally:
        session.close()


# ─── Helpers ─────────────────────────────────────────────────────


def _gateway_headers_school_admin(school_id):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(uuid.uuid4()),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Admin",
        "X-Permissions": "school:manage",
    }


def _gateway_headers_parent(user_id, school_id):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(user_id),
        "X-School-Id": str(school_id),
        "X-User-Roles": "Parent",
    }


def _extract_zip(content: bytes) -> dict[str, str]:
    zf = zipfile.ZipFile(io.BytesIO(content))
    return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


def _csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# ─── School admin export ─────────────────────────────────────────


class TestSchoolExport:

    def test_export_returns_zip(self, client, seeded):
        r = client.get("/api/v1/schools/me/export",
                       headers=_gateway_headers_school_admin(SCHOOL_A))
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"

    def test_export_contains_manifest(self, client, seeded):
        r = client.get("/api/v1/schools/me/export",
                       headers=_gateway_headers_school_admin(SCHOOL_A))
        files = _extract_zip(r.content)
        assert "manifest.json" in files
        manifest = json.loads(files["manifest.json"])
        assert manifest["school_id"] == str(SCHOOL_A)
        assert manifest["schema_version"] == 1
        assert "row_counts" in manifest

    def test_export_contains_students_csv(self, client, seeded):
        r = client.get("/api/v1/schools/me/export",
                       headers=_gateway_headers_school_admin(SCHOOL_A))
        files = _extract_zip(r.content)
        assert "students.csv" in files
        students = _csv_rows(files["students.csv"])
        # Exactly 2 students for School A — NOT 3 (school B's student excluded).
        assert len(students) == 2
        codes = {s["student_code"] for s in students}
        assert codes == {"A001", "A002"}

    def test_export_isolates_school_a_from_school_b(self, client, seeded):
        r_a = client.get("/api/v1/schools/me/export",
                         headers=_gateway_headers_school_admin(SCHOOL_A))
        r_b = client.get("/api/v1/schools/me/export",
                         headers=_gateway_headers_school_admin(SCHOOL_B))

        files_a = _extract_zip(r_a.content)
        files_b = _extract_zip(r_b.content)

        a_codes = {s["student_code"] for s in _csv_rows(files_a["students.csv"])}
        b_codes = {s["student_code"] for s in _csv_rows(files_b["students.csv"])}

        assert "A001" in a_codes and "A002" in a_codes
        assert "B001" not in a_codes        # ← cross-tenant isolation
        assert "B001" in b_codes
        assert "A001" not in b_codes and "A002" not in b_codes

    def test_attendance_in_export_is_school_scoped(self, client, seeded):
        r = client.get("/api/v1/schools/me/export",
                       headers=_gateway_headers_school_admin(SCHOOL_A))
        files = _extract_zip(r.content)
        rows = _csv_rows(files["attendance.csv"])
        # School A had 2 attendance rows. School B's row must not appear.
        assert len(rows) == 2
        for row in rows:
            assert row["school_id"] == str(SCHOOL_A)


# ─── Parent self-service export ───────────────────────────────────


class TestParentExport:

    def test_parent_export_returns_zip(self, client, seeded):
        r = client.get("/api/v1/parents/me/export",
                       headers=_gateway_headers_parent(PARENT_A_USER, SCHOOL_A))
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"

    def test_parent_sees_only_their_linked_child(self, client, seeded):
        r = client.get("/api/v1/parents/me/export",
                       headers=_gateway_headers_parent(PARENT_A_USER, SCHOOL_A))
        files = _extract_zip(r.content)
        assert "children.csv" in files
        kids = _csv_rows(files["children.csv"])
        # Parent A is linked to ONE child (a_kid_1), not BOTH school-A kids.
        assert len(kids) == 1
        assert kids[0]["student_code"] == "A001"

    def test_parent_attendance_scoped_to_linked_children(self, client, seeded):
        r = client.get("/api/v1/parents/me/export",
                       headers=_gateway_headers_parent(PARENT_A_USER, SCHOOL_A))
        files = _extract_zip(r.content)
        rows = _csv_rows(files["attendance.csv"])
        # Only a_kid_1's attendance — not a_kid_2's, not b_kid's.
        assert len(rows) == 1
        assert rows[0]["student_id"] == str(seeded["a_kid_1_id"])

    def test_parent_not_found_returns_empty_manifest(self, client, seeded):
        """If the user_id doesn't match any Parent row for this school,
        the export returns a manifest with PARENT_NOT_FOUND."""
        stranger = uuid.uuid4()
        r = client.get("/api/v1/parents/me/export",
                       headers=_gateway_headers_parent(stranger, SCHOOL_A))
        assert r.status_code == 200
        files = _extract_zip(r.content)
        manifest = json.loads(files["manifest.json"])
        assert manifest.get("error") == "PARENT_NOT_FOUND"
