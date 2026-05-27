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
    # /api/v1/auth resolves at the identity service (PH2-2 rename).
    "/api/v1/auth": ("IDENTITY_SERVICE_URL", "identity"),
    # ─── PH2-10 cutover ────────────────────────────────────────────────
    # All academic-domain prefixes (13) now route to the merged `academics`
    # service. The old per-service containers (school/student/attendance/
    # assessment) remain running during PH2-12's 1-week burn-in so a
    # rollback is one config flip. The route names below intentionally use
    # "academics" so /metrics, logs, and the diagnostics integration card
    # all show one consolidated service.
    "/api/v1/schools": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/academic-years": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/terms": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/classes": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/subjects": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/class-teachers": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/teachers": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/students": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/parents": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/enrollments": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/attendance": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/assessments": ("ACADEMICS_SERVICE_URL", "academics"),
    # PH2-10 also closes the long-standing gateway-routing gap for the
    # provinces + districts reference endpoints (they were never explicitly
    # wired pre-consolidation; admin-web reached them via a direct port).
    "/api/v1/provinces": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/districts": ("ACADEMICS_SERVICE_URL", "academics"),
    # ───────────────────────────────────────────────────────────────────
    # PH2-3: renamed downstream service (finance).
    "/api/v1/fees": ("FINANCE_SERVICE_URL", "finance"),
    # PH2-4: renamed downstream service (communications).
    "/api/v1/comm": ("COMMUNICATIONS_SERVICE_URL", "communications"),
    # PH2-11 cutover: /reports/* now served by academics (read-only). The
    # reporting-service container runs as a pure Kafka consumer with no
    # HTTP surface. /reports/consume and /reports/rebuild are gone from the
    # public API entirely — equivalent functionality is in
    # services/reporting-service/cli/ for ops use.
    "/api/v1/reports": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 9 / INFRA-018: cross-cutting academic audit-log browse.
    # Finance + communications expose their own service-prefixed
    # paths (/fees/audit-log, /comm/audit-log) that route via their
    # respective service prefixes above. Academics gets the bare
    # /audit-log path because it's the consolidated academic-domain
    # service and pre-dates the per-service split.
    "/api/v1/audit-log": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 11c / T-007 — comment bank lives in academics.
    "/api/v1/comment-bank": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 11d — planning routes (periods, lesson plans, formatives,
    # exam seat plans) all live in academics.
    "/api/v1/periods": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/lesson-plans": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/formative-assessments": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/exam-seat-plans": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 11e — student-life routes (incidents, substitute grants,
    # homework + submissions) live in academics.
    "/api/v1/incidents": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/substitute-grants": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/homework": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 11f — org routes (HoD, CPD, self-eval, co-teacher).
    "/api/v1/hod-assignments": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/cpd": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/self-evaluations": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/class-teachers/co": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 13a — staff + HR + admissions + transfers (academics).
    "/api/v1/staff": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/leave-requests": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/contracts": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/salary-slips": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/performance-reviews": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/admissions": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/transfers": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 13b — compliance + health records (academics).
    "/api/v1/compliance": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/health-records": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 13c — operations / inventory / library / visitors (academics).
    "/api/v1/expenses": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/vendor-payments": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/capital-projects": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/assets": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/library": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/visitors": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 13d — community (policies, sponsors, alumni).
    "/api/v1/policies": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/sponsors": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/sponsorships": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/alumni": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 13e — boarding + multi-campus.
    "/api/v1/boarding": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/campuses": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 14 — Ministry (MoPSE) cross-school aggregation (read-only).
    # DEC-013: ministry:read is the ONLY permission Ministry holds.
    # Most Ministry endpoints proxy academics, but the fees rollup
    # (M-003) lives in finance because that's where the Invoice table
    # is. Per ADR 020 the admin-web client joins finance per-school
    # totals against academics geography reference data — no
    # cross-service HTTP on Ministry page loads.
    "/api/v1/ministry/fees": ("FINANCE_SERVICE_URL", "finance"),
    "/api/v1/ministry": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 15 — Onboarding (setup wizard) endpoints.
    # Invitations live in identity; readiness + drafts + bulk-teachers
    # + templates live in academics; bulk-fees lives in finance; invite
    # dispatch + outbox live in communications.
    "/api/v1/invitations": ("IDENTITY_SERVICE_URL", "identity"),
    "/api/v1/drafts": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/onboarding": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/templates": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/bulk/teachers": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/bulk/invite-requests": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/bulk/fee-structures": ("FINANCE_SERVICE_URL", "finance"),
    # Communications-side onboarding endpoints live under /comm/* to
    # avoid path collision with identity's /invitations/* — the gateway
    # iterates SERVICE_ROUTES by insertion order, and we want every
    # identity invitation path to keep going to identity.
    "/api/v1/comm/invitations": ("COMMUNICATIONS_SERVICE_URL", "communications"),
    "/api/v1/comm/invite-outbox": ("COMMUNICATIONS_SERVICE_URL", "communications"),

    # Phase 16 — academic-content (curriculum, question bank,
    # templates). All in academics.
    "/api/v1/curriculum": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/ministry/national-curriculum": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/ministry/bulk/national-curriculum": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/bulk/curriculum": ("ACADEMICS_SERVICE_URL", "academics"),
    # Phase 18b — cross-school Ministry-distributed templates.
    "/api/v1/ministry/national-templates": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/national-templates": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/questions": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/question-drafts": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/homework-templates": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/lesson-plan-templates": ("ACADEMICS_SERVICE_URL", "academics"),

    # Phase 12d/e/f — parent-life surfaces (all in academics).
    "/api/v1/school-events": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/performance-opt-out": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/conference-slots": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/conference-bookings": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/permission-slips": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/grievances": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/transport-buses": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/transport-pings": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/meal-credit": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/donations": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/newsletter": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/gallery": ("ACADEMICS_SERVICE_URL", "academics"),
    "/api/v1/sibling-discount-rule": ("ACADEMICS_SERVICE_URL", "academics"),
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
    # Phase 12g — student self-service (/students/me) BEFORE the
    # broader student:read prefix so it gates on `authenticated`.
    ("GET", "/api/v1/students/me", "authenticated"),
    # Phase 12a — admin link of Student → identity User.
    ("POST", "/api/v1/students/", "student:write"),  # /{id}/link-user etc
    ("POST", "/api/v1/students", "student:write"),
    ("GET", "/api/v1/students", "student:read"),
    ("PUT", "/api/v1/students", "student:write"),
    ("DELETE", "/api/v1/students", "student:write"),

    # Parent self-service (any authenticated parent can see their own children)
    ("GET", "/api/v1/parents/me/children", "authenticated"),
    # PH8-4: data-rights / right-to-export. Authenticated parents can
    # export their own (and their children's) data.
    ("GET", "/api/v1/parents/me/export", "authenticated"),

    ("POST", "/api/v1/parents", "student:write"),
    ("GET", "/api/v1/parents", "student:read"),
    ("POST", "/api/v1/enrollments", "student:write"),
    ("GET", "/api/v1/enrollments", "student:read"),

    # PH8-4: school admin export. The full per-school dump is
    # admin-only.
    ("GET", "/api/v1/schools/me/export", "school:manage"),

    # Phase 9 / INFRA-018: audit log browse — admin-only, school-scoped.
    # Phase 9 follow-up — per-service audit log browse. All are
    # admin-only (`school:manage`); each routes to a different
    # downstream service.
    ("GET", "/api/v1/audit-log", "school:manage"),               # academics
    ("GET", "/api/v1/fees/audit-log", "school:manage"),          # finance
    ("GET", "/api/v1/comm/audit-log", "school:manage"),          # communications

    # Attendance
    ("POST", "/api/v1/attendance/sync", "attendance:write"),
    ("POST", "/api/v1/attendance/records", "attendance:write"),
    ("GET", "/api/v1/attendance/sync/batches", "school:manage"),
    ("GET", "/api/v1/attendance/student-trend", "authenticated"),
    ("GET", "/api/v1/attendance/daily/records", "attendance:read"),
    ("GET", "/api/v1/attendance", "attendance:read"),

    # Fees — Phase 12b provider-config + provider-aware initiate.
    # ORDER MATTERS: more-specific paths first.
    ("GET",  "/api/v1/fees/payment-config", "school:manage"),
    ("PUT",  "/api/v1/fees/payment-config", "school:manage"),
    # Phase 12b provider-aware checkout (new path; the legacy
    # /fees/payments/initiate stays for Paynow-direct callers).
    ("POST", "/api/v1/fees/payments/checkout", "authenticated"),
    ("POST", "/api/v1/fees/payments/manual/confirm", "school:manage"),
    # P-011: parents can download their own receipts. The route layer
    # confirms the payment belongs to one of the caller's children
    # before serving the PDF.
    ("GET",  "/api/v1/fees/payments/", "authenticated"),

    # Fees
    ("POST", "/api/v1/fees", "fees:write"),
    ("GET", "/api/v1/fees/invoices", "authenticated"),
    ("GET", "/api/v1/fees", "fees:read"),

    # Phase 11b / T-011 — parent-teacher 1:1 messaging.
    # ORDER MATTERS: prefix-matching is first-hit-wins, so the
    # /messages/threads/* paths must precede both the catch-all
    # /messages/{id}/redact rule (school:manage) and the broader
    # /api/v1/comm announcements rules. The auth model: any
    # participant can use the threads surface; redaction is
    # admin-only.
    ("GET",    "/api/v1/comm/messages/threads", "authenticated"),
    ("POST",   "/api/v1/comm/messages/threads", "authenticated"),
    ("GET",    "/api/v1/comm/messages/threads/", "authenticated"),
    ("POST",   "/api/v1/comm/messages/threads/", "authenticated"),
    # /api/v1/comm/messages/{id}/redact — admin only.
    ("POST",   "/api/v1/comm/messages/", "school:manage"),

    # Phase 11b / T-008 — attachments. Upload + list + download +
    # delete. The route layer enforces school-scope + uploader/admin
    # authorisation for delete; the gateway just gates "must be
    # authenticated" because any participant of a thread or recipient
    # of an announcement can need to read its attachments.
    ("POST",   "/api/v1/comm/attachments", "authenticated"),
    ("GET",    "/api/v1/comm/attachments", "authenticated"),
    ("DELETE", "/api/v1/comm/attachments/", "authenticated"),

    # Phase 12c — notification provider config + dispatch.
    ("GET",  "/api/v1/comm/notification-config", "school:manage"),
    ("PUT",  "/api/v1/comm/notification-config", "school:manage"),
    ("POST", "/api/v1/comm/notify/dispatch", "school:manage"),

    # Communication (announcements). Placed AFTER messaging so the
    # broader /api/v1/comm prefix doesn't swallow /comm/messages/*.
    ("POST", "/api/v1/comm", "comm:write"),
    ("GET", "/api/v1/comm/feed", "authenticated"),
    ("GET", "/api/v1/comm", "comm:read"),
    ("DELETE", "/api/v1/comm", "comm:write"),

    # Reports — PH2-11: writes (consume/rebuild) dropped from public API.
    # Operators run the equivalents as CLI scripts inside the reporting
    # consumer container; see services/reporting-service/cli/.
    ("GET", "/api/v1/reports", "report:read"),

    # Assessments
    ("POST", "/api/v1/assessments", "assessment:write"),
    ("GET", "/api/v1/assessments", "assessment:read"),

    # Phase 11c / T-007 — comment bank. Read is open to any teacher
    # entering marks; writes are admin-only.
    ("GET",    "/api/v1/comment-bank", "authenticated"),
    ("POST",   "/api/v1/comment-bank", "school:manage"),
    ("PUT",    "/api/v1/comment-bank/", "school:manage"),
    ("DELETE", "/api/v1/comment-bank/", "school:manage"),

    # Phase 11d planning surface.
    # Periods (T-010): admin manages; everyone reads.
    ("GET",  "/api/v1/periods", "authenticated"),
    ("POST", "/api/v1/periods", "school:manage"),
    # Lesson plans (T-005): teacher can create/edit own; reads are
    # gated only at "authenticated" (the route layer scopes by school).
    ("GET",  "/api/v1/lesson-plans", "authenticated"),
    ("POST", "/api/v1/lesson-plans", "authenticated"),
    ("PUT",  "/api/v1/lesson-plans/", "authenticated"),
    # Formative assessments (T-013).
    ("GET",  "/api/v1/formative-assessments", "authenticated"),
    ("POST", "/api/v1/formative-assessments", "authenticated"),
    # Exam seat plans (T-012). Admin-managed because exam logistics
    # belong to the school office.
    ("GET",  "/api/v1/exam-seat-plans", "authenticated"),
    ("POST", "/api/v1/exam-seat-plans", "school:manage"),

    # Phase 11e — incidents (T-004), substitute grants (T-006),
    # homework (T-003).
    ("GET",  "/api/v1/incidents", "authenticated"),
    ("POST", "/api/v1/incidents", "authenticated"),
    ("PUT",  "/api/v1/incidents/", "authenticated"),
    # Substitute grants — admin issues, teacher views their own.
    ("GET",  "/api/v1/substitute-grants", "authenticated"),
    ("POST", "/api/v1/substitute-grants", "school:manage"),
    # /substitute-grants/{id}/revoke is also admin.
    # Homework — any teacher can assign + grade; reads open to any
    # authenticated participant (route-layer scoping).
    ("GET",  "/api/v1/homework", "authenticated"),
    ("POST", "/api/v1/homework", "authenticated"),
    ("PUT",  "/api/v1/homework/", "authenticated"),

    # Phase 11f — org routes.
    # HoD assignments — read open (HoD views their own scope), write
    # admin-only.
    ("GET",    "/api/v1/hod-assignments", "authenticated"),
    ("POST",   "/api/v1/hod-assignments", "school:manage"),
    ("DELETE", "/api/v1/hod-assignments/", "school:manage"),
    # CPD — teacher self-service; read open; admin can read any user
    # via the user_id query (route layer enforces).
    ("GET",  "/api/v1/cpd", "authenticated"),
    ("POST", "/api/v1/cpd", "authenticated"),
    # Self-evaluation — teacher self-service.
    ("GET",  "/api/v1/self-evaluations", "authenticated"),
    ("POST", "/api/v1/self-evaluations", "authenticated"),
    # Co-teacher assignment — admin-only.
    ("POST", "/api/v1/class-teachers/co", "school:manage"),

    # Phase 13a — staff + HR + admissions + transfers.
    # Staff CRUD — admin only.
    ("GET",  "/api/v1/staff", "school:manage"),
    ("POST", "/api/v1/staff", "school:manage"),
    ("POST", "/api/v1/staff/", "school:manage"),  # /{id}/terminate
    # Leave: anyone authenticated can request + read own; admin lists all
    # + decides.
    ("GET",  "/api/v1/leave-requests", "authenticated"),
    ("POST", "/api/v1/leave-requests", "authenticated"),
    ("PUT",  "/api/v1/leave-requests/", "school:manage"),  # /{id}/decide
    # Contracts — admin manages; users read own.
    ("GET",  "/api/v1/contracts", "authenticated"),
    ("POST", "/api/v1/contracts", "school:manage"),
    # Salary slips — admin issues; users read own.
    ("GET",  "/api/v1/salary-slips", "authenticated"),
    ("POST", "/api/v1/salary-slips", "school:manage"),
    # Performance reviews — admin/HoD writes; users read own.
    ("GET",  "/api/v1/performance-reviews", "authenticated"),
    ("POST", "/api/v1/performance-reviews", "school:manage"),
    # Admissions — admin manages; submissions can come from the admin UI
    # (the parent-facing application form is Phase 14 follow-up).
    ("GET",  "/api/v1/admissions", "school:manage"),
    ("POST", "/api/v1/admissions", "school:manage"),
    ("PUT",  "/api/v1/admissions/", "school:manage"),  # /{id}/decide
    # Transfers — admin only.
    ("GET",  "/api/v1/transfers", "school:manage"),
    ("POST", "/api/v1/transfers", "school:manage"),

    # Phase 13b — compliance + health records.
    # Compliance templates + submissions — admin only.
    ("GET",  "/api/v1/compliance/templates", "school:manage"),
    ("POST", "/api/v1/compliance/templates", "school:manage"),
    ("GET",  "/api/v1/compliance/submissions", "school:manage"),
    ("POST", "/api/v1/compliance/submissions", "school:manage"),
    ("PUT",  "/api/v1/compliance/submissions/", "school:manage"),
    ("GET",  "/api/v1/compliance/discipline-rollup", "school:manage"),
    ("GET",  "/api/v1/compliance/grievance-rollup", "school:manage"),
    # Health records — admin OR nurse (route layer also checks).
    ("GET",  "/api/v1/health-records/", "school:manage"),
    ("PUT",  "/api/v1/health-records/", "school:manage"),

    # Phase 13c — operations / inventory / library / visitors.
    # All admin-only.
    ("GET",  "/api/v1/expenses", "school:manage"),
    ("POST", "/api/v1/expenses", "school:manage"),
    ("GET",  "/api/v1/vendor-payments", "school:manage"),
    ("POST", "/api/v1/vendor-payments", "school:manage"),
    ("GET",  "/api/v1/capital-projects", "school:manage"),
    ("POST", "/api/v1/capital-projects", "school:manage"),
    ("PUT",  "/api/v1/capital-projects/", "school:manage"),
    ("GET",  "/api/v1/assets", "school:manage"),
    ("POST", "/api/v1/assets", "school:manage"),
    ("POST", "/api/v1/assets/", "school:manage"),  # /{id}/movements
    # Library — admin manages catalog; staff users can read.
    ("GET",  "/api/v1/library/books", "authenticated"),
    ("POST", "/api/v1/library/books", "school:manage"),
    ("POST", "/api/v1/library/loans", "school:manage"),
    ("POST", "/api/v1/library/loans/", "school:manage"),
    # Visitors — admin/reception manages.
    ("GET",  "/api/v1/visitors", "school:manage"),
    ("POST", "/api/v1/visitors", "school:manage"),
    ("POST", "/api/v1/visitors/", "school:manage"),

    # Phase 13d — community.
    # Policies — read open (parents see published ones); write admin.
    ("GET",  "/api/v1/policies", "authenticated"),
    ("POST", "/api/v1/policies", "school:manage"),
    # Sponsors + sponsorships — admin only.
    ("GET",  "/api/v1/sponsors", "school:manage"),
    ("POST", "/api/v1/sponsors", "school:manage"),
    ("GET",  "/api/v1/sponsorships", "school:manage"),
    ("POST", "/api/v1/sponsorships", "school:manage"),
    ("PUT",  "/api/v1/sponsorships/", "school:manage"),
    # Alumni — admin only.
    ("GET",  "/api/v1/alumni", "school:manage"),
    ("POST", "/api/v1/alumni", "school:manage"),
    ("PUT",  "/api/v1/alumni/", "school:manage"),

    # Phase 13e — boarding + multi-campus. Admin only.
    ("GET",  "/api/v1/boarding/", "school:manage"),
    ("POST", "/api/v1/boarding/", "school:manage"),
    ("GET",  "/api/v1/campuses", "authenticated"),
    ("POST", "/api/v1/campuses", "school:manage"),

    # Phase 14 — Ministry (MoPSE) cross-school aggregation (READ-ONLY).
    # DEC-013: ministry:read is the only permission Ministry holds.
    # NO POST / PUT / DELETE entries here — they would 404 (router does
    # not register them) but listing them explicitly here would also be
    # wrong: gateway must not advertise write paths under /ministry.
    # The academics route layer asserts the Ministry role again as
    # defence-in-depth.
    ("GET", "/api/v1/ministry/schools", "ministry:read"),
    ("GET", "/api/v1/ministry/enrolment", "ministry:read"),
    ("GET", "/api/v1/ministry/attendance", "ministry:read"),
    ("GET", "/api/v1/ministry/geography", "ministry:read"),
    # M-003 — finance rollup. Proxied to finance-service.
    ("GET", "/api/v1/ministry/fees", "ministry:read"),
    ("GET", "/api/v1/ministry/fees/defaulters", "ministry:read"),
    # M-004 — compliance rollup (lives in academics).
    ("GET", "/api/v1/ministry/compliance", "ministry:read"),
    # M-005 — dropout heatmap (academics).
    ("GET", "/api/v1/ministry/dropouts", "ministry:read"),
    # M-006 — subject pass-rate by region (academics).
    ("GET", "/api/v1/ministry/pass-rate", "ministry:read"),
    # M-007 — PTR (academics). Device + electricity TBD in follow-up.
    ("GET", "/api/v1/ministry/ptr", "ministry:read"),
    # M-008 — comparative side-by-side per-school view.
    ("GET", "/api/v1/ministry/comparative", "ministry:read"),
    # M-009 — policy impact (before/after metric).
    ("GET", "/api/v1/ministry/policy-impact", "ministry:read"),
    # M-010 — donor / NGO impact rollup.
    ("GET", "/api/v1/ministry/donors", "ministry:read"),
    # M-011 — UNESCO / UNICEF export snapshot.
    ("GET", "/api/v1/ministry/exports", "ministry:read"),

    # Phase 15 — Onboarding (setup wizard) RBAC.
    # Invitations: write paths gated on invite:write; the public
    # preview / accept / by-code paths bypass via "authenticated"
    # being a no-token-required marker handled by the gateway's
    # public-paths config (see auth.py allowlist). We keep the
    # endpoints listed here so the RBAC map covers everything.
    # Public-by-design (no auth) — these let parents/teachers land on
    # the invite-claim page without a JWT. The token / 6-digit code IS
    # the auth here, validated server-side by identity.
    ("GET",    "/api/v1/invitations/by-code", None),
    ("POST",   "/api/v1/invitations/by-code", None),
    # Token-pathed public endpoints. Use a sentinel-style longer prefix
    # so they match before the bare `/invitations` write rule below.
    # NOTE: startswith() ordering — keep the more-specific entries first.
    ("GET",    "/api/v1/invitations/", None),   # preview path: /{token}/preview
    ("POST",   "/api/v1/invitations/", None),   # accept / resend (resend needs auth, allow but rely on identity to enforce)
    ("POST",   "/api/v1/invitations", "invite:write"),
    ("GET",    "/api/v1/invitations", "invite:write"),  # list (auth required)
    # Drafts.
    ("POST",   "/api/v1/drafts/students", "student:draft"),
    ("GET",    "/api/v1/drafts/students", "school:manage"),
    ("POST",   "/api/v1/drafts/students/", "school:manage"),
    ("GET",    "/api/v1/drafts/parents", "school:manage"),
    ("POST",   "/api/v1/drafts/parents/", "school:manage"),
    # Onboarding readiness + Go Live.
    ("GET",    "/api/v1/onboarding/status", "school:manage"),
    ("POST",   "/api/v1/onboarding/go-live", "school:manage"),
    # Templates — any authenticated user can download.
    ("GET",    "/api/v1/templates", "authenticated"),
    # Bulk imports.
    ("POST",   "/api/v1/bulk/teachers", "school:manage"),
    ("POST",   "/api/v1/bulk/fee-structures", "school:manage"),
    ("GET",    "/api/v1/bulk/invite-requests", "school:manage"),
    ("POST",   "/api/v1/bulk/invite-requests/", "school:manage"),
    # Invite outbox (communications) — admin reads its own school's
    # outbox; worker uses internal-only paths.
    ("GET",    "/api/v1/comm/invite-outbox", "school:manage"),
    ("POST",   "/api/v1/comm/invite-outbox/", "school:manage"),
    ("POST",   "/api/v1/comm/invitations/dispatch", "invite:write"),

    # Phase 16 — Curriculum (school-local).
    ("GET",    "/api/v1/curriculum/tree", "authenticated"),
    ("GET",    "/api/v1/curriculum/subjects", "authenticated"),
    ("GET",    "/api/v1/curriculum/topics/", "authenticated"),
    ("GET",    "/api/v1/curriculum/coverage", "school:manage"),
    ("POST",   "/api/v1/curriculum/subjects", "school:manage"),
    ("POST",   "/api/v1/curriculum/units", "school:manage"),
    ("POST",   "/api/v1/curriculum/topics", "school:manage"),
    ("POST",   "/api/v1/curriculum/adopt-subject", "school:manage"),
    ("POST",   "/api/v1/curriculum/tag", "authenticated"),
    ("POST",   "/api/v1/bulk/curriculum", "school:manage"),
    # Phase 17d / 18a — curriculum versioning + upgrade flow.
    ("GET",    "/api/v1/curriculum/upgrade-subject/preview", "school:manage"),
    ("POST",   "/api/v1/curriculum/upgrade-subject", "school:manage"),

    # Ministry-side National Curriculum.
    # Reads open to ministry:read OR school:manage (SchoolAdmin browses
    # the adoption picker). Writes gated to school:create
    # (Provisioner / EduZimOps).
    ("GET",    "/api/v1/ministry/national-curriculum", "authenticated"),
    ("POST",   "/api/v1/ministry/national-curriculum/", "school:create"),
    ("POST",   "/api/v1/ministry/bulk/national-curriculum", "school:create"),

    # Phase 18b — Ministry-distributed templates.
    # Reads on the school-side surface gated `school:manage` so a HoD
    # can browse the catalog. Writes on the Ministry side gated
    # `school:create` (Provisioner / EduZimOps / Ministry).
    ("GET",    "/api/v1/ministry/national-templates", "authenticated"),
    ("POST",   "/api/v1/ministry/national-templates/", "school:create"),
    ("GET",    "/api/v1/national-templates", "school:manage"),
    ("POST",   "/api/v1/national-templates/", "school:manage"),

    # Question Bank.
    ("GET",    "/api/v1/questions", "authenticated"),
    ("POST",   "/api/v1/questions", "school:manage"),
    # Teachers submit drafts; admins approve.
    ("POST",   "/api/v1/question-drafts", "question:draft"),
    ("GET",    "/api/v1/question-drafts", "school:manage"),
    ("POST",   "/api/v1/question-drafts/", "school:manage"),
    # Assessment composition + auto-grading.
    ("POST",   "/api/v1/assessments/", "school:manage"),

    # Templates.
    ("GET",    "/api/v1/homework-templates", "authenticated"),
    ("POST",   "/api/v1/homework-templates", "authenticated"),
    ("POST",   "/api/v1/homework-templates/", "school:manage"),
    ("POST",   "/api/v1/homework/", "school:manage"),
    ("GET",    "/api/v1/lesson-plan-templates", "authenticated"),
    ("POST",   "/api/v1/lesson-plan-templates", "authenticated"),
    ("POST",   "/api/v1/lesson-plan-templates/", "school:manage"),

    # Phase 12d/e/f — parent-life surfaces.
    # School events — anyone authenticated reads; admin writes.
    ("GET",  "/api/v1/school-events", "authenticated"),
    ("POST", "/api/v1/school-events", "school:manage"),
    # Performance opt-out — admin only.
    ("GET",    "/api/v1/performance-opt-out", "authenticated"),
    ("PUT",    "/api/v1/performance-opt-out", "school:manage"),
    ("DELETE", "/api/v1/performance-opt-out", "school:manage"),
    # Conference slots/bookings — read open; slot create admin/teacher;
    # booking is parent-initiated.
    ("GET",  "/api/v1/conference-slots", "authenticated"),
    ("POST", "/api/v1/conference-slots", "authenticated"),
    ("POST", "/api/v1/conference-bookings", "authenticated"),
    # Permission slips.
    ("GET",  "/api/v1/permission-slips", "authenticated"),
    ("POST", "/api/v1/permission-slips", "school:manage"),
    ("POST", "/api/v1/permission-slips/", "authenticated"),  # /{id}/responses
    # Grievances — parent submits + reads own; admin reads + resolves.
    ("GET",  "/api/v1/grievances", "authenticated"),
    ("POST", "/api/v1/grievances", "authenticated"),
    ("PUT",  "/api/v1/grievances/", "school:manage"),
    # Transport — read open; bus + ping create admin (driver app
    # later).
    ("GET",  "/api/v1/transport-buses", "authenticated"),
    ("POST", "/api/v1/transport-buses", "school:manage"),
    ("POST", "/api/v1/transport-pings", "school:manage"),
    # Meal credit.
    ("GET",  "/api/v1/meal-credit/", "authenticated"),
    ("POST", "/api/v1/meal-credit/topup", "authenticated"),
    # Donations.
    ("GET",  "/api/v1/donations", "authenticated"),
    ("POST", "/api/v1/donations", "authenticated"),
    # Newsletter.
    ("GET",  "/api/v1/newsletter", "authenticated"),
    ("POST", "/api/v1/newsletter", "school:manage"),
    # Gallery.
    ("GET",  "/api/v1/gallery", "authenticated"),
    ("POST", "/api/v1/gallery", "school:manage"),
    # Sibling discount rule.
    ("GET",  "/api/v1/sibling-discount-rule", "authenticated"),
    ("PUT",  "/api/v1/sibling-discount-rule", "school:manage"),

    # Diagnostics (gateway-local; admin only)
    ("GET", "/api/v1/diagnostics", "report:admin"),
    ("POST", "/api/v1/diagnostics", "report:admin"),
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
