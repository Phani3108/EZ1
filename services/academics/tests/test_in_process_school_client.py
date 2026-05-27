"""PH2-7 — in-process school-client replacement.

These tests prove the seam called out in the ADR 006 addendum §2:

> "In academics, the school_client HTTP call is replaced with a direct DB
>  query against the co-located Class + AcademicYear tables."

Specifically:
- `InProcessSchoolClient.validate_class` returns the row when present in
  academics_db, None when missing, None when school_id mismatches.
- Same for `validate_academic_year`.
- The deprecated `HttpSchoolServiceClient(db=db)` still works (one
  transitional minor release); without `db` it raises loudly.
- Enrollment creation through `StudentService` with `InProcessSchoolClient`
  successfully validates against real DB rows (i.e., the seam closes).
"""
import os
import uuid
from datetime import date

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_inproc.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
# JWT/INTERNAL secrets come from tests/__init__.py setdefault.

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.school import Class, AcademicYear  # noqa: F401
from app.models.student import Student, Enrollment  # noqa: F401
from app.services.school_client import (
    InProcessSchoolClient,
    HttpSchoolServiceClient,
    MockSchoolServiceClient,
)
from app.services.student_service import StudentService

engine = create_engine(
    "sqlite:///./test_academics_inproc.db",
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
        path = f"./test_academics_inproc.db{suffix}"
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


# ─── InProcessSchoolClient ───

def test_validate_class_returns_row_when_present(db):
    cls = Class(school_id=SCHOOL_A, name="Grade 6", section="A")
    db.add(cls)
    db.commit()
    db.refresh(cls)

    client = InProcessSchoolClient(db)
    result = client.validate_class(cls.id, SCHOOL_A, token="")
    assert result is not None
    assert result["id"] == str(cls.id)
    assert result["school_id"] == str(SCHOOL_A)
    assert result["name"] == "Grade 6"


def test_validate_class_returns_none_when_missing(db):
    client = InProcessSchoolClient(db)
    assert client.validate_class(uuid.uuid4(), SCHOOL_A) is None


def test_validate_class_returns_none_on_cross_school_query(db):
    """BUG-001 / cross-tenant: class belongs to SCHOOL_A; SCHOOL_B can't see it."""
    cls = Class(school_id=SCHOOL_A, name="Grade 6", section="A")
    db.add(cls)
    db.commit()
    db.refresh(cls)

    client = InProcessSchoolClient(db)
    assert client.validate_class(cls.id, SCHOOL_B) is None


def test_validate_academic_year_returns_row_when_present(db):
    year = AcademicYear(
        school_id=SCHOOL_A, name="2026",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    db.add(year)
    db.commit()
    db.refresh(year)

    client = InProcessSchoolClient(db)
    result = client.validate_academic_year(year.id, SCHOOL_A)
    assert result is not None
    assert result["name"] == "2026"


def test_validate_academic_year_returns_none_cross_school(db):
    year = AcademicYear(
        school_id=SCHOOL_A, name="2026",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    db.add(year)
    db.commit()
    db.refresh(year)

    client = InProcessSchoolClient(db)
    assert client.validate_academic_year(year.id, SCHOOL_B) is None


# ─── Deprecated HttpSchoolServiceClient alias ───

def test_deprecated_alias_requires_db_session():
    """Calling HttpSchoolServiceClient() with no args must fail loudly."""
    with pytest.raises(RuntimeError, match="now requires a db session"):
        HttpSchoolServiceClient()


def test_deprecated_alias_works_with_db(db):
    """Passing a session into the deprecated name works — same as InProcess."""
    cls = Class(school_id=SCHOOL_A, name="Grade 6", section="A")
    db.add(cls)
    db.commit()
    db.refresh(cls)

    client = HttpSchoolServiceClient(db=db)
    assert client.validate_class(cls.id, SCHOOL_A) is not None


# ─── Seam closes: enrollment uses real DB ───

def test_enrollment_validation_goes_through_inprocess_client(db):
    """The full path: StudentService(...) + InProcessSchoolClient validates
    against the *real* Class + AcademicYear rows in academics_db, with NO
    network call. This is the exact thing PH2-7 was about.
    """
    # Real school data in the DB
    cls = Class(school_id=SCHOOL_A, name="Grade 6", section="A")
    year = AcademicYear(
        school_id=SCHOOL_A, name="2026",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    db.add_all([cls, year])
    db.commit()
    db.refresh(cls)
    db.refresh(year)

    # Real student
    student = Student(
        school_id=SCHOOL_A, student_code="S-001",
        first_name="Alice", last_name="N",
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # In-process service
    svc = StudentService(db, school_client=InProcessSchoolClient(db))
    result = svc.create_enrollment(
        school_id=SCHOOL_A,
        student_id=student.id,
        class_id=cls.id,
        academic_year_id=year.id,
        token="",
    )
    assert "error" not in result, f"unexpected error: {result}"

    rows = db.query(Enrollment).filter(Enrollment.student_id == student.id).all()
    assert len(rows) == 1


def test_enrollment_validation_fails_for_unknown_class(db):
    """Same path with a class that doesn't exist → DUPLICATE-style failure."""
    year = AcademicYear(
        school_id=SCHOOL_A, name="2026",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    db.add(year)
    db.commit()
    db.refresh(year)

    student = Student(
        school_id=SCHOOL_A, student_code="S-002",
        first_name="Bob", last_name="N",
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    svc = StudentService(db, school_client=InProcessSchoolClient(db))
    result = svc.create_enrollment(
        school_id=SCHOOL_A,
        student_id=student.id,
        class_id=uuid.uuid4(),  # doesn't exist
        academic_year_id=year.id,
        token="",
    )
    assert "error" in result


def test_mock_client_still_works(db):
    """The existing 40 student tests use MockSchoolServiceClient; keep working."""
    student = Student(
        school_id=SCHOOL_A, student_code="S-003",
        first_name="Carol", last_name="N",
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    mock = MockSchoolServiceClient()
    cls_id = uuid.uuid4()
    year_id = uuid.uuid4()
    mock.add_class(cls_id, SCHOOL_A)
    mock.add_year(year_id, SCHOOL_A)

    svc = StudentService(db, school_client=mock)
    result = svc.create_enrollment(
        school_id=SCHOOL_A,
        student_id=student.id,
        class_id=cls_id,
        academic_year_id=year_id,
        token="",
    )
    assert "error" not in result
