"""School-data client used by the student-side code paths.

History
-------
In the pre-consolidation student-service, this module made HTTP calls into
school-service to validate `class_id` and `academic_year_id` during enrolment
creation. PH2-7 — the student-side code now lives inside academics, and so
do the `Class` and `AcademicYear` models. The HTTP hop is gone; this module
keeps the `SchoolServiceClient` protocol (so tests can still inject a fake)
but the production implementation is `InProcessSchoolClient`, which queries
the same SQLAlchemy session that the caller is already using.

The previous `HttpSchoolServiceClient` name is retained as a deprecated
alias so the unmodified route + bulk modules still import successfully —
but it now wraps `InProcessSchoolClient` and *requires* a session.

This closes the "intra-process replacement for /api/v1/classes HTTP call"
seam called out in the ADR-006 addendum §2.
"""

import logging
import uuid
from typing import Optional, Protocol

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SchoolServiceClient(Protocol):
    """Protocol for school-data lookups (kept for test injection)."""

    def validate_class(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        token: str,
    ) -> Optional[dict]: ...

    def validate_academic_year(
        self,
        year_id: uuid.UUID,
        school_id: uuid.UUID,
        token: str,
    ) -> Optional[dict]: ...


class InProcessSchoolClient:
    """Production implementation — direct DB queries against academics_db.

    The `token` parameter is ignored (kept for protocol compatibility with
    the old HTTP client). Authorization happens at the gateway + dependency
    layer before any of these methods run.

    Constructed per-request with the caller's session so we participate in
    the same transaction.
    """

    def __init__(self, db: Session):
        self._db = db

    def validate_class(
        self,
        class_id: uuid.UUID,
        school_id: uuid.UUID,
        token: str = "",
    ) -> Optional[dict]:
        # Lazy import to keep the module import graph clean.
        from app.models.school import Class as SchoolClass
        cls = self._db.query(SchoolClass).filter(
            SchoolClass.id == class_id,
            SchoolClass.school_id == school_id,
        ).first()
        if not cls:
            return None
        return {
            "id": str(cls.id),
            "school_id": str(cls.school_id),
            "name": cls.name,
            "section": cls.section,
            "is_active": cls.is_active,
        }

    def validate_academic_year(
        self,
        year_id: uuid.UUID,
        school_id: uuid.UUID,
        token: str = "",
    ) -> Optional[dict]:
        from app.models.school import AcademicYear
        year = self._db.query(AcademicYear).filter(
            AcademicYear.id == year_id,
            AcademicYear.school_id == school_id,
        ).first()
        if not year:
            return None
        return {
            "id": str(year.id),
            "school_id": str(year.school_id),
            "name": year.name,
            "is_active": year.is_active,
        }


class HttpSchoolServiceClient(InProcessSchoolClient):
    """Deprecated alias kept for one transitional minor release.

    The old class made HTTP calls into a sibling service. After PH2-7 the
    data is local; the production replacement requires a `db` session. Routes
    have been updated to pass it; if you still see `HttpSchoolServiceClient()`
    without arguments somewhere, that's a bug — fix it to pass `db` (or use
    `InProcessSchoolClient` directly).
    """

    def __init__(self, db: Session = None):  # type: ignore[override]
        if db is None:
            raise RuntimeError(
                "HttpSchoolServiceClient was renamed and now requires a db "
                "session. Use InProcessSchoolClient(db) directly."
            )
        super().__init__(db)


class MockSchoolServiceClient:
    """Mock client for unit tests — pre-loaded with known classes/years.

    Identical shape and behaviour to the pre-consolidation mock; existing
    student tests reuse it without changes.
    """

    def __init__(self):
        self._classes: dict[str, dict] = {}
        self._years: dict[str, dict] = {}

    def add_class(self, class_id: uuid.UUID, school_id: uuid.UUID, name: str = "Grade 1"):
        self._classes[str(class_id)] = {
            "id": str(class_id), "school_id": str(school_id), "name": name,
        }

    def add_year(self, year_id: uuid.UUID, school_id: uuid.UUID, name: str = "2026"):
        self._years[str(year_id)] = {
            "id": str(year_id), "school_id": str(school_id), "name": name,
        }

    def validate_class(self, class_id: uuid.UUID, school_id: uuid.UUID,
                       token: str = "") -> Optional[dict]:
        cls = self._classes.get(str(class_id))
        if cls and cls["school_id"] == str(school_id):
            return cls
        return None

    def validate_academic_year(self, year_id: uuid.UUID, school_id: uuid.UUID,
                                token: str = "") -> Optional[dict]:
        year = self._years.get(str(year_id))
        if year and year["school_id"] == str(school_id):
            return year
        return None
