"""academics service — main app entry point.

PH2-5: shell with only /health.
PH2-6: school-service routes moved in. The service now serves /api/v1/schools,
       /api/v1/academics/*, /api/v1/classes, /api/v1/subjects, /api/v1/class-teachers,
       /api/v1/teachers/me/classes, /api/v1/provinces, /api/v1/districts, and the
       /api/v1/internal/teachers/* endpoints. Gateway routing stays on
       school-service until PH2-10 cutover — academics runs in parallel for
       parity testing.
PH2-7: student-service routes moved in (api/v1/students, /parents, /enrollments,
       /students/import + bulk-enroll + promote, /parents/me/children,
       /internal/parents/authorize). HttpSchoolServiceClient HTTP calls
       replaced with in-process InProcessSchoolClient queries against the
       co-located academics_db Class + AcademicYear tables.
PH2-8: attendance-service routes moved in (api/v1/attendance/sync,
       /attendance/records, /attendance/daily, /attendance/daily/records,
       /attendance/student-trend, /attendance/class-summary,
       /attendance/sync/batches). The HTTP hop into school-service
       /internal/teachers/authorize is gone — the new in-process
       `services/authorization.is_teacher_authorized_for_class` queries
       `class_teacher_assignments` directly.
PH2-9: assessment-service routes moved in (api/v1/assessments + marks bulk +
       student-marks + class-performance). The two remaining HTTP authz hops
       are gone — `is_teacher_authorized_for_student` joins
       `class_teacher_assignments ⋈ enrollments`;
       `is_parent_authorized_for_student` joins `parents ⋈ student_parents`.
       NEW Kafka emits: `eduzim.assessment.created.v1` and
       `eduzim.assessment.marks.recorded.v1` (the pre-consolidation
       assessment-service did not publish events at all). All four academic
       domains now live in academics_db.
PH2-11: /api/v1/reports/* moved in (dashboard / trend / financial / dropout /
       exports). Reads run against the reporting projection DB via a SECOND
       SQLAlchemy connection (see `app/reporting_db.py`). The reporting-
       service container is now a pure Kafka consumer — no HTTP surface.
       /reports/consume and /reports/rebuild dropped from HTTP entirely;
       the same logic is exposed as CLI tools under
       services/reporting-service/cli/. Dropout dropped two HTTP hops
       (students, attendance now in-process); fees still hits finance.
"""
import sys

from app.config import get_settings

settings = get_settings()

# Pull in the shared app factory if available. Falls back to a bare FastAPI
# instance otherwise so unit tests don't require the shared package.
sys.path.insert(0, "../../shared")
try:
    from eduzim_shared.app_factory import create_app
    app = create_app(
        title=settings.APP_NAME,
        service_name=settings.SERVICE_NAME,
        description=(
            "EduZim Academics — merged service combining school config, students, "
            "attendance, and assessments per ADR 006 + addendum. PH2-6 phase: only "
            "school config + classes + subjects + teacher assignments + geo are wired."
        ),
        debug=settings.DEBUG,
    )
except ImportError:  # pragma: no cover — local dev fallback
    from fastapi import FastAPI
    app = FastAPI(title=settings.APP_NAME, docs_url="/docs", redoc_url="/redoc")

    @app.get("/health")
    async def _health():
        return {
            "status": "healthy",
            "service": settings.SERVICE_NAME,
            "version": "0.2.0-ph2-6",
        }


# Always expose a /health that reports the current phase (in addition to the
# factory's /health if present). The factory variant just says "healthy"; this
# one tells callers which sub-phase we're at.
@app.get("/health/phase", tags=["Health"])
async def health_phase():
    return {
        "service": settings.SERVICE_NAME,
        "version": "0.6.0-ph2-11",
        "phase": (
            "PH2-11 — reporting reads folded in. /api/v1/reports/* now lives "
            "here; reporting-service runs as pure Kafka consumer with no HTTP."
        ),
    }


# Register the (formerly school-service) routes.
from app.api.routes import router as _school_router  # noqa: E402

# PH2-7: student-service routes + bulk operations.
from app.api.student_routes import router as _student_router  # noqa: E402
from app.api.bulk import router as _bulk_router  # noqa: E402

# PH2-8: attendance-service routes.
from app.api.attendance_routes import router as _attendance_router  # noqa: E402

# PH2-9: assessment-service routes.
from app.api.assessment_routes import router as _assessment_router  # noqa: E402

# PH2-11: reporting (read-side) routes.
from app.api.reports_query import router as _reports_router  # noqa: E402

# PH8-4: per-school + parent self-service export endpoints (data-rights).
from app.api.export_routes import router as _export_router  # noqa: E402

# Phase 9 / INFRA-018: audit log browse (admin-only).
from app.api.audit_routes import router as _audit_router  # noqa: E402

# Phase 11c / T-007: comment bank for marks remarks.
from app.api.comment_bank_routes import router as _comment_bank_router  # noqa: E402

# Phase 11d: planning surface (periods + lesson plans + formatives + seat plans).
from app.api.planning_routes import router as _planning_router  # noqa: E402

# Phase 11e: student-life surface (incidents + substitute grants + homework).
from app.api.student_life_routes import router as _student_life_router  # noqa: E402

# Phase 11f: org surface (HoD + CPD + self-eval + co-teacher).
from app.api.org_routes import router as _org_router  # noqa: E402

# Phase 12d/e/f: parent-life surfaces (events, conferences, slips,
# grievances, transport, meals, donations, newsletter, gallery,
# sibling discount).
from app.api.parent_life_routes import router as _parent_life_router  # noqa: E402

# Phase 13a: staff + HR + admissions + transfers.
from app.api.staff_routes import router as _staff_router  # noqa: E402

# Phase 13b: compliance reports + rollups + health records.
from app.api.compliance_routes import router as _compliance_router  # noqa: E402

# Phase 13c: finance/inventory/library/visitor admin surface.
from app.api.ops_routes import router as _ops_router  # noqa: E402

# Phase 13d: community surface (policies, sponsors, alumni).
from app.api.community_routes import router as _community_router  # noqa: E402

# Phase 13e: boarding + multi-campus.
from app.api.special_routes import router as _special_router  # noqa: E402

app.include_router(_school_router, prefix="/api/v1")
app.include_router(_student_router, prefix="/api/v1")
app.include_router(_bulk_router, prefix="/api/v1")
app.include_router(_attendance_router, prefix="/api/v1")
app.include_router(_assessment_router, prefix="/api/v1")
app.include_router(_reports_router, prefix="/api/v1")
app.include_router(_export_router, prefix="/api/v1")
app.include_router(_audit_router, prefix="/api/v1")
app.include_router(_comment_bank_router, prefix="/api/v1")
app.include_router(_planning_router, prefix="/api/v1")
app.include_router(_student_life_router, prefix="/api/v1")
app.include_router(_org_router, prefix="/api/v1")
app.include_router(_parent_life_router, prefix="/api/v1")
app.include_router(_staff_router, prefix="/api/v1")
app.include_router(_compliance_router, prefix="/api/v1")
app.include_router(_ops_router, prefix="/api/v1")
app.include_router(_community_router, prefix="/api/v1")
app.include_router(_special_router, prefix="/api/v1")
