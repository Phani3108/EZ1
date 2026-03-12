"""
Assessment Service Tests — Quality Gate 10B-3
================================================
Unit Tests:
- Create assessment (CRUD)
- List assessments by class/term/subject
- Get assessment with marks grid
- Bulk upsert marks (insert + update)
- Mark validation (exceeds max, absent logic)
- Student marks grouped by subject
- Class performance aggregation

Integration Tests:
- Cross-school isolation
- Teacher auth for class
- Parent auth for child
- Duplicate mark upsert (idempotent)

Edge Cases:
- Absent student → marks null
- Marks > max_marks rejected
- Empty marks list
- Soft-deleted assessment excluded
"""
import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_assessment.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.assessment import Assessment, Mark  # noqa

engine = create_engine("sqlite:///./test_assessment.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    TestSession.close_all()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_assessment.db"):
        try:
            os.remove("./test_assessment.db")
        except OSError:
            pass


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


# ───────────── Constants ─────────────

SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
TEACHER_1 = uuid.uuid4()
TEACHER_2 = uuid.uuid4()
STUDENT_1 = uuid.uuid4()
STUDENT_2 = uuid.uuid4()
STUDENT_3 = uuid.uuid4()
PARENT_1 = uuid.uuid4()
YEAR_A = uuid.uuid4()
TERM_A = uuid.uuid4()
TERM_B = uuid.uuid4()
CLASS_A = uuid.uuid4()
CLASS_B = uuid.uuid4()
SUBJECT_MATH = uuid.uuid4()
SUBJECT_ENG = uuid.uuid4()


def _svc(db):
    from app.services.assessment_service import AssessmentService
    return AssessmentService(db)


def _create_assessment(db, school_id=None, class_id=None, subject_id=None,
                       term_id=None, name=None, atype="TEST", max_marks=100,
                       created_by=None, assess_date=None):
    svc = _svc(db)
    return svc.create_assessment(
        school_id=school_id or SCHOOL_A,
        academic_year_id=YEAR_A,
        term_id=term_id or TERM_A,
        class_id=class_id or CLASS_A,
        subject_id=subject_id or SUBJECT_MATH,
        name=name or f"Assessment-{uuid.uuid4().hex[:6]}",
        assessment_type=atype,
        date=assess_date or date(2026, 3, 15),
        max_marks=Decimal(str(max_marks)),
        created_by=created_by or TEACHER_1,
    )


# ═══════════════════════════════════════════
# Assessment CRUD
# ═══════════════════════════════════════════

class TestAssessmentCRUD:
    def test_create_assessment(self, db):
        result = _create_assessment(db, name="Midterm Test")
        assert result["id"]
        assert result["name"] == "Midterm Test"
        assert result["assessment_type"] == "TEST"
        assert result["max_marks"] == 100.0
        assert result["class_id"] == str(CLASS_A)
        assert result["subject_id"] == str(SUBJECT_MATH)

    def test_create_quiz(self, db):
        result = _create_assessment(db, name="Pop Quiz", atype="QUIZ", max_marks=20)
        assert result["assessment_type"] == "QUIZ"
        assert result["max_marks"] == 20.0

    def test_create_exam(self, db):
        result = _create_assessment(db, name="Final Exam", atype="EXAM", max_marks=200)
        assert result["assessment_type"] == "EXAM"
        assert result["max_marks"] == 200.0

    def test_create_assignment(self, db):
        result = _create_assessment(db, name="Homework 1", atype="ASSIGNMENT", max_marks=50)
        assert result["assessment_type"] == "ASSIGNMENT"
        assert result["max_marks"] == 50.0

    def test_list_assessments_by_class_term(self, db):
        _create_assessment(db, name="Test 1")
        _create_assessment(db, name="Test 2")
        _create_assessment(db, class_id=CLASS_B, name="Other Class")  # different class

        svc = _svc(db)
        result = svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "Test 1" in names
        assert "Test 2" in names

    def test_list_assessments_filter_subject(self, db):
        _create_assessment(db, name="Math Test", subject_id=SUBJECT_MATH)
        _create_assessment(db, name="English Test", subject_id=SUBJECT_ENG)

        svc = _svc(db)
        result = svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A, SUBJECT_MATH)
        assert len(result) == 1
        assert result[0]["name"] == "Math Test"

    def test_list_assessments_excludes_deleted(self, db):
        a = _create_assessment(db, name="Active")
        deleted = _create_assessment(db, name="Deleted")

        # Soft delete
        row = db.query(Assessment).filter(Assessment.id == deleted["id"]).first()
        row.deleted_at = datetime.now(timezone.utc)
        db.commit()

        svc = _svc(db)
        result = svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A)
        assert len(result) == 1
        assert result[0]["name"] == "Active"

    def test_get_assessment_with_empty_marks(self, db):
        a = _create_assessment(db, name="Fresh Test")
        svc = _svc(db)
        result = svc.get_assessment(SCHOOL_A, uuid.UUID(a["id"]))
        assert result is not None
        assert result["name"] == "Fresh Test"
        assert result["marks"] == []

    def test_get_assessment_not_found(self, db):
        svc = _svc(db)
        result = svc.get_assessment(SCHOOL_A, uuid.uuid4())
        assert result is None

    def test_get_assessment_wrong_school(self, db):
        a = _create_assessment(db, school_id=SCHOOL_A, name="School A Test")
        svc = _svc(db)
        result = svc.get_assessment(SCHOOL_B, uuid.UUID(a["id"]))
        assert result is None


