# ADR 006 Addendum — Module-Level Call Graph & Migration Sequence

- **Parent ADR**: `006-consolidate-to-4-services.md`
- **Status**: Accepted (PH2-1 deliverable, 2026-05-26)
- **Tags**: architecture, migration, backend

> This addendum makes ADR 006's "consolidate from 8 to 4" concrete: which module merges into which service, which HTTP calls become in-process function calls, which DB schemas merge, and the exact PH2-2…PH2-10 sub-task sequence.
>
> Source data for this document: the Phase 2 survey performed against the live code on 2026-05-26 (see task.md §3 Phase 2 work log).

---

## Final target shape

```
        ┌──────────────────────────────────────────────────────────┐
        │                       api-gateway                         │
        │   (JWT, RBAC, tenant headers, rate-limit, circuit-break)  │
        └────────┬─────────────┬─────────────┬──────────────────────┘
                 │             │             │
        ┌────────▼──┐  ┌──────▼──────┐  ┌───▼────────┐  ┌──────────────┐
        │  identity │  │  academics  │  │  finance   │  │ communications│
        │  HTTP svc │  │  HTTP svc   │  │  HTTP svc  │  │   HTTP svc   │
        └─────┬─────┘  └──────┬──────┘  └─────┬──────┘  └──────┬───────┘
              │               │               │                 │
              ▼               ▼               ▼                 ▼
        identity_db     academics_db     finance_db        comms_db

         (events on Kafka — produced by all four)
                              │
                              ▼
                    ┌─────────────────────┐
                    │ reporting consumer  │   (no HTTP API)
                    │ (Kafka → projections│
                    │  + read-side query) │
                    └──────────┬──────────┘
                               ▼
                         reporting_db
                               │
                               ▲   (academics exposes /reports/* by
                                    reading projections — same gateway path)
```

---

## 1. `identity` service

Absorbs **`auth-service`** (whole) plus the **RBAC parts of `school-service`** are NOT relocated — the school-service RBAC routes are already in `auth-service`. The `school` entity itself stays in `academics` because that's where school operational data lives. So in practice `identity` = `auth-service` renamed, with a few clarifications.

### Final module layout

```
services/identity/
  app/
    main.py
    config.py
    database.py              # identity_db
    dependencies.py          # JWT, gateway-header trust (Phase 3 will replace this)
    events.py                # produces eduzim.identity.* (renamed from eduzim.auth.*)
    api/
      auth.py                # /auth/login, /refresh, /logout, /me
      rbac.py                # /users, /roles, /permissions
      forgot_password.py     # /forgot-password, /reset-password
      preferences.py         # /preferences
    models/user.py
    schemas/auth.py
    services/auth_service.py
    utils/security.py
    utils/seed.py
  alembic/
  tests/
```

### Database: `identity_db`

All 8 tables of `auth_db` move here unchanged:
`users`, `roles`, `permissions`, `refresh_tokens`, `token_blacklist`, `password_reset_tokens`, `login_audit`, `user_preferences`, association tables.

### Kafka topics

- `eduzim.auth.user.created.v1` → **renamed to `eduzim.identity.user.created.v1`** in Phase 2. We keep a transitional dual-publish for one minor release (the reporting consumer subscribes to both during cutover), then drop the old name.

### Cross-service calls IN: none (it's the bottom of the dependency graph).

### Cross-service calls OUT: none.

---

## 2. `academics` service

Absorbs **`school-service` + `student-service` + `attendance-service` + `assessment-service`**. By far the biggest merge — and where most cross-service HTTP calls become in-process function calls.

### Final module layout

```
services/academics/
  app/
    main.py
    config.py
    database.py              # academics_db
    dependencies.py
    events.py                # all academics topics
    api/
      schools.py             # /schools, /schools/current
      academics.py           # /academic-years, /terms
      classes.py             # /classes, /subjects, /class-teachers, /teachers/me/classes
      students.py            # /students, /parents, /enrollments, /students/{id}/parents
      attendance.py          # /attendance (sync, records, daily, trend, class-summary)
      assessments.py         # /assessments, marks
      geo.py                 # /provinces, /districts (Zimbabwe ref data)
      bulk.py                # /students/import, /students/bulk-enroll, /students/promote
      reports_query.py       # GET /reports/* (reads reporting projection)
    models/
      school.py              # School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment
      student.py             # Student, Parent, StudentParent, Enrollment
      attendance.py          # AttendanceRecord, SyncBatch, ProcessedClientEvent
      assessment.py          # Assessment, Mark
      idempotency.py         # IdempotencyKey (shared)
    schemas/
    services/
      school_service.py
      student_service.py
      attendance_service.py
      assessment_service.py
      authorization.py       # NEW: in-process replacement for /internal/teachers/authorize etc.
  alembic/                   # consolidated migrations
  tests/
```

