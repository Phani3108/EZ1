"""Phase 15a — Onboarding readiness + Go Live tests."""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_onboarding.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SCHOOL_A = uuid.uuid4()
ADMIN_A = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    import app.models  # noqa

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
        "X-User-Id": str(ADMIN_A),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "SchoolAdmin",
        "X-Permissions": "school:manage,student:write,student:read",
    }


def _seed_minimal_school(SessionLocal):
    from app.models.school import School
    s = SessionLocal()
    try:
        s.add(School(id=SCHOOL_A, name="Harare Central", country="ZW",
                     timezone="Africa/Harare", is_active=True))
        s.commit()
    finally:
        s.close()


def _seed_terms(SessionLocal, n=1):
    from app.models.school import AcademicYear, Term
    s = SessionLocal()
    try:
        ay = AcademicYear(
            id=uuid.uuid4(), school_id=SCHOOL_A, name="2026",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            is_active=True,
        )
        s.add(ay)
        s.flush()
        for i in range(n):
            s.add(Term(
                id=uuid.uuid4(), school_id=SCHOOL_A,
                academic_year_id=ay.id, name=f"T{i+1}",
                start_date=date(2026, 1 + 4 * i, 1),
                end_date=date(2026, 4 + 4 * i, 1),
            ))
        s.commit()
    finally:
        s.close()


def _seed_classes_and_subjects(SessionLocal, n_classes=1, n_subjects=1):
    from app.models.school import Class, Subject
    s = SessionLocal()
    try:
        for i in range(n_classes):
            s.add(Class(id=uuid.uuid4(), school_id=SCHOOL_A,
                        name=f"Form {i+1}", section="A"))
        for i in range(n_subjects):
            s.add(Subject(id=uuid.uuid4(), school_id=SCHOOL_A,
                          name=f"Subject {i+1}", code=f"SUB{i+1}"))
        s.commit()
    finally:
        s.close()


def _seed_students(SessionLocal, n=1):
    from app.models.student import Student, StudentStatus
    s = SessionLocal()
    try:
        for i in range(n):
            s.add(Student(
                id=uuid.uuid4(), school_id=SCHOOL_A,
                student_code=f"S-{i+1:03d}",
                first_name=f"Stu{i}", last_name="Test",
                dob=date(2010, 1, 1),
                status=StudentStatus.ACTIVE.value,
            ))
        s.commit()
    finally:
        s.close()


def _seed_teacher_assignment(SessionLocal, teacher_id=None):
    from app.models.school import AcademicYear, Class, ClassTeacherAssignment
    s = SessionLocal()
    try:
        # Use the existing AY if seeded; else seed one.
        ay = s.query(AcademicYear).filter(
            AcademicYear.school_id == SCHOOL_A).first()
        if not ay:
            ay = AcademicYear(
                id=uuid.uuid4(), school_id=SCHOOL_A, name="2026",
                start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                is_active=True,
            )
            s.add(ay)
            s.flush()
        cls = s.query(Class).filter(Class.school_id == SCHOOL_A).first()
        if not cls:
            cls = Class(id=uuid.uuid4(), school_id=SCHOOL_A,
                        name="F1", section="A")
            s.add(cls)
            s.flush()
        s.add(ClassTeacherAssignment(
            id=uuid.uuid4(), school_id=SCHOOL_A,
            class_id=cls.id,
            teacher_user_id=teacher_id or uuid.uuid4(),
            academic_year_id=ay.id,
        ))
        s.commit()
    finally:
        s.close()


def _seed_parent_invite(SessionLocal, dispatched=False):
    from app.models.onboarding import InviteRequest
    s = SessionLocal()
    try:
        ir = InviteRequest(
            id=uuid.uuid4(), school_id=SCHOOL_A,
            role="Parent", full_name="Mai Test",
            contact_phone="+263770000099",
            requested_by_user_id=ADMIN_A,
            request_status=("dispatched" if dispatched else "pending"),
        )
        s.add(ir)
        s.commit()
    finally:
        s.close()