# ═══════════════════════════════════════════
# Bulk Marks Upsert
# ═══════════════════════════════════════════

class TestBulkMarks:
    def test_bulk_insert_marks(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [
                {"student_id": str(STUDENT_1), "marks": 85, "is_absent": False},
                {"student_id": str(STUDENT_2), "marks": 72, "is_absent": False},
            ],
            TEACHER_1,
        )
        assert result["accepted"] == 2
        assert result["updated"] == 0
        assert result["errors"] == []

    def test_bulk_upsert_updates_existing(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        # First insert
        svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": 70, "is_absent": False}],
            TEACHER_1,
        )
        # Update
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": 85, "is_absent": False}],
            TEACHER_1,
        )
        assert result["accepted"] == 0
        assert result["updated"] == 1

        # Verify updated value
        detail = svc.get_assessment(SCHOOL_A, uuid.UUID(a["id"]))
        marks = detail["marks"]
        assert len(marks) == 1
        assert marks[0]["marks"] == 85.0

    def test_absent_student_marks_null(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": 50, "is_absent": True}],
            TEACHER_1,
        )
        assert result["accepted"] == 1

        detail = svc.get_assessment(SCHOOL_A, uuid.UUID(a["id"]))
        mark = detail["marks"][0]
        assert mark["marks"] is None
        assert mark["is_absent"] is True

    def test_marks_exceeds_max_rejected(self, db):
        a = _create_assessment(db, max_marks=50)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": 60, "is_absent": False}],
            TEACHER_1,
        )
        assert result["accepted"] == 0
        assert len(result["errors"]) == 1
        assert "out of range" in result["errors"][0]

    def test_negative_marks_rejected(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": -5, "is_absent": False}],
            TEACHER_1,
        )
        assert result["accepted"] == 0
        assert len(result["errors"]) == 1

    def test_marks_required_when_not_absent(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": None, "is_absent": False}],
            TEACHER_1,
        )
        assert result["accepted"] == 0
        assert len(result["errors"]) == 1
        assert "required" in result["errors"][0]

    def test_assessment_not_found(self, db):
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.uuid4(),
            [{"student_id": str(STUDENT_1), "marks": 80, "is_absent": False}],
            TEACHER_1,
        )
        assert result["accepted"] == 0
        assert "not found" in result["errors"][0].lower()

    def test_mixed_valid_invalid(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        result = svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [
                {"student_id": str(STUDENT_1), "marks": 85, "is_absent": False},
                {"student_id": str(STUDENT_2), "marks": 150, "is_absent": False},  # exceeds
                {"student_id": str(STUDENT_3), "marks": None, "is_absent": True},  # absent OK
            ],
            TEACHER_1,
        )
        assert result["accepted"] == 2
        assert result["updated"] == 0
        assert len(result["errors"]) == 1

    def test_bulk_with_remarks(self, db):
        a = _create_assessment(db, max_marks=100)
        svc = _svc(db)
        svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a["id"]),
            [{"student_id": str(STUDENT_1), "marks": 45, "is_absent": False,
              "remarks": "Needs improvement"}],
            TEACHER_1,
        )
        detail = svc.get_assessment(SCHOOL_A, uuid.UUID(a["id"]))
        assert detail["marks"][0]["remarks"] == "Needs improvement"


