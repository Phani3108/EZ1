"""Reports query API tests (PH2-11).

Covers the new academics endpoints:
  GET /reports/dashboard
  GET /reports/attendance/trend
  GET /reports/financial/summary
  GET /reports/dropout/summary
  GET /reports/dropout/students
  GET /reports/dropout/student/{id}

Setup strategy:
  * Two SQLite DBs: the primary academics_db (for students/attendance) and
    a second `reporting_db` file the projection mappings bind to.
  * Each test seeds projection rows directly via the ProjectionBase
    SessionLocal so we don't have to run the consumer.
  * Finance HTTP hops are mocked at the httpx-AsyncClient boundary.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

# PH3 / BUG-007: env vars must be set BEFORE importing app.config (which
# is what `get_settings` runs on import). tests/__init__.py already sets
# JWT_SECRET_KEY + INTERNAL_SERVICE_TOKEN to package-wide test values.
# Identity tokens are no longer JWT-decoded — tests inject gateway
# headers directly via the `token` fixture (a dict, not a string).
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_academics_reports.db")
os.environ.setdefault("REPORTING_DATABASE_URL", "sqlite:///./test_reporting_proj.db")
os.environ.setdefault("KAFKA_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base as AcademicsBase
from app.models import school as _s  # noqa
from app.models import student as _st  # noqa
from app.models import attendance as _a  # noqa
from app.models.projections import (
    AttendanceDailyAggregate,
    DashboardStats,
    FinancialSummary,
    ProcessedEvent,
    ProjectionBase,
    StudentCountProjection,
)


from sqlalchemy.pool import StaticPool


# Per-test in-memory SQLite engines. StaticPool keeps a single shared
# DBAPI connection alive for the lifetime of the engine — necessary
# because each `Session()` checkout would otherwise get its own private
# in-memory DB. `engine_factory` builds a fresh pair per test so there's
# zero cross-test pollution.
def _make_engines():
    a = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    r = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return a, r


# Module-level placeholders — replaced per-test by the autouse fixture.
academics_engine, reporting_engine = _make_engines()
AcademicsSession = sessionmaker(autocommit=False, autoflush=False, bind=academics_engine)
ReportingSession = sessionmaker(autocommit=False, autoflush=False, bind=reporting_engine)


@pytest.fixture(autouse=True)
def setup_dbs():
    """Build fresh in-memory engines for each test.

    Avoids the SQLite-file + pool-cache hazard entirely: a brand-new
    in-memory DB per test, dropped automatically when the engine is
    garbage-collected at fixture teardown.
    """
    global academics_engine, reporting_engine, AcademicsSession, ReportingSession
    academics_engine, reporting_engine = _make_engines()
    AcademicsSession = sessionmaker(autocommit=False, autoflush=False, bind=academics_engine)
    ReportingSession = sessionmaker(autocommit=False, autoflush=False, bind=reporting_engine)

    AcademicsBase.metadata.create_all(bind=academics_engine)
    ProjectionBase.metadata.create_all(bind=reporting_engine)

    # Force `reporting_db.get_reporting_db` to use OUR test engine instead
    # of the one it would otherwise lazily build from settings.
    import app.reporting_db as rdb
    rdb._engine = reporting_engine
    rdb._ReportingSession = ReportingSession

    yield

    academics_engine.dispose()
    reporting_engine.dispose()


@pytest.fixture
def academics_db():
    s = AcademicsSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def reporting_db():
    s = ReportingSession()
    try:
        yield s
    finally:
        s.close()


# ─── TestClient with DB overrides ───

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.reporting_db import get_reporting_db

    def _override_academics_db():
        s = AcademicsSession()
        try:
            yield s
        finally:
            s.close()

    def _override_reporting_db():
        s = ReportingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_academics_db
    app.dependency_overrides[get_reporting_db] = _override_reporting_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def token():
    """PH3 / BUG-007: returns a dict of gateway-injected headers, not a
    bearer token. The name `token` is preserved so every test signature
    still reads naturally; only the test bodies' header construction
    needs to switch from `{"Authorization": f"Bearer {token}"}` to
    `token` (the dict)."""
    return {
        "X-Gateway-Token": os.environ.get(
            "INTERNAL_SERVICE_TOKEN", "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
        ),
        "X-User-Id": str(uuid.uuid4()),
        "X-School-Id": str(SCHOOL_A),
        "X-User-Roles": "Admin",
        "X-Permissions": "report:read",
    }


SCHOOL_A = uuid.uuid4()
SCHOOL_B = uuid.uuid4()
YEAR_A = uuid.uuid4()


# ═══════════════════════════════════════════
# Dashboard / trend / financial — reads
# ═══════════════════════════════════════════

class TestDashboardRead:

    def test_empty_returns_zeroes(self, client, token):
        resp = client.get(
            "/api/v1/reports/dashboard",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_students"] == 0
        assert data["outstanding_fees"] == 0.0
        assert data["announcements_this_month"] == 0

    def test_seeded_stats(self, client, token, reporting_db):
        reporting_db.add(DashboardStats(
            school_id=str(SCHOOL_A),
            total_students=42,
            active_students=40,
            total_enrollments=45,
            attendance_today_present=38,
            attendance_today_total=40,
            total_invoiced=10000,
            total_paid=7500,
            announcements_this_month=6,
        ))
        reporting_db.commit()

        resp = client.get(
            "/api/v1/reports/dashboard",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_students"] == 42
        assert data["active_students"] == 40
        assert data["attendance_today_rate"] == 95.0
        assert data["outstanding_fees"] == 2500.0
        assert data["collected_this_term"] == 7500.0
        assert data["announcements_this_month"] == 6


class TestAttendanceTrendRead:

    def test_returns_only_rows_in_range(self, client, token, reporting_db):
        reporting_db.add_all([
            AttendanceDailyAggregate(
                school_id=str(SCHOOL_A), date=date(2026, 3, 1),
                present_count=20, absent_count=2, late_count=1,
            ),
            AttendanceDailyAggregate(
                school_id=str(SCHOOL_A), date=date(2026, 3, 2),
                present_count=18, absent_count=4, late_count=1,
            ),
            AttendanceDailyAggregate(
                school_id=str(SCHOOL_A), date=date(2026, 4, 10),
                present_count=22, absent_count=0, late_count=1,
            ),
        ])
        reporting_db.commit()
        resp = client.get(
            "/api/v1/reports/attendance/trend?from=2026-03-01&to=2026-03-31",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["date"] == "2026-03-01"
        assert data[1]["date"] == "2026-03-02"


class TestFinancialSummaryRead:

    def test_filter_by_year(self, client, token, reporting_db):
        other_year = uuid.uuid4()
        reporting_db.add_all([
            FinancialSummary(
                school_id=str(SCHOOL_A), academic_year_id=str(YEAR_A),
                total_invoiced=5000, total_paid=2000, total_outstanding=3000,
            ),
            FinancialSummary(
                school_id=str(SCHOOL_A), academic_year_id=str(other_year),
                total_invoiced=1000, total_paid=1000, total_outstanding=0,
            ),
        ])
        reporting_db.commit()

        resp = client.get(
            f"/api/v1/reports/financial/summary?year_id={YEAR_A}",
            headers=token,
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["total_invoiced"] == 5000.0


# ═══════════════════════════════════════════
# Cross-school isolation on projection reads
# ═══════════════════════════════════════════

class TestProjectionTenantIsolation:

    def test_dashboard_isolated(self, client, token, reporting_db):
        reporting_db.add_all([
            DashboardStats(school_id=str(SCHOOL_A), total_students=10),
            DashboardStats(school_id=str(SCHOOL_B), total_students=99),
        ])
        reporting_db.commit()
        resp = client.get(
            "/api/v1/reports/dashboard",
            headers=token,
        )
        assert resp.json()["data"]["total_students"] == 10


# ═══════════════════════════════════════════
# Dropout — in-process gather
# ═══════════════════════════════════════════

class TestDropoutEngineBoundary:
    """Boundary smoke test — heavy rules-engine tests live in
    services/reporting-service/tests/test_dropout.py (the pure-compute
    module didn't move). This class just ensures the engine wired through
    `app.services.reports.dropout_engine` produces matching scores."""

    def test_band_smoke(self):
        from app.services.reports.dropout_engine import DropoutRiskEngine
        days = [{"date": "2026-06-15", "status": "P"}] * 30
        r = DropoutRiskEngine.compute(days, [])
        assert r["risk_band"] == "LOW"


class TestDropoutSummaryInProcess:

    @patch("app.services.reports.dropout_data.httpx.AsyncClient")
    def test_summary_with_zero_students(self, mock_cls, client, token):
        # No students in academics_db → summary returns zero counts.
        resp = client.get(
            "/api/v1/reports/dropout/summary",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_students"] == 0
        assert data["at_risk_count"] == 0
        assert data["band_breakdown"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

    @patch("app.services.reports.dropout_data.httpx.AsyncClient")
    def test_summary_with_one_perfect_student(self, mock_cls, client, token, academics_db):
        # Seed an active student. The dropout flow runs in-process, so we
        # need a real student row; finance HTTP is mocked to return [].
        from app.services.student_service import StudentService
        svc = StudentService(academics_db)
        svc.create_student(
            school_id=SCHOOL_A,
            student_code="STU001",
            first_name="John",
            last_name="Doe",
            dob=date(2012, 5, 15),
            gender="MALE",
        )

        # Mock finance: empty invoice list → no fee signals.
        mock = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {"data": []}
        mock.get = AsyncMock(return_value=ok)

        resp = client.get(
            "/api/v1/reports/dropout/summary",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_students"] == 1
        # No attendance records → no attendance signals; no invoices →
        # no fee signals. Score should be 0, band LOW.
        assert data["band_breakdown"]["LOW"] == 1
        assert data["at_risk_count"] == 0


class TestDropoutDetailInProcess:

    @patch("app.services.reports.dropout_data.httpx.AsyncClient")
    def test_detail_with_consecutive_absences(
        self, mock_cls, client, token, academics_db
    ):
        # Build a student + 30 days of attendance with last 5 as absences.
        from app.services.student_service import StudentService
        svc = StudentService(academics_db)
        student = svc.create_student(
            school_id=SCHOOL_A,
            student_code="STU002",
            first_name="Anna",
            last_name="Test",
            dob=date(2012, 5, 15),
            gender="FEMALE",
        )
        sid = uuid.UUID(student["id"])

        from app.models.attendance import AttendanceRecord
        today = date.today()
        base = today - timedelta(days=29)
        for i in range(30):
            status = "A" if i >= 25 else "P"
            academics_db.add(AttendanceRecord(
                school_id=SCHOOL_A,
                student_id=sid,
                class_id=uuid.uuid4(),
                date=base + timedelta(days=i),
                status=status,
            ))
        academics_db.commit()

        # Mock finance: empty invoices.
        mock = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {"data": []}
        mock.get = AsyncMock(return_value=ok)

        resp = client.get(
            f"/api/v1/reports/dropout/student/{sid}",
            headers=token,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 5 consecutive absences → 40 points → MEDIUM. Attendance rate
        # is 25/30 = 83.3% → no rate signal.
        assert data["risk_score"] == 40
        assert data["risk_band"] == "MEDIUM"
        assert any(s["code"] == "CONSEC_ABSENT_5" for s in data["signals"])


# ═══════════════════════════════════════════
# Auth requirements (sanity)
# ═══════════════════════════════════════════

class TestAuth:

    def test_dashboard_requires_token(self, client):
        resp = client.get("/api/v1/reports/dashboard")
        assert resp.status_code in (401, 403)

    def test_dropout_requires_token(self, client):
        resp = client.get("/api/v1/reports/dropout/summary")
        assert resp.status_code in (401, 403)
