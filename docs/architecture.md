# EduZim Architecture (as-built, 2026-05-26)

> **Truth before reading this**: cross-check any specific capability claim against [`STATUS.md`](../STATUS.md). This document describes the *shape* of what's built and where each piece lives.
>
> **Locked design decisions** that shape this architecture: see [`docs/decisions/`](./decisions/).
> **Operations runbooks**: see [`docs/runbooks/`](./runbooks/).
> **Compliance & privacy docs**: see [`docs/compliance/`](./compliance/).

---

## 1. Layout (post Phase 2 partial — PH2-1 through PH2-5 closed)

```
                  ┌────────────────────────────────────────────┐
                  │  Frontend PWAs (Next.js — three apps)      │
                  │    admin-web · parent-web · teacher-web    │
                  │    (per ADR 002, student uses parent-web)  │
                  └────────────┬───────────────────────────────┘
                               │ HTTPS + httpOnly refresh cookie
                               ▼
                    ┌──────────────────────┐
                    │   api-gateway        │
                    │   (FastAPI)          │
                    │  • JWT validation    │
                    │  • RBAC enforcement  │
                    │  • Tenant injection  │
                    │  • Redis token bucket│
                    │  • Circuit breaker   │
                    │  • Request id        │
                    │  • Prometheus metrics│
                    └─────┬────────────────┘
                          │
   ┌──────────┬───────────┼───────────┬───────────┬──────────────┐
   ▼          ▼           ▼           ▼           ▼              ▼
┌────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐
│identity│ │ school  │ │ student  │ │attendance│ │ finance │ │communications│
│ (PH2-2)│ │ -service│ │ -service │ │ -service │ │ (PH2-3) │ │  (PH2-4)    │
└────────┘ └─────────┘ └──────────┘ └──────────┘ └─────────┘ └─────────────┘
                                          ▼
                                 ┌──────────────────┐
                                 │ assessment-service│
                                 └──────────────────┘

      ┌── academics (PH2-5 shell; future home of school/student/        ┐
      │   attendance/assessment after PH2-6→9 merges)                   │
      └─────────────────────────────────────────────────────────────────┘

                       │ (Kafka event bus, single broker today)
                       ▼
              ┌────────────────────┐
              │ reporting-service  │  (async Kafka consumer + HTTP)
              └────────────────────┘

   ┌─────────── observability (Phase 6 scaffold) ──────────────┐
   │ prometheus (scrapes gateway today) → grafana             │
   │ Sentry SDK hook in shared/app_factory (DSN env-driven)   │
   └───────────────────────────────────────────────────────────┘

   ┌─────────── data plane ─────────────────────────────────────┐
   │ Postgres 16 (one DB per service today; will consolidate)   │
   │ Redis 7 (rate-limit buckets + idempotency stores)          │
   │ Kafka 7.6 single broker + Zookeeper (HA pending Phase 5)   │
   │ pg-backup container: daily pg_dump → named volume          │
   └────────────────────────────────────────────────────────────┘
```

## 2. What's where

### Services (port → role)
- `identity` (8001) — auth, RBAC, sessions, password reset, preferences. Renamed from `auth-service` in PH2-2.
- `school-service` (8002) — schools, classes, subjects, terms, geo, internal teacher-class authz endpoint. PH2-6 folds into `academics`.
- `student-service` (8003) — students, parents, enrollments, internal parent-child authz endpoint. PH2-7 folds into `academics`.
- `attendance-service` (8004) — daily attendance, sync engine, trend queries. PH2-8 folds in.
- `finance` (8005) — fees structures, invoices, payments, Paynow integration. Renamed from `fees-service` in PH2-3.
- `communications` (8006) — announcements, outbox, WhatsApp webhook. Renamed from `communication-service` in PH2-4. Notification-worker code now lives here under `app/workers/`.
- `assessment-service` (8008) — assessments, marks, gradebook queries. PH2-9 folds into `academics`.
- `reporting-service` (8007) — Kafka consumer + read-only projections. PH2-11 strips its HTTP routes.
- `academics` — **shell only today** (PH2-5). PH2-6→9 populate it.
- `api-gateway` (8000) — single ingress for everything above.
- `notification-worker` — long-running dispatcher reading the comms outbox.
- `pg-backup` — `pg_dump` on a 24h interval; 14-snapshot retention.
- `prometheus` (9090), `grafana` (3030) — observability scaffold.

### Shared library (`shared/eduzim_shared/`)
- `app_factory.create_app()` — FastAPI factory with structured logging, X-Request-Id middleware, error envelope handlers, **graceful-shutdown lifespan** (INFRA-022), and **Sentry init** (INFRA-010) when `SENTRY_DSN` set.
- `kafka/producer.EduZimProducer` — Kafka producer wrapper; registers itself with a process-wide flush hook so the lifespan can drain on SIGTERM.
- `idempotency.DbIdempotencyStore` — DB-backed idempotency for retryable writes.
- `errors`, `middleware`, `logging` — error envelope, request-id middleware, JSON logging.