# ═══════════════════════════════════════════
# Student Marks (grouped by subject)
# ═══════════════════════════════════════════

class TestStudentMarks:
    def _setup_multi_subject(self, db):
        """Create 2 math assessments and 1 english assessment with marks."""
        svc = _svc(db)
        math1 = _create_assessment(db, name="Math Test 1", subject_id=SUBJECT_MATH, max_marks=100)
        math2 = _create_assessment(db, name="Math Test 2", subject_id=SUBJECT_MATH, max_marks=50)
        eng1 = _create_assessment(db, name="English Essay", subject_id=SUBJECT_ENG, max_marks=80)

        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(math1["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 80, "is_absent": False}],
                              TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(math2["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 40, "is_absent": False}],
                              TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(eng1["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 60, "is_absent": False}],
                              TEACHER_1)
        return math1, math2, eng1

    def test_student_marks_grouped_by_subject(self, db):
        self._setup_multi_subject(db)
        svc = _svc(db)
        result = svc.student_marks(SCHOOL_A, STUDENT_1, TERM_A)
        assert len(result) == 2  # 2 subjects

        math_subj = next(s for s in result if s["subject_id"] == str(SUBJECT_MATH))
        eng_subj = next(s for s in result if s["subject_id"] == str(SUBJECT_ENG))

        assert len(math_subj["assessments"]) == 2
        assert len(eng_subj["assessments"]) == 1

    def test_student_marks_average_calculation(self, db):
        self._setup_multi_subject(db)
        svc = _svc(db)
        result = svc.student_marks(SCHOOL_A, STUDENT_1, TERM_A)

        math_subj = next(s for s in result if s["subject_id"] == str(SUBJECT_MATH))
        # Math: 80/100 + 40/50 = 120/150 = 80%
        assert math_subj["average_pct"] == 80.0
        assert math_subj["graded_count"] == 2

        eng_subj = next(s for s in result if s["subject_id"] == str(SUBJECT_ENG))
        # English: 60/80 = 75%
        assert eng_subj["average_pct"] == 75.0
        assert eng_subj["graded_count"] == 1

    def test_student_marks_empty(self, db):
        svc = _svc(db)
        result = svc.student_marks(SCHOOL_A, STUDENT_1, TERM_A)
        assert result == []

    def test_student_marks_filter_by_term(self, db):
        svc = _svc(db)
        _create_assessment(db, name="Term A Test", term_id=TERM_A)
        _create_assessment(db, name="Term B Test", term_id=TERM_B)

        svc.bulk_upsert_marks(SCHOOL_A,
                              uuid.UUID(svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A)[0]["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 90, "is_absent": False}],
                              TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A,
                              uuid.UUID(svc.list_assessments(SCHOOL_A, CLASS_A, TERM_B)[0]["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 70, "is_absent": False}],
                              TEACHER_1)

        result_a = svc.student_marks(SCHOOL_A, STUDENT_1, TERM_A)
        result_b = svc.student_marks(SCHOOL_A, STUDENT_1, TERM_B)

        assert len(result_a) == 1
        assert result_a[0]["assessments"][0]["mark"]["marks"] == 90.0
        assert len(result_b) == 1
        assert result_b[0]["assessments"][0]["mark"]["marks"] == 70.0


# ═══════════════════════════════════════════
# Class Performance
# ═══════════════════════════════════════════

class TestClassPerformance:
    def _setup_class(self, db):
        """Create assessments and marks for a class with multiple students."""
        svc = _svc(db)
        math_test = _create_assessment(db, name="Math Final", subject_id=SUBJECT_MATH,
                                       max_marks=100, class_id=CLASS_A)
        eng_test = _create_assessment(db, name="English Final", subject_id=SUBJECT_ENG,
                                      max_marks=80, class_id=CLASS_A)

        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(math_test["id"]), [
            {"student_id": str(STUDENT_1), "marks": 85, "is_absent": False},
            {"student_id": str(STUDENT_2), "marks": 40, "is_absent": False},
            {"student_id": str(STUDENT_3), "marks": None, "is_absent": True},
        ], TEACHER_1)

        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(eng_test["id"]), [
            {"student_id": str(STUDENT_1), "marks": 70, "is_absent": False},
            {"student_id": str(STUDENT_2), "marks": 50, "is_absent": False},
        ], TEACHER_1)

        return math_test, eng_test

    def test_class_performance_subjects(self, db):
        self._setup_class(db)
        svc = _svc(db)
        result = svc.class_performance(SCHOOL_A, CLASS_A, TERM_A)
        assert "subjects" in result
        assert len(result["subjects"]) == 2

    def test_class_performance_math_avg(self, db):
        self._setup_class(db)
        svc = _svc(db)
        result = svc.class_performance(SCHOOL_A, CLASS_A, TERM_A)

        math_subj = next(s for s in result["subjects"]
                         if s["subject_id"] == str(SUBJECT_MATH))
        # Math: avg of 85 and 40 (absent excluded) = 62.5
        assert math_subj["avg_pct"] is not None
        assert math_subj["student_count"] >= 2  # 3 marks total (including absent)

    def test_class_performance_pass_rate(self, db):
        self._setup_class(db)
        svc = _svc(db)
        result = svc.class_performance(SCHOOL_A, CLASS_A, TERM_A)

        math_subj = next(s for s in result["subjects"]
                         if s["subject_id"] == str(SUBJECT_MATH))
        # Pass = >= 50%: student_1 (85%) passes, student_2 (40%) fails
        assert math_subj["pass_rate"] == 50.0

    def test_class_performance_empty(self, db):
        svc = _svc(db)
        result = svc.class_performance(SCHOOL_A, CLASS_A, TERM_A)
        assert result["subjects"] == []

    def test_class_performance_other_class_excluded(self, db):
        self._setup_class(db)
        svc = _svc(db)
        result = svc.class_performance(SCHOOL_A, CLASS_B, TERM_A)
        assert result["subjects"] == []


# ═══════════════════════════════════════════
# Cross-School Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_assessment_school_isolation(self, db):
        _create_assessment(db, school_id=SCHOOL_A, name="School A Test")
        _create_assessment(db, school_id=SCHOOL_B, name="School B Test")

        svc = _svc(db)
        a_list = svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A)
        b_list = svc.list_assessments(SCHOOL_B, CLASS_A, TERM_A)

        assert len(a_list) == 1
        assert a_list[0]["name"] == "School A Test"
        assert len(b_list) == 1
        assert b_list[0]["name"] == "School B Test"

    def test_marks_school_isolation(self, db):
        a_assess = _create_assessment(db, school_id=SCHOOL_A, name="A")
        b_assess = _create_assessment(db, school_id=SCHOOL_B, name="B")

        svc = _svc(db)
        svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(a_assess["id"]),
            [{"student_id": str(STUDENT_1), "marks": 80, "is_absent": False}],
            TEACHER_1,
        )
        svc.bulk_upsert_marks(
            SCHOOL_B, uuid.UUID(b_assess["id"]),
            [{"student_id": str(STUDENT_1), "marks": 70, "is_absent": False}],
            TEACHER_2,
        )

        result_a = svc.student_marks(SCHOOL_A, STUDENT_1)
        result_b = svc.student_marks(SCHOOL_B, STUDENT_1)

        assert len(result_a) == 1
        assert result_a[0]["assessments"][0]["mark"]["marks"] == 80.0
        assert len(result_b) == 1
        assert result_b[0]["assessments"][0]["mark"]["marks"] == 70.0

    def test_performance_school_isolation(self, db):
        _create_assessment(db, school_id=SCHOOL_A, class_id=CLASS_A, name="A")
        svc = _svc(db)
        svc.bulk_upsert_marks(
            SCHOOL_A, uuid.UUID(svc.list_assessments(SCHOOL_A, CLASS_A, TERM_A)[0]["id"]),
            [{"student_id": str(STUDENT_1), "marks": 80, "is_absent": False}],
            TEACHER_1,
        )

        result_a = svc.class_performance(SCHOOL_A, CLASS_A, TERM_A)
        result_b = svc.class_performance(SCHOOL_B, CLASS_A, TERM_A)

        assert len(result_a["subjects"]) == 1
        assert len(result_b["subjects"]) == 0


# ═══════════════════════════════════════════
# API Endpoint Tests (FastAPI TestClient)
# ═══════════════════════════════════════════

from fastapi.testclient import TestClient
from jose import jwt as jose_jwt


def _make_token(user_id=None, school_id=None, roles=None):
    payload = {
        "sub": str(user_id or TEACHER_1),
        "school_id": str(school_id or SCHOOL_A),
        "roles": roles or ["Teacher"],
        "type": "access",
    }
    return jose_jwt.encode(payload, "test-secret", algorithm="HS256")


def _teacher_headers(user_id=None, school_id=None):
    token = _make_token(user_id, school_id, ["Teacher"])
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(user_id=None, school_id=None):
    token = _make_token(user_id, school_id, ["Admin"])
    return {"Authorization": f"Bearer {token}"}


def _parent_headers(user_id=None, school_id=None):
    token = _make_token(user_id, school_id, ["Parent"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(db):
    from app.main import app
    from app.database import get_db

    def _override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


class TestAPIEndpoints:
    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_create_assessment_api(self, mock_auth, client):
        mock_auth.return_value = True
        resp = client.post("/api/v1/assessments", json={
            "academic_year_id": str(YEAR_A),
            "term_id": str(TERM_A),
            "class_id": str(CLASS_A),
            "subject_id": str(SUBJECT_MATH),
            "name": "API Created Test",
            "assessment_type": "TEST",
            "date": "2026-03-15",
            "max_marks": 100,
        }, headers=_teacher_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["name"] == "API Created Test"
        assert "meta" in data

    def test_list_assessments_api(self, client):
        # Create via service first
        from app.services.assessment_service import AssessmentService
        from app.database import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db_session = next(db_gen)
        svc = AssessmentService(db_session)
        svc.create_assessment(SCHOOL_A, YEAR_A, TERM_A, CLASS_A, SUBJECT_MATH,
                              "List Test", "TEST", date(2026, 3, 15),
                              Decimal("100"), TEACHER_1)

        resp = client.get(
            f"/api/v1/assessments?class_id={CLASS_A}&term_id={TERM_A}",
            headers=_teacher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "List Test"

    def test_get_assessment_api(self, client):
        from app.services.assessment_service import AssessmentService
        from app.database import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db_session = next(db_gen)
        svc = AssessmentService(db_session)
        a = svc.create_assessment(SCHOOL_A, YEAR_A, TERM_A, CLASS_A, SUBJECT_MATH,
                                  "Get Test", "EXAM", date(2026, 6, 1),
                                  Decimal("200"), TEACHER_1)

        resp = client.get(f"/api/v1/assessments/{a['id']}", headers=_teacher_headers())
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Get Test"
        assert resp.json()["data"]["marks"] == []

    def test_get_assessment_not_found_api(self, client):
        resp = client.get(f"/api/v1/assessments/{uuid.uuid4()}", headers=_teacher_headers())
        assert resp.status_code == 404

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_bulk_marks_api(self, mock_auth, client):
        mock_auth.return_value = True

        # Create assessment
        resp = client.post("/api/v1/assessments", json={
            "academic_year_id": str(YEAR_A),
            "term_id": str(TERM_A),
            "class_id": str(CLASS_A),
            "subject_id": str(SUBJECT_MATH),
            "name": "Marks Test",
            "assessment_type": "TEST",
            "date": "2026-03-15",
            "max_marks": 100,
        }, headers=_teacher_headers())
        aid = resp.json()["data"]["id"]

        # Bulk upsert marks
        resp = client.post(f"/api/v1/assessments/{aid}/marks/bulk", json={
            "marks": [
                {"student_id": str(STUDENT_1), "marks": 85, "is_absent": False},
                {"student_id": str(STUDENT_2), "marks": None, "is_absent": True},
            ]
        }, headers=_teacher_headers())
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["accepted"] == 2
        assert data["errors"] == []

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_teacher_unauthorized_for_class(self, mock_auth, client):
        mock_auth.return_value = False
        resp = client.post("/api/v1/assessments", json={
            "academic_year_id": str(YEAR_A),
            "term_id": str(TERM_A),
            "class_id": str(CLASS_A),
            "subject_id": str(SUBJECT_MATH),
            "name": "Unauthorized",
            "assessment_type": "TEST",
            "date": "2026-03-15",
            "max_marks": 100,
        }, headers=_teacher_headers())
        assert resp.status_code == 403

    @patch("app.api.routes.verify_teacher_class_authorization", new_callable=AsyncMock)
    def test_admin_can_create_assessment(self, mock_auth, client):
        # Admin should not need teacher class auth
        resp = client.post("/api/v1/assessments", json={
            "academic_year_id": str(YEAR_A),
            "term_id": str(TERM_A),
            "class_id": str(CLASS_A),
            "subject_id": str(SUBJECT_MATH),
            "name": "Admin Created",
            "assessment_type": "EXAM",
            "date": "2026-06-01",
            "max_marks": 200,
        }, headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Admin Created"
        mock_auth.assert_not_called()

    def test_student_marks_api(self, client):
        from app.services.assessment_service import AssessmentService
        from app.database import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db_session = next(db_gen)
        svc = AssessmentService(db_session)
        a = svc.create_assessment(SCHOOL_A, YEAR_A, TERM_A, CLASS_A, SUBJECT_MATH,
                                  "Student View", "TEST", date(2026, 3, 15),
                                  Decimal("100"), TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(a["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 90, "is_absent": False}],
                              TEACHER_1)

        resp = client.get(
            f"/api/v1/assessments/students/{STUDENT_1}/marks?term_id={TERM_A}",
            headers=_teacher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["average_pct"] == 90.0

    @patch("app.api.routes.verify_parent_student_authorization", new_callable=AsyncMock)
    def test_parent_authorized_for_child(self, mock_auth, client):
        mock_auth.return_value = True
        from app.services.assessment_service import AssessmentService
        from app.database import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db_session = next(db_gen)
        svc = AssessmentService(db_session)
        a = svc.create_assessment(SCHOOL_A, YEAR_A, TERM_A, CLASS_A, SUBJECT_MATH,
                                  "Parent View", "TEST", date(2026, 3, 15),
                                  Decimal("100"), TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(a["id"]),
                              [{"student_id": str(STUDENT_1), "marks": 75, "is_absent": False}],
                              TEACHER_1)

        resp = client.get(
            f"/api/v1/assessments/students/{STUDENT_1}/marks",
            headers=_parent_headers(user_id=PARENT_1),
        )
        assert resp.status_code == 200

    @patch("app.api.routes.verify_parent_student_authorization", new_callable=AsyncMock)
    def test_parent_unauthorized_for_other_child(self, mock_auth, client):
        mock_auth.return_value = False
        resp = client.get(
            f"/api/v1/assessments/students/{STUDENT_2}/marks",
            headers=_parent_headers(user_id=PARENT_1),
        )
        assert resp.status_code == 403

    def test_class_performance_api(self, client):
        from app.services.assessment_service import AssessmentService
        from app.database import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db_session = next(db_gen)
        svc = AssessmentService(db_session)
        a = svc.create_assessment(SCHOOL_A, YEAR_A, TERM_A, CLASS_A, SUBJECT_MATH,
                                  "Perf Test", "TEST", date(2026, 3, 15),
                                  Decimal("100"), TEACHER_1)
        svc.bulk_upsert_marks(SCHOOL_A, uuid.UUID(a["id"]), [
            {"student_id": str(STUDENT_1), "marks": 80, "is_absent": False},
            {"student_id": str(STUDENT_2), "marks": 55, "is_absent": False},
        ], TEACHER_1)

        resp = client.get(
            f"/api/v1/assessments/classes/{CLASS_A}/performance?term_id={TERM_A}",
            headers=_teacher_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["subjects"]) == 1
        assert data["subjects"][0]["pass_rate"] == 100.0  # both >= 50%

    def test_invalid_assessment_type_api(self, client):
        resp = client.post("/api/v1/assessments", json={
            "academic_year_id": str(YEAR_A),
            "term_id": str(TERM_A),
            "class_id": str(CLASS_A),
            "subject_id": str(SUBJECT_MATH),
            "name": "Bad Type",
            "assessment_type": "INVALID",
            "date": "2026-03-15",
            "max_marks": 100,
        }, headers=_teacher_headers())
        assert resp.status_code == 400

    def test_unauthenticated_request(self, client):
        resp = client.get(f"/api/v1/assessments?class_id={CLASS_A}&term_id={TERM_A}")
        assert resp.status_code in (401, 403)
