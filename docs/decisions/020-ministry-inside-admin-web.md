# ADR 020 — Ministry surface lives inside admin-web (not a separate ministry-web PWA)

**Status**: Accepted 2026-05-27
**Closes**: Phase 14 / M-001 — Ministry role provisioning + decision on app placement
**Pairs with**: ADR 013 (Ministry is viewer + auditor only), ADR 011 (charts split: ECharts for Ministry dashboards)

## Context

Phase 14 introduces the Ministry of Primary and Secondary Education
(MoPSE) persona. Ministry is a **viewer + auditor only** — explicitly
not an operator (DEC-013). Their entire job is to look at
cross-school aggregations: District/Province/National roll-ups,
compliance dashboards, dropout heatmaps, comparative tables, donor
impact, and UNESCO/UNICEF export templates.

Three deployment shapes were on the table:

### Option A — Standalone `apps/ministry-web`
A new Next.js PWA dedicated to the Ministry persona.

- **For**: Clean separation. Different design language possible.
  Can be hosted on a Ministry-controlled domain. Future regulator
  audits can find the surface in one place.
- **Against**: Three more things to maintain (Dockerfile, dev port,
  CI build job, deploy pipeline). Three more code paths to keep
  i18n + auth + token-refresh in sync with. The same engineer who
  fixed a bug in admin-web has to remember to apply it here.
  Justified by daily-user count this app does not have — Ministry
  has maybe 30 users nationally; admin-web has thousands.

### Option B — `/ministry` route group inside `apps/admin-web` (CHOSEN)
A Ministry-role-gated route group living next to School Admin
routes in the existing admin-web app. Layout-level role guard hides
all operational verbs. Nav uses a distinct Ministry colorway so
users know which mode they're in.

- **For**: Zero new infra. Shared auth, shared i18n, shared chart
  primitives (recharts for simple bars; lazy-loaded `@eduzim/ui/echarts`
  for heatmaps / sankey / geomap per ADR 011). Same gateway, same
  RBAC map, same audit pipeline. Operational burden ≈ free.
- **Against**: Admin-web is now serving two distinct personas;
  reviewers must read role-guards carefully to avoid leaking
  operational UI to Ministry users. Mitigated by a single layout-
  level guard and a route-layer Ministry-role assertion on every
  Ministry endpoint (defence-in-depth).

### Option C — Mode-switch inside admin-web (no route separation)
A toggle in the user menu that re-skins the existing admin-web
pages with Ministry data.

- **For**: Minimal code.
- **Against**: Conflates two mental models. School Admin's "Add
  student" button next to Ministry's "National dropout heatmap" is
  confusing. The /ministry route group from Option B is cheap; we
  pay it.

## Decision

**Option B** — `/ministry` route group inside `apps/admin-web`,
gated by the new `Ministry` role and unlocked by the new
`ministry:read` permission. No separate PWA.

The Ministry persona is so different that we need a route boundary,
but not so heavily-used that we need a separate deployable. A
sub-app inside admin-web is the right grain.

## Implementation

### Identity / RBAC
* `scripts/seed-baseline.sh` adds:
  - Role `Ministry` (UUID `55555555-5555-5555-5555-555555555555`)
  - Permission `ministry:read` (UUID
    `89999999-9999-9999-9999-999999999999`)
  - One `role_permissions` row linking them.
* The Ministry role grants **only** `ministry:read`. Other
  permissions (`school:manage`, `student:write`, `fees:write`, …)
  are never associated with this role, by policy.

### Gateway
* New SERVICE_ROUTES prefix `/api/v1/ministry → academics`.
* New RBAC_MAP entries: every Ministry path is `(GET, …,
  ministry:read)`. No POST/PUT/DELETE entries exist — Ministry has
  no write surface anywhere.

### Academics service (cross-school)
* New router `services/academics/app/api/ministry_routes.py`.
* Every endpoint is a `GET`.
* The route layer asserts `Ministry` role explicitly via
  `_require_ministry` — defence-in-depth in case the gateway RBAC
  is ever misconfigured.
