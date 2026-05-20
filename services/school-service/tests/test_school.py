"""
School Service Tests — Quality Gate 3
========================================
Tests cover:
- Academic year overlap rejected
- Term date outside year rejected  
- Duplicate class (name+section) rejected
- Duplicate subject code rejected
- Teacher assignment rejects duplicate (same class+year)
- Cross-school isolation verified
- Soft delete does not remove row
- Only one active academic year allowed
- Only one teacher per class per year
- Teacher can teach multiple classes (allowed)
"""
import os
import uuid
from datetime import date

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_school.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.school import (  # noqa
    School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment,
)

engine = create_engine("sqlite:///./test_school.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_school.db"):
        try:
            os.remove("./test_school.db")
        except OSError:
            pass


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
TEACHER_1 = uuid.uuid4()
TEACHER_2 = uuid.uuid4()


def _svc(db):
    from app.services.school_service import SchoolService
    return SchoolService(db)


# ═══════════════════════════════════════════
# Academic Year
# ═══════════════════════════════════════════

class TestAcademicYear:
    def test_create_academic_year(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.create_academic_year(SCHOOL_A, "2026",
                                           date(2026, 1, 1), date(2026, 12, 31))
        assert "id" in result
        assert result["name"] == "2026"

    def test_overlap_rejected(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.create_academic_year(SCHOOL_A, "2026",
                                  date(2026, 1, 1), date(2026, 12, 31))
        # Overlapping year
        result = svc.create_academic_year(SCHOOL_A, "2026b",
                                           date(2026, 6, 1), date(2027, 6, 30))
        assert "error" in result
        assert result["error"] == "OVERLAP"

    def test_non_overlapping_allowed(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.create_academic_year(SCHOOL_A, "2025",
                                  date(2025, 1, 1), date(2025, 12, 31))
        result = svc.create_academic_year(SCHOOL_A, "2026",
                                           date(2026, 1, 1), date(2026, 12, 31))
        assert "id" in result

    def test_invalid_dates_rejected(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.create_academic_year(SCHOOL_A, "Bad",
                                           date(2026, 12, 31), date(2026, 1, 1))
        assert result["error"] == "INVALID_DATES"

    def test_only_one_active_year(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        y1 = svc.create_academic_year(SCHOOL_A, "2025",
                                       date(2025, 1, 1), date(2025, 12, 31), is_active=True)
        y2 = svc.create_academic_year(SCHOOL_A, "2026",
                                       date(2026, 1, 1), date(2026, 12, 31), is_active=True)
        # y1 should have been deactivated
        years = svc.list_academic_years(SCHOOL_A)
        active = [y for y in years if y["is_active"]]
        assert len(active) == 1
        assert active[0]["name"] == "2026"


# ═══════════════════════════════════════════
# Term
# ═══════════════════════════════════════════

class TestTerm:
    def _setup_year(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        return svc, uuid.UUID(year["id"])

    def test_create_term(self, db):
        svc, year_id = self._setup_year(db)
        result = svc.create_term(SCHOOL_A, year_id, "Term 1",
                                  date(2026, 1, 15), date(2026, 4, 15))
        assert "id" in result
        assert result["name"] == "Term 1"

    def test_term_outside_year_rejected(self, db):
        svc, year_id = self._setup_year(db)
        result = svc.create_term(SCHOOL_A, year_id, "Bad Term",
                                  date(2025, 11, 1), date(2026, 2, 1))
        assert result["error"] == "OUTSIDE_YEAR"

    def test_term_end_exceeds_year_rejected(self, db):
        svc, year_id = self._setup_year(db)
        result = svc.create_term(SCHOOL_A, year_id, "Too Long",
                                  date(2026, 10, 1), date(2027, 2, 1))
        assert result["error"] == "OUTSIDE_YEAR"

    def test_overlapping_terms_rejected(self, db):
        svc, year_id = self._setup_year(db)
        svc.create_term(SCHOOL_A, year_id, "Term 1",
                          date(2026, 1, 15), date(2026, 4, 15))
        result = svc.create_term(SCHOOL_A, year_id, "Term 1b",
                                  date(2026, 3, 1), date(2026, 5, 30))
        assert result["error"] == "OVERLAP"

    def test_non_overlapping_terms_allowed(self, db):
        svc, year_id = self._setup_year(db)
        svc.create_term(SCHOOL_A, year_id, "Term 1",
                          date(2026, 1, 15), date(2026, 4, 15))
        result = svc.create_term(SCHOOL_A, year_id, "Term 2",
                                  date(2026, 5, 1), date(2026, 8, 15))
        assert "id" in result

    def test_term_wrong_year_rejected(self, db):
        svc, year_id = self._setup_year(db)
        fake_year = uuid.uuid4()
        result = svc.create_term(SCHOOL_A, fake_year, "Term 1",
                                  date(2026, 1, 15), date(2026, 4, 15))
        assert result["error"] == "NOT_FOUND"


# ═══════════════════════════════════════════
# Class
# ═══════════════════════════════════════════

class TestClass:
    def test_create_class(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.create_class(SCHOOL_A, "Grade 6", "A", capacity=40)
        assert result["name"] == "Grade 6"
        assert result["section"] == "A"
        assert result["capacity"] == 40

    def test_duplicate_class_rejected(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.create_class(SCHOOL_A, "Grade 6", "A")
        result = svc.create_class(SCHOOL_A, "Grade 6", "A")
        assert result["error"] == "DUPLICATE_CLASS"

    def test_same_name_different_section_allowed(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.create_class(SCHOOL_A, "Grade 6", "A")
        result = svc.create_class(SCHOOL_A, "Grade 6", "B")
        assert "id" in result

    def test_soft_delete_preserves_row(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        cls = svc.create_class(SCHOOL_A, "Grade 7", "A")
        svc.soft_delete_class(uuid.UUID(cls["id"]), SCHOOL_A)
        # Row still exists in DB
        row = db.query(Class).filter(Class.id == uuid.UUID(cls["id"])).first()
        assert row is not None
        assert row.is_active is False

    def test_soft_deleted_class_excluded_from_list(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        c1 = svc.create_class(SCHOOL_A, "Grade 6", "A")
        c2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        svc.soft_delete_class(uuid.UUID(c2["id"]), SCHOOL_A)
        classes, total = svc.list_classes(SCHOOL_A)
        assert total == 1
        assert classes[0]["name"] == "Grade 6"

    def test_pagination(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        for i in range(5):
            svc.create_class(SCHOOL_A, f"Grade {i+1}", "A")
        page1, total = svc.list_classes(SCHOOL_A, page=1, page_size=2)
        page2, _ = svc.list_classes(SCHOOL_A, page=2, page_size=2)
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2


# ═══════════════════════════════════════════
# Subject
# ═══════════════════════════════════════════

class TestSubject:
    def test_create_subject(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.create_subject(SCHOOL_A, "Mathematics", "MATH")
        assert result["name"] == "Mathematics"
        assert result["code"] == "MATH"

    def test_duplicate_code_rejected(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.create_subject(SCHOOL_A, "Mathematics", "MATH")
        result = svc.create_subject(SCHOOL_A, "Advanced Math", "MATH")
        assert result["error"] == "DUPLICATE_CODE"

    def test_same_code_different_school_allowed(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        svc.create_school(SCHOOL_B, "School B")
        r1 = svc.create_subject(SCHOOL_A, "Math", "MATH")
        r2 = svc.create_subject(SCHOOL_B, "Math", "MATH")
        assert "id" in r1 and "id" in r2


# ═══════════════════════════════════════════
# Teacher-Class Assignment
# ═══════════════════════════════════════════

class TestClassTeacher:
    def _setup(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        cls = svc.create_class(SCHOOL_A, "Grade 6", "A")
        return svc, uuid.UUID(year["id"]), uuid.UUID(cls["id"])

    def test_assign_teacher(self, db):
        svc, year_id, class_id = self._setup(db)
        result = svc.assign_class_teacher(SCHOOL_A, class_id, TEACHER_1, year_id)
        assert "id" in result
        assert result["teacher_user_id"] == str(TEACHER_1)

    def test_duplicate_assignment_same_class_year_rejected(self, db):
        svc, year_id, class_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, class_id, TEACHER_1, year_id)
        result = svc.assign_class_teacher(SCHOOL_A, class_id, TEACHER_2, year_id)
        assert result["error"] == "DUPLICATE_ASSIGNMENT"

    def test_teacher_can_teach_multiple_classes(self, db):
        svc, year_id, class_id = self._setup(db)
        cls2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        r1 = svc.assign_class_teacher(SCHOOL_A, class_id, TEACHER_1, year_id)
        r2 = svc.assign_class_teacher(SCHOOL_A, uuid.UUID(cls2["id"]), TEACHER_1, year_id)
        assert "id" in r1
        assert "id" in r2

    def test_assign_to_nonexistent_class_rejected(self, db):
        svc, year_id, _ = self._setup(db)
        fake_class = uuid.uuid4()
        result = svc.assign_class_teacher(SCHOOL_A, fake_class, TEACHER_1, year_id)
        assert result["error"] == "NOT_FOUND"


# ═══════════════════════════════════════════
# Cross-School Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_class_isolated_by_school(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        svc.create_school(SCHOOL_B, "School B")
        svc.create_class(SCHOOL_A, "Grade 6", "A")
        svc.create_class(SCHOOL_B, "Grade 6", "A")
        classes_a, _ = svc.list_classes(SCHOOL_A)
        classes_b, _ = svc.list_classes(SCHOOL_B)
        assert len(classes_a) == 1
        assert len(classes_b) == 1
        assert classes_a[0]["school_id"] != classes_b[0]["school_id"]

    def test_update_class_cross_school_blocked(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        cls = svc.create_class(SCHOOL_A, "Grade 6", "A")
        result = svc.update_class(uuid.UUID(cls["id"]), SCHOOL_B, name="Hacked")
        assert result is None

    def test_soft_delete_cross_school_blocked(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        cls = svc.create_class(SCHOOL_A, "Grade 6", "A")
        result = svc.soft_delete_class(uuid.UUID(cls["id"]), SCHOOL_B)
        assert result is None

    def test_academic_year_isolated(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        svc.create_school(SCHOOL_B, "School B")
        svc.create_academic_year(SCHOOL_A, "2026A", date(2026, 1, 1), date(2026, 12, 31))
        svc.create_academic_year(SCHOOL_B, "2026B", date(2026, 1, 1), date(2026, 12, 31))
        years_a = svc.list_academic_years(SCHOOL_A)
        years_b = svc.list_academic_years(SCHOOL_B)
        assert len(years_a) == 1
        assert len(years_b) == 1

    def test_term_cross_school_blocked(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        # Try to create term with SCHOOL_B
        result = svc.create_term(SCHOOL_B, uuid.UUID(year["id"]), "Term 1",
                                  date(2026, 1, 15), date(2026, 4, 15))
        assert result["error"] == "NOT_FOUND"

    def test_teacher_assignment_cross_school_blocked(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        cls = svc.create_class(SCHOOL_A, "Grade 6", "A")
        # Try to assign from SCHOOL_B
        result = svc.assign_class_teacher(SCHOOL_B, uuid.UUID(cls["id"]),
                                           TEACHER_1, uuid.UUID(year["id"]))
        assert result["error"] == "NOT_FOUND"


# ═══════════════════════════════════════════
# Teacher Self-Service — get_teacher_classes
# ═══════════════════════════════════════════

class TestGetTeacherClasses:
    def _setup(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        year_id = uuid.UUID(year["id"])
        cls1 = svc.create_class(SCHOOL_A, "Grade 6", "A")
        cls2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        return svc, year_id, uuid.UUID(cls1["id"]), uuid.UUID(cls2["id"])

    def test_returns_assigned_classes(self, db):
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        svc.assign_class_teacher(SCHOOL_A, cls2_id, TEACHER_1, year_id)
        result = svc.get_teacher_classes(TEACHER_1, SCHOOL_A)
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "Grade 6" in names
        assert "Grade 7" in names

    def test_returns_empty_for_no_assignments(self, db):
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        result = svc.get_teacher_classes(TEACHER_1, SCHOOL_A)
        assert result == []

    def test_teacher_only_sees_own_classes(self, db):
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        svc.assign_class_teacher(SCHOOL_A, cls2_id, TEACHER_2, year_id)
        result_t1 = svc.get_teacher_classes(TEACHER_1, SCHOOL_A)
        result_t2 = svc.get_teacher_classes(TEACHER_2, SCHOOL_A)
        assert len(result_t1) == 1
        assert result_t1[0]["name"] == "Grade 6"
        assert len(result_t2) == 1
        assert result_t2[0]["name"] == "Grade 7"

    def test_includes_class_details_and_assignment_id(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        result = svc.get_teacher_classes(TEACHER_1, SCHOOL_A)
        assert len(result) == 1
        cls = result[0]
        assert cls["name"] == "Grade 6"
        assert cls["section"] == "A"
        assert "assignment_id" in cls
        assert "academic_year_id" in cls
        assert cls["is_active"] is True

    def test_excludes_inactive_classes(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        svc.soft_delete_class(cls1_id, SCHOOL_A)
        result = svc.get_teacher_classes(TEACHER_1, SCHOOL_A)
        assert result == []

    def test_cross_school_isolation(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.create_school(SCHOOL_B, "School B")
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        result = svc.get_teacher_classes(TEACHER_1, SCHOOL_B)
        assert result == []


# ═══════════════════════════════════════════
# Teacher Authorization (internal endpoint)
# ═══════════════════════════════════════════

class TestTeacherAuthorize:
    def _setup(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        year_id = uuid.UUID(year["id"])
        cls1 = svc.create_class(SCHOOL_A, "Grade 6", "A")
        cls2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        return svc, year_id, uuid.UUID(cls1["id"]), uuid.UUID(cls2["id"])

    def test_authorized_teacher(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_class(TEACHER_1, cls1_id, SCHOOL_A) is True

    def test_unauthorized_teacher(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        assert svc.is_teacher_authorized_for_class(TEACHER_1, cls1_id, SCHOOL_A) is False

    def test_wrong_class_unauthorized(self, db):
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_class(TEACHER_1, cls2_id, SCHOOL_A) is False

    def test_cross_school_unauthorized(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.create_school(SCHOOL_B, "School B")
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_class(TEACHER_1, cls1_id, SCHOOL_B) is False

    def test_different_teacher_unauthorized(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_class(TEACHER_2, cls1_id, SCHOOL_A) is False


# ═══════════════════════════════════════════
# Teacher Authorization for Student (10B-1E)
# ═══════════════════════════════════════════

STUDENT_1 = uuid.uuid4()
STUDENT_2 = uuid.uuid4()


class TestTeacherAuthorizeStudent:
    def _setup(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        year_id = uuid.UUID(year["id"])
        cls1 = svc.create_class(SCHOOL_A, "Grade 6", "A")
        cls2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        return svc, year_id, uuid.UUID(cls1["id"]), uuid.UUID(cls2["id"])

    def test_authorized_teacher_for_student(self, db):
        """Teacher assigned to class_id → authorized to view student in that class."""
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_student(
            TEACHER_1, STUDENT_1, SCHOOL_A, cls1_id
        ) is True

    def test_unauthorized_teacher_wrong_class(self, db):
        """Teacher not assigned to class → unauthorized for student in that class."""
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_student(
            TEACHER_1, STUDENT_1, SCHOOL_A, cls2_id
        ) is False

    def test_unauthorized_different_teacher(self, db):
        """Different teacher not assigned to class → unauthorized."""
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_student(
            TEACHER_2, STUDENT_1, SCHOOL_A, cls1_id
        ) is False

    def test_cross_school_unauthorized(self, db):
        """Teacher in school A → cannot view student via school B."""
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.create_school(SCHOOL_B, "School B")
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        assert svc.is_teacher_authorized_for_student(
            TEACHER_1, STUDENT_1, SCHOOL_B, cls1_id
        ) is False

    def test_no_assignment_unauthorized(self, db):
        """Teacher with no assignments → unauthorized for any student."""
        svc, year_id, cls1_id, _ = self._setup(db)
        assert svc.is_teacher_authorized_for_student(
            TEACHER_1, STUDENT_1, SCHOOL_A, cls1_id
        ) is False


class TestGetTeacherClassIds:
    def _setup(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "School A")
        year = svc.create_academic_year(SCHOOL_A, "2026",
                                         date(2026, 1, 1), date(2026, 12, 31))
        year_id = uuid.UUID(year["id"])
        cls1 = svc.create_class(SCHOOL_A, "Grade 6", "A")
        cls2 = svc.create_class(SCHOOL_A, "Grade 7", "A")
        return svc, year_id, uuid.UUID(cls1["id"]), uuid.UUID(cls2["id"])

    def test_returns_assigned_class_ids(self, db):
        svc, year_id, cls1_id, cls2_id = self._setup(db)
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        svc.assign_class_teacher(SCHOOL_A, cls2_id, TEACHER_1, year_id)
        ids = svc.get_teacher_class_ids(TEACHER_1, SCHOOL_A)
        assert set(ids) == {cls1_id, cls2_id}

    def test_returns_empty_for_no_assignments(self, db):
        svc, year_id, _, _ = self._setup(db)
        ids = svc.get_teacher_class_ids(TEACHER_1, SCHOOL_A)
        assert ids == []

    def test_cross_school_isolation(self, db):
        svc, year_id, cls1_id, _ = self._setup(db)
        svc.create_school(SCHOOL_B, "School B")
        svc.assign_class_teacher(SCHOOL_A, cls1_id, TEACHER_1, year_id)
        ids = svc.get_teacher_class_ids(TEACHER_1, SCHOOL_B)
        assert ids == []


# ═══════════════════════════════════════════
# Provinces / Districts / School Geo
# ═══════════════════════════════════════════

class TestSchoolGeo:
    def _seed_geo(self, db):
        from app.models.school import Province, District
        db.add_all([
            Province(code="HRE", name="Harare Metropolitan",
                     region="Mashonaland", capital="Harare", country="ZW"),
            Province(code="BYO", name="Bulawayo Metropolitan",
                     region="Matabeleland", capital="Bulawayo", country="ZW"),
        ])
        db.flush()
        db.add_all([
            District(code="hre-cn", name="Harare Central", province_code="HRE"),
            District(code="hre-ea", name="Harare East", province_code="HRE"),
            District(code="byo-cn", name="Bulawayo Central", province_code="BYO"),
        ])
        db.commit()

    def test_list_provinces(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        rows = svc.list_provinces()
        assert {r["code"] for r in rows} == {"HRE", "BYO"}

    def test_list_districts_filtered_by_province(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        rows = svc.list_districts(province_code="HRE")
        assert {r["code"] for r in rows} == {"hre-cn", "hre-ea"}
        assert all(r["province_code"] == "HRE" for r in rows)

    def test_list_districts_unfiltered(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        rows = svc.list_districts()
        assert len(rows) == 3

    def test_get_province(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        p = svc.get_province("HRE")
        assert p["name"] == "Harare Metropolitan"

    def test_get_unknown_province_returns_none(self, db):
        svc = _svc(db)
        assert svc.get_province("ZZZ") is None

    def test_update_school_geo_happy_path(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.update_school_geo(
            SCHOOL_A,
            province_code="HRE", district_code="hre-cn",
            school_type="PRIMARY",
            principal_name="Mrs. Mhlanga",
            address="1 Main St",
            phone="+263 4 1234567",
            email="admin@school.test",
            founded_year=1985,
        )
        assert result["province_code"] == "HRE"
        assert result["district_code"] == "hre-cn"
        assert result["school_type"] == "PRIMARY"
        assert result["principal_name"] == "Mrs. Mhlanga"
        assert result["founded_year"] == 1985

    def test_update_school_geo_invalid_province(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.update_school_geo(SCHOOL_A, province_code="ZZZ")
        assert result["error"] == "INVALID_PROVINCE"

    def test_update_school_geo_invalid_district(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.update_school_geo(SCHOOL_A, district_code="nope-x")
        assert result["error"] == "INVALID_DISTRICT"

    def test_update_school_geo_district_province_mismatch(self, db):
        self._seed_geo(db)
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        svc.update_school_geo(SCHOOL_A, province_code="HRE")
        result = svc.update_school_geo(SCHOOL_A, district_code="byo-cn")
        assert result["error"] == "DISTRICT_PROVINCE_MISMATCH"

    def test_update_school_geo_invalid_school_type(self, db):
        svc = _svc(db)
        svc.create_school(SCHOOL_A, "Test School")
        result = svc.update_school_geo(SCHOOL_A, school_type="MIDDLE")
        assert result["error"] == "INVALID_TYPE"

    def test_update_school_geo_unknown_school(self, db):
        svc = _svc(db)
        result = svc.update_school_geo(uuid.uuid4(), school_type="PRIMARY")
        assert result is None