### Database: `academics_db`

All tables from school_db + student_db + attendance_db + assessment_db merge unchanged. Total ~18 tables. The `school_id` column on every table still scopes tenancy; cross-table FKs (e.g., `Enrollment.class_id` → `classes.id`) can now be **real DB-level FK constraints** (previously index-only because of cross-service boundary).

### Kafka topics

Produces:
- `eduzim.school.*` (school.created, academic_year.created, term.created, class.created, subject.created, class_teacher.assigned) — kept under `school.*` prefix for now; renaming is non-essential.
- `eduzim.student.*` (student.created, parent.linked, enrollment.created, enrollment.updated)
- `eduzim.attendance.recorded.v1`
- `eduzim.assessment.created.v1` / `eduzim.assessment.marks.recorded.v1` (currently NOT produced by assessment-service; opportunity to add during the merge — see Phase 2g)

### The seams (intra-process replacements for current HTTP calls)

**Current cross-service HTTP that becomes in-process function call:**

| Caller (current) | Callee (current) | Route | Replacement |
|---|---|---|---|
| `attendance-service/dependencies.py` | `school-service/internal/teachers/authorize` | GET | `services/authorization.is_teacher_authorized_for_class(teacher_user_id, class_id, school_id)` |
| `assessment-service/dependencies.py` | `school-service/internal/teachers/authorize-student` | GET | `services/authorization.is_teacher_authorized_for_student(teacher_user_id, student_id, school_id)` |
| `assessment-service/dependencies.py` | `student-service/internal/parents/authorize` | GET | `services/authorization.is_parent_authorized_for_student(parent_user_id, student_id, school_id)` |
| `school-service/services/school_client.py` | `student-service /students` | GET | direct DB query via `student_service.list_students(...)` |
| `student-service/services/school_client.py` | `school-service /classes` | GET | direct DB query via `school_service.list_classes(...)` |

**Benefit**: removes 5 internal HTTP round-trips per common operation (e.g., teacher attendance sync did 1 HTTP call per `class_id` in the batch). At scale this is meaningful.

**Risk to manage**: the in-process `authorization.py` must enforce the same `X-Internal-Token`-less safety — i.e., it must require a valid actor context from the gateway, not just be callable from anywhere in the codebase. Mitigated by making it a function that takes an `ActorContext` parameter (post-Phase 3).

### `AuthorizationServiceUnavailable` — handling after consolidation

The 503-on-downstream-failure pattern we added in Phase 1 (BUG-001) becomes irrelevant for these specific calls because they're no longer over HTTP. The dependency code in attendance + assessment can be simplified — they just call `authorization.is_teacher_authorized_for_class(...)` and get a deterministic bool. The exception type stays around for any *future* cross-service authz call (e.g., academics → identity for permission expansion).

### Cross-service calls OUT

- `academics` calls `identity` for: nothing in the hot path (gateway already injects `X-User-Id` / `X-User-Role` headers — academics trusts them). For things like "fetch user details for an audit log entry" we use Kafka events (`eduzim.identity.user.created.v1`).

### Cross-service calls IN

- `finance` → `academics` for student-name / fee-structure resolution? Currently no — finance reads student data via Kafka projection? Actually, the existing code in `fees-service` does NOT call out to other services. The audit confirmed it. So finance stays decoupled.

---

## 3. `finance` service

`fees-service` renamed to `finance`. No module changes; no consolidations.

### Final module layout

```
services/finance/
  app/
    main.py
    config.py
    database.py              # finance_db (renamed from fees_db)
    dependencies.py
    events.py
    api/
      structures.py          # /fees/structures
      invoices.py            # /fees/invoices, /fees/invoices/{id}/pdf
      payments.py            # /fees/payments, /fees/payments/{id}/receipt, defaulters, initiate, webhook, status
      diagnostics.py         # /probe
    models/fees.py
    models/idempotency.py
    schemas/
    services/fees_service.py
  alembic/
  tests/
```

### Database: `finance_db`

Renamed from `fees_db`. Same 5 tables + IdempotencyKey.

### Kafka topics

`eduzim.fees.invoice.created.v1`, `eduzim.fees.payment.recorded.v1` — kept under `fees.*` prefix (renaming optional).

