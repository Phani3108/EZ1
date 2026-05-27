"""PH2-9 — in-process teacher↔student and parent↔student authorization.

Proves the last two ADR-006-addendum §2 seams close:

> "In academics, `school-service /internal/teachers/authorize-student` and
>  `student-service /internal/parents/authorize` HTTP calls are replaced
>  with direct DB queries against the co-located academics_db tables."

Specifically:
- `is_teacher_authorized_for_student` returns True when the teacher
  teaches a class the student is enrolled in (within the same school),
  False otherwise. Cross-tenant blocked.
- `is_parent_authorized_for_student` returns True when a `student_parents`
  link exists between the parent's user account and the student (same
  school), False otherwise. Cross-tenant blocked.
- The async route-layer wrappers `verify_teacher_student_authorization` and
  `verify_parent_student_authorization` surface a DB-level failure as
  `AuthorizationServiceUnavailable` (Phase 1 BUG-001 fail-closed-honestly
  spirit preserved).
"""
import asyncio
import os
import uuid
from datetime import date

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_authz.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
# JWT/INTERNAL secrets come from tests/__init__.py setdefault.

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.database import Base
from app.models.school import Class, ClassTeacherAssignment  # noqa: F401
from app.models.student import Student, Parent, StudentParent, Enrollment  # noqa: F401
from app.services.authorization import (
    is_teacher_authorized_for_class,  # PH2-8 (re-tested briefly)
    is_teacher_authorized_for_student,  # PH2-9
    is_parent_authorized_for_student,  # PH2-9
)
from app.dependencies import (
    verify_teacher_student_authorization,
    verify_parent_student_authorization,
    AuthorizationServiceUnavailable,
)

