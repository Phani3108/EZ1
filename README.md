# EduZim Platform

School management platform for Zimbabwe's education sector. Three web apps (admin, teacher, parent / student) on top of a Python microservices backend.

> **Live build state**: see [`STATUS.md`](./STATUS.md) for the honest "what's actually working" snapshot and [`task.md`](./task.md) for the full backlog with every closed and deferred item.
> Architecture decisions live in [`docs/decisions/`](./docs/decisions/).

<p align="center">
  <img src="docs/screenshots/admin-02-dashboard.png" width="32%" alt="Admin Dashboard"/>
  <img src="docs/screenshots/teacher-02-today.png" width="32%" alt="Teacher Today"/>
  <img src="docs/screenshots/parent-02-home.png" width="32%" alt="Parent Home"/>
</p>

---

## Where the project is

| Phase | Scope | State |
|---|---|---|
| **1–8** | Foundations: identity, school + students + attendance, fees, communications, reporting consumer, RBAC, gateway, tenancy tiers, data-rights exports | ✅ closed |
| **9 + PH9-6** | Privacy + audit log. `AuditLogMixin` substrate + `record_audit_event` wired across academics + finance + communications + identity. Three browse endpoints under `school:manage`. Privacy-at-audit invariants enforced via red-flag tests (bodies / amounts / file names / response values per-domain). | ✅ closed |
| **10** | Charts. Recharts wrappers for line / bar / pie / spark + ECharts wrappers (heatmap, Zimbabwe geomap, sankey) under a separate `@eduzim/ui/echarts` subpath, lazy-loaded via `next/dynamic`. | ✅ closed |
| **11 (a–f)** | **Teacher daily workflow**, 19 backend domains + 7 consolidated teacher-web pages: bulk attendance polish (T-001), period-based attendance (T-002), offline roster cache + offline badge (T-014, closes BUG-010), parent-teacher messaging (T-011), polymorphic file attachments (T-008), gradebook cross-assessment matrix (T-015), comment bank (T-007), MediaRecorder voice notes (T-009), school periods + lesson plans + formatives + exam seat plans (Phase 11d), behaviour incidents + substitute mode + homework (Phase 11e), co-teacher + HoD + CPD + self-eval (Phase 11f). | ✅ closed |
| **12 (a–g)** | **Parent + student in shared parent-web** with provider abstractions. Role-aware nav + ChildSwitcher (12a). PaymentProvider + per-school config + manual-confirm (12b). NotificationProvider per channel + per-school config (12c). Performance opt-out + school events (12d). Conferences + permission slips + grievances + transport (12e). Meal credit + donations + newsletter + gallery + sibling discount (12f). Student-role surface with `/schedule`, `/marks`, `/assignments` (12g). | ✅ closed |
| **13+** | School admin operational depth, ministry layer, Phase 15 learning content. | planned (`task.md` §13–§15) |

**Test totals across the platform** as of the most recent regression sweep:

| Layer | Tests | Notes |
|---|---|---|
| academics | 342 | Phase 11/12 domain models |
| api-gateway | 105 | RBAC + circuit breaker + rate-limit |
| communications | 114 | Messaging + notification providers + attachments |
| finance | 79 | Payment provider abstraction + manual confirm |
| identity | 28 | JWT + role-based auth |
| reporting-service | 51 | Kafka consumer projections |
| teacher-web | 332 | Vitest source-pattern + i18n parity |
| **Total** | **1,051** | |

---

## Architecture