### Provider interface (per ADR 004 / DEC-004 revised)

`finance` is where the `PaymentProvider` interface lives (`services/finance/app/providers/payment/`). PaynowProvider is already de-facto wired; we formalise it during this merge as part of the move, **not** as new build. Phase 12b builds the ManualHandoverProvider on top.

---

## 4. `communications` service

`communication-service` renamed to `communications`. The notification-worker is folded in.

### Final module layout

```
services/communications/
  app/
    main.py
    config.py
    database.py              # communications_db (renamed from comms_db)
    dependencies.py
    events.py
    api/
      announcements.py       # /comm/announcements, /comm/feed
      outbox.py              # /comm/outbox, /comm/outbox/stats, retry
      whatsapp_webhook.py    # /comm/webhooks/whatsapp
      diagnostics.py
    models/communication.py
    models/idempotency.py
    schemas/
    services/communication_service.py
    workers/
      notification_dispatcher.py  # MOVED FROM services/notification-worker/worker.py
  alembic/
  tests/
```

### Database: `communications_db`

Renamed. Same 3 tables. Notification-worker's existing reads of `auth_db.users` for email lookup become a Kafka-event-driven projection table inside communications (so we don't introduce a new cross-DB dependency just to send a notification). Concrete plan:

- Consume `eduzim.identity.user.created.v1` and the new `eduzim.identity.user.updated.v1` (need to add an emit in identity).
- Maintain a `user_contact_projection` table inside communications_db: `(user_id, email, phone, push_token, school_id, language)`.
- Notification dispatcher reads from this projection, not from `auth_db`.

This is part of Phase 2 finishing work (PH2-6 / PH2-7).

### Kafka topics

Produces: `eduzim.comm.announcement.created.v1` (unchanged).
Consumes: `eduzim.identity.user.created.v1`, `eduzim.identity.user.updated.v1` (new).

### Provider interface (per ADR 004 / DEC-004 revised)

`NotificationProvider` interfaces (SmsProvider, EmailProvider, PushProvider, WhatsAppProvider) live here. Reference impls (`AfricasTalkingSmsProvider`, `SendGridEmailProvider`, `FcmPushProvider`, `ManualHandoverProvider`) get formalised during the merge.

---

## 5. `reporting` — async consumer (no HTTP service)

`reporting-service` is rewritten as a pure Kafka consumer process. Its HTTP endpoints move to **`academics/api/reports_query.py`**, which reads the projection DB directly.

### Final module layout

```
services/reporting/
  app/
    main.py                  # ASGI app that exposes /health only; no /api/v1 routes
    config.py
    database.py              # reporting_db (read-write for projections)
    services/
      kafka_consumer.py      # subscribes to all eduzim.* topics
      report_builder.py      # event → projection updates
      report_dropout.py      # dropout-risk projection job (cron-style)
    models/projections.py    # 5 projection tables
  alembic/
  tests/
```

### Database: `reporting_db`

Read-write for projections. The query path (in academics) only reads.

### HTTP surface moved to academics

The `reporting-service /api/v1/reports/*` endpoints become academics endpoints, served by `academics/api/reports_query.py`. The gateway route `/api/v1/reports` simply re-points to academics. This keeps the public API contract identical (clients see no change). The export endpoints (`/reports/export/*`) that currently call multiple services synchronously also move to academics — they become in-process queries because all the data they need (students, attendance, assessments, fees) is in `academics_db` and `finance_db`. For finance data, academics calls finance via its public API (this is one allowed cross-service hop because the gateway-routing model still applies — finance is a separate tenant of the gateway-headers contract).

### Removed: `/reports/consume` and `/reports/rebuild` HTTP routes

These were admin endpoints. They move to CLI tools: `services/reporting/cli/consume_once.py` and `services/reporting/cli/rebuild.py`. Operations runbook updated accordingly.

---

## 6. Gateway route remapping

The gateway's `SERVICE_ROUTES` table is the single seam in the gateway. Updated mapping:

