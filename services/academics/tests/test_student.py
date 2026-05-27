"""
Student Service Tests — Quality Gate 4
=========================================
Unit Tests:
- Duplicate student_code rejected
- Only one active enrollment per year enforced
- Parent link duplicate rejected
- Only one primary guardian allowed
- Soft delete hides from list
- Cannot delete student with active enrollment

Service-to-Service Tests (MockSchoolServiceClient):
- Enrollment rejected if class_id invalid
- Enrollment rejected if academic_year invalid
- Enrollment rejected if class from different school

Integration Tests:
- Cross-school isolation enforced
- Enrollment for soft-deleted student rejected
"""
import os
import uuid
from datetime import date

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_academics_student.db"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["KAFKA_ENABLED"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.student import Student, Parent, StudentParent, Enrollment  # noqa

engine = create_engine("sqlite:///./test_academics_student.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_academics_student.db"):
        try:
            os.remove("./test_academics_student.db")
        except OSError:
            pass


@pytest.fixture
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
CLASS_A = uuid.uuid4()
CLASS_B = uuid.uuid4()
YEAR_A = uuid.uuid4()
YEAR_B = uuid.uuid4()


def _mock_client():
    from app.services.school_client import MockSchoolServiceClient
    mock = MockSchoolServiceClient()
    mock.add_class(CLASS_A, SCHOOL_A, "Grade 6")
    mock.add_class(CLASS_B, SCHOOL_B, "Grade 6")
    mock.add_year(YEAR_A, SCHOOL_A, "2026")
    mock.add_year(YEAR_B, SCHOOL_B, "2026")
    return mock


def _svc(db, mock=True):
    from app.services.student_service import StudentService
    client = _mock_client() if mock else None
    return StudentService(db, school_client=client)


def _student(db, school_id=None, code="STU001"):
    svc = _svc(db, mock=False)
    return svc.create_student(school_id or SCHOOL_A, code, "John", "Doe",
                               dob=date(2012, 5, 15), gender="MALE")


def _parent(db, school_id=None, phone="+263771234567"):
    svc = _svc(db, mock=False)
    return svc.create_parent(school_id or SCHOOL_A, "Jane", "Doe",
                              phone, relationship_type="MOTHER")


# ═══════════════════════════════════════════
# Students
# ═══════════════════════════════════════════

class TestStudent:
    def test_create(self, db):
        result = _student(db)
        assert "id" in result
        assert result["student_code"] == "STU001"
        assert result["status"] == "ACTIVE"

    def test_duplicate_code_rejected(self, db):
        _student(db, code="DUP001")
        result = _student(db, code="DUP001")
        assert result["error"] == "DUPLICATE_CODE"

    def test_same_code_different_school(self, db):
        r1 = _student(db, SCHOOL_A, "SHARED")
        r2 = _student(db, SCHOOL_B, "SHARED")
        assert "id" in r1 and "id" in r2

    def test_soft_delete_hides_from_list(self, db):
        svc = _svc(db, mock=False)
        s1 = _student(db, code="S1")
        s2 = _student(db, code="S2")
        svc.soft_delete_student(uuid.UUID(s2["id"]), SCHOOL_A)
        students, total = svc.list_students(SCHOOL_A)
        assert total == 1
        assert students[0]["student_code"] == "S1"

    def test_soft_delete_preserves_row(self, db):
        s = _student(db)
        svc = _svc(db, mock=False)
        svc.soft_delete_student(uuid.UUID(s["id"]), SCHOOL_A)
        row = db.query(Student).filter(Student.id == uuid.UUID(s["id"])).first()
        assert row is not None
        assert row.deleted_at is not None
        assert row.status == "INACTIVE"

    def test_search_students(self, db):
        _student(db, code="S1")
        svc = _svc(db, mock=False)
        svc.create_student(SCHOOL_A, "S2", "Alice", "Smith")
        results, total = svc.list_students(SCHOOL_A, query="Alice")
        assert total == 1
        assert results[0]["first_name"] == "Alice"

    def test_filter_by_status(self, db):
        svc = _svc(db, mock=False)
        _student(db, code="ACT")
        s2 = svc.create_student(SCHOOL_A, "INACT", "Bob", "Smith")
        svc.update_student(uuid.UUID(s2["id"]), SCHOOL_A, status="INACTIVE")
        results, total = svc.list_students(SCHOOL_A, status="ACTIVE")
        assert total == 1