- **Frontend**: three Next.js 15 PWAs (admin-web, parent-web, teacher-web) sharing `@eduzim/ui`, `@eduzim/auth`, `@eduzim/api-client`, `@eduzim/offline-core`. Recharts is the everyday chart wrapper; ECharts is lazy-loaded under a separate subpath only where the heatmap / geomap / sankey is needed.
- **Backend**: Python (FastAPI) microservices behind an internal `api-gateway`. The four post-PH2-12 services are `identity`, `academics`, `finance`, `communications`. `reporting-service` is a pure Kafka consumer (no HTTP) that builds projections into `reporting_db`. ADR 006 documents the consolidation rationale.
- **Provider abstractions** (Phase 12, DEC-004): `PaymentProvider` (Paynow + ManualHandover impls) in finance; `NotificationProvider` per channel (SMS / Push / Email / WhatsApp — AfricasTalking, FCM, SendGrid, Meta Cloud + per-channel manual fallback) in communications. Per-school config tables drive which provider serves which school.
- **Infra**: PostgreSQL behind PgBouncer (transaction mode), Redis (rate-limit + idempotency cache), Kafka (domain events + reporting projections), Prometheus (metrics endpoints on every service).
- **Audit substrate** (ADR 018): one shared `AuditLogMixin` in `eduzim_shared.audit` + `record_audit_event(...)` helper. Per-service `audit_log` table; three admin-only browse endpoints (`/api/v1/audit-log`, `/api/v1/fees/audit-log`, `/api/v1/comm/audit-log`). Privacy invariant: `target` carries ids; `details` carries event-meta only — bodies / file names / response values / phrase text / messages never logged. Money-move events log the amount explicitly because that IS the audit story.

---

## Quick start (local dev)

### Prerequisites
- Docker Desktop (or compatible)
- Node ≥ 18, pnpm ≥ 9
- Python 3.11 (only needed if you run service tests outside Docker)

### One-time bootstrap

```bash
# Generate dev secrets (JWT_SECRET_KEY, INTERNAL_SERVICE_TOKEN)
bash scripts/bootstrap-secrets.sh

# Install JS workspace
pnpm install
```

### Bring the backend up

```bash
docker compose up -d
```

This starts (under `eduzim-*` container names):

- `postgres` (with `auth_db`, `academics_db`, `fees_db`, `comms_db`, `reporting_db`)
- `pgbouncer` (transaction-mode pooler at `:6432` internally)
- `zookeeper` + `kafka`
- `redis`
- `migrations` (one-shot Alembic per-service runner; exits 0)
- `identity`, `academics`, `finance`, `communications`, `reporting-service`
- `api-gateway` (the only externally addressable HTTP — `:8000`)
- `prometheus` for metrics

Wait ~20s on first run, then:

```bash
curl http://localhost:8000/health
# → {"status":"healthy","service":"api-gateway","version":"1.0.0"}
```

Seed baseline roles + permissions:

```bash
bash scripts/seed-baseline.sh
```

### Bring the three frontends up

```bash
pnpm dev:admin     # admin-web on :3000
pnpm dev:parent    # parent-web on :3001
pnpm dev:teacher   # teacher-web on :3002
```

Each is a `next dev` server. Hot-reload on save; first compile of a route takes a few seconds. If `:3000` is already taken on your host, pick an alternate port: `pnpm exec next dev --port 3003` inside `apps/admin-web/`.

### Port-conflict cheat sheet

If your host already has Postgres / Redis on the canonical ports, `docker-compose.yml` remaps:

| Service | Container port (internal) | Host port (mapped) |
|---|---|---|
| postgres | 5432 | **15432** |
| redis | 6379 | **6380** |
| api-gateway | 8000 | 8000 |
| admin-web | — | 3000 (next dev) |
| parent-web | — | 3001 (next dev) |
| teacher-web | — | 3002 (next dev) |

Services inside the Docker network still address `postgres:5432` and `redis:6379` — only the host-side mappings shifted.

### Mock-data mode (no backend)

```bash
NEXT_PUBLIC_MOCK_DATA=true pnpm dev:admin
NEXT_PUBLIC_MOCK_DATA=true pnpm dev:teacher
NEXT_PUBLIC_MOCK_DATA=true pnpm dev:parent
```

Mock data covers 20 students / 10 parents / 4 classes / 6 subjects, consistent across all three apps. Useful for screenshotting and UI development without the docker stack.

### Tear down

```bash
docker compose down            # stop services, keep volumes
docker compose down -v         # also wipe Postgres + Kafka + Redis state
```

---

## Project structure