def _seed_first_attendance(SessionLocal):
    from app.models.attendance import AttendanceRecord
    from app.models.student import Student
    s = SessionLocal()
    try:
        st = s.query(Student).filter(Student.school_id == SCHOOL_A).first()
        s.add(AttendanceRecord(
            id=uuid.uuid4(), school_id=SCHOOL_A,
            student_id=st.id, class_id=uuid.uuid4(),
            date=date.today(), status="P", period_number=0,
            marked_by_user_id=ADMIN_A,
        ))
        s.commit()
    finally:
        s.close()


class TestStatusEmptySchool:
    def test_all_red_when_empty(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        r = client.get("/api/v1/onboarding/status", headers=_admin_headers())
        d = r.json()["data"]
        statuses = {c["step"]: c["status"] for c in d["checklist"]}
        # school_profile is amber (basics ok, no terms); rest are red.
        assert statuses["school_profile"] == "amber"
        assert statuses["classes"] == "red"
        assert statuses["subjects"] == "red"
        assert statuses["teachers"] == "red"
        assert statuses["students"] == "red"
        assert statuses["parents_invited"] == "red"
        assert statuses["first_attendance"] == "red"
        assert d["go_live_eligible"] is False
        assert d["school_is_live"] is False
        assert set(d["go_live_blockers"]) >= {
            "classes", "subjects", "teachers", "students",
            "parents_invited", "first_attendance",
        }


class TestStatusProgression:
    def test_full_green_unlocks_go_live(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        _seed_terms(SL, n=3)
        _seed_classes_and_subjects(SL, n_classes=1, n_subjects=1)
        _seed_students(SL, n=5)
        _seed_teacher_assignment(SL)
        _seed_parent_invite(SL, dispatched=True)
        _seed_first_attendance(SL)

        r = client.get("/api/v1/onboarding/status", headers=_admin_headers())
        d = r.json()["data"]
        statuses = {c["step"]: c["status"] for c in d["checklist"]}
        assert statuses["school_profile"] == "green"
        assert statuses["classes"] == "green"
        assert statuses["subjects"] == "green"
        # Single teacher → amber (we'd prefer ≥2 but 1 unblocks).
        assert statuses["teachers"] in ("green", "amber")
        assert statuses["students"] == "green"
        assert statuses["parents_invited"] == "green"
        assert statuses["first_attendance"] == "green"
        assert d["go_live_eligible"] is True
        assert d["go_live_blockers"] == []

    def test_pending_parent_invite_is_amber(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        _seed_parent_invite(SL, dispatched=False)
        r = client.get("/api/v1/onboarding/status", headers=_admin_headers())
        statuses = {c["step"]: c["status"] for c in r.json()["data"]["checklist"]}
        assert statuses["parents_invited"] == "amber"


class TestGoLive:
    def test_blocked_when_not_eligible(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        r = client.post("/api/v1/onboarding/go-live",
                        headers=_admin_headers())
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NOT_READY"

    def test_flips_when_eligible(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        _seed_terms(SL, n=1)
        _seed_classes_and_subjects(SL)
        _seed_students(SL, n=1)
        _seed_teacher_assignment(SL)
        _seed_parent_invite(SL, dispatched=True)
        _seed_first_attendance(SL)
        r = client.post("/api/v1/onboarding/go-live",
                        headers=_admin_headers())
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["is_live"] is True
        # Audit row.
        from app.models.audit import AuditLog
        s = SL()
        try:
            audit = s.query(AuditLog).filter(
                AuditLog.event_type == "school.went_live").first()
            assert audit is not None
            blob = _json.dumps({"target": audit.target,
                                "details": audit.details or "{}"})
            assert "checklist_snapshot_hash" in blob
        finally:
            s.close()

    def test_rejected_when_already_live(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_minimal_school(SL)
        _seed_terms(SL)
        _seed_classes_and_subjects(SL)
        _seed_students(SL)
        _seed_teacher_assignment(SL)
        _seed_parent_invite(SL, dispatched=True)
        _seed_first_attendance(SL)
        client.post("/api/v1/onboarding/go-live", headers=_admin_headers())
        r = client.post("/api/v1/onboarding/go-live", headers=_admin_headers())
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "ALREADY_LIVE"