# ═══════════════════════════════════════════
# Cannot Delete with Active Enrollment
# ═══════════════════════════════════════════

class TestDeleteConstraints:
    def test_cannot_delete_with_active_enrollment(self, db):
        s = _student(db, code="ENROLL01")
        svc = _svc(db)
        svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        result = svc.soft_delete_student(uuid.UUID(s["id"]), SCHOOL_A)
        assert result["error"] == "ACTIVE_ENROLLMENT"

    def test_can_delete_without_enrollment(self, db):
        s = _student(db, code="NOENROLL")
        svc = _svc(db, mock=False)
        result = svc.soft_delete_student(uuid.UUID(s["id"]), SCHOOL_A)
        assert result["deleted_at"] is not None


# ═══════════════════════════════════════════
# Parents
# ═══════════════════════════════════════════

class TestParent:
    def test_create(self, db):
        result = _parent(db)
        assert "id" in result
        assert result["phone"] == "+263771234567"

    def test_duplicate_phone_rejected(self, db):
        _parent(db, phone="+263770000001")
        result = _parent(db, phone="+263770000001")
        assert result["error"] == "DUPLICATE_PHONE"

    def test_same_phone_different_school(self, db):
        r1 = _parent(db, SCHOOL_A, "+263779999999")
        r2 = _parent(db, SCHOOL_B, "+263779999999")
        assert "id" in r1 and "id" in r2


# ═══════════════════════════════════════════
# Parent Linking
# ═══════════════════════════════════════════

class TestParentLink:
    def test_link_parent(self, db):
        s = _student(db)
        p = _parent(db)
        svc = _svc(db, mock=False)
        result = svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        assert "id" in result
        assert result["is_primary"] is False

    def test_duplicate_link_rejected(self, db):
        s = _student(db)
        p = _parent(db)
        svc = _svc(db, mock=False)
        svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        result = svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        assert result["error"] == "DUPLICATE_LINK"

    def test_only_one_primary(self, db):
        s = _student(db)
        p1 = _parent(db, phone="+263771111111")
        p2 = _parent(db, phone="+263772222222")
        svc = _svc(db, mock=False)
        l1 = svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p1["id"]), is_primary=True)
        assert l1["is_primary"] is True
        l2 = svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p2["id"]), is_primary=True)
        assert l2["is_primary"] is True

        # p1 should no longer be primary
        links = svc.get_student_parents(uuid.UUID(s["id"]), SCHOOL_A)
        primaries = [l for l in links if l["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["parent_id"] == str(p2["id"])

    def test_parent_cross_school_rejected(self, db):
        s = _student(db, SCHOOL_A)
        p = _parent(db, SCHOOL_B, "+263773333333")
        svc = _svc(db, mock=False)
        result = svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        assert result["error"] == "NOT_FOUND"

    def test_parent_reused_across_siblings(self, db):
        s1 = _student(db, code="SIB1")
        s2 = _student(db, code="SIB2")
        p = _parent(db)
        svc = _svc(db, mock=False)
        r1 = svc.link_parent(SCHOOL_A, uuid.UUID(s1["id"]), uuid.UUID(p["id"]))
        r2 = svc.link_parent(SCHOOL_A, uuid.UUID(s2["id"]), uuid.UUID(p["id"]))
        assert "id" in r1 and "id" in r2


# ═══════════════════════════════════════════
# Parent Me Children (10A-P1)
# ═══════════════════════════════════════════

class TestParentMeChildren:
    def test_get_children_by_user_id(self, db):
        """Parent with user_id can retrieve their linked children."""
        s1 = _student(db, code="CHILD1")
        s2 = _student(db, code="CHILD2")
        p = _parent(db)
        svc = _svc(db, mock=False)

        # Set user_id on parent record
        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        # Link both children
        svc.link_parent(SCHOOL_A, uuid.UUID(s1["id"]), uuid.UUID(p["id"]))
        svc.link_parent(SCHOOL_A, uuid.UUID(s2["id"]), uuid.UUID(p["id"]))

        result = svc.get_children_by_user_id(user_id, SCHOOL_A)
        assert result is not None
        assert len(result) == 2
        codes = {c["student_code"] for c in result}
        assert codes == {"CHILD1", "CHILD2"}

    def test_no_parent_record_returns_none(self, db):
        """user_id not linked to any Parent row → None."""
        svc = _svc(db, mock=False)
        result = svc.get_children_by_user_id(uuid.uuid4(), SCHOOL_A)
        assert result is None

    def test_parent_no_children_returns_empty(self, db):
        """Parent exists with user_id but has no linked students → empty list."""
        p = _parent(db)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        result = svc.get_children_by_user_id(user_id, SCHOOL_A)
        assert result is not None
        assert len(result) == 0

    def test_cross_school_isolation(self, db):
        """Parent in SCHOOL_A cannot see children by querying SCHOOL_B."""
        s = _student(db, SCHOOL_A, "ISOCHILD")
        p = _parent(db, SCHOOL_A)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))

        # Same user_id, wrong school → None
        result = svc.get_children_by_user_id(user_id, SCHOOL_B)
        assert result is None

    def test_soft_deleted_children_excluded(self, db):
        """Soft-deleted students should not appear in results."""
        s1 = _student(db, code="ALIVE")
        s2 = _student(db, code="GONE")
        p = _parent(db)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        svc.link_parent(SCHOOL_A, uuid.UUID(s1["id"]), uuid.UUID(p["id"]))
        svc.link_parent(SCHOOL_A, uuid.UUID(s2["id"]), uuid.UUID(p["id"]))

        # Soft-delete one child
        svc.soft_delete_student(uuid.UUID(s2["id"]), SCHOOL_A)

        result = svc.get_children_by_user_id(user_id, SCHOOL_A)
        assert len(result) == 1
        assert result[0]["student_code"] == "ALIVE"


