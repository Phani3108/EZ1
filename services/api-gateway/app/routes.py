"""
Route Table + RBAC Permissions Map
=====================================
Single source of truth for:
  - route prefix → downstream service URL
  - route pattern → required permission(s)
"""

# ───────────── Service Route Map ─────────────
# prefix → (env key for service URL, service name)

SERVICE_ROUTES = {
    "/api/v1/auth": ("AUTH_SERVICE_URL", "auth-service"),
    "/api/v1/schools": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/academic-years": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/terms": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/classes": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/subjects": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/class-teachers": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/teachers": ("SCHOOL_SERVICE_URL", "school-service"),
    "/api/v1/students": ("STUDENT_SERVICE_URL", "student-service"),
    "/api/v1/parents": ("STUDENT_SERVICE_URL", "student-service"),
    "/api/v1/enrollments": ("STUDENT_SERVICE_URL", "student-service"),
    "/api/v1/attendance": ("ATTENDANCE_SERVICE_URL", "attendance-service"),
    "/api/v1/fees": ("FEES_SERVICE_URL", "fees-service"),
    "/api/v1/comm": ("COMMUNICATION_SERVICE_URL", "communication-service"),
    "/api/v1/reports": ("REPORTING_SERVICE_URL", "reporting-service"),
    "/api/v1/assessments": ("ASSESSMENT_SERVICE_URL", "assessment-service"),
}


# ───────────── RBAC Permissions ─────────────
# (method, path_prefix) → required permission(s)
# Permissions: school:manage, student:write, student:read, attendance:write,
#              attendance:read, fees:write, fees:read, comm:write, comm:read,
#              report:read, report:admin

RBAC_MAP = [
    # Auth — public endpoints (login, register handled by auth-service)
    ("POST", "/api/v1/auth/login", None),
    ("POST", "/api/v1/auth/register", None),
    ("GET", "/api/v1/auth/me", "authenticated"),

    # School
    ("POST", "/api/v1/schools", "school:manage"),
    ("GET", "/api/v1/schools", "school:manage"),
    ("PUT", "/api/v1/schools", "school:manage"),
    ("POST", "/api/v1/academic-years", "school:manage"),
    ("GET", "/api/v1/academic-years", "authenticated"),
    ("POST", "/api/v1/terms", "school:manage"),
    ("GET", "/api/v1/terms", "authenticated"),
    ("POST", "/api/v1/classes", "school:manage"),
    ("GET", "/api/v1/classes", "authenticated"),
    ("POST", "/api/v1/subjects", "school:manage"),
    ("GET", "/api/v1/subjects", "authenticated"),
    ("POST", "/api/v1/class-teachers", "school:manage"),
    ("GET", "/api/v1/class-teachers", "authenticated"),

    # Teacher self-service
    ("GET", "/api/v1/teachers/me/classes", "teacher:read"),

    # Students
    ("POST", "/api/v1/students", "student:write"),
    ("GET", "/api/v1/students", "student:read"),
    ("PUT", "/api/v1/students", "student:write"),
    ("DELETE", "/api/v1/students", "student:write"),

    # Parent self-service (any authenticated parent can see their own children)
    ("GET", "/api/v1/parents/me/children", "authenticated"),

    ("POST", "/api/v1/parents", "student:write"),
    ("GET", "/api/v1/parents", "student:read"),
    ("POST", "/api/v1/enrollments", "student:write"),
    ("GET", "/api/v1/enrollments", "student:read"),

    # Attendance
    ("POST", "/api/v1/attendance/sync", "attendance:write"),
    ("POST", "/api/v1/attendance/records", "attendance:write"),
    ("GET", "/api/v1/attendance/sync/batches", "school:manage"),
    ("GET", "/api/v1/attendance/student-trend", "authenticated"),
    ("GET", "/api/v1/attendance/daily/records", "attendance:read"),
    ("GET", "/api/v1/attendance", "attendance:read"),

    # Fees
    ("POST", "/api/v1/fees", "fees:write"),
    ("GET", "/api/v1/fees/invoices", "authenticated"),
    ("GET", "/api/v1/fees", "fees:read"),

    # Communication
    ("POST", "/api/v1/comm", "comm:write"),
    ("GET", "/api/v1/comm/feed", "authenticated"),
    ("GET", "/api/v1/comm", "comm:read"),
    ("DELETE", "/api/v1/comm", "comm:write"),

    # Reports
    ("GET", "/api/v1/reports", "report:read"),
    ("POST", "/api/v1/reports/rebuild", "report:admin"),
    ("POST", "/api/v1/reports/consume", "report:admin"),

    # Assessments
    ("POST", "/api/v1/assessments", "assessment:write"),
    ("GET", "/api/v1/assessments", "assessment:read"),
]


def get_required_permission(method: str, path: str) -> str:
    """Look up required permission for a request. Returns None for public."""
    for rbac_method, rbac_path, perm in RBAC_MAP:
        if method == rbac_method and path.startswith(rbac_path):
            return perm
    # Default: authenticated
    return "authenticated"


def resolve_service(path: str) -> tuple:
    """Resolve path to (service_url_key, service_name) or None."""
    for prefix, (url_key, svc_name) in SERVICE_ROUTES.items():
        if path.startswith(prefix):
            return url_key, svc_name
    return None, None
