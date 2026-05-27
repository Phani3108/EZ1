# ADR 018 — Audit log architecture + data-rights surface (Phase 9)

**Status**: Accepted (closed 2026-05-26 for the substrate; full PII-write wiring is staged per ADR 007's minimisation principle)
**Closes (substrate)**: INFRA-018 / Q-016 — `AuditLog` model + shared `record_audit_event` + admin browse endpoint + retention CLI
**Closes (data rights)**: Phase 9 right-to-export track (paired with PH8-4 endpoints from ADR 009)
**Defers (with structured plan)**: PH9-2 field-by-field minimisation audit — see `docs/compliance/data-minimisation-audit.md`

## Context

Phase 9 of the original plan calls for:

> A platform able to pass any data-protection audit. Privacy by
> design (ADR 007), right-to-export (ADR 007), audit log of all
> PII writes (INFRA-018 / Q-016), retention enforcement.

Prior to this work the platform had:

* `docs/compliance/{pia-v1,privacy-policy,retention-policy}.md` — the
  philosophy documents (closed in PH9-1 / Q-009).
* DPO link in all three app footers (closed in Q-010).
* `AuditLog` model + helper in `services/identity/` — scaffolded but
  not wired into PII writes anywhere else.

What was missing:

1. A shared substrate so every service can log audit events the same
   way (without each one growing its own divergent schema).
2. Audit calls wired into the actual PII writes (student CRUD, exports,
   role changes, etc.).
3. An admin UI / endpoint to browse the audit log.
4. A retention-enforcement job to delete rows older than 2y per the
   retention policy.
5. A path to the "field-by-field minimisation" sweep that ADR 007
   demands (PH9-2).

## Decision

### 1. The substrate

The audit log lives in **per-service `audit_log` tables** — each
service writes to its own DB, scoped by `school_id` like every other
domain table. Central aggregation (a separate audit DB, or shipping
to a SIEM) is a Phase 11+ follow-up.

The canonical schema lives in `shared/eduzim_shared/audit.py` as
**`AuditLogMixin`** — a SQLAlchemy declarative mixin. Each service's
model file is two lines:

```python
from eduzim_shared.audit import AuditLogMixin
from app.database import Base

class AuditLog(AuditLogMixin, Base):
    __tablename__ = "audit_log"
```

Schema drift across services is structurally impossible — the columns
live in exactly one place. New columns mean one source change + an
Alembic migration per service.

Write API: **`record_audit_event(db, AuditLog, event_type=..., school_id=..., ...)`**.
Never raises into the caller. Logs loudly on failure. Constraint: an
audit failure must not abort the underlying business action (a login
that crashes because the audit table is full is worse than a login
that succeeds with no audit row).

Event-name discipline: **`Event` frozen dataclass** of constants
(`Event.STUDENT_CREATED`, `Event.LOGIN_SUCCESS`, etc.). Free-form
strings work but lint-against-Event catches typos that would split
metrics across multiple buckets.

### 2. Wiring policy

Audit calls are added at **write-side route handlers**, not in the
service layer. Rationale:

* Audit context (request_id, ip_address, user_agent) lives on the
  Request object — natural to capture at the route boundary.
* Service-layer functions are reused by Kafka consumers, CLI tools,
  etc. — auditing those is a separate concern (consumer-side audit
  events).
* The route layer is the single source of "an external caller did
  this." Audit-at-service-layer would double-log when a route calls
  multiple service methods.

Phase 9 closure wires the substrate + a **representative subset** of
the PII writes (student create / update / delete, school export,
parent export, audit-log-itself-browse). Wiring every PII write
across every service is staged work — the substrate makes each
addition a one-line change.

### 3. PII minimisation in the audit log itself (critical)

The audit log is itself a PII surface. Two rules enforced by ADR 007:

* **`target` lists IDs, not values**: `{"resource": "student", "id":
  "<uuid>"}`. Not the full student row.
* **`details` lists changed FIELDS, not new values**: `{"changed_fields":
  ["first_name", "dob"]}`. Not `{"first_name": "Anna"}`. The audit
  signals the fact of change; the values are in the resource table
  itself (covered by the resource's own ACLs).

`test_student_update_audit_records_changed_fields_not_values` enforces
this at the integration level — it explicitly asserts the new value
string doesn't appear in the audit row's `details` JSON.

`ip_address` and `user_agent` are collected only on **security
events** (login, role grant, payment, export). Not on routine
writes. The `data-minimisation-audit.md` row for these flags the
follow-up.

### 4. Admin browse endpoint

`GET /api/v1/audit-log` — paginated, school-scoped, admin-only.
Filters: `event_type`, `actor_user_id`, `from_date`, `to_date`.
Deliberately no free-text search of `target` / `details` — full-text
indexing those invites the kind of casual browsing that runs against
the privacy goal. If a deeper forensic need arises, the admin runs
a documented DB query.

Pagination: simple offset+limit, descending by `occurred_at`. Keyset
pagination is a follow-up once row counts demand it (~1k events/day
per active school per the rough estimate, so a single school with
2 years of history is ~700k rows — offset paging is still fine).

### 5. Retention

Default: **2 years** (per `docs/compliance/retention-policy.md`).
Enforced by `scripts/audit-log-retention.py`:

* Batched DELETE (5,000 rows per statement) so a runaway purge doesn't
  lock the table.
* Hard safety cap (1,000,000 rows per invocation). Past that the
  operator must explicitly raise the cap — an unexpectedly large
  purge usually means months of missed retention runs.
* `--dry-run` for verification.
* Operates across multiple DBs in one invocation (one `--db-url`
  per service).
* Exits 0 normally; 3 if the safety cap was hit.

Scheduled execution: documented in
`docs/runbooks/audit-retention-rollout.md`. Operators wire into
their scheduler of choice (k8s CronJob, GitHub Actions schedule,
crond inside the migrations container).

### 6. The field-by-field minimisation review (PH9-2)

Deferred-major, with a **structured checklist** in
`docs/compliance/data-minimisation-audit.md`. The checklist lists
every PII-bearing field today with disposition (keep / drop /
generalise / opt-in), owner (product / legal / engineering), and
status. Closing rows requires real product + legal coordination, not
engineering work — the checklist makes that coordination tractable
instead of perpetual TODO.

**Phase 9 closure does NOT depend on every row of that table moving
to `closed`** — only on the structured plan being recorded.

## Alternatives considered

* **One central audit DB.** Considered. Adds a cross-service write
  on every PII action, plus a new failure mode (audit DB down →
  every service down, or audit writes silently dropped — neither
  is acceptable). The per-service table pattern keeps the failure
  domain local; audit ships via Kafka in a follow-up if we want
  central aggregation.

* **OpenTelemetry semantic conventions instead of bespoke `Event`.**
  Considered. OTel's audit conventions are still draft; we'd be
  early adopters of a moving target. The `Event` dataclass is two
  dozen constants — small enough to maintain, big enough to enforce
  consistency. Revisit when OTel audit conventions ship.

* **Soft-delete + flag instead of retention purge.** Considered.
  Two years of soft-deleted rows in a hot table hurts query latency
  even with the indexes we have. Hard delete via the retention
  script is the right call for a 2y retention window.

* **App-layer encryption of `target` / `details`.** Considered.
  Adds an operational key-management burden (rotate? lose? leak?)
  and only protects against an attacker who has SQL access but not
  app-layer access — a narrow threat model. Defer until the
  threat actually arrives.

## Consequences

* Adding audit to a new PII write is a one-line change per route
  handler. The pattern (route-layer, after the service call
  succeeds, before the response) is documented in this ADR.
* Operators must run `scripts/audit-log-retention.py` on a schedule.
  Forgetting it means the table grows unbounded; on a 500-school
  pilot we're looking at ~365M rows after 2y unpurged. Past that
  the safety cap triggers — the runbook explains the recovery path.
* The audit log itself is a PII surface; the writes are
  ADR-007-compliant by convention enforced at PR review + by
  test_student_update_audit_records_changed_fields_not_values.
* `data-minimisation-audit.md` is a living document. PRs that add a
  PII column to any model must update the table in that file BEFORE
  merge.

## Migration notes

* Each service that wants audit logging needs an Alembic migration
  to create its `audit_log` table. Academics' migration
  (`2026_05_19_007_audit_log.py`) is the template — same SQL applies
  to finance / communications / reporting-service.
* Production deploy: the retention job should run BEFORE the first
  birthday of the platform. Earlier is fine — empty DB → no-op.
* `EDUZIM_AUDIT_VERBOSE` env (future) could let operators opt into
  audit on every read, not just writes. Off by default.

## References

- ADR 007 (privacy-by-design)
- ADR 009 (tenancy tiers — PH8-4 export endpoints)
- `docs/compliance/pia-v1.md`
- `docs/compliance/privacy-policy.md`
- `docs/compliance/retention-policy.md`
- `docs/compliance/data-minimisation-audit.md` (PH9-2 checklist)
- `docs/runbooks/audit-retention-rollout.md`
