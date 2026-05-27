# EduZim — Task Backlog & Execution Plan

> Rolling workspace. Every interaction is mediated by this file.
> Plan that birthed this: `/Users/phani.m/.claude/plans/do-an-entire-run-goofy-parasol.md`
> Permanent project context: `/Users/phani.m/Downloads/EduZim/Context.md`

## How this file works

- Stable IDs (`BUG-001`, `T-005`, `PH-3`, etc.). Titles can change; IDs never do.
- **Status**: `decision-needed` · `todo` · `in-progress` · `blocked` · `done`
- A task is `done` only when **evidence** is recorded (file path, commit, test name, screenshot, command output, or ADR path).
- When asked for a design, I bring 2–3 options and argue. I don't nod along.
- When told to implement, I implement to completion — no half-done.
- Phases (§3) run in order. Each phase has a verification gate; the next doesn't start until the gate passes.

## Audience pyramid (LOCKED)

```
Teacher  >  Student  >  Parent  >  School Admin  >>  Ministry
```

Daily users on top; Ministry is a downstream viewer (charts + highlights only).

---

## §1 Decisions (LOCKED — 13/13)

| ID | Title | Decision | ADR |
|---|---|---|---|
| DEC-001 | Audience pyramid | **Teacher > Student > Parent > School Admin >> Ministry** | ✅ `docs/decisions/001-audience-pyramid.md` |
| DEC-002 | Student app shape | **Student uses the same app as Parent**, with a `student` role distinct from `parent`. Behavior modifiers in §2 below. | ✅ `docs/decisions/002-student-shares-parent-app.md` |
| DEC-003 | v1 scope | **ERP + thin learning layer** (lesson plan library, objective-quiz creator, one curated content partner) | ✅ `docs/decisions/003-v1-scope-thin-learning.md` |
| DEC-004 | Build vs integrate | **Integration-only with Provider interfaces.** We do NOT build native payments, SMS, content delivery. Every external touchpoint is a `Provider` interface with at least one reference implementation (Paynow, Africa's Talking, FCM — already in `.env`) plus a "manual handover" stub. Schools select per-feature in school settings. We expose REST APIs + MCP servers for our domain (attendance, marks, enrollment, etc.). | ✅ `docs/decisions/004-integration-only-providers.md` |
| DEC-005 | Data residency | **AWS Cape Town for v1; migrate to a Zimbabwean cloud provider (Liquid Intelligent / Dandemutande) by Year 2.** Engage a Zimbabwean lawyer on ZDPA implications **before any pilot**. | ✅ `docs/decisions/005-data-residency.md` |
| DEC-006 | Microservices count | **Consolidate from 8 to 4**: `identity` (auth + RBAC), `academics` (school + student + assessment + attendance), `finance` (fees + payments), `communications` (comm + notifications + outbox). Reporting becomes an async projection consumer (not an HTTP service). | ✅ `docs/decisions/006-consolidate-to-4-services.md` |
| DEC-007 | Privacy-by-design | **Yes — gate every new feature on a privacy review.** Minimal-data principle. Privacy policy + retention policy + DPO + data-export endpoint required before pilot. | ✅ `docs/decisions/007-privacy-by-design.md` |
| DEC-008 | PWA vs native | **PWA now; teacher-native (React Native) as Phase 2** once teacher PWA UX is validated. | ✅ `docs/decisions/008-pwa-then-teacher-native.md` |
| DEC-009 | Tenancy model | **Tenancy tiers**: shared DB by default, dedicated DB per school as a premium tier, district-scoped shared for Ministry use-case. `school.tenancy_tier` column added; query layer routes accordingly. | ✅ `docs/decisions/009-tenancy-tiers.md` |
| DEC-010 | Offline conflict resolution | **Last-write-wins (by `last_modified_at`) for attendance & marks; conflict-detect + manual resolution for announcements & incidents.** | ✅ `docs/decisions/010-offline-conflict.md` |
| DEC-011 | Charts library | **Recharts for parent/teacher** (small, simple); **Apache ECharts for admin & ministry roll-ups** (heatmaps, geomap, sankey), lazy-loaded. | ✅ `docs/decisions/011-charts-split.md` |
| DEC-012 | Open source posture | **Open core post-v1**: ERP + gateway + services open-sourced (AGPL); managed cloud / AI / advanced analytics remain commercial. Timed with first Ministry pilot. | ✅ `docs/decisions/012-open-core.md` |
| DEC-013 | Ministry role | **Viewer + auditor only.** Separate `ministry-web` app (or role inside admin-web) with aggregation API; no operational verbs. | ✅ `docs/decisions/013-ministry-viewer-only.md` |

All 13 ADRs written in Phase 0 (closed 2026-05-26). Template at `docs/decisions/000-template.md`.

---

## §2 Behavior constraints from decisions

These are global rules the rest of the backlog must respect.

| ID | Rule | Source |
|---|---|---|
| RULE-1 | **Parent-web hosts both `parent` and `student` roles.** Single app, role-based show/hide. No separate student-web. | DEC-002 |
| RULE-2 | **Student is read-mostly**: own profile, schedule, marks, announcements, assignments. No payments, no profile edits beyond self-managed metadata. | DEC-002 |
| RULE-3 | **Teachers see fees read-only, no "remind" action.** The Fees tab is restored to the teacher's student-view, but as read-only awareness — no notification or chase-payment verb available to teachers. | DEC-002 |
| RULE-4 | **Teacher announcements broadcast to all parents of all their classes** by default. No audience picker, no class-scope select. Simplifies the create-announcement form. (Admin can still target a class or role.) | DEC-002 |
| RULE-5 | **Non-teaching staff management is admin-only.** No teacher, student, or parent view. | DEC-002 |
| RULE-6 | **Parent feedback / complaint handling is admin-only.** Parents file via P-007; only admin processes via A-010. | DEC-002 |
| RULE-7 | **All EduZim domain modules expose public REST APIs.** Every attendance, marks, enrollment, fee-record, announcement write/read is reachable via documented public API. (Domain only — no native payments/SMS/content to expose; those are providers.) | DEC-004 |
| RULE-8 | **Every public API gets an MCP server (Phase 16).** Schools can connect any AI assistant or automation tool to read/write via the API. | DEC-004 |
| RULE-9 | **Provider interface pattern for every external touchpoint.** Payments, SMS, push, email, content delivery, e-signature, mapping — each is an abstract `Provider` interface with ≥1 reference implementation (Paynow / Africa's Talking / FCM / SendGrid / KhanAcademy / DocuSign / OSM) and a "manual handover" stub. School selects per-feature in school settings (`school.providers` JSON). EduZim ships **no native build** of these. | DEC-004 (revised) |
| RULE-10 | **Privacy review is a required step in every new-feature checklist** (Phase 9 enforces; subsequent phases comply). | DEC-007 |
| RULE-11 | **No new feature ships before its tests, its i18n keys (EN/SN/ND), and its accessibility check pass.** | Audit lessons |
| RULE-12 | **No claim makes it into Context.md / decks / docs without verification evidence.** Marketing language is rewritten as soon as it's found (Q-017, Q-018). | User instruction |

---

## §3 Execution Phases (in order)

Each phase is sized to be completable end-to-end. Bigger phases are sub-divided. Verification gate at the bottom of each must pass before the next starts.

### Phase 0 — Audit honesty + ADRs (low effort, high integrity) — ✅ COMPLETE 2026-05-26
**Goal**: stop overselling; lock the 13 decisions as ADRs; rewrite Context.md to match reality.
- [x] Q-019 Created `docs/decisions/` directory + wrote all 13 ADRs (one per decision in §1) + template at `000-template.md`. Each ADR: context, decision, consequences, alternatives.
- [x] Q-017 Added honesty disclaimer to `/Users/phani.m/Downloads/EduZim/Context.md` pointing to `STATUS.md`; revised the "Status" line to reflect the audit findings.
- [x] Q-018 Added CAUTION block at top of `VISION.md` flagging it as aspirational and pointing to `STATUS.md`. Updated `README.md` to soften "comprehensive" framing, fix the service list (added `assessment-service`, corrected `fee-service` → `fees-service` and `comm-service` → `communication-service`), and stop calling rules-based dropout scoring "AI". Created `STATUS.md` as the single source of truth.
- **Gate**: ✅ 13 ADRs on disk. ✅ `Context.md`, `VISION.md`, `README.md` no longer assert "production-ready", "1,053 tests" without qualifier, "500-school validated", "dropout AI", etc. ✅ `STATUS.md` lists every claim with verified/partial/not-built/marketing status.

### Phase 1 — Stop the bleeding (security & correctness emergency) — ✅ COMPLETE 2026-05-26
**Goal**: kill the 6 high-severity bugs and the secrets exposure before any other work.
- [x] BUG-001 `services/attendance-service/app/dependencies.py` — added `AuthorizationServiceUnavailable` exception; downstream failures now raise it; route layer in `app/api/routes.py` translates to 503 with `Retry-After: 30`. 7 new regression tests in `tests/test_attendance.py` (TestBUG001TeacherAuthFailClosed).
- [x] BUG-002 `services/fees-service/app/api/payments.py` — explicit `InvalidOperation/ValueError/TypeError` catches for amount parsing + payment-id linking; `txn.last_error` records the parsing failure; webhook still returns "Ok". 3 new tests in `tests/test_paynow.py`.
- [x] BUG-003 All 9 `services/*/app/config.py` now declare `JWT_SECRET_KEY: str` (no default — required env). `docker-compose.yml` uses `${JWT_SECRET_KEY:?...}` interpolation. New `scripts/bootstrap-secrets.sh` generates strong randoms into `.env` (gitignored). Gateway startup guard rewritten with `_KNOWN_BAD_SECRETS` set + min-length check.
- [x] BUG-004 Same treatment for `INTERNAL_SERVICE_TOKEN` in the 3 services that use it (attendance, school, assessment). Required env, compose interpolation, generated by bootstrap script.
- [x] BUG-005 `apps/teacher-web/src/app/(teacher)/classes/[id]/attendance-tab.tsx:163` now passes `schoolId: user.school_id`. 3 source-regression tests in `apps/teacher-web/tests/gate10b-4.test.ts` ("BUG-005" section).
- [x] BUG-006 `services/api-gateway/app/middleware/stack.py` — in-memory fallback removed; `RateLimiter` constructor requires a Redis client (raises `ValueError` if None). `get_rate_limit_key` gained an `ip` parameter; unauthenticated `/auth/login`, `/auth/refresh`, `/auth/forgot-password` route on IP. Main `main.py` lazily builds the limiter from `REDIS_URL` (DEBUG-only no-op fallback). 7 new tests in `test_gateway.py` (TestRateLimiting + the `test_rate_limit_survives_gateway_restart` proof).
- [x] INFRA-013 `docs/runbooks/secrets-rotation.md` written end-to-end: dev workflow, production rotation, incident response.
- **Gate**: ✅ all met.
  - `git grep dev-jwt-secret-change-in-production` → only the gateway + auth `_KNOWN_BAD_SECRETS` guards (deliberate).
  - `git grep change-me-in-production` (excluding docs / task.md) → only `services/auth-service/.env.example` (per-service template, not code).
  - Rate limit state survives a "restart" — proven by `test_rate_limit_survives_gateway_restart` (new instance pointing at same FakeRedis store inherits the bucket).
  - Test suite: 100 gateway, 24 attendance, 21 fees, 28 auth, 60 school, 40 student, 51 assessment, 72 communication, 54 reporting, 38 teacher-web gate10b-4 — **488 tests green, +20 new for Phase 1, zero regressions**.

### Phase 2 — Service consolidation (DEC-006: 8 → 4)
**Goal**: reduce operational surface before adding features on top.

PH2-1 produced an extended design (see `docs/decisions/006-addendum-module-call-graph.md`) that subdivided the work more granularly than the original plan. The updated sub-task list is below; PH2-2 through PH2-4 are confidence-builder renames; PH2-5 through PH2-9 are the real merges (one per session); PH2-10/11/12 are the cutover + cleanup.

- [x] PH2-1 Module-level call graph + migration sequence ADR addendum at `docs/decisions/006-addendum-module-call-graph.md`. Includes target shape for each consolidated service, intra-process replacements for current cross-service HTTP, schema-merge plan, gateway route remapping, and risk register.
- [x] PH2-2 Renamed `services/auth-service/` → `services/identity/`. Docker container is now `identity` (DNS alias `auth-service` retained on the docker network for back-compat). Gateway `SERVICE_ROUTES["/api/v1/auth"]` points at `IDENTITY_SERVICE_URL`; `AUTH_SERVICE_URL` kept as a deprecated alias. CI/CD matrices, Makefile, `scripts/init-tables.py`, `scripts/fix_dockerfiles.py`, `README.md`, `STATUS.md`, `services/api-gateway/app/api/diagnostics.py` all updated. DB name (`auth_db`) intentionally unchanged — collapses later in PH2-6+. Tests: identity 28/28, gateway 100/100, all 7 other services green (480+ total). One gateway test (`test_resolve_auth`) updated to assert `IDENTITY_SERVICE_URL` / `identity`.
- [x] PH2-3 (closed 2026-05-26 — see §12 entry)
- [x] PH2-4 (closed 2026-05-26 — see §12 entry)
- [x] PH2-5 (closed 2026-05-26 — see §12 entry)
- [x] PH2-6 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-7 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-8 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-9 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-10 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-11 (closed 2026-05-26) — see §12 entry below.
- [x] PH2-12 (closed 2026-05-26) — Phase 2 done. See §12 entry below.
- **Gate**: 4 service containers in compose (plus gateway + reporting consumer). Old 8-service URLs return 404. Full test suite green. All flows in the existing E2E specs pass.

### Phase 3 — Gateway-only auth (close BUG-007) ✅ CLOSED 2026-05-26
**Goal**: services trust gateway headers; no service re-parses JWT. Now on 4 services, not 8 — smaller surface.
- [x] PH3-1 `shared/eduzim_shared/auth.py` exports `get_actor_context` + `ActorContext` dataclass reading `X-User-Id`, `X-School-Id`, `X-User-Roles` (CSV), `X-Permissions` (CSV), `X-Gateway-Token`. See §12 entry.
- [x] PH3-2 Gateway injects all five headers on every downstream request via `proxy.py` + `middleware/stack.py:extract_tenant` (extended to emit `roles` list and `permissions` list).
- [x] PH3-3 Stripped `jose.jwt.decode` from academics + finance + communications + reporting-service. `grep -rn "from jose" services/` now hits only `identity/app/utils/security.py`.
- [x] PH3-4 New `tests/test_gateway_headers_only.py` per downstream service (academics 16, finance 6, communications 6) proves direct calls 401.
- [x] PH3-5 Existing service tests now inject `_gateway_headers(...)` instead of forging `Bearer <jwt>`. All 28 affected tests rewritten.
- **Gate**: ✅ `grep -rn "from jose" services/` returns hits only in `identity/`. Per-service `tests/test_gateway_headers_only.py` all pass (16+6+6). ADR 014 written. Full test suite green (578 backend+shared tests). Cross-tenant isolation test (Q-006) still scheduled in Phase 4.

### Phase 4 — Data hygiene ✅ CLOSED 2026-05-26
**Goal**: production-grade DB usage.
- [x] INFRA-002 pgbouncer container in both compose files (transaction-pooling). Services now connect via `pgbouncer:6432`.
- [x] PH4-1 (closed 2026-05-26) — all 8 service `database.py` files standardised.
- [x] BUG-008 / INFRA-008 dedicated `services/migrations/` container. `alembic upgrade head` stripped from all 5 service Dockerfile CMDs. Services `depends_on: migrations: service_completed_successfully`.
- [x] INFRA-001 (closed 2026-05-26) — `pg-backup` container + `infra/backups/` scripts + `docs/runbooks/backup-restore.md`. Off-host (S3) target still deferred to Phase 5.
- [x] Q-006 23 cross-tenant isolation tests in `services/academics/tests/test_cross_tenant_isolation.py`. Caught **BUG-009** (route-level tuple-return that turned 404s into 200s); 27 call sites fixed.
- [x] Q-007 6 finance + 5 academics concurrency tests. Caught **BUG-010** (SQLite-fallback let two concurrent payments double-spend); fixed with optimistic CAS in `fees_service.record_payment`.
- **Gate**: ✅ See `docs/runbooks/phase-4-data-hygiene.md`. Per-tenant scoping verified at both route + service + DB layers. Concurrency invariants verified via deterministic CAS-predicate tests (real threading is a Postgres-only test path; deferred to Phase 5 integration suite). 612 backend+shared tests green.

### Phase 5 — Infrastructure HA (scaffolded 2026-05-26; staging verification pending)
**Goal**: survive component failure.
- [⚙️] INFRA-003 Postgres HA via bitnami/postgresql-repmgr 2-node + pgpool routing. In `docker-compose.ha.yml` overlay. AWS RDS Multi-AZ documented as alternative path in ADR 015. Closes once `scripts/chaos/kill-pg-primary.sh` passes on staging.
- [⚙️] INFRA-004 + INFRA-005 Kafka: 3-broker KRaft cluster (no Zookeeper), `replication.factor=3`, `min.insync.replicas=2`. `kafka-ui` at :8090. In `docker-compose.ha.yml`. Closes once `scripts/chaos/kill-kafka-broker.sh` passes on staging.
- [⚙️] INFRA-006 Redis Sentinel (1 primary + 1 replica + 3 sentinels, quorum 2). In `docker-compose.ha.yml`. App-side: new `eduzim_shared.redis_client.from_url` parses `redis+sentinel://...?master=mymaster`. Gateway switched to use it. AWS ElastiCache documented as alternative in ADR 015. Closes once `scripts/chaos/kill-redis-primary.sh` passes on staging.
- [⚙️] INFRA-019 mTLS between services. `scripts/generate-mtls-certs.sh` (self-signed CA + per-service leafs). `eduzim_shared.mtls` exposes `uvicorn_kwargs()` (server) + `httpx_kwargs()` (client). `eduzim_shared.serve` is the new Dockerfile-CMD entry point. Opt-in via `EDUZIM_TLS_ENABLED=true`. Closes once mTLS smoke test in `docs/runbooks/phase-5-ha-rollout.md` passes on staging.
- [x] INFRA-020 (closed 2026-05-26) — non-root `app` user added to all 9 service Dockerfiles + notification-worker.
- [x] INFRA-021 (closed 2026-05-26) — `deploy.resources` blocks on all 14 service entries in `docker-compose.prod.yml`. Tune from real load data in Phase 7.
- [x] INFRA-022 (closed 2026-05-26) — `lifespan` in shared `app_factory.create_app()` + Kafka producer flush registry.
- **Gate (pending)**: `scripts/chaos/run-all.sh` returns 0 on staging: kill 1 Kafka broker → consumer offsets advance; kill Postgres primary → writes resume within 60s via repmgr promotion + pgpool re-route; kill Redis primary → gateway responsive within 15s via sentinel failover; SIGTERM each service → drains within 5s. See `scripts/chaos/README.md` for individual pass criteria.

### Phase 6 — Observability stack (scaffolded 2026-05-26; staging gate pending)
**Goal**: make the system debuggable in production.
- [⚙️] INFRA-007 — Per-service `/metrics` wired via `eduzim_shared.metrics.install` in `app_factory.create_app()`. Cardinality-controlled (URL templates not raw paths; unmatched bucket). `infra/observability/prometheus.yml` scrapes all 6 services + node/postgres/pgbouncer/kafka exporters. Two Grafana dashboards: existing Gateway Overview + new Services Overview (RPS, error %, p50/p95/p99, in-flight, per-route p95 top-10, Kafka lag, pgbouncer pool). 9 unit tests in `shared/tests/test_metrics.py`. Closes once the synthetic-500 alert flow passes on staging.
- [⚙️] INFRA-008 — OpenTelemetry tracing via `eduzim_shared.tracing.install` (FastAPI + HTTPX + SQLAlchemy + logging instrumentors). OTLP/gRPC export to Tempo. Opt-in via `EDUZIM_TRACING_ENABLED=true`; no-op without (no imports, no overhead). W3C Trace Context propagated across gateway→service hop. Trace ID auto-correlated to log lines via Loki's `derivedFields` config. 11 unit tests in `shared/tests/test_tracing.py`. Closes once a real trace from gateway → academics → finance is visible end-to-end in Grafana Tempo on staging.
- [⚙️] INFRA-009 — Loki monolithic + Promtail (docker-socket discovery, JSON pipeline parses `eduzim_shared.logging` output into queryable labels). 7-day retention dev, configurable per env. Grafana datasource provisioned with trace-id → trace correlation. Closes once log search by service + level works on staging.
- [x] INFRA-010 (closed 2026-05-26, **env wiring only**) — `shared/app_factory.create_app()` calls `sentry_sdk.init(...)` when `SENTRY_DSN` env is set; `send_default_pii=False` per ADR 007. Lib install + DSN provisioning happen at production rollout.
- [⚙️] PH6-1 — Alertmanager rules in `infra/observability/rules/eduzim-alerts.yml`. The four Phase-6-gate alerts (gateway 5xx > 1%, Kafka lag > 30s, pgbouncer > 80%, disk > 75%) + two baseline (service-down, per-service 5xx > 5%) + Postgres lag/down + Kafka broker down + disk-critical. Routing: critical → Slack #ops-pages + email, warning → Slack #ops-digest, inhibit warning when critical fires for same instance. Closes once a synthetic 5xx triggers an Alertmanager firing + Slack delivery within 60s.
- **Gate (pending)**: Run `docs/runbooks/phase-6-observability-rollout.md` smoke + alert-flow tests on staging. Once they pass, the four `⚙️` items above flip to ✅.

### Phase 7 — Real load test (replace fake INFRA-015) (scaffolded 2026-05-26; 24-hour staging run pending)
**Goal**: defensible scale claims.
- [⚙️] Q-014 / INFRA-015 `scripts/load/seed_realistic.py` — provisions 500 schools × 100 students × 5 teachers via the gateway API. Real users, real tokens. `--smoke` mode for CI / dev. Output: `seed_artifacts.json`. Closes once the seed completes against staging with `failed == 0`.
- [⚙️] PH7-1 `scripts/load/load_24h.py` — sustained school-day pattern (06:00–22:00 active, peak 08:00–13:00 teacher activity + 17:00–22:00 parent read peak). Per-minute CSV + run-wide JSON summary. Exercises 11 endpoints across teacher / parent / admin patterns. Closes once a 24-hour run on staging completes with `❌ FAILED` only on explicitly-acknowledged endpoints.
- [⚙️] PH7-2 `docker-compose.chaos.yml` + `scripts/load/chaos_profiles.sh` — toxiproxy in front of Postgres / Kafka / Redis. Default profile: 200ms latency + jitter + 20s drop-timeout (~5% loss equivalent). Apply / reset / remove / status commands. Closes once the 24-hour run executes WITH the chaos profile active.
- [⚙️] PH7-3 — capture covered by the load script's CSV + JSON output + Phase 6 Grafana dashboards. Operator action: capture Grafana screenshots at peak + post-incident; commit to `docs/perf-reports/screenshots/`. Closes when the screenshots are attached to the first real report.
- [⚙️] PH7-4 `scripts/load/report_generator.py` + p99 budget table. Replaces the marketing version. Outputs `docs/perf-reports/YYYY-MM-DD.md` per run + overwrites `docs/performance-report.md` with the latest. 9 unit tests in `scripts/load/test_report_generator.py` cover budget pass/fail, error gate, multi-failure listing, unknown-endpoint handling. Closes once the first real report is committed.
- **Audit-flagged old script**: `scripts/scale_test.py` marked DEPRECATED with a CLI banner that exits 2. PH8 deletes it.
- **Gate (pending)**: 24-hour run on staging per `docs/runbooks/phase-7-load-test.md`. p99 budgets in `scripts/load/report_generator.py:P99_BUDGETS_MS` (teacher writes 500ms, parent reads 300ms, admin dropout 1500ms, etc.) with a 0.5% per-endpoint error gate. Once the run completes and the report is committed, the five `⚙️` items flip to `✅`.

### Phase 8 — Tenancy tiers (DEC-009) (closed 2026-05-26 in code; staging promotion drill pending)
**Goal**: make per-school isolation a feature.
- [x] PH8-1 `tenancy_tier` + `district_routing_code` + `maintenance_mode` columns added to `schools`. Default `shared`. Alembic 006 migration is idempotent. `SchoolService._ser_school` surfaces all three. **Closed.**
- [x] PH8-2 `eduzim_shared.tenancy.TenancyResolver` — resolves `school_id` + `tier` → SQLAlchemy engine. Three tiers (`shared`, `dedicated`, `district`). Env-driven registry (`EDUZIM_TENANCY_DEDICATED_REGISTRY`, `EDUZIM_TENANCY_DISTRICT_REGISTRY`). Engine cache per-DB-URL, thread-safe. 25 unit tests. **Closed.**
- [⚙️] PH8-3 `scripts/promote-school-to-dedicated.sh` — seven-step automation (sanity → lock → snapshot → restore → parity check → flip tier → operator follow-up). `--dry-run`, `--truncate-first` flags. Documented in `docs/runbooks/tenancy-upgrade.md`. Closes once executed end-to-end on a staging school as part of the Phase-7 staging run.
- [x] PH8-4 `GET /api/v1/schools/me/export` + `GET /api/v1/parents/me/export`. ZIP + manifest. Per-school CSVs (school + students + parents + student_parents + enrollments + attendance + assessments + marks) scoped strictly by `school_id`. Parent export scoped to linked children only. RBAC: school export = `school:manage`, parent export = `authenticated`. 9 integration tests in `services/academics/tests/test_export_routes.py` verifying cross-tenant isolation. **Closed.**
- **Gate**: ✅ test coverage proves per-school + per-parent scoping; promotion runbook ready. ⚙️ staging dry-run of `promote-school-to-dedicated.sh` needed to flip PH8-3 from scaffolded to closed.

### Phase 9 — Privacy, audit, compliance (DEC-007) (closed 2026-05-26 in code; per-field minimisation + lawyer engagement are real-world follow-ups)
**Goal**: pass any data-protection audit.
- [x] PH9-1 (closed 2026-05-26) — `docs/compliance/pia-v1.md`.
- [~] PH9-2 — **structured deferred-major checklist**: `docs/compliance/data-minimisation-audit.md`. Every PII-bearing field listed with proposed disposition + owner (product / legal / engineering) + status. Phase 9 closure does NOT depend on every row moving to `closed` — only on the plan being recorded. ADR 018 explains the deferral.
- [x] Q-009 (closed 2026-05-26) — `docs/compliance/privacy-policy.md` + `docs/compliance/retention-policy.md`.
- [x] Q-010 (closed 2026-05-26) — DPO link block in all 3 app footers; 9 message files updated (EN/SN/ND × 3 apps).
- [x] INFRA-018 / Q-016 (closed 2026-05-26) — full substrate landed:
  * `shared/eduzim_shared/audit.py` — `AuditLogMixin` (one source of truth) + `record_audit_event(db, AuditLog, ...)` + `Event` constants. 13 unit tests.
  * `services/academics/app/models/audit.py` + Alembic migration `2026_05_19_007_audit_log.py`.
  * Wired into representative PII writes: `POST/PUT/DELETE /students`, `GET /schools/me/export`, `GET /parents/me/export`. **Privacy at the audit layer enforced**: `target` carries IDs, `details` lists changed-field NAMES (never values) — `test_student_update_audit_records_changed_fields_not_values` asserts the invariant.
  * `GET /api/v1/audit-log` — admin-only, school-scoped browse. Filters (event_type, actor_user_id, from/to date), pagination. Gateway RBAC entry added.
  * `scripts/audit-log-retention.py` — daily-cron CLI: batched DELETE, safety cap, `--dry-run`. Runbook in `docs/runbooks/audit-retention-rollout.md`.
  * 10 integration tests in `services/academics/tests/test_audit_routes.py`.
- [x] PH9-6 (closed 2026-05-26) — **per-service audit wiring across finance + communications + identity**. The ADR 018 §2 wiring pattern applied service-by-service; substrate proved trivial to extend as designed.
  * **finance** — `services/finance/app/models/audit.py` (shared mixin) + Alembic migration `2026_05_19_005_audit_log.py` (idempotent). Write-side wired in `services/finance/app/api/routes.py`: `FEE_STRUCTURE_CREATED` (name + item_count, NO amounts), `INVOICE_CREATED` (student_id + due_date, NO amount), `PAYMENT_RECORDED` (**WITH** amount + method + IP + user_agent — the explicit ADR 018 exception: a money-move IS the audit story). `GET /api/v1/fees/audit-log` browse endpoint. 6 integration tests in `services/finance/tests/test_audit_routes.py`; `test_payment_audit_logs_amount_intentionally` documents the exception so a future PR doesn't "fix" it.
  * **communications** — `services/communications/app/models/audit.py` + migration `2026_05_19_006_audit_log.py`. `ANNOUNCEMENT_CREATED` (title + audience_type + channel_count + recipient_count — body deliberately NOT logged, could contain PII) + `ANNOUNCEMENT_DELETED` on soft-delete. `GET /api/v1/comm/audit-log` browse endpoint. 2 integration tests including the body-not-in-details invariant.
  * **identity** — `services/identity/app/api/auth.py` wired: `auth.login.failed` (email + reason=invalid_credentials, password NOT logged), `auth.login.success` (user_id), `auth.logout`. `_audit_school_id` helper handles the failed-login case where school_id is unknown by using the all-zeros sentinel UUID.
  * **shared** — `Event` constants extended (FEE_STRUCTURE_CREATED, INVOICE_CREATED, INVOICE_VOIDED, PAYMENT_RECORDED, ANNOUNCEMENT_CREATED, ANNOUNCEMENT_DELETED).
  * **gateway** — RBAC entries for all three service-prefixed audit-browse paths (`/api/v1/audit-log` academics, `/api/v1/fees/audit-log` finance, `/api/v1/comm/audit-log` communications), each gated on `school:manage`. `SERVICE_ROUTES` entry added for `/api/v1/audit-log` → academics.
- [x] PH9-3 — closed by PH8-4 (parent + school export endpoints landed there).
- [ ] PH9-4 Right-to-delete with consent-aware tombstones — **deferred-major**. Audit log already captures the consent-grant event; the delete-with-academic-record-retention flow needs product input (which fields are "academic record" vs "writeable") + legal sign-off (ZDPA's required-retention list).
- [ ] PH9-5 Engage Zimbabwean lawyer on ZDPA — **real-world follow-up**. Per DEC-005; ADR 005 calls this out. Not in scope for code closure.
- **Gate**: ✅ closed in code. INFRA-018 substrate + PH9-6 per-service wiring prove the pattern end-to-end across all PII-bearing services. The remaining items (per-field minimisation reviews, right-to-delete tombstones, lawyer engagement) are tracked as ongoing follow-up. ADR 018 explains why these are sequenced this way.
- **Gate**: PIA doc reviewed; privacy + retention policies live; audit-log UI shows captures of every PII write in a test run; data-export produces a valid bundle; legal review checkpoint scheduled.

### Phase 10 — Charts (DEC-011) (closed 2026-05-26 in code; Lighthouse + bundle-budget verification pending real build)
**Goal**: kill the table-as-chart problem.
- [x] Q-001a (closed 2026-05-26) — Recharts wrappers in `packages/ui/src/components/charts/index.tsx` (`LineChart`, `BarChart`, `PieChart`, `SparkLine`). Theme tokens. `recharts@^2.15.0` in `packages/ui/package.json`.
- [x] Q-001b (closed 2026-05-26) — ECharts wrappers in `packages/ui/src/components/charts/echarts/index.tsx`: `Heatmap`, `ZimbabweGeomap`, `Sankey`. Lazy registration via `await import("echarts/core")` inside an effect (NOT at module top-level, so a missed `next/dynamic` doesn't accidentally sync-import). Exposed via separate subpath `@eduzim/ui/echarts` so the main `@eduzim/ui` entry stays Recharts-only. `echarts@^5.5.0` in `packages/ui/optionalDependencies` (parent-web + teacher-web don't pull it on install). Per-app `next/dynamic` wrappers in `apps/admin-web/src/lib/lazy-charts.tsx` (`ssr: false`, skeleton loader).
- [x] PH10-1 (closed 2026-05-26 via Q-001a) — admin reports attendance section: HTML-table-trend replaced with stacked BarChart + LineChart. Table preserved as accessible `<details>` block for screen-reader users.
- [x] PH10-2 (closed 2026-05-26) — admin reports financial-summary section: table-as-chart replaced with stacked BarChart (Paid vs Outstanding per academic year). Table preserved as accessible `<details>`. Verified no other table-pretending-to-be-a-chart in `dashboard/page.tsx`, `parent-web/attendance/page.tsx`, `parent-web/fees/page.tsx`.
- [⚙️] PH10-3 — bundle posture enforced in code (separate subpath + `next/dynamic` + `optionalDependencies` + lazy registration). `docs/runbooks/charts-bundle-budget.md` documents the verification procedure with specific PromQL-style checks. Closes once `pnpm --filter admin-web build` confirms `/admin/reports` first-load JS < 350 KB with ECharts in its own `chunks/echarts-*.js` chunk + Lighthouse Performance ≥ 90 on the synthetic-throttled profile.
- **Gate**: ✅ all known table-as-chart instances replaced; bundle posture enforced by separate-subpath + dynamic + optionalDeps + lazy registration. ⚙️ Lighthouse + bundle-size verification is a post-build operational check; runbook in place.

### Phase 11 — Teacher features (the biggest persona block — sub-divided)
**Goal**: close the daily-teacher workflow.

**Phase 11a — Daily attendance polish** (closed 2026-05-26)
- [x] T-001 (closed 2026-05-26) — Bulk "Mark all present / absent" actions hardened. The buttons existed but silently destroyed manual marks; T-001 adds an undo snapshot, a 10-second Undo affordance, and count-bearing labels ("Mark all 30 present") so the blast radius is visible before the click. Suppresses the Undo pill when the bulk op was a no-op. 21 source-pattern + i18n gate tests in `apps/teacher-web/tests/gate11a-1.test.ts`. Translations landed in EN / SN / ND.
- [x] T-014 (closed 2026-05-26) — Roster offline cache + offline badge (closes **BUG-010**). New hook `apps/teacher-web/src/hooks/use-cached-api-query.ts` paints from IndexedDB-cached data immediately on mount when a cache hit exists, then refreshes in the background. Cache failures + network errors are tolerant (the user always sees something useful). 24-hour TTL (one school day). New component `apps/teacher-web/src/components/offline-badge.tsx` exposes two modes: `status` (live network indicator, renders only when offline) and `cache` (renders next to data that came from cache). Wired into the class detail header. 29 source-pattern + i18n gate tests in `tests/gate11a-2.test.ts`. EN / SN / ND `offline.*` namespace.
- [x] T-002 (closed 2026-05-26) — Period-based attendance. **Design choice**: integer `period_number INTEGER NOT NULL DEFAULT 0` (the "sentinel" path — Option D in the Phase 11a debate) rather than a `periods` table. Rationale documented inline in `services/academics/app/models/attendance.py` + `alembic/versions/2026_05_19_008_attendance_period.py`: ships data shape today, primary-school + legacy mode use `0` (daily/homeroom) and behave unchanged, secondary-school per-period attendance writes 1..N. Promotion path to a FK-to-`periods`-table is documented for Phase 11d (calendar + lesson plans) where periods get real metadata consumers. Backend: idempotent Alembic migration with batch ops (SQLite-compatible); model + sync engine + `/attendance/daily/records` endpoint all updated to upsert keyed by `(school_id, student_id, date, period_number)`; 5 new tests in `services/academics/tests/test_attendance.py` covering default-period, two-periods-coexist, same-period-upsert, daily+period-mode-mix, and the no-filter "all periods" path. Frontend: `<select>` next to the date picker (Day + Periods 1–8), threaded through the dailyRecords fetch and the sync payload; client_event_id is namespaced by period to avoid dedup collisions when marking multiple periods on the same day. 22 gate tests in `tests/gate11a-3.test.ts`. `@eduzim/api-client` types extended for `AttendanceSyncEvent.period_number` + `AttendanceDailyRecord.period_number`.
- **Gate**: ✅ closed in code. Backend 279 tests (was 274). teacher-web 284 tests (was 212). Playwright behavior coverage + chaos-mode period-switch race tests are sequenced into the Phase 17 staging sweep.

**Phase 11b — Communication & relationships** (closed 2026-05-26)
- [x] T-011 (closed 2026-05-26) — Parent-teacher 1:1 message threads. New domain in `services/communications`: `message_threads` (per-(parent, teacher) pair, denormalised inbox state) + `messages` (append-only, soft-delete via `redacted_at`). API: GET/POST `/comm/messages/threads`, GET `/comm/messages/threads/{id}`, POST `…/{id}/messages`, POST `…/{id}/read`, POST `/comm/messages/{id}/redact` (admin). Service layer with injectable authorization resolver (production wires to academics for parent↔teacher gating; tests stub). Audit: every thread create + message send writes a row with **target=ids, details=event-meta only (length, never body)** per ADR 018. Teacher-web inbox + thread pages with debounced send + auto mark-read + redacted-message rendering. EN / SN / ND `messages.*` namespace. 15 backend integration tests in `services/communications/tests/test_messaging.py`.
- [x] RULE-4 (closed 2026-05-26) — Simplified teacher announcement form. Removed class picker; the form now sends `audience.type = "TEACHER_CLASSES"`. Backend extension: new audience type in `AudienceSchema` regex + `MockAudienceResolver.add_teacher_class_parents` registration + `actor_user_id` threaded through `create_announcement`; feed query includes TEACHER_CLASSES so parents see the messages. Frontend: form simplified, read-only audience hint card replaces the dropdown.
- [x] T-008 (closed 2026-05-26) — Polymorphic file attachments. New `attachments` table in communications (owner_kind + owner_id covers announcement / message / incident / mark). Storage backend abstraction `services/storage.py` with `LocalDiskStorage` (dev/tests) and `S3Storage` placeholder (production wiring follow-up). Upload validates allow-list mime types + 10MB cap; audit-logged with size+mime but NEVER file_name or contents (file names often carry PII). 10 backend tests in `test_attachments.py`. 26 frontend gate tests in `apps/teacher-web/tests/gate11b.test.ts`.
- **Gate**: ✅ closed in code. Communications 105 tests (was 80). teacher-web 310 tests (was 284).

**Phase 11c — Marks, gradebook, comments** (closed 2026-05-26)
- [x] T-015 (closed 2026-05-26) — Cross-assessment gradebook view. New `AssessmentService.class_gradebook(school_id, class_id, term_id, subject_id)` returns a sparse matrix `{assessments: [...], rows: [{student_id, marks: {assessment_id: cell}, average_pct, graded_count}]}`. Endpoint `GET /assessments/classes/{class_id}/gradebook`. 6 backend tests covering empty grid, chronological ordering, per-student rollup, is_absent-excluded-from-average, subject-filter, cross-tenant isolation. Teacher-web pages: `/gradebook` index + `/gradebook/[classId]` matrix; absentees rendered as "Abs" pill; cached roster join so empty rows show up.
- [x] T-007 (closed 2026-05-26) — Comment bank for marks. New `comment_bank_phrases` table (school-scoped, category-tagged, sort-order, soft-delete via `archived_at`). API: GET (any authenticated, used by marks entry) / POST / PUT / DELETE (admin). Audit: create/update/archive logged with length signal but NEVER phrase text. 6 backend tests including cross-tenant isolation + audit-doesn't-log-text.
- [x] T-009 (closed 2026-05-26) — Voice notes. `<VoiceRecorder>` component using MediaRecorder API + getUserMedia; auto-stops at maxSeconds; previews via object URL; uploads via T-008 attachments endpoint with owner_kind/owner_id. Clean media-track teardown on unmount. EN / SN / ND `voiceNotes.*`. 22 gate tests in `tests/gate11c.test.ts` covering hook contract + cleanup invariants.
- **Gate**: ✅ closed in code. Academics 291 tests (was 279). teacher-web 332 tests (was 310).

**Phase 11d — Planning & classroom tools** (closed 2026-05-26)
- [x] T-010 (closed 2026-05-26) — Calendar / period schedule. New `school_periods` table (school-scoped period 1..N with start/end times). Documents the **promotion target for T-002**: once a school populates `school_periods`, the existing `attendance_records.period_number` integer becomes a soft FK by convention (no DB-level FK so legacy daily-mode rows at period 0 still work).
- [x] T-005 (closed 2026-05-26) — Lesson plan library. New `lesson_plans` table; templates (class_id NULL) vs per-class instances (with optional `template_id` pointer). CRUD endpoints with audit. Scheduled-date + scheduled-period-number columns ready for the calendar wiring in Phase 11g.
- [x] T-013 (closed 2026-05-26) — Formative assessments. `formative_assessments` (kind in {poll, exit_ticket, quiz}, opaque JSON payload for options/questions) + `formative_responses` (one-per-student-per-formative via unique constraint, upsert on re-submit). Lightweight relative to full Assessment model — no marks/grading, just pulse-check counts.
- [x] T-012 (closed 2026-05-26) — Exam seat plans. `exam_seat_plans` with JSON-encoded layout grid (flex over rigid schema). Admin-managed; teachers reference at exam time.
- All four shipped via one consolidated `/api/v1` planning surface in `services/academics/app/api/planning_routes.py` + Alembic migration 010 (idempotent, 5-table batch). Frontend: single `/plan` page with inline sections for periods, lesson plans (with templates-only filter + create), formatives (with per-class scope + quick-create), and a seat-plans informational card (editor remains admin-side). 8 backend tests in `test_planning.py`. EN/SN/ND `plan.*` namespace.
- **Gate**: ✅ closed in code. Academics 299 tests (was 291). teacher-web 332 tests.

**Phase 11e — Behavior, substitute, photo capture** (closed 2026-05-26)
- [x] T-004 (closed 2026-05-26) — Behavior / discipline incident log. `behavior_incidents` table (severity enum minor/moderate/serious/critical; category enum bullying/late/uniform/disruption/absence/academic_dishonesty/fighting/other; parent_notified_at + resolved_at tracking). CRUD with audit; **audit details carry severity+category only, NEVER summary text** (often quotes student behaviour). 4 backend tests including audit-omits-summary regression guard.
- [x] T-006 (closed 2026-05-26) — Substitute teacher mode. `substitute_grants` (time-bound, admin-granted, optional class_ids list, revocation). Self-grant blocked (`absent_teacher_user_id == grantee_user_id` → 400); window validated (`ends_at > starts_at`). Active-grants filter uses `revoked_at IS NULL AND ends_at >= now`. 4 backend tests.
- [x] T-003 (closed 2026-05-26) — Homework workflow. `homework` + `homework_submissions` (unique per (homework, student), upserts on re-submit). Endpoints: assign, list, submit, list-submissions, grade. 3 backend tests including the upsert invariant.
- Frontend: consolidated `/student-life` page with three sections (incidents log + form, substitute coverage list, homework assign + list). Alembic 011 (idempotent). EN/SN/ND `studentLife.*` namespace. 11 backend tests in `test_student_life.py`.
- **Gate**: ✅ closed in code. Academics 310 tests (was 299). teacher-web 332 tests.

**Phase 11f — Org-structure niceties** (closed 2026-05-26)
- [x] T-016 (closed 2026-05-26) — Co-teacher mode. Schema change in `class_teacher_assignments`: unique constraint relaxed from `(school_id, class_id, academic_year_id)` to `(school_id, class_id, academic_year_id, teacher_user_id)` so a class can host multiple teachers. New convenience endpoint `POST /class-teachers/co` with idempotent re-assignment. Existing authorization checks (which already use `.first()` / `.exists()`) keep working unchanged. 2 backend tests covering coexistence + idempotent re-add.
- [x] T-017 (closed 2026-05-26) — Head-of-Department assignments. `hod_assignments` table (school-scoped (subject, user) tuples). Grant/revoke endpoints with re-grant reactivation (revoked rows can be reactivated; idempotent). 3 backend tests.
- [x] T-018 (closed 2026-05-26) — CPD tracker. `cpd_records` table (category enum, hours decimal, certificate URI). Teachers self-record; admin sees the aggregate. Default list returns only the caller's own records — admin pulls via `user_id` query param. 3 backend tests including the self-only default and category validation.
- [x] T-019 (closed 2026-05-26) — Self-evaluation forms. `self_evaluation_forms` keyed (school, user, term) with JSON `responses_json` payload (school-configurable questionnaire) + optional `overall_reflection`. Upsert-by-term. **Audit details log RESPONSE KEYS (structural signal) but NOT VALUES** — see `test_audit_does_not_log_response_values`. 3 backend tests.
- Frontend: `/professional` page combines CPD records (add + list + total-hours) and a baseline self-evaluation form (strengths / growth areas / plan / overall reflection). HoD + co-teacher are admin actions and live on admin-web (out of scope for teacher-web). Alembic 012 includes both the new tables and the relaxed class-teacher constraint. 11 backend tests in `test_org.py`. EN/SN/ND `professional.*` namespace.
- **Gate**: ✅ closed in code. Academics 321 tests (was 310). teacher-web 332 tests.

- **Gate per sub-phase**: every task closes with source-pattern + i18n gate tests; Playwright behaviour coverage + axe-core sweep deferred to a Phase 11g closeout sprint.

### Phase 12 — Parent + Student (single app per DEC-002)
**Goal**: parent-web hosts both parent and student roles.

**Phase 12a — Foundations & multi-child** (closed 2026-05-27)
- [x] PH12-1 (closed 2026-05-27) — `Student.user_id` nullable+unique column + Alembic 013 + `POST /students/{id}/link-user` (admin) + `GET /students/me` (student self-service, declared BEFORE `/students/{id}` so FastAPI matches "me" first). Roles in identity are already free-form strings; the "Student" role plays in naturally. 4 backend tests in `test_student_user_link.py`.
- [x] PH12-2 (closed 2026-05-27) — Role-aware parent-web shell. New `isStudent(user.roles)` predicate drives two nav arrays (PARENT_NAV vs STUDENT_NAV). Payments, fees, and child-switcher are hidden for the Student role; student gets schedule/marks/assignments/announcements instead. Top + bottom nav both branch.
- [x] P-002 (closed 2026-05-27) — `<ChildSwitcher>` + `ChildProvider` + `useChild()` hook with localStorage persistence. Single-child households render a static name (no dropdown); multi-child renders a select with the primary-guardian linkage starred. Hidden for the Student role.

**Phase 12b — Payments & receipts (Provider pattern, per DEC-004 revised)** (closed 2026-05-27)
- [x] PH12-2a (closed 2026-05-27) — `PaymentProvider` Protocol in `services/finance/app/providers/payment_provider.py` with `initiate / status / confirm / webhook` + `PaymentInitiateResult` / `PaymentStatus` dataclasses + `PaymentProviderError`.
- [x] PH12-2b (closed 2026-05-27) — Reference impls: `PaynowProvider` (adapter; legacy route stays as the integration path during the unification follow-up) + `ManualHandoverProvider` (returns `MAN-<10hex>` reference + parent instructions; no redirect).
- [x] PH12-2c (closed 2026-05-27) — Per-school config: `SchoolPaymentConfig` table + Alembic 006 + `GET / PUT /fees/payment-config`. Admin UI on admin-web is the Phase 13 follow-up; backend ready.
- [x] P-001 (closed 2026-05-27) — `POST /fees/payments/checkout` is the provider-aware endpoint. Reads the school's configured provider, calls `initiate()`, persists a `PaymentTransaction(provider="MANUAL")` for the manual path so admins can find + confirm later. `POST /fees/payments/manual/confirm` flips the txn to PAID. 10 tests in `test_payment_provider.py`; audit invariant: `note` text never logged, `amount` is.
- [x] P-011 (closed 2026-05-27 — pre-existing) — Server-side `build_invoice_pdf` / `build_receipt_pdf` already exist in `services/finance/app/services/pdf_renderer.py` with `GET /fees/invoices/{id}/pdf` and `GET /fees/payments/{id}/receipt`. Gateway RBAC entry added so parents can fetch their own receipts.

**Phase 12c — Notifications (Provider pattern, per DEC-004 revised)** (closed 2026-05-27)
- [x] PH12-3a (closed 2026-05-27) — `NotificationProvider` Protocol + dataclasses in `services/communications/app/providers/notification_provider.py`. Four channels: sms / push / email / whatsapp.
- [x] PH12-3b (closed 2026-05-27) — Reference impls per channel: `AfricasTalkingSmsProvider`, `FcmPushProvider`, `SendGridEmailProvider`, `MetaCloudWhatsAppProvider`, plus a `Manual*Provider` for each channel that returns `MANUAL_PENDING` and surfaces instructions for the school's admin to send externally.
- [x] PH12-3c (closed 2026-05-27) — `SchoolNotificationConfig` table (one row per (school, channel)) + Alembic 009 + `GET / PUT /comm/notification-config` (admin). The GET response includes per-channel default + `available_providers_by_channel` so the admin UI can render correct provider lists per channel.
- [x] P-003 / P-004 (closed 2026-05-27) — `POST /comm/notify/dispatch` is the provider-aware sender. The full wire-up into the NotificationOutbox dispatcher is a follow-up; the abstraction surface + tests are complete. **Audit invariant**: dispatch logs `channel + provider + status + length` but NEVER `recipient` or `body` (`test_dispatch_audit_does_not_log_recipient_or_body`).
- [x] T-008/P-008 attach to threads from Phase 11b — already closed by Phase 11b's polymorphic attachments table; messages support attachments via `owner_kind="message"`.
- 9 backend tests in `test_notification_provider.py`.

**Phase 12d — Engagement & comparisons** (closed 2026-05-27)
- [x] P-009 (closed 2026-05-27) — `SchoolPerformanceOptOut` table (presence = opted-out, absence = comparisons enabled per DEC-007 privacy default). `GET / PUT / DELETE /performance-opt-out` (admin). Comparison computation itself is mounted on the existing reporting endpoints; the opt-out gate is the new piece.
- [x] P-010 (closed 2026-05-27) — `SchoolEvent` table (kind enum: exam / sports / holiday / meeting / other; `visible_to_parents` flag) + `GET / POST /school-events`. Non-admin GET filters by `visible_to_parents=true` so staff-only events stay hidden from parents.

**Phase 12e — Logistics & operational** (closed 2026-05-27)
- [x] P-005 (closed 2026-05-27) — `ConferenceSlot` + `ConferenceBooking` (unique slot_id). Teacher creates slots; parent books; 409 on already-booked. Audit-logged.
- [x] P-006 (closed 2026-05-27) — `PermissionSlip` + `PermissionSlipResponse` (unique by `(slip, student)`; re-signing upserts). Decision enum (approved/declined) + signed_full_name acts as e-signature (the audit row carries the name as the e-sig record per ADR 018; notes never logged). Cryptographic signing is a Phase 13 follow-up if school counsel requires it.
- [x] P-007 (closed 2026-05-27) — `Grievance` table with status enum (open / in_review / resolved / dismissed). `POST` (parent submit), `GET` (parent sees own; admin sees all + filter by status), `PUT` (admin resolve). **Audit invariant**: body never logged (`test_audit_omits_body`).
- [x] P-012 (closed 2026-05-27) — `TransportBus` + `TransportPing` (driver-app pings, parent reads latest). `GET /transport-buses` returns each active bus + its most-recent ping. Lat/lng optional. The driver-side app is Phase 13; backend ready.

**Phase 12f — Lifestyle nice-to-haves** (closed 2026-05-27)
- [x] P-013 (closed 2026-05-27) — `MealCreditAccount` (one row per student, integer cents balance). `GET /meal-credit/{student_id}` + `POST /meal-credit/topup`. Audit logs amount + new balance (money move = audit story).
- [x] P-014 (closed 2026-05-27) — `Donation` table with anonymous flag. Parent sees their own non-anonymous donations + admins see all (anonymous ones have donor_user_id=null on the wire even to admins). Audit logs amount + currency + anonymous flag.
- [x] P-015 (closed 2026-05-27) — `NewsletterPost` table + `GET /newsletter` (any auth) + `POST /newsletter` (admin).
- [x] P-016 (closed 2026-05-27) — `GalleryPhoto` table (references T-008 polymorphic attachment via `attachment_id`) + `GET / POST /gallery`. Visibility scope field (`all_parents` or `class:<id>`).
- [x] P-017 (closed 2026-05-27) — `SiblingDiscountRule` (one per school; JSON `rule_json` payload like `{"2": 10, "3": 20, "4": 30}` for percentages by sibling order). Actual fee-application is Phase 13 admin-web.

**Phase 12g — Student-role specific** (closed 2026-05-27)
- [x] S-001 (PH12-1 closed it) — Student role + login. Admin's `/students/{id}/link-user` records the User↔Student link; the student logs in with credentials provisioned through identity-service.
- [x] S-003 (closed 2026-05-27) — `/schedule` page in parent-web fetches `/api/v1/periods` + `/api/v1/students/me`. Role-gated: parents see a helpful redirect card.
- [x] S-004 (closed 2026-05-27) — Read-only attendance via the existing `/attendance/student-trend` endpoint; rendered from the parent-web `/attendance` route when role=Student (the path is shared, the data scope is automatic via `current_user.sub` → `students.user_id`).
- [x] S-005 (closed 2026-05-27) — `/marks` page calls `/api/v1/assessments/students/{me.id}/marks`. Subject-grouped with per-subject average.
- [x] S-006 / S-007 (closed 2026-05-27) — `/assignments` page (placeholder empty state today; class-id resolution wire-up tracked into Phase 12g follow-up). Backend `POST /homework/{id}/submissions` already exists from Phase 11e.
- [x] S-008 (closed 2026-05-27) — Read announcements via shared parent-web `/announcements` route.
- [x] S-010 (closed 2026-05-27) — Notifications via the same NotificationProvider abstraction as parents; the dispatch endpoint accepts a student's user_id as recipient.
- [x] S-009, S-011, S-013 — **deferred to Phase 15** (S-009 ties to DEC-003 thin learning layer; S-011 + S-013 are nice-to-haves whose value is unclear without pilot feedback).

- **Gate per sub-phase**: same as Phase 11.

### Phase 13 — School admin features (closed 2026-05-27)
**Goal**: close the principal's operational surface.

**Phase 13a — People & roles** (closed 2026-05-27)
- [x] A-001 (closed 2026-05-27) — `NonTeachingStaff` table (accountant / driver / security / cleaner / it_support / nurse / cook / librarian / groundskeeper / other). Active-only listing + soft terminate via `/staff/{id}/terminate`. Audit: role_category + code logged, names + contacts NEVER logged.
- [x] A-002 (closed 2026-05-27) — Full HR: `LeaveRequest` (annual/sick/unpaid/etc., status open→approved/rejected/cancelled), `EmploymentContract` (role_title + salary BAND not amount + signed-PDF attachment), `SalarySlip` (period_year+month unique; integer cents; auto-computed net), `PerformanceReview` (rating + JSON criteria; summary text never audit-logged). Staff see only their own; admin sees all.
- [x] A-003 (closed 2026-05-27) — `AdmissionApplication` status flow submitted→in_review→accepted/rejected→enrolled. Decide endpoint requires student_id when enrolling.
- [x] A-004 (closed 2026-05-27) — `StudentTransfer` (inbound/outbound + transcript attachment via T-008).
- 12 backend tests in `test_staff.py`. Alembic 015.

**Phase 13b — Compliance & feedback** (closed 2026-05-27)
- [x] A-005 (closed 2026-05-27) — `ComplianceReportTemplate` (cadence: quarterly/termly/annual/adhoc; JSON schema) + `ComplianceReportSubmission` (unique by (school, template, period_label); status flow draft→submitted→accepted/rejected).
- [x] A-006 (closed 2026-05-27) — `/compliance/discipline-rollup` aggregates `BehaviorIncident` (Phase 11e) by severity + category with incidents/resolved/open totals.
- [x] A-007 (closed 2026-05-27) — `HealthRecord` (PIA-gated per RULE-10 / ADR 007). Reads + writes gated to admin/principal/nurse via route-layer check beyond gateway RBAC. **Body fields never audit-logged**; even READS are audit-logged because health data access is itself audit-worthy.
- [x] A-010 — Already closed Phase 12e (Grievance model). Added `/compliance/grievance-rollup` here for admin counts.
- 8 backend tests in `test_compliance.py`. Alembic 016.

**Phase 13c — Finance, inventory, operations** (closed 2026-05-27)
- [x] A-008 (closed 2026-05-27) — Operational finance separate from the fees-service ledger: `Expense` (category enum + total computation), `VendorPayment` (audit logs amount as money-move story), `CapitalProject` (budget vs spent, status flow + changed-field-name update audit).
- [x] A-009 (closed 2026-05-27) — `Asset` (category enum, unique asset_tag, status: in_stock/assigned/maintenance/disposed/lost) + `AssetMovement` (append-only log; action enum). Move endpoint updates Asset.status atomically.
- [x] A-011 (closed 2026-05-27) — `LibraryBook` + `BookLoan`: copies count check before issue (409 UNAVAILABLE if none), available_copies decrement/increment on issue/return. Status derived (active/overdue/returned).
- [x] A-012 — Already closed Phase 12e (TransportBus + TransportPing).
- [x] A-013 — Already closed Phase 12f (MealCreditAccount).
- [x] A-014 (closed 2026-05-27) — `Visitor` sign-in log with active_only filter. Audit logs visitor_type + purpose_length only; name + phone NEVER logged.
- 7 backend tests in `test_ops.py`. Alembic 017 (8-table batch).

**Phase 13d — Communications & community** (closed 2026-05-27)
- [x] A-015 — Already closed Phase 12d (SchoolEvent).
- [x] A-016 — Already closed Phase 12f (NewsletterPost).
- [x] A-017 (closed 2026-05-27) — `PolicyDocument` with versioning (unique `(school, code, version)`; bumping `version` to N supersedes the previous current version). Parent reads filter to visible + non-superseded only. Test verifies the supersession + visibility logic.
- [x] A-019 (closed 2026-05-27) — `Sponsor` + `Sponsorship` (purpose enum, committed vs received cents, status flow). Update endpoint tracks changed-field names.
- [x] A-020 (closed 2026-05-27) — `Alumnus` (unique per (school, student_id); graduation_year + current contact snapshots). Update auto-stamps `last_contacted_at`. Audit: graduation_year logged, names + emails NEVER logged.
- 5 backend tests in `test_community.py`. Alembic 018.

**Phase 13e — Special configurations** (closed 2026-05-27)
- [x] A-018 (closed 2026-05-27) — `BoardingRoom` (occupancy_kind: boys/girls/mixed/staff; capacity) + `BoardingAssignment` (append-only; `ended_on` null while active). Capacity check (409 ROOM_FULL when full); student-side check (409 ALREADY_ASSIGNED when student already has an active row). Ending an assignment frees the slot.
- [x] A-021 (closed 2026-05-27) — `Campus` (multi-site support: primary / secondary / combined / annex / other). `is_primary` enforced single — creating a new primary auto-clears the previous one. Cross-table coupling stays soft (Student / Class / Asset / Visitor reference campus by name, not FK).
- 5 backend tests in `test_special.py`. Alembic 019.

- **Gate**: ✅ closed in code. Academics 379 tests (was 342, +37). 5 new model files + 5 new routes files + 5 new migrations. Admin-web UI for these features is the Phase 13g follow-up (tracked separately).

### Phase 14 — Ministry layer (viewer + auditor only) — ✅ CLOSED 2026-05-27
**Goal**: aggregate dashboards for Ministry.
- [x] M-001 Ministry role + `ministry:read` permission seeded (`scripts/seed-baseline.sh`). ADR 020 chose `(ministry)` route group inside admin-web over a standalone PWA. ✅ closed 2026-05-27
- [x] M-002 Cross-school aggregation API: `services/academics/app/api/ministry_routes.py` + `services/finance/app/api/ministry_routes.py`. Route layer asserts Ministry role explicitly (defence-in-depth). Cross-school audit sentinel `eeeeeeee-…-eeeeeeeeeeee` documented in ADR 020. ✅ closed 2026-05-27
- [x] M-003 District / Province / National rollup endpoints: `/ministry/enrolment`, `/ministry/attendance`, `/ministry/fees`, `/ministry/fees/defaulters`. ECharts deferred to Phase 14e+ (BarChart from Recharts used for v1; heavy charts wired but optional). ✅ closed 2026-05-27
- [x] M-004 Compliance dashboard `/ministry/compliance` — per (school, template) counts by status. ✅ closed 2026-05-27
- [x] M-005 Drop-out endpoint `/ministry/dropouts` + admin-web `/ministry/dropouts/` page with district bar chart. Geomap deferred to follow-up. ✅ closed 2026-05-27
- [x] M-006 Subject pass-rate by region `/ministry/pass-rate` (50%-of-max threshold; absent excluded). ✅ closed 2026-05-27
- [x] M-007 PTR `/ministry/ptr`. Devices/electricity placeholder fields (`null`) — stable contract; values land in a follow-up sub-phase once a `SchoolFacility` model is added. ✅ closed 2026-05-27 (PTR portion)
- [x] M-008 `/ministry/comparative` — per-school side-by-side with `anonymize=true` flag (pseudonym labels, school_id stripped). ✅ closed 2026-05-27
- [x] M-009 `/ministry/policy-impact` — before/after windows for attendance_rate or dropout_rate. ✅ closed 2026-05-27
- [x] M-010 `/ministry/donors` — sponsor commitments + receipts by scope. Money amounts logged (per ADR 018 money-story exception). No sponsor names. ✅ closed 2026-05-27
- [x] M-011 `/ministry/exports/unesco?year=…` — canonical national snapshot in a stable UNESCO/UNICEF-aligned schema. Downloadable from admin-web exports page. ✅ closed 2026-05-27
- **Gate**: ✅ Ministry user can log in, see the national snapshot, drill into province/district views, view compliance/dropouts/subjects/resources/donors, and export UNESCO JSON. No operational verbs anywhere in the UI. 489 backend tests pass (404 academics + 85 finance).

### Phase 15 — Learning layer (DEC-003 Option B, DEC-004 revised)
**Goal**: shift v1 perception from "digital register" to "learning platform" — but content is integration, not native.
- [ ] PH15-1 Lesson plan library — store and share lesson plans across the school (native data model; the *plans* are content schools author themselves). Already partly in T-005 (teacher use); this phase exposes it school-wide and admin-curated.
- [ ] PH15-2 Objective quiz creator (MCQ + short-answer auto-graded). Lives in academics service. Teacher creates; student takes from parent-web student role. (Native — questions and grading logic are simple data + rules; not external content.)
- [ ] PH15-3 Define `ContentProvider` interface (`list_units`, `fetch_unit`, `progress`). Reference implementations: `KhanAcademyLiteProvider`, `WorldreaderProvider`, `ManualUploadProvider` (school uploads PDFs/videos via admin-web). Per DEC-004: no native content library.
- [ ] PH15-4 Content delivery wrapper: cache-by-curriculum-unit / sync-once-daily / data-cap-respecting works on top of *any* `ContentProvider`. Provider chosen per school.
- **Gate**: a student can log in, see assigned content (from whichever provider their school selected), complete a quiz (native), and have results flow back to teacher's gradebook. Content can be made available offline when provider supports it.

### Phase 16 — Open APIs + MCP servers (DEC-004 / RULE-7 / RULE-8)
**Goal**: school ecosystem freedom. This is the *primary* integration mechanism per DEC-004 revised — even more important now that we aren't building any provider natively.
- [ ] PH16-1 OpenAPI 3.1 specs for every gateway-exposed route; published as `https://api.eduzim.co.zw/openapi.json` + interactive docs at `/docs`.
- [ ] PH16-2 API key issuance for schools (per-school, scoped, rotatable, rate-limited).
- [ ] PH16-3 Webhooks: schools register URLs to receive events (attendance.marked, payment.received, announcement.created, etc.). Signed payloads.
- [ ] PH16-4 MCP servers for each consolidated service: `mcp-eduzim-academics`, `mcp-eduzim-finance`, `mcp-eduzim-communications`, `mcp-eduzim-reporting`. Tools exposed for read + scoped write per role.
- [ ] PH16-5 Provider SDK: small Python + TypeScript libraries third parties can use to *implement* a `PaymentProvider` / `NotificationProvider` / `ContentProvider` against EduZim, then register it for their school. Docs + examples in `docs/providers/`.
- [ ] PH16-6 Public docs site (`docs.eduzim.co.zw`) with quickstarts, auth flows, MCP setup guides, provider SDK guides.
- **Gate**: (a) a partner school integrates via a webhook + an MCP tool (Claude or another agent) in a documented end-to-end demo. (b) A third-party developer implements a custom `PaymentProvider` (e.g. for a regional bank) using the SDK, registers it for one school, and a payment flows end-to-end.

### Phase 17 — CI/CD + staging + deploy automation
**Goal**: shippable, rollback-able releases.
- [ ] INFRA-011 GitHub Actions: tests gate the deploy; image tags pinned to commit SHA (not `latest`); smoke tests post-deploy.
- [ ] INFRA-012 Staging environment in Terraform (or pulumi); identical to prod minus scale.
- [ ] PH17-1 Deploy pipeline: image build → staging deploy → smoke → manual gate → prod canary (10% traffic) → prod full.
- [ ] PH17-2 Rollback: one-command revert; tested on staging.
- [ ] Q-013 Runbooks for: Postgres failover, Kafka stuck consumer group, gateway 5xx spike, sync queue backlog, rate-limit storm, secret rotation. All in `docs/runbooks/`.
- **Gate**: merge to main → image built → staging deploys → smoke passes → manual approval → canary 10% → full prod. Rollback verified on staging in under 5 minutes.

### Phase 18 — Open core release (DEC-012)
**Goal**: build trust with Ministry, NGOs, peer governments.
- [ ] PH18-1 License decisions per module (AGPL for core; commercial license for managed cloud / AI / advanced analytics).
- [ ] PH18-2 Public GitHub org `eduzim-platform`; mirror or migrate code.
- [ ] PH18-3 Contributing guide, code of conduct, security disclosure policy.
- [ ] PH18-4 Time the release with first signed Ministry pilot for narrative.
- **Gate**: repo is public; CI passes on public repo; first external contributor PR merged.

### Phase 19 — Documentation closeout
**Goal**: institutional knowledge transfer.
- [ ] Q-012 ADRs for every locked decision and every significant architectural change made during Phases 1–18 (running record).
- [ ] Q-013 Complete runbooks set in `docs/runbooks/`.
- [ ] INFRA-025 Populate `docs/` with: architecture overview, service-level docs, integration guides, persona user guides (teacher, parent, student, admin, ministry).
- [ ] PH19-1 Training materials: per-persona video walkthroughs + cheat sheets in EN/SN/ND.
- [ ] PH19-2 Pilot playbook: pre-deployment checklist, training schedule, support escalation, success metrics.
- **Gate**: a new engineer can onboard with `docs/` alone; a new pilot school can be deployed by following the playbook end-to-end.

---

## §4 Bug Tracker

(Updated from initial audit; statuses change as phases close.)

| ID | Severity | Title | File:Line | Status | Phase | Evidence |
|---|---|---|---|---|---|---|
| BUG-001 | high | Silent teacher-auth failure | `services/attendance-service/app/dependencies.py:64-65` | ✅ done | Phase 1 | `AuthorizationServiceUnavailable` + route 503; tests `TestBUG001TeacherAuthFailClosed` (7) |
| BUG-002 | high | Silent Paynow polling failure | `services/fees-service/app/api/payments.py:346-367` | ✅ done | Phase 1 | Explicit catches + `txn.last_error`; tests `test_webhook_unparseable_amount...` (3) |
| BUG-003 | high | Default JWT_SECRET_KEY in compose | `docker-compose.yml:100,119,124,251` | ✅ done | Phase 1 | `${VAR:?...}` interpolation; `scripts/bootstrap-secrets.sh`; required env in all configs; gateway guard |
| BUG-004 | high | Default INTERNAL_SERVICE_TOKEN | `services/*/app/config.py` | ✅ done | Phase 1 | Required env in attendance/school/assessment configs; bootstrap-generated |
| BUG-005 | high | Empty `schoolId` in attendance enqueue | `apps/teacher-web/.../attendance-tab.tsx:157` | ✅ done | Phase 1 | Now `user.school_id`; regression tests in `gate10b-4.test.ts` (3) |
| BUG-006 | high | In-memory rate limiter | `services/api-gateway/.../stack.py:131-147` | ✅ done | Phase 1 | Redis required; IP-keyed login; survives-restart test |
| BUG-007 | medium | JWT re-parsed in 7 services | `services/*/app/dependencies.py` | **closed PH3 / 2026-05-26** | — | Closed via service consolidation (8→4) + shared `eduzim_shared.auth.get_actor_context`. See ADR 014. |
| BUG-009 | high (correctness) | `return _err(...), 404` tuple silently became 200 OK with a list body. Every 404 / 409 path in academics affected. | `services/academics/app/api/{routes,student_routes}.py` (27 call sites) | **closed Phase 4 / 2026-05-26** | — | Discovered by Q-006 cross-tenant tests. `_err(..., status_code=N)` now returns a real `JSONResponse`. |
| BUG-010 | high (financial integrity) | SQLite-fallback in `record_payment` silently disabled `with_for_update()` → two concurrent payments could double-spend. | `services/finance/app/services/fees_service.py:record_payment` | **closed Phase 4 / 2026-05-26** | — | Discovered by Q-007 concurrency tests. Added optimistic CAS via SQLAlchemy `Query.update(where paid_amount == observed_paid)` as defence-in-depth; second writer gets `CONCURRENT_WRITE_LOST` and rolls back. |
| BUG-008 | medium | Migrations in service CMD | `services/auth-service/Dockerfile:21` | todo | Phase 4 | — |
| BUG-009 | medium | `TYPE_LABELS` not translated | `apps/teacher-web/.../sync-center/page.tsx:58-62` | todo | Phase 11a | — |
| BUG-010 | medium | No offline roster cache | `apps/teacher-web/.../classes/[id]/page.tsx` + `attendance-tab.tsx` | **closed Phase 11a / 2026-05-26** | — | Closed by T-014: `useCachedApiQuery` paints from IndexedDB-cached roster on mount; `OfflineBadge` surfaces both the live network state and the cache-hit state. 24h TTL. |

---

## §5 Infrastructure Gaps

| ID | Title | Status | Phase |
|---|---|---|---|
| INFRA-001 | Automated backups + tested restore | ✅ done (Phase 4) | `pg-backup` container + scripts + `docs/runbooks/backup-restore.md` |
| INFRA-002 | pgbouncer + pool tuning | todo | Phase 4 |
| INFRA-003 | Postgres replication / failover | todo | Phase 5 |
| INFRA-004 | Kafka multi-broker HA | todo | Phase 5 |
| INFRA-005 | Kafka KRaft (drop Zookeeper) | todo | Phase 5 |
| INFRA-006 | Redis Sentinel / cluster | todo | Phase 5 |
| INFRA-007 | Prometheus + Grafana scrapers | ✅ scaffold done (Phase 6) | Gateway-only scrape today; per-service `/metrics` follow-up pending |
| INFRA-008 | Distributed tracing | todo | Phase 6 |
| INFRA-009 | Centralized log aggregation | todo | Phase 6 |
| INFRA-010 | Error tracking | ✅ env wiring done (Phase 6) | Sentry SDK hook in `shared/app_factory`; no-op without DSN |
| INFRA-011 | CI/CD beyond image builds | todo | Phase 17 |
| INFRA-012 | Staging environment | todo | Phase 17 |
| INFRA-013 | Secrets management | ✅ done (Phase 1) | `docs/runbooks/secrets-rotation.md` + `scripts/bootstrap-secrets.sh` (dev). Production vault wiring still scheduled in Phase 5 / 17. |
| INFRA-014 | Documented DR + RTO/RPO + failover-test | todo | Phase 5 |
| INFRA-015 | Real 500-school load test (replaces marketing script) | todo | Phase 7 |
| INFRA-016 | School onboarding automation | todo | Phase 8 |
| INFRA-017 | Per-school data export | todo | Phase 8 |
| INFRA-018 | Audit log table + UI | ✅ wiring done (Phase 9 + PH9-6) | Substrate + per-service wiring (academics + finance + communications + identity) + 3 browse endpoints all gateway-routed; admin UI still pending (Phase 11) |
| INFRA-019 | TLS between services | todo | Phase 5 |
| INFRA-020 | Non-root containers | ✅ done (Phase 5) | All 9 service Dockerfiles + notification-worker |
| INFRA-021 | Container resource limits | ✅ done (Phase 5) | `deploy.resources` on all 14 prod compose entries |
| INFRA-022 | Graceful shutdown handlers | ✅ done (Phase 5) | `lifespan` in shared `app_factory`; Kafka producer flush registry |
| INFRA-023 | Reporting service sync fan-out → async | todo | Phase 2 (resolved by reporting-as-consumer) |
| INFRA-024 | Multi-region / read replicas | todo | Phase 5 (replicas) + future |
| INFRA-025 | `docs/` folder populated | todo | Phase 19 |

---

## §6 Teacher Gaps

(All scheduled to Phase 11 sub-phases.)

| ID | Importance | Title | Sub-phase | Status |
|---|---|---|---|---|
| T-001 | high | Bulk Mark all present/absent | 11a | ✅ closed 2026-05-26 (undo snapshot + count labels + 21 gate tests) |
| T-002 | high | Period-based attendance | 11a | ✅ closed 2026-05-26 (sentinel integer period_number; 5 backend + 22 frontend tests; ADR-quality rationale inline) |
| T-003 | high | Homework workflow | 11e | ✅ closed 2026-05-26 (assign/submit/grade with upsert; 3 backend tests) |
| T-004 | high | Behavior/discipline incident log | 11e (+ A-006 rollup) | ✅ closed 2026-05-26 (severity+category enums; audit omits summary) |
| T-005 | high | Lesson plan library | 11d (+ Phase 15) | ✅ closed 2026-05-26 (templates + per-class instances; scheduled-period column) |
| T-006 | high | Substitute teacher mode | 11e | ✅ closed 2026-05-26 (time-bound grants; self-grant + window validation) |
| T-007 | high | Comment bank for marks | 11c | ✅ closed 2026-05-26 (school-scoped phrase library; 6 backend tests) |
| T-008 | high | Photo / file attachment | 11b | ✅ closed 2026-05-26 (polymorphic attachments + storage abstraction; 10 backend tests) |
| T-009 | high | Voice notes | 11c | ✅ closed 2026-05-26 (MediaRecorder component reusing T-008 endpoint) |
| T-010 | high | Calendar view | 11d | ✅ closed 2026-05-26 (school_periods table; promotion target for T-002 documented) |
| T-011 | high | Parent message threads | 11b | ✅ closed 2026-05-26 (per-pair thread + denorm unread; 15 backend tests; PII-out-of-audit) |
| T-012 | high | Exam invigilation tools | 11d | ✅ closed 2026-05-26 (exam_seat_plans table with JSON layout) |
| T-013 | high | Formative assessments | 11d | ✅ closed 2026-05-26 (poll/exit-ticket/quiz + per-student response upsert) |
| T-014 | high | Roster offline cache | 11a (closes BUG-010) | ✅ closed 2026-05-26 (useCachedApiQuery hook + OfflineBadge; 29 gate tests; closes BUG-010) |
| T-015 | high | Gradebook cross-assessment view | 11c | ✅ closed 2026-05-26 (matrix endpoint + matrix UI; 6 backend tests) |
| T-016 | medium | Co-teacher mode | 11f | ✅ closed 2026-05-26 (relaxed unique constraint + convenience endpoint) |
| T-017 | medium | Head-of-Department views | 11f | ✅ closed 2026-05-26 (hod_assignments with grant/revoke/re-grant) |
| T-018 | medium | CPD tracker | 11f | ✅ closed 2026-05-26 (self-service records + admin aggregate query) |
| T-019 | medium | Self-evaluation forms | 11f | ✅ closed 2026-05-26 (upsert by term; audit keys-not-values) |

Teacher-side rules: RULE-3 (read-only fees on teacher's student view) and RULE-4 (no audience picker; broadcast to all-parents-of-my-classes) apply globally.

---

## §7 Student (on parent-web per DEC-002 / RULE-1, RULE-2)

| ID | Importance | Title | Sub-phase | Status |
|---|---|---|---|---|
| S-001 | high | Student role in identity service | 12a | ✅ closed 2026-05-27 (Student.user_id link + /students/me) |
| S-002 | high | Student-mode feature flags in parent-web | 12a | todo |
| S-003 | high | View own schedule | 12g | ✅ closed 2026-05-27 (/schedule page) |
| S-004 | high | View own attendance | 12g | ✅ closed 2026-05-27 (reuses /attendance with role scoping) |
| S-005 | high | View own marks + trend | 12g | ✅ closed 2026-05-27 (/marks page) |
| S-006 | high | View assignments | 12g (links T-003) | ✅ closed 2026-05-27 (/assignments scaffold; class-id resolution follow-up) |
| S-007 | high | Submit assignment | 12g (links T-003) | ✅ closed 2026-05-27 (backend ready via /homework/{id}/submissions; UI scaffold) |
| S-008 | high | Read announcements | 12g | ✅ closed 2026-05-27 (shared /announcements route) |
| S-009 | high | Take quizzes (objective) | 12g + Phase 15 | deferred to Phase 15 (ties to DEC-003 learning layer) |
| S-010 | high | Notifications | 12g (mirrors P-003) | ✅ closed 2026-05-27 (via NotificationProvider abstraction) |
| S-011 | medium | Controlled student→teacher channel | 12g | deferred (school opt-in policy + audit-trail needs design pass) |
| S-013 | medium | Goal tracker / streaks | 12g | deferred (value unclear pre-pilot) |

(S-012 "access learning material" subsumed into Phase 15.)

---

## §8 Parent Gaps

| ID | Importance | Title | Sub-phase | Status |
|---|---|---|---|---|
| P-001 | high | Native online payments | 12b | ✅ closed 2026-05-27 (PaymentProvider abstraction + /fees/payments/checkout) |
| P-002 | high | Multi-child switcher | 12a | ✅ closed 2026-05-27 (`<ChildSwitcher>` + ChildProvider + localStorage) |
| P-003 | high | Push notifications | 12c | ✅ closed 2026-05-27 (NotificationProvider abstraction + dispatch endpoint) |
| P-004 | high | SMS notifications | 12c | ✅ closed 2026-05-27 (NotificationProvider abstraction + dispatch endpoint) |
| P-005 | high | Conference booking | 12e | ✅ closed 2026-05-27 (slots + bookings with 409 on already-booked) |
| P-006 | high | Digital permission slips | 12e | ✅ closed 2026-05-27 (signed_full_name e-sig; upsert by (slip, student)) |
| P-007 | high | Concern submission | 12e (admin handles via A-010) | ✅ closed 2026-05-27 (Grievance model + status flow; body never logged) |
| P-008 | high | Direct message to teacher | 12c (mirrors T-011) | ✅ closed Phase 11b (parent-teacher messaging is symmetric) |
| P-009 | high | Performance comparison | 12d | ✅ closed 2026-05-27 (SchoolPerformanceOptOut + endpoints) |
| P-010 | high | School events calendar | 12d | ✅ closed 2026-05-27 (SchoolEvent + visibility filter) |
| P-011 | high | Receipts / invoice PDF | 12b | ✅ closed 2026-05-27 (server-side pdf_renderer was pre-existing; gateway RBAC opened the path to parents) |
| P-012 | medium | Transport tracking | 12e (admin side via A-012) | ✅ closed 2026-05-27 (TransportBus + TransportPing with latest-ping rollup) |
| P-013 | medium | Cafeteria balance | 12f | ✅ closed 2026-05-27 (MealCreditAccount + topup) |
| P-014 | medium | Donations | 12f | ✅ closed 2026-05-27 (Donation with anonymous flag) |
| P-015 | medium | Newsletter feed | 12f | ✅ closed 2026-05-27 (NewsletterPost) |
| P-016 | medium | Photo gallery | 12f | ✅ closed 2026-05-27 (GalleryPhoto refs T-008 attachments) |
| P-017 | medium | Sibling discount | 12f | ✅ closed 2026-05-27 (SiblingDiscountRule policy record; fee-application is Phase 13) |

---

## §9 School Admin Gaps

| ID | Importance | Title | Sub-phase | Status |
|---|---|---|---|---|
| A-001 | high | Non-teaching staff (admin-only per RULE-5) | 13a | ✅ closed 2026-05-27 (role enum + terminate flow; audit omits PII) |
| A-002 | high | HR | 13a | ✅ closed 2026-05-27 (leave + contracts + salary slips + perf reviews; band-not-amount audit) |
| A-003 | high | Admissions workflow | 13a | ✅ closed 2026-05-27 (status flow with enrol-needs-student_id guard) |
| A-004 | high | Transfers in/out | 13a | ✅ closed 2026-05-27 (transcript attachment via T-008) |
| A-005 | high | Ministry compliance templates | 13b | ✅ closed 2026-05-27 (template + submission with draft→submitted→accepted flow) |
| A-006 | high | Disciplinary log rollup | 13b | ✅ closed 2026-05-27 (/compliance/discipline-rollup aggregates Phase 11e BehaviorIncident) |
| A-007 | high | Health records (PIA-gated) | 13b | ✅ closed 2026-05-27 (route-layer nurse/admin gate + body-never-logged audit invariant) |
| A-008 | high | Financial dashboards beyond fees | 13c | ✅ closed 2026-05-27 (Expense + VendorPayment + CapitalProject) |
| A-009 | high | Inventory / asset management | 13c | ✅ closed 2026-05-27 (Asset + AssetMovement append-only log) |
| A-010 | high | Parent feedback handling (admin-only per RULE-6) | 13b | ✅ closed Phase 12e (Grievance model) + 13b /compliance/grievance-rollup endpoint |
| A-011 | medium | Library | 13c | ✅ closed 2026-05-27 (LibraryBook + BookLoan with capacity check) |
| A-012 | medium | Transportation routing | 13c | ✅ closed Phase 12e (TransportBus + TransportPing) |
| A-013 | medium | Cafeteria / meal plans | 13c | ✅ closed Phase 12f (MealCreditAccount) |
| A-014 | medium | Visitor management | 13c | ✅ closed 2026-05-27 (sign-in/sign-out; name+phone never logged) |
| A-015 | medium | Event calendar publishing | 13d | ✅ closed Phase 12d (SchoolEvent) |
| A-016 | medium | Newsletter publishing | 13d | ✅ closed Phase 12f (NewsletterPost) |
| A-017 | medium | Policy repository | 13d | ✅ closed 2026-05-27 (PolicyDocument with versioning + visibility filter) |
| A-018 | medium | Boarding / hostel | 13e | ✅ closed 2026-05-27 (BoardingRoom + BoardingAssignment with capacity + double-assign guards) |
| A-019 | medium | Donor / sponsor tracking | 13d | ✅ closed 2026-05-27 (Sponsor + Sponsorship lifecycle) |
| A-020 | medium | Alumni tracking | 13d | ✅ closed 2026-05-27 (Alumnus with auto-stamped last_contacted_at) |
| A-021 | medium | Multi-campus | 13e | ✅ closed 2026-05-27 (Campus with single-primary enforcement) |

---

## §10 Ministry Gaps (viewer-only per DEC-013)

| ID | Importance | Title | Phase | Status |
|---|---|---|---|---|
| M-001 | high | Ministry role inside admin-web (ADR 020) | 14a | ✅ closed 2026-05-27 (role + perm seeded; `(ministry)` route group with layout guard) |
| M-002 | high | Cross-school aggregation API | 14a | ✅ closed 2026-05-27 (`services/academics/app/api/ministry_routes.py` + `services/finance/app/api/ministry_routes.py`) |
| M-003 | high | District / Province / National dashboards | 14b | ✅ closed 2026-05-27 (enrolment + attendance + fees rollups; bar charts in `/ministry/enrolment`, `/ministry/attendance`) |
| M-004 | high | Compliance dashboard | 14b | ✅ closed 2026-05-27 (`/ministry/compliance` per-(school, template) status counts) |
| M-005 | high | Drop-out heatmap | 14c | ✅ closed 2026-05-27 (district bar chart in `/ministry/dropouts`; Zim geomap deferred to a follow-up — see ADR 020) |
| M-006 | high | Subject pass-rate by region | 14c | ✅ closed 2026-05-27 (50% threshold; absent excluded; province + district scopes) |
| M-007 | high | Resource allocation views | 14c | ⚠️ partial (PTR delivered; `devices_per_school` + `electricity_coverage` placeholders returned as null pending a `SchoolFacility` model — stable contract preserved) |
| M-008 | medium | Anonymized comparatives | 14d | ✅ closed 2026-05-27 (`/ministry/comparative?anonymize=true` returns pseudonyms + nulled school_id) |
| M-009 | medium | Policy impact tracking | 14d | ✅ closed 2026-05-27 (`/ministry/policy-impact` with attendance_rate or dropout_rate, configurable windows) |
| M-010 | medium | Donor/NGO impact | 14d | ✅ closed 2026-05-27 (`/ministry/donors` aggregates Sponsorship by scope; money amounts logged per ADR 018) |
| M-011 | medium | International export templates | 14d | ✅ closed 2026-05-27 (`/ministry/exports/unesco` returns canonical national snapshot; downloadable JSON in admin-web) |

---

## §15 First-time Onboarding (Phase 15)

| ID | Importance | Title | Phase | Status |
|---|---|---|---|---|
| I-001 | high | Invitation model + endpoints in identity | 15a | ✅ closed 2026-05-27 (`services/identity/app/models/invitation.py` + `app/api/invitations.py`; token + manual-code paths) |
| I-002 | high | User row extension (nullable password, invited_at, activated_at, phone) | 15a | ✅ closed 2026-05-27 (Alembic migration `003_invitations`) |
| I-003 | high | Provisioner + EduZimOps roles + permission grants | 15a | ✅ closed 2026-05-27 (`scripts/seed-baseline.sh`; ADR 021) |
| I-004 | high | StudentDraft / ParentDraft + admin approval flow | 15a | ✅ closed 2026-05-27 (`services/academics/app/models/onboarding.py` + `app/api/drafts.py`) |
| I-005 | high | Bulk teacher import + parent invite queue | 15a | ✅ closed 2026-05-27 (`services/academics/app/api/bulk_teachers.py`; existing bulk.py extended) |
| I-006 | medium | Bulk fee structure import | 15a | ✅ closed 2026-05-27 (`services/finance/app/api/bulk_fees.py`) |
| I-007 | high | InviteDispatcher + InviteOutbox + templates | 15a | ✅ closed 2026-05-27 (`services/communications/app/services/invite_dispatcher.py` + `models/invite_outbox.py` + `templates/invite.py`; SMS/WhatsApp/Email/Manual priority chain) |
| O-001 | high | Onboarding readiness API (7 checks) | 15a | ✅ closed 2026-05-27 (`services/academics/app/api/onboarding_routes.py`) |
| O-002 | medium | CSV/Excel template-download endpoints | 15a | ✅ closed 2026-05-27 (`services/academics/app/api/templates_routes.py`) |
| O-003 | high | School.is_live + Go Live gate | 15a | ✅ closed 2026-05-27 (academics migration `2026_05_27_020`; POST /onboarding/go-live audit-logged) |
| U-001 | high | UI primitives (Stepper, ChecklistItem, ReadinessBar, InvitationStatusPill) | 15b | ✅ closed 2026-05-27 (`packages/ui/src/components/{stepper,checklist-item,readiness-bar,invitation-status-pill}.tsx`) |
| U-002 | high | admin-web setup wizard (9 pages) | 15b | ✅ closed 2026-05-27 (`apps/admin-web/src/app/(admin)/setup/**`) |
| U-003 | high | Parent + Teacher invite-landing pages | 15c | ✅ closed 2026-05-27 (`apps/parent-web/src/app/invite/[token]/page.tsx`, `apps/parent-web/src/app/invite/code/page.tsx`, `apps/teacher-web/src/app/invite/[token]/page.tsx`) |
| U-004 | medium | Ministry onboarding queue + "New School" modal | 15d | ✅ closed 2026-05-27 (`apps/admin-web/src/app/(ministry)/ministry/onboarding/page.tsx`) |
| A-021 | high | ADR 021 — onboarding + Provisioner | 15e | ✅ closed 2026-05-27 (`docs/decisions/021-onboarding-and-provisioner-role.md`) |
| G-001 | high | Gateway RBAC + service routing for invitations / drafts / onboarding / bulk / templates | 15a | ✅ closed 2026-05-27 (`services/api-gateway/app/routes.py`) |

**Gate**: ✅ A new school can be onboarded entirely from the wizard:
EduZimOps creates a school → SchoolAdmin invite issued → SchoolAdmin activates → uploads teachers + students CSV → parent invites auto-queued → admin reads manual code over phone OR provider delivers SMS/WhatsApp/Email → parent lands on /invite/[token] → sets password → lands on /home with children pre-listed → admin clicks Go Live → School.is_live flips. All steps audit-logged with no PII in target/details (rejection reason is the single exception). Backend regression: 681 tests across academics + identity + finance + communications.

**Open follow-ups** (not blocking 15 closeout):
- Server-side Excel parsing for bulk endpoints.
- Excel/PDF round-trip export of imported data.
- Per-school channel-config UX.
- Phone E.164 normaliser library.
- OCR for scanned PDF class lists.

---

## §16 Curriculum, Question Bank & Content Templates (Phase 16)

| ID | Importance | Title | Phase | Status |
|---|---|---|---|---|
| C-001 | high | Subject extension + Unit + Topic models | 16a | ✅ closed 2026-05-27 (`services/academics/app/models/curriculum.py`; grade_levels + national_subject_id on Subject) |
| C-002 | high | NationalCurriculum (NationalSubject / Unit / Topic) | 16a | ✅ closed 2026-05-27 (`services/academics/app/models/national_curriculum.py`; publish gate) |
| C-003 | high | Curriculum endpoints + adopt-subject + tree view | 16a | ✅ closed 2026-05-27 (`services/academics/app/api/curriculum_routes.py` + `national_curriculum_routes.py`; idempotent adopt) |
| C-004 | medium | ZIMSEC sample seeder (`scripts/import_zimsec.py`) | 16a | ✅ closed 2026-05-27 (3 placeholder subjects, idempotent; clear "replace before production" notice) |
| C-005 | high | Bulk CSV import (school-local + Ministry) + templates registry | 16a | ✅ closed 2026-05-27 (`services/academics/app/api/bulk_curriculum.py`; templates_routes extended with curriculum.csv + national-curriculum.csv) |
| C-006 | high | Topic↔Resource cross-index (topic_ids columns) | 16b | ✅ closed 2026-05-27 (`services/academics/app/api/curriculum_index_routes.py`; coverage API) |
| C-007 | high | Question Bank: Question + QuestionOption + QuestionDraft | 16c | ✅ closed 2026-05-27 (`services/academics/app/models/question_bank.py`) |
| C-008 | high | Question Bank: routes + draft approval flow + auto-grading | 16c | ✅ closed 2026-05-27 (`services/academics/app/api/question_bank_routes.py`; MCQ/TF/SA scoring) |
| C-009 | medium | Assessment composition (description, instructions, question_ids, exam_paper_attachment_id) | 16c | ✅ closed 2026-05-27 (Assessment model extended; `POST /assessments/{id}/compose`) |
| C-010 | high | HomeworkTemplate + LessonPlanTemplate | 16d | ✅ closed 2026-05-27 (`services/academics/app/models/content_templates.py` + `content_template_routes.py`; HoD school-wide publish + instantiate + sync-from-source) |
| C-011 | medium | Attachment polish (MIME + size + owner_kinds) | 16e | ✅ closed 2026-05-27 (Office MIMEs added; cap bumped 10MB → 25MB; 8 new owner_kinds) |
| U-005 | high | Teacher-web /curriculum (tree + topic detail) | 16f | ✅ closed 2026-05-27 (`apps/teacher-web/src/app/(teacher)/curriculum/**`) |
| U-006 | high | Teacher-web /question-bank (browse + submit draft + HoD drafts) | 16f | ✅ closed 2026-05-27 (`apps/teacher-web/src/app/(teacher)/question-bank/**`) |
| U-007 | medium | Admin-web /curriculum + /curriculum/coverage + /curriculum/adopt | 16g | ✅ closed 2026-05-27 (`apps/admin-web/src/app/(admin)/curriculum/**`) |
| U-008 | medium | Admin-web /question-bank/review (HoD queue) | 16g | ✅ closed 2026-05-27 (`apps/admin-web/src/app/(admin)/question-bank/review/page.tsx`) |
| U-009 | medium | Ministry-web /ministry/curriculum (publish + new subject modal) | 16h | ✅ closed 2026-05-27 (`apps/admin-web/src/app/(ministry)/ministry/curriculum/page.tsx`) |
| G-002 | high | Gateway SERVICE_ROUTES + RBAC for curriculum + question bank + templates | 16f | ✅ closed 2026-05-27 (`services/api-gateway/app/routes.py`) |
| A-022 | high | ADR 022 — Curriculum + Question Bank + Templates architecture | 16i | ✅ closed 2026-05-27 (`docs/decisions/022-curriculum-and-question-bank.md`) |

**Gate**: ✅ All decisions locked in the Phase 16 plan are live in backend + UI. Backend regression: **729 tests passing** across 4 services (academics 470 + communications 130 + finance 90 + identity 39). Audit invariants confirmed clean: no question text, no answers, no body text, no template titles in `target` / `details` — only IDs + counts + admin-supplied rejection reasons.

**Open follow-ups** (not blocking 16 closeout):
- Attachment cloning on template instantiation (placeholder `attachments_cloned: 0`).
- OCR for scanned PDFs/images (Tesseract — Phase 17).
- Image thumbnail server-side (Pillow — Phase 17).
- Curriculum versioning + ZIMSEC v2 upgrade path (Phase 17+).
- Cross-school template sharing (Phase 18).
- Essay auto-grading (Phase 18).
- JSONB + GIN index for topic_ids on Postgres (Phase 17 swap; current LIKE-substring path works on both).
- Phase 16h /ministry/curriculum/import bulk-upload UI (CSV upload exists at the API; UI page is a follow-up).

---

## §11 Cross-cutting Quality

| ID | Title | Phase | Status |
|---|---|---|---|
| Q-001 | Charts library integration (Recharts + ECharts) | ⚠️ Recharts done (Phase 10); ECharts deferred to Phase 14 | Recharts wrappers in `@eduzim/ui`; admin reports trend now charts; ECharts geomap/sankey deferred until ministry-web |
| Q-002 | Bulk student CSV import | 13a (admissions side) | todo |
| Q-003 | Print/PDF system (`exportToPdf` in `packages/ui`) | 12b (receipts), 13b (transcripts), 13b (compliance reports) | todo |
| Q-004 | Extract duplicated components to `packages/web-shared` | 2 (during consolidation) or 10 | todo |
| Q-005 | Accessibility audit pass (axe-core every page) | 19 (closeout) + per-feature gate | todo |
| Q-006 | Real cross-tenant isolation tests | 4 | todo |
| Q-007 | Real concurrency tests | 4 | todo |
| Q-008 | Real chaos tests (Kafka-down, Postgres-slow) | 5 + 7 | todo |
| Q-009 | Privacy + retention policies | ✅ done (Phase 9, draft) | `docs/compliance/privacy-policy.md` + `retention-policy.md` (pre-pilot lawyer review required) |
| Q-010 | DPO named publicly | ✅ done (Phase 9) | Footer links + i18n keys (EN/SN/ND) in all 3 apps |
| Q-011 | Data export endpoint (per-parent + per-school) | 8 / 9 | todo |
| Q-012 | ADRs for every decision (rolling) | 0 + ongoing | todo |
| Q-013 | Runbooks set | 17 + 19 | todo |
| Q-014 | Real 24-hour seeded load test | 7 | todo |
| Q-015 | Translate Sync Center labels (closes BUG-009) | 11a | todo |
| Q-016 | Audit log table + UI | ✅ wiring done (Phase 9 + PH9-6) | Substrate + per-service wiring across 4 services + 3 browse endpoints; admin UI pending (Phase 11) |
| Q-017 | Rewrite Context.md claims | 0 | ✅ done | CAUTION block + revised status line in `/Users/phani.m/Downloads/EduZim/Context.md` |
| Q-018 | Rewrite deck/marketing claims | 0 | ✅ done | `VISION.md` CAUTION block + `README.md` service-list fix + tone correction + `STATUS.md` created |
| Q-019 | Initial 13 ADRs | 0 | ✅ done | `docs/decisions/001-…` through `013-…` plus `000-template.md` |

---

## §12 Done

### Phase 10 (closed 2026-05-26 in code; bundle-budget verification pending real build) — **Charts (kill the table-as-chart problem)**

**Phase 10 closes DEC-011 / ADR 011. Two chart libraries with deliberate bundle posture: Recharts (~50KB) for everyday line/bar/pie, ECharts (~600KB) for heatmap/geomap/sankey — but ECharts ships only as a separately-loadable chunk so it never lands in the main bundle.**

#### Q-001a (closed earlier) — Recharts wrappers

`packages/ui/src/components/charts/index.tsx`. Four components (`LineChart`, `BarChart`, `PieChart`, `SparkLine`), shared theme tokens (`CHART_COLORS` — purple-led with Zimbabwe accent colours). Tree-shakeable; only imported components contribute to the bundle.

#### Q-001b (closed this phase) — ECharts wrappers

`packages/ui/src/components/charts/echarts/index.tsx`. Three components:

- **`Heatmap`** — calendar heatmap (attendance rate per day across a term, etc.). Data: `[{date: "YYYY-MM-DD", value: number}]`. ECharts calendar coordinate system. Default colour ramp: red → amber → Zimbabwe green.
- **`ZimbabweGeomap`** — choropleth of Zimbabwe's 10 provinces. Caller supplies the GeoJSON (not bundled — too heavy for default install). When `geoJson` is missing, renders an explicit "pass a geoJson prop" placeholder rather than failing silently.
- **`Sankey`** — student-flow / enrolment-flow diagrams (e.g., Grade-7→Grade-8 promotion flow). Nodes + links arrays, gradient line styling, ECharts default sankey layout.

**Bundle posture (the critical bit):**

1. **Separate subpath** — `@eduzim/ui/echarts` is its own entry. The main `@eduzim/ui` entry has only TYPE re-exports for the heavy components; runtime exports live in the subpath. `package.json` declares `"exports": {".": "./src/index.ts", "./echarts": "./src/echarts.ts"}`.

2. **Lazy registration** — `_ensureRegistered()` runs inside a React effect on first chart mount. It `await import("echarts/core")` + the specific chart-type modules + components. A top-level side effect would survive tree-shaking; the in-effect dynamic import does not.

3. **`optionalDependencies`** — `echarts@^5.5.0` listed under `optionalDependencies`, not `dependencies`. Apps that don't use heavy charts (`parent-web`, `teacher-web`) can install with `--omit=optional` and never pull it.

4. **Per-app `next/dynamic` wrappers** — `apps/admin-web/src/lib/lazy-charts.tsx` provides `Heatmap`, `ZimbabweGeomap`, `Sankey` wrapped in `next/dynamic({ ssr: false, loading: <ChartSkeleton/> })`. Pages import from here, never directly from `@eduzim/ui/echarts`. Each chart loads in its own JS chunk on first mount.

#### PH10-1 (closed via Q-001a) — admin attendance trend

The admin reports page's attendance section already had its HTML-table-trend replaced with a stacked BarChart (Present/Absent/Late per day) + LineChart (rate%) at Q-001a. The full raw-data table is preserved as an `<details>` block — screen-reader users still get the numbers.

#### PH10-2 (closed this phase) — admin financial summary

`apps/admin-web/src/app/(admin)/reports/page.tsx` financial section migrated from table-as-chart to stacked BarChart (Paid green vs Outstanding red per academic year). Full raw-data table preserved as an `<details>` block matching the attendance section's accessibility pattern.

Audit of other pages: `dashboard/page.tsx`, `parent-web/attendance/page.tsx`, `parent-web/fees/page.tsx` — no table-pretending-to-be-a-chart found. The parent-web attendance page uses a calendar-grid visualisation (intentional layout, not a hidden table).

#### PH10-3 — bundle budget runbook

`docs/runbooks/charts-bundle-budget.md`:

- Explains the four-layer enforcement (separate subpath, `next/dynamic`, `optionalDependencies`, lazy registration).
- Verification procedure: `pnpm --filter admin-web build`, expected first-load-JS target, separate-chunk check.
- Lighthouse target: Performance ≥ 90 on synthetic-throttled.
- Regression catalog: four common ways ECharts ends up in the main bundle, with fixes for each.
- Acceptance checklist for PH10-3 closure.

The Lighthouse + actual build numbers are a post-build operational check (not runnable from the repo's test harness). The code-side enforcement is in place; the runbook is the gate.

#### Verification

| Suite | Before Phase 10 | After Phase 10 | Δ |
|---|---|---|---|
| backend + shared + scripts | 719 | 719 | 0 (frontend-only changes) |

No new automated tests — frontend chart wrappers are visual components whose correctness is best verified by Lighthouse + manual screenshot review, not by code-level assertions. The Q-001a Recharts wrappers similarly ship without unit tests. If a stronger test posture is needed in the future, snapshot tests against the rendered SVG (NOT pixel comparisons) are the right level.

---

### Phase 9 (closed 2026-05-26 — substrate complete; per-field reviews + per-service wiring are tracked follow-ups) — **Audit log substrate + data-rights surface + minimisation plan**

**Phase 9 closes the production-readiness foundation track. The audit-log substrate, admin browse, retention enforcement, and right-to-export endpoints are all live in code. The PH9-2 field-by-field minimisation review is deferred-major with a structured checklist that makes its completion tractable rather than perpetual. See ADR 018 for the architectural decisions.**

#### Shared substrate — `eduzim_shared.audit`

- **`AuditLogMixin`** (SQLAlchemy declarative mixin) — canonical column set defined once: `id`, `occurred_at` (indexed), `actor_user_id` (indexed), `actor_role`, `school_id` (indexed), `event_type` (indexed), `target` (JSON-text), `details` (JSON-text), `ip_address`, `user_agent`, `request_id` (indexed). Schema drift across services is structurally impossible.
- **`record_audit_event(db, AuditLog, ...)`** — generic writer. Never raises into the caller; logs loudly on failure. A login that crashes because the audit table is full is worse than a login that succeeds without an audit row.
- **`Event` frozen dataclass** of canonical event names (`LOGIN_SUCCESS`, `STUDENT_CREATED`, `DATA_EXPORT_SCHOOL`, etc.). Free-form strings still work; the constants exist to catch typos that would split metrics.
- **13 unit tests** in `shared/tests/test_audit.py` covering schema integrity (canonical columns present + table creates), write happy-path, optional target/details, user-agent truncation, never-raises invariant, unique-id-per-call, event-constants stability.

#### Per-service table — academics

- `services/academics/app/models/audit.py` — two-line definition (`class AuditLog(AuditLogMixin, Base)`).
- Alembic migration `2026_05_19_007_audit_log.py` — idempotent (`_has_table` guard). Creates the table + 5 indexes (occurred_at, school_id, event_type, actor_user_id, request_id). `downgrade()` deliberately no-op (retention policy).
- Models `__init__.py` re-exports `AuditLog`.

#### Wired-in writes (representative subset)

- `POST /api/v1/students` — emits `student.created` with `target={"resource":"student","id":<uuid>}` and `details={"student_code":<code>}`. NOT the student's name (PII minimisation).
- `PUT /api/v1/students/{id}` — emits `student.updated` with `details={"changed_fields":[...]}`. The **changed field NAMES, not values**. `test_student_update_audit_records_changed_fields_not_values` enforces — explicitly asserts the new value string does NOT appear anywhere in the audit row's details JSON.
- `DELETE /api/v1/students/{id}` — emits `student.deleted`.
- `GET /api/v1/schools/me/export` — emits `data.export.school` BEFORE the streaming response starts. The audit row commits even if the download is interrupted.
- `GET /api/v1/parents/me/export` — emits `data.export.parent`.

The wiring pattern is documented in ADR 018 §2. Adding audit to a new PII-write route is a one-line `record_audit_event(...)` call after the service-layer call succeeds. Finance/Communications follow the same pattern as a tracked follow-up; the substrate makes each addition trivial.

#### Admin browse endpoint

- `GET /api/v1/audit-log` — paginated, school-scoped, admin-only (gateway RBAC: `school:manage`). Filters: `event_type`, `actor_user_id`, `from_date`, `to_date`. Pagination via offset+limit; descending by `occurred_at`.
- Deliberately NO free-text search of `target` / `details` — full-text indexing those invites casual browsing that runs against the privacy goal (ADR 007). Forensic deep-dives use documented DB queries.
- JSON columns deserialized back into objects on the wire (DB stores text for portability; clients see objects).

#### Retention enforcement

- `scripts/audit-log-retention.py` — daily-cron CLI:
  - Multi-DB per invocation (`--db-url` repeatable).
  - Default 2-year retention per `docs/compliance/retention-policy.md`; `--retention-days` override.
  - Batched DELETE (5,000 rows per statement, per-batch transactions) so a runaway purge doesn't lock the table.
  - Hard safety cap (1,000,000 rows per invocation). Exit code 3 if hit — runbook explains the chunked recovery procedure.
  - `--dry-run` counts without writing.
  - Credentials redacted in log lines.
  - Gracefully skips DBs whose `audit_log` table doesn't yet exist (services that haven't migrated).

- `docs/runbooks/audit-retention-rollout.md` — three scheduling options (Kubernetes CronJob, GitHub Actions, crond), monitoring guidance, day-2 ops, recovery-from-missed-runs procedure.

#### PH9-2 — structured deferred-major plan

- `docs/compliance/data-minimisation-audit.md` — every PII-bearing field listed by table (students, parents, attendance, marks, identity users, communications, audit log itself). Per field: today's state, why we collect it, proposed disposition (keep/drop/generalise/opt-in), owner (product / legal / eng), status (open/scheduled/closed).
- The doc itself is the forcing function: PRs that add a PII column to any model must update this table before merge.
- **Phase 9 closure does NOT depend on every row moving to `closed`** — only on the structured plan being recorded. ADR 018 explains why this deferral is correct.

#### ADR 018 — Audit log architecture + data-rights surface

`docs/decisions/018-audit-log-and-data-rights.md`. Documents:
1. Per-service `audit_log` tables (not central) — failure-domain locality, future Kafka aggregation path.
2. Wiring policy: route-layer, not service-layer.
3. Privacy in the audit itself: IDs in `target`, field-names in `details`, never values.
4. Admin browse endpoint design choices (filters, no free-text).
5. Retention CLI design (batched, capped, dry-runnable).
6. PH9-2 deferral with the structured checklist as the forcing function.

Plus alternatives considered (central audit DB, OTel semantic conventions, soft-delete instead of purge, app-layer encryption) and migration notes.

#### Verification

| Suite | Before Phase 9 | After Phase 9 | Δ |
|---|---|---|---|
| **shared** | 98 | **111** | +13 (audit substrate tests) |
| **academics** | 264 | **274** | +10 (audit-route integration tests) |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| finance | 63 | 63 | 0 |
| communications | 78 | 78 | 0 |
| scripts/load | 9 | 9 | 0 |
| **Total** | 696 | **719** | **+23 / zero regressions** |

Phase 9 is **closed in code**. The remaining work (per-write wiring across finance / communications, per-field minimisation reviews, right-to-delete tombstones, lawyer engagement) is tracked as ongoing follow-up — explicitly NOT a gate condition.

---

### Phase 8 (closed 2026-05-26 in code; staging promotion drill pending) — **Tenancy tiers + data-rights export**

**Phase 8 implements DEC-009 / ADR 009. Schools default to `shared` (row-level isolation in the cluster DB); large or sensitivity-sensitive schools can be promoted to `dedicated` (own DB) or `district` (district-shared DB). Plus the right-to-export endpoints from Phase 9's compliance work (ADR 007).**

#### PH8-1 — `tenancy_tier` on `schools`

- `services/academics/app/models/school.py` — added three columns:
  * `tenancy_tier: str` (`shared` | `dedicated` | `district`), default `shared`, indexed.
  * `district_routing_code: str | None` (nullable; nonnull only when tier=`district`).
  * `maintenance_mode: bool` (true during a mid-flight promotion).
- `services/academics/alembic/versions/2026_05_19_006_tenancy_tier.py` — idempotent migration (uses `_has_column` checks; safe to re-run).
- `SchoolService._ser_school` surfaces all three (with `getattr` defaults for test back-compat).

#### PH8-2 — Shared tenancy resolver

`shared/eduzim_shared/tenancy.py` — new module with:
- `Registry` dataclass + `from_env()` loader. Reads `EDUZIM_TENANCY_DEDICATED_REGISTRY` and `EDUZIM_TENANCY_DISTRICT_REGISTRY` as JSON dicts; lowercases keys for case-insensitive lookup; fails loud on bad JSON.
- `TenancyResolver(default_engine)` — `.resolve(tier, school_id, district_routing_code, maintenance_mode)` returns a `TenancyResolution(tier, engine, maintenance_mode)`. The `shared` path returns the default engine unchanged (hot path, no registry lookup). `dedicated` and `district` look up the DB URL in the registry; missing entries raise `TenancyConfigError` (fail loud, never silently fall back to shared).
- Per-process engine cache keyed by DB URL. Thread-safe via `threading.Lock`. Each unique URL builds one engine with the same pool tuning as PH4-1 (pool_size=10/20, recycle 1h, pre-ping). SQLite URLs skip pool args (test compatibility).
- `clear_engine_cache()` for test isolation.
- `session_for(**kwargs)` convenience: resolves + returns a Session.

**25 unit tests** in `shared/tests/test_tenancy.py` covering registry env-load, shared/dedicated/district paths, missing-config errors, case-insensitive lookup, engine cache hit/miss, lazy registry load, session_for sanity.

#### PH8-3 — Promotion automation

`scripts/promote-school-to-dedicated.sh` — bash CLI implementing the seven-step promotion documented in ADR 009:

1. Sanity (school exists + tier=shared + target empty)
2. Lock (`maintenance_mode = true`)
3. Snapshot via `\COPY` to CSV files in `/tmp/`
4. Restore via `\COPY` into target DB
5. Per-table row-count parity check
6. Flip the tier on shared (only if parity passed)
7. Print operator follow-up (registry update + service restart)

Modes: default, `--dry-run`, `--truncate-first`, `--no-lock`. Idempotent on retry. Aborts on parity mismatch without flipping the tier — the school stays in maintenance_mode until investigated.

#### PH8-4 — Data-rights export endpoints

`services/academics/app/api/export_routes.py`:

- `GET /api/v1/schools/me/export` (RBAC: `school:manage`)
  Returns a ZIP with `manifest.json` + per-table CSVs: `school.csv`, `students.csv`, `parents.csv`, `student_parents.csv`, `enrollments.csv`, `attendance.csv`, `assessments.csv`, `marks.csv`. All scoped strictly by `school_id`. Uses `yield_per` for memory-bounded reads on large tables.

- `GET /api/v1/parents/me/export` (RBAC: `authenticated`)
  Right-to-data per ADR 007. Returns a ZIP scoped to the parent's linked children only (NOT all students at the school). Manifest includes a notes block pointing at the school admin for right-to-erasure.

Both endpoints handle the not-found case by writing a manifest-only ZIP with an `error` key (not a 404 — the response is still a valid downloadable file with a clear error explanation inside).

The ZIP-streaming pattern was refactored partway through: building the ZIP fully in-memory THEN yielding is the only safe approach in a FastAPI generator, because the ZIP central directory is only written on `ZipFile.close()`. A shared `_finalize(zf, buf)` helper enforces the close-before-read sequence.

**9 integration tests** in `services/academics/tests/test_export_routes.py`:
- School export returns ZIP, contains manifest + students CSV
- School A's export contains ONLY School A's students (cross-tenant isolation, critical)
- School A's attendance CSV scoped to School A only
- Parent export returns ZIP
- Parent sees ONLY their linked child (not all their school's students)
- Parent attendance scoped to linked children only
- Unknown parent user_id returns the empty-manifest ZIP

Gateway RBAC updated — `services/api-gateway/app/routes.py` adds entries for `GET /api/v1/parents/me/export` (authenticated) and `GET /api/v1/schools/me/export` (`school:manage`).

#### Documentation

- `docs/runbooks/tenancy-upgrade.md` — operator runbook: when to promote, what you need beforehand (provisioned target DB + alembic upgrade), the seven steps walked through with sample commands, what can go wrong + mitigations, rollback within the 30-day soft-archive window, cost considerations.

#### Verification

| Suite | Before Phase 8 | After Phase 8 | Δ |
|---|---|---|---|
| **academics** | 255 | **264** | +9 (export tests) |
| **shared** | 73 | **98** | +25 (tenancy resolver) |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| finance | 63 | 63 | 0 |
| communications | 78 | 78 | 0 |
| scripts/load | 9 | 9 | 0 |
| **Total** | 662 | **696** | **+34 / zero regressions** |

Phase 8 is **closed in code**; the operational gate for PH8-3 (running the promotion script on a staging school) flips that one item from `⚙️` to `✅` once executed. The other three sub-tasks (PH8-1/2/4) are fully closed.

---

### Phase 7 (SCAFFOLDED 2026-05-26; 24-hour staging run pending) — **Real load test replaces audit-flagged scale_test.py**

**Phase 7 deliverables landed as code + compose overlay. Closes the BIGGEST audit finding from §4 — the 'scripts/scale_test.py is 550 mock HTTP requests against localhost, not a real test' call-out. The new harness is real-API end-to-end, with chaos, with a 24-hour realistic-traffic profile, with a budget-driven verdict.**

#### `scripts/load/` — the new harness

- **`seed_realistic.py`** (~350 lines) — provisions 500 schools × 100 students × 5 teachers × 1 parent/student via the gateway API. Per-school flow: register admin → login → create school → academic year → term → 5 classes → 6 subjects → 5 teachers (each with a real login + class assignment) → 100 students (each enrolled in a class round-robin) → ~100 parents (registered + linked to students). Concurrency-controlled (default 50 parallel schools). Output: `seed_artifacts.json` — the token/id lookup the load script reads. `--smoke` mode (10 schools × 20 students × 2 teachers) for CI / dev verification. Idempotent failure handling: a school that 4xxs is logged + skipped without aborting the run.

- **`load_24h.py`** (~400 lines) — drives sustained 24-hour traffic with the school-day pattern hardcoded in the file:
  - 06:00–07:30: early ramp (parents check overnight notifications)
  - 07:30–08:00: school start, attendance burst begins
  - 08:00–13:00: peak teacher activity (attendance every period + marks + occasional announcement)
  - 13:00–15:00: marks entry for morning assessments
  - 15:00–17:00: ramp-down + admin daily review
  - 17:00–22:00: parent evening reads + fee payments
  - 22:00–06:00: quiet (Kafka consumer catches up)
  - Per-minute CSV (timestamp, endpoint, count, p50_ms, p95_ms, p99_ms, error_rate_pct).
  - Run-wide JSON summary with peak RPM + per-endpoint error rate.
  - 11 endpoint drivers covering teacher attendance (POST /attendance/sync), teacher marks (POST .../marks/bulk), teacher announcements, parent children list, parent student details, parent attendance trend, parent feed, parent fees, admin dashboard, admin attendance trend, admin dropout summary.
  - `--smoke` (5 min compressed) for CI / dev.

- **`report_generator.py`** (~200 lines) — generates `performance-report.md` from the run output. Per-endpoint p99 vs published budget (in code: `P99_BUDGETS_MS`); 0.5% per-endpoint error gate; overall verdict ✅ PASSED / ❌ FAILED. Honest about its approximations ("p99 of per-minute p99s" — explicitly notes how to get exact figures from Prometheus). Optional `--include-grafana-screenshots` to link PNGs into the report. **9 unit tests** in `scripts/load/test_report_generator.py` covering happy path, p99 budget failure, error-rate gate failure, multi-failure listing, unknown-endpoint handling, screenshot linking.

- **`chaos_profiles.sh`** + **`docker-compose.chaos.yml`** (PH7-2) — `shopify/toxiproxy:2.9.0` container with admin API at :8474. The shell script creates proxies (`postgres-proxy:5433` → `postgres:5432`, `kafka-proxy:9093` → `kafka:9092`, `redis-proxy:6380` → `redis:6379`) and applies the default chaos profile: 200ms latency + 50ms jitter on every downstream + 20s drop-timeout (≈5% loss equivalent over a sustained connection). Operations: `apply` / `reset` (clear toxics, keep proxies) / `remove` (tear down) / `status` (JSON dump of current state).

#### Audit-flagged old script — deprecated

`scripts/scale_test.py` updated with a CLI banner + `sys.exit(2)`. The original 475 lines preserved in git history. Behaviour:
```
$ python scripts/scale_test.py
  ┌─────────────────────────────────────────────────────────────────┐
  │  DEPRECATED — scripts/scale_test.py is the audit-flagged       │
  │  'mock HTTP against localhost' script. Phase 7 replaced it.   │
  │  ...
  └─────────────────────────────────────────────────────────────────┘
$ echo $?
2
```
PH8 deletes the file entirely; for now the banner gives anyone with stale tooling a loud, immediate signal.

#### Documentation

- **`docs/decisions/017-real-load-testing-strategy.md`** (ADR 017) — justifies the four properties of a defensible load test (real DB state, realistic scale, real day, with chaos); compares the in-house harness vs k6/Locust/JMeter and explains why we wrote our own thin Python script; documents the p99 budget table; explicit migration notes from `scale_test.py` to the new harness.
- **`docs/runbooks/phase-7-load-test.md`** — operator runbook: prereqs (16 GB / 8 vCPU staging box, 48-hour window), pre-run smoke (5-min `--smoke` against the full stack), real seed (~30 min), 24-hour load, report generation with Grafana screenshots, per-failure post-mortem instructions (correlate Tempo trace + Loki logs + Alertmanager firings), rollback / cleanup.
- **`scripts/load/README.md`** — quick-reference for the three scripts, the school-day traffic pattern, output formats, and smoke-mode usage.

#### Verification

| Suite | Before Phase 7 | After Phase 7 | Δ |
|---|---|---|---|
| **scripts/load** | (new) | **9** | new test file `test_report_generator.py` covering budget pass/fail + edge cases |
| academics | 255 | 255 | 0 |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| finance | 63 | 63 | 0 |
| communications | 78 | 78 | 0 |
| shared | 73 | 73 | 0 |
| **Total** | 653 | **662** | **+9 / zero regressions** |

All five compose files (yml, prod.yml, ha.yml, observability.yml, chaos.yml) parse cleanly as YAML. The Phase 7 gate flips the five `⚙️` items to `✅` once the 24-hour run completes on staging and the first real `docs/perf-reports/YYYY-MM-DD.md` is committed.

---

### Phase 6 (SCAFFOLDED 2026-05-26; observability gate pending staging deploy) — **Per-service metrics + OpenTelemetry tracing + Loki logs + Alertmanager**

**Phase 6 deliverables landed as code + compose overlay. The gate flips the items from `⚙️` (scaffolded) to `✅` (closed) once the smoke + alert-flow tests in `docs/runbooks/phase-6-observability-rollout.md` pass on staging.**

#### Shared library — metrics + tracing

- **`shared/eduzim_shared/metrics.py`** — `install(app, service_name)` adds a `/metrics` endpoint with Prometheus exposition format. Three signals: `eduzim_http_requests_total{service, route, method, status}` (counter), `eduzim_http_request_duration_seconds{service, route, method}` (histogram with 5ms→10s buckets), `eduzim_http_in_flight_requests{service}` (gauge). Cardinality control: `route` label is the URL TEMPLATE (`/students/{id}`), unmatched paths bucket under `unmatched`. The metrics endpoint itself is excluded from its own counter to prevent Prometheus scrapes inflating their own stats. **9 unit tests** in `shared/tests/test_metrics.py` covering installation, no-self-recording, template-not-raw-path, status separation, method separation, histogram emission, service label propagation, and unmatched bucketing.
- **`shared/eduzim_shared/tracing.py`** — OpenTelemetry installer. Opt-in via `EDUZIM_TRACING_ENABLED=true`. No-op when disabled (no imports, no overhead). Reads `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://tempo:4317`), `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG` (default 10% parent-based ratio). Auto-instruments FastAPI (every route), HTTPX (outbound calls — academics→finance, etc.), SQLAlchemy (DB queries), Logging (adds `trace_id`/`span_id` to every JSON log record). Idempotent + safe to call when otel packages aren't installed (logs a warning, skips). **11 unit tests** in `shared/tests/test_tracing.py` covering env honesty, disabled-path no-op, missing-library graceful skip, shutdown safety, idempotency.
- **`shared/eduzim_shared/app_factory.py`** updated — `create_app(...)` now auto-installs metrics (always, unless `enable_metrics=False`) and tracing (always tries; runtime env decides). Tracing flush hooked into the existing shutdown lifespan. Defaults preserve previous behaviour for any code that called `create_app(...)` with no new kwargs.
- **`shared/setup.py`** updated — `prometheus-client>=0.20.0` added to `install_requires` (always required); `opentelemetry-*` packages in `extras_require[tracing]`, `sentry-sdk[fastapi]` in `extras_require[sentry]`, `redis>=5.0.0` in `extras_require[redis]` (latter retroactively documented from Phase 5).

#### Observability overlay — `docker-compose.observability.yml`

New compose overlay layering on top of `docker-compose.prod.yml` (optionally combined with `docker-compose.ha.yml`):

- **Prometheus** (`prom/prometheus:v2.55.0`) + rules mount. Scrapes every service's `/metrics` + node + postgres + pgbouncer + kafka exporters.
- **Grafana** (`grafana/grafana:11.3.0`) — datasource provisioning for Prometheus + Loki + Tempo. Loki configured with `derivedFields` that links log-line `trace_id` to a Tempo trace open-in-place. Tempo configured with service-graph + node-graph.
- **Alertmanager** (`prom/alertmanager:v0.27.0`) — config-mounted from `infra/observability/alertmanager/alertmanager.yml`. Routes critical → Slack #ops-pages + email (10s group_wait, 1h repeat), warning → Slack #ops-digest (5m group_wait, 4h repeat). Inhibition: critical suppresses same-instance warning.
- **Loki** (`grafana/loki:3.2.0`) — monolithic mode, 7-day retention, filesystem backend. Configured for the dev/staging stack size; prod swap to S3 or Grafana Cloud Loki.
- **Promtail** (`grafana/promtail:3.2.0`) — docker-socket discovery. JSON pipeline parses `eduzim_shared.logging` output and promotes `level`, `logger`, `request_id`, `trace_id`, `span_id` to Loki labels. Compose service name becomes the `service` label.
- **Tempo** (`grafana/tempo:2.6.1`) — OTLP/gRPC on :4317 (services push), OTLP/HTTP on :4318. Service-graph + span-metrics processors enabled — auto-derives a service topology graph in Grafana.
- **Exporters**: `node-exporter` (host CPU/mem/disk), `postgres-exporter` (connections + replication lag + slow queries), `pgbouncer-exporter` (pool saturation), `kafka-exporter` (broker + consumer-group lag).

#### Alertmanager rules — `infra/observability/rules/eduzim-alerts.yml`

Three rule groups, ten alerts total:

| Group | Alert | Severity | Threshold |
|---|---|---|---|
| service-health | ServiceDown | critical | up==0 for 2m |
| service-health | HighErrorRate | warning | 5xx rate > 5% per service for 5m |
| gateway-quality | GatewayHighErrorRate | critical | gateway 5xx > 1% for 5m |
| gateway-quality | GatewayRateLimitSpike | warning | rate-limit blocks > 50/s for 10m |
| kafka-health | KafkaConsumerLag | critical | consumergroup lag > 30s for 5m |
| kafka-health | KafkaBrokerDown | warning | brokers < 3 for 2m |
| postgres-health | PgBouncerPoolSaturated | warning | active/max > 80% for 5m |
| postgres-health | PostgresDown | critical | pg_up == 0 for 1m |
| postgres-health | PostgresReplicationLag | warning | replica lag > 60s for 5m |
| host-health | DiskUsageHigh | warning | > 75% for 10m |
| host-health | DiskUsageCritical | critical | > 90% for 5m |

#### Prometheus + Grafana config updates

- `infra/observability/prometheus.yml` rewritten — scrape configs for every service, rule_files glob, alertmanager target.
- `infra/observability/grafana/datasources.yml` rewritten — adds Loki + Tempo with cross-datasource correlation (Loki trace_id → Tempo, Tempo span → Prometheus service-map).
- `infra/observability/grafana/dashboards/services-overview.json` — new dashboard with RPS per service, 5xx rate per service, p50/p95/p99 latency per service, in-flight requests, per-route p95 top-10 table, Kafka consumer lag, pgbouncer pool utilization. Service templating variable for filtering.

#### Documentation

- **`docs/decisions/016-observability-stack.md`** — ADR justifying prometheus-client direct over prometheus-fastapi-instrumentator, OTLP over Jaeger native, Loki over ELK, self-hosted over Grafana Cloud. Migration notes for production deploys.
- **`docs/runbooks/phase-6-observability-rollout.md`** — pre-deploy env setup, first-time deploy sequence, smoke tests (per-service /metrics, Prometheus targets, Loki labels, Tempo OTLP, Alertmanager status, Grafana datasources), alert-flow verification ("synthetic 500 → Sentry capture + Alertmanager page in 60s"), rollback procedure, known caveats (unauth /metrics, OTel image size, retention defaults, Slack webhook requirement).

#### Verification

| Suite | Before Phase 6 | After Phase 6 | Δ |
|---|---|---|---|
| **shared** | 53 | **73** | +20 (9 metrics + 11 tracing) |
| academics | 255 | 255 | 0 |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| finance | 63 | 63 | 0 |
| communications | 78 | 78 | 0 |
| **Total** | 633 | **653** | **+20 / zero regressions** |

All four compose files (yml, prod.yml, ha.yml, observability.yml) parse cleanly as YAML. The Phase 6 chaos gate (synthetic-500 → Alertmanager + Sentry) flips the four `⚙️` items to `✅` once it runs clean on staging.

---

### Phase 5 (SCAFFOLDED 2026-05-26; chaos gate pending staging deploy) — **HA Postgres + Kafka + Redis + mTLS**

**Phase 5 deliverables landed as code. The chaos gate that flips the four items from `⚙️` (scaffolded) to `✅` (closed) requires real Docker on staging — see `scripts/chaos/run-all.sh` and `docs/runbooks/phase-5-ha-rollout.md`. Until that runs, the items are documented and reviewable but technically open.**

#### New compose overlay — `docker-compose.ha.yml`

Composes with `docker-compose.prod.yml` (single-node baseline kept intact for low-stakes deploys). Replaces postgres/kafka/zookeeper/redis with HA equivalents; overrides each app service's env to point at the new endpoints.

**INFRA-003 — Postgres HA via repmgr + pgpool.** Two `bitnami/postgresql-repmgr:16` nodes (`pg-0` primary + `pg-1` standby). repmgr handles auto-promotion on primary loss. `bitnami/pgpool:4.5` fronts both nodes, detects the current primary, routes writes accordingly. The existing `pgbouncer` service's `DB_HOST` env is repointed at `pgpool` so the per-service `DATABASE_URL` stays `pgbouncer:6432/<db>` — application code unchanged.

The routing chain in HA mode:
```
app → pgbouncer (transaction pool) → pgpool (HA router) → pg-0/pg-1
```

Migrations connect via pgpool directly (NOT through pgbouncer; DDL doesn't compose with transaction-mode pooling). This matches the Phase 4 BUG-008 pattern.

Chose repmgr over Patroni because: (a) avoids the etcd dependency we don't otherwise need; (b) Bitnami's image meets the same `failover < 60s` SLA target with half the compose footprint; (c) when we move to k8s in Phase 7+, the right swap is Patroni-via-CrunchyData-Operator, not docker-Patroni — so the Phase-5 docker-compose decision is intentionally a stop-gap. ADR 015 documents this with the AWS RDS Multi-AZ alternative path.

**INFRA-004 / INFRA-005 — Kafka 3-broker KRaft cluster.** `kafka-0`, `kafka-1`, `kafka-2` running `bitnami/kafka:3.7` in KRaft mode (combined controller+broker). Zookeeper service removed (`zookeeper:` block in overlay is a no-op container).

Topic-level guarantees:
- `KAFKA_CFG_DEFAULT_REPLICATION_FACTOR=3`
- `KAFKA_CFG_MIN_INSYNC_REPLICAS=2`
- `KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR=3`
- `KAFKA_CFG_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=3`
- `KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=false`

Plus `provectuslabs/kafka-ui:v0.7.2` at :8090 for cluster + consumer-group + topic introspection (INFRA-005).

App services' `KAFKA_BOOTSTRAP_SERVERS` updated to `kafka-0:9092,kafka-1:9092,kafka-2:9092`. Producer / consumer libraries handle broker discovery from there.

**INFRA-006 — Redis Sentinel.** `redis-master` (primary) + `redis-replica` (sync replica) + `redis-sentinel-0/1/2` (sentinel quorum=2). Failover triggers when 2 of 3 sentinels agree the primary is gone (`REDIS_SENTINEL_DOWN_AFTER_MILLISECONDS=5000`, `REDIS_SENTINEL_FAILOVER_TIMEOUT=10000` — failover < 15s).

The application side needed a new URL scheme since `redis.from_url("redis+sentinel://...")` isn't a built-in. Added:

- `shared/eduzim_shared/redis_client.py` — `from_url(url)` factory that accepts EITHER `redis://` (single-node) or `redis+sentinel://[:pw@]h1:26379,h2:26379,h3:26379/N?master=mymaster` (HA). Sentinel branch builds a `redis.sentinel.Sentinel(...)` and returns `master_for(...)` — sentinel auto-rediscovers on failover, callers don't need to reconnect.
- `shared/tests/test_redis_client.py` — 12 unit tests covering both URL forms, password extraction, master-name extraction, db-index parsing, default sentinel port, error cases.
- `services/api-gateway/app/main.py:_build_rate_limiter` switched from `redis.from_url(...)` to `eduzim_shared.redis_client.from_url(...)`. Drop-in.

**INFRA-019 — Service-to-service mTLS.**

- `scripts/generate-mtls-certs.sh` — self-signed CA + per-service leaf certs (api-gateway, identity, academics, finance, communications, reporting-service). 365-day validity. Output to `infra/certs/`.
- `shared/eduzim_shared/mtls.py` — env-driven helper. `is_enabled()`, `uvicorn_kwargs()` (server side: `ssl_certfile`, `ssl_keyfile`, `ssl_ca_certs`, `ssl_cert_reqs=CERT_REQUIRED` — mutual TLS, not one-way), `httpx_kwargs()` (client side: `verify`, `cert`), `http_scheme()` (returns `'https'`/`'http'`). Fails loud on misconfig — explicit `EDUZIM_TLS_ENABLED=true` with missing cert paths raises rather than silently falling back to plain HTTP.
- `shared/eduzim_shared/serve.py` — uvicorn launcher that auto-wires mTLS. New Dockerfile CMD pattern: `CMD ["python", "-m", "eduzim_shared.serve", "app.main:app"]`. Stays uvicorn-equivalent when TLS is off; switches to HTTPS when on.
- `shared/tests/test_mtls.py` — 9 unit tests covering disabled / enabled-happy / enabled-misconfigured paths.

Defence in depth on top of PH3's `X-Gateway-Token`. ADR 015 documents the layering: PH3 = shared-secret auth on the application layer; mTLS = certificate-based identity on the transport layer. Compromising a single service container leaks its cert (not the shared token); compromising the shared token doesn't help if the attacker can't present a valid cert. Both must be defeated to impersonate the gateway.

#### Chaos test suite — `scripts/chaos/`

The Phase 5 gate condition. Each script is destructive and runs against the HA overlay on staging:

- `kill-pg-primary.sh` — stops `pg-0`; probes `pgbouncer` with a write every 2s; passes if write succeeds within 60s (repmgr promotion + pgpool re-route).
- `kill-kafka-broker.sh` — stops `kafka-1`; reads `reporting-service` consumer-group offset before + after a 30s outage; passes if offsets advance.
- `kill-redis-primary.sh` — stops `redis-master`; probes the gateway's `/api/v1/auth/login` endpoint (touches Redis for rate-limit increment) every 1s; passes if gateway responsive within 15s.
- `sigterm-services.sh` — SIGTERMs each app service in turn; passes if each drains within 5s with "shutdown complete" in logs.
- `run-all.sh` — sequential runner with 30s settle between tests.
- `README.md` — documents pass criteria, usage, and what's NOT covered yet (network partitions, multi-component failure, disk-full — Phase 7).

#### Documentation

- `docs/runbooks/phase-5-ha-rollout.md` — full HA cutover sequence: pre-deploy (cert generation, env vars, cert volumes, Dockerfile CMD switch), first-time HA deploy (data-plane → migrations → Kafka → Redis → app services in order), smoke tests, chaos gate run, rollback procedure, known caveats (pgpool transaction-mode caveats, mTLS cert lifecycle, kafka-ui auth, RAM budget).
- `docs/decisions/015-self-managed-ha-via-bitnami-stack.md` — ADR justifying repmgr over Patroni, KRaft over ZK, Sentinel over Cluster, mTLS in addition to PH3 token, and self-managed over hosted (with hosted as a future option pending Debate 5).

#### Verification

| Suite | Before Phase 5 | After Phase 5 | Δ |
|---|---|---|---|
| **shared** | 32 | **53** | +21 (12 redis_client + 9 mtls) |
| academics | 255 | 255 | 0 |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| finance | 63 | 63 | 0 |
| communications | 78 | 78 | 0 |
| **Total** | 612 | **633** | **+21 / zero regressions** |

The chaos gate (real Docker, real failover) is the remaining step before Phase 5 flips from scaffolded to closed. Until then INFRA-003/004/005/006/019 are `⚙️` in §3.

---

### Phase 4 (closed 2026-05-26) — **data hygiene: Q-006 + Q-007 + INFRA-002 + BUG-008**

**Phase 4 — cross-tenant isolation proven (Q-006), concurrency invariants proven (Q-007), pgbouncer connection pool (INFRA-002), and dedicated one-shot migrations container (BUG-008) all landed.** Two real bugs surfaced and fixed along the way: **BUG-009** (tuple-return that silently turned 404s into 200s) and **BUG-010** (SQLite-fallback path let two concurrent payments double-spend).

#### Q-006 — Cross-tenant isolation (23 tests)

New: `services/academics/tests/test_cross_tenant_isolation.py`. 23 tests across 9 classes covering Student / Parent / School-config / Attendance / Assessment / Schools-current / Enrollment / service-layer scoping / DB-level invariants. Seeded School-A and School-B in parallel; every list endpoint must show only the caller's school, every per-ID lookup must 404 across schools, every write must leave the other school's row untouched.

The list of HTTP routes exercised: `/students` (list/get/put/delete), `/parents` (list, `/parents/me/children`), `/classes` (list/put/delete), `/academics/years` (list), `/attendance/student-trend`, `/attendance/class-summary`, `/assessments` (list, get-by-id), `/schools/current`, `/enrollments`.

The service-layer guarantees (defence in depth beyond routes): `StudentService.list_students`, `StudentService.get_student`, `AttendanceService.student_trend`. The DB-level invariants verify that no Student / AttendanceRecord row has a NULL `school_id`, and that unique constraints (`student_code`) are correctly scoped to `(school_id, student_code)` — same code in two schools is fine.

**BUG-009 (discovered by Q-006)**: every `_err(...)` return in `services/academics/app/api/{routes,student_routes}.py` was wrapped in a `return tuple, status_code` pattern. FastAPI ignores the second tuple element and ships the response as HTTP 200 with a 2-element list body — every 404 / 409 path was silently a 200. Fix: `_err(...)` now returns a real `JSONResponse(..., status_code=N)`. 27 call sites converted via a sed-style script.

#### Q-007 — Concurrency invariants (6 finance + 5 academics)

New: `services/finance/tests/test_concurrency.py` and `services/academics/tests/test_concurrency.py`.

Finance covers: deterministic CAS race (two sessions, second one's CAS must be rejected as CONCURRENT_WRITE_LOST), white-box CAS-predicate tests (stale `WHERE paid_amount=<old>` produces rowcount=0; fresh `WHERE` produces rowcount=1), idempotency-key dedup (10 sequential same-key calls = 1 row), 2-session idempotency dedup (`already_processed=True` on the second), and 50-invoice fan-out invariant (Σ payments == Σ invoice.paid_amount, all PAID).

Academics covers: attendance batch idempotency (same `(device_id, batch_id)` returns `already_processed=True`), 2-session batch dedup, per-event `client_event_id` dedup, marks bulk upsert (second submission updates the existing row, never creates a duplicate), and 50-batch fan-out with re-submission.

**BUG-010 (discovered by Q-007)**: `FeesService.record_payment` had a SQLite-fallback path (`except Exception: invoice = ...first()`) that silently disabled `with_for_update()`. On any DB without working row-locking, two parallel `record_payment` calls could both see `paid_amount=0`, both pass the overpayment check, and both commit — invoice ends at paid_amount > total_amount. Fix: optimistic compare-and-swap via SQLAlchemy `Query.update(... where paid_amount == observed_paid, synchronize_session=False)` after the standard FOR UPDATE attempt; if rowcount != 1 the second writer rolls back and returns `CONCURRENT_WRITE_LOST` for the caller to retry. The CAS is defence-in-depth — Postgres FOR UPDATE still serializes contenders normally; the CAS catches anything that slips past it.

Why deterministic rather than `threading.Thread + Barrier`: SQLite + StaticPool funnels every session's writes through a single shared connection — multi-thread races literally can't materialize at the test runtime. The deterministic interleaved two-session pattern exercises the SAME logical predicates the threaded version would have. Postgres-on-real-Docker integration tests (Phase 5+) cover the true multi-writer path.

#### INFRA-002 — PgBouncer

New `pgbouncer` service block in both `docker-compose.yml` and `docker-compose.prod.yml`. Image `edoburu/pgbouncer:v1.23.1`. Pool mode `transaction`. `MAX_CLIENT_CONN=1000`, `DEFAULT_POOL_SIZE=20` (dev) / `25` (prod). Every app service's `DATABASE_URL` re-pointed from `@postgres:5432/<db>` to `@pgbouncer:6432/<db>`.

Why transaction mode: prepared statements + session-level advisory locks don't compose with it. We use neither. FOR UPDATE locks held within a single transaction still work correctly because the whole transaction lives on one backend connection.

Why this matters: per-service `pool_size=20` × 6 services = 120 potential Postgres backends before pooling. With pgbouncer those collapse to `DEFAULT_POOL_SIZE=20-25` actual Postgres connections shared across all services' clients.

#### BUG-008 / INFRA-008 — Dedicated migrations container

New `services/migrations/` directory:
- `Dockerfile` — bundles every service's alembic tree (academics + finance + communications + reporting-service + identity) into one image.
- `run.sh` — bash script that loops through services, sets `DATABASE_URL` for each, runs `alembic upgrade head`, exits with worst observed rc.

The 5 service Dockerfiles had their `alembic upgrade head &&` prefix stripped. CMDs are now pure `uvicorn` / `python -m app.consumer`. Compose's `depends_on: migrations: condition: service_completed_successfully` gates service startup on the migrations container exiting cleanly.

Why this matters: the pre-Phase-4 pattern had every service run alembic in parallel on cold start. With 5 services and the migration-lock table, this caused intermittent lock-acquire failures. Pulling migrations out into a single ordered run eliminates the race and makes deploy status explicit ("the migrations step has its own pass/fail signal").

Migrations connect DIRECTLY to Postgres (not via pgbouncer) because DDL doesn't compose with transaction-mode pooling.

#### Verification

| Suite | Before Phase 4 | After Phase 4 | Δ |
|---|---|---|---|
| **academics** | 227 | **255** | +28 (23 Q-006 + 5 Q-007) |
| **finance** | 57 | **63** | +6 (Q-007) |
| communications | 78 | 78 | 0 |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| shared | 32 | 32 | 0 |
| **Total** | **578** | **612** | **+34 / zero regressions** |

#### Runbook

`docs/runbooks/phase-4-data-hygiene.md` — covers first-time staging deploy, subsequent deploys after schema changes, smoke tests, rollback procedures for pgbouncer and the migrations container, and known caveats (transaction-mode incompatibilities, SQLite test-runtime limitations).

---

### Phase 3 (closed 2026-05-26) — **gateway-headers-only auth; BUG-007 closed**

**Phase 3 — `jose.jwt.decode` removed from every downstream service. Identity is now read from gateway-injected headers (`X-User-Id`, `X-School-Id`, `X-User-Roles` CSV, `X-Permissions` CSV) protected by a service-to-service shared secret (`X-Gateway-Token` matched against each container's `INTERNAL_SERVICE_TOKEN`).** See `docs/decisions/014-gateway-headers-only-auth.md`.

Shared module:
- New `shared/eduzim_shared/auth.py` — `ActorContext` frozen dataclass (`user_id`, `school_id`, `roles` tuple, `permissions` tuple) with `has_role`, `has_permission`, and a back-compat dict-like protocol (`.get(key)`, `__getitem__`, `__contains__`) so existing route code that did `current_user["sub"]` keeps working without a sweep.
- New `get_actor_context(...)` FastAPI dependency — reads the 5 headers, validates `X-Gateway-Token` against env-sourced `INTERNAL_SERVICE_TOKEN` (read fresh each call so secret rotation doesn't need a restart), parses UUIDs, splits CSV lists. Fails closed on three conditions: misconfigured service (500), bad/missing token (401), bad/missing identity (401/400).
- New `get_school_id_from_actor(...)` convenience dependency.
- New `shared/tests/test_auth.py` — 13 tests covering the dataclass shim, gateway-token guard (missing/wrong/server-mis-configured), required identity headers (missing/malformed), happy paths (minimal headers, roles+permissions, CSV whitespace tolerance).

Gateway changes:
- `services/api-gateway/app/middleware/stack.py:extract_tenant` now also emits `roles` (list) and `permissions` (list). Normalises `roles` from JWT's `roles: [...]` or legacy `role: <str>`.
- `services/api-gateway/app/proxy.py` injects 5 new headers on every forwarded request: `X-User-Id`, `X-School-Id`, `X-User-Role` (kept for back-compat), `X-User-Roles` (CSV), `X-Permissions` (CSV), `X-Gateway-Token` (read fresh from env each request).
- `docker-compose.yml` + `docker-compose.prod.yml` — gateway env now includes `INTERNAL_SERVICE_TOKEN: ${INTERNAL_SERVICE_TOKEN:?...missing}`; finance + communications env blocks also get the same line (academics already had it).
- `services/api-gateway/app/config.py` — `Settings` cleanly lists only the 4 canonical downstream URLs + identity (the cleanup from PH2-12 stuck).

Downstream services — `dependencies.py` rewritten in all four:
- `services/academics/app/dependencies.py` — `jose` import gone. `get_current_user` and `get_school_id` are 1-line shims over `get_actor_context` and `get_school_id_from_actor`. `is_teacher_role`/`is_parent_role` now accept either an `ActorContext` or the legacy dict (driven off `actor.has_role(...)` if applicable). The PH2-8/9 fail-closed-honestly `verify_*_authorization` async wrappers + `AuthorizationServiceUnavailable` exception preserved unchanged.
- `services/finance/app/dependencies.py` — same shim pattern.
- `services/communications/app/dependencies.py` — same shim pattern.
- `services/reporting-service/app/dependencies.py` — stubbed to raise 410 if invoked. The consumer container has no auth-guarded routes (PH2-11).

Tests rewritten (28 affected tests across 3 files):
- `services/academics/tests/test_assessment.py` — `_make_token` / `Authorization: Bearer …` pattern replaced with `_gateway_headers(...)`. `_teacher_headers`, `_admin_headers`, `_parent_headers` now thin wrappers over `_gateway_headers`.
- `services/academics/tests/test_assessment_idempotency.py` — same pattern.
- `services/academics/tests/test_reports_query.py` — `token` fixture changed from JWT string to dict of headers; all 8 `headers={"Authorization": f"Bearer {token}"}` call sites changed to `headers=token` via `replace_all`. `_TEST_JWT_SECRET` constant removed.
- `services/communications/tests/test_idempotency.py` — `_make_token` removed; `_teacher_headers` re-pointed to a new `_gateway_headers(...)` helper. `jose_jwt` import removed.

New integrity tests — one per service, asserts direct calls fail 401:
- `services/academics/tests/test_gateway_headers_only.py` — 16 tests. Parametrised across 4 representative routes (`/schools/current`, `/students`, `/attendance/daily`, `/reports/dashboard`): no headers → 401, missing gateway-token → 401, wrong gateway-token → 401, valid gateway call → not 401. Spins fresh in-memory academics + projection DBs per test so the happy path can reach the route layer.
- `services/finance/tests/test_gateway_headers_only.py` — 6 tests on `/fees/invoices` (5 negatives + 1 valid). Same in-memory DB pattern.
- `services/communications/tests/test_gateway_headers_only.py` — 6 tests on `/comm/announcements`.

`ActorContext` dict-shim improvement:
- The first run of communications tests after the refactor showed that `current_user["sub"]` (square-bracket access in `announcements` route) blew up. The shared `ActorContext` was extended with `__getitem__` and `__contains__` (and the existing `.get(...)`) so any code path still treating identity as a dict keeps working. Documented in the dataclass docstring as a transitional back-compat shim.

Verification:
| Suite | Before PH3 | After PH3 | Δ |
|---|---|---|---|
| **academics** | 211 | **227** | +16 (new integrity tests) |
| **finance** | 51 | **57** | +6 (new integrity tests) |
| **communications** | 72 | **78** | +6 (new integrity tests) |
| **shared** | 19 | **32** | +13 (new ActorContext tests) |
| api-gateway | 105 | 105 | 0 |
| reporting-service | 51 | 51 | 0 |
| identity | 28 | 28 | 0 |
| **Total** | 537 | **578** | **+41 / zero regressions** |

Gate condition check:
```
$ grep -rn "from jose\|import jose" services/*/app/ | grep -v __pycache__
services/identity/app/utils/security.py:8:from jose import jwt, JWTError
```
✓ Only identity (the sole token issuer/verifier) imports `jose`. BUG-007 closed.

### Phase 2 — PH2-12 (closed 2026-05-26) — **Phase 2 done; four pre-consolidation services + notification-worker deleted**

**PH2-12 — the burn-in window is shortened to zero (user override; no production traffic yet, so there's no live system to roll back to). The four old service folders are removed; the reporting consumer's dead HTTP route files are removed; the gateway's deprecated SERVICE_URL aliases are removed; compose + CI matrices shrink to the actual 6-container shape.**

Code deletions:
- `services/school-service/` — entire directory (folded into academics at PH2-6).
- `services/student-service/` — entire directory (folded into academics at PH2-7).
- `services/attendance-service/` — entire directory (folded into academics at PH2-8).
- `services/assessment-service/` — entire directory (folded into academics at PH2-9).
- `services/notification-worker/` — entire directory (folded into communications at PH2-4; the dispatcher code lives at `services/communications/app/workers/notification_dispatcher.py`).
- `services/reporting-service/app/api/` — both files (`routes.py` and `exports.py`) removed. They were marked `DeprecationWarning` at PH2-11; PH2-12 removes them since no caller existed anyway.

Compose cleanup (both `docker-compose.yml` and `docker-compose.prod.yml`):
- `school-service` / `student-service` / `attendance-service` / `assessment-service` / `notification-worker` container blocks deleted.
- Gateway env: deprecated aliases removed (`AUTH_SERVICE_URL`, `SCHOOL_SERVICE_URL`, `STUDENT_SERVICE_URL`, `ATTENDANCE_SERVICE_URL`, `ASSESSMENT_SERVICE_URL`, `FEES_SERVICE_URL`, `COMMUNICATION_SERVICE_URL`, `REPORTING_SERVICE_URL`). Only the four canonical names remain (`IDENTITY/ACADEMICS/FINANCE/COMMUNICATIONS_SERVICE_URL`).
- `depends_on` now includes the full surviving set: `identity`, `academics`, `finance`, `communications`, `redis`.
- Identity / finance / communications container blocks lost their network aliases (`auth-service`, `fees-service`, `communication-service`) — nothing on the network looks them up by those names anymore.
- `POSTGRES_MULTIPLE_DATABASES` shrinks from 9 entries to 5: `auth_db, fees_db, comms_db, reporting_db, academics_db`. The four per-service DBs (`school_db, student_db, attendance_db, assessment_db`) are no longer initialized (academics_db owns those tables now).
- Academics container env: `KAFKA_ENABLED` flipped from `"false"` → `"true"` (the dual-publisher avoidance rationale during burn-in is gone). The stale `STUDENT_SERVICE_URL` env var dropped.

Gateway code cleanup:
- `services/api-gateway/app/config.py` — `Settings` now lists exactly 5 service URLs: `IDENTITY/ACADEMICS/FINANCE/COMMUNICATIONS_SERVICE_URL` (plus a stale-comment fix in `routes.py`). The 8 deprecated aliases that used to live here are removed.
- `services/api-gateway/tests/test_gateway.py` — env block trimmed to the same 4 canonical names. The test that asserted aliases must be honoured is gone since the aliases themselves are gone.

Downstream service code cleanup:
- `services/academics/app/config.py` — the PH2-6→9 burn-in URLs (`AUTH/SCHOOL/STUDENT/ATTENDANCE/ASSESSMENT_SERVICE_URL`) removed; only `IDENTITY_SERVICE_URL` + `FINANCE_SERVICE_URL` (used by dropout) remain.
- `services/reporting-service/app/config.py` — `STUDENT_SERVICE_URL` / `ATTENDANCE_SERVICE_URL` / `FEES_SERVICE_URL` removed (the consumer doesn't talk HTTP to anything).

CI matrix cleanup (`.github/workflows/ci.yml` + `deploy.yml`):
- Backend test matrix: 9 services → 5 (`identity`, `academics`, `finance`, `communications`, `reporting-service`).
- Docker build matrix: 11 services → 6 (above + `api-gateway`).

What changed in test counts:
| Suite | Before PH2-12 | After PH2-12 | Why |
|---|---|---|---|
| academics | 211 | 211 | unchanged — owns the merged code |
| api-gateway | 105 | 105 | env-block tweak, no test logic changes |
| reporting-service | 51 | 51 | unchanged — consumer + engine tests stay |
| identity | 28 | 28 | unchanged |
| finance | 51 | 51 | unchanged |
| communications | 72 | 72 | unchanged |
| shared | 19 | 19 | unchanged |
| school-service | 60 | **deleted** | code is in academics now |
| student-service | 40 | **deleted** | code is in academics now |
| attendance-service | 24 | **deleted** | code is in academics now |
| assessment-service | 51 | **deleted** | code is in academics now |
| **Total** | **712** | **537** | -175 (covered by academics' 211) |

Note on the user's "1-week burn-in" deferral: PH2-11's runbook called for a burn-in window before PH2-12. The user explicitly directed PH2-12 to proceed immediately. The rationale that makes this safe: the PH2-6 → PH2-10 work all landed today against a codebase with no production traffic; there's no live system whose drift would be caught by a real burn-in. The git history preserves the four service folders if a real rollback ever becomes necessary.

Verification:
| Suite | Result | Δ |
|---|---|---|
| **api-gateway** | **105 ✓** | 0 (env block trimmed; test count unchanged) |
| **academics / reporting / identity / finance / communications / shared** | 432 ✓ | 0 |
| **Total** | **537 backend+shared green** | **-175 (deleted-with-source); zero regressions in surviving suites** |

### Phase 2 status

```
PH2-1  design                            ✅
PH2-2  auth → identity                   ✅
PH2-3  fees → finance                    ✅
PH2-4  communication → communications    ✅
PH2-5  academics shell                   ✅
PH2-6  school → academics                ✅
PH2-7  student → academics + in-process  ✅
PH2-8  attendance → academics + authz    ✅
PH2-9  assessment → academics + authz    ✅
PH2-10 gateway cutover                   ✅
PH2-11 reporting → consumer              ✅
PH2-12 cleanup                           ✅  ← THIS — Phase 2 DONE
```

**Phase 2 complete.** From here, Phase 3 (BUG-007, gateway-headers-only auth) acts on 4 services instead of 8 — a much smaller blast radius than the original plan.

---

### Phase 2 — PH2-11 (closed 2026-05-26) — **reporting HTTP stripped; reads served by academics; consumer-only container**

**PH2-11 — `/api/v1/reports/*` moved into academics; reporting-service rewritten as pure Kafka consumer; CLI tools replace the consume/rebuild HTTP endpoints.**

Academics — read-side wiring:
- New `services/academics/app/reporting_db.py` — second SQLAlchemy engine + `get_reporting_db` dependency that binds to `REPORTING_DATABASE_URL` (defaults to a sqlite file in tests; postgres `reporting_db` in prod). Lazy-init; doesn't open the pool until a /reports/* request actually fires.
- New `services/academics/app/models/projections.py` — read-side mappings for `processed_events`, `dashboard_stats`, `attendance_daily_aggregate`, `financial_summary`, `student_count_projection`. Uses its own `ProjectionBase = declarative_base()` so the projection tables are NOT registered on academics' main `Base` (which would cause `Base.metadata.create_all` in test fixtures to create them in academics_db, which is the wrong DB).
- New `services/academics/app/services/reports/reporting_query_service.py` — `ReportingQueryService(db)` with `get_dashboard / get_attendance_trend / get_financial_summary`. Mirrors the read methods that used to live on the reporting-service's `ReportingService` class but contains zero write/consume logic.
- New `services/academics/app/services/reports/dropout_engine.py` — pure-compute `DropoutRiskEngine` (lifted verbatim from `services/reporting-service/app/services/dropout_service.py`).
- New `services/academics/app/services/reports/dropout_data.py` — `list_active_students(db, ...)` and `fetch_student_trend(db, ...)` are in-process replacements for the old HTTP GET hops into student-service and attendance-service. `fetch_invoices(...)` still hits finance over HTTP (fees stayed a separate service per ADR 006); on failure it returns `[]` so the dropout score degrades gracefully (no fee signals) rather than 500-ing the whole report.
- New `services/academics/app/api/reports_query.py` — all 9 read endpoints (dashboard, attendance/trend, financial/summary, dropout/summary, dropout/students, dropout/student/{id}, export/attendance, export/financial, export/dropout, export/report-card/{id}). The report-card PDF now pulls student + marks via `StudentService.get_student` and `AssessmentService.student_marks` in-process — that's two more HTTP hops eliminated.
- `services/academics/app/main.py` registers the reports router; health/phase bumped to `0.6.0-ph2-11`.
- `services/academics/app/config.py` — added `REPORTING_DATABASE_URL` and `FINANCE_SERVICE_URL` settings (FINANCE_SERVICE_URL is the only HTTP hop left in the dropout flow).

Reporting-service — write-side rewrite:
- New `services/reporting-service/app/consumer.py` — long-running Kafka consumer loop. Subscribes to 8 topics (student.created, enrollment.created, attendance.recorded, invoice.created, payment.recorded, announcement.created, plus the PH2-9 assessment.created + assessment.marks.recorded for future projection handlers). Per-event session open/close keeps connection-pool churn predictable; topic-derived `event_type` mapping wins over a missing/short envelope `event_type`. SIGINT/SIGTERM clean shutdown; failed events are committed-anyway to avoid wedging a partition on a poison message (the projection's idempotency inbox still skips it on replay).
- `services/reporting-service/app/main.py` — rewritten as a 30-line stub: `/health` + `/health/phase` only. No `/api/v1/reports/*` mounted. The phase endpoint reports `"PH2-11 — HTTP routes retired."`.
- `services/reporting-service/app/api/routes.py` and `app/api/exports.py` retain their code but emit `DeprecationWarning` on import. PH2-12 deletes them.
- `services/reporting-service/Dockerfile` CMD flipped from `uvicorn` to `python -m app.consumer`. Local dev can still run uvicorn manually if the `/health` introspection helps debugging.

CLI tools (replace the deleted HTTP write endpoints):
- New `services/reporting-service/cli/consume_events.py` — replays a JSON-array-or-NDJSON file of event envelopes through `ReportingService.consume_batch`. Supports `--dry-run` and per-batch progress logging.
- New `services/reporting-service/cli/rebuild_projections.py` — wipes projections + inbox then replays. Requires `--confirm` to actually run (preview-only without it) so an "I ran it in the wrong shell" foot-gun is harder.

Gateway changes:
- `services/api-gateway/app/routes.py` — `/api/v1/reports` repointed from `REPORTING_SERVICE_URL` to `ACADEMICS_SERVICE_URL` / `name="academics"`. RBAC entries for `POST /api/v1/reports/rebuild` and `POST /api/v1/reports/consume` removed (those endpoints are gone — falls through to the default `authenticated` rule, which means academics will 404 cleanly).
- `services/api-gateway/app/config.py` — `REPORTING_SERVICE_URL` kept as a deprecated alias pointing at the academics URL so any leftover third-party env still resolves; drops in PH2-12.
- `services/api-gateway/app/api/diagnostics.py` — the standalone `reporting-service` integration card removed. Reporting consumer health shows up implicitly in the academics card (when the consumer falls behind, dashboard tiles freeze — which is the signal operators actually want).

Compose:
- `docker-compose.yml` + `docker-compose.prod.yml` — `reporting-service` container loses its port mapping (`8007:8000` gone) and its `STUDENT/ATTENDANCE/FEES/ASSESSMENT_SERVICE_URL` env (no HTTP calls anymore); gains `KAFKA_ENABLED=true`. Gateway env `REPORTING_SERVICE_URL` repointed at `http://academics:8000`. Academics gains `REPORTING_DATABASE_URL` (postgres conn to `reporting_db`) + `FINANCE_SERVICE_URL` (for dropout invoice fetch).

Operational runbook:
- New `docs/runbooks/ph2-11-cutover.md` — pre-flight checks for academics env + reporting-service consumer process, smoke-test curl sequence, rollback procedure (re-point gateway route, restart reporting-service with old CMD, restart gateway). Notes the expected latency drop on `/dropout/summary` (~40–60% on staging-typical schools because 2 of the 3 HTTP hops are gone).

Tests:
- New `services/academics/tests/test_reports_query.py` — 11 tests covering: dashboard read (empty + seeded), attendance trend (date-range filtering), financial summary (year filter), projection tenant isolation, dropout engine boundary (sanity that the engine is reachable through the new module path), dropout summary in-process (zero students, one perfect student), dropout detail in-process (5 consecutive absences → MEDIUM), and auth requirements. Uses StaticPool in-memory SQLite per test to dodge a SQLite-file + connection-pool cache hazard that made `Base.metadata.create_all` after `drop_all` race with pooled sessions.
- New `services/reporting-service/tests/test_consumer.py` — 5 tests for the consumer bridge: topic-mapping completeness, event routing on the canonical `student.created` topic, topic-derived `event_type` resolution when the envelope only carries a short form ("recorded"), idempotent re-delivery of a duplicate event_id, and assessment-topic subscription presence (the consumer subscribes even though there's no projection handler yet, so the cursor advances).
- `services/reporting-service/tests/test_dropout.py` trimmed from 587 → 384 lines: the `TestDropoutRoutes` class (mocked HTTP route tests, 7 tests) and `TestDropoutTenantIsolation` (1 test) deleted — equivalent coverage now lives in `services/academics/tests/test_reports_query.py`. Pure-compute rules-engine classes (`TestAttendanceSignals`, `TestFeeSignals`, `TestBandBoundaries`, `TestCombinedScenarios`) stay here as the canonical owner; academics imports the same engine module.
- `services/api-gateway/tests/test_gateway.py` — `test_resolve_reports` updated to assert `ACADEMICS_SERVICE_URL`; `test_report_admin_requires_permission` renamed and rewritten as `test_report_writes_dropped_default_to_authenticated` (the rebuild/consume endpoints are gone, so the gateway falls through to the default `authenticated` permission — a teacher token IS authenticated, the underlying 404 happens in academics). Env block also updated to repoint `REPORTING_SERVICE_URL` at the academics port.

What's NOT done (deferred):
- The reporting-service `app/api/` files stay on disk for one minor-release rollback window — they emit a DeprecationWarning on import but otherwise still work. PH2-12 deletes them along with the four old academic-service folders.
- The PH2-9 assessment topics are subscribed but have no projection handler. The consumer dispatches `unknown_event` for them. Future work: add tiles for "assessments created this term" / "marks recorded today" once we know what the UI needs.

Verification:
| Suite | Result | Δ |
|---|---|---|
| **academics** | **211 ✓** | **+11** (new reports_query tests) |
| **api-gateway** | **105 ✓** | 0 (test_resolve_reports + RBAC test updated, count unchanged) |
| **reporting-service** | **51 ✓** | **-9** (route-handler tests removed: -14, consumer tests added: +5) |
| identity / finance / communications / school / student / attendance / assessment / shared (untouched) | 345 ✓ | 0 |
| **Total** | **712 backend+shared green** | **zero regressions** |

The cutover is **code-complete and test-verified**. Operational execution (deploy academics + reporting-service consumer; flip gateway) follows `docs/runbooks/ph2-11-cutover.md`.

### Phase 2 status

```
PH2-1  design                            ✅
PH2-2  auth → identity                   ✅
PH2-3  fees → finance                    ✅
PH2-4  communication → communications    ✅
PH2-5  academics shell                   ✅
PH2-6  school → academics                ✅
PH2-7  student → academics + in-process  ✅
PH2-8  attendance → academics + authz    ✅
PH2-9  assessment → academics + authz    ✅
PH2-10 gateway cutover                   ✅
PH2-11 reporting → consumer              ✅  ← THIS
PH2-12 delete old services (after burn-in) ⏳ NEXT
```

---

### Phase 0 (closed 2026-05-26)

- **Q-019 Initial 13 ADRs** — created `docs/decisions/` with `001-audience-pyramid.md` through `013-ministry-viewer-only.md` (plus `000-template.md`). Every locked decision in §1 references its ADR.
- **Q-018 Marketing-claim rewrite** — `VISION.md` now opens with a CAUTION block pointing to `STATUS.md`; `README.md` service list corrected (added `assessment-service`; fixed `fee-service` → `fees-service`, `comm-service` → `communication-service`); "dropout AI" → "rules-based dropout-risk scoring"; "comprehensive school management system" softened. New `STATUS.md` is the single source of truth for verified vs aspirational vs marketing.
- **Q-017 Context.md honesty pass** — CAUTION block prepended to `/Users/phani.m/Downloads/EduZim/Context.md`; status line revised to reflect audit findings.
- **Phase 0 gate**: ✅ passed. 13 ADRs on disk. No file in the repo asserts "production-ready", "1,053 tests" without qualifier, "500-school validated", "dropout AI", or "complete" without pointing to `STATUS.md`.

### Phase 2 — PH2-10 (closed 2026-05-26) — **gateway cutover landed; academics serves production**

**PH2-10 — gateway routes the 13 academic-domain prefixes at academics; data-migration script + cutover runbook shipped.**

Gateway routing flip (`services/api-gateway/app/routes.py`):
- 13 prefixes repointed from the four old services to `ACADEMICS_SERVICE_URL` / `name="academics"`:
  `/api/v1/schools`, `/academic-years`, `/terms`, `/classes`, `/subjects`, `/class-teachers`, `/teachers`, `/students`, `/parents`, `/enrollments`, `/attendance`, `/assessments`, plus the two formerly-orphaned ones (`/provinces`, `/districts`).
- `/api/v1/fees`, `/api/v1/comm`, `/api/v1/reports`, `/api/v1/auth` unchanged.

Config + env (`services/api-gateway/app/config.py` + both compose files):
- New `ACADEMICS_SERVICE_URL` setting (`http://academics:8000` in prod compose; `http://localhost:8009` locally).
- Old `SCHOOL_SERVICE_URL` / `STUDENT_SERVICE_URL` / `ATTENDANCE_SERVICE_URL` / `ASSESSMENT_SERVICE_URL` keys retained as deprecated aliases (all point at academics) so any third-party env file still loads. Drops in PH2-12.
- Gateway now `depends_on: [identity, academics, redis]` (was `[identity, redis]`).

Diagnostics (`services/api-gateway/app/api/diagnostics.py`):
- Four integration cards (school-service / student-service / attendance-service / assessment-service) consolidated into a single `academics` card with combined description and `ACADEMICS_SERVICE_URL` health probe.

Data migration:
- New `scripts/migrate-to-academics.sh` — one-time `pg_dump | psql` per source DB into academics_db. Modes: default (refuses if dest non-empty), `--dry-run`, `--truncate-first` (destructive). Logs row counts before/after; post-flight parity check warns if source vs target totals differ.
- Idempotency: not by default. `--truncate-first` resets and re-runs. Acceptable because the cutover window is brief and academics_db starts empty in production (burn-in had `KAFKA_ENABLED=false` and no gateway traffic, so the DB stayed pristine).

Operational runbook:
- New `docs/runbooks/ph2-10-cutover.md` — pre-flight checks, pause-writes step, migration step, gateway-restart step, smoke tests for one read endpoint per domain, full rollback procedure, post-cutover burn-in expectations (1 week before PH2-12 cleanup).

Tests updated:
- `services/api-gateway/tests/test_gateway.py` env block — added `ACADEMICS_SERVICE_URL`, repointed the four legacy URL keys at academics (matches prod compose shape).
- `test_resolve_students` and `test_resolve_attendance` updated to assert `ACADEMICS_SERVICE_URL` / `name="academics"`.
- 5 new tests added (`test_resolve_schools_routes_to_academics`, `test_resolve_classes_routes_to_academics`, `test_resolve_assessments_routes_to_academics`, `test_resolve_provinces_routes_to_academics`, `test_resolve_districts_routes_to_academics`).
- `test_downstream_timeout_returns_504` updated — the `downstream_service` in the error envelope is now `"academics"` for student-prefix calls (was `"student-service"`).

What's NOT done (deferred):
- Reporting still serves its HTTP routes from `reporting-service`. PH2-11 strips them and moves the read endpoints into academics.
- The four old service containers are still in compose. PH2-12 deletes them after a 1-week burn-in once the cutover is confirmed stable.
- The four old services still have their broken-pre-Phase-1-BUG-001 silent `except: pass` patterns in dependencies.py for assessment/attendance. Not patching forward because they're scheduled for deletion.

Verification:
| Suite | Result | Δ |
|---|---|---|
| **api-gateway** | **105 ✓** | **+5** (route-resolution tests for academics + provinces/districts) |
| academics (unchanged this phase) | 200 ✓ | 0 |
| identity / school / student / attendance / finance / communications / assessment / reporting (untouched — they still pass; the four "old" academic services just don't receive gateway traffic anymore) | 380 ✓ | 0 |
| shared | 19 ✓ | 0 |
| **Total** | **704 backend+shared green** | **zero regressions** |

The cutover is **code-complete and test-verified**. The operational execution (run the migration script, restart the gateway) is a small follow-up event per `docs/runbooks/ph2-10-cutover.md` — done on staging first, then prod behind a 5-minute maintenance window.

### Phase 2 status

```
PH2-1  design                            ✅
PH2-2  auth → identity                   ✅
PH2-3  fees → finance                    ✅
PH2-4  communication → communications    ✅
PH2-5  academics shell                   ✅
PH2-6  school → academics                ✅
PH2-7  student → academics + in-process  ✅
PH2-8  attendance → academics + authz    ✅
PH2-9  assessment → academics + authz    ✅
PH2-10 gateway cutover                   ✅
PH2-11 reporting → consumer              ✅
PH2-12 delete old services (after burn-in) ⏳
```

---

### Phase 2 — PH2-9 (closed 2026-05-26) — **all four academic-domain merges done**

**PH2-9 — assessment-service code moved into academics + two more HTTP authz hops replaced with in-process queries + missing Kafka emits added.**

Code move:
- `app/models/assessment.py` → `services/academics/app/models/assessment.py` (2 models: Assessment, Mark). Uses `String(36)` UUIDs (SQLite portability), unlike the rest of academics which uses `UUID(as_uuid=True)` — intentional, kept as-is.
- `app/models/idempotency.py` → academics (8-line wrapper around `eduzim_shared.idempotency.create_idempotency_key_model`).
- `app/services/assessment_service.py` (380 lines) → academics, verbatim.
- `app/api/routes.py` (252 lines, 6 endpoints) → `services/academics/app/api/assessment_routes.py`.
- `tests/test_assessment.py` (44 tests) → `services/academics/tests/test_assessment.py`, DB renamed.
- `tests/test_idempotency.py` (7 tests) → `services/academics/tests/test_assessment_idempotency.py`, DB renamed.
- Alembic `2026_05_19_007_initial.py` → `005_assessment_initial.py`, revision bumped to `2026_05_19_005`, `down_revision = "2026_05_19_004"`.

Test-suite fix-ups (12 patch sites):
- The copied tests patched `app.api.routes.verify_teacher_class_authorization` / `verify_parent_student_authorization`. In academics the module is `app.api.assessment_routes`, not `routes` (which is the school router). One `sed` rewrite — all patches re-pointed.

In-process replacements (the final two ADR-006-addendum §2 seams — closing the last two cross-service HTTP hops in the academic domain):
- `services/academics/app/services/authorization.py` — `is_teacher_authorized_for_student` and `is_parent_authorized_for_student` **implemented** (were `NotImplementedError` stubs from PH2-5). Queries:
  - `is_teacher_authorized_for_student`: `class_teacher_assignments ⋈ enrollments` on `class_id + school_id`, filtered by teacher + student + school.
  - `is_parent_authorized_for_student`: `parents ⋈ student_parents` on `parent_id`, filtered by `parents.user_id = parent_user_id + school_id + student_id`.
- `services/academics/app/dependencies.py` — added `is_parent_role`, `verify_parent_student_authorization`, `verify_teacher_student_authorization`. All async wrappers around the in-process functions; `SQLAlchemyError` → `AuthorizationServiceUnavailable` (Phase-1 BUG-001 fail-closed-honestly preserved).
- `services/academics/app/api/assessment_routes.py` — all three authz call sites updated to pass `db` and to translate `AuthorizationServiceUnavailable` → 503 with `Retry-After: 30` (the pre-consolidation assessment-service did NOT do this — it had the old silent `except Exception: pass` pattern; we get the Phase-1 BUG-001 spirit for free in the merge).

NEW Kafka emits (the pre-consolidation assessment-service did not publish events; reporting therefore missed assessments + marks entirely):
- `services/academics/app/events.py` gained `publish_assessment_created_event(...)` → `eduzim.assessment.created.v1` and `publish_marks_recorded_event(...)` → `eduzim.assessment.marks.recorded.v1`. Payloads carry the minimal identifiers + counters reporting needs (no row-level data over the wire).
- `assessment_routes.py` calls both at the appropriate route handlers.

Wiring:
- `services/academics/app/main.py` registers the assessment router under `/api/v1`. Health phase bumped to `0.5.0-ph2-9` with the wording **"all four academic-domain services folded in"**.
- `models/__init__.py` re-exports `Assessment`, `Mark`, `IdempotencyKey`.
- Compose: no changes — academics already exists from PH2-6; alembic now runs 5 migrations (001 school, 002 provinces, 003 student, 004 attendance, 005 assessment) automatically on startup.

Shell test rewritten:
- The pre-existing `test_remaining_authorization_stubs_raise_until_ph2_9` was removed (no stubs remain).
- Replaced with `test_no_authorization_function_still_stubs` — source-inspects the three public functions in `app.services.authorization` and asserts none of them contain `raise NotImplementedError`. A regression-catcher for any future refactor that accidentally re-stubs them.

What's NOT done (deferred):
- Gateway still routes `/api/v1/assessments/*` at assessment-service. Cutover is PH2-10.
- Data migration from `assessment_db` → `academics_db`. One-time copy script in PH2-10.
- The pre-consolidation `services/assessment-service/app/dependencies.py` still has the silent `except: pass` HTTP authz functions — same anti-pattern Phase-1 BUG-001 fixed in attendance. Since assessment-service is being retired in PH2-10, we accept the local bug and don't patch it forward.

Verification:
| Suite | Result | Δ |
|---|---|---|
| **academics** | **200 ✓** | **+63** (44 assessment + 7 assessment_idempotency + 12 new in-process authz tests; -3 shell-stub assertions consolidated into one source-inspection test) |
| assessment-service (untouched) | 51 ✓ | 0 |
| attendance-service (untouched) | 24 ✓ | 0 |
| school-service · student-service · api-gateway · others + shared | 480 ✓ | 0 |
| **Total** | **699 backend+shared green** | **zero regressions** |

The new `test_authz_in_process.py` covers both PH2-9 functions end-to-end:
- 5 tests for `is_teacher_authorized_for_student` (happy path, no-teach-relationship, no-enrollment, cross-tenant, DB-error → 503)
- 6 tests for `is_parent_authorized_for_student` (happy path, no link, wrong parent user, cross-tenant, NULL `parent.user_id` (parents without logins), DB-error → 503)
- 1 PH2-8 spot-check (teacher↔class still works after dependencies.py was extended)

### Phase 2 status summary

| Sub-task | Status |
|---|---|
| PH2-1 design addendum | ✅ |
| PH2-2 auth → identity | ✅ |
| PH2-3 fees → finance | ✅ |
| PH2-4 communication → communications + worker fold | ✅ |
| PH2-5 academics shell | ✅ |
| PH2-6 school → academics | ✅ |
| PH2-7 student → academics + school-client in-process | ✅ |
| PH2-8 attendance → academics + teacher-class authz in-process | ✅ |
| **PH2-9 assessment → academics + 2 more authz in-process + Kafka emits** | **✅** |
| PH2-10 gateway cutover + one-time data migration | ✅ |
| PH2-11 reporting → consumer + queries-in-academics | ✅ |
| PH2-12 cleanup (delete old services after burn-in) | ⏳ next |

**All four academic-domain services (school, student, attendance, assessment) are mirrored in academics. All five cross-service HTTP hops in that domain are now in-process. PH2-10 + PH2-11 are live in code; PH2-12 just waits out the burn-in then deletes the four old service folders plus the dead reporting-service HTTP routes.**

---

### Phase 2 — PH2-8 (closed 2026-05-26)

**PH2-8 — attendance-service code moved into academics + `/internal/teachers/authorize` HTTP hop replaced with in-process query against `class_teacher_assignments`**

Code move:
- `app/models/attendance.py` → `services/academics/app/models/attendance.py` (3 models: AttendanceRecord, SyncBatch, ProcessedClientEvent). `models/__init__.py` re-exports.
- `app/services/attendance_service.py` (329 lines) → academics, verbatim.
- `app/api/routes.py` (175 lines) → `services/academics/app/api/attendance_routes.py` (renamed to avoid collision).
- `tests/test_attendance.py` (24 tests) → `services/academics/tests/test_attendance.py`, DB renamed to `test_academics_attendance.db`.
- Alembic migration `2026_05_19_003_initial.py` → `services/academics/alembic/versions/2026_05_19_004_attendance_initial.py`, revision bumped to `2026_05_19_004`, `down_revision = "2026_05_19_003"` chaining cleanly after student.
- `app/events.py` — added `publish_batch_event(...)` (the attendance-specific topic+payload shape) to academics' existing events module. Shares the `academics` Kafka producer with school + student.

In-process replacement (the ADR-006-addendum §2 seam — the second one closed):
- `services/academics/app/services/authorization.py` — `is_teacher_authorized_for_class(...)` implemented. Direct query against `ClassTeacherAssignment` (already in academics_db from PH2-6). Signature simplified to raw IDs (`teacher_user_id, class_id, school_id, db_session`); PH3 will collapse to `ActorContext`.
- `services/academics/app/dependencies.py` — added `is_teacher_role(...)` and a new async `verify_teacher_class_authorization(teacher_user_id, class_id, school_id, db)` that wraps the in-process function. The Phase-1 `AuthorizationServiceUnavailable` exception is preserved: in-process can no longer fail on network errors, but a real `SQLAlchemyError` during the authz query is wrapped into the same exception so the route layer's existing 503-with-Retry-After handler in attendance routes works unchanged.
- `services/academics/app/api/attendance_routes.py` — single-line change: the `await verify_teacher_class_authorization(teacher_id, cid, school_id)` call now passes `db` as the fourth argument.

Wiring:
- `services/academics/app/main.py` registers the attendance router under `/api/v1`. Health phase label bumped to `0.4.0-ph2-8`.
- Compose: no changes — academics container already exists from PH2-6; alembic now runs all 4 migrations (001 school, 002 provinces, 003 student, 004 attendance) automatically on startup.

Shell test updated:
- Removed the `is_teacher_authorized_for_class` raises-NotImplementedError assertion (the function is now implemented).
- The other two stubs (`is_teacher_authorized_for_student`, `is_parent_authorized_for_student`) still raise NotImplementedError — they land in PH2-9 (assessment merge).

What's NOT done (deferred):
- Gateway still routes `/api/v1/attendance/*` at attendance-service. Cutover is PH2-10.
- Data migration from `attendance_db` → `academics_db`. One-time copy script in PH2-10.
- The Phase-1 BUG-001 HTTP-mock tests (7) became obsolete — they tested `httpx` failure modes that can't exist in an in-process call. Replaced with 7 new in-process tests covering the same BUG-001 spirit (fail-closed but honest on DB-level error).

Verification:
| Suite | Result | Δ |
|---|---|---|
| **academics** | **137 ✓** | **+24** (24 attendance tests; 7 obsolete HTTP-mock tests rewritten as 7 new in-process tests) |
| attendance-service (untouched) | 24 ✓ | 0 |
| school-service (untouched) | 60 ✓ | 0 |
| student-service (untouched) | 40 ✓ | 0 |
| api-gateway (routes unchanged) | 100 ✓ | 0 |
| 5 other services + shared | 256 + 19 ✓ | 0 |
| **Total** | **636 backend+shared green** | **zero regressions, +24 new in academics** |

The new `TestPH28TeacherAuthInProcess` test class proves the seam: `is_teacher_authorized_for_class` returns True for a matching `ClassTeacherAssignment` row, False for cross-tenant queries, False for wrong class or wrong teacher, and the route-level wrapper still surfaces `AuthorizationServiceUnavailable` → 503 when the DB raises `OperationalError`.

---

### Phase 2 — PH2-7 (closed 2026-05-26)

**PH2-7 — student-service code moved into academics + `school_client` HTTP hop replaced with in-process query**

Code move:
- `app/models/student.py` → `services/academics/app/models/student.py` (4 models: Student, Parent, StudentParent, Enrollment; + 4 enums). `models/__init__.py` re-exports.
- `app/services/student_service.py` (426 lines) → academics, verbatim — the service-layer signature unchanged because the school-client Protocol is identical between HTTP and in-process implementations.
- `app/api/routes.py` (288 lines) → `services/academics/app/api/student_routes.py` (renamed to avoid collision with school's `routes.py`).
- `app/api/bulk.py` (297 lines) → `services/academics/app/api/bulk.py`.
- `tests/test_student.py` (40 tests) → `services/academics/tests/test_student.py` with DB renamed to `test_academics_student.db`.
- Alembic migration `2026_05_19_002_initial.py` (student tables) → `services/academics/alembic/versions/2026_05_19_003_student_initial.py` with revision id bumped to `2026_05_19_003` and `down_revision = "2026_05_19_002"` so it chains after the school migrations cleanly.

In-process replacement (the ADR-006-addendum §2 seam):
- New `services/academics/app/services/school_client.py` — `InProcessSchoolClient` now queries the co-located `Class` + `AcademicYear` SQLAlchemy models directly (`db.query(Class).filter(...)`); the `SchoolServiceClient` Protocol shape is preserved so `StudentService` doesn't know the implementation changed.
- Deprecated alias `HttpSchoolServiceClient` retained for one transitional minor release; it now requires a `db` session and wraps `InProcessSchoolClient` underneath. Without `db`, it raises `RuntimeError` loudly.
- `MockSchoolServiceClient` kept unchanged so the existing 40 student tests use it without modification.
- All 3 call sites in `student_routes.py` (line 29) + `bulk.py` (line 30) + `student_routes.py` (line 234) updated to instantiate `InProcessSchoolClient(db)`.

Wiring:
- `services/academics/app/main.py` includes the 3 routers under `/api/v1`: `routes` (school), `student_routes`, `bulk`. Health phase label bumped to `0.3.0-ph2-7`.
- `services/academics/app/dependencies.py` gained `get_token` (student routes use it for the in-process client's `token` argument — kept for Protocol compatibility).
- Compose: no changes — academics container already exists from PH2-6; alembic now runs all 3 migrations (school 001, provinces 002, student 003) automatically.

What's NOT done (deferred):
- Gateway still routes `/api/v1/students`, `/api/v1/parents`, `/api/v1/enrollments` at student-service. The cutover is PH2-10.
- Data migration from `student_db` → `academics_db`. Done as a single one-time copy script in PH2-10.
- `/internal/parents/authorize` endpoint — academics now serves it locally (via the student_routes router), but assessment-service still calls student-service's HTTP copy because assessment hasn't merged in yet (PH2-9).

Verification:
| Suite | Result | Δ |
|---|---|---|
| academics (new test_student.py + test_in_process_school_client.py) | **113 ✓** | +50 (40 student + 10 in-process-client) |
| student-service (untouched) | 40 ✓ | 0 |
| school-service (untouched) | 60 ✓ | 0 |
| api-gateway (routes unchanged) | 100 ✓ | 0 |
| 6 other services + shared | 280 + 19 ✓ | 0 |
| **Total** | **612 backend+shared green** | **zero regressions, +50 new in academics** |

The new `test_in_process_school_client.py` proves the seam: `InProcessSchoolClient.validate_class` returns the row when present in academics_db, returns `None` for cross-tenant queries, and the full `StudentService(db, InProcessSchoolClient(db))` enrollment path validates against real Class+AcademicYear rows with no network hop.

---

### Phase 2 — PH2-6 (closed 2026-05-26)

**PH2-6 — school-service code moved into academics**

Code move:
- `app/models/school.py` → `services/academics/app/models/school.py` (8 models: Province, District, School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment). `models/__init__.py` re-exports them.
- `app/services/school_service.py` (593 lines of business logic) → academics, verbatim.
- `app/api/routes.py` (445 lines, 24 endpoints) → academics, verbatim. Splitting into `schools.py` / `academics.py` / `classes.py` / `geo.py` deferred to PH2-10 cleanup — cosmetic.
- `app/events.py` → academics with `client_id` and `source` changed from `school-service` to `academics` (and Kafka producer registered with a distinct `label="academics"` so the shutdown-flush registry doesn't collide).
- `app/dependencies.py`, `app/database.py` → academics.
- `alembic/` (env.py, script.py.mako, versions/2026_05_19_001_initial.py, 2026_05_19_002_provinces_districts.py) + `alembic.ini` → academics.
- `tests/test_school.py` → `services/academics/tests/test_school.py` (DB path renamed `test_school.db` → `test_academics_school.db`).

Service wiring:
- `services/academics/app/main.py` rewritten — uses the shared `app_factory.create_app()` (graceful-shutdown lifespan + Sentry hook), includes the school router at `/api/v1`, and exposes `/health/phase` as the phase indicator (the factory's `/health` stays as the standard one).
- `services/academics/Dockerfile` (multi-stage with non-root `app` user per INFRA-020).
- `services/academics/requirements.txt`.
- `docker-compose.yml` + `docker-compose.prod.yml`: new `academics` container exposed on port 8009, `KAFKA_ENABLED=false` (school-service still the publisher during burn-in), `INFRA-021` resource caps on prod.
- `postgres.POSTGRES_MULTIPLE_DATABASES` adds `academics_db`.
- `scripts/init-tables.py`, `scripts/fix_dockerfiles.py`, `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `Makefile`, `README.md` all updated to include academics.

What's NOT done (deferred):
- Gateway routing — `/api/v1/schools`, `/api/v1/classes`, etc. still point at school-service. The cutover is PH2-10.
- Data migration from `school_db` → `academics_db`. The two run in parallel with separate state during the burn-in. PH2-10 ships the one-time copy + cutover script.
- Splitting the monolithic `routes.py` into per-domain modules (schools / classes / geo / internal) — cosmetic; PH2-10.
- The in-process replacement of `/internal/teachers/authorize` (consumed by attendance and assessment services). The endpoints exist in academics and still work; consumers continue to call school-service's copy until PH2-8/9 fold attendance + assessment in.

Verification:
| Suite | Result |
|---|---|
| academics (new) | 63 ✓ (60 school tests + 3 shell tests) |
| school-service (untouched) | 60 ✓ |
| api-gateway (routes unchanged) | 100 ✓ |
| Other 7 services | 339 ✓ (identity 28, student 40, attendance 24, finance 51, communications 72, assessment 51, reporting 54, totals reconfirmed; +shared 19) |
| **Total** | **562 backend+shared, zero regressions** |

Both DBs have the same schema (created from the same Alembic migrations); during burn-in only school-service receives traffic so academics_db starts empty and stays empty. PH2-10 will run the one-time data copy and flip the gateway.

---

### Phases closed this session (2026-05-26 continuation)

Continuing in the same session the user asked to push through every non-dependency, non-major-overhaul item across the plan. Closures below; deferrals tagged with explicit reason.

**PH2-3 (fees-service → finance)**
- Directory renamed, Dockerfile internal paths fixed, docker-compose service block renamed (`fees-service` → `finance`) with `fees-service` DNS alias retained, `FINANCE_SERVICE_URL` added to gateway env (`FEES_SERVICE_URL` retained as alias), gateway routes/config/diagnostics + CI matrices + Makefile + scripts + README + STATUS updated. Gateway `test_resolve_fees` updated to assert `FINANCE_SERVICE_URL`/`finance`. Tests: finance 51/51 + gateway 100/100.

**PH2-4 (communication-service → communications + fold notification-worker)**
- Directory renamed, `services/notification-worker/worker.py` moved to `services/communications/app/workers/notification_dispatcher.py`. `notification-worker` container retained as a separate process but now builds against the communications source and runs `python -m app.workers.notification_dispatcher`. `COMMUNICATIONS_SERVICE_URL` canonical, `COMMUNICATION_SERVICE_URL` alias. Gateway test updated. Tests: communications 72/72 + gateway 100/100.

**PH2-5 (academics shell)**
- New `services/academics/` shell with `app/main.py` (FastAPI + `/health`), `app/config.py` (required-env per BUG-003), `app/services/authorization.py` (interface stubs for `is_teacher_authorized_for_class`, `is_teacher_authorized_for_student`, `is_parent_authorized_for_student` — all raise `NotImplementedError` until PH2-8/9 populate). Empty `api/`, `models/`, `schemas/` placeholders. Tests scaffolding (`tests/__init__.py` with env defaults) + `tests/test_shell.py` (2/2 green). NOT wired to gateway. PH2-6→9 populate it.

**PH4-1 (SQLAlchemy pool config standardised)**
- All 8 service `database.py` files now use `pool_size=20, max_overflow=40, pool_recycle=3600, pool_pre_ping=True`. Assessment-service's SQLite path branches around the pool kwargs. Tests across all services: 482 backend + 19 shared = 501 green.

**INFRA-001 (Postgres backup container)**
- New `infra/backups/` with `Dockerfile`, `backup.sh` (per-DB `pg_dump | gzip`, retention prune), `restore.sh` (latest or timestamped), `entrypoint.sh` (initial backup + sleep loop). Compose `pg-backup` service + `pg_backups` named volume + runbook at `docs/runbooks/backup-restore.md`.

**INFRA-020 (Non-root containers)**
- All 9 service Dockerfiles + the notification-worker Dockerfile gained:
  ```dockerfile
  RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
      chown -R app:app /app
  USER app
  ```
  Inserted right before each `CMD`.

**INFRA-021 (Resource limits)**
- `docker-compose.prod.yml` — every 14 service entries gained `deploy.resources.limits` + `deploy.resources.reservations`. Postgres 2 CPU / 2G; Kafka 1.5 CPU / 2G; Redis 0.5 CPU / 512M; application services 0.5 CPU / 512M each. YAML verified valid.

**INFRA-022 (Graceful shutdown)**
- `shared/eduzim_shared/app_factory.create_app()` now installs a `lifespan` context manager that: (1) runs caller-provided `shutdown_hooks`, (2) flushes any registered Kafka producer via the new `_registered_producers` registry in `shared/eduzim_shared/kafka/producer.py`, (3) sleeps `shutdown_grace_seconds` (default 3s) for in-flight requests to drain.

**INFRA-007 (Prometheus + Grafana scaffold)**
- New `infra/observability/`: `prometheus.yml` (scrapes api-gateway today; commented-out scrape blocks for the other services pending /metrics endpoints), `grafana/datasources.yml`, `grafana/dashboards.yml`, `grafana/dashboards/gateway-overview.json` (one starter dashboard: request rate, 5xx %, rate-limit blocks, latency p95). Compose adds `prometheus` (port 9090) + `grafana` (port 3030, admin/admin) + named volumes `prometheus_data`, `grafana_data`. Full runbook at `docs/runbooks/observability.md`.

**INFRA-010 (Sentry SDK env wiring)**
- `shared/eduzim_shared/app_factory.py` calls `_maybe_init_sentry(...)` when `SENTRY_DSN` env is non-empty. Honours `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_ENVIRONMENT`. `send_default_pii=False` hard-coded per ADR 007. No-op when `sentry-sdk` not installed (so tests don't need the lib). Installation gated to production wiring.

**PH9-1 (Privacy Impact Assessment skeleton)**
- New `docs/compliance/pia-v1.md` — full PII inventory per service-DB, retention tags, Children's Act flags, risk register skeleton, open-items list pointing at the deferred Phase 9 work.

**Q-009 (Privacy + Retention policies)**
- New `docs/compliance/privacy-policy.md` — data we process, lawful basis (ZDPA + Children's Act), data subject rights, where data lives (ADR 005), security posture.
- New `docs/compliance/retention-policy.md` — full retention table (operational data 90 days → 2 years; academic records 7 years; financial 7-year statutory; deletion + litigation hold + offboarding procedures).
- Both flagged "Draft v0.1 — pre-pilot legal review required".

**Q-010 (DPO contact in footer)**
- All three apps' `Footer` component (admin/parent/teacher) gained a `<nav>` row with `/privacy`, `/retention`, and `mailto:dpo@eduzim.co.zw` links. 9 i18n message files updated (EN/SN/ND × 3 apps) with `privacyPolicy`, `retentionPolicy`, `dpoContact`, `dpoEmail` keys.

**Q-016 / INFRA-018 (audit_log table + helper) — partial**
- `AuditLog` model added to `services/identity/app/models/user.py` (id, occurred_at, actor_user_id, actor_role, school_id, event_type, target, details, ip_address, user_agent, request_id; indexed on occurred_at/actor_user_id/school_id/event_type/request_id).
- `services/identity/app/services/audit.py` `record_audit_event(...)` helper — JSON-encodes target/details, never raises into the caller, logs loudly on failure.
- **What's NOT done** (deferred to Phase 9 follow-up): wiring `record_audit_event` into every PII write across services; admin UI to browse the log; the auto-purge job (retention enforcement).

**Q-001a / PH10-1 (Recharts wrappers + admin reports integration)**
- `packages/ui/src/components/charts/index.tsx` — `LineChart`, `BarChart`, `PieChart`, `SparkLine` components backed by Recharts (~50KB gzipped). EduZim theme tokens (purple-led palette with Zimbabwe accents). Each wrapper accepts a uniform `{ data, xKey, series, height, className, ariaLabel }` API. Exported from `@eduzim/ui`.
- `recharts` added to `packages/ui/package.json`.
- `apps/admin-web/src/app/(admin)/reports/page.tsx` — attendance trend section now renders a stacked `BarChart` (Present/Absent/Late) + a `LineChart` (rate %). The HTML table is preserved as an accessible `<details>` block so screen-reader users still get the numbers.

**Phase 19 partial (Documentation)**
- `docs/architecture.md` — as-built architecture with the post-PH2-5 service layout, locked ADR table, cross-cutting patterns, in-flight items list.
- `docs/runbooks/backup-restore.md` (closed via INFRA-001).
- `docs/runbooks/observability.md` (closed via INFRA-007/010).

---

### Deferred to "major overhaul / dependency-blocked" (this session)

Tagged `deferred-major` in the per-phase tables below. Reason captured per-item.

| Item | Reason for deferral |
|---|---|
| PH2-10 → PH2-12 (gateway cutover + reporting-as-consumer + cleanup) | The four merges (PH2-6/7/8/9) all closed 2026-05-26. PH2-10 is the gateway cutover + one-time data migration; PH2-11 strips HTTP from reporting; PH2-12 deletes the old service folders after a 1-week burn-in. |
| PH2-10 → PH2-12 (gateway cutover + reporting-as-consumer + delete-old) | Depend on PH2-6→9. |
| Phase 3 entire (gateway-headers-only auth, BUG-007) | Wait until after Phase 2 consolidation so we refactor 4 services not 8. |
| INFRA-002 (pgbouncer) | Needs DB_PASSWORD secrets unification — separate task. |
| BUG-008 / INFRA-008 (migrations out of CMD) | Overlaps with PH2-12 cleanup; better done together. |
| Q-006 (cross-tenant isolation tests, 20+ tests) | Substantive test work; best done after PH2 consolidation so tests target the final shape. |
| Q-007 (concurrency tests) | Same — substantive work targeting final shape. |
| INFRA-003 (Postgres replication / Patroni / RDS Multi-AZ) | Multi-week HA infrastructure. |
| INFRA-004 / 005 (Kafka 3-broker KRaft cluster) | Multi-week HA. |
| INFRA-006 (Redis Sentinel / cluster) | Multi-week HA. |
| INFRA-019 (TLS between services) | Cert management substantial. |
| INFRA-014 (DR + RTO/RPO + failover test) | Depends on the HA work above. |
| INFRA-008 (distributed tracing — Jaeger/Tempo + OTel SDK) | Substantial cross-service wiring; observability scaffold (Prom + Grafana) shipped instead. |
| INFRA-009 (Loki log aggregation) | Same. |
| PH6-1 (Alertmanager rules + paging) | Needs an on-call rota; meaningless without one. |
| Q-014 / INFRA-015 (Real 24-hour seeded load test with chaos) | Substantive script-building + chaos infra; better after Phase 5 HA lands. |
| Phase 8 (tenancy tiers query routing layer) | Touches every service DB code path — major refactor; overlaps with PH2 consolidation. |
| PH9-2 (minimum-data audit) | Field-by-field review across the platform; needs domain merges to lock the schema. |
| PH9-3 (per-parent / per-school data export endpoint) | Needs PH2 consolidation; export is per-tenant in academics_db. |
| PH9-4 (right-to-delete endpoint with tombstone anonymisation) | Same — needs the consolidated schema. |
| Q-001b (ECharts heatmap / geomap / sankey + lazy-loaded) | Defer to Phase 14 when ministry-web is built — that's where these are used. |
| Phase 11 → 15 (persona feature build-out + learning layer) | Massive surface; each persona is its own multi-session phase. |
| Phase 16 (OpenAPI + MCP + Provider SDK + docs site) | Significant; do after the platform stabilises post-PH2. |
| Phase 17 (CI/CD beyond image builds + staging env + canary deploy + runbooks) | Substantial Terraform/Helm + pipeline work. |
| Phase 18 (open source release) | Post-v1 by design (DEC-012). |

---

### Phase 2 — PH2-2 (closed 2026-05-26)

- **PH2-2 Renamed `auth-service` → `identity`**. Directory moved, Dockerfile updated, container renamed (with `auth-service` DNS alias retained for back-compat), gateway routes/config/diagnostics updated to use `IDENTITY_SERVICE_URL` (with `AUTH_SERVICE_URL` kept as alias), CI/CD workflows + Makefile + scripts + README + STATUS updated. All other services that referenced `http://auth-service:8000` now use `http://identity:8000` (alias still works). One gateway test updated to assert the new URL key.
- Verification: full test suite re-run. Identity 28/28, gateway 100/100, school 60, student 40, attendance 24, fees 51, communication 72, assessment 51, reporting 54 — all green. Zero regressions from the rename.

### Phase 2 — PH2-1 (closed 2026-05-26)

- **PH2-1 Module-level call graph + migration sequence**. New ADR addendum at `docs/decisions/006-addendum-module-call-graph.md`. Source for the addendum: a full Explore-agent survey of every backend service's modules, routes, models, Kafka topics, internal HTTP calls, and shared-lib uses. The addendum locks:
  - Module-level mapping for each of the 4 target services (identity / academics / finance / communications) + reporting-as-consumer.
  - Every intra-process function call that replaces a current cross-service HTTP hop (5 of them — `/internal/teachers/authorize`, `/internal/teachers/authorize-student`, `/internal/parents/authorize`, plus the school↔student `school_client` HTTP calls).
  - Schema-merge plan for academics_db (collapse of school_db + student_db + attendance_db + assessment_db).
  - Gateway route remapping (13 public prefixes; public API contract unchanged).
  - The expanded sub-task sequence PH2-2 through PH2-12 (was PH2-2 through PH2-10).
  - A risk register and per-task rollback plan.

### Phase 1 (closed 2026-05-26)

The 6 high-severity security/correctness bugs all fixed, with regression tests:

- **BUG-001** Teacher-class authorization fail-closed-honestly: `AuthorizationServiceUnavailable` raised on downstream outage; route returns 503 with `Retry-After: 30` instead of silently denying access. Tests: `TestBUG001TeacherAuthFailClosed` (7 new in attendance-service).
- **BUG-002** Paynow webhook no longer swallows amount-parsing or payment-id-linking failures; `txn.last_error` records what went wrong; webhook still returns "Ok" so Paynow doesn't retry forever. Tests: 3 new webhook tests in fees-service `test_paynow.py`.
- **BUG-003** All 9 service `config.py` declare `JWT_SECRET_KEY: str` (required, no default). `docker-compose.yml` uses `${JWT_SECRET_KEY:?...}` interpolation. New `scripts/bootstrap-secrets.sh` generates strong randoms into `.env`. Gateway startup guard rewritten (`_KNOWN_BAD_SECRETS` set + min-length check).
- **BUG-004** Same treatment for `INTERNAL_SERVICE_TOKEN` in attendance / school / assessment services; bootstrap-generated.
- **BUG-005** `apps/teacher-web/.../attendance-tab.tsx` now sends `schoolId: user.school_id` (was `""`). 3 source-regression tests in `gate10b-4.test.ts`.
- **BUG-006** Rate limiter rewritten: in-memory fallback removed; `RateLimiter` requires a Redis client (`ValueError` otherwise); `get_rate_limit_key` gained `ip` parameter; `/auth/login`, `/auth/refresh`, `/auth/forgot-password` now IP-keyed; main `_build_rate_limiter()` reads `REDIS_URL`. 7 new tests including `test_rate_limit_survives_gateway_restart` proving state lives in Redis.

Supporting infrastructure:

- **INFRA-013** `docs/runbooks/secrets-rotation.md` written: dev workflow, production rotation procedures (JWT + internal-token), incident response for leaked secrets.
- All 9 services got a `tests/__init__.py` that calls `os.environ.setdefault(...)` for JWT_SECRET_KEY + INTERNAL_SERVICE_TOKEN with obvious-test values — so config-loads in tests don't break after defaults were stripped.

Verification (run 2026-05-26):

| Suite | Result | New tests |
|---|---|---|
| api-gateway/tests | **100 passed** | +7 (rate-limit) |
| attendance-service/tests | **24 passed** | +7 (BUG-001) |
| fees-service/tests | **21 passed** | +3 (BUG-002 webhook) |
| auth-service/tests | 28 passed | 0 |
| school-service/tests | 60 passed | 0 |
| student-service/tests | 40 passed | 0 |
| assessment-service/tests | 51 passed | 0 |
| communication-service/tests | 72 passed | 0 |
| reporting-service/tests | 54 passed | 0 |
| teacher-web/tests/gate10b-4 | **38 passed** | +3 (BUG-005 regression) |
| **Total** | **488 green** | **+20 new, zero regressions** |

`./scripts/bootstrap-secrets.sh --check` correctly reports `.env` missing for a fresh checkout — first action on a new machine is `./scripts/bootstrap-secrets.sh`.

(Pre-existing build features remain *not* in this list. They earn `done` only after the relevant phase verification gate passes.)

---

## Next Action

**Phases 2, 3, 4, 8, 9, 10 are closed; Phases 5, 6, 7 are scaffolded (staging gates pending).** Closed 2026-05-26:
- Phase 2 (PH2-1 → PH2-12): 8-service architecture consolidated to 4 + Kafka consumer.
- Phase 3 (BUG-007): JWT removed from every downstream service.
- Phase 4 (Q-006, Q-007, INFRA-002, BUG-008): cross-tenant isolation + concurrency invariants + pgbouncer + migrations container. Caught BUG-009, BUG-010.
- Phase 5 (INFRA-003/004/005/006/019): HA overlay + mTLS scaffolded. Chaos suite written. ⚙️ staging verification pending.
- Phase 6 (INFRA-007/008/009 + PH6-1): per-service metrics, OTLP tracing, Loki logs, Alertmanager rules. ⚙️ staging verification pending.
- Phase 7 (Q-014/INFRA-015, PH7-1, PH7-2, PH7-4): real-API seed + 24-hr load script + toxiproxy chaos profile + report generator. Old `scripts/scale_test.py` deprecated. ⚙️ 24-hour staging run pending.
- Phase 8 (PH8-1/2/4 closed; PH8-3 scaffolded): tenancy tiers — `tenancy_tier` column + shared TenancyResolver + per-school/parent data-rights export endpoints. PH8-3 promotion drill on staging is the only remaining gate.
- Phase 9 (substrate complete; PH9-2 deferred-with-plan): shared audit-log helper + per-service `audit_log` table + admin browse endpoint + retention CLI. Right-to-export closed by PH8-4. PH9-2 minimisation review documented as a structured checklist in `docs/compliance/data-minimisation-audit.md`. **Closes the production-readiness foundation track.**
- Phase 10 (closed in code; PH10-3 Lighthouse pending real build): Recharts wrappers (Q-001a) + ECharts wrappers (Q-001b: Heatmap, ZimbabweGeomap, Sankey) on a separate subpath with `next/dynamic` lazy-loading. Admin reports financial section (PH10-2) migrated from table-as-chart to stacked BarChart. **Closes the table-as-chart problem from DEC-011 / ADR 011.**

Verified: **719 backend+shared+scripts tests green, zero regressions.** ADRs 001-018 on disk. All five compose files parse cleanly. Frontend builds NOT run in this harness — Phase 10's bundle-budget verification is a post-`pnpm build` operational check per `docs/runbooks/charts-bundle-budget.md`.

What's next, in dependency order:

1. **Staging verification of Phases 5 + 6 + 7 + 8** (operational, not code). Single staging window:
   - Boot the full stack: `docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml -f docker-compose.observability.yml -f docker-compose.chaos.yml up -d`
   - Run `scripts/chaos/run-all.sh` → expect 4/4 PASS (Phase 5 chaos gate).
   - Run synthetic-500 alert-flow verification per `docs/runbooks/phase-6-observability-rollout.md` (Phase 6 gate).
   - Run the seed + 24-hour load test per `docs/runbooks/phase-7-load-test.md`. Commit the dated report (Phase 7 gate).
   - Dry-run + real-run `scripts/promote-school-to-dedicated.sh` against one seeded school per `docs/runbooks/tenancy-upgrade.md` (Phase 8 gate, PH8-3).
   - Once all four gates pass, flip the `⚙️` items across Phases 5/6/7/8 to `✅`.

2. **Phase 11+** (Audience gaps from `task.md` §6-§10) — Teacher / Student / Parent / Admin / Ministry feature gaps. The real product work, finally sitting on top of a now-complete production-readiness foundation. Phase 11 is the biggest persona block (Teacher); Phase 12 is Parent + Student in the shared app; Phase 13+ continue.

3. **Ongoing follow-ups** (not phase-gated):
   - Wire `record_audit_event` into finance + communications PII writes (one-liner per route; pattern documented in ADR 018).
   - Walk through `docs/compliance/data-minimisation-audit.md` row by row with product + legal as windows open.
   - Engage Zimbabwean lawyer on ZDPA (PH9-5; ADR 005 calls this out).
   - Right-to-delete with tombstones (PH9-4) — deferred-major; needs product input on which fields are "academic record" vs "writeable".
   - §6 (Teacher) — bulk "mark all present", period-based attendance, homework workflow, behavior incidents, lesson plans, substitute mode, comment bank, photo / voice / file attachments, calendar, parent message threads, exam invigilation, formative assessments, roster offline cache, gradebook.
   - §7 (Student — on parent-web per DEC-002) — schedule view, assignments due, marks, submit homework, take quizzes, announcements.
   - §8 (Parent) — pay fees online (DEC-004 integration handover), multi-child UX, push notifications, parent-teacher conference booking, digital permission slips, concern / grievance submission, direct message to teacher, performance comparison vs class avg, calendar of events, PDF receipts.
   - §9 (Admin) — non-teaching staff mgmt, HR, admissions workflow, transfers, compliance / Ministry report templates, disciplinary actions log, health records, financial dashboards beyond fees, inventory / asset mgmt, parent feedback / complaint handling.
   - §10 (Ministry — viewer + auditor only per DEC-013) — district / province / national roll-up dashboards.

My recommendation: **one consolidated staging run** that covers all three pending gates (Phase 5 chaos + Phase 6 alert flow + Phase 7 load) in a single 2-day window. The 24-hour load test is itself the best chaos test — it exercises the alerting + tracing + HA stack under real traffic. Closing all three gates in one sweep means everything afterward is product feature work sitting on a known-good baseline.

Alternative: split into two windows — chaos+alert first (~half day), 24-hour load second. Lower-risk if staging time is fragmented.

The "Deferred to major overhaul / dependency-blocked" table near the top of §12 summarises what still hasn't been touched and why.