engine = create_engine(
    "sqlite:///./test_academics_authz.db",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_wal(dbapi_conn, _rec):
    dbapi_conn.cursor().execute("PRAGMA journal_mode=WAL")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    for suffix in ("", "-wal", "-shm"):
        path = f"./test_academics_authz.db{suffix}"
        try:
            os.remove(path)
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
TEACHER = uuid.uuid4()
OTHER_TEACHER = uuid.uuid4()
PARENT_USER = uuid.uuid4()
OTHER_PARENT_USER = uuid.uuid4()


def _seed_teacher_class_student(db, school_id=SCHOOL_A, teacher=TEACHER):
    """Helper: create one Class + ClassTeacherAssignment + Student + Enrollment."""
    year_id = uuid.uuid4()
    cls = Class(school_id=school_id, name="Grade 6", section="A")
    db.add(cls)
    db.commit()
    db.refresh(cls)

    db.add(ClassTeacherAssignment(
        school_id=school_id,
        class_id=cls.id,
        teacher_user_id=teacher,
        academic_year_id=year_id,
    ))
    student = Student(
        school_id=school_id,
        student_code=f"S-{uuid.uuid4().hex[:6]}",
        first_name="A",
        last_name="B",
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    db.add(Enrollment(
        school_id=school_id,
        student_id=student.id,
        class_id=cls.id,
        academic_year_id=year_id,
    ))
    db.commit()
    return cls, student, year_id


def _seed_parent_student_link(db, parent_user_id=PARENT_USER, school_id=SCHOOL_A,
                                student=None):
    """Helper: create a Parent (with .user_id link) + StudentParent row."""
    parent = Parent(
        school_id=school_id,
        first_name="P",
        last_name="N",
        phone=f"+263{uuid.uuid4().hex[:9]}",
        user_id=parent_user_id,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    if student is None:
        student = Student(
            school_id=school_id,
            student_code=f"S-{uuid.uuid4().hex[:6]}",
            first_name="K",
            last_name="N",
        )
        db.add(student)
        db.commit()
        db.refresh(student)

    db.add(StudentParent(
        school_id=school_id,
        student_id=student.id,
        parent_id=parent.id,
    ))
    db.commit()
    return parent, student


# ───────── is_teacher_authorized_for_student ─────────

class TestPH29TeacherStudentAuthInProcess:
    def test_returns_true_when_teacher_teaches_a_class_student_is_in(self, db):
        cls, student, _ = _seed_teacher_class_student(db)
        assert is_teacher_authorized_for_student(
            teacher_user_id=TEACHER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is True

    def test_returns_false_when_teacher_doesnt_teach_any_class_student_is_in(self, db):
        _, student, _ = _seed_teacher_class_student(db, teacher=OTHER_TEACHER)
        # TEACHER is not assigned to any class this student is enrolled in.
        assert is_teacher_authorized_for_student(
            teacher_user_id=TEACHER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is False

    def test_returns_false_when_student_not_enrolled_anywhere(self, db):
        # Teacher exists for some other school + has an assignment but the
        # target student has no enrollment.
        cls = Class(school_id=SCHOOL_A, name="Grade 6", section="A")
        db.add(cls)
        db.commit()
        db.refresh(cls)
        db.add(ClassTeacherAssignment(
            school_id=SCHOOL_A,
            class_id=cls.id,
            teacher_user_id=TEACHER,
            academic_year_id=uuid.uuid4(),
        ))
        db.commit()
        orphan_student_id = uuid.uuid4()
        assert is_teacher_authorized_for_student(
            teacher_user_id=TEACHER,
            student_id=orphan_student_id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is False

    def test_returns_false_cross_tenant(self, db):
        _, student, _ = _seed_teacher_class_student(db, school_id=SCHOOL_A)
        # Looking for the same student but as SCHOOL_B — no rows match.
        assert is_teacher_authorized_for_student(
            teacher_user_id=TEACHER,
            student_id=student.id,
            school_id=SCHOOL_B,
            db_session=db,
        ) is False

    def test_route_wrapper_db_error_surfaces_503(self):
        broken = MagicMock()
        broken.query.side_effect = OperationalError("SELECT ...", {}, Exception("boom"))
        with pytest.raises(AuthorizationServiceUnavailable):
            asyncio.run(verify_teacher_student_authorization(
                TEACHER, uuid.uuid4(), SCHOOL_A, broken,
            ))


# ───────── is_parent_authorized_for_student ─────────

class TestPH29ParentStudentAuthInProcess:
    def test_returns_true_when_link_exists(self, db):
        _, student = _seed_parent_student_link(db)
        assert is_parent_authorized_for_student(
            parent_user_id=PARENT_USER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is True

    def test_returns_false_when_no_link(self, db):
        # Create a student but no parent link.
        student = Student(
            school_id=SCHOOL_A,
            student_code=f"S-{uuid.uuid4().hex[:6]}",
            first_name="X", last_name="Y",
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        assert is_parent_authorized_for_student(
            parent_user_id=PARENT_USER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is False

    def test_returns_false_when_parent_user_doesnt_match(self, db):
        _, student = _seed_parent_student_link(db)
        # Different parent_user_id → no link.
        assert is_parent_authorized_for_student(
            parent_user_id=OTHER_PARENT_USER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is False

    def test_returns_false_cross_tenant(self, db):
        _, student = _seed_parent_student_link(db, school_id=SCHOOL_A)
        assert is_parent_authorized_for_student(
            parent_user_id=PARENT_USER,
            student_id=student.id,
            school_id=SCHOOL_B,
            db_session=db,
        ) is False

    def test_returns_false_when_parent_user_id_null(self, db):
        """A Parent row without a `user_id` (parents who haven't onboarded
        a login yet) must NOT match against any parent_user_id query."""
        parent = Parent(
            school_id=SCHOOL_A,
            first_name="P", last_name="N",
            phone=f"+263{uuid.uuid4().hex[:9]}",
            user_id=None,  # explicit null
        )
        db.add(parent)
        student = Student(
            school_id=SCHOOL_A,
            student_code=f"S-{uuid.uuid4().hex[:6]}",
            first_name="K", last_name="N",
        )
        db.add(student)
        db.commit()
        db.refresh(parent)
        db.refresh(student)
        db.add(StudentParent(
            school_id=SCHOOL_A,
            student_id=student.id,
            parent_id=parent.id,
        ))
        db.commit()

        # Even searching with the same UUID we'd never get a match — the
        # parent row's user_id is NULL.
        assert is_parent_authorized_for_student(
            parent_user_id=PARENT_USER,
            student_id=student.id,
            school_id=SCHOOL_A,
            db_session=db,
        ) is False

    def test_route_wrapper_db_error_surfaces_503(self):
        broken = MagicMock()
        broken.query.side_effect = OperationalError("SELECT ...", {}, Exception("boom"))
        with pytest.raises(AuthorizationServiceUnavailable):
            asyncio.run(verify_parent_student_authorization(
                PARENT_USER, uuid.uuid4(), SCHOOL_A, broken,
            ))


# ───────── PH2-8 spot-check to keep history coverage ─────────

def test_ph2_8_teacher_class_still_works(db):
    """Sanity: re-prove PH2-8's teacher-class authz still passes after the
    PH2-9 dependency-module rewrite (we extended dependencies.py with two
    new wrappers; the PH2-8 wrapper must remain intact)."""
    cls, _, _ = _seed_teacher_class_student(db)
    assert is_teacher_authorized_for_class(
        teacher_user_id=TEACHER,
        class_id=cls.id,
        school_id=SCHOOL_A,
        db_session=db,
    ) is True