# ═══════════════════════════════════════════
# Parent-Child Authorization (10A-P2)
# ═══════════════════════════════════════════

class TestParentChildAuth:
    """Test verify_parent_child_link — internal authorization for cross-service calls."""

    def test_linked_parent_authorized(self, db):
        s = _student(db, code="AUTH1")
        p = _parent(db)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        assert svc.verify_parent_child_link(user_id, uuid.UUID(s["id"]), SCHOOL_A) is True

    def test_unlinked_parent_rejected(self, db):
        s = _student(db, code="AUTH2")
        p = _parent(db)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        # Not linked
        assert svc.verify_parent_child_link(user_id, uuid.UUID(s["id"]), SCHOOL_A) is False

    def test_unknown_user_rejected(self, db):
        s = _student(db, code="AUTH3")
        svc = _svc(db, mock=False)
        assert svc.verify_parent_child_link(uuid.uuid4(), uuid.UUID(s["id"]), SCHOOL_A) is False

    def test_cross_school_rejected(self, db):
        s = _student(db, SCHOOL_A, "AUTH4")
        p = _parent(db, SCHOOL_A)
        svc = _svc(db, mock=False)

        parent_row = db.query(Parent).filter(Parent.id == uuid.UUID(p["id"])).first()
        user_id = uuid.uuid4()
        parent_row.user_id = user_id
        db.commit()

        svc.link_parent(SCHOOL_A, uuid.UUID(s["id"]), uuid.UUID(p["id"]))
        # Same user_id, wrong school → False
        assert svc.verify_parent_child_link(user_id, uuid.UUID(s["id"]), SCHOOL_B) is False


# ═══════════════════════════════════════════
# Enrollment
# ═══════════════════════════════════════════

