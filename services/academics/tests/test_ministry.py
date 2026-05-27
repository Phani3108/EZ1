"""Phase 14 / M-001 + M-002 tests.

Ministry surface invariants (DEC-013):
  * Non-Ministry role is rejected with 403 even if the gateway lets the
    request through (defence-in-depth route-layer gate).
  * Aggregation queries CORRECTLY span multiple schools — the school-id
    scoping the rest of the service applies is deliberately broken here.
  * Audit log per call contains ONLY scope + endpoint + row-count.
    No school names, no district names, no actor names, no IDs.
  * No POST/PUT/DELETE verbs anywhere under /api/v1/ministry — 405.
"""
from __future__ import annotations

import json as _json
import os
import uuid
from datetime import date, timedelta

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_ministry.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


MINISTRY_ACTOR = uuid.uuid4()
ADMIN_ACTOR = uuid.uuid4()


@pytest.fixture
def engine_and_session():
    from app.database import Base
    from app.models import school as _s   # noqa
    from app.models import student as _st  # noqa
    from app.models import attendance as _a  # noqa
    from app.models import audit as _au  # noqa
    from app.models import compliance as _co  # noqa

    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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


def _headers(role: str, perms: str = "ministry:read"):
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN",
            "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(MINISTRY_ACTOR if role == "Ministry" else ADMIN_ACTOR),
        # Ministry actors carry no school-id; the gateway still injects
        # something. Tests use a sentinel to prove route ignores it.
        "X-School-Id": str(uuid.uuid4()),
        "X-User-Roles": role,
        "X-Permissions": perms,
    }


def _seed_geography_and_schools(SessionLocal):
    from app.models.school import Province, District, School
    from app.models.student import Student, StudentStatus
    from app.models.attendance import AttendanceRecord

    s = SessionLocal()
    try:
        prov_hre = Province(code="HRE", name="Harare", region="Metro", capital="Harare")
        prov_byo = Province(code="BYO", name="Bulawayo", region="Metro", capital="Bulawayo")
        s.add_all([prov_hre, prov_byo])
        d1 = District(code="hre-cn", name="Harare Central", province_code="HRE")
        d2 = District(code="byo-cn", name="Bulawayo Central", province_code="BYO")
        s.add_all([d1, d2])
        sch1 = School(id=uuid.uuid4(), name="School A",
                      province_code="HRE", district_code="hre-cn",
                      school_type="PRIMARY", is_active=True)
        sch2 = School(id=uuid.uuid4(), name="School B",
                      province_code="HRE", district_code="hre-cn",
                      school_type="SECONDARY", is_active=True)
        sch3 = School(id=uuid.uuid4(), name="School C",
                      province_code="BYO", district_code="byo-cn",
                      school_type="COMBINED", is_active=True)
        s.add_all([sch1, sch2, sch3])
        s.flush()
        # Students: 3 in A, 2 in B, 4 in C
        for i in range(3):
            s.add(Student(id=uuid.uuid4(), school_id=sch1.id,
                          student_code=f"A{i}", first_name="X",
                          last_name=f"S{i}", dob=date(2010, 1, 1),
                          gender="M", status=StudentStatus.ACTIVE.value))
        for i in range(2):
            s.add(Student(id=uuid.uuid4(), school_id=sch2.id,
                          student_code=f"B{i}", first_name="X",
                          last_name=f"S{i}", dob=date(2008, 1, 1),
                          gender="F", status=StudentStatus.ACTIVE.value))
        for i in range(4):
            s.add(Student(id=uuid.uuid4(), school_id=sch3.id,
                          student_code=f"C{i}", first_name="X",
                          last_name=f"S{i}", dob=date(2009, 1, 1),
                          gender="M", status=StudentStatus.ACTIVE.value))
        # 1 graduated student in A — should NOT count as active
        s.add(Student(id=uuid.uuid4(), school_id=sch1.id,
                      student_code="AG", first_name="X", last_name="Grad",
                      dob=date(2002, 1, 1), gender="F",
                      status=StudentStatus.GRADUATED.value))

        # Flush so the subsequent Student.query calls see the inserted rows
        # (session has autoflush=False).
        s.flush()

        # Attendance — 7 P + 3 A in sch1 today, all P in sch3 today.
        today = date.today()
        ids_a = s.query(Student).filter(Student.school_id == sch1.id).all()
        for i, st in enumerate(ids_a[:3]):
            s.add(AttendanceRecord(
                id=uuid.uuid4(), school_id=sch1.id, student_id=st.id,
                class_id=uuid.uuid4(), date=today,
                status="P" if i < 2 else "A", period_number=0,
                marked_by_user_id=uuid.uuid4(),
            ))
        ids_c = s.query(Student).filter(Student.school_id == sch3.id).all()
        for st in ids_c:
            s.add(AttendanceRecord(
                id=uuid.uuid4(), school_id=sch3.id, student_id=st.id,
                class_id=uuid.uuid4(), date=today,
                status="P", period_number=0,
                marked_by_user_id=uuid.uuid4(),
            ))

        s.commit()
        return {
            "sch1": str(sch1.id), "sch2": str(sch2.id), "sch3": str(sch3.id),
        }
    finally:
        s.close()