| Public prefix | Today routes to | After consolidation |
|---|---|---|
| `/api/v1/auth` | AUTH_SERVICE_URL | IDENTITY_SERVICE_URL |
| `/api/v1/schools` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/academic-years` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/terms` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/classes` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/subjects` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/class-teachers` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/teachers` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/students` | STUDENT_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/parents` | STUDENT_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/enrollments` | STUDENT_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/attendance` | ATTENDANCE_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/assessments` | ASSESSMENT_SERVICE_URL | ACADEMICS_SERVICE_URL |
| `/api/v1/fees` | FEES_SERVICE_URL | FINANCE_SERVICE_URL |
| `/api/v1/comm` | COMMUNICATION_SERVICE_URL | COMMUNICATIONS_SERVICE_URL |
| `/api/v1/reports` | REPORTING_SERVICE_URL | ACADEMICS_SERVICE_URL (queries projections in reporting_db) |
| `/api/v1/provinces`, `/districts` | SCHOOL_SERVICE_URL | ACADEMICS_SERVICE_URL |

**Public path contracts are unchanged** — frontends keep working without modification.

The `*_SERVICE_URL` env vars rename: gateway config introduces 4 new (`IDENTITY_SERVICE_URL`, `ACADEMICS_SERVICE_URL`, `FINANCE_SERVICE_URL`, `COMMUNICATIONS_SERVICE_URL`). Old env vars kept for one release as fallback aliases so a partial rollout doesn't strand requests.

---

## 7. Schema mergers (Alembic plan)

The 8 service DBs collapse to 5 DBs (identity, academics, finance, communications, reporting). Migration approach: **physical merges done one at a time**, with verification between each step.

The safe approach:

1. **Initial phase**: spin up `academics_db` as a fresh Postgres database. Run consolidated Alembic migrations that re-create the schemas of school + student + attendance + assessment together.
2. **Data move**: a one-time data migration script copies rows from the old per-service DBs into academics_db. Run on staging first; verify row counts + sample checksums.
3. **Cutover**: stop the four old services; start the new `academics` service against academics_db; gateway flips its routing.
4. **Rollback**: keep the old DBs read-only for 30 days. If a regression appears, gateway routes can be flipped back (with the caveat that any *new writes* to academics_db are lost on rollback — we accept this risk after staging burn-in).
5. **Same pattern** for identity (auth_db → identity_db). Trivially identical; just rename + move.
6. **Finance** is just a rename (fees_db → finance_db); no data move needed if we just rename the connection string.
7. **Communications** is just a rename (comms_db → communications_db).
8. **Reporting** stays.

---

## 8. Migration sequence (the PH2-N tasks)

This is the proposed execution order. Each task should be completable in one session and end with `make test` green and a `task.md` evidence row.

| Task | Description | Touches | Risk |
|---|---|---|---|
| PH2-1 | **(this addendum)** | docs/decisions/ | low |
| PH2-2 | Rename `auth-service` → `identity`. Keep DB name (`auth_db`) for now; rename only code + service container + gateway URL var. Update tests/__init__.py. Update env var name in compose. | services/identity/, gateway routes, docker-compose | low — pure rename |
| PH2-3 | Rename `fees-service` → `finance`. Same approach as PH2-2. | services/finance/, gateway routes, docker-compose | low |
| PH2-4 | Rename `communication-service` → `communications`. Move `services/notification-worker/worker.py` into `services/communications/app/workers/notification_dispatcher.py`. Keep the worker as a separate container for now (don't try to unify the process). | services/communications/, services/notification-worker/ (deleted), docker-compose | medium — moves the worker code |
| PH2-5 | Create new `services/academics/` shell with merged module layout but EMPTY routes/models. Copy existing test scaffolding (tests/__init__.py with env defaults). Don't wire to gateway yet. | services/academics/ (new) | low |
| PH2-6 | Move `school-service` code into `services/academics/`: routes → `api/schools.py` + `api/classes.py` + `api/geo.py`, models, services, tests. Update imports. Migrate school_db schema into the new academics_db (Alembic). Verify tests pass under academics/. Keep school-service container running. | services/academics/, services/school-service/, alembic | high — biggest merge step |
| PH2-7 | Move `student-service` into `services/academics/` (api/students.py + api/bulk.py). Replace existing HTTP call to school-service `/classes` with in-process call (now possible because both live in academics). Migrate student_db schema. Tests pass. | services/academics/, services/student-service/ | high |
| PH2-8 | Move `attendance-service` into `services/academics/` (api/attendance.py + models/attendance.py + services/attendance_service.py). Replace `/internal/teachers/authorize` HTTP call with `services/authorization.is_teacher_authorized_for_class()` in-process. Migrate attendance_db schema. Tests pass. | services/academics/, services/attendance-service/ | high |
| PH2-9 | Move `assessment-service` into `services/academics/` (api/assessments.py + models/assessment.py + services/assessment_service.py). Replace both internal HTTP authz calls (teachers/authorize-student, parents/authorize) with in-process functions. Add the missing Kafka emit `eduzim.assessment.created.v1` + `eduzim.assessment.marks.recorded.v1`. Migrate assessment_db schema. Tests pass. | services/academics/, services/assessment-service/ | high |
| PH2-10 | Wire gateway routes: every prefix that pointed at school/student/attendance/assessment now points at ACADEMICS_SERVICE_URL. Keep the old `*_SERVICE_URL` env vars as aliases. Verify TestGatewayAuth, TestGatewayProxy, TestGatewayRouting tests pass. | services/api-gateway/, docker-compose | medium |
| PH2-11 | Convert `reporting-service` into an HTTP-less consumer: drop `/api/v1/reports/*` routes from it, move them into `services/academics/app/api/reports_query.py` (reading reporting_db directly). Verify dashboards still resolve through gateway. CLI tools added for rebuild/consume. | services/reporting/, services/academics/, services/api-gateway/ | medium |
| PH2-12 | Delete the four merged service directories (`auth-service`/`school-service`/`student-service`/`attendance-service`/`assessment-service`/`fees-service`/`communication-service`/`notification-worker`) after a 1-week burn-in. Update docker-compose to remove their containers. Mark Phase 2 done in task.md. | Filesystem cleanup | low — only after burn-in |

**Total**: 12 sub-tasks. Three of them (PH2-6, 7, 8, 9) are high-risk and individually substantial. PH2-2/3/4 are quick wins that should go first to build muscle memory.

**Suggested order in practice**:
1. PH2-2 (rename auth → identity) — small, builds confidence
2. PH2-3 (rename fees → finance) — small
3. PH2-4 (rename communication, fold worker) — medium
4. PH2-5 (academics shell) — small
5. PH2-6, 7, 8, 9 (the merges) — one per session
6. PH2-10 (gateway switch) — one session, all-or-nothing
7. PH2-11 (reporting → consumer) — one session
8. PH2-12 (cleanup) — after burn-in

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Schema merge loses data | M | High | Staging burn-in; row-count + checksum verification; old DBs kept read-only for 30 days. |
| Gateway routing typo strands traffic | L | High | Add 2 e2e tests per route family that exercise the gateway → service path before+after. Cutover behind a one-line env switch in compose. |
| Cross-service tests break en masse | H | Medium | Each PH2-N is its own session; we never leave the suite broken. Tests for the just-moved code run before the next merge. |
| `authorization.py` accidentally callable by wrong actor | M | High | The function takes `ActorContext` parameter; gateway-injected headers are the only legal source (enforced in academics dependencies.py). Add explicit test. |
| Reporting consumer falls behind during cutover | L | Medium | Pause writes briefly; reporting consumer catches up; resume. Acceptable for off-hours migration. |
| FK constraints we *now can* add (intra-academics) break data | M | Medium | Add FKs in a *separate* Alembic step after the merge, with explicit data validation first. Not part of the initial merge. |
| Kafka topic rename breaks reporting | L | High | Identity service dual-publishes old + new topic name for one release; reporting subscribes to both; drop old after cutover. |
| `notification-worker` becomes invisible after fold-in | L | Low | Keep worker as its own container initially; move it to in-process Celery / background task only after the rest of Phase 2 lands. |

---

## 10. Rollback

Per task: if a PH2-N regresses, `git revert` of that task's commits + redeploy reverts the gateway routing and brings the old service container back. The old service DBs are kept read-only for 30 days, so data is recoverable.

Hard rollback for the whole consolidation (all four merges in one go) is more painful and we don't attempt it. The reason we sequence by service is precisely to keep each rollback small.

---

## 11. What this addendum does NOT decide

- Whether to switch Postgres to per-tenant DBs (`shared` / `dedicated` / `district`) — that's ADR 009 / Phase 8.
- Whether to remove the JWT decode from individual services — that's BUG-007 / Phase 3.
- Whether to introduce gRPC or any non-REST inter-service transport — out of scope; we stay on REST + Kafka.
- Whether to colocate two services in one process (e.g., academics + finance) — explicitly rejected. They stay separate processes with separate DBs.

---

## References

- ADR 006 (parent): `006-consolidate-to-4-services.md`
- ADR 004 (provider interfaces): `004-integration-only-providers.md`
- ADR 007 (privacy review per phase): `007-privacy-by-design.md`
- Plan: `/Users/phani.m/.claude/plans/do-an-entire-run-goofy-parasol.md` Phase 2
- Backlog: `task.md` §3 Phase 2 sub-tasks PH2-2 → PH2-12