class TestEnrollment:
    def test_create_enrollment(self, db):
        s = _student(db)
        svc = _svc(db)
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        assert "id" in result
        assert result["status"] == "ENROLLED"

    def test_duplicate_enrollment_same_year_rejected(self, db):
        s = _student(db)
        svc = _svc(db)
        svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        assert result["error"] == "DUPLICATE_ENROLLMENT"

    def test_enrollment_soft_deleted_student_rejected(self, db):
        s = _student(db, code="DEL01")
        svc = _svc(db)
        svc_no_mock = _svc(db, mock=False)
        svc_no_mock.soft_delete_student(uuid.UUID(s["id"]), SCHOOL_A)
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        assert result["error"] == "NOT_FOUND"

    def test_enrollment_inactive_student_rejected(self, db):
        s = _student(db, code="INACT01")
        svc = _svc(db)
        svc.update_student(uuid.UUID(s["id"]), SCHOOL_A, status="INACTIVE")
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_A)
        assert result["error"] == "INACTIVE_STUDENT"


# ═══════════════════════════════════════════
# Service-to-Service Validation (Mock)
# ═══════════════════════════════════════════

class TestServiceToService:
    def test_enrollment_invalid_class_rejected(self, db):
        s = _student(db)
        svc = _svc(db)
        fake_class = uuid.uuid4()
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), fake_class, YEAR_A)
        assert result["error"] == "INVALID_CLASS"

    def test_enrollment_invalid_year_rejected(self, db):
        s = _student(db)
        svc = _svc(db)
        fake_year = uuid.uuid4()
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, fake_year)
        assert result["error"] == "INVALID_YEAR"

    def test_enrollment_class_from_different_school_rejected(self, db):
        s = _student(db)
        svc = _svc(db)
        # CLASS_B belongs to SCHOOL_B, student is in SCHOOL_A
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_B, YEAR_A)
        assert result["error"] == "INVALID_CLASS"

    def test_enrollment_year_from_different_school_rejected(self, db):
        s = _student(db)
        svc = _svc(db)
        # YEAR_B belongs to SCHOOL_B
        result = svc.create_enrollment(SCHOOL_A, uuid.UUID(s["id"]), CLASS_A, YEAR_B)
        assert result["error"] == "INVALID_YEAR"


# ═══════════════════════════════════════════
# Cross-School Isolation
# ═══════════════════════════════════════════

class TestTenantIsolation:
    def test_student_isolated(self, db):
        _student(db, SCHOOL_A, "SA1")
        _student(db, SCHOOL_B, "SB1")
        svc = _svc(db, mock=False)
        a, ta = svc.list_students(SCHOOL_A)
        b, tb = svc.list_students(SCHOOL_B)
        assert ta == 1 and tb == 1

    def test_get_student_cross_school_blocked(self, db):
        s = _student(db, SCHOOL_A)
        svc = _svc(db, mock=False)
        assert svc.get_student(uuid.UUID(s["id"]), SCHOOL_B) is None

    def test_update_student_cross_school_blocked(self, db):
        s = _student(db, SCHOOL_A)
        svc = _svc(db, mock=False)
        assert svc.update_student(uuid.UUID(s["id"]), SCHOOL_B, first_name="Hacked") is None

    def test_delete_student_cross_school_blocked(self, db):
        s = _student(db, SCHOOL_A)
        svc = _svc(db, mock=False)
        assert svc.soft_delete_student(uuid.UUID(s["id"]), SCHOOL_B) is None

    def test_parent_isolated(self, db):
        _parent(db, SCHOOL_A, "+263771111111")
        _parent(db, SCHOOL_B, "+263772222222")
        svc = _svc(db, mock=False)
        assert len(svc.list_parents(SCHOOL_A)) == 1
        assert len(svc.list_parents(SCHOOL_B)) == 1

    def test_enrollment_isolated(self, db):
        s1 = _student(db, SCHOOL_A, "SA")
        s2 = _student(db, SCHOOL_B, "SB")
        svc = _svc(db)
        svc.create_enrollment(SCHOOL_A, uuid.UUID(s1["id"]), CLASS_A, YEAR_A)
        svc.create_enrollment(SCHOOL_B, uuid.UUID(s2["id"]), CLASS_B, YEAR_B)
        assert len(svc.list_enrollments(SCHOOL_A)) == 1
        assert len(svc.list_enrollments(SCHOOL_B)) == 1