```
apps/
  admin-web/         # School admin dashboard (Next.js, :3000)
  parent-web/        # Parent + student app (Next.js, :3001)
    src/app/(parent)/
      home/  attendance/  fees/  announcements/   # core (pre-Phase-12)
      messages/  events/  connect/  more/         # Phase 12 parent surface
      schedule/  marks/   assignments/            # Phase 12g student surface
  teacher-web/       # Teacher dashboard (Next.js, :3002)
    src/app/(teacher)/
      today/  classes/[id]/  announcements/
      messages/                                    # Phase 11b T-011
      gradebook/                                   # Phase 11c T-015
      plan/                                        # Phase 11d (periods, lessons, formatives, seat plans)
      student-life/                                # Phase 11e (incidents, substitute, homework)
      professional/                                # Phase 11f (CPD + self-eval)

packages/
  api-client/        # Typed fetch wrapper + mock data
  auth/              # Token store + RouteGuard
  ui/                # Shared components (cards, buttons, forms, charts)
                     # charts/ → Recharts; charts/echarts → ECharts (subpath)
  offline-core/      # IndexedDB queue + sync engine + cache

services/
  identity/                # Authentication, RBAC, refresh tokens
  academics/               # Schools, students, parents, enrollments,
                           #   attendance (with period_number), assessments,
                           #   gradebook, comment bank, planning (periods,
                           #   lesson plans, formatives, seat plans),
                           #   student-life (incidents, substitute, homework),
                           #   org (HoD, CPD, self-eval, co-teacher),
                           #   parent-life (events, conferences, slips,
                           #   grievances, transport, meals, donations,
                           #   newsletter, gallery, sibling discount)
  finance/                 # Fees, invoices, payments, PaymentProvider
                           #   abstraction (Paynow + Manual), PDF receipts
  communications/          # Announcements + NotificationOutbox + WhatsApp,
                           #   parent-teacher messaging (threads + messages,
                           #   redaction-as-soft-delete), polymorphic
                           #   attachments, NotificationProvider abstraction
                           #   per channel
  reporting-service/       # Pure Kafka consumer (no HTTP). CLI tools under
                           #   cli/ replace the legacy /reports/consume +
                           #   /reports/rebuild HTTP endpoints.
  api-gateway/             # JWT validation, RBAC routing, rate-limit,
                           #   circuit breaker, metrics, request-id propagation
  migrations/              # One-shot Alembic runner — applies every service's
                           #   versions/ folder against the per-service DB

shared/
  eduzim_shared/
    audit.py               # AuditLogMixin + record_audit_event + Event constants
    auth.py                # JWT helpers shared across services
    tenancy.py             # Multi-tenant DB router (shared / dedicated / district)
    metrics.py             # Prometheus instrumentation
    redis_client.py        # Redis url parser + connection helper
    idempotency.py         # X-Request-Id-keyed dedup store

infra/observability/       # Prometheus rules + Grafana dashboards
docker-compose.yml         # Default dev stack
docker-compose.chaos.yml   # toxiproxy overlay for chaos profile
docker-compose.ha.yml      # HA addendum
docker-compose.observability.yml
docker-compose.prod.yml    # production-shape (TLS, cookie-secure, secrets)
```

---

## Provider patterns (Phase 12 / DEC-004)

Both finance and communications introduced a **per-school provider** layer rather than hard-coding integrations:

```
finance/app/providers/
  payment_provider.py      # Protocol: initiate / status / confirm / webhook
  paynow.py                # Adapter — legacy direct route stays during unification
  manual.py                # ManualHandoverProvider (school records off-platform)
  registry.py              # get_provider_for_school() reads SchoolPaymentConfig

communications/app/providers/
  notification_provider.py # Protocol: send / status (per channel)
  sms_providers.py         # AfricasTalking + ManualSmsProvider
  push_providers.py        # FCM + ManualPushProvider
  email_providers.py       # SendGrid + ManualEmailProvider
  whatsapp_providers.py    # MetaCloud + ManualWhatsAppProvider
  registry.py              # get_provider_for_school_channel() reads SchoolNotificationConfig
```