* The actor's `X-School-Id` header is intentionally **ignored** on
  these endpoints. Cross-school is the whole point.
* Every aggregation call is audit-logged.

### admin-web (Phase 14e — separate task)
* Route group `app/(ministry)/ministry/**`.
* Layout-level role guard: if `actor.role !== "Ministry"`, redirect.
* Distinct nav (Dashboard, District, Province, National, Compliance,
  Drop-out, Subjects, Resources, Comparative, Policy, Donors,
  Exports).
* No `<Button>` components with mutation verbs anywhere in the
  Ministry tree.

## Cross-school audit row constraint

The shared `AuditLog` model carries `school_id NOT NULL` (legacy
invariant — every domain row has a tenant). Ministry events have
no single tenant. Two options:

1. Drop the NOT NULL on `school_id` (intrusive migration; affects
   every audit consumer; bad blast radius).
2. Use a **deterministic cross-school sentinel UUID** so the row
   still satisfies NOT NULL and can be filtered out of per-school
   audit dashboards with a single WHERE predicate.

We chose option 2. The sentinel is
`eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee`. All-zeros UUID was tested
first and rejected — it round-trips poorly through SQLAlchemy's
`UUID(as_uuid=True)` on SQLite (the column value can come back as
an integer rather than the UUID, breaking `uuid.UUID(hex=…)` on
read). Any non-zero deterministic UUID would work; we picked the
all-`e` pattern because it is visually obvious in raw audit dumps.

Any future "audit by school" dashboard must filter out
`school_id = 'eeeeeeee-…-eeeeeeeeeeee'`. Documented in this ADR
and called out in the route module's docstring.

## Audit invariants (per ADR 018)

Ministry reads are now audit-logged. The contract is:

* `event_type` — `"ministry.<verb>.<noun>"` (e.g.,
  `"ministry.enrolment.read"`, `"ministry.attendance.read"`).
* `target` — the **scope label only**: `"national"`,
  `"province:HRE"`, `"district:hre-cn|province:*"`, etc. No row
  IDs. No PII.
* `details` — `{"endpoint": <event_type>, "rows": <int>}`. No
  school names, no district names, no province names, no actor
  PII. Test coverage in
  `services/academics/tests/test_ministry.py::TestMinistryAuditNoPII`
  enforces this with a string-membership check against every
  school+district name the seed produces.

## Consequences

### Positive
* One app to deploy, one CI pipeline, one image to scan.
* Ministry inherits all admin-web's i18n + auth + offline
  middleware automatically.
* Reviewers can audit the Ministry surface by reading two files
  per release: the layout guard + the academics ministry_routes.
* Adding the next aggregation endpoint is a single-PR change.

### Negative
* Admin-web's role gating is now load-bearing. A regression that
  removed the layout guard could leak operational UI to Ministry
  users. Mitigated by:
  - Route-layer Ministry-role assertion (defence-in-depth).
  - Explicit test that non-Ministry callers hit 403 even with
    `ministry:read` in their permission set.
  - PR template note (added in Phase 14e closeout): "If you
    touched a `(ministry)` route, did you re-verify the layout
    guard?"
* If we later need a totally separate Ministry domain (e.g.,
  `ministry.eduzim.zw` for political reasons), we'll factor out.
  The route layer is clean enough that the lift would be small
  (a few weeks).

## What this ADR does NOT decide

* Whether the actual Ministry dashboard UIs use ECharts or
  Recharts on a per-widget basis. ADR 011 already says ECharts
  for heatmaps / sankey / geomap; Recharts for line/bar. Phase
  14e picks per-page.
* Whether Ministry users authenticate with the same identity-
  service as school users or a separate IdP. v1 = same IdP,
  role-based; future addendum if MoPSE wants their own SSO.
* The compliance-report aggregation schema (Phase 14b — M-004).
  This ADR only covers M-001 + M-002 foundations.