### Frontend packages
- `@eduzim/ui` — 23 components including `Card`, `DataTable`, `Sheet`, `Tabs`, and (new in Phase 10) `LineChart`, `BarChart`, `PieChart`, `SparkLine` Recharts wrappers.
- `@eduzim/auth` — `AuthProvider`, `useAuth`, `RouteGuard`, in-memory access-token + httpOnly refresh cookie flow.
- `@eduzim/api-client` — typed fetch wrapper + mock-data mode.
- `@eduzim/offline-core` — IndexedDB-backed sync queue + cache for teacher-web's offline attendance writes.
- `@eduzim/themes` — purple-led tokens with Zimbabwe accent variants.

## 3. Locked architectural patterns

These are documented as ADRs under `docs/decisions/`:

| # | Decision |
|---|---|
| 001 | Audience priority: Teacher > Student > Parent > School Admin >> Ministry |
| 002 | Student shares the parent app (role-based show/hide) |
| 003 | v1 scope: ERP + thin learning layer |
| 004 | Integration-only via Provider interfaces — no native payments/SMS/content |
| 005 | AWS Cape Town for v1; ZW provider by Year 2; lawyer review pre-pilot |
| 006 | Consolidate from 8 to 4 services (+ async reporting consumer); see addendum for module map |
| 007 | Privacy-by-design — minimal-data, PIA-gated, DPO named |
| 008 | PWA in v1, teacher-native (React Native) as Phase 2 |
| 009 | Tenancy tiers — shared / dedicated / district |
| 010 | Offline conflict: LWW for attendance + marks; detect+manual for announcements + incidents |
| 011 | Recharts for daily users; ECharts for admin/Ministry roll-ups |
| 012 | Open core post-v1 — AGPL platform + commercial managed offering |
| 013 | Ministry as viewer + auditor only |

## 4. Cross-cutting

### Multi-tenancy
Every operational table carries `school_id`. Gateway extracts it from the JWT and injects via headers; downstream services scope every query. Cross-tenant tests are scheduled in Phase 4 (Q-006) — not yet automated at the time of writing.

### Authentication
JWT issued by `identity`, validated by `api-gateway`. Today every downstream service *also* validates the JWT itself — Phase 3 / BUG-007 strips that duplication and shifts services to trust gateway-injected headers exclusively.

### Authorization
- Coarse-grained: RBAC at the gateway (route → permission map).
- Cross-service fine-grained: `/internal/*` HTTP endpoints with `X-Internal-Token`. PH2-8 / PH2-9 replace these with in-process function calls inside `academics` (see `services/academics/app/services/authorization.py` — stubs today).

### Idempotency
- Attendance sync: `(school_id, device_id, sync_batch_id)` unique constraint.
- Payments: row-locking + `idempotency_key` per Paynow transaction.
- Marks bulk + announcements: `X-Request-Id` → `DbIdempotencyStore`.

### Offline writes
`@eduzim/offline-core` queues teacher-web attendance/marks/announcement writes to IndexedDB. Sync manager flushes on `online` event + every 30s. Each enqueued action carries `device_id` + `sync_batch_id` so the server-side idempotency above prevents double processing.

### Secrets
- No defaults in service `config.py` after BUG-003/004 fix — every service requires `JWT_SECRET_KEY` and (where applicable) `INTERNAL_SERVICE_TOKEN` from env.
- `docker-compose.yml` uses `${VAR:?...}` interpolation — `docker compose up` fails fast if env missing.
- `scripts/bootstrap-secrets.sh` generates strong `.env` for local dev.
- Production wiring to AWS Secrets Manager / Vault: Phase 5 / 17.

## 5. What's in flight / deferred

See `task.md` § Phases for the exhaustive list. Highest-impact deferred items:

- **PH2-6 → PH2-12**: actual service merges into `academics`, gateway cutover, cleanup. Major overhaul; tracked.
- **Phase 3**: gateway-headers-only auth. Will be done on the consolidated 4-service shape, not the current 8-service shape.
- **Phase 5**: Postgres HA / Kafka 3-broker KRaft / Redis Sentinel / TLS between services. Multi-week infrastructure work.
- **Phase 7**: real 24-hour seeded load test with chaos. Phase 5 HA must land first to be useful.
- **Phase 8**: tenancy-tier query routing.
- **Phase 9**: full audit-log wiring across services; data-export + right-to-delete endpoints.
- **Phase 11 → 15**: persona feature build-out (teacher daily reality, parent payments online, admin HR, learning layer).
- **Phase 16**: OpenAPI + MCP + Provider SDK publication.
- **Phase 17**: CI/CD + staging + canary deploy pipeline.
- **Phase 18**: open-source release.