A school picks its provider per channel via the admin endpoints (`PUT /fees/payment-config`, `PUT /comm/notification-config`). Test pilots without a paid gateway use the `manual` providers — the system records intent + returns instructions; an admin marks delivery confirmed externally.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript |
| UI library | Custom `@eduzim/ui` (Tailwind + class-variance-authority) |
| Charts | Recharts (default), ECharts (lazy-loaded subpath) |
| Auth | JWT + httpOnly refresh cookie via `@eduzim/auth` |
| API client | Typed fetch wrapper via `@eduzim/api-client` |
| Offline | IndexedDB-backed queue + cache via `@eduzim/offline-core` |
| i18n | `next-intl` — English, Shona, Ndebele |
| Backend | FastAPI, SQLAlchemy, Alembic |
| DB | PostgreSQL 16 behind PgBouncer (transaction-mode) |
| Cache / rate-limit | Redis 7 |
| Event bus | Kafka (KRaft on the roadmap; Zookeeper today) |
| Observability | Prometheus + Grafana (per-service `/metrics`) |
| Tests | Vitest (web), pytest + FastAPI TestClient (services), Playwright (E2E — staged for Phase 11g sweep) |

---

## 📸 Portal screenshots

These captures cover the pre-Phase-11 baseline. New pages (gradebook, plan, student-life, professional, messages, events, connect, more) ship without screenshots — the Phase 11g sweep adds Playwright captures for each.

### 🏫 Admin portal

<p align="center">
  <img src="docs/screenshots/admin-01-login.png" width="31%" alt="Admin Login"/>
  <img src="docs/screenshots/admin-02-dashboard.png" width="31%" alt="Admin Dashboard"/>
  <img src="docs/screenshots/admin-03-students.png" width="31%" alt="Students List"/>
</p>
<p align="center">
  <em>Login &nbsp;·&nbsp; Dashboard &nbsp;·&nbsp; Students</em>
</p>

<p align="center">
  <img src="docs/screenshots/admin-05-attendance.png" width="31%" alt="Attendance"/>
  <img src="docs/screenshots/admin-06-assessments.png" width="31%" alt="Assessments"/>
  <img src="docs/screenshots/admin-10-language-switch.png" width="31%" alt="Language Switch"/>
</p>
<p align="center">
  <em>Attendance &nbsp;·&nbsp; Assessments &nbsp;·&nbsp; Language Switch</em>
</p>

### 📚 Teacher portal

<p align="center">
  <img src="docs/screenshots/teacher-01-login.png" width="31%" alt="Teacher Login"/>
  <img src="docs/screenshots/teacher-02-today.png" width="31%" alt="Teacher Today"/>
  <img src="docs/screenshots/teacher-03-classes.png" width="31%" alt="My Classes"/>
</p>

<p align="center">
  <img src="docs/screenshots/teacher-05-announcements.png" width="31%" alt="Announcements"/>
  <img src="docs/screenshots/teacher-06-sync-center.png" width="31%" alt="Sync Center"/>
  <img src="docs/screenshots/teacher-07-language-switch.png" width="31%" alt="Shona Language"/>
</p>

### 👨‍👩‍👧 Parent portal

<p align="center">
  <img src="docs/screenshots/parent-01-login.png" width="31%" alt="Parent Login"/>
  <img src="docs/screenshots/parent-02-home.png" width="31%" alt="Parent Home"/>
  <img src="docs/screenshots/parent-03-attendance.png" width="31%" alt="Attendance"/>
</p>

<p align="center">
  <img src="docs/screenshots/parent-04-fees.png" width="31%" alt="Fees"/>
  <img src="docs/screenshots/parent-05-announcements.png" width="31%" alt="Announcements"/>
  <img src="docs/screenshots/parent-06-language-switch.png" width="31%" alt="Language Switch"/>
</p>

---

## Documentation

- [`STATUS.md`](./STATUS.md) — current honest state of every persona, claim, and infrastructure track
- [`task.md`](./task.md) — phase-by-phase backlog with closure evidence on every item
- [`VISION.md`](./VISION.md) — long-term product vision
- [`docs/decisions/`](./docs/decisions/) — Architecture Decision Records (ADRs 001 through 018)
- [`docs/runbooks/`](./docs/runbooks/) — operator playbooks (tenancy upgrades, audit retention, secrets rotation, chart-bundle budget, Phase 7 load tests, etc.)
- [`docs/compliance/`](./docs/compliance/) — PIA, privacy policy, retention policy, data-minimisation audit

## License

Proprietary — © EduZim contributors. Open-sourcing is a Phase-12+ strategic decision (`task.md` Debate 10).