class TestMinistryAuthGate:
    def test_non_ministry_role_forbidden(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        # SchoolAdmin tries to hit a ministry endpoint with the right
        # permission string (simulating a misconfigured gateway). The
        # route-layer gate must reject anyway.
        r = client.get(
            "/api/v1/ministry/schools",
            headers=_headers("SchoolAdmin", perms="ministry:read"),
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "FORBIDDEN"

    def test_no_write_verbs(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        # POST/PUT/DELETE under /ministry must 404/405 — no such routes.
        r = client.post(
            "/api/v1/ministry/schools",
            headers=_headers("Ministry"), json={},
        )
        assert r.status_code in (404, 405)


class TestMinistryEnrolment:
    def test_national_counts_active_only(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/enrolment?scope=national",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["schools"] == 3
        # 3 + 2 + 4 = 9, graduated student excluded
        assert data["students"] == 9

    def test_province_rollup(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/enrolment?scope=province",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        by_code = {row["province_code"]: row for row in data}
        assert by_code["HRE"]["schools"] == 2
        assert by_code["HRE"]["students"] == 5     # 3 + 2
        assert by_code["BYO"]["schools"] == 1
        assert by_code["BYO"]["students"] == 4

    def test_district_rollup(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/enrolment?scope=district",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        by_code = {row["district_code"]: row for row in data}
        assert by_code["hre-cn"]["schools"] == 2
        assert by_code["hre-cn"]["students"] == 5
        assert by_code["byo-cn"]["schools"] == 1
        assert by_code["byo-cn"]["students"] == 4

    def test_invalid_scope(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/enrolment?scope=galaxy",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_SCOPE"


class TestMinistryAttendance:
    def test_national_rate(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/attendance?scope=national&days=7",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        # 2 P + 1 A in sch1, plus 4 P in sch3 = 7 records, 6 present.
        assert data["records"] == 7
        assert data["present"] == 6
        assert data["rate"] == round(6 / 7, 4)

    def test_province_rates(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/attendance?scope=province&days=7",
            headers=_headers("Ministry"),
        )
        rows = {row["province_code"]: row for row in r.json()["data"]}
        # HRE: 2 P / 3 records, BYO: 4 P / 4 records
        assert rows["HRE"]["records"] == 3
        assert rows["HRE"]["present"] == 2
        assert rows["BYO"]["records"] == 4
        assert rows["BYO"]["rate"] == 1.0


class TestMinistryGeography:
    def test_returns_provinces_and_districts(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        r = client.get(
            "/api/v1/ministry/geography",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert {p["code"] for p in data["provinces"]} == {"HRE", "BYO"}
        assert {d["code"] for d in data["districts"]} == {"hre-cn", "byo-cn"}


class TestMinistryDropouts:
    """M-005: dropout / inactive student heatmap."""

    def _seed_dropouts(self, SessionLocal, sch_ids):
        """Add some INACTIVE / TRANSFERRED students. Should appear in
        dropouts but not in active counts."""
        from app.models.student import Student, StudentStatus
        sch1 = uuid.UUID(sch_ids["sch1"])
        sch2 = uuid.UUID(sch_ids["sch2"])
        s = SessionLocal()
        try:
            # sch1: 1 INACTIVE student
            s.add(Student(
                id=uuid.uuid4(), school_id=sch1,
                student_code="A-D1", first_name="X", last_name="D1",
                dob=date(2010, 1, 1), gender="M",
                status=StudentStatus.INACTIVE.value,
            ))
            # sch2: 2 TRANSFERRED students
            for i in range(2):
                s.add(Student(
                    id=uuid.uuid4(), school_id=sch2,
                    student_code=f"B-T{i}", first_name="X",
                    last_name=f"T{i}", dob=date(2009, 1, 1),
                    gender="F",
                    status=StudentStatus.TRANSFERRED.value,
                ))
            s.commit()
        finally:
            s.close()

    def test_district_dropout_rate(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_dropouts(SL, sch)
        r = client.get(
            "/api/v1/ministry/dropouts?scope=district",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 200
        rows = {row["district_code"]: row for row in r.json()["data"]}
        # hre-cn has sch1 (3 active + 1 INACTIVE) + sch2 (2 active + 2 TRANS)
        hre = rows["hre-cn"]
        assert hre["active"] == 5
        assert hre["dropouts"] == 3
        assert hre["dropout_rate"] == round(3 / 8, 4)
        # byo-cn has sch3 (4 active, 0 dropouts)
        byo = rows["byo-cn"]
        assert byo["active"] == 4
        assert byo["dropouts"] == 0
        assert byo["dropout_rate"] == 0.0

    def test_graduated_excluded(self, client, engine_and_session):
        _, SL = engine_and_session
        # Seed only includes one GRADUATED student in sch1; this test
        # confirms graduated is NOT counted as a dropout.
        sch = _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/dropouts?scope=national",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        # 9 active, 0 dropouts (graduated AG doesn't count).
        assert data["active"] == 9
        assert data["dropouts"] == 0
        assert data["dropout_rate"] == 0.0


class TestMinistryPassRate:
    """M-006: subject pass-rate by region."""

    def _seed_marks(self, SessionLocal, sch_ids):
        from app.models.school import Subject, AcademicYear, Term, Class
        from app.models.assessment import Assessment, Mark
        from app.models.student import Student

        sch1 = uuid.UUID(sch_ids["sch1"])
        sch3 = uuid.UUID(sch_ids["sch3"])
        s = SessionLocal()
        try:
            # Two subjects (one per school — code is per-school).
            # Subject uses UUID(as_uuid=True) for id/school_id.
            sub_a = Subject(
                id=uuid.uuid4(), school_id=sch1,
                name="Mathematics", code="MATH",
            )
            sub_c = Subject(
                id=uuid.uuid4(), school_id=sch3,
                name="Mathematics", code="MATH",
            )
            s.add_all([sub_a, sub_c])
            # Minimal AY/term/class — values aren't asserted
            ay = AcademicYear(
                id=uuid.uuid4(), school_id=sch1,
                name="2026", start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31), is_active=True,
            )
            term = Term(
                id=uuid.uuid4(), school_id=sch1,
                academic_year_id=ay.id, name="T1",
                start_date=date(2026, 1, 1), end_date=date(2026, 4, 1),
            )
            cls_a = Class(
                id=uuid.uuid4(), school_id=sch1,
                name="Form 1", section="A",
            )
            cls_c = Class(
                id=uuid.uuid4(), school_id=sch3,
                name="Form 1", section="A",
            )
            s.add_all([ay, term, cls_a, cls_c])
            s.flush()
            # Assessment uses UUID_STR (String(36)) for id/school_id/etc.
            asmt_a = Assessment(
                id=str(uuid.uuid4()), school_id=str(sch1),
                academic_year_id=str(ay.id), term_id=str(term.id),
                class_id=str(cls_a.id), subject_id=str(sub_a.id),
                name="Mid-term", assessment_type="TEST",
                date=date(2026, 3, 1), max_marks=100,
                created_by=str(uuid.uuid4()),
            )
            asmt_c = Assessment(
                id=str(uuid.uuid4()), school_id=str(sch3),
                academic_year_id=str(ay.id), term_id=str(term.id),
                class_id=str(cls_c.id), subject_id=str(sub_c.id),
                name="Mid-term", assessment_type="TEST",
                date=date(2026, 3, 1), max_marks=100,
                created_by=str(uuid.uuid4()),
            )
            s.add_all([asmt_a, asmt_c])
            s.flush()
            # 3 marks in sch1: 70, 40, absent. → 1 pass / 2 graded.
            stu_a = (
                s.query(Student)
                .filter(Student.school_id == sch1).all()[:3]
            )
            for st, score, absent in zip(
                stu_a, [70, 40, None], [False, False, True],
            ):
                s.add(Mark(
                    id=str(uuid.uuid4()), school_id=str(sch1),
                    assessment_id=asmt_a.id, student_id=str(st.id),
                    marks=score, is_absent=absent,
                    graded_by=str(uuid.uuid4()),
                ))
            # 2 marks in sch3: 80, 90. → 2/2 = 100%
            stu_c = (
                s.query(Student)
                .filter(Student.school_id == sch3).all()[:2]
            )
            for st, score in zip(stu_c, [80, 90]):
                s.add(Mark(
                    id=str(uuid.uuid4()), school_id=str(sch3),
                    assessment_id=asmt_c.id, student_id=str(st.id),
                    marks=score, is_absent=False,
                    graded_by=str(uuid.uuid4()),
                ))
            s.commit()
        finally:
            s.close()

    def test_province_pass_rate(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_marks(SL, sch)
        r = client.get(
            "/api/v1/ministry/pass-rate?scope=province",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        # HRE has sch1's mid-term → 1 pass / 2 graded.
        # BYO has sch3's mid-term → 2 pass / 2 graded.
        by_prov = {row["province_code"]: row for row in data}
        assert by_prov["HRE"]["graded"] == 2
        assert by_prov["HRE"]["passes"] == 1
        assert by_prov["HRE"]["pass_rate"] == 0.5
        assert by_prov["BYO"]["graded"] == 2
        assert by_prov["BYO"]["passes"] == 2
        assert by_prov["BYO"]["pass_rate"] == 1.0


class TestMinistryPTR:
    """M-007: pupil:teacher ratio (placeholder for full resource view)."""

    def _seed_teachers(self, SessionLocal, sch_ids):
        from app.models.school import AcademicYear, Class, ClassTeacherAssignment
        sch1 = uuid.UUID(sch_ids["sch1"])
        sch2 = uuid.UUID(sch_ids["sch2"])
        sch3 = uuid.UUID(sch_ids["sch3"])
        s = SessionLocal()
        try:
            ay = AcademicYear(
                id=uuid.uuid4(), school_id=sch1,
                name="2026", start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31), is_active=True,
            )
            cls1 = Class(id=uuid.uuid4(), school_id=sch1,
                         name="F1", section="A")
            cls2 = Class(id=uuid.uuid4(), school_id=sch2,
                         name="F1", section="A")
            cls3 = Class(id=uuid.uuid4(), school_id=sch3,
                         name="F1", section="A")
            s.add_all([ay, cls1, cls2, cls3])
            s.flush()
            t1, t2, t3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            s.add(ClassTeacherAssignment(
                id=uuid.uuid4(), school_id=sch1,
                class_id=cls1.id, teacher_user_id=t1,
                academic_year_id=ay.id,
            ))
            s.add(ClassTeacherAssignment(
                id=uuid.uuid4(), school_id=sch2,
                class_id=cls2.id, teacher_user_id=t2,
                academic_year_id=ay.id,
            ))
            s.add(ClassTeacherAssignment(
                id=uuid.uuid4(), school_id=sch3,
                class_id=cls3.id, teacher_user_id=t3,
                academic_year_id=ay.id,
            ))
            s.commit()
        finally:
            s.close()

    def test_district_ptr(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_teachers(SL, sch)
        r = client.get(
            "/api/v1/ministry/ptr?scope=district",
            headers=_headers("Ministry"),
        )
        rows = {row["district_code"]: row for row in r.json()["data"]}
        # hre-cn: 5 active students (sch1=3 + sch2=2), 2 teachers.
        assert rows["hre-cn"]["active_students"] == 5
        assert rows["hre-cn"]["teachers"] == 2
        assert rows["hre-cn"]["ptr"] == 2.5
        # byo-cn: 4 active students, 1 teacher → 4.0
        assert rows["byo-cn"]["ptr"] == 4.0

    def test_devices_and_electricity_placeholders(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_teachers(SL, sch)
        r = client.get(
            "/api/v1/ministry/ptr?scope=national",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        # Stable contract: placeholder fields exist but are null.
        assert "devices_per_school" in data
        assert data["devices_per_school"] is None
        assert data["electricity_coverage"] is None


class TestMinistryCompliance:
    """M-004: cross-school compliance dashboard."""

    def _seed_compliance(self, SessionLocal, sch_ids):
        from app.models.compliance import (
            ComplianceReportTemplate, ComplianceReportSubmission,
        )
        s = SessionLocal()
        try:
            # Two templates (each `school_id`-scoped, but template
            # CODES are shared by convention — e.g., the Ministry
            # "ANNUAL_STAT_RETURN" template exists per school).
            tpl_a1 = ComplianceReportTemplate(
                school_id=sch_ids["sch1"],
                code="ANNUAL_STAT_RETURN",
                title="Annual Statistical Return",
                cadence="annual",
                created_by_user_id=str(uuid.uuid4()),
            )
            tpl_b1 = ComplianceReportTemplate(
                school_id=sch_ids["sch2"],
                code="ANNUAL_STAT_RETURN",
                title="Annual Statistical Return",
                cadence="annual",
                created_by_user_id=str(uuid.uuid4()),
            )
            s.add_all([tpl_a1, tpl_b1])
            s.flush()
            # sch1 submitted, sch2 only draft.
            s.add(ComplianceReportSubmission(
                school_id=sch_ids["sch1"],
                template_id=tpl_a1.id,
                period_label="2026",
                status="submitted",
                payload_json="{}",
            ))
            s.add(ComplianceReportSubmission(
                school_id=sch_ids["sch2"],
                template_id=tpl_b1.id,
                period_label="2026",
                status="draft",
                payload_json="{}",
            ))
            s.commit()
        finally:
            s.close()

    def test_compliance_rollup(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_compliance(SL, sch)
        r = client.get(
            "/api/v1/ministry/compliance",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        # Two rows expected — one per (school, template).
        assert len(data) == 2
        by_school = {row["school_id"]: row for row in data}
        assert by_school[sch["sch1"]]["submitted"] == 1
        assert by_school[sch["sch1"]]["draft"] == 0
        assert by_school[sch["sch1"]]["total"] == 1
        assert by_school[sch["sch2"]]["draft"] == 1
        assert by_school[sch["sch2"]]["submitted"] == 0
        # Template title is non-PII Ministry text — included.
        assert by_school[sch["sch1"]]["template_code"] == "ANNUAL_STAT_RETURN"

    def test_compliance_filtered_by_period(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_compliance(SL, sch)
        r = client.get(
            "/api/v1/ministry/compliance?period_label=2025",
            headers=_headers("Ministry"),
        )
        # No 2025 data seeded — empty list.
        assert r.json()["data"] == []


class TestMinistryComparative:
    """M-008: per-school side-by-side comparative view."""

    def test_returns_one_row_per_school(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/comparative",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        assert len(data) == 3
        labels = {row["label"] for row in data}
        assert {"School A", "School B", "School C"} <= labels

    def test_anonymize_strips_school_id_and_name(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/comparative?anonymize=true",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        for row in data:
            assert row["school_id"] is None
            assert row["label"].startswith("School-")
        # Pseudonyms are unique:
        pseudonyms = [row["label"] for row in data]
        assert len(set(pseudonyms)) == len(pseudonyms)

    def test_filter_by_district(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/comparative?district_code=byo-cn",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["label"] == "School C"


class TestMinistryPolicyImpact:
    """M-009: before/after policy impact."""

    def test_attendance_before_after(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_geography_and_schools(SL)
        before_start = (date.today() - timedelta(days=60)).isoformat()
        before_end = (date.today() - timedelta(days=30)).isoformat()
        after_start = (date.today() - timedelta(days=30)).isoformat()
        after_end = (date.today() + timedelta(days=1)).isoformat()
        r = client.get(
            f"/api/v1/ministry/policy-impact?metric=attendance_rate"
            f"&before_start={before_start}&before_end={before_end}"
            f"&after_start={after_start}&after_end={after_end}",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        # Seed inserts attendance records dated today — they fall in the
        # "after" window only.
        assert data["before"]["n"] == 0
        assert data["after"]["n"] == 7
        # Before was empty → delta should be null (not 0 — there's no
        # baseline to compare against).
        assert data["before"]["value"] is None
        assert data["delta"] is None
        # After: 6 P / 7 total = ~0.857
        assert data["after"]["value"] == round(6 / 7, 4)

    def test_invalid_metric(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/policy-impact?metric=galactic_score"
            "&before_start=2026-01-01&before_end=2026-02-01"
            "&after_start=2026-02-01&after_end=2026-03-01",
            headers=_headers("Ministry"),
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_METRIC"


class TestMinistryDonors:
    """M-010: donor / NGO impact rollup."""

    def _seed_sponsorships(self, SessionLocal, sch_ids):
        from app.models.community import Sponsor, Sponsorship
        s = SessionLocal()
        try:
            sp1 = Sponsor(
                id=str(uuid.uuid4()), school_id=sch_ids["sch1"],
                name="Acme Foundation", sponsor_type="ngo",
                created_by_user_id=str(uuid.uuid4()),
            )
            sp2 = Sponsor(
                id=str(uuid.uuid4()), school_id=sch_ids["sch3"],
                name="Beta Trust", sponsor_type="company",
                created_by_user_id=str(uuid.uuid4()),
            )
            s.add_all([sp1, sp2])
            s.flush()
            # sch1: $1000 committed, $400 received.
            s.add(Sponsorship(
                id=str(uuid.uuid4()), school_id=sch_ids["sch1"],
                sponsor_id=sp1.id, purpose="scholarships",
                committed_cents=100000, received_cents=40000,
                currency="USD", status="active",
                created_by_user_id=str(uuid.uuid4()),
            ))
            # sch3: $500 committed, $500 received.
            s.add(Sponsorship(
                id=str(uuid.uuid4()), school_id=sch_ids["sch3"],
                sponsor_id=sp2.id, purpose="infrastructure",
                committed_cents=50000, received_cents=50000,
                currency="USD", status="active",
                created_by_user_id=str(uuid.uuid4()),
            ))
            s.commit()
        finally:
            s.close()

    def test_national_donors(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_sponsorships(SL, sch)
        r = client.get(
            "/api/v1/ministry/donors?scope=national",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        assert data["sponsorships"] == 2
        assert data["committed"] == 1500.0
        assert data["received"] == 900.0
        assert data["fulfilment_rate"] == round(900 / 1500, 4)

    def test_province_donors(self, client, engine_and_session):
        _, SL = engine_and_session
        sch = _seed_geography_and_schools(SL)
        self._seed_sponsorships(SL, sch)
        r = client.get(
            "/api/v1/ministry/donors?scope=province",
            headers=_headers("Ministry"),
        )
        rows = {row["province_code"]: row for row in r.json()["data"]}
        # HRE = sch1 only (sch2 has no sponsorship)
        assert rows["HRE"]["committed"] == 1000.0
        assert rows["HRE"]["received"] == 400.0
        # BYO = sch3
        assert rows["BYO"]["committed"] == 500.0
        assert rows["BYO"]["fulfilment_rate"] == 1.0


class TestMinistryExports:
    """M-011: UNESCO/UNICEF export snapshot."""

    def test_returns_canonical_shape(self, client, engine_and_session):
        _, SL = engine_and_session
        _seed_geography_and_schools(SL)
        r = client.get(
            "/api/v1/ministry/exports/unesco?year=2026",
            headers=_headers("Ministry"),
        )
        data = r.json()["data"]
        # Top-level keys are the stable contract.
        assert set(data.keys()) >= {
            "country_code", "reporting_year", "schools", "enrolment",
            "teachers", "attendance", "dropouts", "generated_at",
        }
        assert data["country_code"] == "ZW"
        assert data["reporting_year"] == 2026
        assert data["schools"]["total"] == 3
        assert data["enrolment"]["total_active"] == 9
        # by_province must include both seeded provinces.
        provs = {p["province_code"] for p in data["enrolment"]["by_province"]}
        assert "HRE" in provs
        assert "BYO" in provs


class TestMinistryAuditNoPII:
    """ADR 018: Ministry reads must NOT log school names, district
    names, province names, or any actor PII in the audit row."""

    def test_audit_logs_only_scope_and_counts(self, client, engine_and_session):
        _, SessionLocal = engine_and_session
        _seed_geography_and_schools(SessionLocal)
        # Hit each endpoint at least once.
        client.get("/api/v1/ministry/schools",
                   headers=_headers("Ministry"))
        client.get("/api/v1/ministry/enrolment?scope=national",
                   headers=_headers("Ministry"))
        client.get("/api/v1/ministry/attendance?scope=province&days=7",
                   headers=_headers("Ministry"))
        client.get("/api/v1/ministry/geography",
                   headers=_headers("Ministry"))

        from app.models.audit import AuditLog
        s = SessionLocal()
        try:
            rows = (
                s.query(AuditLog)
                .filter(AuditLog.event_type.like("ministry.%"))
                .all()
            )
            # 4 events expected
            assert len(rows) >= 4
            for row in rows:
                blob = _json.dumps({"target": row.target,
                                    "details": row.details or {}})
                # No school names, no district names, no province names
                # (the names live only in DB rows, not in audit details).
                assert "School A" not in blob
                assert "School B" not in blob
                assert "School C" not in blob
                assert "Harare Central" not in blob
                assert "Bulawayo Central" not in blob
                # Phase 14 contract: details payload is the endpoint
                # event name + the row count integer.
                assert "endpoint" in (row.details or {})
                assert "rows" in (row.details or {})
        finally:
            s.close()
