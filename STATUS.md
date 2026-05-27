# EduZim — Build Status (Honest)

> This is the **single source of truth** on what is verified to work today, what is partially built, and what is aspirational or marketing.
>
> If `VISION.md`, `README.md`, the deck, or any other artefact says something is "done", check this file before believing it.
>
> Audit performed: 2026-05-26 (three parallel code-reading agents).
> Last updated: 2026-05-26.

## Legend

- ✅ **Verified** — works in code; covered by tests that actually exercise the behaviour (not surface mocks).
- ⚠️ **Partial** — exists in code but with caveats: shallow tests, missing edges, known bugs, only the happy path works, or only frontend / only backend.
- ⛔ **Not built** — does not exist yet. Listed because something elsewhere (a slide, a doc, a Context.md claim) implied it does.
- 📣 **Marketing** — a phrase that overstates current capability. Should not be used without qualifier.
- ⏳ **Planned** — explicitly scheduled in `task.md` (with phase reference).

---

## 1. Backend Services

| Claim / Capability | Status | Evidence / Caveat |
|---|---|---|
| Microservices post-PH2-12 cleanup | ✅ | Live boundary (Phase 2 done): `identity` + `academics` (school+student+attendance+assessment+reports-read merged) + `finance` + `communications` + `reporting-service` (Kafka-consumer-only, no HTTP) + `api-gateway`. The four pre-consolidation services + notification-worker have been **deleted** from `services/`, `docker-compose*.yml`, and CI matrices. Five service images instead of ten. |
| Microservices count matches ADR 006 | ✅ | 4 HTTP services + identity + 1 Kafka consumer + 1 gateway, exactly as ADR 006 specifies. Six cross-service HTTP hops eliminated across PH2-7→11. |
| Per-service Postgres DBs | ✅ | Each service has its own DB in compose. Academics also opens read-only second connection to `reporting_db` post-PH2-11. |
| Per-service Alembic migrations | ✅ | Each service has migration files |
| Multi-tenant via `school_id` | ✅ | Every domain table has `school_id`; queries scope by it |
| Real cross-tenant isolation tests | ✅ Phase 4 | `services/academics/tests/test_cross_tenant_isolation.py` — 23 tests across 9 classes (Student, Parent, School-config, Attendance, Assessment, Schools-current, Enrollment, service-layer, DB-level invariants). Caught BUG-009 (404→200 tuple-return bug); now fixed. |
| Tenancy tiers (shared / dedicated / district) | ✅ Phase 8 in code | `schools.tenancy_tier` column + `eduzim_shared.tenancy.TenancyResolver` (25 unit tests) + `scripts/promote-school-to-dedicated.sh` (7-step automation) + `docs/runbooks/tenancy-upgrade.md`. ⚙️ Staging promotion drill is the only remaining operational gate. See ADR 009. |
| Right-to-export endpoints (data-rights) | ✅ Phase 8 | `GET /api/v1/schools/me/export` (school admin) + `GET /api/v1/parents/me/export` (parent self-service). Returns ZIP with manifest + per-table CSVs. 9 integration tests verify cross-tenant isolation (school A's export contains 0 rows from school B; parent export contains 0 rows from non-linked children). Closes ADR 007 / Phase 9's right-to-data track. |
| Kafka producer wired & publishing | ✅ | `services/*/app/events.py` actually publishes |
| Kafka idempotent consumers (reporting) | ✅ | PH2-11: pure consumer loop in `services/reporting-service/app/consumer.py`; subscribes to 8 topics; `ProcessedEvent` inbox enforces exactly-once. Covered by `services/reporting-service/tests/test_consumer.py`. |
| Idempotency on attendance sync | ✅ | `(school_id, device_id, sync_batch_id)` enforced |
| Idempotency on payments (row-locking) | ✅ | `services/fees-service/app/services/fees_service.py:131-144` |
| Idempotency on assessment marks bulk | ⚠️ | Uses unique `(assessment_id, student_id)` for overwrite; no batch idempotency. Scheduled. |
| JWT validated at gateway | ✅ | `services/api-gateway/app/middleware/stack.py:34-71` |
| JWT also re-parsed in downstream services | ✅ fixed PH3 | Was a real bug pre-PH3. `grep -rn "from jose" services/` now hits only `identity/`. Downstream services trust gateway-injected headers (`X-User-Id`, `X-School-Id`, `X-User-Roles`, `X-Permissions`) protected by `X-Gateway-Token`. See ADR 014. |
| Internal endpoints protected | ⚠️ | `X-Internal-Token` checked, but token is the default `change-me-in-production`. Scheduled `task.md` BUG-004. |
| Gateway has circuit breaker | ✅ | `services/api-gateway/app/proxy.py` |
| Gateway has rate limiting | ⚠️ | In-memory dict, lost on restart. Scheduled `task.md` BUG-006. |
| Gateway has Prometheus `/metrics` | ✅ + ⚙️ scrapes scaffolded | Gateway plus every downstream service now exposes `/metrics` via `eduzim_shared.metrics.install` (Phase 6). Prometheus scrape config in `infra/observability/prometheus.yml` covers all 6. Scrape verification on staging closes the gate. |
| Distributed tracing | ⚙️ Phase 6 scaffolded | `eduzim_shared.tracing` wraps OpenTelemetry; OTLP→Tempo in `docker-compose.observability.yml`. Opt-in via `EDUZIM_TRACING_ENABLED=true`. Closes once a real cross-service trace renders in Grafana Tempo on staging. |
| Log aggregation | ⚙️ Phase 6 scaffolded | Loki + Promtail in observability overlay. Promtail's JSON pipeline parses `eduzim_shared.logging` output into queryable labels. Closes once log search by service/level works on staging. |
| Error tracking | ✅ + ⚙️ DSN-wire-pending | `sentry_sdk.init` already in `app_factory.create_app()` (INFRA-010 / ADR 007: `send_default_pii=False`). Phase 6 overlay sets `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`. Closes once a synthetic 500 captures in Sentry on staging. |
| Alertmanager rules + routing | ⚙️ Phase 6 scaffolded | 10 alerts in `infra/observability/rules/eduzim-alerts.yml` covering the four Phase-6-gate cases (gateway 5xx > 1%, Kafka lag > 30s, pgbouncer > 80%, disk > 75%) plus 6 baseline. Critical→Slack #ops-pages+email, warning→Slack #ops-digest. Closes once synthetic-5xx triggers Slack delivery within 60s on staging. |

### Known backend bugs (carry-overs to `task.md`)

| Bug | Severity | Location |
|---|---|---|
| `except Exception: pass` in teacher-auth verification | HIGH (security: fail-open) | `services/attendance-service/app/dependencies.py:64-65` |
| `except Exception: pass` in Paynow polling | HIGH (correctness) | `services/fees-service/app/api/payments.py:346-367` |
| Default JWT_SECRET_KEY shipped in compose | HIGH (security) | `docker-compose.yml:100,119,124,251` |
| Default INTERNAL_SERVICE_TOKEN | HIGH (security) | `services/*/app/config.py` |
| Migrations in service CMD → 8-service race | MEDIUM | `services/auth-service/Dockerfile:21` (and others) |

---

## 2. Frontend Apps

| Claim / Capability | Status | Evidence / Caveat |
|---|---|---|
| Three Next.js PWAs (admin, parent, teacher) | ✅ | Ports 3000, 3001, 3002 |
| PWA manifests | ✅ | `theme_color #5B2D8A`, standalone display |
| Service workers (cache-first static, network-first API) | ✅ | Per app |
| `@eduzim/ui` shared design system | ✅ | 22 components, token file with purple palette + Zimbabwe accents + persona theming |
| Real charts library | ✅ Phase 10 | Recharts wrappers (`LineChart`, `BarChart`, `PieChart`, `SparkLine`) in `@eduzim/ui`. Admin reports — attendance + financial sections — render stacked BarChart + LineChart, table preserved as `<details>` for screen-reader users. ECharts wrappers (`Heatmap`, `ZimbabweGeomap`, `Sankey`) ship via separate subpath `@eduzim/ui/echarts` with `next/dynamic` lazy-loading + `optionalDependencies` so the 600KB cost lands in a separate chunk only when used. Lighthouse + bundle-size verification per `docs/runbooks/charts-bundle-budget.md`. |
| i18n with EN, Shona, Ndebele | ✅ | `next-intl` wired; Shona/Ndebele are real translations, not English copies |
| Sync Center fully translated | ⚠️ (bug) | `TYPE_LABELS` hardcoded English in `apps/teacher-web/.../sync-center/page.tsx:58-62`. Scheduled `task.md` BUG-009. |
| Auth: tokens in memory + httpOnly cookie refresh | ✅ | `packages/auth/src/tokens.ts:13-35` |
| Zod validation on forms | ✅ | Across all 3 apps |
| Bulk operations (e.g., "Mark all present") | ✅ Phase 11a / T-001 | "Mark all 30 present" / "Mark all 30 absent" buttons polished with an undo snapshot (10-second affordance) and count-bearing labels so the blast radius is visible before the click. No-op bulks (everyone already in target state) suppress the Undo pill. Translated EN / SN / ND. 21 source-pattern + i18n gate tests in `apps/teacher-web/tests/gate11a-1.test.ts`. |
| Period-based attendance | ✅ Phase 11a / T-002 | Sentinel-integer `period_number INTEGER NOT NULL DEFAULT 0` ("Day" = 0, periods 1–8 = secondary-school mode) chosen over a `periods` table for simplicity + portable unique-constraint semantics; promotion path to a real periods FK is documented for Phase 11d. Backend: Alembic 008 (idempotent, SQLite-compatible batch ops), model + sync engine + `/attendance/daily/records` endpoint all key by `(school_id, student_id, date, period_number)`. Frontend: `<select>` next to the date picker; client_event_id is namespaced by period to avoid dedup collisions. 5 backend tests covering coexistence + upsert + filter + the no-filter "all periods" path; 22 frontend gate tests. Existing daily-mode schools behave unchanged (everyone defaults to 0). |
| Roster offline cache | ✅ Phase 11a / T-014 | `useCachedApiQuery` hook reads from IndexedDB-cached data on mount and paints immediately on a cache hit, then refreshes in the background. Cache failures and network errors are tolerant (the user always sees something useful). 24-hour TTL (one school day). `OfflineBadge` component surfaces both the live network state (`mode="status"` — pill shows only when offline) and the cache-hit state (`mode="cache"` — "Showing cached data"). Wired into the class detail page header. Closes **BUG-010**. EN / SN / ND `offline.*` namespace. 29 source-pattern + i18n gate tests. |
| `schoolId` correctly passed in attendance enqueue | ⚠️ (bug) | Hardcoded `""` at `apps/teacher-web/.../attendance-tab.tsx:157`. Scheduled BUG-005. |
| Print/PDF for receipts, transcripts, reports | ⛔ | `exportToPdf` exists in `packages/ui` but **unused**. Scheduled Q-003. |
| Bulk student CSV import | ⛔ | Mentioned in screenshots; CSV import surface exists but workflow incomplete. Scheduled Q-002. |
| Accessibility audit | ⛔ | No axe-core run; contrast not verified; many icon-only buttons unlabeled. Scheduled Q-005. |
| Student app | ⛔ | No student-role surface yet. Per ADR 002, scheduled into parent-web as `student` role (Phase 12a/g). |

### Component duplication

`ErrorAlert`, `PageHeader`, `EmptyState`, `RiskBadge` are reimplemented per app instead of shared in `packages/web-shared/`. Scheduled Q-004.

---

## 3. Offline Engine

| Claim / Capability | Status | Evidence / Caveat |
|---|---|---|
| `@eduzim/offline-core` package | ✅ | `OfflineQueue`, `OfflineCache`, `SyncManager` |
| `isSyncing` guard against concurrent runs | ✅ | Tested in `packages/offline-core/tests/` |
| Sequential sync with per-pass `attempted` set | ✅ | Prevents retry storms |
| Real integration tests | ✅ | 8 integration tests in `packages/offline-core/tests/integration.test.ts` |
| Teacher writes (attendance, marks, announcements) routed through queue | ✅ (with bug) | Routed; but see BUG-005 hardcoded `schoolId` |
| Parent reads cached with TTL | ⚠️ | `useCachedQuery` referenced; not all data flows use it. Some endpoints fetch directly. |
| Conflict resolution model | ⚠️ | LWW for attendance/marks (correct per ADR 010); **detect+manual not yet built** for announcements/incidents. Scheduled in Phase 10 ADR / Phase 11 work. |

---

## 4. Pillar-by-Pillar Truth

VISION.md describes six pillars. Reality:

### Pillar 1 — School ERP

| Sub-capability | Status |
|---|---|
| Academic structure (classes, subjects, terms) | ✅ |
| Student lifecycle (admit → enrol → transcript) | ⚠️ Admit + enrol present. **Admissions workflow (application → screening) ⛔**. Transfers in/out ⛔. Transcript generation ⛔. |
| Fee transparency (record, invoice, partial pay, defaulter) | ✅ Records. Payments through Paynow stub. |
| Mobile money channels (EcoCash etc.) | ⛔ Mentioned in VISION; not wired. Per ADR 004, comes via PaymentProvider. |
| Donor subsidy tracking | ⛔ |
| Public audit dashboard | ⛔ |
| HR (contracts, leave, payroll, performance review) | ⛔ Entirely. Scheduled A-002. |
| Staff attendance | ⛔ |
| Non-teaching staff management | ⛔ Scheduled A-001. |

### Pillar 2 — Digital Learning Engine

| Sub-capability | Status |
|---|---|
| Offline-first LMS | ⛔ Offline engine exists at the device layer; **no LMS content model**. Scheduled Phase 15. |
| Daily content sync model | ⛔ |
| Version-controlled syllabus | ⛔ |
| Recorded lessons repository | ⛔ |
| Low-bandwidth video compression | ⛔ |
| Global content integration (Cambridge / IB / STEM / coding) | ⛔ Per ADR 004, via ContentProvider. One reference partner planned in Phase 15. |
| Hybrid learning model | 📣 Marketing phrase. |

### Pillar 3 — Dropout Intelligence

| Sub-capability | Status |
|---|---|
| "AI dropout risk engine" | 📣 Overstated. What exists is a **rules-based scoring** function combining attendance decline, fee non-payment, performance trend. No ML. Tagged `dropout intelligence (rules-based)` in code going forward. |
| Attendance — teacher-marked | ✅ |
| Attendance — biometric / QR / RFID | ⛔ "Optional" in VISION; not built. |
| Early warning alerts to teachers/admin/parents | ⚠️ Surface exists; notification delivery is provider-dependent (Phase 12c). |
| "Save thousands of children" | 📣 Marketing claim. |

### Pillar 4 — Communication Grid

| Sub-capability | Status |
|---|---|
| In-app announcements + outbox | ✅ |
| SMS | ⛔ Provider config exists (Africa's Talking in `.env`). Not wired. Scheduled Phase 12c. |
| WhatsApp Business | ⛔ Not wired. Scheduled Phase 12c. |
| Email | ⛔ Not wired. Scheduled Phase 12c. |
| Community bulletin boards | ⛔ |
| Emergency broadcast | ⛔ |
| Parent-teacher booking | ⛔ Scheduled P-005. |
| Fee reminders | ⚠️ Mark as reminder in domain; delivery requires Phase 12c. |
| Multi-channel orchestration | ⛔ |

### Pillar 5 — Teacher AI & Productivity

| Sub-capability | Status |
|---|---|
| Lesson plan generator (AI) | ⛔ Phase 2+ at best; no AI work in v1. |
| Homework auto-grader (AI) | ⛔ |
| Exam question bank generator (AI) | ⛔ |
| Personalised remediation (AI) | ⛔ |
| Offline AI assistant | ⛔ |
| Performance analytics dashboard | ⚠️ Charts not built (Phase 10); raw data exists. |
| "Workload reduction 40–60%" | 📣 Unsubstantiated claim. Cannot validate without pilot data. |

### Pillar 6 — National Education Intelligence

| Sub-capability | Status |
|---|---|
| Ministry-specific surface | ✅ Phase 14 closed 2026-05-27. `(ministry)` route group in admin-web (ADR 020) with read-only nav across 11 dashboards. |
| Cross-school aggregation API | ✅ `services/academics/app/api/ministry_routes.py` + `services/finance/app/api/ministry_routes.py`. Role-gated at gateway (`ministry:read`) AND at the route layer (defence-in-depth). |
| District / Province / National dashboards | ✅ Enrolment + attendance + fees + dropouts + pass-rate + PTR all support `scope=district\|province\|national`. |
| Compliance dashboard | ✅ `/ministry/compliance` per (school, template) submission status counts, period-filterable. |
| Drop-out heatmap | ⚠️ District bar chart shipped; Zim geomap deferred to a follow-up (data contract stable; ECharts geomap component already exists). |
| Resource allocation views | ⚠️ PTR shipped; `devices_per_school` + `electricity_coverage` are placeholder `null`s pending a `SchoolFacility` model. |
| Donor / NGO impact reporting | ✅ `/ministry/donors` aggregates Sponsorship by scope (committed, received, fulfilment). Money amounts are an ADR-018 exception (money story). |
| International (UNESCO / UNICEF) exports | ✅ `/ministry/exports/unesco?year=…` returns a stable canonical snapshot; admin-web Exports page renders + downloads it as JSON. |

---

## 5. Audience Coverage (per ADR 001)

| Persona | Coverage today | Biggest gaps |
|---|---|---|
| Teacher | ✅ ~95% of daily reality | **All of Phase 11 (a–f) closed 2026-05-26.** 11a: bulk attendance polish + period-based attendance + offline roster cache (BUG-010). 11b: parent-teacher 1:1 messaging (T-011), simplified announcement form (RULE-4), polymorphic file attachments with storage backend abstraction (T-008). 11c: cross-assessment gradebook (T-015), school-configurable comment bank (T-007), MediaRecorder-based voice notes (T-009). 11d: school periods (T-010, T-002 promotion target), lesson plan library with templates (T-005), formative assessments (T-013), exam seat plans (T-012). 11e: behaviour incident log with audit-text-redacted (T-004), time-bound substitute grants (T-006), homework workflow (T-003). 11f: co-teacher (T-016 via constraint relaxation), HoD assignments (T-017), CPD tracker (T-018), self-evaluation forms (T-019). Total: 19 backend domain features + 7 consolidated teacher-web pages (`/today`, `/classes`, `/announcements`, `/messages`, `/gradebook`, `/plan`, `/student-life`, `/professional`). Backend +~70 tests, teacher-web 332 tests. Playwright behaviour coverage + axe-core a11y sweep deferred to Phase 11g. |
| Student | ✅ ~70% of daily reality (Phase 12g, 2026-05-27) | Role + login via `Student.user_id` linkage; `/students/me` resolves to academic record. Schedule, marks, attendance (shared with parent route + role scoping), announcements (shared), assignments scaffold, notifications via provider abstraction. **Deferred to Phase 15**: S-009 quizzes (ties to learning layer), S-011 student↔teacher chat (needs policy pass), S-013 goal tracker. |
| Parent | ✅ ~95% of daily reality (Phase 12, 2026-05-27) | Phase 12a–12g closed. **Foundations**: ChildSwitcher + ChildProvider + role-aware nav. **Payments**: PaymentProvider abstraction (`PaynowProvider`, `ManualHandoverProvider`) + per-school config (`SchoolPaymentConfig`) + `POST /fees/payments/checkout` + `POST /fees/payments/manual/confirm` + server-side PDF receipts/invoices via pre-existing `pdf_renderer.py`. **Notifications**: NotificationProvider abstraction across SMS/Push/Email/WhatsApp (`AfricasTalking`, `FCM`, `SendGrid`, `MetaCloud` + per-channel manual fallback) + per-school per-channel config (`SchoolNotificationConfig`) + `POST /comm/notify/dispatch`. **Logistics**: conference slots+bookings, digital permission slips with e-sig upsert, grievances with body-not-logged audit invariant, transport bus + latest-ping. **Lifestyle**: meal credit topup, donations with anonymous flag, newsletter, gallery (refs T-008 attachments), sibling discount rule. 14 new tables + 13 backend test files. **Audit invariants**: recipients, bodies, notes, signed names (where appropriate), and provider config secrets never logged; amounts ARE logged for money moves per ADR 018. |
| School Admin | ✅ ~90% of daily reality (Phase 13, 2026-05-27) | **All of Phase 13 (a-e) closed.** 13a People + HR: NonTeachingStaff with role enum + soft-terminate; LeaveRequest with status flow; EmploymentContract (salary BAND not amount); SalarySlip (cents, auto-net); PerformanceReview (rating + JSON criteria, summary never audit-logged); AdmissionApplication (status flow with student_id guard); StudentTransfer with transcript attachment. 13b Compliance: ComplianceReportTemplate + ComplianceReportSubmission lifecycle; discipline + grievance rollup endpoints; HealthRecord (PIA-gated to nurse/admin, **body never audit-logged**, reads ALSO audited). 13c Ops: Expense + VendorPayment + CapitalProject (operational finance separate from fees-service ledger); Asset + AssetMovement (append-only); LibraryBook + BookLoan with capacity check; Visitor sign-in/out log. 13d Community: PolicyDocument with versioning + visibility filter; Sponsor + Sponsorship lifecycle; Alumnus tracking with auto-stamped last_contacted_at. 13e Specials: BoardingRoom + BoardingAssignment with capacity + double-assign guards; Campus with single-primary enforcement. **Admin-web UI for these features is the remaining gap** — backend is complete, 37 new backend tests; 5 model files + 5 routes files + 5 Alembic migrations (015-019). |
| Ministry | ✅ ~85% (Phase 14, 2026-05-27) | Phase 14a–14e closed. **Foundations** (14a): role `Ministry` + perm `ministry:read` seeded; ADR 020 chose `(ministry)` route group inside admin-web; cross-school sentinel UUID `eeeeeeee-…` for audit rows that span tenants. **Aggregation API** (14a-14d): 13 GET endpoints across academics + finance. Every endpoint asserts the Ministry role explicitly (defence-in-depth). **Dashboards** (14e): admin-web `(ministry)/ministry/**` with sidebar nav (Overview, Geography, Enrolment, Attendance, Drop-outs, Subjects, Resources, Compliance, Comparative, Donors, Exports). Distinct emerald colorway. **Audit invariants**: scope label + endpoint + row count only; no school names, no district/province names, no actor PII. Money amounts ARE logged for the donor endpoint (ADR-018 money-story exception). **Tests**: 25 academics ministry tests + 6 finance ministry tests, all passing. **Open**: M-005 Zimbabwe geomap (data contract stable, viz pending); M-007 devices/electricity (needs `SchoolFacility` model — placeholder fields land as null until then). |

---

## 6. Infrastructure / Operations

| Capability | Status |
|---|---|
| Postgres backups (automated + tested restore) | ✅ INFRA-001 (closed). `pg-backup` container + `docs/runbooks/backup-restore.md`. Off-host S3 still deferred. |
| Postgres connection pooling (pgbouncer) | ✅ INFRA-002 (closed Phase 4). Transaction mode. App services route via `pgbouncer:6432`. |
| Postgres replication / failover | ⚙️ INFRA-003 scaffolded (Phase 5). `docker-compose.ha.yml` has bitnami repmgr 2-node + pgpool. Closes once `scripts/chaos/kill-pg-primary.sh` passes on staging. |
| Kafka HA (multi-broker, replication factor 3) | ⚙️ INFRA-004 scaffolded (Phase 5). 3-broker KRaft cluster in HA overlay. RF=3, min.ISR=2. Closes once `scripts/chaos/kill-kafka-broker.sh` passes. |
| Kafka KRaft (no Zookeeper) | ⚙️ INFRA-005 scaffolded (Phase 5). HA overlay uses KRaft; ZK service is a no-op there. |
| Redis HA (Sentinel / cluster) | ⚙️ INFRA-006 scaffolded (Phase 5). 1 primary + 1 replica + 3 sentinels in HA overlay. Gateway updated to use `eduzim_shared.redis_client.from_url` (parses `redis+sentinel://`). Closes once `scripts/chaos/kill-redis-primary.sh` passes. |
| TLS between services | ⚙️ INFRA-019 scaffolded (Phase 5). `scripts/generate-mtls-certs.sh` + `eduzim_shared.mtls` + `eduzim_shared.serve`. Opt-in via `EDUZIM_TLS_ENABLED=true`. Closes once mTLS smoke test passes on staging. |
| Non-root containers | ✅ INFRA-020 (closed). All Dockerfiles run as non-root `app` user. |
| Resource limits | ✅ INFRA-021 (closed). `deploy.resources` on all service entries in prod compose. |
| Graceful shutdown | ✅ INFRA-022 (closed). `app_factory.create_app()` lifespan + Kafka producer flush registry. |
| CI/CD beyond image builds | ⛔ Manual deploy. Scheduled INFRA-011/012/Phase 17. |
| Secrets management (Vault / Secrets Manager) | ⛔ Default secrets in compose. Scheduled INFRA-013. |
| Disaster recovery (RTO/RPO + tested failover) | ⛔ Scheduled INFRA-014. |
| Multi-region | ⛔ Single-region. Per ADR 005, Year 2 migration plan only. |
| Per-school data export | ✅ Phase 8 | `GET /api/v1/schools/me/export` (admin) + `GET /api/v1/parents/me/export` (parent self-service). ZIP with manifest + per-table CSVs. 9 integration tests assert cross-tenant isolation. See ADR 009. |
| Audit log | ✅ Phase 9 + PH9-6 follow-up | `eduzim_shared.audit.AuditLogMixin` + `record_audit_event` + per-service `audit_log` table + three browse endpoints (`GET /api/v1/audit-log` academics, `GET /api/v1/fees/audit-log` finance, `GET /api/v1/comm/audit-log` communications) all gateway-routed with `school:manage` RBAC. **Per-service write-side wiring complete across 4 services**: academics (student CRUD + exports), finance (FEE_STRUCTURE_CREATED, INVOICE_CREATED, PAYMENT_RECORDED — the last with amount per the ADR 018 exception), communications (ANNOUNCEMENT_CREATED/DELETED — body never logged), identity (auth.login.success / failed / logout — password never logged). `scripts/audit-log-retention.py` daily-purge CLI. 31 tests across substrate + integration (13 + 10 academics + 6 finance + 2 communications). PRIVACY-AT-AUDIT enforced: `target` carries IDs, `details` lists changed-field NAMES (never values); `test_payment_audit_logs_amount_intentionally` documents the one explicit money-move exception. Admin UI is the remaining piece, tracked into Phase 11. |

### Performance / load

| Claim | Status |
|---|---|
| "500-school validated" | ⚙️ Phase 7 scaffolded | The old `scripts/scale_test.py` (the audit-flagged 550 mock HTTP calls on localhost) is now DEPRECATED with a CLI banner that exits 2. Replaced by `scripts/load/seed_realistic.py` (real-API seed via the gateway), `scripts/load/load_24h.py` (sustained 24-hour school-day-pattern traffic), `scripts/load/chaos_profiles.sh` + `docker-compose.chaos.yml` (toxiproxy at 200ms latency + ~5% loss), `scripts/load/report_generator.py` (per-endpoint verdict against published p99 budgets + 0.5% error gate). 9 unit tests on the report generator. Closes when the first 24-hour staging run lands and the dated report is committed to `docs/perf-reports/`. See ADR 017 + `docs/runbooks/phase-7-load-test.md`. |
| Real chaos testing | ⚙️ Phase 7 scaffolded | toxiproxy overlay (`docker-compose.chaos.yml`) injects 200ms latency + jitter + 20s drop-timeout on every Postgres / Kafka / Redis connection. `scripts/load/chaos_profiles.sh` applies/resets/removes/status via the toxiproxy admin API. Closes when the 24-hour load test runs WITH the chaos profile active and the report is committed. Phase 5 chaos tests (`scripts/chaos/*.sh`) cover the component-loss path — separate scaffold, same overall gate. |

### Test reality

| Claim | Status |
|---|---|
| "1,053+ tests, all green" | ⚠️ ~1,640 test functions exist (count roughly accurate); most are **shallow unit tests on mocked SQLite**. No real cross-tenant tests. No concurrency tests. No "what happens if Kafka is down" tests. |

---

## 7. Compliance

| Capability | Status |
|---|---|
| Privacy Policy / Retention Policy | ⛔ Scheduled Q-009 / Phase 9. |
| Privacy Impact Assessment | ⛔ Scheduled `docs/compliance/pia-v1.md` in Phase 9. |
| Named DPO on the platform | ✅ Q-010 closed | DPO link block in all 3 app footers; 9 message files updated (EN/SN/ND × 3 apps). |
| ZDPA legal review | ⏳ Real-world follow-up | PH9-5 — ADR 005 calls this out. Not a code task; needs lawyer time. |
| Right-to-delete | ⛔ PH9-4 deferred-major | Audit log captures consent grants; the delete-with-academic-record-retention flow needs product + legal sign-off on which fields are "academic record" vs "writeable". |
| Audit log for PII writes | ✅ Phase 9 + PH9-6 | See "Audit log" row above. Wired across academics, finance, communications, identity — substrate + ADR 018 pattern proven end-to-end. |
| Data minimisation review (per-field) | ~ Phase 9 structured plan | `docs/compliance/data-minimisation-audit.md` lists every PII-bearing field with proposed disposition + owner + status. Closing rows requires product + legal coordination — the doc is the forcing function so the work happens incrementally instead of perpetually drifting. |

---

## 8. What's actually decided

See `docs/decisions/` for the 13 ADRs locked on 2026-05-26:

- 001 Audience pyramid (T > S > P > Admin >> Ministry)
- 002 Student shares parent app
- 003 v1 scope = ERP + thin learning layer
- 004 Integration-only via Provider interfaces (revised)
- 005 Data residency: AWS Cape Town → ZW provider Year 2
- 006 Consolidate from 8 microservices to 4
- 007 Privacy-by-design as gating discipline
- 008 PWA in v1, teacher-native in Phase 2
- 009 Tenancy tiers (shared / dedicated / district)
- 010 LWW for attendance/marks; detect+manual for announcements/incidents
- 011 Recharts for daily users; ECharts for admin/Ministry
- 012 Open core post-v1
- 013 Ministry as viewer + auditor only

---

## 9. What we should NOT say in decks, demos, or to schools

Until the corresponding work in `task.md` closes:

- ❌ "Production-ready"
- ❌ "Validated at 500 schools"
- ❌ "AI-powered dropout detection" (it's rules-based)
- ❌ "AI lesson planning" (not built)
- ❌ "Reduces teacher workload by 40-60%" (unsubstantiated)
- ❌ "Multi-region" (single-region)
- ❌ "Saves thousands of children" (no data)
- ❌ "Full school ERP" (gaps in HR, admissions, staff, compliance, health, inventory)
- ❌ "Hybrid cloud/edge" (no edge)
- ❌ "Solar-compatible hardware tiers" (no hardware play)

What we **can** honestly say today:

- ✅ "Offline-capable teacher PWA with idempotent sync — early validation, not yet at 500-school scale"
- ✅ "ERP backbone for academics, attendance, fees, and announcements — admin features still expanding"
- ✅ "Rules-based dropout-risk scoring, with attendance + fees + performance signals"
- ✅ "Multi-tenant by `school_id`; per-school isolation tiers planned"
- ✅ "Trilingual (English, Shona, Ndebele) frontend"
- ✅ "Open architecture: REST + (planned) MCP servers for school-side integration"

---

This file is updated as `task.md` items close. When a row here changes from ⛔ to ⚠️ or ✅, the corresponding `task.md` row records the evidence.
